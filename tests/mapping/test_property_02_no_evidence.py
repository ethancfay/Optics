"""Property 2: No include evidence, never included (condition-grouping design § Grouping_Engine).

For any study and disease whose include matches are all on Masked_Values or in
`ancestorTerms` under Ancestor_Only_Status `questionable`, the row's
match_status is not `included`. A study whose only include matches are on
Masked_Values gets `excluded` or `questionable`.

The oracle recomputes include evidence from the raw matches without using the
Grouping_Engine's own intermediate lists. A Masked_Value is a (source, value)
with an Exclude_Term or a Questionable_Term match (Req 4.1, Open Item 15).
"""
from dataclasses import replace

from hypothesis import given, settings
from hypothesis import strategies as st

from pipeline.mapping.grouping_engine import decide, group
from pipeline.mapping.term_matcher import find_matches
from tests.mapping.strategies import (
    perturb,
    rules_configs,
    studies,
    study_lists,
)


def _masked_values(matches):
    """Masked_Values: (source, value) pairs with an Exclude_Term or Questionable_Term
    match (Req 4.1, Open Item 15)."""
    return {(m.source, m.value) for m in matches if m.kind in ("exclude", "questionable")}


def _evidence(disease, matches):
    """Include matches that count as include evidence (Req 4.1, 4.4, 7.3, 7.4)."""
    masked = _masked_values(matches)
    ancestor_ok = disease.ancestor_only_status == "included"
    return [
        m for m in matches
        if m.kind == "include"
        and (m.source, m.value) not in masked
        and (m.source in ("mesh", "condition_text") or (m.source == "ancestor" and ancestor_ok))
    ]


def _check(study, disease):
    matches = find_matches(study, disease)
    row = decide(study, disease, matches)
    if row is None or _evidence(disease, matches):
        return
    assert row.match_status != "included", (study, disease.measureid, sorted(matches))
    has_include = any(m.kind == "include" for m in matches)
    masked = _masked_values(matches)
    unmasked_include = any(
        m.kind == "include" and (m.source, m.value) not in masked for m in matches
    )
    if has_include and not unmasked_include:
        # Only include matches are on Masked_Values.
        assert row.match_status in ("excluded", "questionable")


@st.composite
def _masked_case(draw):
    """A RulesConfig and a study with a condition value matching an include and an exclude term.

    Puts "<include term> <exclude term>" in `conditions`, which phrase-matches both
    terms and so is a Masked_Value, making the masked-only case frequent.
    """
    rules = draw(rules_configs())
    study = draw(studies())
    extra = []
    for disease in rules.diseases:
        inc = [t.text for t in disease.terms if t.kind == "include"]
        exc = [t.text for t in disease.terms if t.kind == "exclude"]
        if inc and exc:
            extra.append(draw(perturb("%s %s" % (draw(st.sampled_from(inc)),
                                                  draw(st.sampled_from(exc))))))
    keep_others = draw(st.booleans())
    return rules, replace(
        study,
        conditions=tuple(extra) + (study.conditions if keep_others else ()),
        mesh_terms=study.mesh_terms if keep_others else (),
        ancestor_terms=study.ancestor_terms if keep_others else (),
    )


# Feature: condition-grouping, Property 2: No include evidence, never included
@settings(max_examples=200)
@given(rules_configs(), study_lists(max_size=6))
def test_no_evidence_never_included_group(rules, study_list):
    """**Validates: Requirements 4.6, 7.8, 4.1**"""
    by_id = {s.nct_id: s for s in study_list}
    diseases = {d.measureid: d for d in rules.diseases}
    rows = {(r.nctId, r.measureid): r for r in group(by_id, rules)}
    for study in study_list:
        for disease in rules.diseases:
            matches = find_matches(study, disease)
            row = rows.get((study.nct_id, disease.measureid))
            assert (row is None) == (not matches)
            if row is not None and not _evidence(diseases[disease.measureid], matches):
                assert row.match_status != "included", (study, disease.measureid)


# Feature: condition-grouping, Property 2: No include evidence, never included
@settings(max_examples=200)
@given(_masked_case())
def test_masked_only_includes_not_included(case):
    """**Validates: Requirements 4.6, 7.8, 4.1**"""
    rules, study = case
    for disease in rules.diseases:
        _check(study, disease)
