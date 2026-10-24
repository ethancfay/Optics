"""PLACES_Fetcher tests (Req 2.1-2.9, 3.3, 10.1).

A fake HttpClient serves canned pages in order. Pages are stored in a real
RawStore under tmp_path.
"""
import json
import urllib.parse

import pytest

from pipeline.data.places_fetcher import PAGE_SIZE, SELECT_FIELDS, fetch_places
from pipeline.data.raw_store import RawStore
from pipeline.errors import PipelineError

EMAIL = "jane.doe@example.org"


class FakeClient:
    """Serves bodies in order and records every URL; checks the previous page was stored."""

    def __init__(self, bodies, store_root=None):
        self.bodies = iter(bodies)
        self.urls = []
        self.store_root = store_root

    def get(self, url):
        if self.store_root is not None:
            # Req 10.1: the previous page is on disk before the next request.
            stored = sorted(p.name for p in self.store_root.glob("places_page_*.json"))
            assert len(stored) == len(self.urls)
        self.urls.append(url)
        body = next(self.bodies)
        return body if isinstance(body, bytes) else json.dumps(body).encode("utf-8")


def records(n, start=0):
    return [{"locationname": "County%04d" % (start + i), "locationid": "25001",
             "measureid": "M", "stateabbr": "MA", "datavaluetypeid": "CrdPrv"}
            for i in range(n)]


def params(url):
    return urllib.parse.parse_qsl(urllib.parse.urlsplit(url).query, keep_blank_values=True)


def run_fetch(tmp_path, bodies):
    store = RawStore(tmp_path)
    store.begin_network_run()
    client = FakeClient(bodies, tmp_path)
    return client, fetch_places(client, store)


def stored_pages(tmp_path):
    return sorted(p.name for p in tmp_path.glob("places_page_*.json"))


@pytest.mark.parametrize("sizes", [[560], [1000, 3], [1000, 1000, 999]])
def test_one_two_and_three_pages(tmp_path, sizes):
    """Req 2.1-2.6, 10.1: same filters, fields and order on every page; offset steps by 1,000."""
    bodies = [records(n, 1000 * i) for i, n in enumerate(sizes)]
    client, result = run_fetch(tmp_path, bodies)

    assert result.urls == client.urls and len(result.urls) == len(sizes)
    assert result.pages == bodies
    assert result.records == [r for b in bodies for r in b]
    assert stored_pages(tmp_path) == ["places_page_%03d.json" % (i + 1) for i in range(len(sizes))]

    first = params(result.urls[0])
    d = dict(first)
    assert result.urls[0].startswith("https://data.cdc.gov/resource/swc5-untb.json?")
    assert d["$select"].split(",") == list(SELECT_FIELDS)
    assert set(SELECT_FIELDS) == {
        "locationname", "locationid", "measureid", "measure", "data_value",
        "low_confidence_limit", "high_confidence_limit", "totalpop18plus",
        "geolocation", "year", "stateabbr", "datavaluetypeid"}
    assert d["$where"] == "stateabbr='MA' AND datavaluetypeid='CrdPrv'"
    assert d["$order"] == "locationname,measureid,:id"  # probe V9
    assert d["$limit"] == "1000"
    for i, url in enumerate(result.urls):
        p = params(url)
        assert p[:-1] == first[:-1]
        assert p[-1] == ("$offset", str(1000 * i))


def test_empty_page_after_full_page_stops(tmp_path):
    """Req 2.5: 0 records on a page after the first ends paging without error."""
    _, result = run_fetch(tmp_path, [records(PAGE_SIZE), []])
    assert len(result.urls) == 2 and len(result.records) == PAGE_SIZE
    assert stored_pages(tmp_path) == ["places_page_001.json", "places_page_002.json"]


def test_empty_first_page_stops_run(tmp_path):
    """Req 2.7: an empty first page stops the run with the URL; nothing is stored."""
    with pytest.raises(PipelineError) as excinfo:
        run_fetch(tmp_path, [[]])
    message = str(excinfo.value)
    assert "no PLACES records were returned" in message
    assert "https://data.cdc.gov/resource/swc5-untb.json?" in message
    assert stored_pages(tmp_path) == []


@pytest.mark.parametrize("body", [
    {"error": True, "message": EMAIL},
    [{"ok": 1}, "contact %s" % EMAIL],
    ("<html>%s</html>" % EMAIL).encode(),
])
def test_invalid_body_stops_without_body_content(tmp_path, body):
    """Req 2.8, 3.3: a body that is not a list of records stops with the URL; no body text leaks."""
    with pytest.raises(PipelineError) as excinfo:
        run_fetch(tmp_path, [records(PAGE_SIZE), body])
    message = str(excinfo.value)
    assert "response format was invalid" in message and "page 2" in message
    assert "%24offset=1000" in message or "$offset=1000" in message
    assert EMAIL not in message and "html" not in message
    assert stored_pages(tmp_path) == ["places_page_001.json"]


def test_page_limit_of_100(tmp_path):
    """Req 2.9: page 100 with 1,000 records stops the run, stating the 100-page limit."""
    full = records(PAGE_SIZE)
    client = FakeClient(full for _ in range(200))
    store = RawStore(tmp_path)
    store.begin_network_run()
    with pytest.raises(PipelineError) as excinfo:
        fetch_places(client, store)
    assert "100-page limit" in str(excinfo.value)
    assert len(client.urls) == 100


def test_exactly_100_pages_ending_short_is_fine(tmp_path):
    """Req 2.9: the limit applies only when page 100 is still full."""
    bodies = [records(PAGE_SIZE)] * 99 + [records(5)]
    _, result = run_fetch(tmp_path, bodies)
    assert len(result.pages) == 100
