"""Tests for pipeline/__main__.py: version check (Req 14.2), CLI and error handling (Req 14.1, 14.8)."""

import json
import subprocess
import sys
from pathlib import Path

import pytest

import pipeline.__main__ as main_mod
from pipeline.errors import PipelineError

MAIN_PATH = Path(main_mod.__file__)
REPO_ROOT = MAIN_PATH.parent.parent

# Runs pipeline/__main__.py as __main__ in a fresh interpreter with a faked
# sys.version_info. The source is compiled before an audit hook is installed;
# the hook then records every file, directory, process and network event, so
# the parent test can assert the rejection path did no I/O.
_REJECT_PROBE = r"""
import sys, json
src_path, version = sys.argv[1], tuple(json.loads(sys.argv[2]))
with open(src_path, encoding="utf-8") as fh:
    code = compile(fh.read(), src_path, "exec")
events = []
IO_PREFIXES = ("open", "os.", "shutil.", "socket.", "urllib.", "http.", "subprocess.", "import")
def hook(event, args):
    if event.startswith(IO_PREFIXES):
        events.append(event)
sys.addaudithook(hook)
sys.version_info = version
exit_code = None
try:
    exec(code, {"__name__": "__main__", "__file__": src_path})
except SystemExit as exc:
    exit_code = exc.code
sys.__stdout__.write(json.dumps({
    "exit_code": exit_code,
    "events": events,
    "pipeline_modules": sorted(m for m in sys.modules if m.startswith("pipeline")),
}))
"""


def _run_reject_probe(version):
    proc = subprocess.run(
        [sys.executable, "-c", _REJECT_PROBE, str(MAIN_PATH), json.dumps(list(version))],
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
        timeout=60,
    )
    return proc, json.loads(proc.stdout)


@pytest.mark.parametrize("version", [(3, 10, 12, "final", 0), (3, 10, 0, "final", 0), (3, 8, 18, "final", 0)])
def test_version_check_rejects_old_python_without_io(version):
    """Req 14.2: < 3.11 exits non-zero, names both versions, and does no file/network I/O."""
    proc, result = _run_reject_probe(version)
    assert result["exit_code"] == 1
    expected = "Python %d.%d.%d detected; minimum is 3.11\n" % version[:3]
    assert proc.stderr == expected
    assert result["events"] == []
    assert result["pipeline_modules"] == []


@pytest.mark.parametrize(
    "version",
    [(3, 11, 0, "final", 0), (3, 12, 5, "final", 0), (3, 14, 0, "final", 0), (4, 0, 0, "final", 0)],
)
def test_version_check_accepts_311_and_newer(version, monkeypatch, capsys):
    """Req 14.2: 3.11 and every newer version pass the check."""
    monkeypatch.setattr(sys, "version_info", version)
    code = compile(MAIN_PATH.read_text(encoding="utf-8"), str(MAIN_PATH), "exec")
    namespace = {"__name__": "version_probe", "__file__": str(MAIN_PATH)}
    exec(code, namespace)  # raises SystemExit if the check rejects
    assert "run" in namespace
    assert capsys.readouterr().err == ""


def test_main_module_parses_with_old_grammar():
    """Req 14.2: the version check must be reachable on old Pythons, so the file parses under 3.8 grammar."""
    import ast

    ast.parse(MAIN_PATH.read_text(encoding="utf-8"), feature_version=(3, 8))
    assert (REPO_ROOT / "pipeline" / "__init__.py").read_text(encoding="utf-8") == ""


def _paths(tmp_path):
    return main_mod.Paths(tmp_path)


def test_pipeline_error_goes_to_stderr_with_exit_1(monkeypatch, capsys, tmp_path):
    """Req 14.8: a defined error prints its message to stderr, exits 1, and prints no summary."""

    def fail(args, paths, client):
        raise PipelineError("page 3 of https://clinicaltrials.gov/api/v2/studies failed")

    monkeypatch.setattr(main_mod, "_run_stages", fail)
    assert main_mod.run([], _paths(tmp_path), None) == 1
    out, err = capsys.readouterr()
    assert out == ""
    assert "page 3 of https://clinicaltrials.gov/api/v2/studies failed" in err


def test_unexpected_exception_prints_only_type_name(monkeypatch, capsys, tmp_path):
    """Design § Error model: unexpected errors print only the type name, no message or traceback."""

    def fail(args, paths, client):
        raise KeyError("secret-record-content")

    monkeypatch.setattr(main_mod, "_run_stages", fail)
    assert main_mod.run([], _paths(tmp_path), None) == 1
    out, err = capsys.readouterr()
    assert out == ""
    assert "KeyError" in err
    assert "secret-record-content" not in err
    assert "Traceback" not in err


def test_offline_flag_is_parsed(monkeypatch, tmp_path):
    """Req 14.1: the single command accepts --offline and passes paths and client through."""
    seen = {}

    def record(args, paths, client):
        seen.update(offline=args.offline, paths=paths, client=client)

    monkeypatch.setattr(main_mod, "_run_stages", record)
    sentinel = object()
    assert main_mod.run(["--offline"], _paths(tmp_path), sentinel) == 0
    assert seen == {"offline": True, "paths": _paths(tmp_path), "client": sentinel}
    assert main_mod.run([], _paths(tmp_path), None) == 0
    assert seen["offline"] is False


def test_unknown_argument_exits_2(tmp_path):
    """Design § Error model: argument errors use the argparse default exit code 2."""
    with pytest.raises(SystemExit) as excinfo:
        main_mod.run(["--bogus"], _paths(tmp_path), None)
    assert excinfo.value.code == 2


def test_paths_layout(tmp_path):
    paths = main_mod.Paths(tmp_path)
    assert paths.raw == tmp_path / "pipeline" / "raw"
    assert paths.processed == tmp_path / "pipeline" / "processed"
