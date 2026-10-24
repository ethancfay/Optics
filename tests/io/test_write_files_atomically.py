"""Tests for atomic.write_files_atomically (condition-grouping design § Atomic write;
Req 9.11, 9.12, 14.11)."""
import os

import pytest

from pipeline.errors import PipelineError
from pipeline.io import atomic


def _dirs(tmp_path):
    processed = tmp_path / "pipeline" / "processed"
    burden = tmp_path / "burden_test"
    processed.mkdir(parents=True)
    burden.mkdir()
    return processed, burden


def _snapshot(*dirs):
    return {(d.name, p.name): p.read_bytes() for d in dirs for p in d.iterdir()}


def _no_temps(*dirs):
    return not any(p.name.startswith(".tmp-") for d in dirs for p in d.iterdir())


def test_writes_files_in_two_directories(tmp_path):
    """Req 9.11: every target gets its new bytes; existing files are replaced."""
    processed, burden = _dirs(tmp_path)
    (processed / "study_diseases.csv").write_bytes(b"old\n")
    atomic.write_files_atomically([
        (processed / "study_diseases.csv", b"new\n"),
        (burden / "precision_sample.csv", b"sample\n"),
    ])
    assert _snapshot(processed, burden) == {
        ("processed", "study_diseases.csv"): b"new\n",
        ("burden_test", "precision_sample.csv"): b"sample\n",
    }
    assert _no_temps(processed, burden)


def test_temp_write_failure_leaves_all_targets_untouched(tmp_path, monkeypatch):
    """Req 9.12: a write failure names the file and OS error type; no target changes."""
    processed, burden = _dirs(tmp_path)
    (processed / "study_diseases.csv").write_bytes(b"old sd\n")
    (burden / "precision_sample.csv").write_bytes(b"old ps\n")
    before = _snapshot(processed, burden)
    real = atomic._write_bytes
    calls = []

    def failing(path, data):
        calls.append(path)
        if len(calls) == 2:
            raise PermissionError(13, "Permission denied")
        real(path, data)

    monkeypatch.setattr(atomic, "_write_bytes", failing)
    with pytest.raises(PipelineError, match="precision_sample.csv") as excinfo:
        atomic.write_files_atomically([
            (processed / "study_diseases.csv", b"new sd\n"),
            (burden / "precision_sample.csv", b"new ps\n"),
        ])
    assert "PermissionError" in str(excinfo.value)
    assert _snapshot(processed, burden) == before
    assert _no_temps(processed, burden)


@pytest.mark.parametrize("first_existed", [True, False])
def test_second_replace_failure_restores_first_target(tmp_path, monkeypatch, first_existed):
    """Req 9.12: replace k fails -> targets 1..k-1 restored (or removed if absent)."""
    processed, burden = _dirs(tmp_path)
    first = processed / "study_diseases.csv"
    second = burden / "precision_sample.csv"
    if first_existed:
        first.write_bytes(b"old sd\n")
    second.write_bytes(b"old ps\n")
    before = _snapshot(processed, burden)
    real = os.replace

    def failing(src, dst):
        if os.fspath(dst) == os.fspath(second):
            raise OSError(28, "No space left on device")
        real(src, dst)

    monkeypatch.setattr(atomic.os, "replace", failing)
    with pytest.raises(PipelineError, match="precision_sample.csv") as excinfo:
        atomic.write_files_atomically([(first, b"new sd\n"), (second, b"new ps\n")])
    assert "OSError" in str(excinfo.value)
    assert _snapshot(processed, burden) == before
    assert first.exists() == first_existed
    assert _no_temps(processed, burden)
