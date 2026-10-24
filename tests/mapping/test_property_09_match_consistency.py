"""Property 9: Match consistency (condition-grouping design § Grouping_Engine).

For any Study_Disease_Row, `matched_on` and `matched_term` are non-empty,
`matched_term` is an element (as written) of the study column named by
`matched_on`, and that element matches at least one term of the row's
Disease_Definition under Exact_Match (mesh, ancestor) or Phrase_Match
(condition_text) (Req 8.9, 8.5). When `exclusion_reason` comes from the
Rules_Config, a term carrying that reason matches the same value (Req 8.6).
"""
from hypothesis import given, settings
from hypothesis import strategies as st

from pipeline.mapping.grouping_engine import group
from pipeline.mapping.term_matcher import exact_match, find_matches, normalize, phrase_match
from tests.mapping.strategies import rules_configs, study_lists

_COLUMN = {"mesh": "mesh_terms", "ancestor": "ancestor_terms", "condition_text": "conditions"}
_RULE = {"mesh": exact_match, "ancestor": exact_match, "condition_text": phrase_match}
_FIXED_REASONS = {"child_only", "healthy_volunteers_only", "ancestor_only", "unparseable_age"}


def _matching_terms(disease, source, value):
    """Rules_Config terms of `disease` that match `value` under `source`'s rule."""
    rule = _RULE[source]
    value_norm = normalize(value)
    return [t for t in disease.terms if rule(t.norm, value_norm)]


# Feature: condition-grouping, Property 9: Match consistency
@settings(max_examples=200)
@given(st.data())
def test_match_consistency(data):
    """**Validates: Requirements 8.9, 8.5**"""
    rules = data.draw(rules_configs())
    study_list = data.draw(study_lists(min_size=1, max_size=6))
    studies = {s.nct_id: s for s in study_list}
    diseases = {d.measureid: d for d in rules.diseases}

    for row in group(studies, rules):
        study, disease = studies[row.nctId], diseases[row.measureid]
        assert row.matched_on in _COLUMN, row
        assert row.matched_term != "", row
        # matched_term is a value as written in the named column (Req 8.5, 8.9).
        assert row.matched_term in getattr(study, _COLUMN[row.matched_on]), row
        # That value matches a term of this disease under the column's rule (Req 8.9).
        terms = _matching_terms(disease, row.matched_on, row.matched_term)
        assert terms, row
        # It is one of the matches the Term_Matcher reports for this pair.
        assert any(
            m.source == row.matched_on and m.value == row.matched_term
            for m in find_matches(study, disease)
        ), row
        # A Rules_Config reason is paired with a term matching that value (Req 8.6).
        if row.exclusion_reason and row.exclusion_reason not in _FIXED_REASONS:
            assert any(
                t.kind in ("exclude", "questionable") and t.reason == row.exclusion_reason
                for t in terms
            ), row
