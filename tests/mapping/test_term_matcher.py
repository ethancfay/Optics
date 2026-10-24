"""Term_Matcher example tests (condition-grouping Req 3.1, 3.2, 3.3, 3.5, 3.6)."""
import pytest

from pipeline.mapping.inputs import Study
from pipeline.mapping.rules_loader import Disease, Term, normalize
from pipeline.mapping.term_matcher import Match, exact_match, find_matches, phrase_match


def _term(text, kind="include", reason=""):
    return Term(text, normalize(text), kind, reason)


def _disease(*terms, measureid="DIABETES"):
    return Disease(measureid, "Diabetes", "questionable", "diabetes", tuple(terms))


def _study(conditions=(), mesh=(), ancestor=(), brief_title="t"):
    return Study(
        nct_id="NCT00000001",
        brief_title=brief_title,
        overall_status="COMPLETED",
        healthy_volunteers="false",
        maximum_age="",
        conditions=tuple(conditions),
        mesh_terms=tuple(mesh),
        ancestor_terms=tuple(ancestor),
        conditions_cell="[]",
        source_url="https://clinicaltrials.gov/study/NCT00000001",
    )


# Req 3.1: Exact_Match on meshTerms / ancestorTerms
def test_exact_match_examples():
    term = normalize("Diabetes Mellitus")
    assert exact_match(term, normalize("diabetes mellitus"))
    assert not exact_match(term, normalize("Diabetes Mellitus, Type 2"))


@pytest.mark.parametrize("source,kw", [("mesh", "mesh"), ("ancestor", "ancestor")])
def test_mesh_and_ancestor_use_exact_match(source, kw):
    disease = _disease(_term("Diabetes Mellitus"))
    study = _study(**{kw: ("diabetes mellitus", "Diabetes Mellitus, Type 2")})
    assert find_matches(study, disease) == frozenset(
        {Match("DIABETES", "include", "Diabetes Mellitus", source, "diabetes mellitus")}
    )


# Req 3.2: Phrase_Match on conditions
@pytest.mark.parametrize("value", ["Severe Asthma", "Asthma, Exercise-Induced"])
def test_phrase_match_asthma_matches(value):
    assert phrase_match(normalize("asthma"), normalize(value))


def test_phrase_match_rejects_word_prefix():
    assert not phrase_match(normalize("asthma"), normalize("Asthmatic Bronchitis"))


def test_phrase_match_extra_internal_whitespace():
    assert phrase_match(normalize("type 2 diabetes"), normalize("Type  2 Diabetes Mellitus"))


def test_phrase_match_checks_every_occurrence():
    assert phrase_match("asthma", "asthmatic and asthma")


def test_conditions_use_phrase_match():
    disease = _disease(_term("asthma"), measureid="CASTHMA")
    study = _study(conditions=("Severe Asthma", "Asthmatic Bronchitis"))
    assert find_matches(study, disease) == frozenset(
        {Match("CASTHMA", "include", "asthma", "condition_text", "Severe Asthma")}
    )


def test_conditions_do_not_use_exact_only():
    # "Diabetes Mellitus" as an exact MeSH term does not match the longer
    # meshTerms value, but phrase-matches the same text in conditions.
    disease = _disease(_term("Diabetes Mellitus"))
    study = _study(conditions=("Diabetes Mellitus, Type 2",), mesh=("Diabetes Mellitus, Type 2",))
    assert find_matches(study, disease) == frozenset(
        {Match("DIABETES", "include", "Diabetes Mellitus", "condition_text", "Diabetes Mellitus, Type 2")}
    )


# Req 3.3: recorded fields, value as written, one match per distinct tuple
def test_match_records_kind_term_and_value_as_written():
    disease = _disease(
        _term("diabetes"),
        _term("gestational diabetes", "exclude", "gestational"),
    )
    study = _study(conditions=("  Gestational  DIABETES ",))
    assert find_matches(study, disease) == frozenset(
        {
            Match("DIABETES", "include", "diabetes", "condition_text", "  Gestational  DIABETES "),
            Match("DIABETES", "exclude", "gestational diabetes", "condition_text", "  Gestational  DIABETES "),
        }
    )


def test_duplicate_list_values_give_one_match():
    disease = _disease(_term("Diabetes Mellitus"))
    study = _study(mesh=("Diabetes Mellitus", "Diabetes Mellitus"))
    assert len(find_matches(study, disease)) == 1


def test_distinct_written_values_give_separate_matches():
    disease = _disease(_term("Diabetes Mellitus"))
    study = _study(mesh=("Diabetes Mellitus", "diabetes mellitus"))
    assert {m.value for m in find_matches(study, disease)} == {"Diabetes Mellitus", "diabetes mellitus"}


# Req 3.5: only the three list columns; empty arrays give no match
def test_empty_lists_give_no_match():
    assert find_matches(_study(), _disease(_term("diabetes"))) == frozenset()


def test_term_only_in_brief_title_gives_no_match():
    study = _study(conditions=("Obesity",), brief_title="A Diabetes Study")
    assert find_matches(study, _disease(_term("diabetes"))) == frozenset()


# Req 3.6: empty Normalized_Text values are skipped
def test_whitespace_only_values_are_skipped():
    study = _study(conditions=("  ",), mesh=("",), ancestor=("\t",))
    assert find_matches(study, _disease(_term("diabetes"))) == frozenset()


def test_match_is_frozen_and_ordered():
    a = Match("A", "include", "t", "mesh", "v")
    b = Match("B", "include", "t", "mesh", "v")
    assert a < b
    with pytest.raises(Exception):
        a.value = "x"  # type: ignore[misc]
