"""Property 8: Rows exist exactly for matched pairs (condition-grouping design § Grouping_Engine).

For any rules config and studies, the set of (nctId, measureid) pairs in the
output equals the set of pairs with at least one term match, each pair appears
once, every nctId exists in the input studies, and every measureid is a
configured one (Req 8.1, 8.7, 3.7, 2.4).
"""
from hypothesis import given, settings
from hypothesis import strategies as st

from pipeline.mapping.grouping_engine import group
from pipeline.mapping.rules_loader import validate
from pipeline.mapping.term_matcher import find_matches
from tests.mapping.strategies import rules_dicts, study_lists


def _matched_pairs(studies, rules):
    return {
        (s.nct_id, d.measureid)
        for s in studies.values()
        for d in rules.diseases
        if find_matches(s, d)
    }


@st.composite
def _cases(draw):
    """(full rules, rules with a subset of the diseases, studies keyed by nctId)."""
    diseases, seed = draw(rules_dicts())
    keep = draw(st.lists(st.booleans(), min_size=len(diseases), max_size=len(diseases)))
    subset = [d for d, k in zip(diseases, keep) if k] or diseases[:1]
    study_list = draw(study_lists())
    return (validate(diseases, seed), validate(subset, seed),
            {s.nct_id: s for s in study_list})


# Feature: condition-grouping, Property 8: Rows exist exactly for matched pairs
@settings(max_examples=200)
@given(_cases())
def test_rows_exist_exactly_for_matched_pairs(case):
    """**Validates: Requirements 8.1, 8.7, 3.7, 2.4**"""
    rules, subset_rules, studies = case
    rows = group(studies, rules)
    pairs = [(r.nctId, r.measureid) for r in rows]

    # Exactly one row per pair with at least one match; none without (Req 8.1, 3.7).
    assert len(pairs) == len(set(pairs))
    assert set(pairs) == _matched_pairs(studies, rules)

    # Referential integrity: nctIds from the input, measureids configured (Req 8.7, 2.4).
    configured = {d.measureid for d in rules.diseases}
    for nct, mid in pairs:
        assert nct in studies
        assert mid in configured

    # Dropping diseases from the Rules_Config removes exactly their rows and
    # leaves every other row unchanged (Req 2.4).
    kept = {d.measureid for d in subset_rules.diseases}
    assert group(studies, subset_rules) == [r for r in rows if r.measureid in kept]
