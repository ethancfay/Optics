"""Scoring runs fully offline — a complete export makes zero network requests (task 11.2).

The Scoring & Export stage is a local, offline step (Req 1.4): it reads the
Spec 1 CSVs, `fetch_log.json`, and the Spec 2 `study_diseases.csv` and writes
the four contract JSON files, never touching the network. This test proves that
by running a full export through the public entry point
`pipeline.scoring.export.run(processed_dir, web_data_dir)` and asserting the
autouse `network_block` fixture (defined in `tests/conftest.py`, same harness
`tests/test_network_block.py` exercises) recorded no connection attempt.

The `network_block` fixture patches `urllib.request.urlopen`,
`socket.socket.connect`, and `socket.socket.connect_ex` so any network attempt
raises `NetworkBlocked` AND is appended to the yielded `attempts` list; the
fixture then fails the test at teardown if that list is non-empty. So an empty
`attempts` list after a successful run is a direct, explicit confirmation that
the export touched the network zero times.

The input fixture set is built exactly like the end-to-end integration test
(`tests/scoring/test_integration.py`), reusing its full-coverage `_build_inputs`
helper so the run exercises every component (readers, index, scoring,
decompose, findings, evidence, sources, PII_Check, atomic writer).
"""
from __future__ import annotations

from pathlib import Path

from pipeline.scoring.export import OUTPUT_FILE_NAMES, run

from tests.scoring.test_integration import _build_inputs


def test_full_export_makes_zero_network_requests(
    tmp_path: Path, network_block: list[str]
) -> None:
    processed_dir = tmp_path / "processed"
    processed_dir.mkdir()
    web_data_dir = tmp_path / "web" / "public" / "data"

    _build_inputs(processed_dir)

    # Run the entire Scoring & Export stage end to end (Req 1.4).
    exit_code = run(processed_dir, web_data_dir)

    # The run succeeds offline...
    assert exit_code == 0
    # ...and actually produced the four contract files, so "no network" is not
    # vacuously true because the run bailed out early.
    for name in OUTPUT_FILE_NAMES:
        assert (web_data_dir / name).is_file(), f"{name} should be written"

    # The core assertion (Req 1.4): the autouse network_block fixture recorded
    # zero connection attempts. urlopen / socket.connect / socket.connect_ex
    # are all patched, so this covers every network path the stage could take.
    assert network_block == []
