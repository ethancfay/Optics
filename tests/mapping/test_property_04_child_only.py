"""Property 4: Child-only studies are never included (condition-grouping design § Grouping_Engine).

For any study whose `maximumAge` parses to less than 18 years, every
Study_Disease_Row of that study has match_status `excluded` and exclusion_reason
`child_only`, whatever its healthyVolunteers value or term matches.
"""
from dataclasses import replace

from hypothesis import given, settings
from hypothesis import strategies as st

from pipeline.mapping.age_parser import is_child_only
from pipeline.mapping.grouping_engine import group
from tests.mapping.strategies import AGE_UNITS, random_case, rules_configs, study_lists


@st.composite
def child_only_ages(draw) -> str:
    """A well-formed `maximumAge` strictly below 18 years, unit in mixed case."""
    singular = draw(st.sampled_from(sorted(AGE_UNITS)))
    d, u = AGE_UNITS[singular]
    edge = -(-18 * u // d)  # smallest count that is not child-only
    # Near the boundary (n = edge - 1, edge - 2, ...) or anywhere in [0, edge - 1].
    n = draw(st.one_of(st.integers(max(0, edge - 3), edge - 1), st.integers(0, edge - 1)))
    unit = draw(random_case(singular + ("s" if draw(st.booleans()) else "")))
    lead = draw(st.sampled_from(("", " ", "\t", "  ")))
    trail = draw(st.sampled_from(("", " ", "\t")))
    return "%s%d %s%s" % (lead, n, unit, trail)


@st.composite
def _studies_some_child_only(draw):
    """(studies by nctId, nctIds whose maximumAge was set to a child-only value)."""
    study_list = draw(study_lists(min_size=1))
    child_flags = draw(st.lists(st.booleans(), min_size=len(study_list),
                                max_size=len(study_list)))
    if not any(child_flags):
        child_flags[0] = True
    out, child_ids = {}, set()
    for study, child in zip(study_list, child_flags):
        if child:
            study = replace(study, maximum_age=draw(child_only_ages()))
            child_ids.add(study.nct_id)
        out[study.nct_id] = study
    return out, frozenset(child_ids)


# Feature: condition-grouping, Property 4: Child-only studies are never included
@settings(max_examples=200)
@given(rules_configs(), _studies_some_child_only())
def test_child_only_studies_are_never_included(rules, studies_pair):
    """**Validates: Requirements 5.5, 5.3**"""
    studies, child_ids = studies_pair
    for nct in child_ids:
        assert is_child_only(studies[nct].maximum_age), studies[nct].maximum_age
    for row in group(studies, rules):
        if row.nctId in child_ids:
            assert (row.match_status, row.exclusion_reason) == ("excluded", "child_only"), row
