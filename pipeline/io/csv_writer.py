"""CSV_Writer (design § CSV_Writer; Req 7.2-7.5, 7.8, 7.9).

`encode_rows` sorts the rows and turns every value into its final cell string.
`serialize` turns an encoded table into the exact file bytes. The PII_Guard
runs on the encoded table, so it sees the same strings that are written
(Req 8.1). Writing the bytes to disk is done by the atomic output step.

List columns are defined once here and shared with the CSV_Reader (Req 7.6).
"""
from __future__ import annotations

import json
from dataclasses import astuple, dataclass, fields
from typing import Iterable, Literal

from pipeline.transform.places_transformer import PlacesRow
from pipeline.transform.study_transformer import SiteRow, StudyRow

TableKind = Literal["studies", "sites", "places"]

ROW_TYPES: dict[str, type] = {"studies": StudyRow, "sites": SiteRow, "places": PlacesRow}

FILE_NAMES: dict[str, str] = {
    "studies": "studies.csv", "sites": "sites.csv", "places": "places_ma.csv",
}

# Column order is the dataclass field order, which follows Req 4.2, 5.1 and 6.1 (Req 7.2).
COLUMNS: dict[str, tuple[str, ...]] = {
    kind: tuple(f.name for f in fields(row_type)) for kind, row_type in ROW_TYPES.items()
}

# Multi-valued fields, written as JSON_Array_Cells (Req 7.4).
LIST_COLUMNS: dict[str, frozenset[str]] = {
    "studies": frozenset({
        "phases", "stdAges", "conditions", "interventionTypes", "interventionNames",
        "meshTerms", "meshIds", "ancestorTerms", "ancestorIds",
    }),
    "sites": frozenset(),
    "places": frozenset(),
}

# Sort keys (Req 7.8). Sites and PLACES add the remaining columns, in column
# order, as tie-breakers so equal keys still give byte-identical files.
_PRIMARY_KEYS: dict[str, tuple[str, ...]] = {
    "studies": ("nctId",),
    "sites": ("nctId", "facility", "zip"),
    "places": ("locationname", "measureid", "locationid"),
}
_TIE_BREAK = {"studies": False, "sites": True, "places": True}

_QUOTE_TRIGGERS = (",", '"', "\r", "\n")


@dataclass(frozen=True)
class EncodedTable:
    kind: str
    header: tuple[str, ...]
    rows: list[list[str]]   # cell strings, in sorted order

    @property
    def file_name(self) -> str:
        return FILE_NAMES[self.kind]


def encode_list_cell(values: Iterable[str]) -> str:
    """JSON array of strings, compact, UTF-8 text rather than \\u escapes (Req 7.4, 7.5)."""
    return json.dumps(list(values), ensure_ascii=False, separators=(",", ":"))


def _encode_scalar(value: object) -> str:
    return "" if value is None else str(value)


def _sort_key_indices(kind: str) -> list[int]:
    header = COLUMNS[kind]
    keys = [header.index(name) for name in _PRIMARY_KEYS[kind]]
    if _TIE_BREAK[kind]:
        keys += [i for i in range(len(header)) if i not in keys]
    return keys


def encode_rows(kind: TableKind, rows: Iterable[object]) -> EncodedTable:
    """Sort rows and encode every value to its cell string (Req 7.4, 7.8)."""
    if kind not in ROW_TYPES:
        raise ValueError("unknown table kind: %s" % kind)
    header = COLUMNS[kind]
    list_columns = LIST_COLUMNS[kind]
    encoded: list[list[str]] = []
    for row in rows:
        values = astuple(row)
        encoded.append([
            encode_list_cell(value) if name in list_columns else _encode_scalar(value)
            for name, value in zip(header, values)
        ])
    indices = _sort_key_indices(kind)
    # Plain str comparison is Unicode code point order (Req 7.8).
    encoded.sort(key=lambda cells: [cells[i] for i in indices])
    return EncodedTable(kind=kind, header=header, rows=encoded)


def quote_cell(cell: str) -> str:
    """Quote iff the cell contains a comma, double quote, CR or LF (Req 7.3)."""
    if any(ch in cell for ch in _QUOTE_TRIGGERS):
        return '"' + cell.replace('"', '""') + '"'
    return cell


def serialize(table: EncodedTable) -> bytes:
    """Header row then data rows, LF endings, UTF-8 without BOM (Req 7.2, 7.9)."""
    lines = [",".join(quote_cell(c) for c in table.header)]
    lines.extend(",".join(quote_cell(c) for c in cells) for cells in table.rows)
    return ("\n".join(lines) + "\n").encode("utf-8")
