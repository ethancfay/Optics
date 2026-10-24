"""Smoke test for the Recall_Checker with a stub client (task 4.1).

Full stub-client unit tests are in test_recall_checker.py (task 4.3).
"""
import io
import json
import urllib.parse
from datetime import date
from types import SimpleNamespace

import pytest

from pipeline.errors import PipelineError
from pipeline.mapping import recall_checker as rc
from pipeline.mapping.grouping_engine import StudyDiseaseRow


class StubClient:
    def __init__(self, bodies):
        self.bodies = dict(bodies)  # recall_query_term -> body bytes
        self.urls = []

    def get(self, url):
        self.urls.append(url)
        term = urllib.parse.parse_qs(urllib.parse.urlsplit(url).query)["query.cond"][0]
        return self.bodies[term]


def _row(nct, mid, status):
    return StudyDiseaseRow(nct, mid, mid.lower(), status, "", "conditions", "x")


RULES = SimpleNamespace(diseases=(
    SimpleNamespace(measureid="DIABETES", label="Diabetes", recall_query_term="Diabetes"),
    SimpleNamespace(measureid="CASTHMA", label="Asthma", recall_query_term="Asthma"),
))
STUDIES = {
    "NCT1": SimpleNamespace(overall_status="RECRUITING"),
    "NCT2": SimpleNamespace(overall_status="ACTIVE_NOT_RECRUITING"),
    "NCT3": SimpleNamespace(overall_status="COMPLETED"),
    "NCT4": SimpleNamespace(overall_status="RECRUITING"),  # no MA site
}
MA_IDS = frozenset({"NCT1", "NCT2", "NCT3"})
ROWS = [
    _row("NCT1", "CASTHMA", "included"),
    _row("NCT2", "CASTHMA", "excluded"),
    _row("NCT3", "CASTHMA", "included"),
    _row("NCT4", "CASTHMA", "included"),
    _row("NCT1", "DIABETES", "questionable"),
]


def test_check_serialize_and_warnings():
    client = StubClient({"Asthma": b'{"totalCount": 2}', "Diabetes": b'{"totalCount": 0}'})
    result = rc.check(RULES, ROWS, STUDIES, MA_IDS, client, date(2025, 1, 2))

    assert [e.measureid for e in result.entries] == ["CASTHMA", "DIABETES"]
    assert len(client.urls) == 2 and "query.cond=Asthma" in client.urls[0]
    asthma, diabetes = result.entries
    assert (asthma.found_count, asthma.included_count, asthma.ctgov_count) == (2, 1, 2)
    assert (float(asthma.ratio_found), float(asthma.ratio_included), asthma.flagged) == (1.0, 0.5, False)
    assert diabetes.ratio_found is None and diabetes.flagged

    data = rc.serialize(result)
    assert data.endswith(b"}\n") and b"\r" not in data
    obj = json.loads(data)
    assert list(obj) == ["check_date", "threshold", "diseases"]
    assert obj["check_date"] == "2025-01-02" and obj["threshold"] == 0.8
    assert list(obj["diseases"][0]) == [
        "measureid", "disease_label", "recall_query_term", "found_count", "included_count",
        "ctgov_count", "ratio_found", "ratio_included", "flagged", "request_url",
    ]
    assert obj["diseases"][1]["ratio_found"] is None

    out = io.StringIO()
    rc.emit_warnings(result, out)
    assert out.getvalue() == (
        "warning: recall DIABETES: found_count=1 included_count=0 ctgov_count=0 ratio_found=null\n"
    )


def test_rounding_half_up_and_flag():
    assert rc.rounded_ratio(7995, 10000) == rc.Fraction(800, 1000)
    assert not rc.is_flagged(rc.rounded_ratio(7995, 10000))
    assert rc.is_flagged(rc.rounded_ratio(7994, 10000))
    assert rc.rounded_ratio(9, 8) == rc.Fraction(1125, 1000)


@pytest.mark.parametrize("body", [b"not json", b"{}", b'{"totalCount": true}', b'{"totalCount": -1}'])
def test_bad_body_raises_without_body_text(body):
    client = StubClient({"Asthma": body, "Diabetes": b'{"totalCount": 1}'})
    with pytest.raises(PipelineError) as info:
        rc.check(RULES, ROWS, STUDIES, MA_IDS, client, date(2025, 1, 2))
    msg = str(info.value)
    assert msg.startswith("recall check failed for CASTHMA: https://clinicaltrials.gov/")
    assert "not json" not in msg
