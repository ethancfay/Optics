"""PII_Guard (design § PII_Guard; Req 8.1, 8.2, 8.4, 8.5).

The guard runs on EncodedTables, so it checks the exact cell strings the
CSV_Writer will write (Req 8.1). For list columns it also checks every
decoded element. It never changes a row (Req 8.5).

On any match it raises one PipelineError that states the total match count
and lists every match by file, row identifier, field and pattern. The
matched text is never included (Req 8.4, 3.3).
"""
from __future__ import annotations

import json
import re

from pipeline.errors import PipelineError
from pipeline.io.csv_writer import LIST_COLUMNS, EncodedTable

EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
# The (?<![\d.]) lookbehind stops the decimal part of a long coordinate such
# as -71.8123456789 from matching (design § PII_Guard).
PHONE = re.compile(
    r"(?<![\d.])(?:\+?1[ .-]?)?(?:\(\d{3}\)|\d{3})[ .-]?\d{3}[ .-]?\d{4}(?!\d)"
)
PATTERNS = (("email", EMAIL), ("phone", PHONE))

# Table order used when listing matches.
TABLE_ORDER = ("studies", "sites", "places")


def _candidates(cell: str, is_list: bool) -> list[str]:
    """The encoded cell, plus each decoded element for list columns (Req 8.1)."""
    values = [cell]
    if is_list:
        try:
            decoded = json.loads(cell)
        except ValueError:
            decoded = None
        if isinstance(decoded, list):
            values.extend(str(e) for e in decoded)
    return values


def _matched_patterns(cell: str, is_list: bool) -> list[str]:
    values = _candidates(cell, is_list)
    return [name for name, regex in PATTERNS if any(regex.search(v) for v in values)]


def _is_clean(value: str) -> bool:
    return not any(regex.search(value) for _, regex in PATTERNS)


def _row_identifier(table: EncodedTable, index: int, cells: list[str]) -> str:
    """Req 8.4 row identifier. An identifier cell that itself matches a pattern
    is replaced by a placeholder, so the message never carries matched text."""
    by_name = dict(zip(table.header, cells))

    def ident(name: str) -> str:
        value = by_name.get(name, "")
        return "%s=%s" % (name, value) if _is_clean(value) else "%s=<redacted>" % name

    if table.kind == "studies":
        return ident("nctId")
    if table.kind == "sites":
        return "%s, row %d" % (ident("nctId"), index + 1)
    return "%s, %s" % (ident("locationname"), ident("measureid"))


def find_matches(tables: dict[str, EncodedTable]) -> list[str]:
    """One entry per (file, row, field, pattern) that matched, in table, row and column order."""
    entries: list[str] = []
    ordered = [k for k in TABLE_ORDER if k in tables] + sorted(k for k in tables if k not in TABLE_ORDER)
    for key in ordered:
        table = tables[key]
        list_columns = LIST_COLUMNS.get(table.kind, frozenset())
        for index, cells in enumerate(table.rows):
            for name, cell in zip(table.header, cells):
                for pattern in _matched_patterns(cell, name in list_columns):
                    entries.append("%s: %s: field %s: %s" % (
                        table.file_name, _row_identifier(table, index, cells), name, pattern))
    return entries


def check(tables: dict[str, EncodedTable]) -> None:
    """Raise PipelineError listing every Email_Pattern / Phone_Pattern match (Req 8.2, 8.4)."""
    entries = find_matches(tables)
    if entries:
        lines = ["PII_Guard: %d contact pattern match(es) found; no output written" % len(entries)]
        lines.extend("  " + entry for entry in entries)
        raise PipelineError("\n".join(lines))
