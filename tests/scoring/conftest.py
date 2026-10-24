"""Scoring test fixtures (Req 2.1, 2.2).

`study_diseases.csv` is produced by Spec 2 (condition grouping), which has not
yet landed. These fixtures supply a checked-in fixture file carrying exactly the
data-contract columns so the Scoring & Export stage is fully testable now, and
expose it two ways:

- `study_diseases_dir` / `study_diseases_path`: the fixture directory and the CSV
  file, for tests that exercise the Readers' fixture-directory precedence
  (task 2.1) once that module lands.
- `disease_matches`: the same file already decoded to `DiseaseMatch` rows using
  the stdlib `csv` module, so scoring logic can be tested before the Readers
  exist.

The file has one row per `(nctId, measureid)` match over the active measures
CASTHMA / HIGHCHOL / DIABETES, covering `included`, `questionable`, and
`excluded` rows and many-to-many matches (a study matching several measures).
"""
from __future__ import annotations

import csv
from pathlib import Path

import pytest

from pipeline.scoring.models import DiseaseMatch

# Exactly the data-contract columns, in order (Req 2.2; data-contract § Spec 2).
STUDY_DISEASES_COLUMNS: tuple[str, ...] = (
    "nctId",
    "measureid",
    "disease_label",
    "match_status",
    "exclusion_reason",
    "matched_on",
    "matched_term",
)

FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture
def study_diseases_dir() -> Path:
    """Directory holding the checked-in `study_diseases.csv` fixture."""
    return FIXTURES_DIR


@pytest.fixture
def study_diseases_path(study_diseases_dir: Path) -> Path:
    """Path to the checked-in `study_diseases.csv` fixture."""
    return study_diseases_dir / "study_diseases.csv"


def load_disease_matches(path: Path) -> list[DiseaseMatch]:
    """Decode a `study_diseases.csv` file into `DiseaseMatch` rows with the stdlib csv module."""
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        if tuple(reader.fieldnames or ()) != STUDY_DISEASES_COLUMNS:
            raise AssertionError(
                "study_diseases.csv fixture header must be exactly %s"
                % (STUDY_DISEASES_COLUMNS,)
            )
        return [
            DiseaseMatch(
                nctId=row["nctId"],
                measureid=row["measureid"],
                disease_label=row["disease_label"],
                match_status=row["match_status"],
                exclusion_reason=row["exclusion_reason"],
                matched_on=row["matched_on"],
                matched_term=row["matched_term"],
            )
            for row in reader
        ]


@pytest.fixture
def disease_matches(study_diseases_path: Path) -> list[DiseaseMatch]:
    """The fixture file decoded to `DiseaseMatch` rows."""
    return load_disease_matches(study_diseases_path)
