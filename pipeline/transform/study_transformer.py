"""Study_Transformer (design § Study_Transformer; Req 4, 5).

Input is the ClinicalTrials.gov pages in Q1-then-Q2 order, each in page order.
Steps, in this order:

1. flatten the records of every page, keeping that order;
2. drop records with an absent or empty `nctId` (Req 4.9);
3. deduplicate by `nctId`, keeping the first record and discarding later
   records with their sites (Req 4.5); this runs before the status filter;
4. status filter, including the post-fetch Recent_Completed_Cutoff, which
   always runs whatever Q2 did on the server (Req 4.1); every `studyType` is kept;
5. build Site_Rows for Allowed_States locations, with `location_quality` and
   deduplication on (nctId, facility, city, state, zip) (Req 5);
6. drop studies left with zero Site_Rows (Req 4.3);
7. list the retained sites whose quality is not `ok` (Req 5.4, 5.7, 5.11).

No error is raised for bad record content: malformed values become empty
values, so no record content can reach an error message (Req 3.3).
"""
from __future__ import annotations

import math
import re
from dataclasses import dataclass
from datetime import date, datetime
from typing import Literal

from pipeline.data.ctgov_fetcher import is_allowed_state, recent_completed_cutoff

ALLOWED_OVERALL_STATUS = frozenset({
    "RECRUITING", "NOT_YET_RECRUITING", "ACTIVE_NOT_RECRUITING", "COMPLETED",
})
SOURCE_URL_PREFIX = "https://clinicaltrials.gov/study/"
_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

LocationQuality = Literal["ok", "missing_geo", "out_of_range"]


@dataclass(frozen=True)
class StudyRow:
    nctId: str
    briefTitle: str
    overallStatus: str
    studyType: str
    phases: list[str]
    healthyVolunteers: str
    minimumAge: str
    maximumAge: str
    stdAges: list[str]
    conditions: list[str]
    interventionTypes: list[str]
    interventionNames: list[str]
    meshTerms: list[str]
    meshIds: list[str]
    ancestorTerms: list[str]
    ancestorIds: list[str]
    lastUpdatePostDate: str
    source_url: str


@dataclass(frozen=True)
class SiteRow:
    nctId: str
    facility: str
    city: str
    state: str
    zip: str
    latitude: str
    longitude: str
    siteStatus: str
    location_quality: LocationQuality


@dataclass(frozen=True)
class MissingGeo:
    nctId: str
    facility: str
    location_quality: LocationQuality


def build_study_and_site_rows(pages: list[dict], fetch_date: datetime
                              ) -> tuple[list[StudyRow], list[SiteRow], list[MissingGeo]]:
    """`pages` is the Q1 pages followed by the Q2 pages, each query in page order."""
    cutoff = recent_completed_cutoff(fetch_date)

    # Steps 1-3: flatten, drop records with no nctId, keep the first per nctId.
    first_by_id: dict[str, dict] = {}
    for page in pages:
        studies = page.get("studies") if isinstance(page, dict) else None
        if not isinstance(studies, list):
            continue
        for record in studies:
            if not isinstance(record, dict):
                continue
            nct_id = _get(record, "protocolSection", "identificationModule", "nctId")
            if not isinstance(nct_id, str) or nct_id == "":
                continue
            first_by_id.setdefault(nct_id, record)

    study_rows: list[StudyRow] = []
    site_rows: list[SiteRow] = []
    for nct_id, record in first_by_id.items():
        # Step 4: status filter.
        if not _status_retained(record, cutoff):
            continue
        # Step 5: sites.
        sites = _build_sites(nct_id, record)
        # Step 6: a study needs at least one Site_Row.
        if not sites:
            continue
        study_rows.append(_build_study(nct_id, record))
        site_rows.extend(sites)

    # Step 7: missing-geo list (each site at most once, after deduplication).
    missing = [MissingGeo(s.nctId, s.facility, s.location_quality)
               for s in site_rows if s.location_quality != "ok"]
    return study_rows, site_rows, missing


def _get(node: object, *path: str) -> object:
    for key in path:
        if not isinstance(node, dict):
            return None
        node = node.get(key)
    return node


def _status_retained(record: dict, cutoff: date) -> bool:
    """Req 4.1: exact, case-sensitive status match; COMPLETED needs a recent valid date."""
    status = _get(record, "protocolSection", "statusModule", "overallStatus")
    if not isinstance(status, str) or status not in ALLOWED_OVERALL_STATUS:
        return False
    if status != "COMPLETED":
        return True
    raw = _get(record, "protocolSection", "statusModule", "lastUpdatePostDateStruct", "date")
    if not isinstance(raw, str) or not _DATE_RE.match(raw):
        return False
    try:
        updated = date.fromisoformat(raw)
    except ValueError:
        return False
    return updated >= cutoff


def _scalar(value: object) -> str:
    """Copy a scalar unchanged; missing becomes empty (Req 4.2, 4.4)."""
    if value is None:
        return ""
    return value if isinstance(value, str) else str(value)


def _element(value: object) -> str:
    """A list element as a string (Req 7.7). A missing element becomes ""."""
    if value is None:
        return ""
    return value if isinstance(value, str) else str(value)


def _list(value: object) -> list[str]:
    """A multi-valued field in source order; missing or non-list becomes [] (Req 4.4, 4.7)."""
    if not isinstance(value, list):
        return []
    return [_element(v) for v in value]


def _pairs(value: object, first: str, second: str) -> tuple[list[str], list[str]]:
    """Two paired lists built in one pass, so they always have equal length (Req 4.7)."""
    a: list[str] = []
    b: list[str] = []
    if isinstance(value, list):
        for item in value:
            item = item if isinstance(item, dict) else {}
            a.append(_element(item.get(first)))
            b.append(_element(item.get(second)))
    return a, b


def _build_study(nct_id: str, record: dict) -> StudyRow:
    ps = record.get("protocolSection")
    ident = _get(ps, "identificationModule")
    status = _get(ps, "statusModule")
    design = _get(ps, "designModule")
    elig = _get(ps, "eligibilityModule")
    browse = _get(record, "derivedSection", "conditionBrowseModule")

    healthy = _get(elig, "healthyVolunteers")
    healthy_text = ("true" if healthy else "false") if isinstance(healthy, bool) else ""

    int_types, int_names = _pairs(
        _get(ps, "armsInterventionsModule", "interventions"), "type", "name")
    mesh_terms, mesh_ids = _pairs(_get(browse, "meshes"), "term", "id")
    anc_terms, anc_ids = _pairs(_get(browse, "ancestors"), "term", "id")

    return StudyRow(
        nctId=nct_id,
        briefTitle=_scalar(_get(ident, "briefTitle")),
        overallStatus=_scalar(_get(status, "overallStatus")),
        studyType=_scalar(_get(design, "studyType")),
        phases=_list(_get(design, "phases")),
        healthyVolunteers=healthy_text,
        minimumAge=_scalar(_get(elig, "minimumAge")),
        maximumAge=_scalar(_get(elig, "maximumAge")),
        stdAges=_list(_get(elig, "stdAges")),
        conditions=_list(_get(ps, "conditionsModule", "conditions")),
        interventionTypes=int_types,
        interventionNames=int_names,
        meshTerms=mesh_terms,
        meshIds=mesh_ids,
        ancestorTerms=anc_terms,
        ancestorIds=anc_ids,
        lastUpdatePostDate=_scalar(_get(status, "lastUpdatePostDateStruct", "date")),
        source_url=SOURCE_URL_PREFIX + nct_id,
    )


def _text(value: object) -> str:
    """Site text value with leading and trailing whitespace removed (Req 5.1, 5.9)."""
    return _scalar(value).strip()


def _coordinate(value: object) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    number = float(value)
    return number if math.isfinite(number) else None


def _geo(geo_point: object) -> tuple[str, str, LocationQuality]:
    """Req 5.4, 5.6-5.8: `ok`, `out_of_range` or `missing_geo`."""
    lat = _coordinate(_get(geo_point, "lat"))
    lon = _coordinate(_get(geo_point, "lon"))
    if lat is None or lon is None:
        return "", "", "missing_geo"
    if not (-90.0 <= lat <= 90.0 and -180.0 <= lon <= 180.0):
        return "", "", "out_of_range"
    return repr(lat), repr(lon), "ok"


def _build_sites(nct_id: str, record: dict) -> list[SiteRow]:
    locations = _get(record, "protocolSection", "contactsLocationsModule", "locations")
    if not isinstance(locations, list):
        return []
    rows: list[SiteRow] = []
    seen: set[tuple[str, str, str, str, str]] = set()
    for loc in locations:
        if not isinstance(loc, dict) or not is_allowed_state(loc.get("state")):
            continue  # Req 5.3
        facility, city = _text(loc.get("facility")), _text(loc.get("city"))
        state, zip_code = _text(loc.get("state")), _text(loc.get("zip"))
        key = (nct_id, facility, city, state, zip_code)
        if key in seen:
            continue  # Req 5.10
        seen.add(key)
        lat, lon, quality = _geo(loc.get("geoPoint"))
        rows.append(SiteRow(
            nctId=nct_id, facility=facility, city=city, state=state, zip=zip_code,
            latitude=lat, longitude=lon,
            siteStatus=_text(loc.get("status")),  # every status kept (Req 5.2)
            location_quality=quality,
        ))
    return rows
