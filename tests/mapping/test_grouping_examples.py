"""Per-reason example tests for the Grouping_Engine against the real `rules.py`.
Condition-grouping Req 13.4, 4.2, 4.3, 4.4, 5.3, 5.4, 6.1, 6.4, 7.1, 7.2, 7.4,
Open Item 9 (design § Grouping_Engine).

Each example is one representative study, decided against the Disease_Definition
loaded from `rules.py`. `test_every_rules_reason_has_an_example` enumerates the
Exclude_Term and Questionable_Term reason codes from the loaded Rules_Config, so
adding a reason to `rules.py` without an example here fails the suite.

Study values are chosen with Phrase_Match in mind: a free-text condition value
also matches every shorter term it contains on word boundaries, so terms whose
condition text would also hit an Include_Term (for example
"Cystic Fibrosis-related Diabetes" contains "diabetes") are given as `meshTerms`
values, which use Exact_Match.
"""
import pytest

from pipeline.mapping.grouping_engine import decide, group
from pipeline.mapping.inputs import Study
from pipeline.mapping.rules_loader import RESERVED_REASONS, load_rules
from pipeline.mapping.term_matcher import find_matches

RULES = load_rules()
DISEASES = {d.measureid: d for d in RULES.diseases}


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


def _decide(measureid, study):
    disease = DISEASES[measureid]
    return decide(study, disease, find_matches(study, disease))


def _cells(row):
    return (row.match_status, row.exclusion_reason, row.matched_on, row.matched_term)


# (measureid, reason) -> (study kwargs, expected (status, reason, matched_on, matched_term))
REASON_EXAMPLES = {
    # Reserved reason codes (Req 5.3, 5.4, 6.1, 7.2)
    ("DIABETES", "child_only"): (
        dict(conditions=["Type 2 Diabetes"], max_age="17 Years"),
        ("excluded", "child_only", "condition_text", "Type 2 Diabetes"),
    ),
    ("CASTHMA", "unparseable_age"): (
        dict(conditions=["Asthma"], max_age="17.5 Years"),
        ("questionable", "unparseable_age", "condition_text", "Asthma"),
    ),
    # CASTHMA ancestor matches count as include evidence, but not for a
    # healthy-volunteer study (Req 6.1).
    ("CASTHMA", "healthy_volunteers_only"): (
        dict(ancestor=["Asthma"], hv="true"),
        ("excluded", "healthy_volunteers_only", "ancestor", "Asthma"),
    ),
    ("DIABETES", "ancestor_only"): (
        dict(mesh=["Metabolic Diseases"], ancestor=["Diabetes Mellitus"]),
        ("questionable", "ancestor_only", "ancestor", "Diabetes Mellitus"),
    ),
    # CASTHMA questionable reasons (condition text "Pediatric Asthma" would also
    # match the Include_Term "Asthma", so these use meshTerms)
    ("CASTHMA", "pediatric_label"): (
        dict(mesh=["Pediatric Asthma"]),
        ("questionable", "pediatric_label", "mesh", "Pediatric Asthma"),
    ),
    ("CASTHMA", "overlap_syndrome"): (
        dict(mesh=["Asthma COPD"]),
        ("questionable", "overlap_syndrome", "mesh", "Asthma COPD"),
    ),
    # DIABETES exclude reasons (Req 4.2)
    ("DIABETES", "gestational"): (
        dict(mesh=["Diabetes, Gestational"]),
        ("excluded", "gestational", "mesh", "Diabetes, Gestational"),
    ),
    ("DIABETES", "prediabetes"): (
        dict(conditions=["Prediabetes"]),
        ("excluded", "prediabetes", "condition_text", "Prediabetes"),
    ),
    # "diabetes" also matches here, but on a Masked_Value (Req 4.1)
    ("DIABETES", "not_mellitus"): (
        dict(conditions=["Diabetes Insipidus"]),
        ("excluded", "not_mellitus", "condition_text", "Diabetes Insipidus"),
    ),
    # DIABETES questionable reasons (Req 7.1)
    ("DIABETES", "complication_only"): (
        dict(conditions=["Diabetic Retinopathy"]),
        ("questionable", "complication_only", "condition_text", "Diabetic Retinopathy"),
    ),
    ("DIABETES", "monogenic_or_rare"): (
        dict(mesh=["Diabetes Mellitus, Insulin-Dependent, 12"]),
        ("questionable", "monogenic_or_rare", "mesh", "Diabetes Mellitus, Insulin-Dependent, 12"),
    ),
    ("DIABETES", "pregnancy_population"): (
        dict(conditions=["Pregnancy in Diabetics"]),
        ("questionable", "pregnancy_population", "condition_text", "Pregnancy in Diabetics"),
    ),
    ("DIABETES", "secondary_cause"): (
        dict(mesh=["Cystic Fibrosis-related Diabetes"]),
        ("questionable", "secondary_cause", "mesh", "Cystic Fibrosis-related Diabetes"),
    ),
    # HIGHCHOL exclude reason (Req 4.2)
    ("HIGHCHOL", "ascvd_only"): (
        dict(mesh=["Coronary Artery Disease"]),
        ("excluded", "ascvd_only", "mesh", "Coronary Artery Disease"),
    ),
    # HIGHCHOL questionable reasons (Req 7.1)
    ("HIGHCHOL", "lab_value_only"): (
        dict(mesh=["HDL Cholesterol"]),
        ("questionable", "lab_value_only", "mesh", "HDL Cholesterol"),
    ),
    ("HIGHCHOL", "broad_category"): (
        dict(conditions=["Lipid Disorders"]),
        ("questionable", "broad_category", "condition_text", "Lipid Disorders"),
    ),
    # Condition text would also hit "Cholesterol" (lab_value_only)
    ("HIGHCHOL", "monogenic_or_rare"): (
        dict(mesh=["Cholesterol Ester Storage Disease"]),
        ("questionable", "monogenic_or_rare", "mesh", "Cholesterol Ester Storage Disease"),
    ),
    # Condition text would also hit the Include_Term "hyperlipoproteinemia"
    ("HIGHCHOL", "triglyceride_predominant"): (
        dict(mesh=["Hyperlipoproteinemia Type V"]),
        ("questionable", "triglyceride_predominant", "mesh", "Hyperlipoproteinemia Type V"),
    ),
}

# measureid -> (study kwargs, expected cells) for one `included` study per disease (Req 7.4)
INCLUDED_EXAMPLES = {
    "CASTHMA": (
        dict(mesh=["Asthma"], conditions=["Severe Asthma"]),
        ("included", "", "mesh", "Asthma"),
    ),
    "DIABETES": (
        dict(conditions=["Type 2 Diabetes"], mesh=["Diabetes Mellitus, Type 2"]),
        ("included", "", "mesh", "Diabetes Mellitus, Type 2"),
    ),
    "HIGHCHOL": (
        dict(conditions=["Hypercholesterolemia"]),
        ("included", "", "condition_text", "Hypercholesterolemia"),
    ),
}


def _rules_reasons():
    return {
        (d.measureid, t.reason)
        for d in RULES.diseases
        for t in d.terms
        if t.kind in ("exclude", "questionable")
    }


def test_every_rules_reason_has_an_example():
    missing = _rules_reasons() - set(REASON_EXAMPLES)
    assert not missing, "reason codes without an example: %s" % sorted(missing)


def test_every_reserved_reason_has_an_example():
    assert set(RESERVED_REASONS) <= {reason for _, reason in REASON_EXAMPLES}


def test_every_disease_has_an_included_example():
    assert set(DISEASES) <= set(INCLUDED_EXAMPLES)


@pytest.mark.parametrize("key", sorted(REASON_EXAMPLES), ids=lambda k: "%s-%s" % k)
def test_reason_example(key):
    measureid, _ = key
    kwargs, expected = REASON_EXAMPLES[key]
    row = _decide(measureid, _study(**kwargs))
    assert row is not None
    assert row.measureid == measureid
    assert row.disease_label == DISEASES[measureid].label
    assert _cells(row) == expected


@pytest.mark.parametrize("measureid", sorted(INCLUDED_EXAMPLES))
def test_included_example(measureid):
    kwargs, expected = INCLUDED_EXAMPLES[measureid]
    row = _decide(measureid, _study(**kwargs))
    assert row is not None
    assert _cells(row) == expected


# Named examples


def test_gestational_with_diabetes_ancestor_is_excluded():
    """Req 4.3: direct exclude beats include evidence found only in ancestorTerms."""
    row = _decide("DIABETES", _study(conditions=["Gestational Diabetes"], ancestor=["Diabetes Mellitus"]))
    assert _cells(row) == ("excluded", "gestational", "condition_text", "Gestational Diabetes")


def test_type2_plus_gestational_is_included():
    """Req 4.4: a direct unmasked include match wins over any number of excludes."""
    row = _decide("DIABETES", _study(conditions=["Type 2 Diabetes", "Gestational Diabetes"]))
    assert _cells(row) == ("included", "", "condition_text", "Type 2 Diabetes")


def test_highchol_myocardial_infarction_only_is_excluded():
    """Req 4.2: HIGHCHOL "Myocardial Infarction" alone is excluded as ascvd_only."""
    row = _decide("HIGHCHOL", _study(conditions=["Myocardial Infarction"]))
    assert _cells(row) == ("excluded", "ascvd_only", "condition_text", "Myocardial Infarction")


def test_questionable_beats_term_exclude_without_ancestor_include():
    """Open Item 9 / Req 7.1: an unmasked Questionable_Term match prevents a term exclude."""
    row = _decide("DIABETES", _study(conditions=["Gestational Diabetes", "Diabetic Retinopathy"]))
    assert _cells(row) == ("questionable", "complication_only", "condition_text", "Diabetic Retinopathy")


def test_healthy_volunteer_asthma_with_condition_is_included():
    """Req 6.4: with a direct include match, healthyVolunteers=true changes nothing."""
    hv_row = _decide("CASTHMA", _study(conditions=["Asthma"], hv="true"))
    plain_row = _decide("CASTHMA", _study(conditions=["Asthma"], hv="false"))
    assert _cells(hv_row) == ("included", "", "condition_text", "Asthma")
    assert hv_row == plain_row


def test_pediatric_asthma_condition_only_is_questionable():
    """Req 4.1, 4.6, 7.1: "Pediatric Asthma" matches the Include_Term "asthma" and the
    Questionable_Term "Pediatric Asthma"; the value is masked for CASTHMA, so the
    questionable match decides (Open Item 15)."""
    row = _decide("CASTHMA", _study(conditions=["Pediatric Asthma"]))
    assert _cells(row) == ("questionable", "pediatric_label", "condition_text", "Pediatric Asthma")


def test_pediatric_asthma_plus_asthma_is_included():
    """Req 4.4, 7.4: a clean "Asthma" value is include evidence next to a masked one."""
    row = _decide("CASTHMA", _study(conditions=["Pediatric Asthma", "Asthma"]))
    assert _cells(row) == ("included", "", "condition_text", "Asthma")


def test_healthy_volunteer_pediatric_asthma_only_is_excluded():
    """Req 6.1, 6.3: the only direct include value is questionable-masked, so a
    healthy-volunteer study gets healthy_volunteers_only."""
    row = _decide("CASTHMA", _study(conditions=["Pediatric Asthma"], hv="true"))
    assert _cells(row) == (
        "excluded", "healthy_volunteers_only", "condition_text", "Pediatric Asthma")


def test_group_uses_loaded_rules_per_disease():
    """One study can give rows for several diseases, each decided on its own (Req 8.1)."""
    studies = {
        "NCT00000002": _study(
            conditions=["Asthma", "Gestational Diabetes"], nct="NCT00000002"
        ),
    }
    rows = group(studies, RULES)
    assert [(r.measureid, *_cells(r)) for r in rows] == [
        ("CASTHMA", "included", "", "condition_text", "Asthma"),
        ("DIABETES", "excluded", "gestational", "condition_text", "Gestational Diabetes"),
    ]
