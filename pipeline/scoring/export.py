"""PII_Check + deterministic serialization for the Scoring & Export stage.

Design § Component 8: `PII_Check` + `Atomic_JSON_Writer`
(`pipeline/scoring/export.py`); Req 7.1, 7.2, 7.4, 7.5, 8.1, 8.2, 8.3, 8.4.

This module orchestrates the final step of the stage. Task 10.1 provides the
two safety scans and the deterministic serializer; task 10.2 adds `write_all`
and the `python -m pipeline.scoring.export` entry point to this same file.

Two scans run over every string in the four assembled output structures before
any file is written:

1. `scan_for_pii` reuses `pipeline.patterns.PATTERNS` (the Email_Pattern and
   Phone_Pattern), the same regexes `pipeline.transform.pii_guard` applies to
   Spec 1 output. A match aborts the run with a `PipelineError` naming the file,
   the field path, and which pattern matched, never quoting the matched text
   (Req 7.1, 7.2).
2. `scan_for_forbidden_terms` is a case-insensitive substring scan for the
   banned claim language of `product.md` / `health-safety.md`. A match aborts
   with a `PipelineError` naming the file and field, never quoting the matched
   text (Req 7.4, 7.5).

`serialize(obj)` produces deterministic UTF-8 bytes (Req 8.1-8.4): top-level
arrays ordered by `measure_id` as a byte string, `investigate.json` breakdown
arrays ordered by `label`, `evidence.json` `ncts` ordered by `nct_id`, object
keys sorted, `ensure_ascii=False`, `indent=2`, no BOM, and a single trailing LF.

Error messages name only files, field paths, and pattern names, never record
content (Req 3.3-style, consistent with `pii_guard`).
"""
from __future__ import annotations

import json
from typing import Iterator

from pipeline.errors import PipelineError
from pipeline.patterns import PATTERNS

# Forbidden claim language (Req 7.4, 7.5; requirements § Forbidden_Term).
# Matched case-insensitively as a substring of any output string. The phrase
# variants cover "needs more trials/drugs" and the shorter "need more
# trials/drugs" wording a finding might otherwise produce.
FORBIDDEN_TERMS: tuple[str, ...] = (
    "neglected",
    "underfunded",
    "needs more trials",
    "needs more drugs",
    "need more trials",
    "need more drugs",
)

# The four output structures, keyed by their file name. Top-level value is a
# list for the three array files and a dict for sources.json.
_ARRAY_FILES: frozenset[str] = frozenset(
    {"what.json", "investigate.json", "evidence.json"}
)


def _sort_key(value: str) -> bytes:
    """Byte-string sort key (Req 8.1-8.3 use UTF-8 byte comparison)."""
    return value.encode("utf-8")


# --------------------------------------------------------------------------- #
# Recursive string walk (shared by both scans)
# --------------------------------------------------------------------------- #
def _walk_strings(value: object, path: str) -> Iterator[tuple[str, str]]:
    """Yield `(field_path, string)` for every string reachable from `value`.

    Nested arrays and objects are walked recursively. The field path names the
    JSON location (e.g. ``ncts[0].title``) so error messages can point at the
    field without quoting the matched text (Req 7.2, 7.5).
    """
    if isinstance(value, str):
        yield path, value
    elif isinstance(value, dict):
        for key in value:
            child = f"{path}.{key}" if path else str(key)
            yield from _walk_strings(value[key], child)
    elif isinstance(value, (list, tuple)):
        for index, element in enumerate(value):
            yield from _walk_strings(element, f"{path}[{index}]")
    # Numbers, bools, and None carry no scannable text.


# --------------------------------------------------------------------------- #
# PII_Check (Req 7.1, 7.2)
# --------------------------------------------------------------------------- #
def _matched_patterns(text: str) -> list[str]:
    """Names of the PATTERNS that match `text` (reuses pii_guard's approach)."""
    return [name for name, regex in PATTERNS if regex.search(text)]


def find_pii(files: "dict[str, object]") -> list[str]:
    """One `file: field: pattern` entry per PII match, in file then field order.

    `files` maps each output file name to its assembled structure. Files are
    scanned in sorted name order and, within a file, in the natural traversal
    order of `_walk_strings`, so the listing is deterministic.
    """
    entries: list[str] = []
    for file_name in sorted(files):
        for field_path, text in _walk_strings(files[file_name], ""):
            for pattern in _matched_patterns(text):
                entries.append(
                    "%s: field %s: %s" % (file_name, field_path, pattern)
                )
    return entries


def scan_for_pii(files: "dict[str, object]") -> None:
    """Raise if any output string matches the Email_Pattern or Phone_Pattern.

    The error names every (file, field, pattern) match and the total count, and
    never quotes the matched text (Req 7.2). On no match this returns silently.
    """
    entries = find_pii(files)
    if entries:
        lines = [
            "PII_Check: %d contact pattern match(es) found; no output written"
            % len(entries)
        ]
        lines.extend("  " + entry for entry in entries)
        raise PipelineError("\n".join(lines))


# --------------------------------------------------------------------------- #
# Forbidden_Term scan (Req 7.4, 7.5)
# --------------------------------------------------------------------------- #
def _matched_forbidden_terms(text: str) -> list[str]:
    """Forbidden terms that occur as a case-insensitive substring of `text`."""
    lowered = text.casefold()
    return [term for term in FORBIDDEN_TERMS if term in lowered]


def find_forbidden_terms(files: "dict[str, object]") -> list[str]:
    """One `file: field` entry per output string containing a Forbidden_Term.

    The matched term is never included in the entry (Req 7.5). Files are scanned
    in sorted name order for deterministic output. A single field is listed once
    even if it contains several forbidden terms.
    """
    entries: list[str] = []
    for file_name in sorted(files):
        for field_path, text in _walk_strings(files[file_name], ""):
            if _matched_forbidden_terms(text):
                entries.append("%s: field %s" % (file_name, field_path))
    return entries


def scan_for_forbidden_terms(files: "dict[str, object]") -> None:
    """Raise if any output string contains a Forbidden_Term (case-insensitive).

    The error names every (file, field) that matched and the total count, and
    never quotes the matched text (Req 7.5). On no match this returns silently.
    """
    entries = find_forbidden_terms(files)
    if entries:
        lines = [
            "Forbidden_Term scan: %d field(s) contain banned language; "
            "no output written" % len(entries)
        ]
        lines.extend("  " + entry for entry in entries)
        raise PipelineError("\n".join(lines))


# --------------------------------------------------------------------------- #
# Deterministic ordering (Req 8.1, 8.2, 8.3)
# --------------------------------------------------------------------------- #
def _order_investigate_entry(entry: "dict[str, object]") -> "dict[str, object]":
    """Return a copy of an investigate.json entry with breakdowns ordered by label."""
    ordered = dict(entry)
    for key in ("by_overall_status", "by_study_type", "by_intervention_type", "by_phase"):
        breakdown = entry.get(key)
        if isinstance(breakdown, list):
            ordered[key] = sorted(
                breakdown, key=lambda item: _sort_key(str(item.get("label", "")))
            )
    return ordered


def _order_evidence_entry(entry: "dict[str, object]") -> "dict[str, object]":
    """Return a copy of an evidence.json entry with `ncts` ordered by nct_id."""
    ordered = dict(entry)
    ncts = entry.get("ncts")
    if isinstance(ncts, list):
        ordered["ncts"] = sorted(
            ncts, key=lambda item: _sort_key(str(item.get("nct_id", "")))
        )
    return ordered


def order_output(file_name: str, obj: object) -> object:
    """Apply the deterministic ordering for `file_name` ahead of serialization.

    - `what.json` / `investigate.json` / `evidence.json`: order the top-level
      array by each entry's `measure_id` as a byte string (Req 8.1).
    - `investigate.json`: order each breakdown array by `label` (Req 8.2).
    - `evidence.json`: order each entry's `ncts` by `nct_id` (Req 8.3).
    - `sources.json`: a single object; key ordering is handled by `sort_keys`.

    Object key ordering is deferred to `json.dumps(..., sort_keys=True)`.
    """
    if file_name in _ARRAY_FILES and isinstance(obj, list):
        entries = list(obj)
        if file_name == "investigate.json":
            entries = [_order_investigate_entry(e) for e in entries]
        elif file_name == "evidence.json":
            entries = [_order_evidence_entry(e) for e in entries]
        return sorted(
            entries,
            key=lambda entry: _sort_key(str(entry.get("measure_id", ""))),
        )
    return obj


def serialize(obj: object, file_name: str | None = None) -> bytes:
    """Serialize `obj` to deterministic UTF-8 bytes (Req 8.1-8.4).

    When `file_name` is given, the structure is first reordered: top-level
    arrays by `measure_id`, `investigate.json` breakdowns by `label`, and
    `evidence.json` `ncts` by `nct_id`. Object keys are always emitted in sorted
    order. Non-ASCII characters are preserved (`ensure_ascii=False`), the output
    is indented with two spaces, UTF-8 encoded without a BOM, and ends with a
    single trailing LF newline.
    """
    prepared = order_output(file_name, obj) if file_name is not None else obj
    text = json.dumps(
        prepared,
        ensure_ascii=False,
        sort_keys=True,
        indent=2,
    )
    return (text + "\n").encode("utf-8")

# --------------------------------------------------------------------------- #
# Atomic write (Req 8.5, 8.6; mirrors pipeline/io/atomic.py)
# --------------------------------------------------------------------------- #
import os
import shutil
import sys
import tempfile
from pathlib import Path

# The four — and only four — contract files this stage produces. `where.json`
# and `ma_counties.geojson` (the Deferred_Files) are never written (Req 3.3).
OUTPUT_FILE_NAMES: tuple[str, ...] = (
    "what.json",
    "investigate.json",
    "evidence.json",
    "sources.json",
)

STAGING_PREFIX = ".staging-"


def _reason(exc: OSError) -> str:
    """OS error type and text for a message, never any record content (Req 3.3)."""
    text = getattr(exc, "strerror", None)
    return "%s: %s" % (type(exc).__name__, text) if text else type(exc).__name__


def _write_bytes(path: Path, data: bytes) -> None:
    """Write and fsync one staged file (mirrors atomic.py `_write_bytes`)."""
    with open(path, "wb") as fh:
        fh.write(data)
        fh.flush()
        os.fsync(fh.fileno())


def write_all(web_data_dir: "str | os.PathLike", files: "dict[str, object]") -> None:
    """Scan, serialize, then atomically commit the four contract files (Req 8.5, 8.6).

    `files` maps each of `OUTPUT_FILE_NAMES` to its assembled structure. The two
    safety scans run over every string in all four structures BEFORE any file is
    written: a PII_Check match (Req 7.1, 7.2) or a Forbidden_Term match (Req 7.4,
    7.5) raises a `PipelineError` and nothing is written. On a clean scan each
    file is serialized deterministically, staged with fsync in a sibling
    `.staging-*` directory, and moved into `web_data_dir` with `os.replace`, so a
    target file is never observed partially written (Req 8.5). The staging
    directory is always removed in a `finally` block, and any OS failure leaves
    `web_data_dir` unchanged (Req 8.6).
    """
    # 1. Safety scans over the assembled structures, before any I/O (Req 7.*).
    scan_for_pii(files)
    scan_for_forbidden_terms(files)

    # 2. Serialize all four files up front, so a serialization failure also
    #    leaves web_data_dir untouched.
    payloads = [(name, serialize(files[name], name)) for name in OUTPUT_FILE_NAMES]

    web_data_dir = Path(web_data_dir)
    parent = web_data_dir.parent
    staging: Path | None = None
    try:
        try:
            parent.mkdir(parents=True, exist_ok=True)
            staging = Path(tempfile.mkdtemp(dir=parent, prefix=STAGING_PREFIX))
        except OSError as exc:
            raise PipelineError(
                "could not create a staging directory in %s (%s)"
                % (parent, _reason(exc))
            ) from None

        # 3. Stage every file (fsync) before committing any (Req 8.5).
        for name, data in payloads:
            try:
                _write_bytes(staging / name, data)
            except OSError as exc:
                raise PipelineError(
                    "could not write %s (%s)" % (name, _reason(exc))
                ) from None

        try:
            web_data_dir.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            raise PipelineError(
                "could not create %s (%s)" % (web_data_dir, _reason(exc))
            ) from None

        # 4. Commit each file with a single atomic rename (Req 8.5).
        for name, _ in payloads:
            try:
                os.replace(staging / name, web_data_dir / name)
            except OSError as exc:
                raise PipelineError(
                    "could not write %s (%s)" % (name, _reason(exc))
                ) from None
    finally:
        # 5. Remove staging, on the failure path too (Req 8.6).
        if staging is not None:
            shutil.rmtree(staging, ignore_errors=True)


# --------------------------------------------------------------------------- #
# Entry point: python -m pipeline.scoring.export (Req 1.1-1.5, 4.10)
# --------------------------------------------------------------------------- #
# Import-light so the version check at module import of the readers/builders is
# never the first thing an old interpreter hits; the real version gate lives in
# `main` and runs before any input is read or any file is written (Req 1.3).

# Active disease measures, in the order the entry point iterates (Req 3.1). The
# final files are reordered by `measure_id` byte string during serialization, so
# this order only governs the stderr warnings and the sources prevalence_years.
ACTIVE_MEASURES: tuple[str, ...] = ("CASTHMA", "HIGHCHOL", "DIABETES")

# The full MA county set is exactly 14 (Req 4.3, 4.10).
EXPECTED_COUNTY_COUNT = 14

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
PROCESSED_DIR = REPO_ROOT / "pipeline" / "processed"
WEB_DATA_DIR = REPO_ROOT / "web" / "public" / "data"


def _county_count(places: "list[object]", measure_id: str) -> int:
    """Distinct MA counties present for a measure in places_ma.csv (by locationid)."""
    return len({row.locationid for row in places if row.measureid == measure_id})


def _measure_present(places: "list[object]", measure_id: str) -> bool:
    """Whether the measure appears at all in places_ma.csv (Req 4.9)."""
    return any(row.measureid == measure_id for row in places)


def build_outputs(
    studies: "list[object]",
    sites: "list[object]",
    places: "list[object]",
    diseases: "list[object]",
    fetch_log: "dict[str, object]",
    warn: "object" = None,
) -> "dict[str, object]":
    """Assemble the four contract structures from the loaded inputs.

    Iterates the active measures in `ACTIVE_MEASURES` order. For each measure it
    builds the `what.json` entry, the breakdowns, the rules-based findings, the
    `investigate.json` entry (carrying those findings), and the `evidence.json`
    entry (with `measure_present` from `places`). `sources.json` is built last
    from the `what.json` entries so `prevalence_years` matches them exactly. A
    measure whose county count != 14 is reported through `warn` (a callable
    taking one message string) without aborting the run (Req 4.10).
    """
    from pipeline.scoring.decompose import build_investigate_entry
    from pipeline.scoring.evidence import build_evidence_entry
    from pipeline.scoring.findings import generate_findings
    from pipeline.scoring.index import build_scopes
    from pipeline.scoring.scoring import build_what_entry
    from pipeline.scoring.sources import build_sources

    scopes = build_scopes(studies, sites, diseases)

    what: list[object] = []
    investigate: list[object] = []
    evidence: list[object] = []
    for measure_id in ACTIVE_MEASURES:
        scope = scopes[measure_id]

        if warn is not None:
            count = _county_count(places, measure_id)
            if count != EXPECTED_COUNTY_COUNT:
                warn(
                    "%s: found %d MA county/counties in places_ma.csv, expected %d"
                    % (measure_id, count, EXPECTED_COUNTY_COUNT)
                )

        what_entry = build_what_entry(scope, places, scope.condition)

        # Breakdowns first (no findings yet), then findings from the computed
        # numbers, then the entry carrying those findings (design Part B).
        breakdowns = build_investigate_entry(scope)
        findings = generate_findings(scope, what_entry, breakdowns)
        investigate_entry = build_investigate_entry(scope, findings)

        evidence_entry = build_evidence_entry(
            scope, scope.condition, _measure_present(places, measure_id)
        )

        what.append(what_entry)
        investigate.append(investigate_entry)
        evidence.append(evidence_entry)

    sources = build_sources(fetch_log, what)

    return {
        "what.json": what,
        "investigate.json": investigate,
        "evidence.json": evidence,
        "sources.json": sources,
    }


def run(
    processed_dir: "str | os.PathLike" = PROCESSED_DIR,
    web_data_dir: "str | os.PathLike" = WEB_DATA_DIR,
    study_diseases_dir: "str | os.PathLike | None" = None,
) -> int:
    """Load inputs, build the four files, and atomically write them (Req 1.1, 1.2).

    `study_diseases_dir`, when given, takes precedence over `processed_dir` for
    `study_diseases.csv` (the fixture directory; Req 2.1). Any `PipelineError`
    from the readers, the scans, or the writer is printed to stderr and the run
    exits non-zero leaving `web_data_dir` unchanged (Req 2.4, 2.5, 2.6, 3.7, 7.5,
    8.6). A measure whose county count != 14 only warns to stderr; the run still
    exits 0 (Req 4.10). Returns the process exit code.
    """
    from pipeline.scoring.readers import (
        load_fetch_log,
        load_places,
        load_sites,
        load_studies,
        load_study_diseases,
        resolve_study_diseases_path,
    )

    processed_dir = Path(processed_dir)

    def warn(message: str) -> None:
        sys.stderr.write("warning: %s\n" % message)

    try:
        studies = load_studies(processed_dir / "studies.csv")
        sites = load_sites(processed_dir / "sites.csv")
        places = load_places(processed_dir / "places_ma.csv")
        diseases = load_study_diseases(
            resolve_study_diseases_path(processed_dir, study_diseases_dir)
        )
        fetch_log = load_fetch_log(processed_dir / "fetch_log.json")

        files = build_outputs(studies, sites, places, diseases, fetch_log, warn)
        write_all(web_data_dir, files)
    except PipelineError as exc:
        sys.stderr.write("error: %s\n" % exc)
        return 1
    except Exception as exc:  # noqa: BLE001 - no traceback: it could carry record content
        sys.stderr.write("error: unexpected %s\n" % type(exc).__name__)
        return 1

    for name in OUTPUT_FILE_NAMES:
        sys.stdout.write("%s written\n" % name)
    return 0


def main() -> int:
    """Gate on Python >= 3.11 before any I/O, then run (Req 1.3)."""
    if sys.version_info < (3, 11):
        sys.stderr.write(
            "Python %d.%d.%d detected; minimum is 3.11\n" % sys.version_info[:3]
        )
        return 1
    return run()


if __name__ == "__main__":
    sys.exit(main())
