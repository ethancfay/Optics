"""read_table examples and the read_csv wrapper (Spec 2 Req 1.3, 1.4, 1.6, 14.12)."""
from dataclasses import asdict

import pytest

from pipeline.errors import PipelineError
from pipeline.io.csv_reader import read_csv, read_table
from pipeline.io.csv_writer import COLUMNS, LIST_COLUMNS, encode_rows, serialize
from pipeline.transform.study_transformer import SiteRow

HEADER = ("id", "tags", "note")


def _write(tmp_path, text: str, name: str = "t.csv"):
    path = tmp_path / name
    path.write_bytes(text.encode("utf-8"))
    return path


def test_rows_carry_start_line_numbers(tmp_path):
    path = _write(tmp_path, 'id,tags,note\nA,"[""x""]",n1\nB,[],n2\n')
    assert read_table(path, HEADER, {"tags"}) == [
        (2, {"id": "A", "tags": ["x"], "note": "n1"}),
        (3, {"id": "B", "tags": [], "note": "n2"}),
    ]


def test_multi_line_cell_reports_start_line(tmp_path):
    path = _write(tmp_path, 'id,tags,note\nA,[],"one\ntwo\nthree"\nB,[],n\nC,BAD,n\n')
    with pytest.raises(PipelineError) as err:
        read_table(path, HEADER, {"tags"})
    assert str(err.value) == "t.csv: line 6 column tags is not a JSON array of strings"
    path = _write(tmp_path, 'id,tags,note\nA,[],"one\ntwo"\nB,[],n\n')
    assert [line for line, _ in read_table(path, HEADER, {"tags"})] == [2, 4]


def test_multi_line_bad_cell_reports_first_line(tmp_path):
    path = _write(tmp_path, 'id,tags,note\nA,"SECRET\nmore",n\n')
    with pytest.raises(PipelineError) as err:
        read_table(path, HEADER, {"tags"})
    assert "line 2 column tags" in str(err.value)
    assert "SECRET" not in str(err.value)


def test_header_mismatch_names_file_only(tmp_path):
    path = _write(tmp_path, "id,SECRET,note\nA,[],n\n", "studies.csv")
    with pytest.raises(PipelineError) as err:
        read_table(path, HEADER, {"tags"})
    assert str(err.value).startswith("studies.csv: header row does not match")
    assert "SECRET" not in str(err.value)


def test_empty_file_is_header_mismatch(tmp_path):
    path = _write(tmp_path, "")
    with pytest.raises(PipelineError, match="t.csv: header row"):
        read_table(path, HEADER, set())


def test_bad_list_cell_names_line_and_column(tmp_path):
    path = _write(tmp_path, 'id,tags,note\nA,[],n\nB,"[1]",SECRET\n')
    with pytest.raises(PipelineError) as err:
        read_table(path, HEADER, {"tags"})
    assert str(err.value) == "t.csv: line 3 column tags is not a JSON array of strings"


def test_non_list_columns_are_not_json_checked(tmp_path):
    path = _write(tmp_path, "id,tags,note\nA,not json,n\n")
    assert read_table(path, HEADER, frozenset()) == [
        (2, {"id": "A", "tags": "not json", "note": "n"})]


def test_wrong_cell_count_names_line(tmp_path):
    path = _write(tmp_path, 'id,tags,note\nA,[],n\nB,"SECRET\nx",n,extra\n')
    with pytest.raises(PipelineError) as err:
        read_table(path, HEADER, {"tags"})
    assert str(err.value) == "t.csv: line 3 has 4 cells, expected 3"


def test_read_csv_matches_read_table_without_line_numbers(tmp_path):
    rows = [SiteRow(nctId="NCT1", facility="F, \"q\"\nx", city="Boston", state="MA",
                    zip="02115", latitude="42.3", longitude="-71.1",
                    siteStatus="RECRUITING", location_quality="ok"),
            SiteRow(nctId="NCT2", facility="", city="", state="", zip="", latitude="",
                    longitude="", siteStatus="", location_quality="missing_geo")]
    path = tmp_path / "sites.csv"
    path.write_bytes(serialize(encode_rows("sites", rows)))
    expected = [asdict(r) for r in rows]
    assert read_csv(path, "sites") == expected
    table = read_table(path, COLUMNS["sites"], LIST_COLUMNS["sites"])
    assert [row for _, row in table] == expected
    assert [line for line, _ in table] == [2, 4]


def test_read_csv_keeps_spec1_header_message(tmp_path):
    path = _write(tmp_path, "a,b\n1,2\n", "sites.csv")
    with pytest.raises(PipelineError) as err:
        read_csv(path, "sites")
    assert str(err.value) == "sites.csv: header row does not match the sites columns"
