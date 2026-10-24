"""Property 5: Exact age threshold (condition-grouping design § Age_Parser).

For any n >= 0 and any of the 12 units in any letter case, `is_child_only(f"{n} {unit}")`
is true exactly when n * d < 18 * u as integers, where the unit is d/u years (Req 5.1).
The oracle uses plain integers, independent of the parser's own unit table.
"""

from fractions import Fraction

from hypothesis import given, settings
from hypothesis import strategies as st

from pipeline.mapping.age_parser import is_child_only, parse_max_age

# Unit -> (d, u): one unit is d/u years (Req 5.1).
_UNITS: dict[str, tuple[int, int]] = {
    "year": (1, 1),
    "month": (1, 12),
    "week": (10000, 521775),
    "day": (4, 1461),
    "hour": (1, 8766),
    "minute": (1, 525960),
}


def _boundary(d: int, u: int) -> int:
    """Smallest n with n * d >= 18 * u, i.e. the first count that is not child-only."""
    return -(-18 * u // d)


@st.composite
def _unit_text(draw):
    """One of the 12 unit spellings (singular or plural) in random letter case."""
    singular = draw(st.sampled_from(sorted(_UNITS)))
    word = singular + ("s" if draw(st.booleans()) else "")
    flips = draw(st.lists(st.booleans(), min_size=len(word), max_size=len(word)))
    return singular, "".join(c.upper() if f else c for c, f in zip(word, flips))


@st.composite
def _age_case(draw):
    singular, unit = draw(_unit_text())
    d, u = _UNITS[singular]
    edge = _boundary(d, u)
    n = draw(st.one_of(
        # Biased near the 18-year boundary of this unit.
        st.integers(max(0, edge - 3), edge + 3),
        st.integers(0, 2 * edge),
        st.integers(0, 10**12),
    ))
    return n, unit, d, u


# Feature: condition-grouping, Property 5: Exact age threshold
@settings(max_examples=300)
@given(_age_case())
def test_child_only_exactly_below_18_years(case):
    """**Validates: Requirements 5.1, 5.6**"""
    n, unit, d, u = case
    text = f"{n} {unit}"
    assert is_child_only(text) == (n * d < 18 * u)
    assert parse_max_age(text) == Fraction(n * d, u)


def test_boundaries_match_requirement_examples():
    """The integer boundaries agree with the examples listed in Req 5.6."""
    assert {s: _boundary(*du) for s, du in _UNITS.items() if s != "minute"} == {
        "year": 18, "month": 216, "week": 940, "day": 6575, "hour": 157788,
    }
