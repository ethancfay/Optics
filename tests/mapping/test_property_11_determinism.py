"""Property 11: deterministic, order-independent output (condition-grouping design § Outputs).
`group` + `encode_study_diseases` + `csv_writer.serialize` gives the same
study_diseases.csv bytes on repeated runs, when the studies dict is built in a
different insertion order, and when the elements of any study's conditions,
mesh_terms or ancestor_terms are permuted. Rows come out sorted by
(nctId, measureid) (Req 9.7, 9.8, 8.8, 9.5).
"""
from dataclasses import replace

from hypothesis import given, settings
from hypothesis import strategies as st

from pipeline.io.csv_writer import encode_list_cell, serialize
from pipeline.mapping.grouping_engine import group
from pipeline.mapping.outputs import encode_study_diseases

from tests.mapping.strategies import rules_configs, study_lists


def _csv_bytes(studies, rules) -> bytes:
    return serialize(encode_study_diseases(group({s.nct_id: s for s in studies}, rules)))


@st.composite
def _permuted_study(draw, study):
    """`study` with each list column independently permuted."""
    conditions = tuple(draw(st.permutations(study.conditions)))
    return replace(
        study,
        conditions=conditions,
        mesh_terms=tuple(draw(st.permutations(study.mesh_terms))),
        ancestor_terms=tuple(draw(st.permutations(study.ancestor_terms))),
        conditions_cell=encode_list_cell(list(conditions)),
    )


@st.composite
def _cases(draw):
    rules = draw(rules_configs())
    studies = draw(study_lists())
    reordered = draw(st.permutations(studies))
    permuted = [draw(_permuted_study(s)) for s in reordered]
    return rules, studies, permuted


# Feature: condition-grouping, Property 11: Deterministic, order-independent output
@settings(max_examples=200)
@given(_cases())
def test_output_is_deterministic_and_order_independent(case):
    """**Validates: Requirements 9.7, 9.8, 8.8, 9.5**"""
    rules, studies, permuted = case
    first = _csv_bytes(studies, rules)
    assert _csv_bytes(studies, rules) == first
    assert _csv_bytes(permuted, rules) == first

    table = encode_study_diseases(group({s.nct_id: s for s in studies}, rules))
    keys = [(row[0], row[1]) for row in table.rows]
    assert keys == sorted(keys)
