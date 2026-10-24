"""Fetch_Log_Writer examples (Req 12.2-12.8, 12.11, 12.12)."""
import json
from datetime import datetime, timezone

from pipeline.data.contact_scrubber import RemovalCounts
from pipeline.io import fetch_log_writer
from pipeline.io.csv_writer import encode_rows
from pipeline.transform.places_transformer import PlacesDuplicate, PlacesRow
from pipeline.transform.study_transformer import MissingGeo, SiteRow, StudyRow

STARTED = datetime(2026, 10, 25, 9, 30, 5, tzinfo=timezone.utc)
FETCHED = datetime(2026, 10, 24, 15, 0, 0, tzinfo=timezone.utc)


def study(nct_id):
    return StudyRow(
        nctId=nct_id, briefTitle="", overallStatus="RECRUITING", studyType="INTERVENTIONAL",
        phases=[], healthyVolunteers="", minimumAge="", maximumAge="", stdAges=[],
        conditions=[], interventionTypes=[], interventionNames=[], meshTerms=[], meshIds=[],
        ancestorTerms=[], ancestorIds=[], lastUpdatePostDate="",
        source_url="https://clinicaltrials.gov/study/" + nct_id)


def site(nct_id, facility):
    return SiteRow(nctId=nct_id, facility=facility, city="", state="MA", zip="", latitude="",
                   longitude="", siteStatus="", location_quality="missing_geo")


def place(name):
    return PlacesRow(locationname=name, locationid="25027", measureid="CASTHMA", measure="",
                     data_value="", low_confidence_limit="", high_confidence_limit="",
                     totalpop18plus="", latitude="", longitude="", year="2023")


def build(**overrides):
    args = dict(
        run_started_at=STARTED, run_mode="network", fetch_date=FETCHED,
        tables={"studies": encode_rows("studies", [study("NCT2"), study("NCT1")]),
                "sites": encode_rows("sites", [site("NCT1", "B"), site("NCT1", "A"),
                                               site("NCT2", "A")]),
                "places": encode_rows("places", [place("Worcester")])},
        pages_by_query={
            "q1": [{"totalCount": 3, "studies": [{}, {}], "nextPageToken": "t"},
                   {"studies": [{}]}],
            "q2": [{"totalCount": 0, "studies": []}],
        },
        q2_server_cutoff=True,
        urls={"clinicaltrials_gov": ["https://clinicaltrials.gov/a", "https://clinicaltrials.gov/b",
                                     "https://clinicaltrials.gov/c"],
              "cdc_places": ["https://data.cdc.gov/p"]},
        contact_removals=RemovalCounts(1, 2, 3, 4),
        missing_geo=[MissingGeo("NCT2", "A", "missing_geo"),
                     MissingGeo("NCT1", "B", "out_of_range"),
                     MissingGeo("NCT1", "A", "missing_geo")],
        places_duplicates=[PlacesDuplicate("25027", "CASTHMA", "2023", 1),
                           PlacesDuplicate("25001", "OBESITY", "", 2)],
        warnings=["warning: one", "warning: two"],
    )
    args.update(overrides)
    return fetch_log_writer.build_fetch_log(**args)


def test_shape_and_key_order():
    """Design § Fetch_Log_Writer key order; Req 12.2-12.6, 12.8, 12.11, 12.12."""
    log = json.loads(fetch_log_writer.serialize(build()))
    assert tuple(log) == fetch_log_writer.TOP_LEVEL_KEYS
    assert log["run_started_at"] == "2026-10-25T09:30:05Z"
    assert log["run_mode"] == "network"
    assert log["fetch_date"] == "2026-10-24T15:00:00Z"
    assert list(log["clinicaltrials_gov"]) == ["q1", "q2", "q2_server_cutoff"]
    assert log["clinicaltrials_gov"]["q1"] == {"total_count": 3, "records_fetched": 3}
    assert log["clinicaltrials_gov"]["q2"] == {"total_count": 0, "records_fetched": 0}
    assert log["clinicaltrials_gov"]["q2_server_cutoff"] is True
    assert log["urls"]["clinicaltrials_gov"][0] == "https://clinicaltrials.gov/a"
    assert log["urls"]["cdc_places"] == ["https://data.cdc.gov/p"]
    assert log["contact_removals"] == {
        "centralContacts": 1, "overallOfficials": 2, "locations[].contacts": 3,
        "responsibleParty investigator name fields": 4,
        "locations[] facility/city pattern matches": 0}
    assert log["missing_geo"]["count"] == 3
    assert [(s["nctId"], s["facility"]) for s in log["missing_geo"]["sites"]] == [
        ("NCT1", "A"), ("NCT1", "B"), ("NCT2", "A")]
    assert log["missing_geo"]["sites"][1]["location_quality"] == "out_of_range"
    assert log["places_duplicates"] == [
        {"locationid": "25001", "measureid": "OBESITY", "kept_year": "", "discarded": 2},
        {"locationid": "25027", "measureid": "CASTHMA", "kept_year": "2023", "discarded": 1}]
    assert log["warnings"] == ["warning: one", "warning: two"]


def test_row_counts_match_written_tables():
    """Req 12.2, 12.7: data rows only, keyed by file name."""
    log = build()
    assert log["files"] == {"studies.csv": 2, "sites.csv": 3, "places_ma.csv": 1}


def test_empty_run_values():
    """Req 12.3, 12.6, 12.12: zero counts and empty lists; offline mode (Req 12.8)."""
    log = build(run_mode="offline", missing_geo=[], places_duplicates=[], warnings=[],
                contact_removals=RemovalCounts(),
                tables={k: encode_rows(k, []) for k in ("studies", "sites", "places")})
    assert log["run_mode"] == "offline"
    assert log["missing_geo"] == {"count": 0, "sites": []}
    assert log["places_duplicates"] == [] and log["warnings"] == []
    assert set(log["contact_removals"].values()) == {0}
    assert log["files"] == {"studies.csv": 0, "sites.csv": 0, "places_ma.csv": 0}


def test_serialize_is_indented_utf8_with_trailing_newline():
    """Design § Fetch_Log_Writer serialization; deterministic bytes (Req 10.5)."""
    data = fetch_log_writer.serialize(build(warnings=["warning: Diabète"]))
    assert data.endswith(b"}\n")
    assert "Diabète".encode("utf-8") in data
    assert data.startswith(b'{\n  "run_started_at"')
    assert data == fetch_log_writer.serialize(build(warnings=["warning: Diabète"]))
