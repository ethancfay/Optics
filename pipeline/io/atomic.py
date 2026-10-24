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


TMP_PREFIX = ".tmp-"


def _write_error(target: Path, exc: OSError) -> PipelineError:
    return PipelineError("could not write %s (%s)" % (target.name, _reason(exc)))


def _make_temp(target: Path, data: bytes, temps: "list[Path]") -> Path:
    """Create a temp file next to `target` (tracked in `temps` for cleanup),
    then write and fsync `data` into it."""
    fd, name = tempfile.mkstemp(dir=target.parent, prefix=TMP_PREFIX)
    os.close(fd)
    temp = Path(name)
    temps.append(temp)
    _write_bytes(temp, data)
    return temp


def _restore(target: Path, original: "bytes | None", temps: "list[Path]") -> None:
    """Best-effort rollback of one already replaced target."""
    try:
        if original is None:
            target.unlink()
        else:
            os.replace(_make_temp(target, original, temps), target)
    except OSError:
        pass


def write_files_atomically(files: "list[tuple[Path, bytes]]") -> None:
    """Write several files, possibly in different directories, all or nothing
    (condition-grouping design § Atomic write; Req 9.11, 9.12, 14.11).

    1. Write and fsync a temp file per target in the target's own directory.
       A failure here leaves every target untouched.
    2. Save the original bytes of each target (None if absent).
    3. `os.replace` each temp onto its target in list order. If replace k
       fails, targets 1..k-1 are restored (or deleted if they were absent).
    4. Remove leftover temp files in `finally`.
    """
    targets = [Path(target) for target, _ in files]
    temps: "list[Path]" = []
    try:
        staged: "list[Path]" = []
        for target, (_, data) in zip(targets, files):
            try:
                staged.append(_make_temp(target, data, temps))
            except OSError as exc:
                raise _write_error(target, exc) from None

        originals: "list[bytes | None]" = []
        for target in targets:
            try:
                originals.append(target.read_bytes())
            except FileNotFoundError:
                originals.append(None)
            except OSError as exc:
                raise _write_error(target, exc) from None

        for k, (target, temp) in enumerate(zip(targets, staged)):
            try:
                os.replace(temp, target)
            except OSError as exc:
                for done in range(k):
                    _restore(targets[done], originals[done], temps)
                raise _write_error(target, exc) from None
    finally:
        for temp in temps:
            try:
                temp.unlink()
            except OSError:
                pass
