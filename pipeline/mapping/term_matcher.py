"""Term_Matcher: match Rules_Config terms against a study's list columns.

Condition-grouping Req 3 (design § Term_Matcher).

- `meshTerms` and `ancestorTerms` use Exact_Match (equal Normalized_Text).
- `conditions` uses Phrase_Match (term occurs with a word boundary on both
  sides; a boundary is the string edge or a character that is not a letter
  or digit).
- Only these three columns are searched (Req 3.5). Values whose
  Normalized_Text is empty are skipped (Req 3.6).
"""
from __future__ import annotations

from dataclasses import dataclass

from pipeline.mapping.inputs import Study
from pipeline.mapping.rules_loader import Disease, normalize

__all__ = ["Match", "normalize", "exact_match", "phrase_match", "find_matches"]


def exact_match(term_norm: str, value_norm: str) -> bool:
    """Exact_Match on already-normalized strings."""
    return term_norm == value_norm


def phrase_match(term_norm: str, value_norm: str) -> bool:
    """Phrase_Match on already-normalized strings.

    Checks every occurrence of `term_norm` in `value_norm`, so a later
    occurrence with word boundaries still matches when an earlier one does not.
    """
    if not term_norm:
        return False
    n = len(term_norm)
    start = value_norm.find(term_norm)
    while start != -1:
        end = start + n
        left_ok = start == 0 or not value_norm[start - 1].isalnum()
        right_ok = end == len(value_norm) or not value_norm[end].isalnum()
        if left_ok and right_ok:
            return True
        start = value_norm.find(term_norm, start + 1)
    return False


@dataclass(frozen=True, order=True)
class Match:
    measureid: str
    kind: str    # include | exclude | questionable
    term: str    # Rules_Config term text
    source: str  # mesh | ancestor | condition_text
    value: str   # study list value exactly as written in studies.csv


def _normalized(values: tuple[str, ...]) -> list[tuple[str, str]]:
    """(value as written, Normalized_Text) pairs, skipping empty Normalized_Text."""
    out = []
    for value in values:
        norm = normalize(value)
        if norm:
            out.append((value, norm))
    return out


def find_matches(study: Study, disease: Disease) -> frozenset[Match]:
    """Every distinct (measureid, kind, term, source, value) match (Req 3.1-3.3)."""
    columns = (
        ("mesh", _normalized(study.mesh_terms), exact_match),
        ("ancestor", _normalized(study.ancestor_terms), exact_match),
        ("condition_text", _normalized(study.conditions), phrase_match),
    )
    found: set[Match] = set()
    for source, values, matcher in columns:
        for value, value_norm in values:
            for term in disease.terms:
                if matcher(term.norm, value_norm):
                    found.add(Match(disease.measureid, term.kind, term.text, source, value))
    return frozenset(found)
