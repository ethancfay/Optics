"""Fetch_Log_Writer (design § Fetch_Log_Writer; Req 12.2-12.8, 12.11, 12.12).

`build_fetch_log` assembles the log object with a fixed key order, and
`serialize` turns it into the exact bytes of `fetch_log.json`. Writing the
bytes to disk is done by the atomic output step (design § Atomic output).

Only identifiers, counts, URLs, field names and timestamps go into the log
(Req 3.3).
"""
from __future__ import annotations

import json
from datetime import datetime
from typing import Iterable, Literal

from pipeline.data.contact_scrubber import RemovalCounts
from pipeline.data.raw_store import format_fetch_date
from pipeline.io.csv_writer import FILE_NAMES, EncodedTable
from pipeline.transform.places_transformer import PlacesDuplicate
from pipeline.transform.study_transformer import MissingGeo

FILE_NAME = "fetch_log.json"
TOP_LEVEL_KEYS = (
    "run_started_at", "run_mode", "fetch_date", "files", "clinicaltrials_gov", "urls",
    "contact_removals", "missing_geo", "invalid_zip_count", "places_duplicates", "warnings",
)
QUERIES = ("q1", "q2")
URL_SOURCES = ("clinicaltrials_gov", "cdc_places")

RunMode = Literal["network", "offline"]


def query_counts(pages_by_query: dict[str, list[dict]]) -> dict[str, dict[str, object]]:
    """Per-query Total_Count (page 1 `totalCount`) and records fetched (Req 1.9, 12.11).
    
    Same reading in network and offline runs. A non-integer or bool
    `totalCount` is reported as null (the fetch check stops such runs first).
    """
    counts: dict[str, dict[str, object]] = {}
    for query in QUERIES:
        pages = pages_by_query.get(query, [])
        total = pages[0].get("totalCount") if pages else None
        if type(total) is not int:
            total = None
        fetched = sum(len(page.get("studies", [])) for page in pages)
        counts[query] = {"total_count": total, "records_fetched": fetched}
    return counts


def build_fetch_log(
    *,
    run_started_at: datetime,
    run_mode: RunMode,
    fetch_date: datetime,
    tables: dict[str, EncodedTable],
    pages_by_query: dict[str, list[dict]],
    q2_server_cutoff: bool,
    urls: dict[str, list[str]],
    contact_removals: RemovalCounts,
    missing_geo: Iterable[MissingGeo],
    invalid_zip_count: int,
    places_duplicates: Iterable[PlacesDuplicate],
    warnings: Iterable[str],
) -> dict:
    if run_mode not in ("network", "offline"):
        raise ValueError("run_mode must be 'network' or 'offline'")

    # Row counts come from the tables that are written (Req 12.2, 12.7).
    files = {FILE_NAMES[kind]: len(tables[kind].rows) for kind in ("studies", "sites", "places")}
    counts = query_counts(pages_by_query)
    sites = sorted(missing_geo, key=lambda m: (m.nctId, m.facility))
    duplicates = sorted(places_duplicates, key=lambda d: (d.locationid, d.measureid))

    log = {
        "run_started_at": format_fetch_date(run_started_at),
        "run_mode": run_mode,
        "fetch_date": format_fetch_date(fetch_date),
        "files": files,
        "clinicaltrials_gov": {
            "q1": counts["q1"], "q2": counts["q2"], "q2_server_cutoff": bool(q2_server_cutoff),
        },
        "urls": {source: list(urls.get(source, [])) for source in URL_SOURCES},
        "contact_removals": contact_removals.to_log_dict(),
        "missing_geo": {
            "count": len(sites),
            "sites": [
                {"nctId": m.nctId, "facility": m.facility, "location_quality": m.location_quality}
                for m in sites
            ],
        },
        "invalid_zip_count": invalid_zip_count,
        "places_duplicates": [
            {"locationid": d.locationid, "measureid": d.measureid,
             "kept_year": d.kept_year, "discarded": d.discarded}
            for d in duplicates
        ],
        "warnings": list(warnings),
    }
    return log


def serialize(log: dict) -> bytes:
    """`json.dumps(indent=2, ensure_ascii=False)` plus a trailing LF, UTF-8."""
    return (json.dumps(log, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
