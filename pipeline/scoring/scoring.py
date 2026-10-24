"""Scoring_Engine (design § Scoring_Engine, Part B; Req 4.3-4.8, 4.11, 1.6, 3.6).

Computes the `what.json` numbers for a single disease exactly per the data
contract:

- `T` is the count of distinct eligible-and-recruiting nctIds (`scope.t_ids`).
- `N` is adults 18+ summed over the distinct MA counties present for the
  measure (counted once per county by `locationid`).
- Prevalence `p` / `p_low` / `p_high` are MA crude prevalence as FRACTIONS,
  population-weighted over counties: `p = sum(pop18 * value/100) / sum(pop18)`.
- The per-100,000 index uses `low = T/(N*p_high)*100000`,
  `high = T/(N*p_low)*100000`, `mid = T/(N*p)*100000` (note `low` uses the
  HIGH confidence limit and `high` uses the LOW limit — larger prevalence gives
  a lower per-capita index).

Every uncomputable value is `None` (serialized as JSON `null`), never `0`
(Req 1.6, 3.6): a divisor of 0, an absent measure, or a zero total population
propagates to `null`. All rounding is round-half-to-even via Python's built-in
`round`, to 2 decimals for the index and to the nearest integer for
`affected_adults`.
"""
from __future__ import annotations

from typing import Iterable
from urllib.parse import quote

from pipeline.scoring.models import (
    DiseaseScope,
    PlacesRow,
    Prevalence,
)

LabelCount = dict[str, object]        # {"label": str, "count": int}


def compute_T(scope: DiseaseScope) -> int:
    """Count of distinct nctIds that count toward T (Req 4.3).

    `scope.t_ids` is already restricted by the MA_Index_Builder to eligible MA
    studies with `overallStatus == "RECRUITING"` that also have >=1 MA site
    whose own site status is `RECRUITING`; unknown site status never
    contributes. The count is distinct `nctId` because `t_ids` is a set.
    """
    return len(scope.t_ids)


def _parse_int(cell: str) -> int | None:
    """Parse a source-text population cell; blank/non-numeric becomes `None`."""
    cell = (cell or "").strip()
    if not cell:
        return None
    try:
        return int(cell)
    except ValueError:
        return None


def _parse_float(cell: str) -> float | None:
    """Parse a source-text value cell; blank/non-numeric becomes `None`."""
    cell = (cell or "").strip()
    if not cell:
        return None
    try:
        return float(cell)
    except ValueError:
        return None


def compute_N(places: Iterable[PlacesRow], measure_id: str) -> int | None:
    """Adults 18+ summed over the distinct MA counties present (Req 4.4).

    Counts each county once (by `locationid`), keeping the first row seen for a
    county. Returns `None` when the measure is absent from `places_ma.csv`
    (a null result propagates to a null index rather than `0`; Req 4.8, 1.6).
    Counties whose `totalpop18plus` cell is blank contribute nothing.
    """
    rows = [r for r in places if r.measureid == measure_id]
    if not rows:
        return None
    pop_by_county: dict[str, int] = {}
    for row in rows:
        if row.locationid in pop_by_county:
            continue
        pop = _parse_int(row.totalpop18plus)
        pop_by_county[row.locationid] = pop if pop is not None else 0
    return sum(pop_by_county.values())


def compute_prevalence(places: Iterable[PlacesRow], measure_id: str) -> Prevalence | None:
    """Population-weighted MA crude prevalence as fractions (Req 4.4).

    `p = sum(pop18 * value/100) / sum(pop18)` over the rows for the measure, and
    likewise for `p_low` / `p_high` using the confidence-limit cells. Returns
    `None` when the measure is absent or the total weighting population is 0, so
    an unavailable prevalence propagates to a null index (Req 4.6, 4.8, 1.6).

    Rows with a blank population weight nothing; a blank value cell contributes
    nothing to that cell's weighted numerator.
    """
    rows = [r for r in places if r.measureid == measure_id]
    if not rows:
        return None

    pop_total = 0
    num_p = 0.0
    num_low = 0.0
    num_high = 0.0
    for row in rows:
        pop = _parse_int(row.totalpop18plus)
        if pop is None or pop == 0:
            continue
        pop_total += pop
        value = _parse_float(row.data_value)
        low = _parse_float(row.low_confidence_limit)
        high = _parse_float(row.high_confidence_limit)
        if value is not None:
            num_p += pop * value / 100
        if low is not None:
            num_low += pop * low / 100
        if high is not None:
            num_high += pop * high / 100

    if pop_total == 0:
        return None

    return Prevalence(
        p=num_p / pop_total,
        p_low=num_low / pop_total,
        p_high=num_high / pop_total,
        year=rows[0].year,
    )


def population_weighted_index(
    T: int, N: int | None, prev: Prevalence | None
) -> tuple[float | None, float | None, float | None]:
    """Return `(low, mid, high)` per 100,000 affected adults, or `None`s (Req 4.5).

    - `low  = T / (N * p_high) * 100000`
    - `mid  = T / (N * p)      * 100000`
    - `high = T / (N * p_low)  * 100000`

    Each value is rounded to 2 decimals with round-half-to-even (Python's
    built-in `round`). Any value whose divisor is 0 — or when `N` / `prev` is
    `None` — is `None`, never `0` (Req 4.7, 4.8, 1.6). `low` uses `p_high` and
    `high` uses `p_low` on purpose: a larger prevalence gives a lower per-capita
    index, keeping `low <= mid <= high`.
    """
    if N is None or prev is None:
        return (None, None, None)

    def rate(divisor_prev: float) -> float | None:
        denom = N * divisor_prev
        return round(T / denom * 100000, 2) if denom > 0 else None

    low = rate(prev.p_high)
    high = rate(prev.p_low)
    mid = rate(prev.p)
    return (low, mid, high)


def _ctgov_url(condition: str) -> str:
    """The data-contract clinicaltrials.gov search URL for a condition (Req 4.11)."""
    return (
        "https://clinicaltrials.gov/search?"
        f"cond={quote(condition)}&locStr=Massachusetts"
    )


def build_what_entry(
    scope: DiseaseScope, places: Iterable[PlacesRow], condition: str
) -> dict[str, object]:
    """Assemble the contract `what.json` entry for one disease (Req 4.3-4.8, 4.11).

    `affected_adults = round(N * p)` with round-half-to-even, or `None` when `N`
    or prevalence is unavailable. `adults_18plus` is `N` (null only when the
    measure is absent). `low` / `mid` / `high` and the `p*` fractions are `None`
    rather than `0` when uncomputable (Req 1.6, 3.6).
    """
    places = list(places)
    T = compute_T(scope)
    N = compute_N(places, scope.measure_id)
    prev = compute_prevalence(places, scope.measure_id)
    low, mid, high = population_weighted_index(T, N, prev)
    affected = round(N * prev.p) if (N is not None and prev is not None) else None
    return {
        "condition": condition,
        "measure_id": scope.measure_id,
        "low": low,
        "mid": mid,
        "high": high,
        "t": T,
        "affected_adults": affected,
        "adults_18plus": N,
        "p_low": prev.p_low if prev else None,
        "p_high": prev.p_high if prev else None,
        "p": prev.p if prev else None,
        "prevalence_year": prev.year if prev else None,
        "ctgov_url": _ctgov_url(condition),
    }
