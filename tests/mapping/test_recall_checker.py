"""Recall_Checker stub-client unit tests (condition-grouping Req 10.1-10.7, 13.5).

The stub client returns a configured body per Recall_Query_Term and records
each requested URL. No test touches the network.
"""
import io
import json
import urllib.parse
from datetime import date
from fractions import Fraction

import pytest

from pipeline.data.http_client import HttpStatusError
from pipeline.errors import PipelineError
from pipeline.io.csv_writer import quote_cell
from pipeline.mapping import recall_checker as rc
from pipeline.mapping.grouping_engine import StudyDiseaseRow
from pipeline.mapping.inputs import SITES_HEADER, STUDIES_HEADER, InputPaths, Study, read_inputs
from pipeline.mapping.rules_loader import Disease, RulesConfig

TODAY = date(2025, 3, 4)


class StubClient:
    """Returns `bodies[term]` (bytes) or raises it if it is an exception."""

    def __init__(self, bodies):
        self.bodies = dict(bodies)
        self.urls = []

    def get(self, url):
        self.urls.append(url)
        term = urllib.parse.parse_qs(urllib.parse.urlsplit(url).query)["query.cond"][0]
        body = self.bodies[term]
        if isinstance(body, BaseException):
            raise body
        return body


def _total(n):
    return json.dumps({"totalCount": n, "studies": []}).encode("utf-8")


def _disease(mid, label, term):
    return Disease(measureid=mid, label=label, ancestor_only_status="questionable",
                   recall_query_term=term, terms=())


def _rules(*diseases):
    return RulesConfig(diseases=tuple(sorted(diseases, key=lambda d: d.measureid)), seed=1)


def _study(nct, status="RECRUITING"):
    return Study(nct_id=nct, brief_title="t", overall_status=status, healthy_volunteers="",
                 maximum_age="", conditions=(), mesh_terms=(), ancestor_terms=(),
                 conditions_cell="[]", source_url="https://clinicaltrials.gov/study/" + nct)


def _row(nct, mid, status):
    return StudyDiseaseRow(nct, mid, mid.lower(), status, "", "conditions", "x")


ASTHMA = _disease("CASTHMA", "Current asthma", "Asthma")
DIABETES = _disease("DIABETES", "Diagnosed diabetes", "Diabetes Mellitus")
COPD = _disease("COPD", "COPD", "Pulmonary Disease, Chronic Obstructive")


# --- URL parameters and request order (Req 10.2) ---------------------------

def test_request_url_parameters():
    url = rc.request_url("Pulmonary Disease, Chronic Obstructive")
    parts = urllib.parse.urlsplit(url)
    assert (parts.scheme, parts.netloc, parts.path) == ("https", "clinicaltrials.gov",
                                                        "/api/v2/studies")
    assert urllib.parse.parse_qsl(parts.query) == [
        ("query.cond", "Pulmonary Disease, Chronic Obstructive"),
        ("query.locn", "Massachusetts"),
        ("filter.overallStatus", "RECRUITING,NOT_YET_RECRUITING,ACTIVE_NOT_RECRUITING"),
        ("countTotal", "true"),
        ("pageSize", "1"),
        ("fields", "NCTId"),
    ]
    assert " " not in url  # fully percent-encoded


def test_one_request_per_disease_in_measureid_order():
    client = StubClient({"Asthma": _total(1), "Diabetes Mellitus": _total(1),
                         "Pulmonary Disease, Chronic Obstructive": _total(1)})
    # Rules given in a non-sorted order: requests still go in measureid order.
    rules = RulesConfig(diseases=(DIABETES, COPD, ASTHMA), seed=1)
    result = rc.check(rules, [], {}, frozenset(), client, TODAY)
    assert client.urls == [rc.request_url("Asthma"),
                           rc.request_url("Pulmonary Disease, Chronic Obstructive"),
                           rc.request_url("Diabetes Mellitus")]
    assert [e.measureid for e in result.entries] == ["CASTHMA", "COPD", "DIABETES"]
    assert [e.request_url for e in result.entries] == client.urls
    assert all(e.found_count == 0 and e.included_count == 0 for e in result.entries)


# --- found_count / included_count (Req 10.1) --------------------------------

def test_counts_by_match_status_status_and_ma_site():
    studies = {
        "NCT01": _study("NCT01", "RECRUITING"),
        "NCT02": _study("NCT02", "NOT_YET_RECRUITING"),
        "NCT03": _study("NCT03", "ACTIVE_NOT_RECRUITING"),
        "NCT04": _study("NCT04", "COMPLETED"),       # not active
        "NCT05": _study("NCT05", "RECRUITING"),      # no MA site
        "NCT06": _study("NCT06", "WITHDRAWN"),       # not active
    }
    ma_ids = frozenset({"NCT01", "NCT02", "NCT03", "NCT04", "NCT06"})
    rows = [
        _row("NCT01", "CASTHMA", "included"),
        _row("NCT02", "CASTHMA", "questionable"),
        _row("NCT03", "CASTHMA", "excluded"),
        _row("NCT04", "CASTHMA", "included"),
        _row("NCT05", "CASTHMA", "included"),
        _row("NCT06", "CASTHMA", "questionable"),
        _row("NCT01", "DIABETES", "excluded"),
    ]
    assert rc.found_count(rows, studies, ma_ids, "CASTHMA") == 3
    assert rc.included_count(rows, studies, ma_ids, "CASTHMA") == 1
    assert rc.found_count(rows, studies, ma_ids, "DIABETES") == 1
    assert rc.included_count(rows, studies, ma_ids, "DIABETES") == 0
    assert rc.found_count(rows, studies, ma_ids, "COPD") == 0

    client = StubClient({"Asthma": _total(4), "Diabetes Mellitus": _total(2)})
    result = rc.check(_rules(ASTHMA, DIABETES), rows, studies, ma_ids, client, TODAY)
    asthma, diabetes = result.entries
    assert (asthma.found_count, asthma.included_count, asthma.ctgov_count) == (3, 1, 4)
    assert (asthma.ratio_found, asthma.ratio_included) == (Fraction(750, 1000), Fraction(250, 1000))
    assert (diabetes.found_count, diabetes.included_count) == (1, 0)
    assert diabetes.ratio_included == 0


def _csv(header, rows):
    lines = [",".join(header)]
    for cells in rows:
        row = {c: "" for c in header}
        row.update(cells)
        lines.append(",".join(quote_cell(row[c]) for c in header))
    return ("\n".join(lines) + "\n").encode("utf-8")


def test_study_with_several_ma_sites_counted_once(tmp_path):
    lists = {c: "[]" for c in ("phases", "stdAges", "conditions", "interventionTypes",
                               "interventionNames", "meshTerms", "meshIds",
                               "ancestorTerms", "ancestorIds")}
    (tmp_path / "studies.csv").write_bytes(_csv(STUDIES_HEADER, [
        dict(lists, nctId="NCT1", overallStatus="RECRUITING"),
        dict(lists, nctId="NCT2", overallStatus="RECRUITING"),
    ]))
    (tmp_path / "sites.csv").write_bytes(_csv(SITES_HEADER, [
        {"nctId": "NCT1", "state": "Massachusetts", "city": "Boston"},
        {"nctId": "NCT1", "state": "Massachusetts", "city": "Worcester"},
        {"nctId": "NCT1", "state": "MA", "city": "Springfield"},
        {"nctId": "NCT2", "state": "New Hampshire", "city": "Nashua"},
    ]))
    studies, ma_ids = read_inputs(InputPaths(tmp_path / "studies.csv", tmp_path / "sites.csv"),
                                  stderr=io.StringIO())
    rows = [_row("NCT1", "CASTHMA", "included"), _row("NCT2", "CASTHMA", "included")]
    client = StubClient({"Asthma": _total(1)})
    (entry,) = rc.check(_rules(ASTHMA), rows, studies, ma_ids, client, TODAY).entries
    assert (entry.found_count, entry.included_count, entry.ratio_found) == (1, 1, Fraction(1))


# --- Ratios and flagged (Req 10.3, 10.4) ------------------------------------

def test_half_up_rounding_and_flag_boundary():
    r = rc.rounded_ratio(7995, 10000)
    assert r == Fraction(800, 1000) and not rc.is_flagged(r)
    r = rc.rounded_ratio(7994, 10000)
    assert r == Fraction(799, 1000) and rc.is_flagged(r)
    assert not rc.is_flagged(rc.rounded_ratio(4, 5))
    assert rc.is_flagged(None)
    assert rc.rounded_ratio(1, 0) is None and rc.rounded_ratio(0, 0) is None


def _entry(found_inc_statuses, ctgov):
    """One CASTHMA entry from rows with the given match_statuses (all active, all MA)."""
    ids = ["NCT%02d" % i for i in range(len(found_inc_statuses))]
    studies = {n: _study(n) for n in ids}
    rows = [_row(n, "CASTHMA", s) for n, s in zip(ids, found_inc_statuses)]
    client = StubClient({"Asthma": _total(ctgov)})
    (entry,) = rc.check(_rules(ASTHMA), rows, studies, frozenset(ids), client, TODAY).entries
    return entry


def test_ratio_exactly_point_eight_not_flagged():
    e = _entry(["included"] * 4, 5)
    assert e.ratio_found == Fraction(800, 1000) and not e.flagged


def test_ctgov_zero_gives_null_ratios_and_flag():
    e = _entry(["included", "excluded"], 0)
    assert (e.ratio_found, e.ratio_included, e.flagged) == (None, None, True)
    obj = json.loads(rc.serialize(rc.RecallResult(TODAY, (e,))))
    assert obj["diseases"][0]["ratio_found"] is None
    assert obj["diseases"][0]["ratio_included"] is None


def test_flag_ignores_ratio_included():
    e = _entry(["included"] + ["excluded"] * 8, 10)
    assert (e.ratio_found, e.ratio_included) == (Fraction(9, 10), Fraction(1, 10))
    assert not e.flagged
    e = _entry(["questionable"] * 7, 10)  # ratio_found 0.7 flagged, ratio_included 0
    assert e.flagged


def test_ratio_above_one_is_kept():
    e = _entry(["included"] * 9, 8)
    assert (e.ratio_found, e.ratio_included) == (Fraction(1125, 1000), Fraction(1125, 1000))
    assert not e.flagged
    assert json.loads(rc.serialize(rc.RecallResult(TODAY, (e,))))["diseases"][0][
        "ratio_found"] == 1.125


# --- Failures (Req 10.7) -----------------------------------------------------

BODY_SECRET = "SECRETBODYTEXT"


@pytest.mark.parametrize("response, kind", [
    (PipelineError("request failed: " + BODY_SECRET), "PipelineError"),
    (HttpStatusError("https://clinicaltrials.gov/x", 404), "HttpStatusError"),
    (("<html>" + BODY_SECRET + "</html>").encode(), "invalid JSON"),
    (b"\xff\xfe" + BODY_SECRET.encode(), "invalid JSON"),
    (json.dumps({"studies": [BODY_SECRET]}).encode(), "missing totalCount"),
    (json.dumps([BODY_SECRET]).encode(), "missing totalCount"),
    (b'{"totalCount": true}', "totalCount not an integer"),
    (b'{"totalCount": "5"}', "totalCount not an integer"),
    (b'{"totalCount": 5.0}', "totalCount not an integer"),
    (b'{"totalCount": -1}', "negative totalCount"),
])
def test_failure_names_measureid_and_url_without_body(response, kind):
    client = StubClient({"Asthma": _total(3), "Diabetes Mellitus": response})
    with pytest.raises(PipelineError) as info:
        rc.check(_rules(ASTHMA, DIABETES), [], {}, frozenset(), client, TODAY)
    msg = str(info.value)
    assert msg == "recall check failed for DIABETES: %s (%s)" % (
        rc.request_url("Diabetes Mellitus"), kind)
    assert BODY_SECRET not in msg
    assert len(client.urls) == 2


def test_failure_stops_before_later_requests():
    client = StubClient({"Asthma": b"oops", "Diabetes Mellitus": _total(1)})
    with pytest.raises(PipelineError, match="CASTHMA"):
        rc.check(_rules(ASTHMA, DIABETES), [], {}, frozenset(), client, TODAY)
    assert client.urls == [rc.request_url("Asthma")]


# --- JSON layout and warnings (Req 10.5, 10.6) -------------------------------

def _two_disease_result():
    studies = {"NCT1": _study("NCT1"), "NCT2": _study("NCT2")}
    rows = [_row("NCT1", "CASTHMA", "included"), _row("NCT2", "CASTHMA", "questionable"),
            _row("NCT1", "DIABETES", "included")]
    client = StubClient({"Asthma": _total(2), "Diabetes Mellitus": _total(0)})
    return rc.check(_rules(ASTHMA, DIABETES), rows, studies, frozenset(studies), client, TODAY)


def test_json_layout_is_byte_exact():
    asthma_url = rc.request_url("Asthma")
    diabetes_url = rc.request_url("Diabetes Mellitus")
    expected = (
        '{\n'
        '  "check_date": "2025-03-04",\n'
        '  "threshold": 0.8,\n'
        '  "diseases": [\n'
        '    {\n'
        '      "measureid": "CASTHMA",\n'
        '      "disease_label": "Current asthma",\n'
        '      "recall_query_term": "Asthma",\n'
        '      "found_count": 2,\n'
        '      "included_count": 1,\n'
        '      "ctgov_count": 2,\n'
        '      "ratio_found": 1.0,\n'
        '      "ratio_included": 0.5,\n'
        '      "flagged": false,\n'
        '      "request_url": "' + asthma_url + '"\n'
        '    },\n'
        '    {\n'
        '      "measureid": "DIABETES",\n'
        '      "disease_label": "Diagnosed diabetes",\n'
        '      "recall_query_term": "Diabetes Mellitus",\n'
        '      "found_count": 1,\n'
        '      "included_count": 1,\n'
        '      "ctgov_count": 0,\n'
        '      "ratio_found": null,\n'
        '      "ratio_included": null,\n'
        '      "flagged": true,\n'
        '      "request_url": "' + diabetes_url + '"\n'
        '    }\n'
        '  ]\n'
        '}\n'
    ).encode("utf-8")
    result = _two_disease_result()
    assert rc.serialize(result) == expected
    assert rc.serialize(_two_disease_result()) == expected  # byte-identical rerun
    assert not expected.startswith(b"\xef\xbb\xbf")


def test_non_ascii_label_written_as_utf8():
    d = _disease("CASTHMA", "Asthme é", "Asthma")
    result = rc.check(_rules(d), [], {}, frozenset(), StubClient({"Asthma": _total(1)}), TODAY)
    assert '"disease_label": "Asthme é"'.encode("utf-8") in rc.serialize(result)


def test_warning_lines():
    studies = {n: _study(n) for n in ("NCT1", "NCT2", "NCT3")}
    rows = [_row("NCT1", "CASTHMA", "included"),
            _row("NCT1", "COPD", "included"), _row("NCT2", "COPD", "excluded"),
            _row("NCT3", "COPD", "excluded"),
            _row("NCT1", "DIABETES", "questionable")]
    client = StubClient({"Asthma": _total(1), "Diabetes Mellitus": _total(0),
                         "Pulmonary Disease, Chronic Obstructive": _total(4)})
    result = rc.check(_rules(ASTHMA, COPD, DIABETES), rows, studies, frozenset(studies),
                      client, TODAY)
    assert rc.warnings(result) == [
        "warning: recall COPD: found_count=3 included_count=1 ctgov_count=4 ratio_found=0.75",
        "warning: recall DIABETES: found_count=1 included_count=0 ctgov_count=0 ratio_found=null",
    ]
    out = io.StringIO()
    rc.emit_warnings(result, out)
    assert out.getvalue() == "".join(line + "\n" for line in rc.warnings(result))


def test_no_warnings_when_nothing_flagged():
    e = _entry(["included"] * 4, 5)
    out = io.StringIO()
    rc.emit_warnings(rc.RecallResult(TODAY, (e,)), out)
    assert out.getvalue() == ""
