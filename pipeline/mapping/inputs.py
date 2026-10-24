"""Inputs: read and validate `studies.csv` and `sites.csv` (design § Inputs; Req 1, 6.6, 11.4).

`read_inputs(paths, stderr=None)` takes an `InputPaths(studies, sites)` and returns
`(studies by nctId, nctIds with at least one MA_Site)`. The orphan-site warning
goes to `stderr` (default `sys.stderr`), so tests can capture it.

Error messages name the file, the failed check, and where relevant the line
and column. The only cell content they may hold is an nctId (Req 1.6, 12.8).
"""
from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import NamedTuple, TextIO

from pipeline.errors import PipelineError
from pipeline.io.csv_reader import read_table
from pipeline.io.csv_writer import COLUMNS, LIST_COLUMNS, encode_list_cell

STUDIES_HEADER: tuple[str, ...] = COLUMNS["studies"]
SITES_HEADER: tuple[str, ...] = COLUMNS["sites"]

MA_STATES = frozenset({"Massachusetts", "MA"})
_HEALTHY_VALUES = frozenset({"true", "false", ""})


class InputPaths(NamedTuple):
    studies: Path
    sites: Path


@dataclass(frozen=True)
class Study:
    nct_id: str
    brief_title: str
    overall_status: str
    healthy_volunteers: str
    maximum_age: str
    conditions: tuple[str, ...]
    mesh_terms: tuple[str, ...]
    ancestor_terms: tuple[str, ...]
    conditions_cell: str   # JSON array string, byte-identical to the source cell (Req 11.4)
    source_url: str


def _read(path: Path, header: tuple[str, ...], list_columns) -> list[tuple[int, dict]]:
    name = os.path.basename(os.fspath(path))
    try:
        return read_table(path, header, list_columns)
    except FileNotFoundError:
        raise PipelineError("%s: cannot open (file is missing)" % name) from None
    except UnicodeDecodeError:
        raise PipelineError("%s: not valid UTF-8" % name) from None
    except OSError as exc:
        raise PipelineError("%s: cannot open (%s)" % (name, type(exc).__name__)) from None


def _studies(path: Path) -> dict[str, Study]:
    name = os.path.basename(os.fspath(path))
    rows = _read(path, STUDIES_HEADER, LIST_COLUMNS["studies"])
    if not rows:
        raise PipelineError("%s: has zero data rows" % name)
    studies: dict[str, Study] = {}
    for line, row in rows:
        nct_id = row["nctId"]
        if nct_id == "":
            raise PipelineError("%s: line %d has an empty nctId" % (name, line))
        if nct_id in studies:
            raise PipelineError("%s: line %d has duplicate nctId %s" % (name, line, nct_id))
        if row["healthyVolunteers"] not in _HEALTHY_VALUES:
            raise PipelineError("%s: line %d column healthyVolunteers is not true, false or empty"
                                % (name, line))
        studies[nct_id] = Study(
            nct_id=nct_id,
            brief_title=row["briefTitle"],
            overall_status=row["overallStatus"],
            healthy_volunteers=row["healthyVolunteers"],
            maximum_age=row["maximumAge"],
            conditions=tuple(row["conditions"]),
            mesh_terms=tuple(row["meshTerms"]),
            ancestor_terms=tuple(row["ancestorTerms"]),
            conditions_cell=encode_list_cell(row["conditions"]),
            source_url=row["source_url"],
        )
    return studies


def read_inputs(paths: InputPaths, stderr: TextIO | None = None
                ) -> tuple[dict[str, Study], frozenset[str]]:
    """Read both inputs; return studies by nctId and the nctIds with an MA_Site (Req 1)."""
    studies = _studies(Path(paths.studies))
    sites = _read(Path(paths.sites), SITES_HEADER, LIST_COLUMNS["sites"])
    ma: set[str] = set()
    orphans = 0
    for _, row in sites:
        nct_id = row["nctId"]
        if nct_id not in studies:
            orphans += 1
            continue
        if row["state"] in MA_STATES:
            ma.add(nct_id)
    if orphans:
        out = sys.stderr if stderr is None else stderr
        print("warning: %s: ignored %d site rows whose nctId is not in %s"
              % (os.path.basename(os.fspath(paths.sites)), orphans,
                 os.path.basename(os.fspath(paths.studies))), file=out)
    return studies, frozenset(ma)
