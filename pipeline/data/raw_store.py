"""Raw_Store (design § Raw_Store; Req 10.1, 10.4, 10.6-10.9).

Files in `pipeline/raw/` (gitignored, Req 10.2):

    ctgov_q1_page_001.json ...   scrubbed ClinicalTrials.gov pages, Q1
    ctgov_q2_page_001.json ...   scrubbed ClinicalTrials.gov pages, Q2
    places_page_001.json ...     PLACES pages
    manifest.json                written last; marks a complete fetch (Req 10.7)

Every file is written to a temporary name, then moved with `os.replace`.
`begin_network_run` deletes the manifest before anything else, so from that
moment until `finish_network_run` the store counts as incomplete. A failed run
therefore never leaves a usable offline cache (Req 10.8, 10.9).

Callers must scrub ClinicalTrials.gov pages before `write_page` (Req 3.2,
10.6). Error messages name files and sources only, never content (Req 3.3).
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from pipeline.data.contact_scrubber import RemovalCounts
from pipeline.errors import PipelineError

CTGOV_SOURCES = ("ctgov_q1", "ctgov_q2")
PLACES_SOURCE = "places"
SOURCES = CTGOV_SOURCES + (PLACES_SOURCE,)
MANIFEST = "manifest.json"
PLACES_PAGE_SIZE = 1000
FETCH_DATE_FORMAT = "%Y-%m-%dT%H:%M:%SZ"

# Source names as they appear in the manifest "pages" object (design § Raw_Store).
_MANIFEST_PAGE_KEYS = {"ctgov_q1": "ctgov_q1", "ctgov_q2": "ctgov_q2", "places": "cdc_places"}
CTGOV_LABEL = "ClinicalTrials.gov"
PLACES_LABEL = "PLACES"


def page_file_name(source: str, n: int) -> str:
    if source not in SOURCES:
        raise ValueError("unknown raw source %r" % source)
    if type(n) is not int or n < 1:
        raise ValueError("page number must be a positive integer")
    return "%s_page_%03d.json" % (source, n)


def format_fetch_date(fetch_date: datetime) -> str:
    return fetch_date.astimezone(timezone.utc).strftime(FETCH_DATE_FORMAT)


@dataclass
class RawCache:
    """A complete prior fetch, as read by `RawStore.load` (Offline_Mode)."""

    fetch_date: datetime
    q2_server_cutoff: bool
    urls: dict[str, list[str]]  # {"clinicaltrials_gov": [...Q1, ...Q2], "cdc_places": [...]}
    ctgov_q1_pages: list[dict]
    ctgov_q2_pages: list[dict]
    places_pages: list[list]
    contact_removals: RemovalCounts


class RawStore:
    def __init__(self, root: Path | str) -> None:
        self.root = Path(root)
        self._written: dict[str, int] = {s: 0 for s in SOURCES}

    # ---- network run -------------------------------------------------------

    def begin_network_run(self) -> None:
        """Invalidate the cache, then delete every page from earlier runs (Req 10.8)."""
        try:
            self.root.mkdir(parents=True, exist_ok=True)
            (self.root / MANIFEST).unlink(missing_ok=True)
            for pattern in ("ctgov_*_page_*.json", "places_page_*.json", ".*.tmp"):
                for path in self.root.glob(pattern):
                    path.unlink()
        except OSError as exc:
            raise PipelineError(
                "could not clear raw store %s (%s)" % (self.root, type(exc).__name__)
            ) from None
        self._written = {s: 0 for s in SOURCES}

    def write_page(self, source: str, n: int, obj: object) -> None:
        """Write one page before the next request (Req 10.1). Pages go in order from 1."""
        name = page_file_name(source, n)
        if n != self._written[source] + 1:
            raise PipelineError(
                "raw page %s written out of order (expected page %d)"
                % (name, self._written[source] + 1)
            )
        self._atomic_write(name, _dumps(obj))
        self._written[source] = n

    def finish_network_run(
        self,
        fetch_date: datetime,
        q2_server_cutoff: bool,
        urls: dict[str, list[str]],
        removal_counts: RemovalCounts,
    ) -> None:
        """Write manifest.json after both sources have finished (Req 10.7)."""
        ctgov_pages = self._written["ctgov_q1"] + self._written["ctgov_q2"]
        ctgov_urls = list(urls.get("clinicaltrials_gov", []))
        places_urls = list(urls.get("cdc_places", []))
        if (self._written["ctgov_q1"] < 1 or self._written["ctgov_q2"] < 1
                or self._written["places"] < 1):
            raise PipelineError("raw store manifest not written: a source has no pages")
        if len(ctgov_urls) != ctgov_pages or len(places_urls) != self._written["places"]:
            raise PipelineError(
                "raw store manifest not written: URL count does not match page count"
            )
        manifest = {
            "fetch_date": format_fetch_date(fetch_date),
            "q2_server_cutoff": bool(q2_server_cutoff),
            "urls": {"clinicaltrials_gov": ctgov_urls, "cdc_places": places_urls},
            "pages": {_MANIFEST_PAGE_KEYS[s]: self._written[s] for s in SOURCES},
            "contact_removals": removal_counts.to_log_dict(),
        }
        self._atomic_write(MANIFEST, _dumps(manifest))

    def _atomic_write(self, name: str, data: bytes) -> None:
        target = self.root / name
        tmp = self.root / (".%s.tmp" % name)
        try:
            self.root.mkdir(parents=True, exist_ok=True)
            with open(tmp, "wb") as fh:
                fh.write(data)
                fh.flush()
                os.fsync(fh.fileno())
            os.replace(tmp, target)
        except OSError as exc:
            try:
                tmp.unlink(missing_ok=True)
            except OSError:
                pass
            raise PipelineError(
                "could not write raw file %s (%s)" % (target, type(exc).__name__)
            ) from None

    # ---- offline run -------------------------------------------------------

    def load(self) -> RawCache:
        """Read a complete prior fetch, or stop naming each incomplete source (Req 10.4)."""
        problems: dict[str, list[str]] = {CTGOV_LABEL: [], PLACES_LABEL: []}
        manifest = self._read_json(MANIFEST)
        if not isinstance(manifest, dict):
            reason = "%s missing or unreadable" % MANIFEST
            problems[CTGOV_LABEL].append(reason)
            problems[PLACES_LABEL].append(reason)
            _raise_incomplete(self.root, problems)

        fetch_date = _parse_fetch_date(manifest.get("fetch_date"))
        cutoff = manifest.get("q2_server_cutoff")
        urls = manifest.get("urls")
        pages_meta = manifest.get("pages")
        removals = None
        try:
            removals = RemovalCounts.from_log_dict(manifest.get("contact_removals"))
        except ValueError:
            pass
        if fetch_date is None or type(cutoff) is not bool or removals is None:
            reason = "%s has no valid fetch_date, q2_server_cutoff or contact_removals" % MANIFEST
            problems[CTGOV_LABEL].append(reason)
            problems[PLACES_LABEL].append(reason)
        if not isinstance(urls, dict):
            urls = {}
        if not isinstance(pages_meta, dict):
            pages_meta = {}

        loaded: dict[str, list] = {}
        for source in SOURCES:
            label = PLACES_LABEL if source == PLACES_SOURCE else CTGOV_LABEL
            count = pages_meta.get(_MANIFEST_PAGE_KEYS[source])
            if type(count) is not int or count < 1:
                problems[label].append("%s: no page count in %s" % (source, MANIFEST))
                continue
            pages = []
            for n in range(1, count + 1):
                name = page_file_name(source, n)
                page = self._read_json(name)
                ok = (isinstance(page, list) if source == PLACES_SOURCE
                      else isinstance(page, dict) and isinstance(page.get("studies"), list))
                if not ok:
                    problems[label].append("%s missing or invalid" % name)
                    break
                pages.append(page)
            else:
                last = pages[-1]
                if source == PLACES_SOURCE:
                    if len(last) >= PLACES_PAGE_SIZE:
                        problems[label].append(
                            "last page %s has %d records" % (page_file_name(source, count), len(last))
                        )
                elif last.get("nextPageToken") not in (None, ""):
                    problems[label].append(
                        "last page %s has a nextPageToken" % page_file_name(source, count)
                    )
            loaded[source] = pages

        ctgov_urls = urls.get("clinicaltrials_gov")
        places_urls = urls.get("cdc_places")
        ctgov_expected = sum(
            pages_meta.get(s) for s in CTGOV_SOURCES if type(pages_meta.get(s)) is int
        )
        if not _is_str_list(ctgov_urls) or len(ctgov_urls) != ctgov_expected:
            problems[CTGOV_LABEL].append("saved URL list does not match the page count")
        if not _is_str_list(places_urls) or len(places_urls) != pages_meta.get("cdc_places"):
            problems[PLACES_LABEL].append("saved URL list does not match the page count")

        if problems[CTGOV_LABEL] or problems[PLACES_LABEL]:
            _raise_incomplete(self.root, problems)

        return RawCache(
            fetch_date=fetch_date,  # type: ignore[arg-type]
            q2_server_cutoff=cutoff,  # type: ignore[arg-type]
            urls={"clinicaltrials_gov": list(ctgov_urls), "cdc_places": list(places_urls)},
            ctgov_q1_pages=loaded["ctgov_q1"],
            ctgov_q2_pages=loaded["ctgov_q2"],
            places_pages=loaded["places"],
            contact_removals=removals,  # type: ignore[arg-type]
        )

    def _read_json(self, name: str) -> object:
        try:
            with open(self.root / name, "rb") as fh:
                return json.loads(fh.read().decode("utf-8"))
        except (OSError, ValueError):
            return None


def _dumps(obj: object) -> bytes:
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _parse_fetch_date(value: object) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        return datetime.strptime(value, FETCH_DATE_FORMAT).replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def _is_str_list(value: object) -> bool:
    return isinstance(value, list) and all(isinstance(v, str) for v in value)


def _raise_incomplete(root: Path, problems: dict[str, list[str]]) -> None:
    bad = [label for label in (CTGOV_LABEL, PLACES_LABEL) if problems[label]]
    details = "; ".join("%s: %s" % (label, ", ".join(problems[label])) for label in bad)
    raise PipelineError(
        "Offline_Mode: raw store %s has no complete prior fetch for %s (%s). "
        "Run without --offline first."
        % (root, " and ".join(bad), details)
    )
