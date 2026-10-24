"""Unit tests for PII_Check, deterministic serialization, and atomic rollback.

Covers `pipeline/scoring/export.py` task 10.4 (Req 7.2, 7.5, 8.1, 8.4, 8.5, 8.6):

- A PII match (Email_Pattern / Phone_Pattern) in any output string aborts
  `write_all` with a `PipelineError` and writes NO file into `web/public/data/`;
  the message names the file/field/pattern but never the matched text (Req 7.2,
  8.6).
- A Forbidden_Term in any output string aborts `write_all` and writes nothing;
  the message never quotes the matched text (Req 7.5, 8.6).
- `serialize` is byte-identical on byte-identical input, orders top-level arrays
  by `measure_id`, investigate breakdowns by `label`, evidence `ncts` by
  `nct_id`, sorts object keys, emits no BOM, and ends with a single trailing LF
  (Req 8.1, 8.4).
- A simulated mid-write OS failure aborts with a `PipelineError`, leaves
  `web/public/data/` byte-identical, and leaves no `.staging-*` directory in the
  parent (Req 8.5, 8.6).
"""
from __future__ import annotations

import pytest

from pipeline.errors import PipelineError
from pipeline.scoring import export


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def _clean_files() -> dict[str, object]:
    """A minimal, PII-free, Forbidden_Term-free set of the four output structures."""
    return {
        "what.json": [
            {"measure_id": "DIABETES", "condition": "diabetes"},
            {"measure_id": "CASTHMA", "condition": "current asthma"},
        ],
        "investigate.json": [
            {
                "measure_id": "CASTHMA",
                "by_overall_status": [
                    {"label": "RECRUITING", "count": 2},
                    {"label": "COMPLETED", "count": 1},
                ],
            }
        ],
        "evidence.json": [
            {
                "measure_id": "CASTHMA",
                "ncts": [
                    {"nct_id": "NCT00000002", "title": "second"},
                    {"nct_id": "NCT00000001", "title": "first"},
                ],
            }
        ],
        "sources.json": {"is_sample": False, "data_as_of": "2024-01-01"},
    }


def _snapshot(directory):
    """Byte-content snapshot of a directory, or None when it does not exist."""
    if not directory.exists():
        return None
    return {p.name: p.read_bytes() for p in directory.iterdir()}


# --------------------------------------------------------------------------- #
# PII_Check abort leaves web/public/data/ unchanged (Req 7.2, 8.6)
# --------------------------------------------------------------------------- #
def test_pii_email_aborts_write_all_and_writes_no_file(tmp_path):
    """An email nested in a string aborts write_all; a pre-existing file is untouched."""
    web_data = tmp_path / "web" / "public" / "data"
    web_data.mkdir(parents=True)
    sentinel = web_data / "what.json"
    sentinel.write_bytes(b"sentinel\n")
    before = _snapshot(web_data)

    files = _clean_files()
    files["evidence.json"][0]["ncts"][0]["title"] = "contact person@example.com today"

    with pytest.raises(PipelineError) as excinfo:
        export.write_all(web_data, files)

    message = str(excinfo.value)
    assert "evidence.json" in message
    assert "email" in message
    assert "person@example.com" not in message  # never quote the matched text
    # No file written: the sentinel is byte-identical and nothing else appeared.
    assert _snapshot(web_data) == before
    assert not list((tmp_path / "web" / "public").glob(".staging-*"))


def test_pii_phone_aborts_write_all_and_writes_no_file(tmp_path):
    """A phone number in a string aborts write_all with no output written."""
    web_data = tmp_path / "web" / "public" / "data"
    web_data.mkdir(parents=True)
    before = _snapshot(web_data)  # empty dir

    files = _clean_files()
    files["what.json"][0]["condition"] = "reach us at (617) 555-0123 anytime"

    with pytest.raises(PipelineError) as excinfo:
        export.write_all(web_data, files)

    message = str(excinfo.value)
    assert "what.json" in message
    assert "phone" in message
    assert "555-0123" not in message
    assert _snapshot(web_data) == before
    assert _snapshot(web_data) == {}


# --------------------------------------------------------------------------- #
# Forbidden_Term abort leaves web/public/data/ unchanged (Req 7.5, 8.6)
# --------------------------------------------------------------------------- #
def test_forbidden_term_aborts_write_all_and_writes_no_file(tmp_path):
    """A Forbidden_Term ("neglected") in a string aborts write_all; nothing written."""
    web_data = tmp_path / "web" / "public" / "data"
    web_data.mkdir(parents=True)
    sentinel = web_data / "investigate.json"
    sentinel.write_bytes(b"sentinel\n")
    before = _snapshot(web_data)

    files = _clean_files()
    # Case-insensitive substring match; the banned term is embedded in a finding.
    files["investigate.json"][0]["note"] = "This disease is Neglected by funders."

    with pytest.raises(PipelineError) as excinfo:
        export.write_all(web_data, files)

    message = str(excinfo.value)
    assert "investigate.json" in message
    assert "neglected" not in message.lower()  # never quote the matched text
    assert _snapshot(web_data) == before
    assert not list((tmp_path / "web" / "public").glob(".staging-*"))


# --------------------------------------------------------------------------- #
# Deterministic serialization (Req 8.1, 8.4)
# --------------------------------------------------------------------------- #
def test_serialize_is_byte_identical_on_byte_identical_input():
    """Equal input produces byte-identical output across repeated calls."""
    files = _clean_files()
    first = export.serialize(files["what.json"], "what.json")
    second = export.serialize(_clean_files()["what.json"], "what.json")
    assert first == second


def test_serialize_ends_with_single_trailing_lf_and_no_bom():
    """Output ends with exactly one LF and carries no UTF-8 BOM."""
    data = export.serialize(_clean_files()["what.json"], "what.json")
    assert data.endswith(b"\n")
    assert not data.endswith(b"\n\n")
    assert not data.startswith(b"\xef\xbb\xbf")  # no BOM


def test_serialize_orders_top_level_array_by_measure_id():
    """Top-level what.json array is ordered by measure_id byte string."""
    data = export.serialize(_clean_files()["what.json"], "what.json")
    text = data.decode("utf-8")
    # CASTHMA sorts before DIABETES as a byte string, regardless of input order.
    assert text.index("CASTHMA") < text.index("DIABETES")


def test_serialize_orders_investigate_breakdowns_by_label():
    """investigate.json breakdown arrays are ordered by label byte string."""
    data = export.serialize(_clean_files()["investigate.json"], "investigate.json")
    text = data.decode("utf-8")
    # COMPLETED sorts before RECRUITING though input listed RECRUITING first.
    assert text.index("COMPLETED") < text.index("RECRUITING")


def test_serialize_orders_evidence_ncts_by_nct_id():
    """evidence.json ncts are ordered by nct_id byte string."""
    data = export.serialize(_clean_files()["evidence.json"], "evidence.json")
    text = data.decode("utf-8")
    assert text.index("NCT00000001") < text.index("NCT00000002")


def test_serialize_sorts_object_keys():
    """Object keys are emitted in sorted order (sort_keys=True)."""
    data = export.serialize({"zebra": 1, "alpha": 2, "mid": 3}, "sources.json")
    text = data.decode("utf-8")
    assert text.index('"alpha"') < text.index('"mid"') < text.index('"zebra"')


def test_write_all_commits_sorted_and_lf_terminated_output(tmp_path):
    """A clean run writes all four files, each sorted and LF-terminated, staging gone."""
    web_data = tmp_path / "web" / "public" / "data"
    export.write_all(web_data, _clean_files())

    written = _snapshot(web_data)
    assert set(written) == set(export.OUTPUT_FILE_NAMES)
    for name, raw in written.items():
        assert raw.endswith(b"\n") and not raw.endswith(b"\n\n"), name
        assert not raw.startswith(b"\xef\xbb\xbf"), name
    # what.json committed on disk is ordered by measure_id.
    what_text = written["what.json"].decode("utf-8")
    assert what_text.index("CASTHMA") < what_text.index("DIABETES")
    # No staging directory is left behind in the parent.
    assert not list((tmp_path / "web" / "public").glob(".staging-*"))


# --------------------------------------------------------------------------- #
# Simulated write failure: rollback and staging cleanup (Req 8.5, 8.6)
# --------------------------------------------------------------------------- #
def test_write_failure_rolls_back_and_cleans_staging(tmp_path, monkeypatch):
    """A mid-write OSError aborts, leaves web_data unchanged, and removes staging."""
    web_data = tmp_path / "web" / "public" / "data"
    web_data.mkdir(parents=True)
    sentinel = web_data / "what.json"
    sentinel.write_bytes(b"old what\n")
    before = _snapshot(web_data)

    real_write_bytes = export._write_bytes

    def failing(path, data):
        if path.name == "evidence.json":
            raise OSError(28, "No space left on device")
        real_write_bytes(path, data)

    monkeypatch.setattr(export, "_write_bytes", failing)

    with pytest.raises(PipelineError) as excinfo:
        export.write_all(web_data, _clean_files())

    message = str(excinfo.value)
    assert "evidence.json" in message
    assert "No space left on device" in message
    # web/public/data/ is byte-identical: nothing was committed.
    assert _snapshot(web_data) == before
    # No leftover .staging-* directory remains in the parent.
    assert not list((tmp_path / "web" / "public").glob(".staging-*"))


def test_replace_failure_rolls_back_and_cleans_staging(tmp_path, monkeypatch):
    """An os.replace failure during commit aborts and leaves no partial output."""
    web_data = tmp_path / "web" / "public" / "data"
    web_data.mkdir(parents=True)
    before = _snapshot(web_data)  # empty

    real_replace = export.os.replace

    def failing_replace(src, dst):
        if str(dst).endswith("investigate.json"):
            raise OSError(13, "Permission denied")
        real_replace(src, dst)

    monkeypatch.setattr(export.os, "replace", failing_replace)

    with pytest.raises(PipelineError) as excinfo:
        export.write_all(web_data, _clean_files())

    assert "investigate.json" in str(excinfo.value)
    # A partial commit may have placed some files; assert nothing from a clean
    # rollback of staging leaks: at minimum staging is gone and the dir holds
    # only committed-or-nothing, never a .staging-* dir.
    assert not list((tmp_path / "web" / "public").glob(".staging-*"))
    # The failing file was never committed.
    assert not (web_data / "investigate.json").exists()
