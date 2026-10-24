"""CSV_Writer examples (Req 7.2-7.5, 7.8, 7.9)."""
from dataclasses import fields

from pipeline.io.csv_writer import (
    COLUMNS, LIST_COLUMNS, ROW_TYPES, encode_rows, quote_cell, serialize,
)
from pipeline.transform.places_transformer import PlacesRow
from pipeline.transform.study_transformer import SiteRow, StudyRow

STUDIES_HEADER = (
    "nctId,briefTitle,overallStatus,studyType,phases,healthyVolunteers,minimumAge,"
    "maximumAge,stdAges,conditions,interventionTypes,interventionNames,meshTerms,"
    "meshIds,ancestorTerms,ancestorIds,lastUpdatePostDate,source_url"
)
SITES_HEADER = "nctId,facility,city,state,zip,latitude,longitude,siteStatus,location_quality"
PLACES_HEADER = (
    "locationname,locationid,measureid,measure,data_value,low_confidence_limit,"
    "high_confidence_limit,totalpop18plus,latitude,longitude,year"
)


def study(nct_id="NCT00000001", **overrides):
    values = dict(
        nctId=nct_id, briefTitle='Drug "X", phase 2', overallStatus="RECRUITING",
        studyType="INTERVENTIONAL", phases=["PHASE2", "PHASE3"], healthyVolunteers="false",
        minimumAge="18 Years", maximumAge="", stdAges=["ADULT", "OLDER_ADULT"],
        conditions=["Diabète"], interventionTypes=["DRUG"], interventionNames=["X|Y"],
        meshTerms=[], meshIds=[], ancestorTerms=[""], ancestorIds=[""],
        lastUpdatePostDate="2026-01-02", source_url="https://clinicaltrials.gov/study/" + nct_id,
    )
    values.update(overrides)
    return StudyRow(**values)


def site(nct_id="NCT00000001", facility="Site A", zip_code="01605", city="Worcester"):
    return SiteRow(nctId=nct_id, facility=facility, city=city, state="Massachusetts",
                   zip=zip_code, latitude="42.3", longitude="-71.8", siteStatus="RECRUITING",
                   location_quality="ok")


def test_columns_follow_dataclass_order_and_list_fields():
    """Req 7.2: header order is the field order of Req 4.2, 5.1, 6.1; stdAges is a list column."""
    assert ",".join(COLUMNS["studies"]) == STUDIES_HEADER
    assert ",".join(COLUMNS["sites"]) == SITES_HEADER
    assert ",".join(COLUMNS["places"]) == PLACES_HEADER
    for kind, row_type in ROW_TYPES.items():
        annotated = {f.name for f in fields(row_type) if "list" in str(f.type)}
        assert LIST_COLUMNS[kind] == annotated
    assert "stdAges" in LIST_COLUMNS["studies"]


def test_exact_bytes_for_small_fixture():
    """Req 7.2, 7.3, 7.4, 7.5: header row, minimal quoting, compact UTF-8 JSON arrays, LF."""
    data = serialize(encode_rows("studies", [study()]))
    expected = (
        STUDIES_HEADER + "\n"
        'NCT00000001,"Drug ""X"", phase 2",RECRUITING,INTERVENTIONAL,'
        '"[""PHASE2"",""PHASE3""]",false,18 Years,,"[""ADULT"",""OLDER_ADULT""]",'
        '"[""Diabète""]","[""DRUG""]","[""X|Y""]",[],[],"[""""]","[""""]",'
        "2026-01-02,https://clinicaltrials.gov/study/NCT00000001\n"
    ).encode("utf-8")
    assert data == expected
    assert not data.startswith(b"\xef\xbb\xbf")
    assert b"\r" not in data


def test_quote_cell_rule():
    """Req 7.3: quote iff comma, double quote, CR or LF."""
    assert quote_cell("plain|text") == "plain|text"
    assert quote_cell("") == ""
    assert quote_cell("a,b") == '"a,b"'
    assert quote_cell('a"b') == '"a""b"'
    assert quote_cell("a\rb") == '"a\rb"'
    assert quote_cell("a\nb") == '"a\nb"'


def test_list_elements_with_line_breaks_are_json_escaped():
    """Req 7.4, 7.5: JSON escaping is the only list-level escape."""
    row = study(conditions=["a\nb", "c\\d", "[x]"])
    cell = encode_rows("studies", [row]).rows[0][COLUMNS["studies"].index("conditions")]
    assert cell == '["a\\nb","c\\\\d","[x]"]'


def test_zero_rows_writes_header_only():
    """Req 7.9."""
    assert serialize(encode_rows("sites", [])) == (SITES_HEADER + "\n").encode()
    assert serialize(encode_rows("places", [])) == (PLACES_HEADER + "\n").encode()


def test_sort_order_with_tie_breakers():
    """Req 7.8: code point order on the specified keys, remaining columns break ties."""
    studies = encode_rows("studies", [study("NCT2"), study("NCT10"), study("nct1")])
    assert [r[0] for r in studies.rows] == ["NCT10", "NCT2", "nct1"]
    sites = encode_rows("sites", [
        site("NCT1", "B", "1"), site("NCT1", "A", "2"), site("NCT1", "A", "1", city="Z"),
        site("NCT1", "A", "1", city="Boston"), site("NCT0", "Z", "9"),
    ])
    assert [(r[0], r[1], r[4], r[2]) for r in sites.rows] == [
        ("NCT0", "Z", "9", "Worcester"), ("NCT1", "A", "1", "Boston"),
        ("NCT1", "A", "1", "Z"), ("NCT1", "A", "2", "Worcester"), ("NCT1", "B", "1", "Worcester"),
    ]
    p = dict(measure="m", data_value="1", low_confidence_limit="", high_confidence_limit="",
             totalpop18plus="", latitude="", longitude="")
    places = encode_rows("places", [
        PlacesRow("Worcester", "25027", "ARTHRITIS", year="2023", **p),
        PlacesRow("Barnstable", "25001", "OBESITY", year="2023", **p),
        PlacesRow("Barnstable", "25001", "ARTHRITIS", year="2023", **p),
    ])
    assert [(r[0], r[2]) for r in places.rows] == [
        ("Barnstable", "ARTHRITIS"), ("Barnstable", "OBESITY"), ("Worcester", "ARTHRITIS"),
    ]


def test_same_input_gives_identical_bytes():
    """Req 7.8: identical inputs (in any order) give byte-identical files."""
    rows = [site("NCT2", "B"), site("NCT1", "A"), site("NCT1", "A", city="Boston")]
    first = serialize(encode_rows("sites", rows))
    second = serialize(encode_rows("sites", list(reversed(rows))))
    assert first == second
    assert serialize(encode_rows("studies", [study()])) == serialize(encode_rows("studies", [study()]))
