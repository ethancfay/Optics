"""Sanity_Checker examples (Req 11.1, 11.2, 11.6)."""
import io

import pytest

from pipeline.transform import sanity_checker
from pipeline.transform.places_transformer import PlacesRow
from pipeline.transform.study_transformer import SiteRow, StudyRow


def study(nct_id, study_type="INTERVENTIONAL"):
    return StudyRow(
        nctId=nct_id, briefTitle="", overallStatus="RECRUITING", studyType=study_type,
        phases=[], healthyVolunteers="", minimumAge="", maximumAge="", stdAges=[],
        conditions=[], interventionTypes=[], interventionNames=[], meshTerms=[], meshIds=[],
        ancestorTerms=[], ancestorIds=[], lastUpdatePostDate="",
        source_url="https://clinicaltrials.gov/study/" + nct_id)


def site(nct_id, state="Massachusetts", status="RECRUITING"):
    return SiteRow(nctId=nct_id, facility="F", city="C", state=state, zip="", latitude="",
                   longitude="", siteStatus=status, location_quality="missing_geo")


def places(n_counties):
    return [PlacesRow(locationname="County %d" % i, locationid="%05d" % i, measureid=m,
                      measure="", data_value="", low_confidence_limit="",
                      high_confidence_limit="", totalpop18plus="", latitude="", longitude="",
                      year="2023")
            for i in range(n_counties) for m in ("A", "B")]


def ma_rows(n):
    ids = ["NCT%08d" % i for i in range(n)]
    states = ["Massachusetts", "MA", " ma "]
    return [study(i) for i in ids], [site(i, states[k % 3]) for k, i in enumerate(ids)]


def run(studies, sites, place_rows):
    stream = io.StringIO()
    warnings = sanity_checker.check(studies, sites, place_rows, stream=stream)
    assert stream.getvalue() == "".join(w + "\n" for w in warnings)
    return warnings


def test_2000_ma_studies_and_14_counties_give_no_warning():
    """Req 11.1 (exactly 2,000 is fine), 11.6."""
    studies, sites = ma_rows(2000)
    assert run(studies, sites, places(14)) == []


def test_1999_ma_studies_warns_with_count_and_threshold():
    """Req 11.1."""
    studies, sites = ma_rows(1999)
    warnings = run(studies, sites, places(14))
    assert len(warnings) == 1
    assert "1999" in warnings[0] and "2000" in warnings[0]


def test_non_qualifying_studies_are_not_counted():
    """Req 11.1: needs INTERVENTIONAL, a MA site, and site status RECRUITING."""
    studies, sites = ma_rows(1999)
    studies += [study("NCTX1", "OBSERVATIONAL"), study("NCTX2"), study("NCTX3")]
    sites += [site("NCTX1"), site("NCTX2", state="Rhode Island"),
              site("NCTX3", status="COMPLETED"), site(studies[0].nctId, "MA")]
    assert sanity_checker.ma_recruiting_interventional_count(studies, sites) == 1999


@pytest.mark.parametrize("n", [13, 0])
def test_county_count_other_than_14_warns(n):
    """Req 11.2, including zero PLACES_Rows."""
    studies, sites = ma_rows(2000)
    warnings = run(studies, sites, places(n))
    assert len(warnings) == 1
    assert ("%d distinct" % n) in warnings[0] and "14" in warnings[0]


def test_both_warnings_go_to_stderr_by_default(capsys):
    """Req 11.1, 11.2: printed to standard error."""
    warnings = sanity_checker.check([], [], [])
    assert len(warnings) == 2
    captured = capsys.readouterr()
    assert captured.err == "".join(w + "\n" for w in warnings)
    assert captured.out == ""
