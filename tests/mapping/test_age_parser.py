"""Age_Parser example tests (condition-grouping Req 5.1, 5.2, 5.4, 5.6, 5.7, 13.3)."""
from fractions import Fraction

import pytest

from pipeline.mapping.age_parser import NO_LIMIT, UNPARSEABLE, is_child_only, parse_max_age

CHILD_ONLY = ("17 Years", "215 Months", "939 Weeks", "6574 Days", "157787 Hours", "0 Years")
NOT_CHILD_ONLY = ("18 Years", "216 Months", "940 Weeks", "6575 Days", "157788 Hours")
UNPARSEABLE_VALUES = (
    "-1 Years", "1.5 Years", "17Years", "17 Decades", "17", "Years",
    "17  Years", "\u0661\u0667 Years", "\uff11\uff17 Years",
)


@pytest.mark.parametrize("text", CHILD_ONLY)
def test_child_only_examples(text):
    assert is_child_only(text)


@pytest.mark.parametrize("text", NOT_CHILD_ONLY)
def test_not_child_only_examples(text):
    assert not is_child_only(text)


@pytest.mark.parametrize("text", ("", " ", "\t\n "))
def test_empty_or_whitespace_is_no_limit(text):
    assert parse_max_age(text) == NO_LIMIT
    assert not is_child_only(text)


@pytest.mark.parametrize("text", UNPARSEABLE_VALUES)
def test_malformed_values_are_unparseable(text):
    assert parse_max_age(text) == UNPARSEABLE
    assert not is_child_only(text)


def test_exact_conversions():
    assert parse_max_age("157788 Hours") == Fraction(18)
    assert parse_max_age("939 Weeks") == Fraction(9390000, 521775)
    assert parse_max_age("525960 Minutes") == Fraction(1)
    assert parse_max_age("1461 Days") == Fraction(4)


@pytest.mark.parametrize("text", ("1 years", "2 Year", "  17 YEARS  ", "3 mOnTh", "1 minute"))
def test_unit_case_and_number_insensitive(text):
    assert isinstance(parse_max_age(text), Fraction)
