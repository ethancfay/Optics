"""Age_Parser (condition-grouping design § Age_Parser; Req 5.1, 5.2, 5.4, 5.6, 5.7).

Converts a ClinicalTrials.gov `maximumAge` string into an exact number of years.
Only `maximumAge` is read; `minimumAge` and `stdAges` play no part (Req 5.7).
All arithmetic uses `Fraction`, so the child-only threshold has no rounding error.
"""
from __future__ import annotations

import re
from fractions import Fraction

# ASCII digits only, exactly one space, ASCII letters; applied with fullmatch after strip().
_AGE_RE = re.compile(r"([0-9]+) ([A-Za-z]+)")

# 1 year = 12 months = 52.1775 weeks = 365.25 days = 8,766 hours = 525,960 minutes (Req 5.1).
_SINGULAR_YEARS: dict[str, Fraction] = {
    "year": Fraction(1),
    "month": Fraction(1, 12),
    "week": Fraction(10000, 521775),
    "day": Fraction(4, 1461),
    "hour": Fraction(1, 8766),
    "minute": Fraction(1, 525960),
}
_YEARS_PER_UNIT: dict[str, Fraction] = {
    **_SINGULAR_YEARS,
    **{unit + "s": years for unit, years in _SINGULAR_YEARS.items()},
}

NO_LIMIT = "no_limit"
UNPARSEABLE = "unparseable"

_CHILD_LIMIT = Fraction(18)


def parse_max_age(text: str) -> Fraction | str:
    """Return the age in years, `NO_LIMIT` for empty/whitespace, else `UNPARSEABLE`."""
    stripped = text.strip()
    if not stripped:
        return NO_LIMIT
    match = _AGE_RE.fullmatch(stripped)
    if match is None:
        return UNPARSEABLE
    years_per_unit = _YEARS_PER_UNIT.get(match.group(2).casefold())
    if years_per_unit is None:
        return UNPARSEABLE
    return int(match.group(1)) * years_per_unit


def is_child_only(text: str) -> bool:
    """True exactly when `text` parses to an age strictly below 18 years."""
    age = parse_max_age(text)
    return isinstance(age, Fraction) and age < _CHILD_LIMIT
