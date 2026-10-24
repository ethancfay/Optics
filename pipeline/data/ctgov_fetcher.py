"""CTGov_Fetcher (design § CTGov_Fetcher; Req 1.1-1.9, 1.11, 3.1, 3.3, 3.5).

Runs Q1 (active statuses) to completion, then Q2 (recent COMPLETED). For each
query the parameters are built once and only `pageToken` changes between
pages (Req 1.2). Per page, in this order:

1. record the URL, then `client.get` (Req 1.4);
2. parse the JSON and require a `studies` list (Req 1.6, 3.5);
3. scrub contact data, then write the page to the Raw_Store before the next
   request (Req 3.2, 10.1);
4. on page 1, keep `totalCount` for the post-fetch check (Req 1.9, 1.10);
5. follow `nextPageToken`, stopping on a repeated token (Req 1.5) or after
   100 pages (Req 1.7). Page numbers, seen tokens and the page limit are all
   tracked per query.

Error messages hold only the query name, page numbers, URLs, tokens, status
codes and parameter names, never response body content (Req 3.3).
"""
from __future__ import annotations

import json
import urllib.parse
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from typing import Literal

from pipeline.data.contact_scrubber import RemovalCounts, scrub
from pipeline.data.http_client import HttpStatusError
from pipeline.errors import PipelineError

# Probe V10 passed on 2026-10-24 (probe_results.md), so Q2 sends filter.advanced.
Q2_SERVER_CUTOFF: bool = True

CTGOV_STUDIES_URL = "https://clinicaltrials.gov/api/v2/studies"
GEO_FILTER = "distance(42.3,-71.8,150mi)"
Q1_STATUSES = "RECRUITING,NOT_YET_RECRUITING,ACTIVE_NOT_RECRUITING"
Q2_STATUSES = "COMPLETED"
PAGE_SIZE = 1000
MAX_PAGES = 100  # per query (Req 1.7)

# Only what Req 4 and 5 need. No centralContacts, overallOfficials,
# locations.contacts or responsibleParty (Req 3.1, probes V3 and V6).
FIELDS = (
    "protocolSection.identificationModule.nctId",
    "protocolSection.identificationModule.briefTitle",
    "protocolSection.statusModule.overallStatus",
    "protocolSection.statusModule.lastUpdatePostDateStruct",
    "protocolSection.designModule.studyType",
    "protocolSection.designModule.phases",
    "protocolSection.eligibilityModule.healthyVolunteers",
    "protocolSection.conditionsModule.conditions",
    "protocolSection.armsInterventionsModule.interventions.type",
    "protocolSection.armsInterventionsModule.interventions.name",
    "protocolSection.contactsLocationsModule.locations.facility",
    "protocolSection.contactsLocationsModule.locations.city",
    "protocolSection.contactsLocationsModule.locations.state",
    "protocolSection.contactsLocationsModule.locations.zip",
    "protocolSection.contactsLocationsModule.locations.status",
    "protocolSection.contactsLocationsModule.locations.geoPoint",
    "derivedSection.conditionBrowseModule.meshes",
    "derivedSection.conditionBrowseModule.ancestors",
)

# Allowed_States, compared after stripping and casefolding (Req 5.3). Shared
# by the Req 1.12 fetch check and the Study_Transformer.
ALLOWED_STATES = frozenset({
    "massachusetts", "ma", "rhode island", "ri", "new hampshire", "nh",
    "connecticut", "ct", "new york", "ny", "vermont", "vt",
})

QueryName = Literal["q1", "q2"]
_RAW_SOURCE = {"q1": "ctgov_q1", "q2": "ctgov_q2"}


@dataclass
class QueryResult:
    query: QueryName
    pages: list[dict] = field(default_factory=list)  # scrubbed pages, in order
    urls: list[str] = field(default_factory=list)    # one per page, in order sent (Req 1.4)
    total_count: int | None = None                   # from this query's page 1 (Req 1.9)


@dataclass
class CtgovFetchResult:
    queries: list[QueryResult]  # always [q1, q2], in that order
    removal_counts: RemovalCounts


def is_allowed_state(state: object) -> bool:
    """Req 5.3: stripped, case-insensitive match on a full name or abbreviation."""
    return isinstance(state, str) and state.strip().casefold() in ALLOWED_STATES


def recent_completed_cutoff(fetch_date: datetime) -> date:
    """UTC date of the Fetch_Date minus 3 years; 29 February maps to 28 February."""
    today = fetch_date.astimezone(timezone.utc).date()
    day = 28 if (today.month, today.day) == (2, 29) else today.day
    return today.replace(year=today.year - 3, day=day)


def q2_lower_bound(fetch_date: datetime) -> date:
    """Q2_Lower_Bound: the Recent_Completed_Cutoff minus 1 day."""
    return recent_completed_cutoff(fetch_date) - timedelta(days=1)


def query_params(query: QueryName, fetch_date: datetime) -> list[tuple[str, str]]:
    """First-page parameters of a query, in a fixed order (Req 1.1). No study type filter."""
    params = [("filter.geo", GEO_FILTER)]
    if query == "q1":
        params.append(("filter.overallStatus", Q1_STATUSES))
    else:
        params.append(("filter.overallStatus", Q2_STATUSES))
        if Q2_SERVER_CUTOFF:
            bound = q2_lower_bound(fetch_date).isoformat()
            params.append(("filter.advanced", "AREA[LastUpdatePostDate]RANGE[%s,MAX]" % bound))
    params += [
        ("pageSize", str(PAGE_SIZE)),
        ("countTotal", "true"),
        ("fields", ",".join(FIELDS)),
    ]
    return params


def build_url(params: list[tuple[str, str]]) -> str:
    return "%s?%s" % (CTGOV_STUDIES_URL, urllib.parse.urlencode(params, safe="(),"))


def fetch_ctgov(client, raw_store, fetch_date: datetime) -> CtgovFetchResult:
    """Fetch Q1 then Q2, scrubbing and storing each page before the next request."""
    total_removals = RemovalCounts()
    results = []
    for query in ("q1", "q2"):
        result, removals = _fetch_query(client, raw_store, query, fetch_date)
        results.append(result)
        total_removals = total_removals + removals
    return CtgovFetchResult(queries=results, removal_counts=total_removals)


def _fetch_query(client, raw_store, query: QueryName, fetch_date: datetime
                 ) -> tuple[QueryResult, RemovalCounts]:
    label = query.upper()
    base = query_params(query, fetch_date)
    result = QueryResult(query=query)
    removals = RemovalCounts()
    seen_tokens: set[str] = set()
    token: str | None = None
    page_number = 0
    while True:
        page_number += 1
        params = base if token is None else base + [("pageToken", token)]
        url = build_url(params)
        result.urls.append(url)
        body = _get(client, url, query)

        try:
            page = json.loads(body)
        except (ValueError, RecursionError):
            raise PipelineError(
                "%s page %d of %s: response is not valid JSON" % (label, page_number, url)
            ) from None
        if not isinstance(page, dict) or not isinstance(page.get("studies"), list):
            raise PipelineError(
                "%s page %d of %s: response has no studies array" % (label, page_number, url)
            )

        scrubbed, page_removals = scrub(page, page_number=page_number, url=url)
        removals = removals + page_removals
        raw_store.write_page(_RAW_SOURCE[query], page_number, scrubbed)
        result.pages.append(scrubbed)

        if page_number == 1:
            total = scrubbed.get("totalCount")
            result.total_count = total if type(total) is int else None

        next_token = scrubbed.get("nextPageToken")
        if next_token is None or next_token == "":
            return result, removals
        if not isinstance(next_token, str):
            raise PipelineError(
                "%s page %d of %s: nextPageToken is not a string" % (label, page_number, url)
            )
        if next_token in seen_tokens:
            raise PipelineError(
                "%s page %d of %s: nextPageToken %s was already used earlier in %s"
                % (label, page_number, url, next_token, label)
            )
        if page_number >= MAX_PAGES:
            raise PipelineError(
                "%s reached the page limit of %d pages and page %d still has a nextPageToken"
                % (label, MAX_PAGES, page_number)
            )
        seen_tokens.add(next_token)
        token = next_token


def _get(client, url: str, query: QueryName) -> bytes:
    try:
        return client.get(url)
    except HttpStatusError as exc:
        if exc.status != 400:
            raise
        hint = "filter.geo" if query == "q1" else "filter.geo or filter.advanced"
        raise PipelineError(
            "request failed: %s returned HTTP 400; check parameter %s" % (url, hint)
        ) from None
