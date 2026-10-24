"""Property-based tests for the Scoring_Engine (design § Correctness Properties).

Property 1 (Index ordering) — for every `what.json` entry whose `low`, `mid`,
and `high` are all non-null, the per-100,000 index satisfies `low <= mid <=
high`. The data contract builds `low` from the HIGH confidence limit (`p_high`)
and `high` from the LOW limit (`p_low`), so a larger prevalence yields a lower
per-capita index and the ordering must hold whenever all three are computable.

**Validates: Requirements 9.1**
"""
from __future__ import annotations

from hypothesis import given

from pipeline.scoring.index import build_scopes
from pipeline.scoring.scoring import build_what_entry
from tests.strategies import scoring_inputs


@given(scoring_inputs())
def test_index_ordering_low_mid_high(inputs: dict) -> None:
    """Every what.json entry with all three index values non-null is ordered low<=mid<=high."""
    scopes = build_scopes(inputs["studies"], inputs["sites"], inputs["diseases"])
    for scope in scopes.values():
        entry = build_what_entry(scope, inputs["places"], scope.condition)
        low, mid, high = entry["low"], entry["mid"], entry["high"]
        if low is not None and mid is not None and high is not None:
            assert low <= mid <= high


# --- Property 2: Prevalence bounds -------------------------------------------
# For every `what.json` entry whose `p_low`, `p`, `p_high` are non-null, the
# population-weighted MA prevalence satisfies `0 <= p_low <= p <= p_high <= 1`.
# PLACES values are percentages in 0..100, and `compute_prevalence` divides each
# by 100, so the fractions land in 0..1. The ordering `p_low <= p <= p_high`
# follows from the county confidence limits being ordered (`low <= value <=
# high`): a population-weighted mean of three per-county series that are
# pointwise ordered stays ordered. The shared `places_rows` strategy may blank a
# confidence/value cell to exercise null propagation (task 4.4); that degenerate
# case drops a single weighted numerator and is intentionally excluded here, so
# this test draws PLACES rows with all three cells present and ordered — the
# exact input space in which the design states the bound holds.

from hypothesis import strategies as st

from pipeline.transform.places_transformer import PlacesRow
from tests.strategies import (
    MA_COUNTY_FIPS,
    SCORING_MEASURE_POOL,
    YEARS,
    disease_matches,
    site_rows,
    study_rows,
)


@st.composite
def _ordered_places_rows(draw) -> list[PlacesRow]:
    """PLACES rows for MA counties with every (low, value, high) cell present and ordered.

    Reuses the shared county/measure/year pools and the same population cells
    (including "0" and "" for the zero/blank-population branches) as
    `tests.strategies.places_rows`, but never blanks a confidence/value cell, so
    the per-county ordering `low <= value <= high` holds for every row. A subset
    of measures and counties is still drawn so "missing measure" and
    "county count != 14" cases remain reachable.
    """
    rows: list[PlacesRow] = []
    measures = draw(st.lists(st.sampled_from(SCORING_MEASURE_POOL), unique=True, max_size=4))
    counties = draw(st.lists(st.sampled_from(MA_COUNTY_FIPS), unique=True, max_size=14))
    year = draw(st.sampled_from(YEARS))
    for measure_id in measures:
        for fips in counties:
            low, value, high = sorted(draw(st.lists(
                st.floats(min_value=0.0, max_value=100.0,
                          allow_nan=False, allow_infinity=False),
                min_size=3, max_size=3)))
            pop = draw(st.sampled_from(["0", "1000", "250000", ""]))
            rows.append(PlacesRow(
                locationname="",
                locationid=fips,
                measureid=measure_id,
                measure="",
                data_value=repr(value),
                low_confidence_limit=repr(low),
                high_confidence_limit=repr(high),
                totalpop18plus=pop,
                latitude="",
                longitude="",
                year=year,
            ))
    return rows


@st.composite
def _bounds_inputs(draw) -> dict:
    """A scoring input set whose PLACES rows have ordered, fully-populated cells."""
    return {
        "studies": draw(study_rows()),
        "sites": draw(site_rows()),
        "places": draw(_ordered_places_rows()),
        "diseases": draw(disease_matches()),
    }


@given(_bounds_inputs())
def test_prevalence_bounds(inputs: dict) -> None:
    """Every what.json entry with non-null prevalence satisfies 0<=p_low<=p<=p_high<=1."""
    scopes = build_scopes(inputs["studies"], inputs["sites"], inputs["diseases"])
    for scope in scopes.values():
        entry = build_what_entry(scope, inputs["places"], scope.condition)
        p_low, p, p_high = entry["p_low"], entry["p"], entry["p_high"]
        if p_low is not None and p is not None and p_high is not None:
            assert 0 <= p_low <= p <= p_high <= 1
