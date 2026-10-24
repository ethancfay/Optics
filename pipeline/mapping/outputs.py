"""Output encoding for the Mapping_Pipeline (design § Outputs and PII_Guard; Req 9).

Tables are built as `csv_writer.EncodedTable` values and turned into bytes only
by `csv_writer.serialize`, so they follow the Spec 1 byte conventions exactly
(Req 9.3, 9.4). Only `serialize` is used; `EncodedTable.file_name` looks up
Spec 1 kinds and is never called for these tables.

PII_Guard API for the CLI (Req 9.9, 9.10, 12.8). Run it on the final content of
every output before `write_files_atomically`:

    pii_check("study_diseases.csv", study_table)            # id column nctId
    pii_check("precision_sample.csv", sample_table)         # also decodes `conditions`
    pii_check("recall_check.json", recall_bytes)            # bytes, str or parsed obj

`pii_check` dispatches on the value type to `pii_check_table` or
`pii_check_json`. On the first Email_Pattern or Phone_Pattern match it raises
`PipelineError` naming only the file, the column (or JSON key) and the nctId
(or measureid); no cell content is ever included.

`summary(rules, rows)` returns the stdout summary text (Req 12.6), ending in a
newline, ready for `sys.stdout.write`.
"""
from __future__ import annotations

import json
from collections import Counter
from typing import Iterable

from pipeline.errors import PipelineError
from pipeline.io.csv_writer import EncodedTable
from pipeline.patterns import PATTERNS

STUDY_DISEASES_HEADER: tuple[str, ...] = (
    "nctId", "measureid", "disease_label", "match_status",
    "exclusion_reason", "matched_on", "matched_term",
)


def _cell(value: object) -> str:
    return "" if value is None else str(value)


def encode_study_diseases(rows: Iterable[object]) -> EncodedTable:
    """Encode Study_Disease_Rows sorted by (nctId, measureid) (Req 9.1, 9.5).

    Accepts any objects with the seven header attributes. Plain str comparison
    is Unicode code point order. The remaining columns break ties so equal keys
    still give byte-identical output.
    """
    encoded = [
        [_cell(getattr(row, name)) for name in STUDY_DISEASES_HEADER]
        for row in rows
    ]
    encoded.sort()
    return EncodedTable(kind="study_diseases", header=STUDY_DISEASES_HEADER, rows=encoded)


# Columns whose cells hold a JSON array of strings, per table kind. The decoded
# elements are checked too, so a JSON escape (e.g. "\u0040" for "@") cannot hide a match.
JSON_LIST_COLUMNS: dict[str, tuple[str, ...]] = {"precision_sample": ("conditions",)}


def _has_pii(text: str) -> bool:
    return any(pattern.search(text) for _, pattern in PATTERNS)


def _decoded_strings(cell: str) -> list[str]:
    """String elements of a JSON array cell; [] when the cell is not one."""
    try:
        value = json.loads(cell)
    except ValueError:
        return []
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, str)]


def pii_check_table(file_name: str, table: EncodedTable, id_column: str = "nctId",
                    json_list_columns: Iterable[str] = ()) -> None:
    """Raise PipelineError("<file>: column <c>: nctId <id>") on the first PII cell (Req 9.9).

    Checks every header and data cell, plus the decoded string elements of any
    `json_list_columns` cell. `id_column` names the identifier column whose
    value is reported; the identifier is assumed PII-free (an nctId).
    """
    list_cols = frozenset(json_list_columns)
    for name in table.header:
        if _has_pii(name):
            raise PipelineError("%s: header" % file_name)
    id_index = table.header.index(id_column)
    for cells in table.rows:
        for name, cell in zip(table.header, cells):
            hit = _has_pii(cell) or (
                name in list_cols and any(_has_pii(x) for x in _decoded_strings(cell)))
            if hit:
                raise PipelineError("%s: column %s: %s %s"
                                    % (file_name, name, id_column, cells[id_index]))


def _walk_json(file_name: str, value: object, key: str, measureid: str | None) -> None:
    if isinstance(value, str):
        if _has_pii(value):
            where = "%s: key %s" % (file_name, key)
            if measureid is not None:
                where += ": measureid %s" % measureid
            raise PipelineError(where)
    elif isinstance(value, dict):
        mid = value.get("measureid")
        if isinstance(mid, str) and not _has_pii(mid):
            measureid = mid
        for k, v in value.items():
            _walk_json(file_name, v, str(k), measureid)
    elif isinstance(value, list):
        for item in value:
            _walk_json(file_name, item, key, measureid)


def pii_check_json(file_name: str, obj: object) -> None:
    """Check every string value of a JSON document (Req 9.9).

    `obj` is the parsed document, or its `bytes`/`str` text. The error names
    the innermost key and, inside an object with a `measureid`, that measureid:
    `PipelineError("<file>: key <k>: measureid <m>")`.
    """
    if isinstance(obj, (bytes, bytearray)):
        obj = obj.decode("utf-8")
    if isinstance(obj, str):
        obj = json.loads(obj)
    _walk_json(file_name, obj, "", None)


def pii_check(file_name: str, table_or_json: object, id_key: str = "nctId") -> None:
    """PII_Guard entry point: dispatch to `pii_check_table` or `pii_check_json`.

    For an EncodedTable, `id_key` is the reported id column and the
    JSON-list columns come from `JSON_LIST_COLUMNS[table.kind]`. For JSON
    input `id_key` is unused; the measureid is reported.
    """
    if isinstance(table_or_json, EncodedTable):
        pii_check_table(file_name, table_or_json, id_key,
                        JSON_LIST_COLUMNS.get(table_or_json.kind, ()))
    else:
        pii_check_json(file_name, table_or_json)


STATUSES: tuple[str, ...] = ("included", "questionable", "excluded")


def summary(rules, rows: Iterable[object]) -> str:
    """Stdout summary, one block per disease sorted by measureid (Req 12.6).

    Each block: "<measureid>: included N, questionable N, excluded N", then one
    "  <reason>: N" line per non-empty exclusion_reason (any status), sorted by
    reason code in Unicode code point order. Returns text ending in a newline.
    """
    status_counts: dict[str, Counter] = {}
    reason_counts: dict[str, Counter] = {}
    for row in rows:
        status_counts.setdefault(row.measureid, Counter())[row.match_status] += 1
        if row.exclusion_reason:
            reason_counts.setdefault(row.measureid, Counter())[row.exclusion_reason] += 1
    lines: list[str] = []
    for mid in sorted(d.measureid for d in rules.diseases):
        counts = status_counts.get(mid, Counter())
        lines.append("%s: %s" % (mid, ", ".join(
            "%s %d" % (status, counts[status]) for status in STATUSES)))
        reasons = reason_counts.get(mid, Counter())
        lines.extend("  %s: %d" % (reason, reasons[reason]) for reason in sorted(reasons))
    return "".join(line + "\n" for line in lines)
