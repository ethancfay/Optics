"""Grouping_Engine unit tests: one test per status rule branch plus helpers.
Condition-grouping Req 3.7, 4-8 (design § Grouping_Engine).
"""
from pipeline.mapping.grouping_engine import (
    SOURCE_ORDER,
    StudyDiseaseRow,
    decide,
    dm_key,
    group,
    pick,
)
from pipeline.mapping.inputs import Study
from pipeline.mapping.rules_loader import Disease, RulesConfig, Term, normalize
from pipeline.mapping.term_matcher import Match, find_matches


def _t(text, kind="include", reason=""):
    return Term(text, normalize(text), kind, reason)


DIABETES = Disease(
    "DIABETES",
    "Diabetes",
    "questionable",
    "Diabetes",
    (
        _t("Diabetes Mellitus"),
        _t("Diabetes Mellitus, Type 2"),
        _t("diabetes"),
        _t("Diabetes, Gestational", "exclude", "gestational"),
        _t("gestational diabetes", "exclude", "gestational"),
        _t("prediabetes", "exclude", "prediabetes"),
        _t("Diabetic Retinopathy", "questionable", "complication_only"),
        _t("diabetic neuropathy", "questionable", "complication_only"),
    ),
)
ASTHMA = Disease("CASTHMA", "Asthma", "included", "Asthma", (_t("Asthma"),))


def _study(conditions=(), mesh=(), ancestor=(), hv="false", max_age="", nct="NCT00000001"):
    return Study(
        nct_id=nct,
        brief_title="t",
        overall_status="RECRUITING",
        healthy_volunteers=hv,
        maximum_age=max_age,
        conditions=tuple(conditions),
        mesh_terms=tuple(mesh),
        ancestor_terms=tuple(ancestor),
        conditions_cell="[]",
        source_url="https://clinicaltrials.gov/study/" + nct,
    )


def _decide(study, disease=DIABETES):
    return decide(study, disease, find_matches(study, disease))


def _cells(row):
    return (row.match_status, row.exclusion_reason, row.matched_on, row.matched_term)


def test_dm_key_and_pick_order():
    a = Match("D", "include", "b", "condition_text", "A")
    b = Match("D", "include", "b", "mesh", "Z")
    c = Match("D", "include", "a", "mesh", "Z")
    assert SOURCE_ORDER == {"mesh": 0, "ancestor": 1, "condition_text": 2}
    assert dm_key(b) == (0, "Z", "b")
    assert pick([a, b, c]) is c


def test_no_matches_gives_no_row():  # Req 3.7
    assert _decide(_study(conditions=["Hypertension"])) is None


def test_rule1_child_only_prefers_unmasked_include():  # Req 5.3, 8.6 (b)
    s = _study(conditions=["Type 2 diabetes", "gestational diabetes"], hv="true", max_age="17 Years")
    assert _cells(_decide(s)) == ("excluded", "child_only", "condition_text", "Type 2 diabetes")


def test_rule1_child_only_falls_back_to_all_matches():
    s = _study(conditions=["gestational diabetes"], mesh=["Diabetes, Gestational"], max_age="215 Months")
    assert _cells(_decide(s)) == ("excluded", "child_only", "mesh", "Diabetes, Gestational")


def test_rule2_healthy_volunteers_only_uses_all_matches():  # Req 6.1, 6.3
    s = _study(conditions=["Diabetic Retinopathy"], ancestor=["Diabetes Mellitus"], hv="true",
               max_age="bad")
    assert _cells(_decide(s)) == (
        "excluded", "healthy_volunteers_only", "ancestor", "Diabetes Mellitus")


def test_rule2_not_applied_with_direct_include():  # Req 6.4
    on = _decide(_study(conditions=["Type 2 diabetes"], hv="true"))
    off = _decide(_study(conditions=["Type 2 diabetes"], hv="false"))
    assert on == off and on.match_status == "included"


def test_rule2_not_applied_when_hv_false_or_empty():  # Req 6.5
    for hv in ("false", ""):
        row = _decide(_study(ancestor=["Diabetes Mellitus"], hv=hv))
        assert row.exclusion_reason == "ancestor_only"


def test_rule3a_direct_exclude_beats_ancestor_include_and_questionable():  # Req 4.3, 8.6 (d)
    s = _study(conditions=["Gestational Diabetes", "Diabetic Neuropathy"],
               mesh=["Diabetes, Gestational"], ancestor=["Diabetes Mellitus", "Diabetes, Gestational"])
    assert _cells(_decide(s)) == ("excluded", "gestational", "mesh", "Diabetes, Gestational")


def test_rule3a_applies_regardless_of_ancestor_only_status():
    disease = Disease("CASTHMA", "Asthma", "included", "Asthma",
                      (_t("Asthma"), _t("occupational asthma", "exclude", "occupational")))
    s = _study(conditions=["Occupational Asthma"], ancestor=["Asthma"])
    assert _cells(_decide(s, disease)) == (
        "excluded", "occupational", "condition_text", "Occupational Asthma")


def test_rule3b_masked_include_only():  # Req 4.2, 4.6, 8.6 (c)
    s = _study(conditions=["Prediabetes"])
    assert _cells(_decide(s)) == ("excluded", "prediabetes", "condition_text", "Prediabetes")


def test_rule3b_not_applied_with_unmasked_questionable():  # Open Item 9
    s = _study(conditions=["Prediabetes", "Diabetic Retinopathy"])
    assert _cells(_decide(s)) == (
        "questionable", "complication_only", "condition_text", "Diabetic Retinopathy")


def test_direct_include_beats_exclude():  # Req 4.4
    s = _study(conditions=["Type 2 Diabetes", "Gestational Diabetes"])
    assert _cells(_decide(s)) == ("included", "", "condition_text", "Type 2 Diabetes")


def test_exclude_masks_value_for_that_disease_only():  # Req 4.1
    both = Disease("DIABETES", "Diabetes", "questionable", "Diabetes",
                   (_t("diabetes"), _t("gestational diabetes", "exclude", "gestational")))
    other = Disease("HIGHCHOL", "High cholesterol", "questionable", "x", (_t("diabetes"),))
    s = _study(conditions=["Gestational Diabetes"])
    assert _decide(s, both).match_status == "excluded"
    assert _decide(s, other).match_status == "included"


def test_rule4_unparseable_age_replaces_included():  # Req 5.4
    s = _study(conditions=["Type 2 Diabetes"], ancestor=["Diabetes Mellitus"], max_age="17.5 Years")
    assert _cells(_decide(s)) == ("questionable", "unparseable_age", "ancestor", "Diabetes Mellitus")


def test_rule4_yields_to_term_exclude():  # Req 7.6
    s = _study(conditions=["gestational diabetes"], max_age="18Years")
    assert _decide(s).match_status == "excluded"


def test_rule5_included_direct_ignores_questionable():  # Req 7.4, 8.6 (a)
    s = _study(conditions=["Diabetic Retinopathy"], mesh=["Diabetes Mellitus, Type 2"],
               ancestor=["Diabetes Mellitus"])
    assert _cells(_decide(s)) == ("included", "", "mesh", "Diabetes Mellitus, Type 2")


def test_rule5_ancestor_included_when_status_included():  # Req 7.3
    s = _study(ancestor=["Asthma"], max_age="65 Years")
    row = _decide(s, ASTHMA)
    assert row == StudyDiseaseRow("NCT00000001", "CASTHMA", "Asthma", "included", "",
                                  "ancestor", "Asthma")


def test_rule5_ancestor_excludes_only_fall_through():  # Req 4.5
    s = _study(ancestor=["Diabetes Mellitus", "Diabetes, Gestational"])
    assert _cells(_decide(s)) == ("questionable", "ancestor_only", "ancestor", "Diabetes Mellitus")


def test_rule6_questionable_term():  # Req 7.1, 8.6 (f)
    s = _study(conditions=["Diabetic Retinopathy"])
    assert _cells(_decide(s)) == (
        "questionable", "complication_only", "condition_text", "Diabetic Retinopathy")


QMASK = Disease(
    "DIABETES",
    "Diabetes",
    "questionable",
    "Diabetes",
    (
        _t("diabetes"),
        _t("gestational diabetes", "exclude", "gestational"),
        _t("retinopathy", "questionable", "complication_only"),
        _t("neuropathy", "questionable", "nerve"),
    ),
)


def test_questionable_masks_include_on_same_value():  # Req 4.1, 4.6, 7.1, Open Item 15
    s = _study(conditions=["Diabetes Retinopathy"])
    assert _cells(_decide(s, QMASK)) == (
        "questionable", "complication_only", "condition_text", "Diabetes Retinopathy")


def test_questionable_masked_value_beside_clean_include_is_included():  # Req 4.4, 7.4
    s = _study(conditions=["Diabetes Retinopathy", "Type 2 Diabetes"])
    assert _cells(_decide(s, QMASK)) == ("included", "", "condition_text", "Type 2 Diabetes")


def test_rule6_ignores_questionable_on_exclude_masked_value():  # Req 7.1, 8.6 (f)
    # "Gestational Diabetes Neuropathy" is an Exclude_Masked_Value, so its
    # "neuropathy" match is not a rule 6 candidate even though it sorts first.
    s = _study(conditions=["Gestational Diabetes Neuropathy", "Retinopathy"])
    assert _cells(_decide(s, QMASK)) == (
        "questionable", "complication_only", "condition_text", "Retinopathy")


def test_rule6_ancestor_only():  # Req 7.2, 8.6 (g)
    s = _study(ancestor=["Diabetes Mellitus"])
    assert _cells(_decide(s)) == ("questionable", "ancestor_only", "ancestor", "Diabetes Mellitus")


def test_rule6_both_apply_pick_by_source_order():  # Req 7.5
    s = _study(conditions=["Diabetic Retinopathy"], ancestor=["Diabetes Mellitus"])
    assert _cells(_decide(s)) == ("questionable", "ancestor_only", "ancestor", "Diabetes Mellitus")
    s = _study(mesh=["Diabetic Retinopathy"], ancestor=["Diabetes Mellitus"])
    assert _cells(_decide(s)) == ("questionable", "complication_only", "mesh", "Diabetic Retinopathy")


def test_group_sorted_and_skips_unmatched():  # Req 8.1
    studies = {
        "NCT2": _study(conditions=["Asthma", "Type 2 diabetes"], nct="NCT2"),
        "NCT1": _study(conditions=["Asthma"], nct="NCT1"),
        "NCT3": _study(conditions=["Hypertension"], nct="NCT3"),
    }
    rows = group(studies, RulesConfig((ASTHMA, DIABETES), 1))
    assert [(r.nctId, r.measureid) for r in rows] == [
        ("NCT1", "CASTHMA"), ("NCT2", "CASTHMA"), ("NCT2", "DIABETES")]
