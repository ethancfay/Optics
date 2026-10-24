"""CLI integration tests for `python -m pipeline.mapping` (condition-grouping task 5.7).

Covers Req 9.7, 9.10, 9.12, 10.6-10.9, 11.6-11.8, 12.2-12.5, 12.7, 12.9,
13.6-13.8 and 14.10. Every run uses a temporary repository root under
`tmp_path`, so the committed `pipeline/processed/` and `burden_test/` files are
never read or written. The network is blocked by `tests/conftest.py`; recall
runs use a stub client.
"""
import ast
import io
import json
import os
import subprocess
import sys
import urllib.parse
import uuid
from datetime import date
from pathlib import Path

import pytest

import pipeline.data.http_client as http_client
import pipeline.mapping.__main__ as cli
from pipeline.data.http_client import HttpStatusError
from pipeline.mapping import recall_checker
from pipeline.mapping.__main__ import REPO_ROOT, Paths, run
from pipeline.mapping.inputs import SITES_HEADER, STUDIES_HEADER
from tests.mapping.test_main_smoke import _site, _study, _table

TODAY = date(2025, 3, 4)
SENTINELS = {
    "study_diseases": b"sentinel study_diseases\n",
    "recall_check": b'{"sentinel": true}\n',
    "precision_sample": b"sentinel precision_sample\n",
}
# found_count per Recall_Query_Term for the default studies; a ctgov total equal
# to it gives ratio_found 1.0 (not flagged).
FOUND = {"Asthma": 2, "Diabetes": 1, "High Cholesterol": 1}


def _studies():
    return [
        _study("NCT00000001", ["Asthma"]),
        _study("NCT00000002", ["Type 2 Diabetes"]),
        _study("NCT00000003", ["Asthma"], maximumAge="12 Years"),
        _study("NCT00000004", ["Broken Leg"]),
        _study("NCT00000005", ["Hypercholesterolemia"]),
    ]


def _make_root(root, studies=None):
    processed = root / "pipeline" / "processed"
    processed.mkdir(parents=True)
    (root / "burden_test").mkdir()
    studies = _studies() if studies is None else studies
    (processed / "studies.csv").write_bytes(_table(STUDIES_HEADER, studies))
    (processed / "sites.csv").write_bytes(_table(SITES_HEADER, [_site(s["nctId"]) for s in studies]))
    return Paths(root)


def _seed_outputs(paths):
    paths.study_diseases.write_bytes(SENTINELS["study_diseases"])
    paths.recall_check.write_bytes(SENTINELS["recall_check"])
    paths.precision_sample.write_bytes(SENTINELS["precision_sample"])


def _outputs(paths):
    return {name: (getattr(paths, name).read_bytes() if getattr(paths, name).exists() else None)
            for name in SENTINELS}


def _temp_files(paths):
    return sorted(p.name for d in (paths.processed, paths.burden_test)
                  for p in d.iterdir() if p.name.startswith(".tmp-"))


class StubClient:
    """Returns {"totalCount": n} per Recall_Query_Term, or raises / returns raw bytes."""

    def __init__(self, totals=None):
        self.totals = dict(FOUND if totals is None else totals)
        self.urls = []

    def get(self, url):
        self.urls.append(url)
        term = urllib.parse.parse_qs(urllib.parse.urlsplit(url).query)["query.cond"][0]
        value = self.totals[term]
        if isinstance(value, BaseException):
            raise value
        if isinstance(value, bytes):
            return value
        return json.dumps({"totalCount": value, "studies": []}).encode("utf-8")


class ForbiddenClient:
    def get(self, url):
        pytest.fail("unexpected recall request: %s" % url)


def _run(paths, *argv, client=None):
    out, err = io.StringIO(), io.StringIO()
    code = run(list(argv), paths, client=client, clock=lambda: TODAY, stdout=out, stderr=err)
    return code, out.getvalue(), err.getvalue()


@pytest.fixture
def no_http_client(monkeypatch):
    """Fail the test if the real HTTP_Client is constructed."""
    def forbidden(*args, **kwargs):
        pytest.fail("HttpClient constructed")
    monkeypatch.setattr(http_client, "HttpClient", forbidden)


@pytest.fixture
def no_stages(monkeypatch):
    """Fail the test if the rules are loaded or the inputs are read."""
    def forbidden(*args, **kwargs):
        pytest.fail("a pipeline stage ran")
    monkeypatch.setattr(cli, "load_rules", forbidden)
    monkeypatch.setattr(cli, "read_inputs", forbidden)


# --- Usage (Req 12.3, 12.4) -------------------------------------------------

@pytest.mark.parametrize("argv", [["--bogus"], ["--off"], ["extra"], ["--offline", "x"],
                                  ["--offline=1"], ["--resample", "--verbose"]])
def test_usage_error_exits_2_before_any_io(tmp_path, capsys, no_stages, no_http_client, argv):
    root = tmp_path / "absent"
    with pytest.raises(SystemExit) as excinfo:
        run(argv, Paths(root), client=ForbiddenClient())
    assert excinfo.value.code == 2
    assert "usage: python -m pipeline.mapping" in capsys.readouterr().err
    assert not root.exists()


@pytest.mark.parametrize("argv", [["--offline", "--resample"], ["--resample", "--offline"]])
def test_both_options_accepted_in_either_order(tmp_path, no_http_client, argv):
    paths = _make_root(tmp_path)
    code, out, err = _run(paths, *argv, client=ForbiddenClient())
    assert code == 0, err
    assert paths.study_diseases.exists() and paths.precision_sample.exists()
    assert not paths.recall_check.exists()


# --- Config and input errors (Req 2.7, 2.9, 12.5) ---------------------------

def _rules_module(tmp_path, monkeypatch, source):
    pkg_dir = tmp_path / "rulespkg"
    pkg_dir.mkdir()
    name = "bad_rules_%s" % uuid.uuid4().hex
    (pkg_dir / (name + ".py")).write_text(source, encoding="utf-8")
    monkeypatch.syspath_prepend(str(pkg_dir))
    return name


def _guard_inputs(monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("inputs were read")
    monkeypatch.setattr(cli, "read_inputs", forbidden)


def test_config_error_exits_1_before_inputs_and_network(tmp_path, monkeypatch, no_http_client):
    module = _rules_module(tmp_path, monkeypatch,
                           'SAMPLE_SEED = -1\n'
                           'DISEASES = [{"measureid": "CASTHMA", "disease_label": "Asthma",\n'
                           '  "ancestor_only_status": "maybe", "recall_query_term": "Asthma",\n'
                           '  "include": ["asthma"], "exclude": [], "questionable": []}]\n')
    root = tmp_path / "repo"
    paths = _make_root(root)
    paths = Paths(root, rules_module=module)
    _seed_outputs(paths)
    _guard_inputs(monkeypatch)
    code, out, err = _run(paths, client=ForbiddenClient())
    assert code == 1 and out == ""
    lines = err.splitlines()
    assert len(lines) >= 2 and all(line.startswith("error: ") for line in lines)
    assert any(line.startswith("error: CASTHMA") for line in lines)
    assert any("Rules_Config" in line for line in lines)
    assert _outputs(paths) == SENTINELS


def test_missing_rules_module_exits_1_before_inputs_and_network(tmp_path, monkeypatch,
                                                                 no_http_client):
    root = tmp_path / "repo"
    _make_root(root)
    paths = Paths(root, rules_module="no_such_rules_%s" % uuid.uuid4().hex)
    _seed_outputs(paths)
    _guard_inputs(monkeypatch)
    code, out, err = _run(paths, client=ForbiddenClient())
    assert (code, out, err) == (1, "", "error: rules.py: file not found\n")
    assert _outputs(paths) == SENTINELS


def test_input_error_leaves_outputs_unchanged(tmp_path, no_http_client):
    paths = _make_root(tmp_path)
    _seed_outputs(paths)
    data = paths.studies.read_bytes()
    paths.studies.write_bytes(data.replace(b"nctId,briefTitle", b"nctId,title", 1))
    code, out, err = _run(paths, client=ForbiddenClient())
    assert code == 1 and out == ""
    assert err.startswith("error: studies.csv:") and err.count("\n") == 1
    assert _outputs(paths) == SENTINELS


def test_unreadable_existing_sample_exits_1_without_resample(tmp_path):
    paths = _make_root(tmp_path)
    _seed_outputs(paths)  # the sentinel sample has the wrong header (Req 11.8)
    code, _, err = _run(paths, "--offline")
    assert code == 1
    assert "precision_sample.csv" in err
    assert _outputs(paths) == SENTINELS


# --- Recall check (Req 10.6, 10.7, 13.6) -------------------------------------

@pytest.mark.parametrize("failing_term, failure", [
    ("Asthma", HttpStatusError(recall_checker.request_url("Asthma"), 503)),
    ("High Cholesterol", HttpStatusError(recall_checker.request_url("High Cholesterol"), 500)),
    ("Diabetes", b'{"studies": []}'),
    ("Asthma", b'{"totalCount": "12"}'),
    ("Asthma", b'{"totalCount": true}'),
    ("Asthma", b"not json"),
])
def test_recall_failure_exits_nonzero_and_leaves_outputs_unchanged(tmp_path, failing_term,
                                                                   failure):
    measureid = {"Asthma": "CASTHMA", "Diabetes": "DIABETES",
                 "High Cholesterol": "HIGHCHOL"}[failing_term]
    paths = _make_root(tmp_path)
    _seed_outputs(paths)
    totals = dict(FOUND)
    totals[failing_term] = failure
    code, out, err = _run(paths, "--resample", client=StubClient(totals))
    assert code != 0 and out == ""
    assert measureid in err
    assert recall_checker.request_url(failing_term) in err
    assert "studies" not in err.replace("/studies?", "")  # no response body content
    assert _outputs(paths) == SENTINELS
    assert _temp_files(paths) == []


def test_flagged_ratio_warns_and_exits_0(tmp_path):
    paths = _make_root(tmp_path)
    client = StubClient({"Asthma": 1000, "Diabetes": 1, "High Cholesterol": 0})
    code, out, err = _run(paths, client=client)
    assert code == 0, err
    assert "warning: recall CASTHMA: found_count=2 included_count=1 ctgov_count=1000 " \
           "ratio_found=0.002" in err
    assert "warning: recall HIGHCHOL: found_count=1 included_count=1 ctgov_count=0 " \
           "ratio_found=null" in err
    assert "DIABETES" not in "".join(l for l in err.splitlines() if l.startswith("warning: recall"))
    data = json.loads(paths.recall_check.read_bytes())
    assert data["check_date"] == "2025-03-04"
    assert [(d["measureid"], d["flagged"]) for d in data["diseases"]] == [
        ("CASTHMA", True), ("DIABETES", False), ("HIGHCHOL", True)]
    assert client.urls == [recall_checker.request_url(t)
                           for t in ("Asthma", "Diabetes", "High Cholesterol")]
    assert out.startswith("CASTHMA: included 1, questionable 0, excluded 1\n")


# --- PII and write failures (Req 9.9, 9.10, 9.12) ---------------------------

def test_pii_hit_leaves_all_outputs_unchanged(tmp_path):
    studies = _studies()
    studies[0]["briefTitle"] = "Contact jane.doe@example.org"
    paths = _make_root(tmp_path, studies)
    _seed_outputs(paths)
    code, out, err = _run(paths, "--resample", client=StubClient())
    assert code == 1 and out == ""
    assert err.endswith("\nerror: precision_sample.csv: column briefTitle: nctId NCT00000001\n")
    assert sum(line.startswith("error: ") for line in err.splitlines()) == 1
    assert "example.org" not in err
    assert _outputs(paths) == SENTINELS
    assert _temp_files(paths) == []


def test_replace_failure_on_second_target_rolls_back(tmp_path, monkeypatch):
    paths = _make_root(tmp_path)
    _seed_outputs(paths)
    real_replace = os.replace
    replaced = []

    def flaky_replace(src, dst):
        if Path(dst) == paths.recall_check:  # second target: study_diseases, recall, sample
            raise PermissionError(13, "Permission denied")
        replaced.append(Path(dst))
        return real_replace(src, dst)

    monkeypatch.setattr(os, "replace", flaky_replace)
    code, out, err = _run(paths, "--resample", client=StubClient())
    assert code == 1 and out == ""
    assert err.splitlines()[-1] == ("error: could not write recall_check.json "
                                    "(PermissionError: Permission denied)")
    assert sum(line.startswith("error: ") for line in err.splitlines()) == 1
    assert replaced[0] == paths.study_diseases  # the first target was replaced, then restored
    assert _outputs(paths) == SENTINELS
    assert _temp_files(paths) == []


# --- Offline, precision sample, determinism (Req 9.7, 10.8, 10.9, 11.6, 11.7, 13.8)

def test_offline_without_recall_file_creates_none(tmp_path, no_http_client):
    paths = _make_root(tmp_path)
    code, _, err = _run(paths, "--offline", client=ForbiddenClient())
    assert code == 0, err
    assert not paths.recall_check.exists()
    assert "notice: recall check skipped (--offline); no recall_check.json exists" in err
    assert "warning: recall" not in err


def test_offline_keeps_existing_recall_file(tmp_path, no_http_client):
    paths = _make_root(tmp_path)
    paths.recall_check.write_bytes(SENTINELS["recall_check"])
    mtime = paths.recall_check.stat().st_mtime_ns
    code, _, err = _run(paths, "--offline", client=ForbiddenClient())
    assert code == 0, err
    assert paths.recall_check.read_bytes() == SENTINELS["recall_check"]
    assert paths.recall_check.stat().st_mtime_ns == mtime
    assert "notice: recall" not in err
    assert paths.study_diseases.exists() and paths.precision_sample.exists()


def test_filled_correct_cell_kept_without_resample_and_replaced_with_resample(tmp_path):
    paths = _make_root(tmp_path)
    assert _run(paths, "--offline")[0] == 0
    fresh = paths.precision_sample.read_bytes()
    lines = fresh.decode("utf-8").splitlines()
    assert lines[1].endswith(",")  # empty `correct` cell
    lines[1] += "yes"
    filled = ("\n".join(lines) + "\n").encode("utf-8")
    paths.precision_sample.write_bytes(filled)

    code, out, err = _run(paths, "--offline")
    assert code == 0, err
    assert paths.precision_sample.read_bytes() == filled
    assert "notice: precision_sample.csv: kept unchanged, 1 filled correct cells" in err
    assert out.startswith("CASTHMA:")

    code, _, err = _run(paths, "--offline", "--resample")
    assert code == 0, err
    assert paths.precision_sample.read_bytes() == fresh
    assert "kept unchanged" not in err


@pytest.mark.parametrize("argv", [["--offline"], []])
def test_two_runs_give_identical_outputs(tmp_path, argv):
    paths = _make_root(tmp_path)
    if argv:
        paths.recall_check.write_bytes(SENTINELS["recall_check"])
    first = _run(paths, *argv, client=StubClient())
    assert first[0] == 0, first[2]
    outputs = _outputs(paths)
    assert all(v is not None for v in outputs.values())
    second = _run(paths, *argv, client=StubClient())
    assert second == first
    assert _outputs(paths) == outputs


def test_run_from_other_working_directory_uses_same_files(tmp_path, monkeypatch):
    here = _make_root(tmp_path / "a")
    assert _run(here, "--offline")[0] == 0
    elsewhere_root = tmp_path / "b"
    elsewhere = _make_root(elsewhere_root)
    unrelated = tmp_path / "unrelated"
    unrelated.mkdir()
    monkeypatch.chdir(unrelated)
    assert _run(elsewhere, "--offline")[0] == 0
    assert _outputs(elsewhere) == _outputs(here)
    assert list(unrelated.iterdir()) == []


def test_repo_root_is_absolute_and_independent_of_cwd(tmp_path):
    assert REPO_ROOT.is_absolute()
    assert (REPO_ROOT / "pipeline" / "mapping" / "__main__.py").is_file()
    assert Paths(REPO_ROOT).studies == REPO_ROOT / "pipeline" / "processed" / "studies.csv"
    code = ("import pipeline.mapping.__main__ as m, sys; "
            "sys.stdout.write(str(m.Paths(m.REPO_ROOT).study_diseases))")
    out = subprocess.run([sys.executable, "-c", code], cwd=tmp_path, check=True,
                         capture_output=True, text=True,
                         env={**os.environ, "PYTHONPATH": str(REPO_ROOT)}).stdout
    assert out == str(REPO_ROOT / "pipeline" / "processed" / "study_diseases.csv")


# --- Unexpected errors, imports, requirements (Req 12.5, 12.9, 14.10) ------

def test_unexpected_exception_prints_only_type_name(tmp_path, monkeypatch):
    paths = _make_root(tmp_path)
    _seed_outputs(paths)

    def boom(*args, **kwargs):
        raise KeyError("secret cell content")

    monkeypatch.setattr(cli, "group", boom)
    code, out, err = _run(paths, "--offline")
    assert (code, out, err) == (1, "", "error: unexpected KeyError\n")
    assert _outputs(paths) == SENTINELS


def test_run_does_not_import_term_audit(tmp_path, monkeypatch):
    monkeypatch.delitem(sys.modules, "pipeline.mapping.term_audit", raising=False)
    paths = _make_root(tmp_path)
    assert _run(paths, client=StubClient())[0] == 0
    assert "pipeline.mapping.term_audit" not in sys.modules


def _requirement_names(text):
    names = set()
    for line in text.splitlines():
        line = line.split("#", 1)[0].strip()
        if line:
            assert "==" in line, line
            names.add(line.split("==", 1)[0].strip().lower())
    return names


def test_requirements_gain_no_new_package():
    current = (REPO_ROOT / "requirements.txt").read_text(encoding="utf-8")
    assert _requirement_names(current) <= {"pytest", "hypothesis"}
    try:
        committed = subprocess.run(["git", "show", "HEAD:requirements.txt"], cwd=REPO_ROOT,
                                   capture_output=True, text=True, check=True).stdout
    except (OSError, subprocess.CalledProcessError):
        committed = None
    if committed is not None:
        assert _requirement_names(current) == _requirement_names(committed)


def test_mapping_modules_import_only_stdlib_and_pipeline():
    for path in sorted((REPO_ROOT / "pipeline" / "mapping").glob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                roots = [alias.name.split(".")[0] for alias in node.names]
            elif isinstance(node, ast.ImportFrom) and node.level == 0:
                roots = [node.module.split(".")[0]]
            else:
                continue
            for root in roots:
                assert root == "pipeline" or root in sys.stdlib_module_names, (path.name, root)
