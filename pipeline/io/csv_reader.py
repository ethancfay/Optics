"""CSV_Reader (Spec 1 design § CSV_Reader; Req 7.6. Spec 2 design § Input_Reader).

`read_table` parses a CSV file into `(line, row)` pairs, where `line` is the
1-based line on which the record starts (a quoted multi-line cell reports the
row's first line) and `row` is a dict keyed by the expected header. Cells in
`list_columns` are decoded as JSON arrays of strings; `[]` gives an empty list.
`read_csv` is the Spec 1 entry point: it reads a Spec 1 table kind and drops
the line numbers.

Error messages name the file, line and column only, never cell content
(Spec 1 Req 3.3; Spec 2 Req 1.3, 1.4, 1.6, 14.12).
"""
from __future__ import annotations

import csv
import json
import os
from collections.abc import Collection, Sequence

from pipeline.errors import PipelineError
from pipeline.io.csv_writer import COLUMNS, LIST_COLUMNS, TableKind


def read_table(path: str | os.PathLike, header: Sequence[str],
               list_columns: Collection[str]) -> list[tuple[int, dict[str, object]]]:
    return _read(path, tuple(header), list_columns, "expected")


def read_csv(path: str | os.PathLike, kind: TableKind) -> list[dict[str, object]]:
    return [row for _, row in _read(path, COLUMNS[kind], LIST_COLUMNS[kind], kind)]


def _read(path: str | os.PathLike, header: tuple[str, ...], list_columns: Collection[str],
          label: str) -> list[tuple[int, dict[str, object]]]:
    name = os.path.basename(os.fspath(path))
    with open(path, encoding="utf-8", newline="") as handle:
        reader = csv.reader(handle)
        found = next(reader, None)
        if found is None or tuple(found) != header:
            raise PipelineError("%s: header row does not match the %s columns" % (name, label))
        rows: list[tuple[int, dict[str, object]]] = []
        while True:
            line = reader.line_num + 1
            cells = next(reader, None)
            if cells is None:
                break
            if len(cells) != len(header):
                raise PipelineError("%s: line %d has %d cells, expected %d"
                                    % (name, line, len(cells), len(header)))
            row: dict[str, object] = {}
            for column, cell in zip(header, cells):
                row[column] = _decode_list(name, line, column, cell) \
                    if column in list_columns else cell
            rows.append((line, row))
    return rows


def _decode_list(name: str, line: int, column: str, cell: str) -> list[str]:
    try:
        value = json.loads(cell)
    except ValueError:
        value = None
    if not isinstance(value, list) or not all(isinstance(v, str) for v in value):
        raise PipelineError("%s: line %d column %s is not a JSON array of strings"
                            % (name, line, column))
    return value
