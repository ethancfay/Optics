"""CSV_Reader (design § CSV_Reader; Req 7.6).

Parses a file written by the CSV_Writer back into one dict per data line,
keyed by the header row. Cells in the table's list columns (shared with the
writer) are decoded as JSON arrays of strings; `[]` gives an empty list.
Error messages name the file, line and column only, never cell content (Req 3.3).
"""
from __future__ import annotations

import csv
import json
import os

from pipeline.errors import PipelineError
from pipeline.io.csv_writer import COLUMNS, LIST_COLUMNS, TableKind


def read_csv(path: str | os.PathLike, kind: TableKind) -> list[dict[str, object]]:
    name = os.path.basename(os.fspath(path))
    with open(path, encoding="utf-8", newline="") as handle:
        reader = csv.reader(handle)
        header = next(reader, None)
        if header is None or tuple(header) != COLUMNS[kind]:
            raise PipelineError("%s: header row does not match the %s columns" % (name, kind))
        list_columns = LIST_COLUMNS[kind]
        rows: list[dict[str, object]] = []
        for cells in reader:
            if len(cells) != len(header):
                raise PipelineError("%s: line %d has %d cells, expected %d"
                                    % (name, reader.line_num, len(cells), len(header)))
            row: dict[str, object] = {}
            for column, cell in zip(header, cells):
                row[column] = _decode_list(name, reader.line_num, column, cell) \
                    if column in list_columns else cell
            rows.append(row)
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
