# Entry point: python -m pipeline [--offline]
#
# The version check below must stay first and must use only syntax that any
# Python 3 can parse, so that an old interpreter reaches it and exits cleanly
# before any pipeline import, network request, or file access (Req 14.2,
# design § Version check).
import sys
if sys.version_info < (3, 11):
    sys.stderr.write("Python %d.%d.%d detected; minimum is 3.11\n" % sys.version_info[:3])
    sys.exit(1)

import argparse
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from pipeline.data import ctgov_fetcher
from pipeline.data.contact_scrubber import RemovalCounts, scrub
from pipeline.data.ctgov_fetcher import is_allowed_state
from pipeline.data.http_client import HttpClient
from pipeline.data.places_fetcher import fetch_places
from pipeline.data.raw_store import RawStore
from pipeline.errors import PipelineError
from pipeline.io import csv_writer, fetch_log_writer
from pipeline.io.atomic import write_outputs
from pipeline.transform import pii_guard, sanity_checker
from pipeline.transform.places_transformer import build_places_rows
from pipeline.transform.study_transformer import build_study_and_site_rows

REPO_ROOT = Path(__file__).resolve().parent.parent


@dataclass(frozen=True)
class Paths:
    """Filesystem locations used by a run, rooted at a project directory."""

    root: Path

    @property
    def pipeline_dir(self) -> Path:
        return self.root / "pipeline"

    @property
    def raw(self) -> Path:
        return self.pipeline_dir / "raw"

    @property
    def processed(self) -> Path:
        return self.pipeline_dir / "processed"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m pipeline",
        description="Fetch ClinicalTrials.gov and CDC PLACES data and write pipeline/processed/.",
    )
    parser.add_argument(
        "--offline",
        action="store_true",
        help="rerun from the cached pages in pipeline/raw/ with no network requests",
    )
    return parser


def check_total_counts(pages_by_query: "dict[str, list[dict]]") -> None:
    """Req 1.10: each query's page 1 has an integer totalCount equal to its fetched records.

    `pages_by_query` maps "q1" and "q2" to that query's scrubbed pages, from a
    network fetch or the Raw_Store. Records are counted as received, so
    duplicates and records without an nctId count (design § Fetch checks).
    """
    for query, pages in pages_by_query.items():
        label = query.upper()
        total = pages[0].get("totalCount") if pages else None
        fetched = sum(len(page.get("studies", [])) for page in pages)
        if type(total) is not int:
            raise PipelineError(
                "%s: page 1 has no integer totalCount (fetched %d records)" % (label, fetched)
            )
        if fetched != total:
            raise PipelineError(
                "%s: fetched %d records but totalCount is %d; rerun the pipeline"
                % (label, fetched, total)
            )


def check_allowed_states(pages_by_query: "dict[str, list[dict]]") -> None:
    """Req 1.12: at least one record has a site whose state is in Allowed_States (Req 5.3)."""
    for pages in pages_by_query.values():
        for page in pages:
            for study in page.get("studies", []):
                for location in _locations(study):
                    if isinstance(location, dict) and is_allowed_state(location.get("state")):
                        return
    raise PipelineError(
        "no study has a site in Allowed_States (MA, RI, NH, CT, NY, VT); "
        "check parameter filter.geo"
    )


def _locations(study: object) -> list:
    node: object = study
    for key in ("protocolSection", "contactsLocationsModule", "locations"):
        if not isinstance(node, dict):
            return []
        node = node.get(key)
    return node if isinstance(node, list) else []


@dataclass
class _Sources:
    """Source data for the transform stages, from a network fetch or the Raw_Store."""

    run_mode: str
    fetch_date: datetime
    q2_server_cutoff: bool
    urls: dict
    pages_by_query: dict
    places_records: list
    contact_removals: RemovalCounts


def _network_sources(paths: Paths, client: object, run_started_at: datetime) -> _Sources:
    """Fetch Q1, Q2, then PLACES, storing each scrubbed page before the next request."""
    if client is None:
        client = HttpClient()
    store = RawStore(paths.raw)
    store.begin_network_run()
    fetch_date = run_started_at  # Req 1.8: captured once, before the first request
    ctgov = ctgov_fetcher.fetch_ctgov(client, store, fetch_date)
    places = fetch_places(client, store)
    q2_server_cutoff = ctgov_fetcher.Q2_SERVER_CUTOFF
    urls = {
        "clinicaltrials_gov": [u for q in ctgov.queries for u in q.urls],
        "cdc_places": list(places.urls),
    }
    store.finish_network_run(fetch_date, q2_server_cutoff, urls, ctgov.removal_counts)
    return _Sources(
        run_mode="network",
        fetch_date=fetch_date,
        q2_server_cutoff=q2_server_cutoff,
        urls=urls,
        pages_by_query={q.query: q.pages for q in ctgov.queries},
        places_records=list(places.records),
        contact_removals=ctgov.removal_counts,
    )


def _offline_sources(paths: Paths) -> _Sources:
    """Read the Raw_Store and re-scrub every ClinicalTrials.gov page (Req 3.6, 10.3).

    No HTTP_Client is built on this path, so no request can be sent (Req 14.4).
    """
    cache = RawStore(paths.raw).load()
    ctgov_urls = cache.urls["clinicaltrials_gov"]
    removals = cache.contact_removals
    pages_by_query: "dict[str, list[dict]]" = {}
    offset = 0
    for query, pages in (("q1", cache.ctgov_q1_pages), ("q2", cache.ctgov_q2_pages)):
        rescrubbed = []
        for n, page in enumerate(pages, start=1):
            clean, counts = scrub(page, page_number=n, url=ctgov_urls[offset + n - 1])
            removals = removals + counts
            rescrubbed.append(clean)
        offset += len(pages)
        pages_by_query[query] = rescrubbed
    return _Sources(
        run_mode="offline",
        fetch_date=cache.fetch_date,
        q2_server_cutoff=cache.q2_server_cutoff,
        urls=cache.urls,
        pages_by_query=pages_by_query,
        places_records=[r for page in cache.places_pages for r in page],
        contact_removals=removals,
    )


def _run_stages(args: argparse.Namespace, paths: Paths, client: object) -> None:
    """Run every stage in the design § Data flow order. Nothing touches
    pipeline/processed/ until the PII_Guard and the Sanity_Checker have run."""
    run_started_at = datetime.now(timezone.utc).replace(microsecond=0)
    if args.offline:
        sources = _offline_sources(paths)
    else:
        sources = _network_sources(paths, client, run_started_at)

    # Fetch checks (Req 1.10, 1.12), the same code path in both modes.
    check_total_counts(sources.pages_by_query)
    check_allowed_states(sources.pages_by_query)

    ctgov_pages = sources.pages_by_query["q1"] + sources.pages_by_query["q2"]
    studies, sites, missing_geo, invalid_zip_count = build_study_and_site_rows(ctgov_pages, sources.fetch_date)
    places, places_duplicates = build_places_rows(sources.places_records)

    tables = {
        "studies": csv_writer.encode_rows("studies", studies),
        "sites": csv_writer.encode_rows("sites", sites),
        "places": csv_writer.encode_rows("places", places),
    }
    pii_guard.check(tables)  # Req 8.1, 8.2: before any output write
    warnings = sanity_checker.check(studies, sites, places)  # Req 11.5

    log = fetch_log_writer.build_fetch_log(
        run_started_at=run_started_at,
        run_mode=sources.run_mode,
        fetch_date=sources.fetch_date,
        tables=tables,
        pages_by_query=sources.pages_by_query,
        q2_server_cutoff=sources.q2_server_cutoff,
        urls=sources.urls,
        contact_removals=sources.contact_removals,
        missing_geo=missing_geo,
        invalid_zip_count=invalid_zip_count,
        places_duplicates=places_duplicates,
        warnings=warnings,
    )
    write_outputs(
        paths.pipeline_dir,
        paths.processed,
        [(t.file_name, csv_writer.serialize(t)) for t in tables.values()],
        fetch_log_writer.serialize(log),
    )

    # Req 14.6: summary only after every output file is written.
    for table in tables.values():
        sys.stdout.write("%s: %d rows\n" % (table.file_name, len(table.rows)))


def run(argv: "list[str] | None", paths: Paths, client: object = None) -> int:
    """Parse arguments, run the pipeline, and return the process exit code.

    - PipelineError: message to stderr, exit code 1 (Req 14.8).
    - Any other exception: only the exception type name to stderr, exit
      code 1, no traceback, because a traceback could carry record content
      (design § Error model).
    - Argument errors: argparse prints usage and raises SystemExit(2).
    """
    args = build_parser().parse_args(argv)
    try:
        _run_stages(args, paths, client)
    except PipelineError as exc:
        sys.stderr.write("error: %s\n" % exc)
        return 1
    except Exception as exc:  # noqa: BLE001 - deliberate catch-all, see docstring
        sys.stderr.write("error: unexpected %s\n" % type(exc).__name__)
        return 1
    return 0


def main() -> int:
    return run(sys.argv[1:], Paths(REPO_ROOT), client=None)


if __name__ == "__main__":
    sys.exit(main())
