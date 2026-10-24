"""Precision_Sampler (design § Precision_Sampler; Req 11).

For each disease, the candidates are the nctIds with an `included`
Study_Disease_Row for that measureid and at least one MA_Site, sorted by nctId
in Unicode code point order (Req 11.1). `select` draws up to 20 of them with a
fresh `random.Random(seed)` per disease, so one disease's sample depends only on
the seed and its own candidate list (Req 11.5).

`existing_state` decides whether an existing `burden_test/precision_sample.csv`
is kept (some `correct` cell filled, Req 11.6) or rewritten (Req 11.7), and
rejects an unreadable file or wrong header (Req 11.8).

Warnings and notices go to `stderr` (default `sys.stderr`) so tests can capture
them. Messages carry only file names, measureids and counts.
"""
from __future__ import annotations

import csv
import os
import random
import sys
from pathlib import Path
from typing import Iterable, Literal, Mapping, TextIO

from pipeline.errors import PipelineError
from pipeline.io.csv_reader import read_table
from pipeline.io.csv_writer import EncodedTable

HEADER: tuple[str, ...] = (
    "nctId", "measureid", "briefTitle", "conditions", "matched_term", "source_url", "correct",
)
SAMPLE_SIZE = 20
INCLUDED = "included"


def candidates(rows: Iterable, ma_ids: Iterable[str], measureid: str) -> list[str]:
    """Distinct included nctIds for `measureid` with an MA_Site, sorted (Req 11.1)."""
    ma = frozenset(ma_ids)
    found = {
        row.nctId for row in rows
        if row.measureid == measureid and row.match_status == INCLUDED and row.nctId in ma
    }
    return sorted(found)


def select(cands: list[str], seed: int) -> list[str]:
    """Seeded sample of min(20, n) candidates; a new generator per call (Req 11.1, 11.5)."""
    return random.Random(seed).sample(cands, min(SAMPLE_SIZE, len(cands)))


def build(rules, rows: Iterable, studies: Mapping, ma_ids: Iterable[str],
          stderr: TextIO | None = None) -> EncodedTable:
    """Encode the sample, rows sorted by (measureid, nctId) (Req 11.2-11.4).

    A disease with fewer than 20 candidates gets one stderr warning with the count.
    """
    out = sys.stderr if stderr is None else stderr
    rows = list(rows)
    ma = frozenset(ma_ids)
    matched = {(row.nctId, row.measureid): row.matched_term for row in rows}
    encoded: list[list[str]] = []
    for disease in rules.diseases:
        mid = disease.measureid
        cands = candidates(rows, ma, mid)
        if len(cands) < SAMPLE_SIZE:
            print("warning: precision sample %s: only %d candidates (fewer than %d)"
                  % (mid, len(cands), SAMPLE_SIZE), file=out)
        for nct in select(cands, rules.seed):
            study = studies[nct]
            encoded.append([nct, mid, study.brief_title, study.conditions_cell,
                            matched[(nct, mid)], study.source_url, ""])
    encoded.sort(key=lambda cells: (cells[1], cells[0]))
    return EncodedTable(kind="precision_sample", header=HEADER, rows=encoded)


def existing_state(path: str | os.PathLike, resample: bool, stderr: TextIO | None = None
                   ) -> tuple[Literal["write", "keep"], int]:
    """Return (decision, filled `correct` cell count) (Req 11.6-11.8)."""
    if resample or not Path(path).exists():
        return "write", 0
    name = os.path.basename(os.fspath(path))
    try:
        table = read_table(path, HEADER, frozenset())
    except FileNotFoundError:
        raise PipelineError("%s: cannot open (file is missing)" % name) from None
    except UnicodeDecodeError:
        raise PipelineError("%s: not valid UTF-8" % name) from None
    except OSError as exc:
        raise PipelineError("%s: cannot open (%s)" % (name, type(exc).__name__)) from None
    except csv.Error:
        raise PipelineError("%s: cannot be parsed as CSV" % name) from None
    filled = sum(1 for _, row in table if str(row["correct"]).strip())
    if filled:
        out = sys.stderr if stderr is None else stderr
        print("notice: %s: kept unchanged, %d filled correct cells (use --resample to replace)"
              % (name, filled), file=out)
        return "keep", filled
    return "write", 0
