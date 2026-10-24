"""Precision_Sampler unit tests (task 5.3).
Condition-grouping Req 11.2, 11.3, 11.6, 11.7, 11.8 (design § Precision_Sampler).
"""
import io

import pytest

from pipeline.errors import PipelineError
from pipeline.io.csv_writer import EncodedTable, serialize
from pipeline.mapping import precision_sampler as ps
from pipeline.mapping.grouping_engine import StudyDiseaseRow
from pipeline.mapping.inputs import Study
from pipeline.mapping.rules_loader import Disease, RulesConfig, Term, normalize

HEADER_LINE = b"nctId,measureid,briefTitle,conditions,matched_term,source_url,correct\n"


def _disease(mid):
    return Disease(mid, mid.title(), "included", mid.title(),
                   (Term(mid.title(), normalize(mid.title()), "include", ""),))


RULES = RulesConfig(diseases=(_disease("CASTHMA"), _disease("DIABETES")), seed=42)


def _row(nct, mid, status="included"):
    return StudyDiseaseRow(nct, mid, mid.title(), status, "", "condition_text", "term " + nct)


def _study(nct):
    return Study(nct, "Title " + nct, "RECRUITING", "false", "", ("A",), (), (),
                 '["A"]', "https://clinicaltrials.gov/study/" + nct)


def _sample_file(tmp_path, correct_cells):
    rows = [["NCT%02d" % i, "CASTHMA", "t", "[]", "x", "u", c]
            for i, c in enumerate(correct_cells)]
    path = tmp_path / "precision_sample.csv"
    path.write_bytes(serialize(EncodedTable("precision_sample", ps.HEADER, rows)))
    return path


# Req 11.2: fewer than 20 candidates -> every candidate, one warning with the count.
def test_fewer_than_20_candidates_includes_all_and_warns():
    ids = ["NCT%02d" % i for i in range(5)]
    rows = [_row(n, "DIABETES") for n in ids] + [_row("NCT90", "DIABETES", "questionable")]
    rows += [_row("NCT%02d" % i, "CASTHMA") for i in range(30)]
    studies = {s: _study(s) for s in ["NCT%02d" % i for i in range(30)] + ["NCT90"]}
    ma = set(studies)
    err = io.StringIO()
    table = ps.build(RULES, rows, studies, ma, stderr=err)

    assert [r[0] for r in table.rows if r[1] == "DIABETES"] == ids
    assert len([r for r in table.rows if r[1] == "CASTHMA"]) == 20
    assert err.getvalue() == "warning: precision sample DIABETES: only 5 candidates (fewer than 20)\n"


# Req 11.2: zero candidates -> warning naming measureid with count 0, no rows.
def test_zero_candidates_warns_and_writes_no_rows():
    rows = [_row("NCT01", "CASTHMA"),                    # no MA_Site
            _row("NCT02", "CASTHMA", "excluded")]        # not included
    studies = {"NCT01": _study("NCT01"), "NCT02": _study("NCT02")}
    err = io.StringIO()
    table = ps.build(RULES, rows, studies, {"NCT02"}, stderr=err)

    assert table.rows == []
    assert "warning: precision sample CASTHMA: only 0 candidates" in err.getvalue()
    assert "warning: precision sample DIABETES: only 0 candidates" in err.getvalue()


# Req 11.3: no disease has candidates -> header row only.
def test_no_candidates_serializes_header_only():
    table = ps.build(RULES, [], {}, set(), stderr=io.StringIO())
    assert serialize(table) == HEADER_LINE


# Req 11.3: rows sorted by measureid then nctId.
def test_rows_sorted_by_measureid_then_nctid():
    rows = [_row("NCT03", "DIABETES"), _row("NCT01", "DIABETES"),
            _row("NCT02", "CASTHMA"), _row("NCT01", "CASTHMA")]
    studies = {n: _study(n) for n in ("NCT01", "NCT02", "NCT03")}
    table = ps.build(RULES, rows, studies, set(studies), stderr=io.StringIO())
    assert [r[:2] for r in table.rows] == [["NCT01", "CASTHMA"], ["NCT02", "CASTHMA"],
                                           ["NCT01", "DIABETES"], ["NCT03", "DIABETES"]]


# Req 11.6: one filled `correct` cell -> keep, notice names the file and count.
def test_keep_when_a_correct_cell_is_filled(tmp_path):
    path = _sample_file(tmp_path, ["", "  ", "yes", ""])
    before = path.read_bytes()
    err = io.StringIO()
    assert ps.existing_state(path, False, stderr=err) == ("keep", 1)
    assert "precision_sample.csv" in err.getvalue() and " 1 " in err.getvalue()
    assert path.read_bytes() == before


# Req 11.7: all `correct` cells blank or whitespace -> write; --resample -> write.
def test_write_when_all_correct_cells_blank(tmp_path):
    err = io.StringIO()
    path = _sample_file(tmp_path, ["", " ", "\t"])
    assert ps.existing_state(path, False, stderr=err) == ("write", 0)
    assert err.getvalue() == ""
    path = _sample_file(tmp_path, ["yes"])
    assert ps.existing_state(path, True) == ("write", 0)


def test_write_when_existing_file_is_header_only(tmp_path):
    path = tmp_path / "precision_sample.csv"
    path.write_bytes(HEADER_LINE)
    assert ps.existing_state(path, False) == ("write", 0)


def test_write_when_file_missing(tmp_path):
    assert ps.existing_state(tmp_path / "precision_sample.csv", False) == ("write", 0)


# Req 11.8: unreadable file or wrong header -> PipelineError naming the file.
def test_wrong_header_raises_naming_file(tmp_path):
    path = tmp_path / "precision_sample.csv"
    path.write_bytes(b"nctId,measureid,briefTitle,conditions,matched_term,source_url\n")
    with pytest.raises(PipelineError, match="precision_sample.csv: header row"):
        ps.existing_state(path, False)


def test_empty_file_raises_naming_file(tmp_path):
    path = tmp_path / "precision_sample.csv"
    path.write_bytes(b"")
    with pytest.raises(PipelineError, match="precision_sample.csv"):
        ps.existing_state(path, False)


def test_wrong_cell_count_raises_naming_file(tmp_path):
    path = tmp_path / "precision_sample.csv"
    path.write_bytes(HEADER_LINE + b"NCT01,CASTHMA,t\n")
    with pytest.raises(PipelineError, match="precision_sample.csv: line 2"):
        ps.existing_state(path, False)


def test_invalid_utf8_raises_naming_file(tmp_path):
    path = tmp_path / "precision_sample.csv"
    path.write_bytes(HEADER_LINE + b"\xff,\n")
    with pytest.raises(PipelineError, match="precision_sample.csv: not valid UTF-8"):
        ps.existing_state(path, False)


def test_unopenable_path_raises_naming_file(tmp_path):
    path = tmp_path / "precision_sample.csv"
    path.mkdir()
    with pytest.raises(PipelineError, match="precision_sample.csv: cannot open"):
        ps.existing_state(path, False)
