"""Property 12: Ratio rounding and flag depend only on ratio_found
(condition-grouping design § Recall_Checker; Req 10.3, 10.4, 13.5, Open Items 11, 12).

For any integers found >= included >= 0 and ctgov >= 0, `ratio_found` and
`ratio_included` are both null when ctgov = 0 and otherwise equal
floor(1000 * count / ctgov + 1/2) / 1000 computed exactly (no cap at 1.0);
`flagged` is true exactly when `ratio_found` is null or below 0.800; and for a
fixed `ratio_found`, changing `included` never changes `flagged`.

The oracle uses integer arithmetic only:
floor(1000 * c / g + 1/2) = (2000 * c + g) // (2 * g).
Inputs are biased towards the 0.7995 half boundary.
"""
import json
from datetime import date
from fractions import Fraction
from types import SimpleNamespace

from hypothesis import given
from hypothesis import strategies as st

from pipeline.mapping import recall_checker as rc
from pipeline.mapping.grouping_engine import StudyDiseaseRow


def _oracle_ratio(count, ctgov):
    if ctgov == 0:
        return None
    return Fraction((2000 * count + ctgov) // (2 * ctgov), 1000)


def _oracle_flag(ratio_found):
    # 0.800 is 800/1000; compare thousandths as integers.
    return ratio_found is None or ratio_found * 1000 < 800


@st.composite
def ctgov_and_found(draw, max_ctgov=20000):
    """(ctgov, found) pairs, about half placed within a few counts of 0.7995 * ctgov."""
    ctgov = draw(st.one_of(
        st.just(0),
        st.integers(1, 50),
        st.integers(1, max_ctgov),
        st.sampled_from([2000, 4000, 10000, 20000]),  # 0.7995 exactly representable
    ))
    if ctgov > 0 and draw(st.booleans()):
        # Values just around the half boundary 0.7995 * ctgov (floor(1599 * g / 2000)).
        centre = (1599 * ctgov) // 2000
        found = max(0, centre + draw(st.integers(-2, 2)))
    else:
        # Not capped: counts above ctgov are allowed (Open Item 12).
        found = draw(st.integers(0, 2 * max(ctgov, 1) + 5))
    return ctgov, found


# Feature: condition-grouping, Property 12: Ratio rounding and flag depend only on ratio_found
@given(ctgov_and_found(), st.data())
def test_rounded_ratio_and_flag_match_oracle(pair, data):
    ctgov, found = pair
    included = data.draw(st.integers(0, found))
    r_found = rc.rounded_ratio(found, ctgov)
    r_included = rc.rounded_ratio(included, ctgov)
    assert r_found == _oracle_ratio(found, ctgov)
    assert r_included == _oracle_ratio(included, ctgov)
    if ctgov == 0:
        assert r_found is None and r_included is None
    else:
        assert isinstance(r_found, Fraction) and (r_found * 1000).denominator == 1
    assert rc.is_flagged(r_found) == _oracle_flag(r_found)


def test_named_boundary_examples():
    assert rc.rounded_ratio(7995, 10000) == Fraction(800, 1000)
    assert not rc.is_flagged(rc.rounded_ratio(7995, 10000))
    assert rc.rounded_ratio(7994, 10000) == Fraction(799, 1000)
    assert rc.is_flagged(rc.rounded_ratio(7994, 10000))
    assert rc.is_flagged(None)
    assert rc.rounded_ratio(3, 2) == Fraction(1500, 1000)  # not capped


class _StubClient:
    def __init__(self, total):
        self.body = json.dumps({"totalCount": total}).encode("utf-8")
        self.urls = []

    def get(self, url):
        self.urls.append(url)
        return self.body


_RULES = SimpleNamespace(diseases=(
    SimpleNamespace(measureid="CASTHMA", label="Asthma", recall_query_term="Asthma"),
))


def _run(found, included, ctgov):
    """Run `check` on `found` active MA studies, the first `included` of them included."""
    studies, rows = {}, []
    for i in range(found):
        nct = "NCT%08d" % i
        studies[nct] = SimpleNamespace(overall_status="RECRUITING")
        status = "included" if i < included else ("questionable" if i % 2 else "excluded")
        rows.append(StudyDiseaseRow(nct, "CASTHMA", "casthma", status, "", "conditions", "asthma"))
    client = _StubClient(ctgov)
    result = rc.check(_RULES, rows, studies, frozenset(studies), client, date(2025, 1, 2))
    assert len(client.urls) == 1
    (entry,) = result.entries
    return result, entry


# Feature: condition-grouping, Property 12: Ratio rounding and flag depend only on ratio_found
@given(ctgov_and_found(max_ctgov=600), st.data())
def test_check_flag_independent_of_included(pair, data):
    ctgov, found = pair
    inc_a = data.draw(st.integers(0, found), label="included_a")
    inc_b = data.draw(st.integers(0, found), label="included_b")
    expected_found = _oracle_ratio(found, ctgov)
    flags = []
    for included in (inc_a, inc_b):
        result, entry = _run(found, included, ctgov)
        assert (entry.found_count, entry.included_count, entry.ctgov_count) == (found, included, ctgov)
        assert entry.ratio_found == expected_found
        assert entry.ratio_included == _oracle_ratio(included, ctgov)
        assert entry.flagged == _oracle_flag(expected_found)
        flags.append(entry.flagged)
        (obj,) = json.loads(rc.serialize(result))["diseases"]
        for key, value in (("ratio_found", entry.ratio_found), ("ratio_included", entry.ratio_included)):
            assert obj[key] == (None if value is None else float(value))
        assert obj["flagged"] == entry.flagged
    assert flags[0] == flags[1]
