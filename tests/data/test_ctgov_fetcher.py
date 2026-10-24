"""CTGov_Fetcher and fetch check tests (Req 1.1-1.12, 3.1, 3.3, 3.5).

A fake HttpClient serves canned pages per query. Pages are stored in a real
RawStore under tmp_path.
"""
import json
import urllib.parse
from datetime import datetime, timezone

import pytest

from pipeline.__main__ import check_allowed_states, check_total_counts
from pipeline.data import ctgov_fetcher
from pipeline.data.contact_scrubber import RemovalCounts
from pipeline.data.ctgov_fetcher import FIELDS, fetch_ctgov
from pipeline.data.http_client import HttpStatusError
from pipeline.data.raw_store import RawStore
from pipeline.errors import PipelineError

FETCH_DATE = datetime(2026, 10, 24, 15, 0, 0, tzinfo=timezone.utc)
EMAIL = "jane.doe@example.org"
PHONE = "617-555-0100"


class FakeClient:
    """Serves bodies per query. Q2 requests are recognised by the COMPLETED status filter."""

    def __init__(self, q1, q2):
        self.queues = {"q1": iter(q1), "q2": iter(q2)}
        self.urls = []

    def get(self, url):
        self.urls.append(url)
        query = "q2" if "filter.overallStatus=COMPLETED" in url else "q1"
        body = next(self.queues[query])
        if isinstance(body, Exception):
            raise body
        return body if isinstance(body, bytes) else json.dumps(body).encode("utf-8")


def study(nct, state="Massachusetts"):
    return {"protocolSection": {
        "identificationModule": {"nctId": nct},
        "contactsLocationsModule": {"locations": [{"facility": "F", "state": state}]},
    }}


def page(studies, token=None, total=None):
    body = {"studies": studies}
    if token is not None:
        body["nextPageToken"] = token
    if total is not None:
        body["totalCount"] = total
    return body


def params(url):
    return urllib.parse.parse_qsl(urllib.parse.urlsplit(url).query, keep_blank_values=True)


def run_fetch(tmp_path, q1, q2, fetch_date=FETCH_DATE):
    client = FakeClient(q1, q2)
    store = RawStore(tmp_path)
    store.begin_network_run()
    return client, fetch_ctgov(client, store, fetch_date)


def pages_by_query(result):
    return {q.query: q.pages for q in result.queries}


# ---- request parameters and pagination ----------------------------------------

def test_params_identical_across_pages_except_page_token(tmp_path):
    """Req 1.1, 1.2, 1.3, 1.4, 3.1: Q1 then Q2; only pageToken changes; one URL per page."""
    client, result = run_fetch(
        tmp_path,
        [page([study("NCT1")], "a", 3), page([study("NCT2")], "b"), page([study("NCT3")])],
        [page([study("NCT4")], None, 1)],
    )
    q1, q2 = result.queries
    assert [q.query for q in result.queries] == ["q1", "q2"]
    assert client.urls == q1.urls + q2.urls
    assert len(q1.urls) == 3 and len(q2.urls) == 1

    first = params(q1.urls[0])
    assert "pageToken" not in dict(first)
    assert params(q1.urls[1]) == first + [("pageToken", "a")]
    assert params(q1.urls[2]) == first + [("pageToken", "b")]
    assert all(url.startswith("https://clinicaltrials.gov/api/v2/studies?") for url in client.urls)

    d1 = dict(first)
    assert d1["filter.geo"] == "distance(42.3,-71.8,150mi)"
    assert d1["filter.overallStatus"] == "RECRUITING,NOT_YET_RECRUITING,ACTIVE_NOT_RECRUITING"
    assert d1["pageSize"] == "1000" and d1["countTotal"] == "true"
    assert d1["fields"].split(",") == list(FIELDS)
    assert "filter.advanced" not in d1
    assert not any("studyType" in key for key, _ in first)
    segments = {seg for path in FIELDS for seg in path.split(".")}
    for banned in ("centralContacts", "overallOfficials", "contacts", "responsibleParty"):
        assert banned not in segments
    # Req 4.2, 4.4, 4.7: age eligibility fields in order after healthyVolunteers
    fields_list = list(FIELDS)
    hv_idx = fields_list.index("protocolSection.eligibilityModule.healthyVolunteers")
    assert fields_list[hv_idx + 1] == "protocolSection.eligibilityModule.minimumAge"
    assert fields_list[hv_idx + 2] == "protocolSection.eligibilityModule.maximumAge"
    assert fields_list[hv_idx + 3] == "protocolSection.eligibilityModule.stdAges"
    assert dict(params(q2.urls[0]))["filter.overallStatus"] == "COMPLETED"

    assert q1.total_count == 3 and q2.total_count == 1
    assert sorted(p.name for p in tmp_path.iterdir()) == [
        "ctgov_q1_page_001.json", "ctgov_q1_page_002.json", "ctgov_q1_page_003.json",
        "ctgov_q2_page_001.json",
    ]


@pytest.mark.parametrize("fetch_date, bound", [
    (datetime(2026, 10, 24, 15, 0, tzinfo=timezone.utc), "2023-10-23"),
    (datetime(2028, 2, 29, 0, 30, tzinfo=timezone.utc), "2025-02-27"),  # 29 Feb -> 28 Feb, minus 1 day
    (datetime(2026, 1, 1, 0, 0, tzinfo=timezone.utc), "2022-12-31"),
])
def test_q2_url_contains_cutoff_minus_one_day(tmp_path, fetch_date, bound):
    """Q2 glossary, Q2_Lower_Bound: filter.advanced uses the Recent_Completed_Cutoff minus 1 day."""
    _, result = run_fetch(tmp_path, [page([study("NCT1")], None, 1)],
                          [page([study("NCT2")], None, 1)], fetch_date)
    q2_url = result.queries[1].urls[0]
    assert dict(params(q2_url))["filter.advanced"] == "AREA[LastUpdatePostDate]RANGE[%s,MAX]" % bound
    assert "filter.advanced=AREA%5BLastUpdatePostDate%5DRANGE%5B" + bound + ",MAX%5D" in q2_url


def test_q2_without_server_cutoff(tmp_path, monkeypatch):
    """Design § CTGov_Fetcher: Q2_SERVER_CUTOFF=False leaves filter.advanced out of Q2."""
    monkeypatch.setattr(ctgov_fetcher, "Q2_SERVER_CUTOFF", False)
    _, result = run_fetch(tmp_path, [page([study("NCT1")], None, 1)],
                          [page([study("NCT2")], None, 1)])
    for q in result.queries:
        assert "filter.advanced" not in dict(params(q.urls[0]))


def test_repeated_token_within_query_stops(tmp_path):
    """Req 1.5: a token already used in the same query stops the run, naming the token."""
    with pytest.raises(PipelineError) as excinfo:
        run_fetch(tmp_path, [page([study("NCT1")], "tok"), page([study("NCT2")], "tok")], [])
    message = str(excinfo.value)
    assert "tok" in message and "Q1" in message and "page 2" in message


def test_same_token_in_q1_and_q2_is_allowed(tmp_path):
    """Req 1.5 (as amended): tokens are tracked per query."""
    _, result = run_fetch(
        tmp_path,
        [page([study("NCT1")], "tok", 2), page([study("NCT2")])],
        [page([study("NCT3")], "tok", 2), page([study("NCT4")])],
    )
    assert [len(q.pages) for q in result.queries] == [2, 2]
    check_total_counts(pages_by_query(result))


def test_exact_multiple_of_page_size_ends_with_empty_page(tmp_path):
    """Probe V7, Req 1.3, 1.6: a full last page carries a token; the next page is studies: [] with no token."""
    full = [study("NCT%05d" % i) for i in range(1000)]
    _, result = run_fetch(tmp_path, [page(full, "t1", 1000), page([])],
                          [page([study("NCTX")], None, 1)])
    q1 = result.queries[0]
    assert len(q1.pages) == 2 and q1.pages[1]["studies"] == []
    assert (tmp_path / "ctgov_q1_page_002.json").exists()
    check_total_counts(pages_by_query(result))


def test_page_limit_of_100_per_query(tmp_path):
    """Req 1.7: page 100 of a query with a nextPageToken stops the run."""
    pages = (page([], "t%d" % n, 0 if n == 1 else None) for n in range(1, 200))
    client = FakeClient(pages, [])
    store = RawStore(tmp_path)
    store.begin_network_run()
    with pytest.raises(PipelineError) as excinfo:
        fetch_ctgov(client, store, FETCH_DATE)
    assert "page limit of 100" in str(excinfo.value)
    assert len(client.urls) == 100


def test_exactly_100_pages_ending_without_token_is_fine(tmp_path):
    """Req 1.7: the limit applies only when page 100 still has a token."""
    q1 = [page([], "t%d" % n, 0 if n == 1 else None) for n in range(1, 100)] + [page([])]
    _, result = run_fetch(tmp_path, q1, [page([], None, 0)])
    assert len(result.queries[0].pages) == 100


# ---- invalid responses ----------------------------------------------------------

def test_non_json_body_stops_without_body_content(tmp_path):
    """Req 1.6, 3.3, 3.5: invalid JSON names the URL and page number, stores nothing, leaks no body."""
    bad = ("<html>contact %s %s</html>" % (EMAIL, PHONE)).encode()
    with pytest.raises(PipelineError) as excinfo:
        run_fetch(tmp_path, [page([study("NCT1")], "a", 2), bad], [])
    message = str(excinfo.value)
    assert "page 2" in message and "pageToken=a" in message
    assert EMAIL not in message and PHONE not in message and "html" not in message
    assert not (tmp_path / "ctgov_q1_page_002.json").exists()


def test_missing_studies_key_stops(tmp_path):
    """Req 1.6: a 2xx body without a studies array stops the run with the URL and page number."""
    with pytest.raises(PipelineError) as excinfo:
        run_fetch(tmp_path, [page([study("NCT1")], None, 1)], [{"totalCount": 1, "note": EMAIL}])
    message = str(excinfo.value)
    assert "Q2 page 1" in message and "filter.overallStatus=COMPLETED" in message
    assert EMAIL not in message
    assert not (tmp_path / "ctgov_q2_page_001.json").exists()


@pytest.mark.parametrize("query, hint", [
    ("q1", "check parameter filter.geo"),
    ("q2", "check parameter filter.geo or filter.advanced"),
])
def test_http_400_names_filter_parameters(tmp_path, query, hint):
    """Req 1.11: HTTP 400 gives the URL, status 400 and the parameter names."""
    error = HttpStatusError("https://clinicaltrials.gov/api/v2/studies?x", 400)
    q1 = [error] if query == "q1" else [page([study("NCT1")], None, 1)]
    q2 = [error] if query == "q2" else []
    with pytest.raises(PipelineError) as excinfo:
        run_fetch(tmp_path, q1, q2)
    message = str(excinfo.value)
    assert "HTTP 400" in message and hint in message
    assert "https://clinicaltrials.gov/api/v2/studies?filter.geo=" in message


def test_other_4xx_is_passed_through(tmp_path):
    """Req 9.4: statuses other than 400 keep the HTTP_Client error."""
    error = HttpStatusError("https://clinicaltrials.gov/api/v2/studies?x", 404)
    with pytest.raises(HttpStatusError) as excinfo:
        run_fetch(tmp_path, [error], [])
    assert excinfo.value.status == 404


def test_pages_are_scrubbed_before_raw_write(tmp_path):
    """Req 3.2, 3.4, 10.6: contact structures never reach the Raw_Store; counts are summed over queries."""
    s = study("NCT1")
    s["protocolSection"]["contactsLocationsModule"]["centralContacts"] = [{"email": EMAIL}]
    s["protocolSection"]["contactsLocationsModule"]["locations"][0]["contacts"] = [{"phone": PHONE}]
    _, result = run_fetch(tmp_path, [page([s], None, 1)], [page([s], None, 1)])
    for name in ("ctgov_q1_page_001.json", "ctgov_q2_page_001.json"):
        text = (tmp_path / name).read_text(encoding="utf-8")
        assert EMAIL not in text and PHONE not in text
        assert '"contacts"' not in text and '"centralContacts"' not in text
    assert result.removal_counts == RemovalCounts(centralContacts=2, locations_contacts=2)


# ---- fetch checks in __main__ ---------------------------------------------------

@pytest.mark.parametrize("query", ["q1", "q2"])
def test_total_count_mismatch_names_query(tmp_path, query):
    """Req 1.10: a fetched count that differs from totalCount stops, naming the query and both numbers."""
    q1 = [page([study("NCT1"), study("NCT2")], None, 5 if query == "q1" else 2)]
    q2 = [page([study("NCT3")], None, 7 if query == "q2" else 1)]
    _, result = run_fetch(tmp_path, q1, q2)
    with pytest.raises(PipelineError) as excinfo:
        check_total_counts(pages_by_query(result))
    message = str(excinfo.value)
    expected = "Q1: fetched 2 records but totalCount is 5" if query == "q1" \
        else "Q2: fetched 1 records but totalCount is 7"
    assert expected in message


@pytest.mark.parametrize("bad_total", [None, "3", True, 3.0])
def test_missing_or_non_integer_total_count(tmp_path, bad_total):
    """Req 1.10: page 1 without an integer totalCount stops the run."""
    q2_page = page([study("NCT3")])
    if bad_total is not None:
        q2_page["totalCount"] = bad_total
    _, result = run_fetch(tmp_path, [page([study("NCT1")], None, 1)], [q2_page])
    assert result.queries[1].total_count is None
    with pytest.raises(PipelineError) as excinfo:
        check_total_counts(pages_by_query(result))
    assert "Q2: page 1 has no integer totalCount" in str(excinfo.value)


def test_duplicates_count_as_received(tmp_path):
    """Design § Fetch checks: duplicate nctIds count once per record received."""
    _, result = run_fetch(tmp_path, [page([study("NCT1"), study("NCT1")], None, 2)],
                          [page([study("NCT1")], None, 1)])
    check_total_counts(pages_by_query(result))


def test_no_allowed_states_site_stops(tmp_path):
    """Req 1.12: no site in Allowed_States stops the run and names filter.geo."""
    _, result = run_fetch(tmp_path, [page([study("NCT1", "Beijing")], None, 1)],
                          [page([study("NCT2", None), {"protocolSection": {}}], None, 2)])
    with pytest.raises(PipelineError) as excinfo:
        check_allowed_states(pages_by_query(result))
    message = str(excinfo.value)
    assert "no study has a site in Allowed_States" in message and "filter.geo" in message


@pytest.mark.parametrize("state", ["Massachusetts", "  vermont ", "NY", "ri"])
def test_allowed_states_site_passes(state):
    """Req 1.12 with the Req 5.3 comparison: stripped, case-insensitive name or abbreviation."""
    check_allowed_states({"q1": [page([study("NCT1", "Ontario")])],
                          "q2": [page([study("NCT2", state)])]})
