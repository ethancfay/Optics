"""Unit tests for the MA_Index_Builder (design § MA_Index_Builder; Req 4.1, 4.2, 5.1).

Covers the four behaviours called out by the data contract:

- **MA detection** (Req 5.1): `ma_study_ids` treats a site as Massachusetts only
  when its `state` is `massachusetts` or `ma` compared case-insensitively (the
  `sanity_checker` `.strip().casefold()` handling), and only known study nctIds
  count.
- **`included`-only eligibility** (Req 4.1): `build_scopes` puts an MA study in a
  measure's `eligible_ids` only when its `study_diseases.csv` row for that
  measure has `match_status == "included"`; `questionable`/`excluded` rows and
  non-MA studies never qualify.
- **T-eligible subset rules** (Req 4.1): `t_ids` is the subset of `eligible_ids`
  whose study `overallStatus == "RECRUITING"` and that also has >=1 MA site whose
  own site status is `RECRUITING`.
- **Unknown/blank site status never counts** (Req 4.2): a site whose `siteStatus`
  is absent, empty, or any value other than `RECRUITING` never contributes to
  `recruiting_ma_site_ids` and so never puts a study in `t_ids`.
"""
from __future__ import annotations

from pipeline.scoring.index import (
    build_scopes,
    ma_study_ids,
    recruiting_ma_site_ids,
)
from pipeline.scoring.models import (
    CONDITION_LABELS,
    MEASURE_IDS,
    DiseaseMatch,
    SiteRow,
    StudyRow,
)


# --- small builders so each test states only the fields it exercises ------------

def _study(nct_id: str, *, overall_status: str = "RECRUITING") -> StudyRow:
    return StudyRow(
        nctId=nct_id,
        briefTitle="",
        overallStatus=overall_status,
        studyType="INTERVENTIONAL",
        phases=[],
        healthyVolunteers="",
        minimumAge="",
        maximumAge="",
        stdAges=[],
        conditions=[],
        interventionTypes=[],
        interventionNames=[],
        meshTerms=[],
        meshIds=[],
        ancestorTerms=[],
        ancestorIds=[],
        lastUpdatePostDate="",
        source_url="https://clinicaltrials.gov/study/" + nct_id,
    )


def _site(nct_id: str, *, state: str = "Massachusetts", site_status: str = "RECRUITING") -> SiteRow:
    return SiteRow(
        nctId=nct_id,
        facility="",
        city="",
        state=state,
        zip="",
        latitude="",
        longitude="",
        siteStatus=site_status,
        location_quality="ok",
    )


def _match(nct_id: str, measure_id: str, *, status: str = "included") -> DiseaseMatch:
    return DiseaseMatch(
        nctId=nct_id,
        measureid=measure_id,
        disease_label="",
        match_status=status,
        exclusion_reason="" if status == "included" else "child only",
        matched_on="mesh",
        matched_term="",
    )


# --- MA detection (Req 5.1) ------------------------------------------------------

def test_ma_study_ids_matches_full_name_and_abbreviation_case_insensitively():
    studies = [_study("NCT1"), _study("NCT2"), _study("NCT3"), _study("NCT4")]
    sites = [
        _site("NCT1", state="Massachusetts"),
        _site("NCT2", state="massachusetts"),
        _site("NCT3", state="MA"),
        _site("NCT4", state=" ma "),
    ]
    assert ma_study_ids(studies, sites) == {"NCT1", "NCT2", "NCT3", "NCT4"}


def test_ma_study_ids_excludes_non_ma_and_blank_states():
    studies = [_study("NCT1"), _study("NCT2"), _study("NCT3")]
    sites = [
        _site("NCT1", state="Rhode Island"),
        _site("NCT2", state=""),
        _site("NCT3", state="connecticut"),
    ]
    assert ma_study_ids(studies, sites) == set()


def test_ma_study_ids_counts_a_study_with_any_ma_site():
    studies = [_study("NCT1")]
    sites = [
        _site("NCT1", state="Rhode Island"),
        _site("NCT1", state="Massachusetts"),
    ]
    assert ma_study_ids(studies, sites) == {"NCT1"}


def test_ma_study_ids_ignores_sites_with_no_matching_study_row():
    """A site whose nctId has no study row never inflates the MA set."""
    studies = [_study("NCT1")]
    sites = [_site("NCT1", state="Massachusetts"), _site("NCT_ORPHAN", state="Massachusetts")]
    assert ma_study_ids(studies, sites) == {"NCT1"}


# --- recruiting MA site detection; unknown/blank status never counts (Req 4.2) ---

def test_recruiting_ma_site_ids_requires_recruiting_ma_site():
    sites = [_site("NCT1", state="Massachusetts", site_status="RECRUITING")]
    assert recruiting_ma_site_ids(sites) == {"NCT1"}


def test_recruiting_ma_site_ids_excludes_absent_empty_or_other_status():
    sites = [
        _site("NCT1", state="Massachusetts", site_status=""),
        _site("NCT2", state="Massachusetts", site_status="COMPLETED"),
        _site("NCT3", state="Massachusetts", site_status="recruiting"),  # wrong case
        _site("NCT4", state="Massachusetts", site_status="WITHDRAWN"),
    ]
    assert recruiting_ma_site_ids(sites) == set()


def test_recruiting_ma_site_ids_requires_the_recruiting_site_to_be_in_ma():
    """A RECRUITING site outside MA does not qualify the study."""
    sites = [_site("NCT1", state="Rhode Island", site_status="RECRUITING")]
    assert recruiting_ma_site_ids(sites) == set()


def test_recruiting_ma_site_ids_counts_when_a_separate_ma_site_recruits():
    sites = [
        _site("NCT1", state="Massachusetts", site_status="COMPLETED"),
        _site("NCT1", state="Massachusetts", site_status="RECRUITING"),
    ]
    assert recruiting_ma_site_ids(sites) == {"NCT1"}


# --- build_scopes: one scope per active measure with contract labels ------------

def test_build_scopes_covers_every_active_measure_with_condition_labels():
    scopes = build_scopes([], [], [])
    assert set(scopes) == set(MEASURE_IDS)
    for measure_id, scope in scopes.items():
        assert scope.measure_id == measure_id
        assert scope.condition == CONDITION_LABELS[measure_id]
        assert scope.eligible_ids == set()
        assert scope.t_ids == set()
        assert scope.studies_by_id == {}


# --- included-only eligibility (Req 4.1) ----------------------------------------

def test_eligible_ids_contain_only_included_ma_studies():
    studies = [_study("NCT1"), _study("NCT2"), _study("NCT3")]
    sites = [
        _site("NCT1", state="Massachusetts"),
        _site("NCT2", state="Massachusetts"),
        _site("NCT3", state="Massachusetts"),
    ]
    diseases = [
        _match("NCT1", "CASTHMA", status="included"),
        _match("NCT2", "CASTHMA", status="questionable"),
        _match("NCT3", "CASTHMA", status="excluded"),
    ]
    scopes = build_scopes(studies, sites, diseases)
    assert scopes["CASTHMA"].eligible_ids == {"NCT1"}


def test_eligible_ids_exclude_included_non_ma_studies():
    studies = [_study("NCT1"), _study("NCT2")]
    sites = [
        _site("NCT1", state="Massachusetts"),
        _site("NCT2", state="Rhode Island"),
    ]
    diseases = [
        _match("NCT1", "DIABETES", status="included"),
        _match("NCT2", "DIABETES", status="included"),
    ]
    scopes = build_scopes(studies, sites, diseases)
    assert scopes["DIABETES"].eligible_ids == {"NCT1"}


def test_eligible_ids_are_per_measure():
    studies = [_study("NCT1"), _study("NCT2")]
    sites = [_site("NCT1", state="Massachusetts"), _site("NCT2", state="Massachusetts")]
    diseases = [
        _match("NCT1", "CASTHMA", status="included"),
        _match("NCT2", "HIGHCHOL", status="included"),
    ]
    scopes = build_scopes(studies, sites, diseases)
    assert scopes["CASTHMA"].eligible_ids == {"NCT1"}
    assert scopes["HIGHCHOL"].eligible_ids == {"NCT2"}
    assert scopes["DIABETES"].eligible_ids == set()


def test_inactive_measure_match_is_ignored():
    """A match for a measure outside MEASURE_IDS never creates a scope or eligibility."""
    studies = [_study("NCT1")]
    sites = [_site("NCT1", state="Massachusetts")]
    diseases = [_match("NCT1", "DEPRESSION", status="included")]
    scopes = build_scopes(studies, sites, diseases)
    assert "DEPRESSION" not in scopes
    for scope in scopes.values():
        assert scope.eligible_ids == set()


def test_studies_by_id_maps_each_eligible_nctid_to_its_row():
    studies = [_study("NCT1"), _study("NCT2")]
    sites = [_site("NCT1", state="Massachusetts"), _site("NCT2", state="Massachusetts")]
    diseases = [
        _match("NCT1", "CASTHMA", status="included"),
        _match("NCT2", "CASTHMA", status="excluded"),
    ]
    scopes = build_scopes(studies, sites, diseases)
    scope = scopes["CASTHMA"]
    assert set(scope.studies_by_id) == {"NCT1"}
    assert scope.studies_by_id["NCT1"] is studies[0]


# --- T-eligible subset rules (Req 4.1) ------------------------------------------

def test_t_ids_require_recruiting_study_and_recruiting_ma_site():
    studies = [_study("NCT1", overall_status="RECRUITING")]
    sites = [_site("NCT1", state="Massachusetts", site_status="RECRUITING")]
    diseases = [_match("NCT1", "CASTHMA", status="included")]
    scopes = build_scopes(studies, sites, diseases)
    assert scopes["CASTHMA"].t_ids == {"NCT1"}


def test_t_ids_exclude_eligible_study_not_overall_recruiting():
    studies = [_study("NCT1", overall_status="ACTIVE_NOT_RECRUITING")]
    sites = [_site("NCT1", state="Massachusetts", site_status="RECRUITING")]
    diseases = [_match("NCT1", "CASTHMA", status="included")]
    scopes = build_scopes(studies, sites, diseases)
    scope = scopes["CASTHMA"]
    assert scope.eligible_ids == {"NCT1"}
    assert scope.t_ids == set()


def test_t_ids_exclude_recruiting_study_without_recruiting_ma_site():
    studies = [_study("NCT1", overall_status="RECRUITING")]
    sites = [_site("NCT1", state="Massachusetts", site_status="COMPLETED")]
    diseases = [_match("NCT1", "CASTHMA", status="included")]
    scopes = build_scopes(studies, sites, diseases)
    scope = scopes["CASTHMA"]
    assert scope.eligible_ids == {"NCT1"}
    assert scope.t_ids == set()


def test_t_ids_exclude_recruiting_study_whose_recruiting_site_is_outside_ma():
    """overallStatus RECRUITING plus a RECRUITING non-MA site is not T-eligible."""
    studies = [_study("NCT1", overall_status="RECRUITING")]
    sites = [
        _site("NCT1", state="Massachusetts", site_status="COMPLETED"),
        _site("NCT1", state="Rhode Island", site_status="RECRUITING"),
    ]
    diseases = [_match("NCT1", "CASTHMA", status="included")]
    scopes = build_scopes(studies, sites, diseases)
    assert scopes["CASTHMA"].t_ids == set()


def test_t_ids_are_a_subset_of_eligible_ids():
    # NCT1: eligible + T-eligible; NCT2: eligible only; NCT3: recruiting but excluded.
    studies = [
        _study("NCT1", overall_status="RECRUITING"),
        _study("NCT2", overall_status="COMPLETED"),
        _study("NCT3", overall_status="RECRUITING"),
    ]
    sites = [
        _site("NCT1", state="Massachusetts", site_status="RECRUITING"),
        _site("NCT2", state="Massachusetts", site_status="RECRUITING"),
        _site("NCT3", state="Massachusetts", site_status="RECRUITING"),
    ]
    diseases = [
        _match("NCT1", "CASTHMA", status="included"),
        _match("NCT2", "CASTHMA", status="included"),
        _match("NCT3", "CASTHMA", status="excluded"),
    ]
    scopes = build_scopes(studies, sites, diseases)
    scope = scopes["CASTHMA"]
    assert scope.eligible_ids == {"NCT1", "NCT2"}
    assert scope.t_ids == {"NCT1"}
    assert scope.t_ids <= scope.eligible_ids


# --- unknown/blank site status never contributes to t_ids (Req 4.2) -------------

def test_blank_or_unknown_site_status_never_enters_t_ids():
    studies = [
        _study("NCT1", overall_status="RECRUITING"),
        _study("NCT2", overall_status="RECRUITING"),
        _study("NCT3", overall_status="RECRUITING"),
    ]
    sites = [
        _site("NCT1", state="Massachusetts", site_status=""),           # blank
        _site("NCT2", state="Massachusetts", site_status="recruiting"),  # wrong case
        _site("NCT3", state="Massachusetts", site_status="WITHDRAWN"),   # other value
    ]
    diseases = [
        _match("NCT1", "CASTHMA", status="included"),
        _match("NCT2", "CASTHMA", status="included"),
        _match("NCT3", "CASTHMA", status="included"),
    ]
    scopes = build_scopes(studies, sites, diseases)
    scope = scopes["CASTHMA"]
    assert scope.eligible_ids == {"NCT1", "NCT2", "NCT3"}
    assert scope.t_ids == set()
