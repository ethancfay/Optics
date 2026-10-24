"""Property-based tests for the Decomposer (design § Correctness Properties).

Property 3 (Distinct-count integrity) — every breakdown `count`, the
`what.json` `t`, and `ma_studies` is the size of a set of DISTINCT nctIds; no
such count ever exceeds `ma_studies`; and duplicating study rows or adding more
MA sites to a study never changes any count.

The Decomposer and MA_Index_Builder are built so a study contributes to a count
once, by nctId, regardless of how many duplicate study rows or MA sites it
carries (Req 5.1, 5.8). This test draws from the duplicate-heavy `scoring_inputs`
strategy (task 1.3), whose tiny shared nctId pool makes duplicate study rows and
multiple MA sites per study common, and asserts the three parts of the property.

**Validates: Requirements 9.4**
"""
from __future__ import annotations

from hypothesis import given

from pipeline.scoring.decompose import (
    by_intervention_type,
    by_overall_status,
    by_phase,
    by_study_type,
    ma_studies,
    phase_overlap_studies,
)
from pipeline.scoring.index import build_scopes
from pipeline.scoring.models import SiteRow, StudyRow
from pipeline.scoring.scoring import compute_T
from tests.strategies import scoring_inputs

# The four label breakdowns, each a distinct-nctId count per label.
_BREAKDOWNS = (by_overall_status, by_study_type, by_intervention_type, by_phase)


def _duplicate_ma_sites(sites: list[SiteRow]) -> list[SiteRow]:
    """Clones of every existing MA site, so each MA study gains a duplicate MA site.

    Only existing MA sites are cloned: adding a site to a study that has no MA
    site would turn a non-MA study into an MA study, a real change rather than a
    duplicate, so it is intentionally excluded from this invariance check.
    """
    return [
        SiteRow(**site.__dict__)
        for site in sites
        if site.state.strip().casefold() in {"massachusetts", "ma"}
    ]


@given(scoring_inputs())
def test_distinct_count_integrity(inputs: dict) -> None:
    """Every breakdown count, t, and ma_studies is a distinct-nctId size bounded by ma_studies."""
    scopes = build_scopes(inputs["studies"], inputs["sites"], inputs["diseases"])
    for scope in scopes.values():
        total = ma_studies(scope)

        # ma_studies is exactly the number of distinct eligible nctIds.
        assert total == len(set(scope.eligible_ids))

        # t is a distinct-nctId count, a subset of the eligible studies.
        t = compute_T(scope)
        assert t == len(set(scope.t_ids))
        assert scope.t_ids <= scope.eligible_ids
        assert t <= total

        # phase_overlap_studies is a distinct-nctId count over eligible studies.
        overlap = phase_overlap_studies(scope)
        assert 0 <= overlap <= total

        # Every breakdown label count is a distinct-nctId size that never
        # exceeds ma_studies, and a sum of counts can exceed the total only
        # because one study may carry several distinct labels (never because a
        # label double-counts a study).
        for breakdown in _BREAKDOWNS:
            entries = breakdown(scope)
            labels = [entry["label"] for entry in entries]
            assert len(labels) == len(set(labels))  # one entry per label
            for entry in entries:
                count = entry["count"]
                assert count > 0                      # zero-count labels excluded
                assert count <= total                 # bounded by distinct studies


@given(scoring_inputs())
def test_counts_invariant_under_duplicate_rows_and_sites(inputs: dict) -> None:
    """Duplicating study rows and adding MA sites never changes any Decomposer count."""
    studies = inputs["studies"]
    sites = inputs["sites"]
    diseases = inputs["diseases"]

    base = build_scopes(studies, sites, diseases)

    # Duplicate every study row and clone every existing MA site, so each study
    # now has >=2 identical rows and each MA study has >=2 MA sites. Distinct-
    # nctId counts must be unchanged.
    dup_studies = studies + [StudyRow(**s.__dict__) for s in studies]
    dup_sites = sites + _duplicate_ma_sites(sites)

    dup = build_scopes(dup_studies, dup_sites, diseases)

    for measure_id, base_scope in base.items():
        dup_scope = dup[measure_id]
        assert ma_studies(dup_scope) == ma_studies(base_scope)
        assert compute_T(dup_scope) == compute_T(base_scope)
        assert phase_overlap_studies(dup_scope) == phase_overlap_studies(base_scope)
        for breakdown in _BREAKDOWNS:
            assert breakdown(dup_scope) == breakdown(base_scope)
