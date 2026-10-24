"""PLACES_Transformer tests (Req 6.1-6.8, 13.11).
Property P7 (design § Correctness Properties) plus examples.
"""
import pytest
from hypothesis import given
from hypothesis import strategies as st

from pipeline.errors import PipelineError
from pipeline.transform.places_transformer import (
    PlacesDuplicate, PlacesRow, build_places_rows,
)


def rec(**overrides):
    """A PLACES record shaped like probe V5/V8 output (all values as JSON strings)."""
    record = {
        "locationname": "Worcester", "locationid": "25027", "measureid": "ARTHRITIS",
        "measure": "Arthritis among adults", "data_value": "27.3",
        "low_confidence_limit": "24.4", "high_confidence_limit": "30.4",
        "totalpop18plus": "687005",
        "geolocation": {"type": "Point", "coordinates": [-71.9077, 42.3513]},
        "year": "2023", "stateabbr": "MA", "datavaluetypeid": "CrdPrv",
    }
    record.update(overrides)
    return {k: v for k, v in record.items() if v is not None}


# --- Property P7 (Req 6.8, 13.11) ---------------------------------------------

locationid_sources = st.one_of(
    st.integers(0, 99999),
    st.text(alphabet="0123456789", min_size=1, max_size=5),  # includes leading zeros
)


@given(st.lists(locationid_sources, min_size=1, max_size=20))
def test_p7_locationid_is_zero_padded_five_digits(sources):
    """**Validates: Requirements 6.8, 13.11**"""
    records = [rec(locationid=src, measureid="M%d" % i) for i, src in enumerate(sources)]
    rows, _ = build_places_rows(records)
    assert len(rows) == len(sources)
    by_measure = {row.measureid: row for row in rows}
    for i, src in enumerate(sources):
        fips = by_measure["M%d" % i].locationid
        assert isinstance(fips, str) and len(fips) == 5 and fips.isdigit()
        assert fips == str(src).zfill(5)


# --- Examples -------------------------------------------------------------------

def test_basic_row_keeps_source_text():
    """Req 6.1, 6.5: values copied as source text; GeoJSON is longitude first."""
    rows, dups = build_places_rows([rec()])
    assert dups == []
    assert rows == [PlacesRow("Worcester", "25027", "ARTHRITIS", "Arthritis among adults",
                              "27.3", "24.4", "30.4", "687005", "42.3513", "-71.9077",
                              "2023")]


def test_filter_keeps_only_ma_crude_prevalence():
    """Req 6.2: other states and value types are dropped before the duplicate check."""
    rows, dups = build_places_rows([
        rec(stateabbr="RI"), rec(datavaluetypeid="AgeAdjPrv"), rec(stateabbr="ma"),
        rec(measureid="KEEP"),
    ])
    assert [r.measureid for r in rows] == ["KEEP"]
    assert dups == []


@pytest.mark.parametrize("records", [[], [rec(stateabbr="CT")], [rec(datavaluetypeid="AgeAdjPrv")]])
def test_zero_records_after_filter_stops(records):
    """Req 6.7."""
    with pytest.raises(PipelineError, match="no Massachusetts Crude_Prevalence records"):
        build_places_rows(records)


def test_numeric_year_beats_missing_year():
    """Req 6.3: a missing or non-numeric year is older than any numeric year."""
    rows, dups = build_places_rows([
        rec(year=None, data_value="1"), rec(year="n/a", data_value="2"),
        rec(year="2022", data_value="3"),
    ])
    assert [r.data_value for r in rows] == ["3"]
    assert dups == [PlacesDuplicate("25027", "ARTHRITIS", "2022", 2)]


def test_latest_year_kept_and_tie_goes_to_first_in_fetch_order():
    """Req 6.3: highest year wins; equal years keep the first record."""
    rows, dups = build_places_rows([
        rec(year="2022", data_value="1"), rec(year="2023", data_value="2"),
        rec(year="2023", data_value="3"),
        rec(measureid="OTHER", year="2023"),
    ])
    assert {r.measureid: r.data_value for r in rows} == {"ARTHRITIS": "2", "OTHER": "27.3"}
    assert dups == [PlacesDuplicate("25027", "ARTHRITIS", "2023", 2)]


def test_duplicates_match_on_fips_not_source_text():
    """Req 6.3, 6.8: int 1001 and string "01001" are the same County_FIPS."""
    rows, dups = build_places_rows([rec(locationid=1001), rec(locationid="01001")])
    assert [r.locationid for r in rows] == ["01001"]
    assert dups == [PlacesDuplicate("01001", "ARTHRITIS", "2023", 1)]


@pytest.mark.parametrize("bad", ["25a", 250010, 1.0, True, "", "123456", "-1", " 25027",
                                 "25027\n", "٢٥٠٢٧", None])
def test_bad_locationid_stops_naming_field(bad):
    """Req 6.6: the error names the field and the record identifiers, not the value."""
    with pytest.raises(PipelineError) as err:
        build_places_rows([rec(locationid=bad)])
    message = str(err.value)
    assert "locationid" in message
    assert "locationname Worcester" in message and "measureid ARTHRITIS" in message
    if isinstance(bad, str) and bad.strip():
        assert bad.strip() not in message


@pytest.mark.parametrize("field", ["locationname", "measureid"])
@pytest.mark.parametrize("value", [None, "", "  "])
def test_missing_identifier_stops_naming_field(field, value):
    """Req 6.6."""
    with pytest.raises(PipelineError, match="field %s is missing or empty" % field):
        build_places_rows([rec(**{field: value})])


def test_bad_identifier_in_any_record_stops_even_if_valid_duplicate_exists():
    """Req 6.6: identifiers are validated on every retained record."""
    with pytest.raises(PipelineError, match="locationid"):
        build_places_rows([rec(), rec(locationid="25a")])


@pytest.mark.parametrize("field", ["data_value", "low_confidence_limit", "high_confidence_limit"])
@pytest.mark.parametrize("value", ["-0.1", "100.01", "abc", "", None, "NaN", "Infinity",
                                   " 5", "1_0", True, [5]])
def test_out_of_range_or_invalid_percentages_become_empty(field, value):
    """Req 6.4: the row is still written with an empty cell."""
    rows, _ = build_places_rows([rec(**{field: value})])
    assert len(rows) == 1 and getattr(rows[0], field) == ""


@pytest.mark.parametrize("value", ["0", "100", "0.0", "100.000", "1e1"])
def test_percentage_boundaries_keep_source_text(value):
    """Req 6.1, 6.4: 0 and 100 are inside the range; text is not reformatted."""
    rows, _ = build_places_rows([rec(data_value=value)])
    assert rows[0].data_value == value


@pytest.mark.parametrize("value,expected", [("-1", ""), ("0", "0"), ("x", ""), (None, ""),
                                            ("12345678901234567890", "12345678901234567890")])
def test_totalpop18plus_range(value, expected):
    """Req 6.4: totalpop18plus must be numeric and at least 0."""
    rows, _ = build_places_rows([rec(totalpop18plus=value)])
    assert rows[0].totalpop18plus == expected


@pytest.mark.parametrize("geo,expected", [
    ("POINT (-71.9077 42.3513)", ("42.3513", "-71.9077")),
    ({"type": "Point", "coordinates": [-180, 90]}, ("90", "-180")),
    ({"type": "Point", "coordinates": [-71.9, 90.5]}, ("", "")),
    ({"type": "Point", "coordinates": [-180.5, 42.0]}, ("", "")),
    ({"type": "Point", "coordinates": [-71.9]}, ("", "")),
    ({"type": "Polygon", "coordinates": [-71.9, 42.3]}, ("", "")),
    ("POINT (-71.9 95)", ("", "")),
    ("garbage", ("", "")),
    (None, ("", "")),
])
def test_geolocation(geo, expected):
    """Req 6.5: GeoJSON (longitude first) or WKT; missing or out of range is empty."""
    rows, _ = build_places_rows([rec(geolocation=geo)])
    assert (rows[0].latitude, rows[0].longitude) == expected
