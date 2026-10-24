"""Property 3: Exclude monotonicity (condition-grouping design § Grouping_Engine).

For any study and disease whose row status is `excluded` or `questionable`,
adding to `conditions`, `meshTerms` or `ancestorTerms` a value that matches an
Exclude_Term and no Include_Term of that disease does not make the status
`included` (Req 4.7).
"""

from dataclasses import replace

from hypothesis import assume, given, settings
from hypothesis import strategies as st

from pipeline.io.csv_writer import encode_list_cell
from pipeline.mapping.grouping_engine import decide
from pipeline.mapping.inputs import Study
from pipeline.mapping.rules_loader import SUPPORTED_MEASURES, validate
from pipeline.mapping.term_matcher import find_matches
from tests.mapping.strategies import NOISE_WORDS, disease_dicts, perturb, seeds, studies

_COLUMNS = ("conditions", "mesh_terms", "ancestor_terms")
_BLANK = Study("NCT00000000", "", "", "", "", (), (), (), "[]", "")


def _with_value(study: Study, column: str, value: str, position: int) -> Study:
    """`study` with `value` inserted into `column`; keeps conditions_cell in sync."""
    values = list(getattr(study, column))
    values.insert(min(position, len(values)), value)
    if column == "conditions":
        return replace(study, conditions=tuple(values),
                       conditions_cell=encode_list_cell(values))
    return replace(study, **{column: tuple(values)})


def _only(column: str, value: str) -> Study:
    """A study whose only list value is `value` in `column`."""
    return _with_value(_BLANK, column, value, 0)


@st.composite
def _cases(draw):
    """(disease, base study, column, added value, insert position)."""
    d = draw(disease_dicts(draw(st.sampled_from(SUPPORTED_MEASURES))))
    assume(d["exclude"])
    disease = validate([d], draw(seeds)).diseases[0]

    # Bias the base study toward matching the disease, so it has a row.
    study = draw(studies())
    for _ in range(draw(st.integers(0, 2))):
        term = draw(st.sampled_from(disease.terms))
        study = _with_value(study, draw(st.sampled_from(_COLUMNS)),
                            draw(perturb(term.text)), draw(st.integers(0, 4)))

    # The added value: a perturbed Exclude_Term, with noise words in conditions.
    column = draw(st.sampled_from(_COLUMNS))
    excl = [t for t in disease.terms if t.kind == "exclude"]
    value = draw(perturb(draw(st.sampled_from(excl)).text))
    if column == "conditions":
        before = draw(st.lists(st.sampled_from(NOISE_WORDS), max_size=2))
        after = draw(st.lists(st.sampled_from(NOISE_WORDS), max_size=2))
        value = " ".join(before + [value] + after)
    return disease, study, column, value, draw(st.integers(0, 4))


# Feature: condition-grouping, Property 3: Exclude monotonicity
@settings(max_examples=200)
@given(_cases())
def test_adding_exclude_only_value_never_makes_included(case):
    """**Validates: Requirements 4.7**"""
    disease, study, column, value, position = case

    # The added value matches an Exclude_Term and no Include_Term of the disease.
    kinds = {m.kind for m in find_matches(_only(column, value), disease)}
    assume("exclude" in kinds and "include" not in kinds)

    before = decide(study, disease, find_matches(study, disease))
    assume(before is not None and before.match_status in ("excluded", "questionable"))

    added = _with_value(study, column, value, position)
    after = decide(added, disease, find_matches(added, disease))
    assert after is not None
    assert after.match_status != "included", (before, after)
