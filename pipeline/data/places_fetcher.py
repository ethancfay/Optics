"""PLACES_Fetcher (design § PLACES_Fetcher; Req 2.1-2.9, 10.1).

Pages through the CDC PLACES 2025 county dataset (`swc5-untb`) for
Massachusetts crude prevalence rows. Every page uses the same `$select`,
`$where`, `$order` and `$limit`; only `$offset` changes, by 1,000 per page
(Req 2.3, 2.4). Per page, in this order:

1. record the URL, then `client.get` (Req 2.6);
2. parse the JSON and require a list of objects (Req 2.8);
3. write the page to the Raw_Store before the next request (Req 10.1);
4. stop on an empty first page (Req 2.7), stop paging on a short page
   (Req 2.5), and stop the run if page 100 is still full (Req 2.9).

PLACES pages are not scrubbed: they hold no contact structures, and the
PII_Guard still checks their output. Error messages hold only page numbers,
URLs and counts, never response body content (Req 3.3).
"""
from __future__ import annotations

import json
import urllib.parse
from dataclasses import dataclass, field

from pipeline.errors import PipelineError

PLACES_URL = "https://data.cdc.gov/resource/swc5-untb.json"
SELECT_FIELDS = (
    "locationname", "locationid", "measureid", "measure", "data_value",
    "low_confidence_limit", "high_confidence_limit", "totalpop18plus",
    "geolocation", "year", "stateabbr", "datavaluetypeid",
)
WHERE = "stateabbr='MA' AND datavaluetypeid='CrdPrv'"
# Probe V9 passed on 2026-10-24 (probe_results.md), so `:id` is kept as the tie-breaker.
ORDER = "locationname,measureid,:id"
PAGE_SIZE = 1000
MAX_PAGES = 100
RAW_SOURCE = "places"


@dataclass
class PlacesFetchResult:
    records: list[dict] = field(default_factory=list)  # all pages, in fetch order
    pages: list[list] = field(default_factory=list)    # one list per page, in order
    urls: list[str] = field(default_factory=list)      # one per page, in order sent (Req 2.6)


def page_params(offset: int) -> list[tuple[str, str]]:
    """Parameters of one page, in a fixed order (Req 2.1-2.3)."""
    return [
        ("$select", ",".join(SELECT_FIELDS)),
        ("$where", WHERE),
        ("$order", ORDER),
        ("$limit", str(PAGE_SIZE)),
        ("$offset", str(offset)),
    ]


def build_url(params: list[tuple[str, str]]) -> str:
    return "%s?%s" % (PLACES_URL, urllib.parse.urlencode(params, safe="$,:'"))


def fetch_places(client, raw_store) -> PlacesFetchResult:
    """Fetch every PLACES page, storing each one before the next request."""
    result = PlacesFetchResult()
    page_number = 0
    while True:
        page_number += 1
        url = build_url(page_params((page_number - 1) * PAGE_SIZE))
        result.urls.append(url)
        body = client.get(url)

        try:
            page = json.loads(body)
        except (ValueError, RecursionError):
            page = None
        if not isinstance(page, list) or not all(isinstance(r, dict) for r in page):
            raise PipelineError(
                "PLACES page %d of %s: response format was invalid (expected a list of records)"
                % (page_number, url)
            )
        if page_number == 1 and not page:
            raise PipelineError("PLACES page 1 of %s: no PLACES records were returned" % url)

        raw_store.write_page(RAW_SOURCE, page_number, page)
        result.pages.append(page)
        result.records.extend(page)

        if len(page) < PAGE_SIZE:
            return result
        if page_number >= MAX_PAGES:
            raise PipelineError(
                "PLACES reached the 100-page limit: page %d of %s still has %d records"
                % (page_number, url, PAGE_SIZE)
            )
