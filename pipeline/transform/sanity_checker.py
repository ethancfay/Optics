"""Sanity_Checker (design § Sanity_Checker; Req 11.1, 11.2, 11.5, 11.6).

`check` returns the warning texts and prints each one to stderr. Warnings
never stop the run (Req 11.4).
"""
from __future__ import annotations

import sys
from typing import Iterable, TextIO

from pipeline.transform.places_transformer import PlacesRow
from pipeline.transform.study_transformer import SiteRow, StudyRow

MA_STUDY_THRESHOLD = 2000
EXPECTED_COUNTIES = 14
MA_STATES = frozenset({"massachusetts", "ma"})


def ma_recruiting_interventional_count(studies: Iterable[StudyRow], sites: Iterable[SiteRow]) -> int:
    """Distinct INTERVENTIONAL studies with a RECRUITING site in Massachusetts (Req 11.1)."""
    interventional = {s.nctId for s in studies if s.studyType == "INTERVENTIONAL"}
    with_ma_site = {
        site.nctId for site in sites
        if site.siteStatus == "RECRUITING" and site.state.strip().casefold() in MA_STATES
    }
    return len(interventional & with_ma_site)


def county_count(places: Iterable[PlacesRow]) -> int:
    """Distinct locationname values across PLACES_Rows (Req 11.2)."""
    return len({row.locationname for row in places})


def check(studies: Iterable[StudyRow], sites: Iterable[SiteRow], places: Iterable[PlacesRow],
          stream: TextIO | None = None) -> list[str]:
    studies, sites, places = list(studies), list(sites), list(places)
    warnings: list[str] = []
    ma_count = ma_recruiting_interventional_count(studies, sites)
    if ma_count < MA_STUDY_THRESHOLD:
        warnings.append(
            "warning: %d INTERVENTIONAL studies have a RECRUITING Massachusetts site; "
            "threshold is %d" % (ma_count, MA_STUDY_THRESHOLD)
        )
    counties = county_count(places)
    if counties != EXPECTED_COUNTIES:
        warnings.append(
            "warning: %d distinct PLACES counties (locationname); expected %d"
            % (counties, EXPECTED_COUNTIES)
        )
    out = stream if stream is not None else sys.stderr
    for warning in warnings:
        out.write(warning + "\n")
    return warnings
