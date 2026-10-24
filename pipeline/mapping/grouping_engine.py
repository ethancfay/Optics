"""Grouping_Engine: one match_status per (nctId, measureid).
Condition-grouping Req 3.7 and 4-8 (design § Grouping_Engine).

Status rules, first that applies wins (Req 7.6):
  1   child_only               (Req 5.3)
  2   healthy_volunteers_only  (Req 6.1, 6.2)
  3a  term exclude, ancestor include + direct exclude  (Req 4.3)
  3b  term exclude, no unmasked include/questionable   (Req 4.2)
  4   unparseable_age          (Req 5.4)
  5   included                 (Req 7.3, 7.4, 4.4)
  6   questionable: Questionable_Term reason or ancestor_only (Req 7.1, 7.2, 7.5)

The Determining_Match (Req 8.6, 8.8) is the minimum of the rule's candidate
matches under `dm_key`; `matched_on` is its source and `matched_term` its
study value as written (Req 8.5).
"""
from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
from typing import Iterable

from pipeline.mapping.age_parser import UNPARSEABLE, parse_max_age
from pipeline.mapping.inputs import Study
from pipeline.mapping.rules_loader import Disease, RulesConfig
from pipeline.mapping.term_matcher import Match, find_matches, normalize

__all__ = ["SOURCE_ORDER", "dm_key", "pick", "StudyDiseaseRow", "decide", "group"]

SOURCE_ORDER = {"mesh": 0, "ancestor": 1, "condition_text": 2}

_CHILD_LIMIT = Fraction(18)
_DIRECT_SOURCES = ("mesh", "condition_text")


def dm_key(m: Match) -> tuple:
    """Req 8.8: source order, then study value, then Normalized_Text of the term."""
    return (SOURCE_ORDER[m.source], m.value, normalize(m.term))


def pick(cands: Iterable[Match]) -> Match:
    """The Determining_Match among `cands` (Req 8.8)."""
    return min(cands, key=dm_key)


@dataclass(frozen=True)
class StudyDiseaseRow:
    nctId: str
    measureid: str
    disease_label: str
    match_status: str
    exclusion_reason: str
    matched_on: str
    matched_term: str


def _reason(disease: Disease, m: Match) -> str:
    """The Rules_Config reason paired with the matched term (Req 8.6 (c), (d), (f))."""
    norm = normalize(m.term)
    for term in disease.terms:
        if term.kind == m.kind and term.norm == norm:
            return term.reason
    raise AssertionError("no Rules_Config term for match %r" % (m,))


def decide(study: Study, disease: Disease, matches: frozenset[Match]) -> StudyDiseaseRow | None:
    """Status, reason and Determining_Match for one (study, disease)."""
    if not matches:
        return None  # Req 3.7

    def row(status: str, reason: str, dm: Match) -> StudyDiseaseRow:
        return StudyDiseaseRow(
            study.nct_id, disease.measureid, disease.label, status, reason, dm.source, dm.value
        )

    by_kind: dict[str, list[Match]] = {"include": [], "exclude": [], "questionable": []}
    for m in matches:
        by_kind[m.kind].append(m)
    excl = by_kind["exclude"]
    quest = by_kind["questionable"]
    # Exclude_Masked_Values: decide rules 3a/3b precedence and which
    # Questionable_Term matches stay rule 6 candidates (Req 4.2, 7.1, 8.6 (f)).
    masked = {(m.source, m.value) for m in excl}
    # Masked_Values: an Exclude_Term or Questionable_Term match on the same
    # value removes its Include_Term matches as evidence (Req 4.1, Open Item 15).
    qmasked = {(m.source, m.value) for m in quest}
    inc_mask = masked | qmasked
    inc_nm = [m for m in by_kind["include"] if (m.source, m.value) not in inc_mask]
    direct = [m for m in inc_nm if m.source in _DIRECT_SOURCES]
    anc = [m for m in inc_nm if m.source == "ancestor"]
    excl_direct = [m for m in excl if m.source in _DIRECT_SOURCES]
    q_nm = [m for m in quest if (m.source, m.value) not in masked]
    age = parse_max_age(study.maximum_age)

    # 1. Child-only (Req 5.3, 8.6 (b))
    if isinstance(age, Fraction) and age < _CHILD_LIMIT:
        return row("excluded", "child_only", pick(inc_nm or matches))
    # 2. Healthy volunteers without a direct unmasked include (Req 6.1, 6.3, 8.6 (e))
    if study.healthy_volunteers == "true" and not direct:
        return row("excluded", "healthy_volunteers_only", pick(matches))
    # 3a. Direct exclude, include evidence only in ancestorTerms (Req 4.3, 8.6 (d))
    if excl_direct and not direct and anc:
        dm = pick(excl_direct)
        return row("excluded", _reason(disease, dm), dm)
    # 3b. Exclude with no unmasked include or questionable match (Req 4.2, 8.6 (c))
    if excl and not inc_nm and not q_nm:
        dm = pick(excl)
        return row("excluded", _reason(disease, dm), dm)
    # 4. Unparseable maximumAge (Req 5.4, 8.6 (b))
    if age == UNPARSEABLE:
        return row("questionable", "unparseable_age", pick(inc_nm or matches))
    # 5. Included (Req 7.3, 7.4, 4.4, 8.6 (a))
    ancestor_included = disease.ancestor_only_status == "included"
    evidence = direct or (anc if ancestor_included else [])
    if evidence:
        return row("included", "", pick(evidence))
    # 6. Questionable (Req 7.1, 7.2, 7.5, 8.6 (f), (g)). Candidates are the
    # Questionable_Term matches on values that are not Exclude_Masked_Values
    # (questionable-masked values keep theirs) plus, under Ancestor_Only_Status
    # `questionable`, the unmasked ancestor include matches. Reaching here means
    # rule 3b did not fire and there is no evidence, so one of them is non-empty.
    cands = q_nm + ([] if ancestor_included else anc)
    assert cands, "rule 6 reached with no questionable or ancestor candidates"
    dm = pick(cands)
    reason = "ancestor_only" if dm.kind == "include" else _reason(disease, dm)
    return row("questionable", reason, dm)


def group(studies: dict[str, Study], rules: RulesConfig) -> list[StudyDiseaseRow]:
    """Every Study_Disease_Row, sorted by (nctId, measureid) (Req 8.1)."""
    rows: list[StudyDiseaseRow] = []
    for study in studies.values():
        for disease in rules.diseases:
            r = decide(study, disease, find_matches(study, disease))
            if r is not None:
                rows.append(r)
    rows.sort(key=lambda r: (r.nctId, r.measureid))
    return rows
