"""Unit tests for the Findings_Generator Drug rule and forbidden-term ban.

Concrete examples complementing the findings-label property test (task 7.2):

- **Drug finding** (Req 6.5): WHERE `by_intervention_type` contains a `"Drug"`
  label with a count of 1 or more, a Finding whose text notes the drug may be an
  existing drug, a comparator, or a placebo is emitted; absent the `"Drug"`
  label, no such Finding appears.
- **Forbidden-term absence** (Req 6.6): across a range of inputs, no emitted
  Finding text contains any Forbidden_Term ("neglected", "underfunded",
  "needs more trials", "needs more drugs") under case-insensitive matching.
"""
from __future__ import annotations

import pytest

from pipeline.scoring.findings import (
    LABEL_POSSIBLE,
    generate_findings,
)

# The Forbidden_Terms the generator must never emit (Req 6.6; requirements § 4).
FORBIDDEN_TERMS: tuple[str, ...] = (
    "neglected",
    "underfunded",
    "needs more trials",
    "needs more drugs",
)

# Substrings that uniquely identify the Drug finding (Req 6.5).
_DRUG_FINDING_MARKERS: tuple[str, ...] = ("existing drug", "comparator", "placebo")


def _what(t: int = 0) -> dict[str, object]:
    """A minimal `what.json` entry carrying only the `t` the generator reads."""
    return {"t": t}


def _breakdowns(
    *,
    by_intervention_type: list[dict[str, object]] | None = None,
    ma_studies: int = 0,
    phase_overlap_studies: int = 0,
) -> dict[str, object]:
    """An `investigate.json` entry with the keys the generator consumes."""
    return {
        "by_intervention_type": by_intervention_type
        if by_intervention_type is not None
        else [],
        "ma_studies": ma_studies,
        "phase_overlap_studies": phase_overlap_studies,
    }


def _is_drug_finding(text: str) -> bool:
    lowered = text.casefold()
    return all(marker in lowered for marker in _DRUG_FINDING_MARKERS)


# --- Drug finding presence (Req 6.5) --------------------------------------------

@pytest.mark.parametrize("drug_count", [1, 2, 5, 37])
def test_drug_count_at_least_one_emits_drug_comparator_placebo_finding(drug_count):
    findings = generate_findings(
        None,
        _what(),
        _breakdowns(by_intervention_type=[{"label": "Drug", "count": drug_count}]),
    )

    drug_findings = [f for f in findings if _is_drug_finding(f["text"])]
    assert len(drug_findings) == 1
    assert drug_findings[0]["label"] == LABEL_POSSIBLE


def test_drug_finding_mentions_existing_drug_comparator_and_placebo():
    findings = generate_findings(
        None,
        _what(),
        _breakdowns(by_intervention_type=[{"label": "Drug", "count": 1}]),
    )

    drug_text = next(f["text"] for f in findings if _is_drug_finding(f["text"]))
    lowered = drug_text.casefold()
    assert "existing drug" in lowered
    assert "comparator" in lowered
    assert "placebo" in lowered


def test_drug_finding_present_alongside_other_intervention_labels():
    findings = generate_findings(
        None,
        _what(),
        _breakdowns(
            by_intervention_type=[
                {"label": "Behavioral", "count": 4},
                {"label": "Drug", "count": 2},
                {"label": "Device", "count": 1},
            ]
        ),
    )

    assert sum(1 for f in findings if _is_drug_finding(f["text"])) == 1


# --- Drug finding absence (Req 6.5) ---------------------------------------------

def test_no_drug_label_omits_drug_finding():
    findings = generate_findings(
        None,
        _what(),
        _breakdowns(
            by_intervention_type=[
                {"label": "Behavioral", "count": 3},
                {"label": "Device", "count": 1},
            ]
        ),
    )

    assert not any(_is_drug_finding(f["text"]) for f in findings)


def test_empty_intervention_breakdown_omits_drug_finding():
    findings = generate_findings(None, _what(), _breakdowns(by_intervention_type=[]))

    assert not any(_is_drug_finding(f["text"]) for f in findings)


def test_missing_intervention_breakdown_omits_drug_finding():
    # `by_intervention_type` absent entirely (generator defaults to no Drug).
    findings = generate_findings(
        None,
        _what(),
        {"ma_studies": 0, "phase_overlap_studies": 0},
    )

    assert not any(_is_drug_finding(f["text"]) for f in findings)


# --- Forbidden-term absence across inputs (Req 6.6) -----------------------------

# A spread of inputs toggling each gated finding on and off, so every finding
# the generator can emit is covered by the forbidden-term scan below.
_FORBIDDEN_SCAN_CASES: tuple[dict[str, object], ...] = (
    {"what": _what(0), "breakdowns": _breakdowns()},
    {
        "what": _what(0),
        "breakdowns": _breakdowns(
            by_intervention_type=[{"label": "Drug", "count": 1}]
        ),
    },
    {"what": _what(0), "breakdowns": _breakdowns(ma_studies=5)},
    {"what": _what(3), "breakdowns": _breakdowns(ma_studies=5)},
    {"what": _what(0), "breakdowns": _breakdowns(phase_overlap_studies=2)},
    {
        "what": _what(0),
        "breakdowns": _breakdowns(
            by_intervention_type=[{"label": "Drug", "count": 9}],
            ma_studies=4,
            phase_overlap_studies=6,
        ),
    },
)


@pytest.mark.parametrize("case", _FORBIDDEN_SCAN_CASES)
def test_no_finding_text_contains_a_forbidden_term(case):
    findings = generate_findings(None, case["what"], case["breakdowns"])

    assert findings, "every entry must carry at least one finding"
    for finding in findings:
        lowered = finding["text"].casefold()
        for term in FORBIDDEN_TERMS:
            assert term not in lowered, (
                f"forbidden term {term!r} found in finding text"
            )
