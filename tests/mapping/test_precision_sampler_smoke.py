"""Smoke test for the Precision_Sampler (task 5.1).
Property 13 is in task 5.2 and full unit tests in task 5.3.
"""
import io
from types import SimpleNamespace

import pytest

from pipeline.errors import PipelineError
from pipeline.io.csv_writer import serialize
from pipeline.mapping import precision_sampler as ps
from pipeline.mapping.grouping_engine import StudyDiseaseRow


def _row(nct, mid, status):
    return StudyDiseaseRow(nct, mid, mid.lower(), status, "", "condition_text", "term " + nct)


def _study(nct):
    return SimpleNamespace(brief_title="Title, " + nct, conditions_cell='["A","B"]',
                           source_url="https://clinicaltrials.gov/study/" + nct)


def test_build_samples_included_ma_rows_and_warns():
    ids = ["NCT%02d" % i for i in range(25)]
    rows = [_row(n, "DIABETES", "included") for n in ids]
    rows += [_row("NCT01", "CASTHMA", "included"), _row("NCT02", "CASTHMA", "excluded"),
             _row("NCT99", "CASTHMA", "included")]          # NCT99 has no MA_Site
    studies = {n: _study(n) for n in ids + ["NCT99"]}
    rules = SimpleNamespace(seed=7, diseases=(SimpleNamespace(measureid="CASTHMA"),
                                              SimpleNamespace(measureid="DIABETES")))
    err = io.StringIO()
    table = ps.build(rules, rows, studies, set(ids), stderr=err)

    assert table.header == ps.HEADER
    assert [r[:2] for r in table.rows if r[1] == "CASTHMA"] == [["NCT01", "CASTHMA"]]
    diabetes = [r for r in table.rows if r[1] == "DIABETES"]
    assert len(diabetes) == 20 and len({r[0] for r in diabetes}) == 20
    assert [r[0] for r in diabetes] == sorted(ps.select(ids, 7))
    assert diabetes[0][2:] == ["Title, " + diabetes[0][0], '["A","B"]', "term " + diabetes[0][0],
                               "https://clinicaltrials.gov/study/" + diabetes[0][0], ""]
    assert err.getvalue() == "warning: precision sample CASTHMA: only 1 candidates (fewer than 20)\n"
    assert ps.build(rules, rows, studies, set(ids), stderr=io.StringIO()) == table


def test_existing_state(tmp_path):
    path = tmp_path / "precision_sample.csv"
    assert ps.existing_state(path, False) == ("write", 0)

    blank = ps.EncodedTable("precision_sample", ps.HEADER, [["N1", "M", "t", "[]", "x", "u", " "]])
    path.write_bytes(serialize(blank))
    assert ps.existing_state(path, False) == ("write", 0)

    filled = ps.EncodedTable("precision_sample", ps.HEADER,
                             [["N1", "M", "t", "[]", "x", "u", "yes"],
                              ["N2", "M", "t", "[]", "x", "u", "no"]])
    path.write_bytes(serialize(filled))
    err = io.StringIO()
    assert ps.existing_state(path, False, stderr=err) == ("keep", 2)
    assert "precision_sample.csv" in err.getvalue() and "2" in err.getvalue()
    assert ps.existing_state(path, True) == ("write", 0)

    path.write_bytes(b"wrong,header\n")
    with pytest.raises(PipelineError, match="precision_sample.csv"):
        ps.existing_state(path, False)
    path.write_bytes(b"\xff\xfe")
    with pytest.raises(PipelineError, match="precision_sample.csv: not valid UTF-8"):
        ps.existing_state(path, False)
