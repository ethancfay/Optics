"""Term_Audit (condition-grouping design § Term_Audit; Req 14).

One-off development step: `python -m pipeline.mapping.term_audit`. Lists, per
Audit_Keyword and per list column of `pipeline/processed/studies.csv`, the 40
most frequent values containing the keyword, and writes them to
`.kiro/specs/condition-grouping/term_audit.md` with empty disposition cells.

The Mapping_Pipeline never imports this module (Req 14.10). It reads only
`studies.csv` and `term_audit.md`, sends no network request and writes only
`term_audit.md` (Req 14.11). Error messages name the file and the failed check,
never cell content (Req 14.12).
"""
from __future__ import annotations

import argparse
import hashlib
import os
import re
import sys
from dataclasses import dataclass
from pathlib import Path

from pipeline.errors import PipelineError
from pipeline.io.atomic import write_files_atomically
from pipeline.io.csv_reader import read_table

REPO_ROOT = Path(__file__).resolve().parent.parent.parent

AUDIT_KEYWORDS: tuple[tuple[str, str], ...] = (
    ("asthma", "CASTHMA"), ("cholesterol", "HIGHCHOL"), ("lipid", "HIGHCHOL"),
    ("LDL", "HIGHCHOL"), ("lipoprotein", "HIGHCHOL"), ("diabet", "DIABETES"))
AUDIT_COLUMNS = ("meshTerms", "ancestorTerms", "conditions")
TOP_N = 40

# The 18 Spec 1 `studies.csv` columns, in order (requirements § Input facts).
STUDIES_HEADER: tuple[str, ...] = (
    "nctId", "briefTitle", "overallStatus", "studyType", "phases", "healthyVolunteers",
    "minimumAge", "maximumAge", "stdAges", "conditions", "interventionTypes",
    "interventionNames", "meshTerms", "meshIds", "ancestorTerms", "ancestorIds",
    "lastUpdatePostDate", "source_url",
)

STUDIES_RELPATH = Path("pipeline", "processed", "studies.csv")
AUDIT_RELPATH = Path(".kiro", "specs", "condition-grouping", "term_audit.md")

TABLE_HEADER = "| rank | value | count | measureid | disposition | reason_or_note |"
TABLE_RULE = "|---|---|---|---|---|---|"

_UNESCAPED_PIPE = re.compile(r"(?<!\\)\|")


@dataclass(frozen=True)
class AuditTable:
    keyword: str
    measureid: str
    column: str
    entries: tuple[tuple[str, int], ...]   # (value as written, study count), in output order


def _normalized(text: str) -> str:
    """Normalized_Text: case-folded, whitespace runs collapsed, trimmed."""
    return " ".join(text.casefold().split())


def audit_tables(rows: list[dict]) -> list[AuditTable]:
    """Build every (Audit_Keyword, column) table from parsed `studies.csv` rows (Req 14.1-14.4)."""
    # Per column: value -> number of distinct studies whose list contains it.
    counts: dict[str, dict[str, int]] = {}
    for column in AUDIT_COLUMNS:
        column_counts: dict[str, int] = {}
        for row in rows:
            for value in set(row[column]):
                if _normalized(value):
                    column_counts[value] = column_counts.get(value, 0) + 1
        counts[column] = column_counts

    tables: list[AuditTable] = []
    for keyword, measureid in AUDIT_KEYWORDS:
        needle = keyword.casefold()
        for column in AUDIT_COLUMNS:
            matches = [(value, n) for value, n in counts[column].items()
                       if needle in value.casefold()]
            matches.sort(key=lambda item: (-item[1], item[0]))
            tables.append(AuditTable(keyword, measureid, column, tuple(matches[:TOP_N])))
    return tables


def _escape(value: str) -> str:
    return value.replace("|", "\\|")


def render(sha256_hex: str, row_count: int, tables: list[AuditTable]) -> bytes:
    """The exact `term_audit.md` bytes: UTF-8, no BOM, LF, no timestamp (Req 14.5)."""
    lines = [
        "# Term audit (condition-grouping, Requirement 14)",
        "",
        "- Source: pipeline/processed/studies.csv",
        "- SHA-256: %s" % sha256_hex,
        "- Data rows: %d" % row_count,
    ]
    for table in tables:
        lines += ["", "## %s / %s (%s)" % (table.keyword, table.column, table.measureid), ""]
        if not table.entries:
            lines.append("no values")
            continue
        lines += [TABLE_HEADER, TABLE_RULE]
        for rank, (value, count) in enumerate(table.entries, start=1):
            lines.append("| %d | %s | %d | %s |  |  |"
                         % (rank, _escape(value), count, table.measureid))
    return ("\n".join(lines) + "\n").encode("utf-8")


def filled_cells(existing_md: str) -> int:
    """Count disposition and reason/note cells holding non-whitespace text.

    Cells are split on unescaped `|`. The two cells are taken from the right
    end of each table row, so an escaped `|` in the value cell cannot shift them.
    """
    filled = 0
    for line in existing_md.splitlines():
        stripped = line.strip()
        if not stripped.startswith("|") or stripped == TABLE_HEADER \
                or stripped.startswith("|---"):
            continue
        cells = _UNESCAPED_PIPE.split(stripped)
        # A table row "| r | v | c | m | d | n |" splits into 8 parts with
        # empty first and last parts.
        if len(cells) < 8:
            continue
        filled += sum(1 for cell in cells[-3:-1] if cell.strip())
    return filled


def _read_studies(path: Path) -> tuple[bytes, list[dict]]:
    """Read `studies.csv`; return its bytes and parsed rows (Req 14.12)."""
    name = path.name
    try:
        data = path.read_bytes()
    except FileNotFoundError:
        raise PipelineError("%s: file is missing" % name) from None
    except OSError as exc:
        raise PipelineError("%s: file cannot be opened (%s)" % (name, type(exc).__name__)) from None
    try:
        data.decode("utf-8")
    except UnicodeDecodeError:
        raise PipelineError("%s: file is not valid UTF-8" % name) from None
    try:
        parsed = read_table(path, STUDIES_HEADER, set(AUDIT_COLUMNS))
        again = path.read_bytes()
    except FileNotFoundError:
        raise PipelineError("%s: file is missing" % name) from None
    except UnicodeDecodeError:
        raise PipelineError("%s: file is not valid UTF-8" % name) from None
    except OSError as exc:
        raise PipelineError("%s: file cannot be opened (%s)" % (name, type(exc).__name__)) from None
    # The digest must describe the bytes that were parsed.
    if again != data:
        raise PipelineError("%s: file changed while it was read" % name)
    return data, [row for _, row in parsed]


def _existing_filled(path: Path) -> int:
    try:
        text = path.read_bytes().decode("utf-8", errors="replace")
    except FileNotFoundError:
        return 0
    except OSError as exc:
        raise PipelineError("%s: file cannot be read (%s)" % (path.name, type(exc).__name__)) from None
    return filled_cells(text)


def main(argv: "list[str] | None" = None, root: Path = REPO_ROOT) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m pipeline.mapping.term_audit",
        description="List disease-related studies.csv values into term_audit.md.")
    parser.parse_args(argv)
    root = Path(root)
    studies_path = root / STUDIES_RELPATH
    audit_path = root / AUDIT_RELPATH
    try:
        filled = _existing_filled(audit_path)
        if filled:
            sys.stderr.write(
                "%s already has %d filled disposition or reason/note cells; "
                "left unchanged\n" % (audit_path.name, filled))
            return 1
        data, rows = _read_studies(studies_path)
        output = render(hashlib.sha256(data).hexdigest(), len(rows), audit_tables(rows))
        try:
            audit_path.parent.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            raise PipelineError("could not create the directory for %s (%s)"
                                % (audit_path.name, type(exc).__name__)) from None
        write_files_atomically([(audit_path, output)])
    except PipelineError as exc:
        sys.stderr.write("error: %s\n" % exc)
        return 1
    sys.stdout.write("wrote %s\n" % os.fspath(AUDIT_RELPATH))
    return 0


if __name__ == "__main__":
    sys.exit(main())
