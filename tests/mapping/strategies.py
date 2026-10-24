"""Hypothesis generators for the condition-grouping property tests (design § Testing Strategy).

Rules configs and studies share one small vocabulary, so include matches,
Masked_Values (Exclude_Term matches) and Phrase_Match boundary cases such as
"asthmatic" or "prediabetes" (which does not phrase-match "diabetes") are frequent.

Main entry points:
- `rules_dicts()` -> `(DISEASES list, SAMPLE_SEED)` raw data that passes `validate`.
- `rules_configs()` -> validated `RulesConfig`.
- `studies()` / `study_lists()` -> `Study` objects (lists have distinct nctIds).
- `ma_site_ids(studies)` -> frozenset of nctIds with an MA_Site.
- `max_ages`, `healthy_volunteers`, `overall_statuses` -> single column values.
- `random_case`, `perturb_whitespace`, `perturb` -> case / whitespace perturbation.
"""
from __future__ import annotations

from hypothesis import strategies as st

from pipeline.io.csv_writer import encode_list_cell
from pipeline.mapping.inputs import Study
from pipeline.mapping.rules_loader import (
    RESERVED_REASONS,
    SUPPORTED_MEASURES,
    RulesConfig,
    normalize,
    validate,
)

# Terms for Rules_Configs and the core of study values. Normalized_Text is
# distinct for every entry, so any subset of it has no duplicates (Req 2.6).
VOCABULARY: tuple[str, ...] = (
    "asthma",
    "asthma, occupational",
    "type 2 diabetes",
    "type 1 diabetes",
    "gestational diabetes",
    "diabetes",
    "diabetes mellitus",
    "diabetes insipidus",
    "prediabetes",
    "ldl",
    "ldl cholesterol",
    "high cholesterol",
    "hypercholesterolemia",
    "myocardial infarction",
)
assert len({normalize(v) for v in VOCABULARY}) == len(VOCABULARY)

# Words that are not in the vocabulary and appear next to it in study values.
NOISE_WORDS: tuple[str, ...] = (
    "severe", "chronic", "in", "children", "adult", "pregnancy", "healthy",
    "obesity", "control", "risk", "of", "and", "-", "(", ")", "/",
)

# Values that contain a vocabulary term without a word boundary on one side.
BOUNDARY_VALUES: tuple[str, ...] = (
    "asthmatic", "asthmatics", "nonasthma", "vldl", "ldls", "diabetesrisk",
    "prediabetic", "hypercholesterolemias", "type 2 diabetes2",
)

# Reason codes for Exclude_Terms and Questionable_Terms (valid, not reserved).
REASON_CODES: tuple[str, ...] = (
    "gestational", "prediabetes", "not_mellitus", "ascvd_only", "broad_category",
    "lab_value_only", "complication_only", "monogenic_or_rare", "secondary_cause",
)
assert not set(REASON_CODES) & set(RESERVED_REASONS)

ACTIVE_STATUSES: tuple[str, ...] = ("RECRUITING", "NOT_YET_RECRUITING", "ACTIVE_NOT_RECRUITING")
OTHER_STATUSES: tuple[str, ...] = (
    "COMPLETED", "TERMINATED", "WITHDRAWN", "SUSPENDED", "ENROLLING_BY_INVITATION",
    "UNKNOWN", "",
)

# Age units: singular -> (d, u), one unit is d/u years (Req 5.1).
AGE_UNITS: dict[str, tuple[int, int]] = {
    "year": (1, 1),
    "month": (1, 12),
    "week": (10000, 521775),
    "day": (4, 1461),
    "hour": (1, 8766),
    "minute": (1, 525960),
}
MALFORMED_AGES: tuple[str, ...] = (
    "-1 Years", "1.5 Years", "17Years", "17 Decades", "17  Years", "Years",
    "17", "N/A", "\u0661\u0667 Years", "17 Years old",
)

_WHITESPACE = (" ", "  ", "\t", " \t ")


# --- perturbation helpers ---------------------------------------------------

@st.composite
def random_case(draw, text: str) -> str:
    """`text` with each character independently upper- or lower-cased."""
    flips = draw(st.lists(st.booleans(), min_size=len(text), max_size=len(text)))
    return "".join(c.upper() if f else c.lower() for c, f in zip(text, flips))


@st.composite
def perturb_whitespace(draw, text: str) -> str:
    """Add leading, trailing and extra internal whitespace next to existing whitespace.

    Never inserts whitespace between two non-whitespace characters, so the
    Normalized_Text is unchanged (Property 1).
    """
    out = [draw(st.sampled_from(("",) + _WHITESPACE))]
    for ch in text:
        out.append(ch)
        if ch.isspace():
            out.append(draw(st.sampled_from(("",) + _WHITESPACE)))
    out.append(draw(st.sampled_from(("",) + _WHITESPACE)))
    return "".join(out)


@st.composite
def perturb(draw, text: str) -> str:
    """Random letter case plus whitespace perturbation; `normalize` is unchanged."""
    return draw(perturb_whitespace(draw(random_case(text))))


# --- Rules_Config -----------------------------------------------------------

@st.composite
def disease_dicts(draw, measureid: str) -> dict:
    """One Disease_Definition dict for `measureid`, with terms drawn from VOCABULARY."""
    pool = draw(st.permutations(VOCABULARY))
    n_include = draw(st.integers(1, 4))
    n_exclude = draw(st.integers(0, 3))
    n_question = draw(st.integers(0, 3))
    include = pool[:n_include]
    exclude = pool[n_include:n_include + n_exclude]
    question = pool[n_include + n_exclude:n_include + n_exclude + n_question]
    reason = st.sampled_from(REASON_CODES)
    label = draw(random_case(draw(st.sampled_from(VOCABULARY))))
    return {
        "measureid": measureid,
        "disease_label": label,
        "ancestor_only_status": draw(st.sampled_from(("included", "questionable"))),
        "recall_query_term": draw(random_case(include[0])),
        "include": [draw(random_case(t)) for t in include],
        "exclude": [(draw(random_case(t)), draw(reason)) for t in exclude],
        "questionable": [(draw(random_case(t)), draw(reason)) for t in question],
    }


seeds = st.integers(0, 2**32 - 1)


@st.composite
def rules_dicts(draw) -> tuple[list[dict], int]:
    """Raw `(DISEASES, SAMPLE_SEED)` with 1-5 diseases; always passes `validate`."""
    ids = draw(st.lists(st.sampled_from(SUPPORTED_MEASURES), min_size=1, max_size=5,
                        unique=True))
    return [draw(disease_dicts(m)) for m in ids], draw(seeds)


def rules_configs() -> st.SearchStrategy[RulesConfig]:
    """Validated `RulesConfig` objects built from `rules_dicts()`."""
    return rules_dicts().map(lambda pair: validate(*pair))


# --- study column values ----------------------------------------------------

@st.composite
def _age_with_unit(draw) -> str:
    singular = draw(st.sampled_from(sorted(AGE_UNITS)))
    d, u = AGE_UNITS[singular]
    edge = -(-18 * u // d)  # smallest count that is not child-only
    n = draw(st.one_of(st.integers(max(0, edge - 2), edge + 2), st.integers(0, 2 * edge)))
    unit = draw(random_case(singular + ("s" if draw(st.booleans()) else "")))
    text = "%d %s" % (n, unit)
    if draw(st.booleans()):
        text = draw(st.sampled_from(("", " ", "\t"))) + text + draw(st.sampled_from(("", " ")))
    return text


max_ages = st.one_of(
    st.just(""),
    st.sampled_from((" ", "  ", "\t", " \t ")),
    _age_with_unit(),
    st.sampled_from(MALFORMED_AGES),
)
healthy_volunteers = st.sampled_from(("true", "false", ""))
overall_statuses = st.sampled_from(ACTIVE_STATUSES + OTHER_STATUSES)
nct_ids = st.integers(0, 99_999_999).map(lambda n: "NCT%08d" % n)


@st.composite
def _phrase(draw) -> str:
    """A vocabulary term, possibly with noise words around it."""
    before = draw(st.lists(st.sampled_from(NOISE_WORDS), max_size=2))
    after = draw(st.lists(st.sampled_from(NOISE_WORDS), max_size=2))
    return " ".join(before + [draw(st.sampled_from(VOCABULARY))] + after)


@st.composite
def study_values(draw) -> str:
    """One list value: vocabulary term, phrase, boundary case, noise, empty or blank."""
    base = draw(st.one_of(
        st.sampled_from(VOCABULARY),
        _phrase(),
        st.sampled_from(BOUNDARY_VALUES),
        st.sampled_from(NOISE_WORDS),
        st.just(""),
        st.sampled_from(_WHITESPACE),
    ))
    return draw(perturb(base))


value_lists = st.lists(study_values(), max_size=4).map(tuple)

brief_titles = st.text(
    alphabet=st.sampled_from(list("abc XYZ,\"\r\n\u00e9\u4e2d")), max_size=20
)


@st.composite
def studies(draw, nct_id: str | None = None) -> Study:
    """One `Study`; `conditions_cell` is the JSON encoding of `conditions`."""
    nct = nct_id if nct_id is not None else draw(nct_ids)
    conditions = draw(value_lists)
    return Study(
        nct_id=nct,
        brief_title=draw(brief_titles),
        overall_status=draw(overall_statuses),
        healthy_volunteers=draw(healthy_volunteers),
        maximum_age=draw(max_ages),
        conditions=conditions,
        mesh_terms=draw(value_lists),
        ancestor_terms=draw(value_lists),
        conditions_cell=encode_list_cell(list(conditions)),
        source_url="https://clinicaltrials.gov/study/%s" % nct,
    )


@st.composite
def study_lists(draw, min_size: int = 0, max_size: int = 8) -> list[Study]:
    """Studies with distinct nctIds."""
    ids = draw(st.lists(nct_ids, min_size=min_size, max_size=max_size, unique=True))
    return [draw(studies(nct_id=i)) for i in ids]


def ma_site_ids(study_list: list[Study]) -> st.SearchStrategy[frozenset[str]]:
    """A subset of the given studies' nctIds: those with at least one MA_Site."""
    ids = sorted(s.nct_id for s in study_list)
    if not ids:
        return st.just(frozenset())
    return st.sets(st.sampled_from(ids)).map(frozenset)


@st.composite
def studies_with_ma(draw, min_size: int = 0, max_size: int = 8
                    ) -> tuple[list[Study], frozenset[str]]:
    """A study list together with its MA-site nctId set."""
    study_list = draw(study_lists(min_size=min_size, max_size=max_size))
    return study_list, draw(ma_site_ids(study_list))
