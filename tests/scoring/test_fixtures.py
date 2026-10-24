"""Self-check for the `study_diseases.csv` fixture (Req 2.1, 2.2).

Confirms the fixture carries exactly the data-contract header, is keyed one row
per `(nctId, measureid)` match over the active measures, and covers the
`included`, `questionable`, and `excluded` match statuses so scoring is testable
before Spec 2 lands.
"""
from __future__ import annotations

import csv

from pipeline.scoring.models import MEASURE_IDS
from tests.scoring.conftest import STUDY_DISEASES_COLUMNS


def test_fixture_header_is_exactly_the_contract_columns(study_diseases_path):
    with study_diseases_path.open(newline="", encoding="utf-8") as handle:
        header = tuple(next(csv.reader(handle)))
    assert header == STUDY_DISEASES_COLUMNS


def test_one_row_per_distinct_nctid_measureid_match(disease_matches):
    keys = [(m.nctId, m.measureid) for m in disease_matches]
    assert len(keys) == len(set(keys))


def test_only_active_measures_appear(disease_matches):
    assert {m.measureid for m in disease_matches} <= MEASURE_IDS


def test_all_three_match_statuses_are_covered(disease_matches):
    statuses = {m.match_status for m in disease_matches}
    assert {"included", "questionable", "excluded"} <= statuses


def test_many_to_many_matches_present(disease_matches):
    """At least one study matches more than one measure (many-to-many)."""
    seen: dict[str, int] = {}
    for match in disease_matches:
        seen[match.nctId] = seen.get(match.nctId, 0) + 1
    assert any(count > 1 for count in seen.values())


def test_excluded_rows_carry_a_reason_and_included_rows_do_not(disease_matches):
    for match in disease_matches:
        if match.match_status == "included":
            assert match.exclusion_reason == ""
        elif match.match_status == "excluded":
            assert match.exclusion_reason != ""
