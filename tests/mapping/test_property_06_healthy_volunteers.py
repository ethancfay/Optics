"""Property 6: Healthy-volunteer rule (condition-grouping design § Grouping_Engine).

For any study and disease with no unmasked Include_Term match in `conditions`
or `meshTerms`, setting healthyVolunteers to "true" yields no `included` row
(and `healthy_volunteers_only` unless child-only); for any study that has such
a match, the row with "true" equals the row with "false"; and healthyVolunteers
"false" or "" never yields `healthy_volunteers_only`.

"Unmasked direct include" is computed here from `find_matches` output, not
from the Grouping_Engine's internals: an Include_Term match on a `mesh` or
`condition_text` value that has no Exclude_Term and no Questionable_Term match
on the same (source, value) (Masked_Value, Req 4.1, Open Item 15).
"""
from dataclasses import replace

from hypothesis import given, settings

from pipeline.mapping.age_parser import is_child_only
from pipeline.mapping.grouping_engine import decide
from pipeline.mapping.term_matcher import find_matches
from tests.mapping.strategies import rules_configs, studies


def _has_unmasked_direct_include(matches) -> bool:
    masked = {(m.source, m.value) for m in matches if m.kind in ("exclude", "questionable")}
    return any(
        m.kind == "include"
        and m.source in ("mesh", "condition_text")
        and (m.source, m.value) not in masked
        for m in matches
    )


# Feature: condition-grouping, Property 6: Healthy-volunteer rule
@settings(max_examples=200)
@given(rules_configs(), studies())
def test_healthy_volunteer_rule(rules, study):
    """**Validates: Requirements 6.7, 6.4, 6.5, 6.1**"""
    hv_true = replace(study, healthy_volunteers="true")
    hv_false = replace(study, healthy_volunteers="false")
    hv_empty = replace(study, healthy_volunteers="")
    child = is_child_only(study.maximum_age)

    for disease in rules.diseases:
        # Matching ignores healthyVolunteers, so one match set serves all variants.
        matches = find_matches(study, disease)
        row_true = decide(hv_true, disease, matches)
        row_false = decide(hv_false, disease, matches)
        row_empty = decide(hv_empty, disease, matches)

        # Req 6.5: "false" and "" never yield healthy_volunteers_only.
        for r in (row_false, row_empty):
            if r is not None:
                assert r.exclusion_reason != "healthy_volunteers_only", r

        if not matches:
            assert row_true is None
            continue

        if _has_unmasked_direct_include(matches):
            # Req 6.4: "true" gives the same row as "false".
            assert row_true == row_false, (row_true, row_false)
        else:
            # Req 6.7: never included; Req 6.1/6.2: healthy_volunteers_only unless child-only.
            assert row_true.match_status != "included", row_true
            expected = "child_only" if child else "healthy_volunteers_only"
            assert (row_true.match_status, row_true.exclusion_reason) == (
                "excluded", expected), row_true
