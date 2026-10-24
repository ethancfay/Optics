"""Unit tests for Evidence_Builder and Sources_Builder (Req 3.2, 4.9).

Covers the behaviours the data contract pins down for `evidence.json` and
`sources.json`:

- **NCT row shape** (Req 4.9): each `ncts` row restates only the non-PII study
  fields the contract allows, and its `url` is the canonical
  ``https://clinicaltrials.gov/study/{nct_id}`` page; rows are sorted by
  `nct_id`.
- **`missing_data_notes` on an absent measure** (Req 4.9): one note naming the
  measure is added when `measure_present` is ``False`` and the list is empty
  otherwise.
- **`is_sample == False`** (Req 3.2): `sources.json` is real output, never the
  shipped sample.
- **Date formats** (Req 3.2): `data_as_of` and every `sources[].fetched` are
  `YYYY-MM-DD` calendar dates derived from the fetch log's run date.
- **`prevalence_years` coverage** (Req 3.2): one entry per measure present in
  `what.json`, mapping `measure_id` to its `prevalence_year`.
"""
from __future__ import annotations

import re

from pipeline.scoring.evidence import CTGOV_STUDY_URL, build_evidence_entry
from pipeline.scoring.models import DiseaseScope, StudyRow
from pipeline.scoring.sources import build_sources

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


# --- small builders so each test states only the fields it exercises ------------

def _study(
    nct_id: str,
    *,
    brief_title: str = "A study",
    overall_status: str = "RECRUITING",
    study_type: str = "INTERVENTIONAL",
    phases: list[str] | None = None,
    intervention_types: list[str] | None = None,
    intervention_names: list[str] | None = None,
) -> StudyRow:
    return StudyRow(
        nctId=nct_id,
        briefTitle=brief_title,
        overallStatus=overall_status,
        studyType=study_type,
        phases=phases if phases is not None else [],
        healthyVolunteers="",
        minimumAge="",
        maximumAge="",
        stdAges=[],
        conditions=[],
        interventionTypes=intervention_types if intervention_types is not None else [],
        interventionNames=intervention_names if intervention_names is not None else [],
        meshTerms=[],
        meshIds=[],
        ancestorTerms=[],
        ancestorIds=[],
        lastUpdatePostDate="",
        source_url="https://clinicaltrials.gov/study/" + nct_id,
    )


def _scope(
    measure_id: str = "CASTHMA",
    condition: str = "Asthma",
    studies: list[StudyRow] | None = None,
) -> DiseaseScope:
    studies = studies if studies is not None else []
    studies_by_id = {s.nctId: s for s in studies}
    return DiseaseScope(
        measure_id=measure_id,
        condition=condition,
        eligible_ids=set(studies_by_id),
        t_ids=set(),
        studies_by_id=studies_by_id,
    )


# --- Evidence_Builder: NCT row shape (Req 4.9) ----------------------------------

def test_nct_row_has_the_contract_shape_and_canonical_url():
    study = _study(
        "NCT0001",
        brief_title="Asthma inhaler trial",
        overall_status="RECRUITING",
        study_type="INTERVENTIONAL",
        phases=["PHASE2", "PHASE3"],
        intervention_types=["DRUG"],
        intervention_names=["albuterol"],
    )
    entry = build_evidence_entry(_scope(studies=[study]), "Asthma")

    assert len(entry["ncts"]) == 1
    row = entry["ncts"][0]
    assert row == {
        "nct_id": "NCT0001",
        "url": "https://clinicaltrials.gov/study/NCT0001",
        "title": "Asthma inhaler trial",
        "status": "RECRUITING",
        "study_type": "INTERVENTIONAL",
        "phases": ["PHASE2", "PHASE3"],
        "intervention_types": ["DRUG"],
        "intervention_names": ["albuterol"],
    }


def test_nct_row_url_uses_the_canonical_study_page_per_nct():
    studies = [_study("NCT0002"), _study("NCT0003")]
    entry = build_evidence_entry(_scope(studies=studies), "Asthma")
    for row in entry["ncts"]:
        assert row["url"] == CTGOV_STUDY_URL.format(nct_id=row["nct_id"])
        assert row["url"] == f"https://clinicaltrials.gov/study/{row['nct_id']}"


def test_ncts_are_sorted_by_nct_id():
    studies = [_study("NCT0003"), _study("NCT0001"), _study("NCT0002")]
    entry = build_evidence_entry(_scope(studies=studies), "Asthma")
    assert [row["nct_id"] for row in entry["ncts"]] == [
        "NCT0001",
        "NCT0002",
        "NCT0003",
    ]


def test_entry_carries_measure_id_condition_and_static_method_notes():
    entry = build_evidence_entry(_scope("DIABETES", "Diabetes"), "Diabetes")
    assert entry["measure_id"] == "DIABETES"
    assert entry["condition"] == "Diabetes"
    assert isinstance(entry["filters"], list) and entry["filters"]
    assert isinstance(entry["mapping_choices"], list) and entry["mapping_choices"]


# --- Evidence_Builder: missing_data_notes on an absent measure (Req 4.9) --------

def test_missing_data_notes_empty_when_measure_present():
    entry = build_evidence_entry(_scope(), "Asthma", measure_present=True)
    assert entry["missing_data_notes"] == []


def test_missing_data_notes_has_one_note_naming_the_measure_when_absent():
    entry = build_evidence_entry(
        _scope("CASTHMA", "Asthma"), "Asthma", measure_present=False
    )
    notes = entry["missing_data_notes"]
    assert len(notes) == 1
    assert "Asthma" in notes[0]
    assert "CASTHMA" in notes[0]


def test_missing_data_notes_does_not_drop_the_ncts_list():
    """An absent measure still lists its eligible studies; only burden numbers go."""
    entry = build_evidence_entry(
        _scope(studies=[_study("NCT0001")]), "Asthma", measure_present=False
    )
    assert len(entry["ncts"]) == 1
    assert len(entry["missing_data_notes"]) == 1


# --- Sources_Builder: is_sample, date formats, prevalence_years (Req 3.2) -------

def _fetch_log(**overrides: object) -> dict[str, object]:
    log: dict[str, object] = {
        "fetch_date": "2026-10-24T18:12:26Z",
        "run_started_at": "2026-10-24T18:38:40Z",
        "urls": {
            "clinicaltrials_gov": ["https://clinicaltrials.gov/api/v2/studies?x=1"],
            "cdc_places": ["https://data.cdc.gov/resource/swc5-untb.json?y=2"],
        },
    }
    log.update(overrides)
    return log


def test_is_sample_is_false():
    sources = build_sources(_fetch_log())
    assert sources["is_sample"] is False


def test_data_as_of_and_fetched_are_yyyy_mm_dd():
    sources = build_sources(_fetch_log())
    assert sources["data_as_of"] == "2026-10-24"
    assert _DATE_RE.match(sources["data_as_of"])
    for source in sources["sources"]:
        assert _DATE_RE.match(source["fetched"])
        assert source["fetched"] == "2026-10-24"


def test_each_source_has_name_url_and_fetched():
    sources = build_sources(_fetch_log())
    names = {source["name"] for source in sources["sources"]}
    assert len(sources["sources"]) == 2
    for source in sources["sources"]:
        assert set(source) == {"name", "url", "fetched"}
        assert source["url"].startswith("https://")
    assert "ClinicalTrials.gov" in names


def test_prevalence_years_has_one_entry_per_what_json_measure():
    what_entries = [
        {"measure_id": "CASTHMA", "prevalence_year": "2023"},
        {"measure_id": "HIGHCHOL", "prevalence_year": "2021"},
        {"measure_id": "DIABETES", "prevalence_year": None},
    ]
    sources = build_sources(_fetch_log(), what_entries)
    assert sources["prevalence_years"] == {
        "CASTHMA": "2023",
        "HIGHCHOL": "2021",
        "DIABETES": None,
    }


def test_prevalence_years_lists_an_absent_measure_with_null_year():
    """A measure present in what.json but without a prevalence year still appears."""
    what_entries = [{"measure_id": "DIABETES", "prevalence_year": None}]
    sources = build_sources(_fetch_log(), what_entries)
    assert sources["prevalence_years"] == {"DIABETES": None}


def test_prevalence_years_empty_when_no_what_entries():
    sources = build_sources(_fetch_log())
    assert sources["prevalence_years"] == {}
