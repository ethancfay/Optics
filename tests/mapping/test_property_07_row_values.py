"""Property 7: Row values are valid (condition-grouping design § Grouping_Engine).
Every Study_Disease_Row has its Disease_Definition's label, a valid
match_status, an empty exclusion_reason exactly when `included`, and a reason
code allowed for its status and measureid (Req 7.7, 8.2, 8.3, 8.4).
"""
from hypothesis import given, settings

from pipeline.mapping.grouping_engine import group
from tests.mapping.strategies import rules_configs, study_lists

_STATUSES = {"included", "questionable", "excluded"}
_SOURCES = {"mesh", "ancestor", "condition_text"}


# Feature: condition-grouping, Property 7: Row values are valid
@settings(max_examples=200)
@given(rules_configs(), study_lists())
def test_row_values_are_valid(rules, study_list):
    """**Validates: Requirements 7.7, 8.2, 8.3, 8.4**"""
    by_id = {d.measureid: d for d in rules.diseases}
    rows = group({s.nct_id: s for s in study_list}, rules)
    for row in rows:
        disease = by_id[row.measureid]
        assert row.disease_label == disease.label, row
        assert row.match_status in _STATUSES, row
        assert row.matched_on in _SOURCES, row
        assert (row.exclusion_reason == "") == (row.match_status == "included"), row
        if row.match_status == "questionable":
            allowed = {"ancestor_only", "unparseable_age"} | {
                t.reason for t in disease.terms if t.kind == "questionable"}
            assert row.exclusion_reason in allowed, row
        elif row.match_status == "excluded":
            allowed = {"child_only", "healthy_volunteers_only"} | {
                t.reason for t in disease.terms if t.kind == "exclude"}
            assert row.exclusion_reason in allowed, row
