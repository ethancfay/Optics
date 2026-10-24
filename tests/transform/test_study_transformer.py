"""Study_Transformer tests (Req 4.1-4.9, 5.1-5.11, 13.2, 13.3, 13.12).

Properties P3, P4, P8 (design § Correctness Properties) plus examples.
"""
from datetime import datetime, timezone

from hypothesis import given

from pipeline.transform.study_transformer import build_study_and_site_rows
from tests.strategies import ctgov_query_pages

FETCH_DATE = datetime(2026, 10, 24, 15, 0, 0, tzinfo=timezone.utc)  # cutoff 2023-10-24


def study(nct_id="NCT00000001", status="RECRUITING", date="2026-01-01",
          locations=None, **modules):
    """A scrubbed record. `modules` override or add protocolSection modules."""
    if locations is None:
        locations = [{"facility": "Site", "city": "Boston", "state": "Massachusetts",
                      "zip": "02115", "status": "RECRUITING",
                      "geoPoint": {"lat": 42.3, "lon": -71.1}}]
    ps = {
        "identificationModule": {"nctId": nct_id, "briefTitle": "Title " + nct_id},
        "statusModule": {"overallStatus": status,
                         "lastUpdatePostDateStruct": {"date": date}},
        "contactsLocationsModule": {"locations": locations},
    }
    derived = modules.pop("derivedSection", None)
    ps.update(modules)
    record = {"protocolSection": ps}
    if derived is not None:
        record["derivedSection"] = derived
    return record


def run(*records, q2=()):
    pages = [{"studies": list(records)}]
    if q2:
        pages.append({"studies": list(q2)})
    return build_study_and_site_rows(pages, FETCH_DATE)


def loc(state="Massachusetts", geo=None, **fields):
    out = {"facility": "Site", "city": "Boston", "state": state, "zip": "02115"}
    out.update(fields)
    if geo is not None:
        out["geoPoint"] = geo
    return out


# --- Properties -----------------------------------------------------------------

@given(ctgov_query_pages())
def test_p3_every_site_nctid_is_a_study_row(pages):
    """P3. **Validates: Requirements 5.5, 13.2**"""
    studies, sites, _, _ = build_study_and_site_rows(pages, FETCH_DATE)
    study_ids = [s.nctId for s in studies]
    for site in sites:
        assert study_ids.count(site.nctId) == 1


@given(ctgov_query_pages())
def test_p4_non_empty_coordinates_are_in_range(pages):
    """P4. **Validates: Requirements 5.6, 13.3**"""
    _, sites, _, _ = build_study_and_site_rows(pages, FETCH_DATE)
    for site in sites:
        if site.latitude != "":
            assert -90.0 <= float(site.latitude) <= 90.0
        if site.longitude != "":
            assert -180.0 <= float(site.longitude) <= 180.0


@given(ctgov_query_pages())
def test_p8_nctid_unique_in_study_rows(pages):
    """P8. **Validates: Requirements 4.6, 13.12**"""
    studies, _, _, _ = build_study_and_site_rows(pages, FETCH_DATE)
    ids = [s.nctId for s in studies]
    assert len(ids) == len(set(ids))


# --- Status filter and Recent_Completed_Cutoff (Req 4.1) -------------------------

def test_completed_cutoff_boundary():
    studies, _, _, _ = run(
        study("NCT1", "COMPLETED", "2023-10-24"),  # on the cutoff: kept
        study("NCT2", "COMPLETED", "2023-10-23"),  # one day before: dropped
        study("NCT3", "COMPLETED", "2023-02-30"),  # invalid date: dropped
        study("NCT4", "COMPLETED", "23-10-24"),    # wrong format: dropped
        study("NCT5", "COMPLETED", None),          # missing: dropped
    )
    assert [s.nctId for s in studies] == ["NCT1"]


def test_cutoff_on_29_february_maps_to_28_february():
    leap = datetime(2028, 2, 29, 12, tzinfo=timezone.utc)  # cutoff 2025-02-28
    pages = [{"studies": [study("NCT1", "COMPLETED", "2025-02-28"),
                          study("NCT2", "COMPLETED", "2025-02-27")]}]
    studies, _, _, _ = build_study_and_site_rows(pages, leap)
    assert [s.nctId for s in studies] == ["NCT1"]


def test_active_statuses_kept_regardless_of_date_and_others_dropped():
    studies, _, _, _ = run(
        study("NCT1", "RECRUITING", "2001-01-01"),
        study("NCT2", "NOT_YET_RECRUITING", None),
        study("NCT3", "ACTIVE_NOT_RECRUITING", "bad"),
        study("NCT4", "recruiting"),  # case-sensitive (Req 4.1)
        study("NCT5", "TERMINATED"),
    )
    assert [s.nctId for s in studies] == ["NCT1", "NCT2", "NCT3"]


def test_every_study_type_kept_including_empty_and_absent():
    studies, _, _, _ = run(
        study("NCT1", designModule={"studyType": "INTERVENTIONAL"}),
        study("NCT2", designModule={"studyType": "OBSERVATIONAL"}),
        study("NCT3", designModule={"studyType": "EXPANDED_ACCESS"}),
        study("NCT4", designModule={"studyType": ""}),
        study("NCT5"),
    )
    assert [s.studyType for s in studies] == [
        "INTERVENTIONAL", "OBSERVATIONAL", "EXPANDED_ACCESS", "", ""]


# --- Deduplication and nctId (Req 4.3, 4.5, 4.9) ---------------------------------

def test_study_in_q1_and_q2_keeps_the_q1_copy_and_its_sites():
    q1 = study("NCT1", "ACTIVE_NOT_RECRUITING", locations=[loc(facility="Q1 site")])
    q2 = study("NCT1", "COMPLETED", "2026-01-01", locations=[loc(facility="Q2 site")])
    studies, sites, _, _ = run(q1, q2=[q2])
    assert [(s.nctId, s.overallStatus) for s in studies] == [("NCT1", "ACTIVE_NOT_RECRUITING")]
    assert [s.facility for s in sites] == ["Q1 site"]


def test_dedup_runs_before_status_filter():
    # The first copy is dropped by the status filter; the later copy is not used.
    studies, sites, _, _ = run(study("NCT1", "TERMINATED"), study("NCT1", "RECRUITING"))
    assert studies == [] and sites == []


def test_missing_or_empty_nctid_excluded():
    no_id = study("x")
    del no_id["protocolSection"]["identificationModule"]["nctId"]
    studies, sites, _, _ = run(no_id, study(""), study("NCT1"))
    assert [s.nctId for s in studies] == ["NCT1"]
    assert {s.nctId for s in sites} == {"NCT1"}


def test_study_without_allowed_state_site_dropped():
    studies, sites, _, _ = run(
        study("NCT1", locations=[loc("California"), loc(None), loc("")]),
        study("NCT2", locations=[]),
    )
    assert studies == [] and sites == []


# --- Study_Row fields (Req 4.2, 4.4, 4.7, 4.8) -----------------------------------

def test_study_row_fields_copied_and_source_url():
    record = study(
        "NCT9",
        designModule={"studyType": "INTERVENTIONAL", "phases": ["PHASE2", "PHASE3"]},
        eligibilityModule={"healthyVolunteers": False, "minimumAge": "18 Years",
                           "maximumAge": "6 Months", "stdAges": ["CHILD", "ADULT", "OLDER_ADULT"]},
        conditionsModule={"conditions": ["Asthma", "COPD"]},
        armsInterventionsModule={"interventions": [
            {"type": "DRUG", "name": "Drug A"}, {"name": "No type"}, {"type": "DEVICE"}]},
        derivedSection={"conditionBrowseModule": {
            "meshes": [{"id": "D001249", "term": "Asthma"}, {"term": "No id"}],
            "ancestors": [{"id": "D012140", "term": "Respiratory Tract Diseases"}]}},
    )
    (row,), _, _, _ = run(record)
    assert row.briefTitle == "Title NCT9"
    assert row.phases == ["PHASE2", "PHASE3"]
    assert row.healthyVolunteers == "false"
    assert (row.minimumAge, row.maximumAge) == ("18 Years", "6 Months")
    assert row.stdAges == ["CHILD", "ADULT", "OLDER_ADULT"]
    assert row.conditions == ["Asthma", "COPD"]
    assert row.interventionTypes == ["DRUG", "", "DEVICE"]
    assert row.interventionNames == ["Drug A", "No type", ""]
    assert row.meshTerms == ["Asthma", "No id"] and row.meshIds == ["D001249", ""]
    assert row.ancestorTerms == ["Respiratory Tract Diseases"] and row.ancestorIds == ["D012140"]
    assert row.lastUpdatePostDate == "2026-01-01"
    assert row.source_url == "https://clinicaltrials.gov/study/NCT9"


def test_healthy_volunteers_true_false_or_empty():
    studies, _, _, _ = run(
        study("NCT1", eligibilityModule={"healthyVolunteers": True}),
        study("NCT2", eligibilityModule={"healthyVolunteers": False}),
        study("NCT3", eligibilityModule={}),
    )
    assert [s.healthyVolunteers for s in studies] == ["true", "false", ""]


def test_missing_fields_become_empty_values():
    record = study("NCT1", eligibilityModule={"minimumAge": "", "stdAges": []})
    record["protocolSection"]["identificationModule"].pop("briefTitle")
    record["protocolSection"]["statusModule"].pop("lastUpdatePostDateStruct")
    (row,), _, _, _ = run(record)
    assert row.briefTitle == "" and row.lastUpdatePostDate == ""
    assert row.minimumAge == "" and row.maximumAge == ""
    assert row.stdAges == [] and row.phases == [] and row.conditions == []
    assert row.interventionTypes == [] and row.interventionNames == []
    assert row.meshTerms == [] and row.meshIds == []
    assert row.ancestorTerms == [] and row.ancestorIds == []


# --- Site rows (Req 5) ------------------------------------------------------------

def test_every_site_status_kept_and_stripped():
    locations = [loc(facility=str(i), status=s)
                 for i, s in enumerate(["RECRUITING", " COMPLETED ", "WITHDRAWN", ""])]
    locations.append(loc(facility="none"))  # no status key
    _, sites, _, _ = run(study("NCT1", locations=locations))
    assert [s.siteStatus for s in sites] == ["RECRUITING", "COMPLETED", "WITHDRAWN", "", ""]


def test_state_match_strips_and_ignores_case():
    states = ["Massachusetts", " ma ", "RHODE ISLAND", "nh", "Connecticut", "NY", "vermont",
              "Maine", "Ontario"]
    _, sites, _, _ = run(study("NCT1", locations=[loc(s, facility=s) for s in states]))
    assert [s.state for s in sites] == [
        "Massachusetts", "ma", "RHODE ISLAND", "nh", "Connecticut", "NY", "vermont"]


def test_site_text_stripped_and_missing_values_empty():
    _, (site,), _, _ = run(study("NCT1", locations=[
        {"facility": "  Mass General  ", "state": " Massachusetts "}]))
    assert (site.facility, site.city, site.state, site.zip) == (
        "Mass General", "", "Massachusetts", "")


def test_location_quality_ok_missing_geo_out_of_range():
    geos = {
        "ok": {"lat": 42.3, "lon": -71.1},
        "boundary": {"lat": -90, "lon": 180},
        "absent": None,
        "no_lon": {"lat": 42.3},
        "string": {"lat": "42.3", "lon": "-71.1"},
        "bool": {"lat": True, "lon": -71.1},
        "nan": {"lat": float("nan"), "lon": -71.1},
        "lat_out": {"lat": 90.5, "lon": -71.1},
        "lon_out": {"lat": 42.3, "lon": -180.1},
    }
    _, sites, missing, _ = run(study("NCT1", locations=[loc(geo=g, facility=k)
                                                      for k, g in geos.items()]))
    got = {s.facility: (s.latitude, s.longitude, s.location_quality) for s in sites}
    assert got == {
        "ok": ("42.3", "-71.1", "ok"),
        "boundary": ("-90.0", "180.0", "ok"),
        "absent": ("", "", "missing_geo"),
        "no_lon": ("", "", "missing_geo"),
        "string": ("", "", "missing_geo"),
        "bool": ("", "", "missing_geo"),
        "nan": ("", "", "missing_geo"),
        "lat_out": ("", "", "out_of_range"),
        "lon_out": ("", "", "out_of_range"),
    }
    assert [(m.nctId, m.facility, m.location_quality) for m in missing] == [
        ("NCT1", k, q) for k, (_, _, q) in got.items() if q != "ok"]


def test_duplicate_sites_collapse_and_missing_geo_listed_once():
    dup = loc(facility=" Site ", geo=None)
    same = loc(facility="Site", geo=None)        # equal after stripping
    other_zip = loc(facility="Site", zip="01605")
    outside = loc("California", facility="Far", geo=None)  # not retained, not logged
    _, sites, missing, _ = run(study("NCT1", locations=[dup, same, other_zip, outside]))
    assert [(s.facility, s.zip) for s in sites] == [("Site", "02115"), ("Site", "01605")]
    assert [(m.facility, m.location_quality) for m in missing] == [
        ("Site", "missing_geo"), ("Site", "missing_geo")]



def test_zip_used_in_deduplication_before_validation():
    """Req 5.10: deduplication uses the stripped source zip; validation happens after."""
    def loc(z): return {"city": "Boston", "state": "MA", "facility": "A", "zip": z, "geoPoint": {"lat": 42, "lon": -71}}
    
    # Two sites with same invalid zip: deduplicated to one, then blanked
    dup = page(nct("NCT10", locations=[loc("0211512345"), loc("0211512345")]))
    _, sites, _, count = build_study_and_site_rows([dup], FETCH_DATE)
    assert len(sites) == 1
    assert sites[0].zip == ""
    assert count == 1  # counted once, not twice


def test_zip_validation():
    r"""Req 5.1: zip must match ^\d{5}(-?\d{4})?$, else blanked and counted."""
    def build(z):
        return study(locations=[loc(zip=z)])
    
    # Valid zips
    _, sites, _, count = run(build("02115"))
    assert len(sites) == 1
    assert sites[0].zip == "02115"
    assert count == 0
    
    _, sites, _, count = run(build("021151234"))
    assert sites[0].zip == "021151234"
    assert count == 0
    
    _, sites, _, count = run(build("02115-1234"))
    assert sites[0].zip == "02115-1234"
    assert count == 0
    
    # Whitespace stripped before validation
    _, sites, _, count = run(build("  02115  "))
    assert sites[0].zip == "02115"
    assert count == 0
    
    # Invalid: 10 digits (the trigger for this requirement)
    _, sites, _, count = run(build("0211512345"))
    assert sites[0].zip == ""
    assert count == 1
    
    # Invalid: letters
    _, sites, _, count = run(build("ABC12"))
    assert sites[0].zip == ""
    assert count == 1
    
    # Invalid: 4 digits
    _, sites, _, count = run(build("1234"))
    assert sites[0].zip == ""
    assert count == 1
    
    # Empty zip is kept empty, not counted
    _, sites, _, count = run(build(""))
    assert sites[0].zip == ""
    assert count == 0
    
    # Multiple sites: some valid, some invalid
    multi = study(locations=[
        loc(zip="02115"), loc(zip="0211512345"), loc(zip="ABC"), loc(zip="02116-1234")
    ])
    _, sites, _, count = run(multi)
    assert len(sites) == 4
    assert [s.zip for s in sites] == ["02115", "", "", "02116-1234"]
    assert count == 2


def test_zip_used_in_deduplication_before_validation():
    """Req 5.10: deduplication uses the stripped source zip; validation happens after."""
    # Two sites with same invalid zip: deduplicated to one, then blanked
    dup = study(locations=[
        loc(facility="A", zip="0211512345"),
        loc(facility="A", zip="0211512345")
    ])
    _, sites, _, count = run(dup)
    assert len(sites) == 1
    assert sites[0].zip == ""
    assert count == 1  # counted once, not twice
