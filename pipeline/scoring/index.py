"""MA_Index_Builder (design § MA_Index_Builder; Req 4.1, 4.2, 5.1, 5.7).

Applies the data-contract definitions once and produces one `DiseaseScope`
per active measure that the rest of the scoring pipeline consumes.

Definitions (restating the data contract):
- **MA study**: a study with >=1 site whose `state` is Massachusetts, compared
  case-insensitively against the full name `massachusetts` or the abbreviation
  `ma`, matching `sanity_checker.MA_STATES` handling (`.strip().casefold()`).
- **Eligible for a disease**: an MA study whose `study_diseases.csv` row for
  that measure has `match_status == "included"`.
- **T-eligible**: an eligible study with `overallStatus == "RECRUITING"` that
  also has >=1 MA site whose own `siteStatus` is `RECRUITING`. A site whose
  status is absent, empty, or any other value never counts (Req 4.2).
"""
from __future__ import annotations

from typing import Iterable

from pipeline.scoring.models import (
    MEASURE_IDS,
    CONDITION_LABELS,
    DiseaseMatch,
    DiseaseScope,
    SiteRow,
    StudyRow,
)
from pipeline.transform.sanity_checker import MA_STATES


def _is_ma_state(state: str) -> bool:
    """Case-insensitive Massachusetts match, matching `sanity_checker.MA_STATES`."""
    return state.strip().casefold() in MA_STATES


def ma_study_ids(studies: Iterable[StudyRow], sites: Iterable[SiteRow]) -> set[str]:
    """nctIds of studies with >=1 MA site (data-contract MA study definition; Req 5.1).

    The `studies` argument restricts the result to known studies so a site
    without a matching study row never inflates the set.
    """
    study_ids = {study.nctId for study in studies}
    return {
        site.nctId for site in sites
        if site.nctId in study_ids and _is_ma_state(site.state)
    }


def recruiting_ma_site_ids(sites: Iterable[SiteRow]) -> set[str]:
    """nctIds with >=1 MA site whose own site status is `RECRUITING` (Req 4.1, 4.2).

    A site whose `siteStatus` is absent, empty, or any value other than
    `RECRUITING` never counts.
    """
    return {
        site.nctId for site in sites
        if site.siteStatus == "RECRUITING" and _is_ma_state(site.state)
    }


def build_scopes(studies: Iterable[StudyRow], sites: Iterable[SiteRow],
                 diseases: Iterable[DiseaseMatch]) -> dict[str, DiseaseScope]:
    """One `DiseaseScope` per active measure (Req 4.1, 4.2, 5.1, 5.7).

    For each measure in `MEASURE_IDS`:
    - `eligible_ids` = MA studies whose `study_diseases.csv` row for that
      measure is `match_status == "included"`.
    - `t_ids` = eligible studies with `overallStatus == "RECRUITING"`
      intersected with the studies that have a recruiting MA site.
    - `studies_by_id` maps each eligible nctId to its `StudyRow`.
    """
    studies = list(studies)
    sites = list(sites)
    diseases = list(diseases)

    ma_ids = ma_study_ids(studies, sites)
    recruiting_ma = recruiting_ma_site_ids(sites)
    study_by_id = {study.nctId: study for study in studies}

    # Eligible (included) nctIds per measure, restricted to MA studies.
    included_by_measure: dict[str, set[str]] = {measure_id: set() for measure_id in MEASURE_IDS}
    for match in diseases:
        if match.measureid not in MEASURE_IDS:
            continue
        if match.match_status != "included":
            continue
        if match.nctId not in ma_ids:
            continue
        included_by_measure[match.measureid].add(match.nctId)

    scopes: dict[str, DiseaseScope] = {}
    for measure_id in MEASURE_IDS:
        eligible_ids = included_by_measure[measure_id]
        t_ids = {
            nct_id for nct_id in eligible_ids
            if nct_id in recruiting_ma
            and study_by_id[nct_id].overallStatus == "RECRUITING"
        }
        studies_by_id = {
            nct_id: study_by_id[nct_id] for nct_id in eligible_ids
        }
        scopes[measure_id] = DiseaseScope(
            measure_id=measure_id,
            condition=CONDITION_LABELS[measure_id],
            eligible_ids=eligible_ids,
            t_ids=t_ids,
            studies_by_id=studies_by_id,
        )
    return scopes
