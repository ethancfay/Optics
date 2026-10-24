"""Atomic output (design § Atomic output; Req 7.1, 7.10, 8.2, 9.6, 12.1, 12.9, 12.10).

`write_outputs` is called only after the transformers, the PII_Guard and the
Sanity_Checker have all finished, so every earlier failure leaves
`pipeline/processed/` untouched.

1. Create a staging directory `pipeline/.staging-*` (same filesystem as
   `processed/`, outside it).
2. Write and fsync the three CSVs into staging. A failure names the file, and
   `processed/` is untouched (Req 7.10).
3. Move each CSV into `processed/` with `os.replace` (Req 7.1).
4. Write `fetch_log.json` to staging, then move it with `os.replace`
   (Req 12.1). A failure names `fetch_log.json` and the reason (Req 12.10).
5. Remove the staging directory, in a `finally` block on failure too.

Error messages name only files and the OS error type and text, never content
(Req 3.3).
"""
from __future__ import annotations

import os
import shutil
import tempfile
from pathlib import Path

from pipeline.errors import PipelineError

FETCH_LOG_NAME = "fetch_log.json"
STAGING_PREFIX = ".staging-"


def _reason(exc: OSError) -> str:
    text = getattr(exc, "strerror", None)
    return "%s: %s" % (type(exc).__name__, text) if text else type(exc).__name__


def _write_bytes(path: Path, data: bytes) -> None:
    """Write and fsync one staged file. Tests patch this to simulate disk errors."""
    with open(path, "wb") as fh:
        fh.write(data)
        fh.flush()
        os.fsync(fh.fileno())


def _stage(staging: Path, name: str, data: bytes) -> None:
    try:
        _write_bytes(staging / name, data)
    except OSError as exc:
        raise PipelineError("could not write %s (%s)" % (name, _reason(exc))) from None


def _commit(staging: Path, processed: Path, name: str) -> None:
    try:
        os.replace(staging / name, processed / name)
    except OSError as exc:
        raise PipelineError("could not write %s (%s)" % (name, _reason(exc))) from None


def write_outputs(pipeline_dir: Path, processed_dir: Path,
                  csv_files: "list[tuple[str, bytes]]", fetch_log: bytes) -> None:
    """Stage and commit the CSVs, then stage and commit fetch_log.json."""
    pipeline_dir = Path(pipeline_dir)
    processed_dir = Path(processed_dir)
    staging: Path | None = None
    try:
        try:
            pipeline_dir.mkdir(parents=True, exist_ok=True)
            staging = Path(tempfile.mkdtemp(dir=pipeline_dir, prefix=STAGING_PREFIX))
        except OSError as exc:
            raise PipelineError(
                "could not create a staging directory in %s (%s)" % (pipeline_dir, _reason(exc))
            ) from None

        for name, data in csv_files:
            _stage(staging, name, data)
        try:
            processed_dir.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            raise PipelineError(
                "could not create %s (%s)" % (processed_dir, _reason(exc))
            ) from None
        for name, _ in csv_files:
            _commit(staging, processed_dir, name)

        _stage(staging, FETCH_LOG_NAME, fetch_log)
        _commit(staging, processed_dir, FETCH_LOG_NAME)
    finally:
        if staging is not None:
            shutil.rmtree(staging, ignore_errors=True)
