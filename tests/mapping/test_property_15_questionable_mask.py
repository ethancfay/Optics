"""Property 15: Questionable-masked include evidence is never included
(condition-grouping design § Correctness Properties, Req 4.1, 4.4, 4.6, 7.4, 7.8,
Open Item 15).

Disease definitions are built so every Questionable_Term and Exclude_Term wraps
an Include_Term with a word boundary ("pediatric asthma" around "asthma", or
"asthma in children"). A `conditions` value holding the wrapper phrase-matches
both terms, so its include match is on a Masked_Value.

The oracle derives masking from `find_matches` output only: a Masked_Value is a
(source, value) with an Exclude_Term or Questionable_Term match for that disease.

- First half: with no include evidence (every include match masked, or
  ancestor-only under Ancestor_Only_Status `questionable`) the row is not
  `included`.
- Second half: adding a clean direct include value (an Include_Term match in
  `conditions` or `meshTerms` with no Exclude/Questionable match on that value)
  to a study with empty or >= 18 years `maximumAge` and `healthyVolunteers`
  not `true` gives `included`.
"""
from __future__ import annotations

from dataclasses import replace
from fractions import Fraction

from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from pipeline.io.csv_writer import encode_list_cell
from pipeline.mapping.age_parser import NO_LIMIT, parse_max_age
from pipeline.mapping.grouping_engine import decide
from pipeline.mapping.inputs import Study
from pipeline.mapping.rules_loader import SUPPORTED_MEASURES, RulesConfig, validate
from pipeline.mapping.term_matcher import find_matches
from tests.mapping.strategies import (
    REASON_CODES,
    healthy_volunteers,
    max_ages,
    nct_ids,
    overall_statuses,
    perturb,
    random_case,
    seeds,
)

# Include_Term bases; no base is a word-bounded substring of another.
BASES: tuple[str, ...] = (
    "asthma", "diabetes", "ldl cholesterol", "hypertension", "depression",
)
# Modifiers that wrap a base into a Questionable_Term or Exclude_Term.
MODIFIERS: tuple[str, ...] = (
    "pediatric", "childhood", "gestational", "occupational", "secondary",
    "type 1", "drug induced", "in children", "in pregnancy", "monogenic",
)
# Noise around study values; disjoint from BASES and MODIFIERS words.
NOISE: tuple[str, ...] = ("severe", "chronic", "adult", "control", "risk", "-", "(", ")", "/")


@st.composite
def _wrapper(draw, base: str, modifier: str) -> str:
    """A term containing `base` with a word boundary on both sides."""
    form = draw(st.sampled_from(("{m} {b}", "{b} {m}", "{b}, {m}", "{m}-{b}")))
    return form.format(m=modifier, b=base)


@st.composite
def _disease_dict(draw, measureid: str) -> dict:
    """Include bases plus Questionable/Exclude wrappers around them.

    The first include base always has at least one Questionable_Term wrapper.
    """
    bases = draw(st.permutations(BASES))[: draw(st.integers(1, 2))]
    question: list[tuple[str, str]] = []
    exclude: list[tuple[str, str]] = []
    for i, base in enumerate(bases):
        mods = draw(st.permutations(MODIFIERS))
        n_q = draw(st.integers(1 if i == 0 else 0, 2))
        n_e = draw(st.integers(0, 2))
        for mod in mods[:n_q]:
            question.append((draw(_wrapper(base, mod)), draw(st.sampled_from(REASON_CODES))))
        for mod in mods[n_q:n_q + n_e]:
            exclude.append((draw(_wrapper(base, mod)), draw(st.sampled_from(REASON_CODES))))
    return {
        "measureid": measureid,
        "disease_label": draw(random_case(bases[0])),
        "ancestor_only_status": draw(st.sampled_from(("included", "questionable"))),
        "recall_query_term": draw(random_case(bases[0])),
        "include": [draw(random_case(b)) for b in bases],
        "exclude": [(draw(random_case(t)), r) for t, r in exclude],
        "questionable": [(draw(random_case(t)), r) for t, r in question],
    }


@st.composite
def masking_rules(draw) -> RulesConfig:
    """A RulesConfig of 1-3 diseases, validated with `rules_loader.validate`."""
    ids = draw(st.lists(st.sampled_from(SUPPORTED_MEASURES), min_size=1, max_size=3,
                        unique=True))
    return validate([draw(_disease_dict(m)) for m in ids], draw(seeds))


def _terms(disease, kind: str) -> list[str]:
    return [t.text for t in disease.terms if t.kind == kind]


@st.composite
def _with_noise(draw, core: str) -> str:
    before = draw(st.lists(st.sampled_from(NOISE), max_size=2))
    after = draw(st.lists(st.sampled_from(NOISE), max_size=2))
    return draw(perturb(" ".join(before + [core] + after)))


def _make_study(nct: str, status: str, hv: str, age: str,
                conditions: tuple, mesh: tuple, ancestor: tuple) -> Study:
    return Study(
        nct_id=nct, brief_title="t", overall_status=status, healthy_volunteers=hv,
        maximum_age=age, conditions=conditions, mesh_terms=mesh, ancestor_terms=ancestor,
        conditions_cell=encode_list_cell(list(conditions)),
        source_url="https://clinicaltrials.gov/study/%s" % nct,
    )


@st.composite
def masked_studies(draw, rules: RulesConfig) -> Study:
    """A study whose direct include matches are all on wrapper (masked) values.

    `ancestorTerms` may hold a bare include term (ancestor-only case) or a wrapper.
    """
    wrappers = [t for d in rules.diseases
                for t in _terms(d, "questionable") + _terms(d, "exclude")]
    includes = [t for d in rules.diseases for t in _terms(d, "include")]
    conditions = draw(st.lists(st.sampled_from(wrappers).flatmap(_with_noise),
                               min_size=1, max_size=3))
    mesh = draw(st.lists(st.one_of(st.sampled_from(wrappers).flatmap(perturb),
                                   st.sampled_from(NOISE)), max_size=2))
    ancestor = draw(st.lists(st.sampled_from(includes + wrappers).flatmap(perturb),
                             max_size=2))
    return _make_study(draw(nct_ids), draw(overall_statuses), draw(healthy_volunteers),
                       draw(max_ages), tuple(conditions), tuple(mesh), tuple(ancestor))


eligible_ages = st.one_of(
    st.sampled_from(("", " ")),
    st.integers(18, 99).map(lambda n: "%d Years" % n),
    st.integers(216, 1200).map(lambda n: "%d Months" % n),
)


@st.composite
def cases(draw):
    """(rules, masked-only study, same study plus clean include values)."""
    rules = draw(masking_rules())
    base = draw(masked_studies(rules))
    clean_cond: list[str] = []
    clean_mesh: list[str] = []
    for disease in rules.diseases:
        if draw(st.booleans()) and (clean_cond or clean_mesh):
            continue  # not every disease gets a clean value
        term = draw(st.sampled_from(_terms(disease, "include")))
        if draw(st.booleans()):
            clean_cond.append(draw(_with_noise(term)))
        else:
            clean_mesh.append(draw(perturb(term)))
    clean = replace(
        base,
        conditions=base.conditions + tuple(clean_cond),
        conditions_cell=encode_list_cell(list(base.conditions + tuple(clean_cond))),
        mesh_terms=base.mesh_terms + tuple(clean_mesh),
        maximum_age=draw(eligible_ages),
        healthy_volunteers=draw(st.sampled_from(("false", ""))),
    )
    return rules, base, clean


# --- oracle (from find_matches output only) --------------------------------

def _masked(matches) -> set[tuple[str, str]]:
    return {(m.source, m.value) for m in matches if m.kind in ("exclude", "questionable")}


def _evidence(disease, matches) -> list:
    masked = _masked(matches)
    ancestor_ok = disease.ancestor_only_status == "included"
    return [m for m in matches
            if m.kind == "include" and (m.source, m.value) not in masked
            and (m.source != "ancestor" or ancestor_ok)]


def _clean_direct(matches) -> list:
    masked = _masked(matches)
    return [m for m in matches
            if m.kind == "include" and m.source in ("mesh", "condition_text")
            and (m.source, m.value) not in masked]


def _age_eligible(text: str) -> bool:
    age = parse_max_age(text)
    return age == NO_LIMIT or (isinstance(age, Fraction) and age >= 18)


def _questionable_masked_only(matches) -> bool:
    """Include matches exist, none is evidence-capable directly, and at least one
    sits on a value with a Questionable_Term match."""
    q_vals = {(m.source, m.value) for m in matches if m.kind == "questionable"}
    inc = [m for m in matches if m.kind == "include"]
    return (bool(inc) and not _clean_direct(matches)
            and any((m.source, m.value) in q_vals for m in inc))


def _check_first_half(study, disease):
    matches = find_matches(study, disease)
    row = decide(study, disease, matches)
    if row is None or _evidence(disease, matches):
        return
    assert row.match_status != "included", (study, disease.measureid, sorted(matches), row)


def _check_second_half(study, disease):
    matches = find_matches(study, disease)
    if not (_clean_direct(matches) and _age_eligible(study.maximum_age)
            and study.healthy_volunteers != "true"):
        return
    row = decide(study, disease, matches)
    assert row is not None and row.match_status == "included", (
        study, disease.measureid, sorted(matches), row)


# Feature: condition-grouping, Property 15: Questionable-masked include evidence is never included
@settings(max_examples=300, suppress_health_check=[HealthCheck.too_slow])
@given(cases())
def test_questionable_masked_include_never_included(case):
    """**Validates: Requirements 4.1, 4.4, 4.6, 7.4, 7.8**"""
    rules, base, clean = case
    for disease in rules.diseases:
        _check_first_half(base, disease)
        _check_first_half(clean, disease)
        _check_second_half(base, disease)
        _check_second_half(clean, disease)


def test_generator_produces_masked_only_and_clean_cases():
    """The generator yields questionable-masked-only pairs and clean included pairs."""
    counts = {"pairs": 0, "q_masked_only": 0, "clean_eligible": 0}

    @settings(max_examples=200, derandomize=True, database=None,
              suppress_health_check=[HealthCheck.too_slow])
    @given(cases())
    def collect(case):
        rules, base, clean = case
        for disease in rules.diseases:
            counts["pairs"] += 1
            if _questionable_masked_only(find_matches(base, disease)):
                counts["q_masked_only"] += 1
            if _clean_direct(find_matches(clean, disease)):
                counts["clean_eligible"] += 1

    collect()
    print("Property 15 generator counts:", counts)
    assert counts["q_masked_only"] >= counts["pairs"] // 10
    assert counts["clean_eligible"] >= counts["pairs"] // 4
