"""Smoke test for `python -m pipeline.mapping` (task 5.6).

Runs `run()` offline against a temporary repository root with the real
`rules.py`. Full CLI integration tests are in test_main.py (task 5.7).
"""
import io

from pipeline.io.csv_writer import encode_list_cell, quote_cell
from pipeline.mapping.__main__ import Paths, run
from pipeline.mapping.inputs import SITES_HEADER, STUDIES_HEADER

LIST_COLS = ("phases", "stdAges", "conditions", "interventionTypes", "interventionNames",
             "meshTerms", "meshIds", "ancestorTerms", "ancestorIds")


def _study(nct_id, conditions, **cells):
    row = {c: "" for c in STUDIES_HEADER}
    row.update({c: "[]" for c in LIST_COLS})
    row.update(nctId=nct_id, overallStatus="RECRUITING", healthyVolunteers="false",
               briefTitle="Title " + nct_id, conditions=encode_list_cell(conditions),
               source_url="https://clinicaltrials.gov/study/" + nct_id)
    row.update(cells)
    return row


def _site(nct_id):
    row = {c: "" for c in SITES_HEADER}
    row.update(nctId=nct_id, state="Massachusetts")
    return row


def _table(header, rows):
    lines = [",".join(header)] + [",".join(quote_cell(r[c]) for c in header) for r in rows]
    return ("\n".join(lines) + "\n").encode("utf-8")


def _root(tmp_path):
    processed = tmp_path / "pipeline" / "processed"
    processed.mkdir(parents=True)
    (tmp_path / "burden_test").mkdir()
    studies = [
        _study("NCT00000001", ["Asthma"]),
        _study("NCT00000002", ["Type 2 Diabetes"]),
        _study("NCT00000003", ["Asthma"], maximumAge="12 Years"),
        _study("NCT00000004", ["Broken Leg"]),
    ]
    (processed / "studies.csv").write_bytes(_table(STUDIES_HEADER, studies))
    sites = [_site(s["nctId"]) for s in studies]
    (processed / "sites.csv").write_bytes(_table(SITES_HEADER, sites))
    return Paths(tmp_path)


def _run(paths, *argv):
    out, err = io.StringIO(), io.StringIO()
    code = run(list(argv), paths, stdout=out, stderr=err)
    return code, out.getvalue(), err.getvalue()


def test_offline_run_writes_outputs_and_summary(tmp_path):
    paths = _root(tmp_path)
    code, out, err = _run(paths, "--offline")
    assert code == 0, err
    assert not paths.recall_check.exists()
    assert "no recall_check.json exists" in err

    lines = paths.study_diseases.read_bytes().decode("utf-8").splitlines()
    assert lines[0] == "nctId,measureid,disease_label,match_status,exclusion_reason,matched_on,matched_term"
    assert lines[1:] == [
        "NCT00000001,CASTHMA,Asthma,included,,condition_text,Asthma",
        "NCT00000002,DIABETES,Diabetes,included,,condition_text,Type 2 Diabetes",
        "NCT00000003,CASTHMA,Asthma,excluded,child_only,condition_text,Asthma",
    ]
    sample = paths.precision_sample.read_bytes().decode("utf-8").splitlines()
    assert [line.split(",")[:2] for line in sample[1:]] == [
        ["NCT00000001", "CASTHMA"], ["NCT00000002", "DIABETES"]]
    assert "CASTHMA: included 1, questionable 0, excluded 1\n  child_only: 1\n" in out
    assert "HIGHCHOL: included 0, questionable 0, excluded 0\n" in out


def test_offline_rerun_is_byte_identical_and_keeps_recall_file(tmp_path):
    paths = _root(tmp_path)
    paths.recall_check.write_bytes(b'{"keep": true}\n')
    assert _run(paths, "--offline")[0] == 0
    first = (paths.study_diseases.read_bytes(), paths.precision_sample.read_bytes())
    mtimes = (paths.study_diseases.stat().st_mtime_ns, paths.precision_sample.stat().st_mtime_ns)
    code, _, err = _run(paths, "--resample", "--offline")
    assert code == 0, err
    assert (paths.study_diseases.read_bytes(), paths.precision_sample.read_bytes()) == first
    # Unchanged content is not rewritten.
    assert (paths.study_diseases.stat().st_mtime_ns,
            paths.precision_sample.stat().st_mtime_ns) == mtimes
    assert paths.recall_check.read_bytes() == b'{"keep": true}\n'
    assert "no recall_check.json exists" not in err


def test_missing_input_exits_1_without_traceback(tmp_path):
    paths = _root(tmp_path)
    paths.sites.unlink()
    code, out, err = _run(paths, "--offline")
    assert code == 1 and out == ""
    assert err == "error: sites.csv: cannot open (file is missing)\n"
    assert not paths.study_diseases.exists()
