"""Tests for pipeline/io/atomic.py (design § Atomic output; Req 7.1, 7.10, 12.1, 12.10)."""

import pytest

from pipeline.errors import PipelineError
from pipeline.io import atomic

CSVS = [("studies.csv", b"s\n"), ("sites.csv", b"t\n"), ("places_ma.csv", b"p\n")]


def _snapshot(directory):
    return {p.name: p.read_bytes() for p in directory.iterdir()} if directory.exists() else None


def test_writes_all_files_and_removes_staging(tmp_path):
    """Req 7.1, 12.1: three CSVs and fetch_log.json land in processed/, replacing old files."""
    processed = tmp_path / "pipeline" / "processed"
    processed.mkdir(parents=True)
    (processed / "studies.csv").write_bytes(b"old\n")
    atomic.write_outputs(tmp_path / "pipeline", processed, CSVS, b"{}\n")
    assert _snapshot(processed) == {
        "studies.csv": b"s\n", "sites.csv": b"t\n", "places_ma.csv": b"p\n", "fetch_log.json": b"{}\n",
    }
    assert not list((tmp_path / "pipeline").glob(".staging-*"))


def _failing_on(target, real):
    def write(path, data):
        if path.name == target:
            raise PermissionError(13, "Permission denied")
        real(path, data)
    return write


def test_csv_write_failure_names_file_and_leaves_processed_unchanged(tmp_path, monkeypatch):
    """Req 7.10: the error names the file; existing outputs stay byte-identical."""
    processed = tmp_path / "pipeline" / "processed"
    processed.mkdir(parents=True)
    (processed / "sites.csv").write_bytes(b"old sites\n")
    (processed / "fetch_log.json").write_bytes(b"old log\n")
    before = _snapshot(processed)
    monkeypatch.setattr(atomic, "_write_bytes", _failing_on("sites.csv", atomic._write_bytes))
    with pytest.raises(PipelineError, match="sites.csv") as excinfo:
        atomic.write_outputs(tmp_path / "pipeline", processed, CSVS, b"{}\n")
    assert "Permission denied" in str(excinfo.value)
    assert _snapshot(processed) == before
    assert not list((tmp_path / "pipeline").glob(".staging-*"))


def test_fetch_log_failure_names_file_and_keeps_old_log(tmp_path, monkeypatch):
    """Req 12.10: the error names fetch_log.json and the reason; the old log is kept."""
    processed = tmp_path / "pipeline" / "processed"
    processed.mkdir(parents=True)
    (processed / "fetch_log.json").write_bytes(b"old log\n")
    monkeypatch.setattr(atomic, "_write_bytes", _failing_on("fetch_log.json", atomic._write_bytes))
    with pytest.raises(PipelineError, match=r"fetch_log\.json \(PermissionError: Permission denied\)"):
        atomic.write_outputs(tmp_path / "pipeline", processed, CSVS, b"{}\n")
    assert (processed / "fetch_log.json").read_bytes() == b"old log\n"
    assert not list((tmp_path / "pipeline").glob(".staging-*"))
