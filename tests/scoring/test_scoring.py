"""Unit tests for Scoring_Engine null propagation and rounding.

Covers the Scoring_Engine behaviours the data contract pins down for the
`what.json` numbers (design § Scoring_Engine, Part B; Req 4.6, 4.7, 4.8, 9.2,
1.6, 3.6):

- **Absent measure** (Req 4.8, 1.6): a measure with no rows in `places_ma.csv`
  yields `None` for `N` and prevalence, so `adults_18plus`, `p`/`p_low`/`p_high`,
  `prevalence_year`, `low`/`mid`/`high`, and `affected_adults` are all `None`
  (serialized as JSON `null`, never `0`).
- **Zero divisor / zero population** (Req 4.6, 4.7): a measure present only with
  zero population yields `None` prevalence (no weighting mass); a prevalence
  fraction of `0` makes the matching index divisor `0`, so that index value is
  `None` rather than `0`.
- **`null`, not `0`** (Req 1.6, 3.6, 9.2): uncomputable numeric values are
  literally `None`, distinguishable from a legitimately computed `0`.
- **Round-half-to-even** (Req 4.5, 4.6): `low`/`mid`/`high` (2 decimals) and
  `affected_adults` (integer) use Python's banker's-rounding `round`, breaking
  ties toward the even neighbour in both directions.
"""
from __future__ import annotations

from pipeline.scoring.models import DiseaseScope, Prevalence
from pipeline.scoring.scoring import (
    build_what_entry,
    compute_N,
    compute_prevalence,
    population_weighted_index,
)
from pipeline.transform.places_transformer import PlacesRow


# --- small builders so each test states only the fields it exercises ------------

def _places_row(
    measure_id: str,
    *,
    locationid: str = "25001",
    totalpop18plus: str = "100000",
    data_value: str = "10.0",
    low_confidence_limit: str = "9.0",
    high_confidence_limit: str = "11.0",
    year: str = "2023",
) -> PlacesRow:
    return PlacesRow(
        locationname="County",
        locationid=locationid,
        measureid=measure_id,
        measure="",
        data_value=data_value,
        low_confidence_limit=low_confidence_limit,
        high_confidence_limit=high_confidence_limit,
        totalpop18plus=totalpop18plus,
        latitude="",
        longitude="",
        year=year,
    )


def _scope(measure_id: str = "CASTHMA", *, t_ids: set[str] | None = None) -> DiseaseScope:
    ids = set(t_ids or set())
    return DiseaseScope(
        measure_id=measure_id,
        condition="Asthma",
        eligible_ids=set(ids),
        t_ids=ids,
        studies_by_id={},
    )


# --- absent measure -> everything null (Req 4.8, 1.6) ---------------------------

def test_compute_n_is_none_when_measure_absent():
    places = [_places_row("HIGHCHOL")]
    assert compute_N(places, "CASTHMA") is None


def test_compute_prevalence_is_none_when_measure_absent():
    places = [_places_row("HIGHCHOL")]
    assert compute_prevalence(places, "CASTHMA") is None


def test_build_what_entry_nulls_everything_for_absent_measure():
    # places carry a different measure, so CASTHMA is absent entirely.
    places = [_places_row("DIABETES")]
    scope = _scope("CASTHMA", t_ids={"NCT1", "NCT2"})

    entry = build_what_entry(scope, places, "Asthma")

    # T is still a real count; everything derived from N / prevalence is null.
    assert entry["t"] == 2
    for key in (
        "adults_18plus",
        "p",
        "p_low",
        "p_high",
        "prevalence_year",
        "low",
        "mid",
        "high",
        "affected_adults",
    ):
        assert entry[key] is None, key


# --- zero population / zero divisor -> null, not 0 (Req 4.6, 4.7, 9.2) -----------

def test_compute_prevalence_is_none_when_total_population_is_zero():
    # The measure is present, but every county weights nothing.
    places = [_places_row("CASTHMA", totalpop18plus="0")]
    assert compute_prevalence(places, "CASTHMA") is None


def test_compute_n_is_zero_not_none_when_measure_present_with_zero_population():
    # N is a real, computed 0 here (measure present) -- distinct from the absent
    # case which is None.
    places = [_places_row("CASTHMA", totalpop18plus="0")]
    assert compute_N(places, "CASTHMA") == 0


def test_build_what_entry_nulls_prevalence_and_index_on_zero_population():
    places = [_places_row("CASTHMA", totalpop18plus="0")]
    scope = _scope("CASTHMA", t_ids={"NCT1"})

    entry = build_what_entry(scope, places, "Asthma")

    assert entry["adults_18plus"] == 0            # computed 0, measure present
    assert entry["p"] is None                     # no weighting mass -> null
    assert entry["low"] is None
    assert entry["mid"] is None
    assert entry["high"] is None
    assert entry["affected_adults"] is None


def test_population_weighted_index_is_none_not_zero_when_a_prevalence_is_zero():
    # p_high == 0 makes the `low` divisor zero; that value is null, not 0, while
    # the others compute normally.
    prev = Prevalence(p=0.1, p_low=0.05, p_high=0.0, year="2023")
    low, mid, high = population_weighted_index(T=1, N=100000, prev=prev)
    assert low is None
    assert mid is not None and mid != 0
    assert high is not None and high != 0


def test_population_weighted_index_all_none_when_n_or_prev_missing():
    prev = Prevalence(p=0.1, p_low=0.05, p_high=0.2, year="2023")
    assert population_weighted_index(T=1, N=None, prev=prev) == (None, None, None)
    assert population_weighted_index(T=1, N=100000, prev=None) == (None, None, None)


def test_index_is_null_distinct_from_a_computed_zero():
    # A T of 0 produces a genuine computed 0.0 (not null); the zero-divisor case
    # produces null. Both must be distinguishable.
    prev = Prevalence(p=0.1, p_low=0.05, p_high=0.2, year="2023")
    low, mid, high = population_weighted_index(T=0, N=100000, prev=prev)
    assert (low, mid, high) == (0.0, 0.0, 0.0)

    zero_divisor = Prevalence(p=0.0, p_low=0.0, p_high=0.0, year="2023")
    assert population_weighted_index(T=1, N=100000, prev=zero_divisor) == (
        None,
        None,
        None,
    )


# --- round-half-to-even on the 2-decimal index (Req 4.5) ------------------------

def test_population_weighted_index_rounds_half_to_even_down():
    # mid = T/(N*p)*100000 = 1/(800000*1.0)*100000 = 0.125 -> 0.12 (even).
    prev = Prevalence(p=1.0, p_low=1.0, p_high=1.0, year="2023")
    _, mid, _ = population_weighted_index(T=1, N=800000, prev=prev)
    assert mid == 0.12


def test_population_weighted_index_rounds_half_to_even_up():
    # mid = 3/(800000*1.0)*100000 = 0.375 -> 0.38 (even).
    prev = Prevalence(p=1.0, p_low=1.0, p_high=1.0, year="2023")
    _, mid, _ = population_weighted_index(T=3, N=800000, prev=prev)
    assert mid == 0.38


def test_population_weighted_index_rounds_half_to_even_both_directions():
    prev = Prevalence(p=1.0, p_low=1.0, p_high=1.0, year="2023")
    # 0.625 ties to the even neighbour 0.62 (down), confirming the rule applies
    # regardless of which side is even.
    _, mid, _ = population_weighted_index(T=5, N=800000, prev=prev)
    assert mid == 0.62


# --- round-half-to-even on integer affected_adults (Req 4.5, 4.6) ---------------

def _affected(pop: str, value: str) -> object:
    # Single county: N = pop, p = value/100, so affected_adults = round(N*p).
    places = [_places_row("CASTHMA", totalpop18plus=pop, data_value=value,
                           low_confidence_limit=value, high_confidence_limit=value)]
    scope = _scope("CASTHMA", t_ids={"NCT1"})
    return build_what_entry(scope, places, "Asthma")["affected_adults"]


def test_affected_adults_rounds_half_down_to_even():
    # N*p = 2 * 25/100 = 0.5 -> 0 (even).
    assert _affected("2", "25") == 0


def test_affected_adults_rounds_half_up_to_even():
    # N*p = 2 * 75/100 = 1.5 -> 2 (even).
    assert _affected("2", "75") == 2


def test_affected_adults_rounds_half_to_even_both_directions():
    # 2.5 -> 2 (down to even) and 3.5 -> 4 (up to even).
    assert _affected("2", "125") == 2
    assert _affected("2", "175") == 4


def test_affected_adults_is_an_int_not_a_float():
    assert isinstance(_affected("2", "75"), int)
