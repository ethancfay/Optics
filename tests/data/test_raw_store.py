"""Raw_Store tests (Req 10.1, 10.4, 10.6-10.9)."""
import json
import os
from datetime import datetime, timezone

import pytest

from pipeline.data import raw_store as raw_store_module
from pipeline.data.contact_scrubber import RemovalCounts
from pipeline.data.raw_store import RawStore
from pipeline.errors import PipelineError

FETCH_DATE = datetime(2026, 10, 24, 15, 0, 0, tzinfo=timezone.utc)
Q1 = "https://clinicaltrials.gov/api/v2/studies?q=1"
Q2 = "https://clinicaltrials.gov/api/v2/studies?q=2"
PL = "https://data.cdc.gov/resource/swc5-untb.json?$offset=0"


def complete_run(store: RawStore) -> None:
    store.begin_network_run()
    store.write_page("ctgov_q1", 1, {"studies": [{"a": 1}], "nextPageToken": "t1", "totalCount": 2})
    store.write_page("ctgov_q1", 2, {"studies": [{"a": 2}]})
    store.write_page("ctgov_q2", 1, {"studies": [], "totalCount": 0})
    store.write_page("places", 1, [{"locationname": "Worcester"}])
    store.finish_network_run(
        FETCH_DATE, True,
        {"clinicaltrials_gov": [Q1, Q1 + "&pageToken=t1", Q2], "cdc_places": [PL]},
        RemovalCounts(1, 2, 3, 4),
    )


def test_file_names_and_manifest(tmp_path):
    """Req 10.1, 10.7: one file per page named by source and page; manifest holds date, URLs, counts."""
    store = RawStore(tmp_path)
    complete_run(store)
    names = sorted(p.name for p in tmp_path.iterdir())
    assert names == ["ctgov_q1_page_001.json", "ctgov_q1_page_002.json",
                     "ctgov_q2_page_001.json", "manifest.json", "places_page_001.json"]
    manifest = json.loads((tmp_path / "manifest.json").read_text())
    assert manifest == {
        "fetch_date": "2026-10-24T15:00:00Z",
        "q2_server_cutoff": True,
        "urls": {"clinicaltrials_gov": [Q1, Q1 + "&pageToken=t1", Q2], "cdc_places": [PL]},
        "pages": {"ctgov_q1": 2, "ctgov_q2": 1, "cdc_places": 1},
        "contact_removals": {"centralContacts": 1, "overallOfficials": 2,
                             "locations[].contacts": 3,
                             "responsibleParty investigator name fields": 4},
    }


def test_load_round_trip(tmp_path):
    complete_run(RawStore(tmp_path))
    cache = RawStore(tmp_path).load()
    assert cache.fetch_date == FETCH_DATE
    assert cache.q2_server_cutoff is True
    assert [p["studies"] for p in cache.ctgov_q1_pages] == [[{"a": 1}], [{"a": 2}]]
    assert cache.ctgov_q1_pages[0]["totalCount"] == 2
    assert cache.ctgov_q2_pages == [{"studies": [], "totalCount": 0}]
    assert cache.places_pages == [[{"locationname": "Worcester"}]]
    assert cache.urls["clinicaltrials_gov"][-1] == Q2
    assert cache.contact_removals == RemovalCounts(1, 2, 3, 4)


def test_begin_network_run_deletes_manifest_first_then_old_pages(tmp_path, monkeypatch):
    """Req 10.8: manifest goes first so an interrupted clear still leaves the store incomplete."""
    complete_run(RawStore(tmp_path))
    (tmp_path / "unrelated.txt").write_text("keep")
    deleted = []
    real_unlink = os.unlink

    def recording_unlink(path, *args, **kwargs):
        deleted.append(os.path.basename(path))
        return real_unlink(path, *args, **kwargs)

    monkeypatch.setattr(os, "unlink", recording_unlink)
    RawStore(tmp_path).begin_network_run()
    assert deleted[0] == "manifest.json"
    assert sorted(p.name for p in tmp_path.iterdir()) == ["unrelated.txt"]


@pytest.mark.parametrize("remove, expected, not_expected", [
    ("manifest.json", ["ClinicalTrials.gov", "PLACES"], []),
    ("ctgov_q2_page_001.json", ["ClinicalTrials.gov"], ["PLACES"]),
    ("places_page_001.json", ["PLACES"], ["ClinicalTrials.gov"]),
])
def test_load_names_incomplete_source(tmp_path, remove, expected, not_expected):
    """Req 10.4: the error names each source whose raw files are missing or incomplete."""
    complete_run(RawStore(tmp_path))
    (tmp_path / remove).unlink()
    with pytest.raises(PipelineError) as info:
        RawStore(tmp_path).load()
    message = str(info.value).split("(")[0]  # source list precedes the details
    for label in expected:
        assert label in message
    for label in not_expected:
        assert label not in message


def test_load_both_sources_missing_pages(tmp_path):
    complete_run(RawStore(tmp_path))
    (tmp_path / "ctgov_q1_page_002.json").unlink()
    (tmp_path / "places_page_001.json").unlink()
    with pytest.raises(PipelineError, match="for ClinicalTrials.gov and PLACES"):
        RawStore(tmp_path).load()


def test_load_empty_store_names_both(tmp_path):
    with pytest.raises(PipelineError, match="for ClinicalTrials.gov and PLACES"):
        RawStore(tmp_path / "raw").load()


def test_load_rejects_last_page_with_token_and_full_places_page(tmp_path):
    """Req 10.4: complete means no nextPageToken on the last CTGov page and a short last PLACES page."""
    complete_run(RawStore(tmp_path))
    (tmp_path / "ctgov_q2_page_001.json").write_text('{"studies":[],"nextPageToken":"x"}')
    (tmp_path / "places_page_001.json").write_text(json.dumps([{}] * 1000))
    with pytest.raises(PipelineError) as info:
        RawStore(tmp_path).load()
    assert "ClinicalTrials.gov and PLACES" in str(info.value)
    assert "nextPageToken" in str(info.value)


def test_write_failure_names_file_and_leaves_store_incomplete(tmp_path, monkeypatch):
    """Req 10.9: a raw write failure names the file; a later offline load still fails."""
    complete_run(RawStore(tmp_path))
    store = RawStore(tmp_path)
    store.begin_network_run()
    store.write_page("ctgov_q1", 1, {"studies": []})

    def failing_replace(src, dst):
        raise OSError("disk full")

    monkeypatch.setattr(raw_store_module.os, "replace", failing_replace)
    with pytest.raises(PipelineError) as info:
        store.write_page("ctgov_q1", 2, {"studies": []})
    assert "ctgov_q1_page_002.json" in str(info.value)
    monkeypatch.undo()
    assert not list(tmp_path.glob(".*.tmp"))
    with pytest.raises(PipelineError, match="no complete prior fetch"):
        RawStore(tmp_path).load()


def test_pages_must_be_written_in_order(tmp_path):
    store = RawStore(tmp_path)
    store.begin_network_run()
    with pytest.raises(PipelineError, match="out of order"):
        store.write_page("places", 2, [])


def test_written_bytes_are_canonical_json(tmp_path):
    """Design § Raw_Store: sorted keys, compact separators, UTF-8 without escapes."""
    store = RawStore(tmp_path)
    store.begin_network_run()
    store.write_page("ctgov_q1", 1, {"studies": [{"b": "é", "a": 1.5}]})
    data = (tmp_path / "ctgov_q1_page_001.json").read_bytes()
    assert data == '{"studies":[{"a":1.5,"b":"é"}]}'.encode("utf-8")
