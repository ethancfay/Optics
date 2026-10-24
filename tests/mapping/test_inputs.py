"""Inputs example tests (condition-grouping Req 1.1-1.4, 1.6, 1.7, 6.6, 11.4).
Every test writes its own `studies.csv` and `sites.csv` under `tmp_path`.
"""
import csv
import io

import pytest

from pipeline.errors import PipelineError
from pipeline.io.csv_writer import encode_list_cell, quote_cell
from pipeline.mapping.inputs import SITES_HEADER, STUDIES_HEADER, InputPaths, read_inputs

LIST_COLS = ("phases", "stdAges", "conditions", "interventionTypes", "interventionNames",
             "meshTerms", "meshIds", "ancestorTerms", "ancestorIds")


def _study(nct_id, **cells):
    row = {c: "" for c in STUDIES_HEADER}
    row.update({c: "[]" for c in LIST_COLS})
    row["nctId"] = nct_id
    row.update(cells)
    return row


def _site(nct_id, state="Massachusetts"):
    row = {c: "" for c in SITES_HEADER}
    row.update(nctId=nct_id, state=state)
    return row


def _table(header, rows):
    lines = [",".join(header)] + [",".join(quote_cell(r[c]) for c in header) for r in rows]
    return ("\n".join(lines) + "\n").encode("utf-8")


def _write(tmp_path, studies, sites=(), studies_bytes=None, sites_bytes=None):
    s = tmp_path / "studies.csv"
    t = tmp_path / "sites.csv"
    s.write_bytes(_table(STUDIES_HEADER, studies) if studies_bytes is None else studies_bytes)
    t.write_bytes(_table(SITES_HEADER, sites) if sites_bytes is None else sites_bytes)
    return InputPaths(studies=s, sites=t)


def _error(paths):
    with pytest.raises(PipelineError) as info:
        read_inputs(paths, stderr=io.StringIO())
    return str(info.value)


def test_reads_studies_and_ma_sites(tmp_path):
    paths = _write(tmp_path,
                   [_study("NCT1", briefTitle="T", overallStatus="RECRUITING",
                           healthyVolunteers="true", maximumAge="17 Years",
                           conditions='["Asthma"]', meshTerms='["Asthma"]',
                           ancestorTerms='["Lung Diseases"]', source_url="u1"),
                    _study("NCT2"), _study("NCT3"), _study("NCT4")],
                   [_site("NCT1"), _site("NCT2", "MA"), _site("NCT3", "New York"),
                    _site("NCT4", "ma"), _site("NCT4", "Massachusetts ")])
    err = io.StringIO()
    studies, ma = read_inputs(paths, stderr=err)
    assert ma == frozenset({"NCT1", "NCT2"})
    assert err.getvalue() == ""
    s = studies["NCT1"]
    assert (s.brief_title, s.overall_status, s.healthy_volunteers, s.maximum_age, s.source_url) \
        == ("T", "RECRUITING", "true", "17 Years", "u1")
    assert s.conditions == ("Asthma",) and s.mesh_terms == ("Asthma",)
    assert s.ancestor_terms == ("Lung Diseases",)
    assert sorted(studies) == ["NCT1", "NCT2", "NCT3", "NCT4"]


def test_conditions_cell_is_byte_identical_to_source(tmp_path):
    cells = [encode_list_cell(v) for v in
             (["Asthma"], [], ['Type "2", Diabetes', "Diabète", "a\\b", "\u00e9\u4e2d"])]
    paths = _write(tmp_path, [_study("NCT%d" % i, conditions=c) for i, c in enumerate(cells)])
    studies, _ = read_inputs(paths, stderr=io.StringIO())
    with open(paths.studies, encoding="utf-8", newline="") as handle:
        raw = {r["nctId"]: r["conditions"] for r in csv.DictReader(handle)}
    for nct_id, study in studies.items():
        assert study.conditions_cell == raw[nct_id]


def test_orphan_sites_are_ignored_with_one_warning(tmp_path):
    paths = _write(tmp_path, [_study("NCT1")],
                   [_site("NCT1", "New York"), _site("NCT9"), _site("NCT8"), _site("NCT9")])
    err = io.StringIO()
    _, ma = read_inputs(paths, stderr=err)
    assert ma == frozenset()
    lines = err.getvalue().splitlines()
    assert len(lines) == 1
    assert "warning" in lines[0] and " 3 " in lines[0] and "sites.csv" in lines[0]
    assert "NCT9" not in lines[0]


@pytest.mark.parametrize("which", ["studies", "sites"])
def test_missing_file(tmp_path, which):
    paths = _write(tmp_path, [_study("NCT1")])
    getattr(paths, which).unlink()
    msg = _error(paths)
    assert msg.startswith("%s.csv: cannot open" % which)


def test_unopenable_file(tmp_path):
    paths = _write(tmp_path, [_study("NCT1")])
    paths.sites.unlink()
    paths.sites.mkdir()   # opening a directory raises an OSError
    msg = _error(paths)
    assert msg.startswith("sites.csv: cannot open (")


@pytest.mark.parametrize("which", ["studies", "sites"])
def test_invalid_utf8(tmp_path, which):
    good = _table(STUDIES_HEADER, [_study("NCT1")])
    bad = b"\xff\xfe" + good
    paths = _write(tmp_path, [_study("NCT1")],
                   studies_bytes=bad if which == "studies" else None,
                   sites_bytes=bad if which == "sites" else None)
    assert _error(paths) == "%s.csv: not valid UTF-8" % which


@pytest.mark.parametrize("which", ["studies", "sites"])
def test_header_mismatch(tmp_path, which):
    header = STUDIES_HEADER if which == "studies" else SITES_HEADER
    wrong = (",".join(reversed(header)) + "\n").encode("utf-8")
    paths = _write(tmp_path, [_study("NCT1")],
                   studies_bytes=wrong if which == "studies" else None,
                   sites_bytes=wrong if which == "sites" else None)
    msg = _error(paths)
    assert msg.startswith("%s.csv: header row" % which)


def test_bad_list_cell_names_line_and_column(tmp_path):
    paths = _write(tmp_path, [_study("NCT1"), _study("NCT2", meshTerms='["secret", 3]')])
    msg = _error(paths)
    assert msg == "studies.csv: line 3 column meshTerms is not a JSON array of strings"
    assert "secret" not in msg


def test_zero_rows(tmp_path):
    paths = _write(tmp_path, [])
    assert _error(paths) == "studies.csv: has zero data rows"


def test_empty_nct_id(tmp_path):
    paths = _write(tmp_path, [_study("NCT1"), _study("", briefTitle="secret"), _study("")])
    assert _error(paths) == "studies.csv: line 3 has an empty nctId"


def test_duplicate_nct_id_reports_first_offending_line(tmp_path):
    paths = _write(tmp_path, [_study("NCT1"), _study("NCT2"), _study("NCT1", briefTitle="secret"),
                              _study("NCT2")])
    assert _error(paths) == "studies.csv: line 4 has duplicate nctId NCT1"


@pytest.mark.parametrize("value", ["True", "yes", " true", "FALSE"])
def test_bad_healthy_volunteers(tmp_path, value):
    paths = _write(tmp_path, [_study("NCT1"), _study("NCT2", healthyVolunteers=value)])
    msg = _error(paths)
    assert msg == "studies.csv: line 3 column healthyVolunteers is not true, false or empty"


def test_multiline_cell_reports_first_line_of_row(tmp_path):
    paths = _write(tmp_path, [_study("NCT1", briefTitle="a\nb"), _study("NCT1")])
    assert _error(paths) == "studies.csv: line 4 has duplicate nctId NCT1"
