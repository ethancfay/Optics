"""Property 1: Case- and whitespace-insensitive matching (condition-grouping design § Term_Matcher).

For any study, any disease definition and any perturbation that changes letter
case of study values or Rules_Config terms, or adds leading, trailing or extra
internal whitespace next to existing whitespace, `find_matches` returns the same
set of (measureid, kind, normalized term, source) tuples.
"""
from dataclasses import replace

from hypothesis import given, settings
from hypothesis import strategies as st

from pipeline.mapping.rules_loader import normalize, validate
from pipeline.mapping.term_matcher import find_matches
from tests.mapping.strategies import perturb, rules_dicts, studies


@st.composite
def _perturbed_rules(draw):
    """(original RulesConfig, RulesConfig with every term perturbed)."""
    diseases, seed = draw(rules_dicts())
    perturbed = [
        {
            **d,
            "include": [draw(perturb(t)) for t in d["include"]],
            "exclude": [(draw(perturb(t)), r) for t, r in d["exclude"]],
            "questionable": [(draw(perturb(t)), r) for t, r in d["questionable"]],
        }
        for d in diseases
    ]
    return validate(diseases, seed), validate(perturbed, seed)


@st.composite
def _perturbed_study(draw):
    """(original Study, Study with every list value perturbed)."""
    study = draw(studies())

    def values(vs):
        return tuple(draw(perturb(v)) for v in vs)

    return study, replace(
        study,
        conditions=values(study.conditions),
        mesh_terms=values(study.mesh_terms),
        ancestor_terms=values(study.ancestor_terms),
    )


def _keys(matches):
    return {(m.measureid, m.kind, normalize(m.term), m.source) for m in matches}


# Feature: condition-grouping, Property 1: Case- and whitespace-insensitive matching
@settings(max_examples=200)
@given(_perturbed_rules(), _perturbed_study())
def test_matching_ignores_case_and_whitespace(rules_pair, study_pair):
    """**Validates: Requirements 3.4, 3.1, 3.2**"""
    rules, rules_p = rules_pair
    study, study_p = study_pair
    assert [d.measureid for d in rules.diseases] == [d.measureid for d in rules_p.diseases]
    for disease, disease_p in zip(rules.diseases, rules_p.diseases):
        expected = _keys(find_matches(study, disease))
        # Perturbing study values, terms, or both leaves the match set unchanged.
        assert _keys(find_matches(study_p, disease)) == expected
        assert _keys(find_matches(study, disease_p)) == expected
        assert _keys(find_matches(study_p, disease_p)) == expected
