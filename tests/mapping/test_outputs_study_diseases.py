"""Unit tests for `outputs.encode_study_diseases` (Req 9.1-9.5)."""
from __future__ import annotations

from dataclasses import dataclass

from pipeline.io.csv_writer import serialize
from pipeline.mapping.outputs import STUDY_DISEASES_HEADER, encode_study_diseases

HEADER_LINE = b"nctId,measureid,disease_label,match_status,exclusion_reason,matched_on,matched_term\n"


@dataclass(frozen=True)
class Row:  # local stand-in with the StudyDiseaseRow attributes
    nctId: str
    measureid: str
    disease_label: str = "Asthma"
    match_status: str = "included"
    exclusion_reason: str = ""
    matched_on: str = "meshTerms"
    matched_term: str = "Asthma"


def _bytes(rows) -> bytes:
    return serialize(encode_study_diseases(rows))


def test_header_order_and_kind():
    table = encode_study_diseases([])
    assert table.kind == "study_diseases"
    assert table.header == STUDY_DISEASES_HEADER
    assert table.rows == []


def test_no_rows_gives_header_only_file():
    assert _bytes([]) == HEADER_LINE


def test_each_row_has_seven_cells_and_lf_endings_no_bom():
    data = _bytes([Row("NCT00000001", "CASTHMA")])
    assert not data.startswith(b"\xef\xbb\xbf")
    assert b"\r" not in data
    assert data.endswith(b"\n") and not data.endswith(b"\n\n")
    assert data == HEADER_LINE + b"NCT00000001,CASTHMA,Asthma,included,,meshTerms,Asthma\n"


def test_quoting_of_comma_quote_cr_lf_and_no_quotes_on_empty():
    row = Row(
        "NCT00000001", "DIABETES",
        disease_label="Diabetes",
        match_status="excluded",
        exclusion_reason="",
        matched_on="conditions",
        matched_term='Diabetes Mellitus, Type 2',
    )
    tricky = [
        Row("NCT00000002", "CASTHMA", matched_term='say "asthma"'),
        Row("NCT00000003", "CASTHMA", matched_term="a\rb"),
        Row("NCT00000004", "CASTHMA", matched_term="a\nb"),
        Row("NCT00000005", "CASTHMA", matched_term="Asthme é"),
    ]
    lines = _bytes([row, *tricky]).decode("utf-8")
    assert lines == (
        HEADER_LINE.decode()
        + 'NCT00000001,DIABETES,Diabetes,excluded,,conditions,"Diabetes Mellitus, Type 2"\n'
        + 'NCT00000002,CASTHMA,Asthma,included,,meshTerms,"say ""asthma"""\n'
        + 'NCT00000003,CASTHMA,Asthma,included,,meshTerms,"a\rb"\n'
        + 'NCT00000004,CASTHMA,Asthma,included,,meshTerms,"a\nb"\n'
        + "NCT00000005,CASTHMA,Asthma,included,,meshTerms,Asthme é\n"
    )


def test_sorted_by_nctid_then_measureid_code_point_order():
    rows = [
        Row("NCT2", "HIGHCHOL"),
        Row("NCT1", "HIGHCHOL"),
        Row("NCT2", "CASTHMA"),
        Row("NCT1", "DIABETES"),
        Row("NCT1", "CASTHMA"),
        Row("nct0", "CASTHMA"),  # lowercase sorts after uppercase by code point
    ]
    keys = [(r[0], r[1]) for r in encode_study_diseases(rows).rows]
    assert keys == [
        ("NCT1", "CASTHMA"), ("NCT1", "DIABETES"), ("NCT1", "HIGHCHOL"),
        ("NCT2", "CASTHMA"), ("NCT2", "HIGHCHOL"), ("nct0", "CASTHMA"),
    ]
    assert _bytes(rows) == _bytes(list(reversed(rows)))
