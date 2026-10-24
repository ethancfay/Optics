"""Property-based tests for the Findings_Generator (design § Correctness Properties).

Property 4 (Findings label validity) — for every disease's generated findings:

- every finding carries exactly one of the two valid `FINDING_LABELS`;
- exactly one finding carries the mandatory
  `"cannot determine from public data"` label (so every entry has at least one
  finding — the mandatory funding/sponsor finding is always appended); and
- no finding text contains a Forbidden_Term (case-insensitive substring):
  "neglected", "underfunded", "needs more trials", or "needs more drugs".

Each example builds the real `what.json` entry (`build_what_entry`) and
`investigate.json` breakdowns (`build_investigate_entry`) from generated inputs
via the production MA_Index_Builder, Scoring_Engine, and Decomposer, then calls
`generate_findings` with those computed numbers — the same path the exporter
takes. The duplicate-heavy `scoring_inputs` strategy drives many measures,
intervention mixes (including repeated "DRUG"), phase overlaps, and T==0 cases,
exercising every findings rule across inputs.

**Validates: Requirements 9.5**
"""
from __future__ import annotations

from hypothesis import given, settings

from pipeline.scoring.decompose import build_investigate_entry
from pipeline.scoring.findings import FINDING_LABELS, LABEL_CANNOT_DETERMINE, generate_findings
from pipeline.scoring.index import build_scopes
from pipeline.scoring.scoring import build_what_entry
from tests.strategies import scoring_inputs

# The product-defined banned claim phrases (product.md / health-safety.md),
# restated here independently of the module so the property checks the contract,
# not the module's own guard. Matched case-insensitively as substrings.
FORBIDDEN_TERMS: tuple[str, ...] = (
    "neglected",
    "underfunded",
    "needs more trials",
    "needs more drugs",
)


@settings(max_examples=200)
@given(scoring_inputs())
def test_findings_label_validity(inputs: dict) -> None:
    """Every entry's findings: valid labels, exactly one funding finding, no forbidden terms."""
    scopes = build_scopes(inputs["studies"], inputs["sites"], inputs["diseases"])
    for scope in scopes.values():
        what = build_what_entry(scope, inputs["places"], scope.condition)
        breakdowns = build_investigate_entry(scope)
        findings = generate_findings(scope, what, breakdowns)

        # At least one finding per entry (the mandatory funding finding).
        assert len(findings) >= 1

        # Every finding label is exactly one of the two valid labels.
        for finding in findings:
            assert finding["label"] in FINDING_LABELS

        # Exactly one "cannot determine from public data" finding per entry.
        cannot = sum(1 for f in findings if f["label"] == LABEL_CANNOT_DETERMINE)
        assert cannot == 1

        # No finding text contains a Forbidden_Term (case-insensitive).
        for finding in findings:
            lowered = finding["text"].casefold()
            for term in FORBIDDEN_TERMS:
                assert term.casefold() not in lowered
