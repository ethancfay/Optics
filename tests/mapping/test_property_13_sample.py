"""Property 13: Deterministic precision sample (design § Correctness Properties).

**Validates: Requirements 11.5, 11.1, 11.4**
"""
from __future__ import annotations

import io

from hypothesis import given, settings
from hypothesis import strategies as st

from pipeline.mapping.grouping_engine import StudyDiseaseRow
from pipeline.mapping.precision_sampler import HEADER, SAMPLE_SIZE, build, candidates, select
from pipeline.mapping.rules_loader import SUPPORTED_MEASURES, validate
from tests.mapping.strategies import (
    REASON_CODES,
    VOCABULARY,
    ma_site_ids,
    rules_dicts,
    seeds,
    study_lists,
)

STATUSES = ("included", "excluded", "questionable", None)


@st.composite
def sample_inputs(draw):
    """Rules dicts, seed, studies (up to 40, so n > 20 occurs), MA ids and rows.

    Rows are generated for every supported measureid, including ones absent
    from the Rules_Config, with many `included` rows.
    """
    diseases, seed = draw(rules_dicts())
    study_list = draw(st.one_of(study_lists(min_size=0, max_size=8),
                                study_lists(min_size=21, max_size=40)))
    every = frozenset(s.nct_id for s in study_list)
    ma = draw(st.one_of(ma_site_ids(study_list), st.just(every)))
    status = st.sampled_from(STATUSES)
    rows: list[StudyDiseaseRow] = []
    for study in study_list:
        for mid in SUPPORTED_MEASURES:
            s = draw(st.one_of(st.just("included"), st.just("included"), status))
            if s is None:
                continue
            rows.append(StudyDiseaseRow(
                nctId=study.nct_id, measureid=mid, disease_label="label",
                match_status=s,
                exclusion_reason="" if s == "included" else draw(st.sampled_from(REASON_CODES)),
                matched_on=draw(st.sampled_from(("mesh", "ancestor", "condition_text"))),
                matched_term=draw(st.sampled_from(VOCABULARY)),
            ))
    rows = draw(st.permutations(rows))
    return diseases, seed, study_list, ma, rows


def _build(diseases, seed, rows, studies, ma):
    return build(validate(diseases, seed), rows, studies, ma, stderr=io.StringIO())


# Feature: condition-grouping, Property 13: Deterministic precision sample
@settings(max_examples=100, deadline=None)
@given(cands=st.lists(st.sampled_from(["NCT%08d" % i for i in range(60)]), unique=True)
       .map(sorted), seed=seeds)
def test_select_is_deterministic_and_sized(cands, seed):
    first = select(cands, seed)
    assert select(list(cands), seed) == first
    assert len(first) == min(SAMPLE_SIZE, len(cands))
    assert len(set(first)) == len(first)
    assert set(first) <= set(cands)


# Feature: condition-grouping, Property 13: Deterministic precision sample
@settings(max_examples=100, deadline=None)
@given(data=sample_inputs())
def test_build_is_deterministic_independent_and_copies_cells(data):
    diseases, seed, study_list, ma, rows = data
    studies = {s.nct_id: s for s in study_list}
    table = _build(diseases, seed, rows, studies, ma)

    # Repeated runs give identical output (Req 11.5).
    again = _build(diseases, seed, list(reversed(rows)), dict(reversed(studies.items())), ma)
    assert table.header == HEADER
    assert again.rows == table.rows
    assert table.rows == sorted(table.rows, key=lambda c: (c[1], c[0]))

    by_key = {(r.nctId, r.measureid): r for r in rows}
    for disease in diseases:
        mid = disease["measureid"]
        cands = candidates(rows, ma, mid)
        picked = [c for c in table.rows if c[1] == mid]
        ids = [c[0] for c in picked]
        # min(20, n) distinct candidates, the seeded selection (Req 11.1).
        assert len(ids) == len(set(ids)) == min(SAMPLE_SIZE, len(cands))
        assert sorted(ids) == sorted(select(cands, seed))
        # Removing every other disease leaves this disease's rows unchanged (Req 11.5).
        alone = _build([disease], seed, rows, studies, ma)
        assert alone.rows == picked

    # Adding the remaining supported diseases does not change existing ones (Req 11.5).
    present = {d["measureid"] for d in diseases}
    extra = [dict(diseases[0], measureid=m) for m in SUPPORTED_MEASURES if m not in present]
    bigger = _build(diseases + extra, seed, rows, studies, ma)
    assert [c for c in bigger.rows if c[1] in present] == table.rows

    # Copied cells equal their source (Req 11.4).
    for nct, mid, title, conditions, term, url, correct in table.rows:
        study = studies[nct]
        assert nct in ma
        assert by_key[(nct, mid)].match_status == "included"
        assert title == study.brief_title
        assert conditions == study.conditions_cell
        assert url == study.source_url
        assert term == by_key[(nct, mid)].matched_term
        assert correct == ""
