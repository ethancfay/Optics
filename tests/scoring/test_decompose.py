"""Unit tests for the Decomposer labels (design § Decomposer; Req 5.2-5.6).

Covers the specific label behaviours the data contract calls out, as concrete
examples complementing the distinct-count property test (task 6.2):

- **Multi-intervention counting** (Req 5.3): a study listing several
  intervention types counts once under each distinct humanized type, keyed on
  distinct nctId.
- **"Not reported" phase label** (Req 5.4): a study with an empty or missing
  `phases` list contributes the single label "Not reported".
- **"Not applicable" phase label** (Req 5.5): an "NA" / "Not Applicable" phase
  maps to the label "Not applicable".
- **Zero-count label exclusion** (Req 5.2): a label whose distinct-nctId count
  would be 0 is never emitted.
- **`phase_overlap_studies`** (Req 5.6): distinct eligible studies whose
  `phases` list has more than one element.

The Decomposer humanizes raw ClinicalTrials.gov enums (`RECRUITING` ->
"Recruiting", `DRUG` -> "Drug", `PHASE2` -> "Phase 2").
"""
from __future__ import annotations

from pipeline.scoring.decompose import (
    by_intervention_type,
    by_overall_status,
    by_phase,
    by_study_type,
    phase_overlap_studies,
)
from pipeline.scoring.models import DiseaseScope, StudyRow


# --- small builders so each test states only the fields it exercises ------------

def _study(
    nct_id: str,
    *,
    overall_status: str = "RECRUITING",
    study_type: str = "INTERVENTIONAL",
    phases: list[str] | None = None,
    intervention_types: list[str] | None = None,
) -> StudyRow:
    return StudyRow(
        nctId=nct_id,
        briefTitle="",
        overallStatus=overall_status,
        studyType=study_type,
        phases=phases if phases is not None else [],
        healthyVolunteers="",
        minimumAge="",
        maximumAge="",
        stdAges=[],
        conditions=[],
        interventionTypes=intervention_types if intervention_types is not None else [],
        interventionNames=[],
        meshTerms=[],
        meshIds=[],
        ancestorTerms=[],
        ancestorIds=[],
        lastUpdatePostDate="",
        source_url="https://clinicaltrials.gov/study/" + nct_id,
    )


def _scope(studies: list[StudyRow]) -> DiseaseScope:
    """A scope whose eligible studies are exactly `studies` (all eligible)."""
    studies_by_id = {s.nctId: s for s in studies}
    return DiseaseScope(
        measure_id="CASTHMA",
        condition="Asthma",
        eligible_ids=set(studies_by_id),
        t_ids=set(),
        studies_by_id=studies_by_id,
    )


def _counts(breakdown: list[dict[str, object]]) -> dict[str, int]:
    """A {label: count} view of a breakdown array for easy assertions."""
    return {entry["label"]: entry["count"] for entry in breakdown}


# --- multi-intervention counting (Req 5.3) --------------------------------------

def test_multi_intervention_study_counts_once_under_each_type():
    scope = _scope([_study("NCT1", intervention_types=["DRUG", "DEVICE", "BEHAVIORAL"])])
    counts = _counts(by_intervention_type(scope))
    assert counts == {"Drug": 1, "Device": 1, "Behavioral": 1}


def test_repeated_intervention_type_in_one_study_counts_once():
    """A study repeating a type counts once for it (distinct label per study)."""
    scope = _scope([_study("NCT1", intervention_types=["DRUG", "DRUG", "DEVICE"])])
    counts = _counts(by_intervention_type(scope))
    assert counts == {"Drug": 1, "Device": 1}


def test_intervention_type_count_is_distinct_nctid_across_studies():
    scope = _scope(
        [
            _study("NCT1", intervention_types=["DRUG", "DEVICE"]),
            _study("NCT2", intervention_types=["DRUG"]),
        ]
    )
    counts = _counts(by_intervention_type(scope))
    assert counts == {"Drug": 2, "Device": 1}


# --- "Not reported" phase label (Req 5.4) ---------------------------------------

def test_empty_phases_map_to_not_reported():
    scope = _scope([_study("NCT1", phases=[])])
    counts = _counts(by_phase(scope))
    assert counts == {"Not reported": 1}


def test_blank_only_phases_map_to_not_reported():
    """Phases made only of blank strings are treated as missing."""
    scope = _scope([_study("NCT1", phases=["", "  "])])
    counts = _counts(by_phase(scope))
    assert counts == {"Not reported": 1}


# --- "Not applicable" phase label (Req 5.5) -------------------------------------

def test_na_phase_maps_to_not_applicable():
    scope = _scope([_study("NCT1", phases=["NA"])])
    counts = _counts(by_phase(scope))
    assert counts == {"Not applicable": 1}


def test_numeric_phase_humanizes_and_na_is_separate_label():
    scope = _scope(
        [
            _study("NCT1", phases=["PHASE2"]),
            _study("NCT2", phases=["NA"]),
        ]
    )
    counts = _counts(by_phase(scope))
    assert counts == {"Phase 2": 1, "Not applicable": 1}


def test_na_and_numeric_phase_in_one_study_are_distinct_labels():
    scope = _scope([_study("NCT1", phases=["PHASE1", "NA"])])
    counts = _counts(by_phase(scope))
    assert counts == {"Phase 1": 1, "Not applicable": 1}


# --- zero-count label exclusion (Req 5.2) ---------------------------------------

def test_labels_with_zero_count_are_excluded():
    """No study carries "Device", so it never appears in the breakdown."""
    scope = _scope([_study("NCT1", intervention_types=["DRUG"])])
    breakdown = by_intervention_type(scope)
    labels = {entry["label"] for entry in breakdown}
    assert "Device" not in labels
    assert labels == {"Drug"}


def test_empty_scope_produces_no_labels():
    scope = _scope([])
    assert by_overall_status(scope) == []
    assert by_study_type(scope) == []
    assert by_intervention_type(scope) == []
    assert by_phase(scope) == []


def test_blank_status_and_type_contribute_no_label():
    """A study with blank overallStatus/studyType adds no breakdown label."""
    scope = _scope([_study("NCT1", overall_status="", study_type="")])
    assert by_overall_status(scope) == []
    assert by_study_type(scope) == []


# --- phase_overlap_studies (Req 5.6) --------------------------------------------

def test_phase_overlap_counts_studies_with_more_than_one_phase():
    scope = _scope(
        [
            _study("NCT1", phases=["PHASE1", "PHASE2"]),  # overlap
            _study("NCT2", phases=["PHASE2"]),            # single
            _study("NCT3", phases=[]),                    # none
            _study("NCT4", phases=["PHASE2", "PHASE3"]),  # overlap
        ]
    )
    assert phase_overlap_studies(scope) == 2


def test_phase_overlap_ignores_blank_phase_entries():
    """A single real phase padded with blanks is not an overlap."""
    scope = _scope([_study("NCT1", phases=["PHASE2", "", "  "])])
    assert phase_overlap_studies(scope) == 0


def test_phase_overlap_is_zero_without_multi_phase_studies():
    scope = _scope([_study("NCT1", phases=["PHASE2"]), _study("NCT2", phases=[])])
    assert phase_overlap_studies(scope) == 0
