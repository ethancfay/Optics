"""Shared data models for the Scoring & Export stage (design § Data Models).

Input row models reuse the Spec 1 dataclasses `StudyRow`, `SiteRow`, and
`PlacesRow` from the transform stage; they are re-exported here so the rest of
the scoring package can import every model it needs from one module. The Spec 2
match model `DiseaseMatch` (one row of `study_diseases.csv`) and the computed
`Prevalence` and `DiseaseScope` are new to this stage.

`MEASURE_IDS` is the set of active disease measures (Req 3.1); `CONDITION_LABELS`
maps each measure id to the human-readable `condition` used in `what.json`,
`investigate.json`, `evidence.json`, and the `ctgov_url` (Req 2.2, 3.1).
"""
from __future__ import annotations

from dataclasses import dataclass

from pipeline.transform.places_transformer import PlacesRow
from pipeline.transform.study_transformer import SiteRow, StudyRow

__all__ = [
    "StudyRow",
    "SiteRow",
    "PlacesRow",
    "DiseaseMatch",
    "Prevalence",
    "DiseaseScope",
    "MEASURE_IDS",
    "CONDITION_LABELS",
]


@dataclass(frozen=True)
class DiseaseMatch:
    """One row of `study_diseases.csv` (Spec 2 contract; Req 2.2)."""

    nctId: str
    measureid: str             # CASTHMA / HIGHCHOL / DIABETES (later BPHIGH/DEPRESSION)
    disease_label: str
    match_status: str          # included | questionable | excluded
    exclusion_reason: str      # "" if included; e.g. child_only, gestational
    matched_on: str            # mesh | ancestor | condition_text
    matched_term: str


@dataclass(frozen=True)
class Prevalence:
    """Population-weighted MA crude prevalence for a measure, as fractions."""

    p: float                   # fraction, e.g. 0.102
    p_low: float
    p_high: float
    year: str                  # PLACES year for this measure


@dataclass(frozen=True)
class DiseaseScope:
    """Per-measure scope produced by the MA_Index_Builder."""

    measure_id: str
    condition: str
    eligible_ids: set[str]              # eligible MA studies (all fetched statuses)
    t_ids: set[str]                     # subset that counts toward T
    studies_by_id: dict[str, StudyRow]


# Active disease measures for this spec (Req 3.1). Later BPHIGH / DEPRESSION.
MEASURE_IDS: frozenset[str] = frozenset({"CASTHMA", "HIGHCHOL", "DIABETES"})

# measure_id -> condition label, used for `condition` and the `ctgov_url`
# (Req 2.2, 3.1; data-contract what.json example: CASTHMA -> "Asthma").
CONDITION_LABELS: dict[str, str] = {
    "CASTHMA": "Asthma",
    "HIGHCHOL": "High Cholesterol",
    "DIABETES": "Diabetes",
}
