"""PII_Guard examples (Req 8.1, 8.2, 8.4, 8.5)."""
import pytest

from pipeline.errors import PipelineError
from pipeline.io.csv_writer import encode_rows
from pipeline.transform import pii_guard
from pipeline.transform.places_transformer import PlacesRow
from pipeline.transform.study_transformer import SiteRow, StudyRow

EMAIL_VALUE = "jane.doe@example.org"
PHONE_VALUE = "(617) 555-0100"


def study(nct_id="NCT00000001", **overrides):
    values = dict(
        nctId=nct_id, briefTitle="A study", overallStatus="RECRUITING",
        studyType="INTERVENTIONAL", phases=["PHASE2"], healthyVolunteers="false",
        minimumAge="18 Years", maximumAge="", stdAges=["ADULT"], conditions=["Asthma"],
        interventionTypes=["DRUG"], interventionNames=["X"], meshTerms=[], meshIds=[],
        ancestorTerms=[], ancestorIds=[], lastUpdatePostDate="2026-01-02",
        source_url="https://clinicaltrials.gov/study/" + nct_id,
    )
    values.update(overrides)
    return StudyRow(**values)


def site(nct_id="NCT00000001", facility="Site A", latitude="42.3", longitude="-71.8"):
    return SiteRow(nctId=nct_id, facility=facility, city="Worcester", state="Massachusetts",
                   zip="01605", latitude=latitude, longitude=longitude,
                   siteStatus="RECRUITING", location_quality="ok")


def place(**overrides):
    values = dict(locationname="Worcester", locationid="25027", measureid="CASTHMA",
                  measure="Current asthma", data_value="10.1", low_confidence_limit="9.0",
                  high_confidence_limit="11.2", totalpop18plus="700000",
                  latitude="42.35", longitude="-71.9", year="2023")
    values.update(overrides)
    return PlacesRow(**values)


def tables(studies=(), sites=(), places=()):
    return {"studies": encode_rows("studies", studies), "sites": encode_rows("sites", sites),
            "places": encode_rows("places", places)}


def test_clean_tables_pass_unchanged():
    """Req 8.5: no match, no error, rows untouched."""
    t = tables([study()], [site()], [place()])
    before = {k: [list(r) for r in v.rows] for k, v in t.items()}
    pii_guard.check(t)
    assert {k: v.rows for k, v in t.items()} == before


def test_email_in_scalar_cell_is_caught():
    """Req 8.1, 8.2, 8.4."""
    with pytest.raises(PipelineError) as err:
        pii_guard.check(tables([study(briefTitle="Contact " + EMAIL_VALUE)]))
    msg = str(err.value)
    assert "1 contact pattern match" in msg
    assert "studies.csv: nctId=NCT00000001: field briefTitle: email" in msg
    assert EMAIL_VALUE not in msg and "example.org" not in msg


def test_phone_in_list_item_is_caught():
    """Req 8.1: decoded list elements are checked."""
    with pytest.raises(PipelineError) as err:
        pii_guard.check(tables([study(interventionNames=["X", "call " + PHONE_VALUE])]))
    msg = str(err.value)
    assert "field interventionNames: phone" in msg
    assert "555-0100" not in msg


@pytest.mark.parametrize("value", ["617-555-0100", "+1 617.555.0100", "6175550100"])
def test_phone_forms_are_caught(value):
    """Req 8.1, Phone_Pattern glossary examples."""
    assert pii_guard.find_matches(tables(places=[place(measure="x " + value)]))


@pytest.mark.parametrize("coordinate", ["-71.8123456789", "42.30000000000001", "-71.80123456789012"])
def test_long_coordinate_decimal_is_not_flagged(coordinate):
    """Design § PII_Guard: lookbehind stops coordinates matching Phone_Pattern."""
    t = tables(sites=[site(latitude=coordinate, longitude=coordinate)],
               places=[place(latitude=coordinate, longitude=coordinate)])
    pii_guard.check(t)


def test_error_lists_every_match_and_no_matched_text():
    """Req 8.4: total count plus one entry per match, with Site_Row positions."""
    t = tables(
        studies=[study("NCT00000001", briefTitle=EMAIL_VALUE),
                 study("NCT00000002", conditions=["Asthma", PHONE_VALUE])],
        sites=[site("NCT00000001", facility="A"),
               site("NCT00000002", facility="Clinic " + EMAIL_VALUE)],
        places=[place(measure="Call " + PHONE_VALUE)],
    )
    with pytest.raises(PipelineError) as err:
        pii_guard.check(t)
    msg = str(err.value)
    assert msg.startswith("PII_Guard: 4 contact pattern match(es)")
    assert "studies.csv: nctId=NCT00000001: field briefTitle: email" in msg
    assert "studies.csv: nctId=NCT00000002: field conditions: phone" in msg
    assert "sites.csv: nctId=NCT00000002, row 2: field facility: email" in msg
    assert "places_ma.csv: locationname=Worcester, measureid=CASTHMA: field measure: phone" in msg
    for fragment in (EMAIL_VALUE, "jane.doe", "example.org", "617", "555-0100"):
        assert fragment not in msg


def test_matching_identifier_is_redacted():
    """Req 8.4: the row identifier never carries matched text."""
    with pytest.raises(PipelineError) as err:
        pii_guard.check(tables(places=[place(locationname=EMAIL_VALUE)]))
    msg = str(err.value)
    assert "locationname=<redacted>" in msg
    assert EMAIL_VALUE not in msg
