"""Readers (design § Component 1: Readers; Req 2.1-2.6, 1.6).

Load and type the five Input_Files for the Scoring & Export stage.
`studies.csv`, `sites.csv`, and `places_ma.csv` are read through the shared
`pipeline.io.csv_reader`, so header validation and JSON-array list columns
follow exactly the same conventions as the rest of the pipeline. `fetch_log.json`
is loaded as a plain JSON object.

`study_diseases.csv` is produced by Spec 2, which has not yet landed, so in a
production run the file is absent and `load_study_diseases` raises a
`PipelineError` naming the file (Req 2.5). Tests supply a fixture with the
data-contract columns in any directory; `resolve_study_diseases_path` lets a
configured fixture directory take precedence over `pipeline/processed/`
(Req 2.1). The dedicated reader validates exactly the contract columns and
decodes one row to one `DiseaseMatch` (Req 2.2).

Every error message names the file, and where relevant the column and nctId,
without quoting any cell content (Req 2.4, 2.6, 3.3).
"""
from __future__ import annotations

import csv
import json
import os
from dataclasses import fields

from pipeline.errors import PipelineError
from pipeline.io.csv_writer import COLUMNS, LIST_COLUMNS, TableKind
from pipeline.scoring.models import (
    DiseaseMatch,
    PlacesRow,
    SiteRow,
    StudyRow,
)

PathLike = str | os.PathLike

# The data-contract columns of `study_diseases.csv`, in contract order (Req 2.2).
# Derived from the DiseaseMatch dataclass so the two never drift apart.
STUDY_DISEASES_COLUMNS: tuple[str, ...] = tuple(f.name for f in fields(DiseaseMatch))

STUDY_DISEASES_FILE_NAME = "study_diseases.csv"
FETCH_LOG_FILE_NAME = "fetch_log.json"


def load_studies(path: PathLike) -> list[StudyRow]:
    """Load `studies.csv` into `StudyRow`s (Req 2.1, 2.3, 2.4, 2.6)."""
    return [StudyRow(**row) for row in _read_table(path, "studies")]


def load_sites(path: PathLike) -> list[SiteRow]:
    """Load `sites.csv` into `SiteRow`s (Req 2.1, 2.6)."""
    return [SiteRow(**row) for row in _read_table(path, "sites")]


def load_places(path: PathLike) -> list[PlacesRow]:
    """Load `places_ma.csv` into `PlacesRow`s (Req 2.1, 2.6)."""
    return [PlacesRow(**row) for row in _read_table(path, "places")]


def _read_table(path: PathLike, kind: TableKind) -> list[dict[str, object]]:
    """Read one of the three Spec 1 CSVs, reusing the CSV_Writer column and
    list-column definitions for header validation and JSON-array decoding
    (Req 2.1, 2.3, 2.6).

    This mirrors `pipeline.io.csv_reader.read_csv` but, when a list cell is not
    valid JSON, names the offending row's `nctId` as well as the file and column
    (Req 2.4) rather than the line number. No cell content is ever quoted
    (Req 3.3).
    """
    name = os.path.basename(os.fspath(path))
    columns = COLUMNS[kind]
    list_columns = LIST_COLUMNS[kind]
    try:
        handle = open(path, encoding="utf-8", newline="")
    except FileNotFoundError:
        raise PipelineError("%s: required input file is absent" % name) from None
    with handle:
        reader = csv.reader(handle)
        header = next(reader, None)
        if header is None or tuple(header) != columns:
            raise PipelineError(
                "%s: header row does not match the %s columns" % (name, kind))
        list_indices = [(column, columns.index(column)) for column in list_columns]
        rows: list[dict[str, object]] = []
        for cells in reader:
            if len(cells) != len(columns):
                raise PipelineError(
                    "%s: line %d has %d cells, expected %d"
                    % (name, reader.line_num, len(cells), len(columns)))
            row = dict(zip(columns, cells))
            nct_id = row.get("nctId", "")
            for column, index in list_indices:
                row[column] = _decode_list(name, column, nct_id, cells[index])
            rows.append(row)
    return rows


def _decode_list(name: str, column: str, nct_id: object, cell: str) -> list[str]:
    """Decode a JSON-array list cell, or raise naming file/column/nctId (Req 2.4)."""
    try:
        value = json.loads(cell)
    except ValueError:
        value = None
    if not isinstance(value, list) or not all(isinstance(v, str) for v in value):
        raise PipelineError(
            "%s: column %s for nctId %s is not a JSON array of strings"
            % (name, column, nct_id))
    return value


def resolve_study_diseases_path(processed_dir: PathLike,
                                fixture_dir: PathLike | None = None) -> str:
    """Pick the directory to read `study_diseases.csv` from (Req 2.1).

    A configured `fixture_dir` takes precedence over `processed_dir`; absence of
    the file is handled by `load_study_diseases`, not here, so the chosen path is
    returned even when it does not yet exist.
    """
    base = fixture_dir if fixture_dir is not None else processed_dir
    return os.path.join(os.fspath(base), STUDY_DISEASES_FILE_NAME)


def load_study_diseases(path: PathLike) -> list[DiseaseMatch]:
    """Load `study_diseases.csv` into `DiseaseMatch`es (Req 2.2, 2.5, 2.6).

    Validates exactly the contract columns and decodes one row to one match.
    When the file is absent (the production case before Spec 2 lands), raises a
    `PipelineError` naming the file (Req 2.5). A header that does not match the
    contract columns raises a `PipelineError` naming the file (Req 2.6). No cell
    content is ever quoted in an error message (Req 3.3).
    """
    name = os.path.basename(os.fspath(path))
    try:
        handle = open(path, encoding="utf-8", newline="")
    except FileNotFoundError:
        raise PipelineError("%s: required input file is absent" % name) from None
    with handle:
        reader = csv.reader(handle)
        header = next(reader, None)
        if header is None or tuple(header) != STUDY_DISEASES_COLUMNS:
            raise PipelineError(
                "%s: header row does not match the study_diseases columns" % name)
        matches: list[DiseaseMatch] = []
        for cells in reader:
            if len(cells) != len(STUDY_DISEASES_COLUMNS):
                raise PipelineError(
                    "%s: line %d has %d cells, expected %d"
                    % (name, reader.line_num, len(cells), len(STUDY_DISEASES_COLUMNS)))
            matches.append(DiseaseMatch(**dict(zip(STUDY_DISEASES_COLUMNS, cells))))
    return matches


def load_fetch_log(path: PathLike) -> dict:
    """Load `fetch_log.json` as a JSON object (Req 2.1, 2.5).

    An absent file raises a `PipelineError` naming the file (Req 2.5); content
    that is not a JSON object raises a `PipelineError` naming the file, without
    quoting any of its content (Req 3.3).
    """
    name = os.path.basename(os.fspath(path))
    try:
        handle = open(path, encoding="utf-8")
    except FileNotFoundError:
        raise PipelineError("%s: required input file is absent" % name) from None
    with handle:
        try:
            value = json.load(handle)
        except ValueError:
            raise PipelineError("%s: not valid JSON" % name) from None
    if not isinstance(value, dict):
        raise PipelineError("%s: top-level value is not a JSON object" % name)
    return value
