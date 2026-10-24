"""Sources_Builder (design § Component 7: Sources_Builder; Req 3.1, 3.2).

Builds `sources.json` from `fetch_log.json`, as a single JSON object rather than
an array (Req 3.1). The object carries:

- `is_sample = false` — this is real output, not the dashboard's shipped sample
  files (design § Key Design Decisions; Req 3.2);
- `data_as_of` and each `sources[].fetched` as a `YYYY-MM-DD` calendar date,
  derived from the fetch log's run date (Req 3.2);
- `sources` — one entry per upstream data source (ClinicalTrials.gov and the
  CDC PLACES county release), each with a `name`, `url`, and `fetched` date; the
  URLs come from the fetch log's recorded `urls` when present, falling back to
  the canonical source URLs;
- `prevalence_years` — one entry per disease measure present in `what.json`,
  mapping `measure_id` to the PLACES data year used for that measure's
  prevalence (`prevalence_year` in `what.json`; Req 3.2, Open Item 6).

`prevalence_years` is taken from the `what.json` entries so it is guaranteed to
reflect exactly the measures and years those entries carry; a measure whose
`prevalence_year` is unavailable (an absent PLACES measure) is still listed, with
a `null` year, so `prevalence_years` has one entry per measure present in
`what.json` (Req 3.2).
"""
from __future__ import annotations

from typing import Iterable, Mapping

# Canonical upstream URLs, used when the fetch log does not record a URL for a
# source. These mirror the fetchers' own constants so the two never drift.
CTGOV_SOURCE_NAME = "ClinicalTrials.gov"
CTGOV_SOURCE_URL = "https://clinicaltrials.gov/api/v2/studies"

PLACES_SOURCE_NAME = "CDC PLACES county release"
PLACES_SOURCE_URL = "https://data.cdc.gov/resource/swc5-untb.json"


def _calendar_date(value: object) -> str | None:
    """Return the `YYYY-MM-DD` date portion of an ISO-8601 timestamp (Req 3.2).

    The fetch log records timestamps like ``"2026-10-24T18:12:26Z"``; this keeps
    only the leading ``YYYY-MM-DD`` date when the string starts with a valid
    calendar date. Any other shape (missing, not a string, not a date) yields
    `None` so callers can decide what to emit rather than inventing a date.
    """
    if not isinstance(value, str):
        return None
    head = value[:10]
    if len(head) != 10 or head[4] != "-" or head[7] != "-":
        return None
    year, month, day = head[0:4], head[5:7], head[8:10]
    if not (year.isdigit() and month.isdigit() and day.isdigit()):
        return None
    # Reject impossible months/days so a malformed stamp never passes as a date.
    if not (1 <= int(month) <= 12 and 1 <= int(day) <= 31):
        return None
    return head


def _run_date(fetch_log: Mapping[str, object]) -> str | None:
    """Pick the calendar date the data was fetched (Req 3.2).

    Prefers `fetch_date`, then `run_started_at`; both are ISO timestamps in the
    fetch log. Returns `None` when neither yields a valid calendar date.
    """
    for key in ("fetch_date", "run_started_at"):
        date = _calendar_date(fetch_log.get(key))
        if date is not None:
            return date
    return None


def _source_url(fetch_log: Mapping[str, object], key: str, fallback: str) -> str:
    """Return the first recorded URL for a source, or the canonical fallback.

    The fetch log stores `urls` as ``{source_key: [url, ...]}``; the first entry
    is the representative query URL for that source. Anything unexpected (no
    `urls` object, no list, no string entries) falls back to the canonical URL.
    """
    urls = fetch_log.get("urls")
    if isinstance(urls, Mapping):
        entries = urls.get(key)
        if isinstance(entries, (list, tuple)):
            for entry in entries:
                if isinstance(entry, str) and entry:
                    return entry
    return fallback


def build_sources(
    fetch_log: Mapping[str, object],
    what_entries: Iterable[Mapping[str, object]] = (),
) -> dict[str, object]:
    """Build the single `sources.json` object (Req 3.1, 3.2).

    `fetch_log` is the parsed `fetch_log.json` (as returned by
    `load_fetch_log`). `what_entries` are the computed `what.json` entries, in
    the order they will be written; `prevalence_years` reflects exactly those
    entries, one per measure present, mapping `measure_id` to its
    `prevalence_year` (Req 3.2).

    `data_as_of` and each `sources[].fetched` are the run's calendar date as
    `YYYY-MM-DD`; `is_sample` is always `False` (Req 3.2).
    """
    fetched = _run_date(fetch_log)

    prevalence_years: dict[str, object] = {}
    for entry in what_entries:
        measure_id = entry.get("measure_id")
        if not isinstance(measure_id, str):
            continue
        prevalence_years[measure_id] = entry.get("prevalence_year")

    return {
        "data_as_of": fetched,
        "is_sample": False,
        "sources": [
            {
                "name": CTGOV_SOURCE_NAME,
                "url": _source_url(fetch_log, "clinicaltrials_gov", CTGOV_SOURCE_URL),
                "fetched": fetched,
            },
            {
                "name": PLACES_SOURCE_NAME,
                "url": _source_url(fetch_log, "cdc_places", PLACES_SOURCE_URL),
                "fetched": fetched,
            },
        ],
        "prevalence_years": prevalence_years,
    }
