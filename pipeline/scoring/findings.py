"""Findings_Generator (design § Findings (rules-based), Part B; Req 6.1-6.6).

Produces the rules-based, record-grounded `findings` list for a single
disease's `investigate.json` entry. Every finding is derived solely from the
numbers already computed for that disease (the `what.json` entry and the
`investigate.json` breakdowns); no AI, ML, or LLM is involved (Req 6.1). Each
finding is a `{"text", "label"}` object whose `label` is exactly one of the two
allowed `FINDING_LABELS` (Req 6.2).

The deterministic rules (design Part B `generate_findings`):

- `Drug` intervention count >= 1 -> a "possible explanation from available
  records" finding noting the DRUG-type intervention may be an existing drug, a
  comparator, or a placebo (Req 6.5).
- `t == 0` and `ma_studies > 0` -> a "possible explanation" finding that no
  study is both recruiting overall and recruiting at an MA site, though other
  MA-associated studies exist in the record.
- `phase_overlap_studies > 0` -> a "possible explanation" finding that some
  studies list more than one phase, so counts by phase overlap.

A single mandatory "cannot determine from public data" finding about funding
levels or sponsor decisions is always appended last, so every entry has at
least one finding and exactly one finding carrying that label (Req 6.3, 6.4).

No finding text ever contains a Forbidden_Term (case-insensitive): "neglected",
"underfunded", or a phrase stating the disease needs more trials or more drugs
(Req 6.6). The fixed sentences below avoid these terms by construction, and a
defensive assertion guarantees it before returning.
"""
from __future__ import annotations

Finding = dict[str, str]              # {"text": str, "label": str}

# The two — and only two — allowed Finding_Label values (Req 6.2).
LABEL_POSSIBLE = "possible explanation from available records"
LABEL_CANNOT_DETERMINE = "cannot determine from public data"
FINDING_LABELS: frozenset[str] = frozenset({LABEL_POSSIBLE, LABEL_CANNOT_DETERMINE})

# The intervention-type breakdown label for DRUG-type interventions, as
# humanized by the Decomposer (`DRUG` -> "Drug").
_DRUG_LABEL = "Drug"

# Forbidden claim terms banned by product.md / health-safety.md (Req 6.6).
# Case-insensitive substring match; the fixed finding text avoids all of them.
_FORBIDDEN_TERMS: tuple[str, ...] = (
    "neglected",
    "underfunded",
    "needs more trials",
    "needs more drugs",
    "need more trials",
    "need more drugs",
)


def _drug_count(breakdowns: dict[str, object]) -> int:
    """Count for the `"Drug"` label in the `by_intervention_type` breakdown.

    Returns 0 when the breakdown is absent or carries no `"Drug"` label; the
    Decomposer never emits a label with count 0, so any present `"Drug"` entry
    has count >= 1.
    """
    rows = breakdowns.get("by_intervention_type") or []
    for row in rows:
        if row.get("label") == _DRUG_LABEL:
            return int(row.get("count", 0))
    return 0


def _possible(text: str) -> Finding:
    return {"text": text, "label": LABEL_POSSIBLE}


def _cannot_determine(text: str) -> Finding:
    return {"text": text, "label": LABEL_CANNOT_DETERMINE}


def generate_findings(
    scope: object,
    what: dict[str, object],
    breakdowns: dict[str, object],
) -> list[Finding]:
    """Rules-based findings for one disease (design Part B; Req 6.1-6.6).

    `what` is the computed `what.json` entry (supplies `t`); `breakdowns` is the
    `investigate.json` entry (supplies `by_intervention_type`,
    `phase_overlap_studies`, and `ma_studies`). `scope` is accepted for a stable
    signature but every value used is one of the already-computed numbers, so no
    source row is re-interpreted here (Req 6.1).

    The record-grounded "possible explanation from available records" findings
    are each gated on a numeric condition and appended first; exactly one
    mandatory "cannot determine from public data" funding/sponsor finding is
    always appended last (Req 6.3, 6.4). No emitted text contains a
    Forbidden_Term (Req 6.6).
    """
    findings: list[Finding] = []

    # Record-grounded observations, each gated on a numeric condition.
    if _drug_count(breakdowns) >= 1:
        findings.append(
            _possible(
                "Some studies list a drug-type intervention, which may be an "
                "existing drug, a comparator, or a placebo."
            )
        )

    t = int(what.get("t", 0) or 0)
    ma = int(breakdowns.get("ma_studies", 0) or 0)
    if t == 0 and ma > 0:
        findings.append(
            _possible(
                "No studies are both recruiting overall and recruiting at a "
                "Massachusetts site, though other Massachusetts-associated "
                "studies appear in the record."
            )
        )

    phase_overlap = int(breakdowns.get("phase_overlap_studies", 0) or 0)
    if phase_overlap > 0:
        findings.append(
            _possible(
                "Some studies list more than one phase, so counts by phase "
                "overlap."
            )
        )

    # MANDATORY — always exactly one, appended last (Req 6.3, 6.4).
    findings.append(
        _cannot_determine(
            "Whether this reflects funding levels or sponsor decisions cannot "
            "be determined from ClinicalTrials.gov or CDC PLACES records."
        )
    )

    _assert_contract(findings)
    return findings


def _assert_contract(findings: list[Finding]) -> None:
    """Defensive guard for the Part B ASSERTs (Req 6.2, 6.4, 6.6).

    Guarantees every label is valid, exactly one "cannot determine from public
    data" finding exists, and no text carries a Forbidden_Term before the list
    leaves this module. A violation is a programming error, not bad input.
    """
    assert all(f["label"] in FINDING_LABELS for f in findings), "invalid Finding_Label"
    cannot = sum(1 for f in findings if f["label"] == LABEL_CANNOT_DETERMINE)
    assert cannot == 1, "exactly one 'cannot determine from public data' finding required"
    for finding in findings:
        lowered = finding["text"].casefold()
        for term in _FORBIDDEN_TERMS:
            assert term not in lowered, "forbidden term in finding text"
