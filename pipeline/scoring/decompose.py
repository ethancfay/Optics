"""Decomposer (design § Decomposer, Part B; Req 5.1-5.8, 3.4).

Builds the `investigate.json` breakdown arrays and the two scalar counts for a
single disease. Every count is a Distinct_Count of nctIds: a study counts once
per label no matter how many MA sites, duplicate rows, or repeated labels it
carries (Req 5.1, 5.8).

The shared `by_label` helper implements the Part B algorithm: for each eligible
nctId it gathers the DISTINCT labels the study carries (via an `extract`
function), adds the nctId to that label's set, then emits
`{"label", "count"}` objects sorted by label using Unicode code-point order,
excluding any label whose count is 0 (Req 5.2).

Raw ClinicalTrials.gov enum values (`RECRUITING`, `INTERVENTIONAL`, `DRUG`,
`PHASE2`, `DIETARY_SUPPLEMENT`, ...) are humanized to Title Case with
underscores turned into spaces (`RECRUITING` -> "Recruiting",
`NOT_YET_RECRUITING` -> "Not Yet Recruiting", `DIETARY_SUPPLEMENT` ->
"Dietary Supplement", `PHASE2` -> "Phase 2"). Phases are special-cased: an empty
or missing phase list maps to the single label "Not reported" and an
"NA" / "Not Applicable" phase maps to "Not applicable", each a separate label
(Req 5.4, 5.5).
"""
from __future__ import annotations

import re
from typing import Callable, Iterable

from pipeline.scoring.models import DiseaseScope, StudyRow

LabelCount = dict[str, object]        # {"label": str, "count": int}

# Phase enum values that mean "not applicable" (case-insensitive, after
# stripping and collapsing separators). ClinicalTrials.gov uses "NA".
_NOT_APPLICABLE_PHASES: frozenset[str] = frozenset({"na", "notapplicable"})

_PHASE_NUMBER_RE = re.compile(r"^phase(\d+)$", re.IGNORECASE)


def _humanize(value: str) -> str:
    """Humanize a raw enum token (`NOT_YET_RECRUITING` -> "Not Yet Recruiting").

    Underscores become spaces and each whitespace-separated word is title-cased.
    """
    return " ".join(part.capitalize() for part in value.strip().split("_") if part)


def _humanize_phase(value: str) -> str:
    """Humanize a single phase token (`PHASE2` -> "Phase 2", `EARLY_PHASE1` -> ...)."""
    match = _PHASE_NUMBER_RE.match(value.strip())
    if match:
        return f"Phase {match.group(1)}"
    return _humanize(value)


def by_label(
    scope: DiseaseScope, extract: Callable[[StudyRow], Iterable[str]]
) -> list[LabelCount]:
    """Distinct-nctId counts per label, sorted by label (Part B; Req 5.1, 5.2, 5.8).

    `extract(study)` returns the labels a study carries. Within one study the
    labels are de-duplicated so a study counts at most once per label, and the
    nctId set per label guarantees duplicate study rows never change a count.
    Labels are emitted sorted by Unicode code point; a label whose count is 0 is
    never produced (it cannot occur here because a label is only seen when a
    study carries it).
    """
    ids_per_label: dict[str, set[str]] = {}
    for nct_id in scope.eligible_ids:
        study = scope.studies_by_id[nct_id]
        for label in set(extract(study)):
            ids_per_label.setdefault(label, set()).add(nct_id)
    return [
        {"label": label, "count": len(ids_per_label[label])}
        for label in sorted(ids_per_label)
        if len(ids_per_label[label]) > 0
    ]


def by_overall_status(scope: DiseaseScope) -> list[LabelCount]:
    """`by_overall_status` breakdown: humanized `overallStatus` (Req 5.1)."""
    return by_label(
        scope,
        lambda study: [_humanize(study.overallStatus)] if study.overallStatus.strip() else [],
    )


def by_study_type(scope: DiseaseScope) -> list[LabelCount]:
    """`by_study_type` breakdown: humanized `studyType` (Req 5.1)."""
    return by_label(
        scope,
        lambda study: [_humanize(study.studyType)] if study.studyType.strip() else [],
    )


def by_intervention_type(scope: DiseaseScope) -> list[LabelCount]:
    """`by_intervention_type` breakdown: humanized `interventionTypes` (Req 5.1, 5.3).

    A study listing several intervention types counts once under each distinct
    type (distinct nctId per label).
    """
    return by_label(
        scope,
        lambda study: [
            _humanize(t) for t in study.interventionTypes if t.strip()
        ],
    )


def _phase_labels(study: StudyRow) -> list[str]:
    """The `by_phase` labels a single study carries (Req 5.4, 5.5).

    An empty or missing phase list -> ["Not reported"]. An "NA" /
    "Not Applicable" phase -> "Not applicable". Numeric phases humanize to
    "Phase N". Each distinct phase is a separate label.
    """
    phases = [p for p in study.phases if p.strip()]
    if not phases:
        return ["Not reported"]
    labels: list[str] = []
    for phase in phases:
        normalized = re.sub(r"[\s_]+", "", phase).casefold()
        if normalized in _NOT_APPLICABLE_PHASES:
            labels.append("Not applicable")
        else:
            labels.append(_humanize_phase(phase))
    return labels


def by_phase(scope: DiseaseScope) -> list[LabelCount]:
    """`by_phase` breakdown with "Not reported" / "Not applicable" labels (Req 5.4, 5.5)."""
    return by_label(scope, _phase_labels)


def phase_overlap_studies(scope: DiseaseScope) -> int:
    """Distinct eligible nctIds whose `phases` list has >1 element (Req 5.6)."""
    return sum(
        1
        for nct_id in scope.eligible_ids
        if len([p for p in scope.studies_by_id[nct_id].phases if p.strip()]) > 1
    )


def ma_studies(scope: DiseaseScope) -> int:
    """Distinct eligible nctIds across all fetched statuses (Req 5.7).

    `scope.eligible_ids` is already the set of included MA studies for the
    measure across the fetched statuses, so this is simply its size.
    """
    return len(scope.eligible_ids)


def build_investigate_entry(
    scope: DiseaseScope,
    findings: list[dict[str, object]] | None = None,
) -> dict[str, object]:
    """Assemble the `investigate.json` entry for one disease (Req 3.4, 5.1-5.8).

    `us_studies` is always `null` (national comparison is deferred). `findings`
    is produced by the Findings_Generator (a separate module); it is accepted as
    a parameter and defaults to an empty list so the Decomposer stays
    independent of that module. The breakdown arrays and scalar counts are all
    distinct-nctId counts.
    """
    return {
        "measure_id": scope.measure_id,
        "condition": scope.condition,
        "ma_studies": ma_studies(scope),
        "us_studies": None,
        "by_overall_status": by_overall_status(scope),
        "by_study_type": by_study_type(scope),
        "by_intervention_type": by_intervention_type(scope),
        "by_phase": by_phase(scope),
        "phase_overlap_studies": phase_overlap_studies(scope),
        "findings": findings if findings is not None else [],
    }
