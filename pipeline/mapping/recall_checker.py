"""Recall_Checker (design § Recall_Checker; Req 10).

Compares our per-disease counts with ClinicalTrials.gov's own condition search.

- `found_count` counts distinct nctIds with a Study_Disease_Row of any
  match_status; `included_count` counts only `included` rows. Both count only
  studies with an Active_Status overallStatus and at least one MA_Site
  (Req 10.1, Open Item 8).
- One GET per disease, in ascending measureid order, through the injected
  HTTP_Client (Req 10.2). `ctgov_count` is the response `totalCount`.
- Ratios are rounded to 3 decimals half up with exact `Fraction` arithmetic and
  are not capped at 1.0 (Req 10.3, Open Items 11, 12). `flagged` depends on the
  rounded `ratio_found` only (Req 10.4).
- Any request or response failure raises `PipelineError` naming the measureid,
  the URL and the failure type. Response bodies never appear in messages
  (Req 10.7).
"""
from __future__ import annotations

import json
import math
import sys
from dataclasses import dataclass
from datetime import date
from fractions import Fraction
from typing import Iterable, Mapping, TextIO

from pipeline.data.ctgov_fetcher import build_url
from pipeline.errors import PipelineError

ACTIVE = ("RECRUITING", "NOT_YET_RECRUITING", "ACTIVE_NOT_RECRUITING")
THRESHOLD = Fraction(800, 1000)
THRESHOLD_JSON = 0.8


@dataclass(frozen=True)
class RecallEntry:
    measureid: str
    disease_label: str
    recall_query_term: str
    found_count: int
    included_count: int
    ctgov_count: int
    ratio_found: Fraction | None
    ratio_included: Fraction | None
    flagged: bool
    request_url: str


@dataclass(frozen=True)
class RecallResult:
    check_date: date
    entries: tuple[RecallEntry, ...]  # sorted by measureid


def _count(rows: Iterable, studies: Mapping, ma_ids, measureid: str,
           included_only: bool) -> int:
    ids: set[str] = set()
    for row in rows:
        if row.measureid != measureid:
            continue
        if included_only and row.match_status != "included":
            continue
        study = studies.get(row.nctId)
        if study is None or study.overall_status not in ACTIVE:
            continue
        if row.nctId not in ma_ids:
            continue
        ids.add(row.nctId)
    return len(ids)


def found_count(rows, studies, ma_ids, measureid: str) -> int:
    """Distinct active MA nctIds with a row of any match_status (Req 10.1)."""
    return _count(rows, studies, ma_ids, measureid, included_only=False)


def included_count(rows, studies, ma_ids, measureid: str) -> int:
    """Distinct active MA nctIds with an `included` row (Req 10.1)."""
    return _count(rows, studies, ma_ids, measureid, included_only=True)


def request_url(term: str) -> str:
    """The full percent-encoded recall request URL for one Recall_Query_Term (Req 10.2)."""
    return build_url([
        ("query.cond", term),
        ("query.locn", "Massachusetts"),
        ("filter.overallStatus", ",".join(ACTIVE)),
        ("countTotal", "true"),
        ("pageSize", "1"),
        ("fields", "NCTId"),
    ])


def rounded_ratio(count: int, ctgov: int) -> Fraction | None:
    """count / ctgov rounded half up to 3 decimals, exactly; None when ctgov is 0 (Req 10.3)."""
    if ctgov == 0:
        return None
    return Fraction(math.floor(Fraction(count, ctgov) * 1000 + Fraction(1, 2)), 1000)


def is_flagged(ratio_found: Fraction | None) -> bool:
    """True when the rounded ratio_found is null or below 0.800 (Req 10.4)."""
    return ratio_found is None or ratio_found < THRESHOLD


def _ctgov_count(client, measureid: str, url: str) -> int:
    def fail(kind: str) -> PipelineError:
        return PipelineError("recall check failed for %s: %s (%s)" % (measureid, url, kind))

    try:
        body = client.get(url)
    except PipelineError as exc:
        raise fail(type(exc).__name__) from None
    try:
        data = json.loads(body)
    except (ValueError, TypeError, RecursionError):
        raise fail("invalid JSON") from None
    if not isinstance(data, dict) or "totalCount" not in data:
        raise fail("missing totalCount")
    total = data["totalCount"]
    if isinstance(total, bool) or not isinstance(total, int):
        raise fail("totalCount not an integer")
    if total < 0:
        raise fail("negative totalCount")
    return total


def check(rules, rows, studies, ma_ids, client, today: date) -> RecallResult:
    """Run the recall check for every disease in ascending measureid order (Req 10.1-10.4)."""
    rows = list(rows)
    entries: list[RecallEntry] = []
    for disease in sorted(rules.diseases, key=lambda d: d.measureid):
        url = request_url(disease.recall_query_term)
        ctgov = _ctgov_count(client, disease.measureid, url)
        found = found_count(rows, studies, ma_ids, disease.measureid)
        included = included_count(rows, studies, ma_ids, disease.measureid)
        ratio_found = rounded_ratio(found, ctgov)
        entries.append(RecallEntry(
            measureid=disease.measureid,
            disease_label=disease.label,
            recall_query_term=disease.recall_query_term,
            found_count=found,
            included_count=included,
            ctgov_count=ctgov,
            ratio_found=ratio_found,
            ratio_included=rounded_ratio(included, ctgov),
            flagged=is_flagged(ratio_found),
            request_url=url,
        ))
    return RecallResult(check_date=today, entries=tuple(entries))


def _ratio_json(value: Fraction | None) -> float | None:
    return None if value is None else float(value)


def serialize(result: RecallResult) -> bytes:
    """recall_check.json bytes: fixed key order, indent 2, UTF-8, trailing LF (Req 10.5)."""
    obj = {
        "check_date": result.check_date.isoformat(),
        "threshold": THRESHOLD_JSON,
        "diseases": [
            {
                "measureid": e.measureid,
                "disease_label": e.disease_label,
                "recall_query_term": e.recall_query_term,
                "found_count": e.found_count,
                "included_count": e.included_count,
                "ctgov_count": e.ctgov_count,
                "ratio_found": _ratio_json(e.ratio_found),
                "ratio_included": _ratio_json(e.ratio_included),
                "flagged": e.flagged,
                "request_url": e.request_url,
            }
            for e in sorted(result.entries, key=lambda e: e.measureid)
        ],
    }
    return (json.dumps(obj, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def warnings(result: RecallResult) -> list[str]:
    """One warning line per flagged disease, in measureid order (Req 10.6)."""
    lines = []
    for e in sorted(result.entries, key=lambda e: e.measureid):
        if not e.flagged:
            continue
        ratio = "null" if e.ratio_found is None else repr(float(e.ratio_found))
        lines.append(
            "warning: recall %s: found_count=%d included_count=%d ctgov_count=%d ratio_found=%s"
            % (e.measureid, e.found_count, e.included_count, e.ctgov_count, ratio)
        )
    return lines


def emit_warnings(result: RecallResult, stderr: TextIO | None = None) -> None:
    """Write `warnings(result)` to stderr (or the given stream)."""
    out = sys.stderr if stderr is None else stderr
    for line in warnings(result):
        print(line, file=out)
