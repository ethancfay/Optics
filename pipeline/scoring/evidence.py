"""Evidence_Builder (design § Component 6: Evidence_Builder; Req 3.1, 4.9).

Builds one `evidence.json` entry per disease: the per-NCT study list the
dashboard links out to, plus three lists of human-readable method notes
(`filters`, `mapping_choices`, `missing_data_notes`). The per-NCT rows restate
only the non-PII study fields the data contract allows (identifiers, titles,
statuses, counts, phases, intervention types, intervention names, URLs); no
contact data is ever read or emitted (Req 7.3).

`ncts` carries one row per eligible MA study for the measure (``scope.eligible_ids``),
each with:

- `nct_id` — the ClinicalTrials.gov identifier;
- `url` — the canonical study page ``https://clinicaltrials.gov/study/{nct_id}``;
- `title` — the study's brief title;
- `status` — the raw `overallStatus` enum (e.g. ``RECRUITING``);
- `study_type` — the raw `studyType` enum (e.g. ``INTERVENTIONAL``);
- `phases`, `intervention_types`, `intervention_names` — the study's list
  columns, copied as-is.

Rows are emitted sorted by `nct_id` (Unicode code point) so output is
deterministic regardless of set iteration order; the serialization step (task
10.1) also enforces this ordering.

`filters` and `mapping_choices` are static, human-readable notes describing how
the NCT list was selected and how studies were mapped to the disease measure.
They are plain method prose and must never contain a Forbidden_Term
(``neglected`` / ``underfunded`` / needs-more-trials / needs-more-drugs
language) or any PII (Req 4 § Forbidden terms; Req 7.3).

`missing_data_notes` is normally empty. When a measure has no prevalence data in
`places_ma.csv` (``measure_present`` is ``False``), a single note identifying
the measure is added so the dashboard can explain why burden-based numbers are
absent for that disease; the run continues to the next measure without
terminating (Req 4.9).
"""
from __future__ import annotations

from pipeline.scoring.models import DiseaseScope, StudyRow

# Canonical ClinicalTrials.gov study page, per the data contract's evidence.json
# example: one URL per study, keyed by nctId.
CTGOV_STUDY_URL = "https://clinicaltrials.gov/study/{nct_id}"

# Static method notes. These are deliberately factual descriptions of the
# selection and mapping method; they contain no Forbidden_Term and no PII.
_FILTERS: tuple[str, ...] = (
    "Studies with at least one Massachusetts location (state 'Massachusetts' "
    "or 'MA', matched case-insensitively).",
    "Studies retained by the pipeline's status and recency rules from "
    "ClinicalTrials.gov.",
    "Only studies mapped to this condition with match status 'included' are "
    "listed; 'questionable' and 'excluded' matches are not shown here.",
)

_MAPPING_CHOICES: tuple[str, ...] = (
    "Conditions were mapped to a CDC PLACES measure using MeSH terms, MeSH "
    "ancestor terms, and condition text.",
    "A study may map to more than one condition; it then appears under each "
    "condition it was mapped to.",
    "Counts elsewhere in the dashboard count each study once per category, "
    "identified by its ClinicalTrials.gov identifier.",
)


def _nct_row(study: StudyRow) -> dict[str, object]:
    """Build one `ncts` row from a study (non-PII fields only; Req 7.3)."""
    return {
        "nct_id": study.nctId,
        "url": CTGOV_STUDY_URL.format(nct_id=study.nctId),
        "title": study.briefTitle,
        "status": study.overallStatus,
        "study_type": study.studyType,
        "phases": list(study.phases),
        "intervention_types": list(study.interventionTypes),
        "intervention_names": list(study.interventionNames),
    }


def build_evidence_entry(
    scope: DiseaseScope,
    condition: str,
    measure_present: bool = True,
) -> dict[str, object]:
    """Assemble the `evidence.json` entry for one disease (Req 3.1, 4.9).

    `scope` is the measure's Disease_Scope; `condition` is the human-readable
    condition label. `measure_present` is ``False`` when the measure is absent
    from `places_ma.csv`; in that case a single `missing_data_notes` entry
    naming the measure is added and the caller continues to the next measure
    without terminating (Req 4.9).

    `ncts` carries one row per eligible MA study (``scope.eligible_ids``), sorted
    by `nct_id`. `filters` and `mapping_choices` are static method notes.
    """
    ncts = [
        _nct_row(scope.studies_by_id[nct_id])
        for nct_id in sorted(scope.eligible_ids)
    ]

    missing_data_notes: list[str] = []
    if not measure_present:
        missing_data_notes.append(
            f"Prevalence data for {condition} ({scope.measure_id}) is not "
            "available in the CDC PLACES county data, so burden-based numbers "
            "are not shown for this condition."
        )

    return {
        "measure_id": scope.measure_id,
        "condition": condition,
        "ncts": ncts,
        "filters": list(_FILTERS),
        "mapping_choices": list(_MAPPING_CHOICES),
        "missing_data_notes": missing_data_notes,
    }
