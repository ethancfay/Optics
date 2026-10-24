"""Unit tests for the Readers (design § Component 1: Readers; Req 2.1-2.6).

Covers:
- loading the checked-in `study_diseases.csv` fixture into `DiseaseMatch` rows
  (Req 2.1, 2.2);
- the absent-file error naming `study_diseases.csv` (Req 2.5);
- fixture-directory precedence over `pipeline/processed/` (Req 2.1);
- the header-mismatch error naming the file without quoting cell content
  (Req 2.6);
- the invalid-JSON list-cell error naming file, column, and nctId, never the
  cell content (Req 2.4).
"""
from __future__ import annotations

import pytest

from pipeline.errors import PipelineError
from pipeline.io.csv_writer import COLUMNS, LIST_COLUMNS
from pipeline.scoring.models import DiseaseMatch
from pipeline.scoring.readers import (
    STUDY_DISEASES_COLUMNS,
    STUDY_DISEASES_FILE_NAME,
    load_studies,
    load_study_diseases,
    resolve_study_diseases_path,
)


# --- study_diseases.csv fixture load success (Req 2.1, 2.2) ----------------------

def test_load_study_diseases_fixture_decodes_every_row(study_diseases_path,
                                                        disease_matches):
    loaded = load_study_diseases(study_diseases_path)
    assert loaded == disease_matches
    assert all(isinstance(m, DiseaseMatch) for m in loaded)
    assert len(loaded) == 10


def test_load_study_diseases_populates_contract_fields(study_diseases_path):
    first = load_study_diseases(study_diseases_path)[0]
    assert first.nctId == "NCT00000001"
    assert first.measureid == "CASTHMA"
    assert first.match_status == "included"
    assert first.exclusion_reason == ""


# --- absent file error names study_diseases.csv (Req 2.5) ------------------------

def test_absent_study_diseases_raises_naming_the_file(tmp_path):
    missing = tmp_path / STUDY_DISEASES_FILE_NAME
    with pytest.raises(PipelineError) as err:
        load_study_diseases(missing)
    message = str(err.value)
    assert STUDY_DISEASES_FILE_NAME in message
    assert "absent" in message


# --- fixture-directory precedence (Req 2.1) --------------------------------------

def test_fixture_dir_takes_precedence_over_processed_dir(tmp_path):
    processed = tmp_path / "processed"
    fixtures = tmp_path / "fixtures"
    resolved = resolve_study_diseases_path(processed, fixtures)
    assert resolved == str(fixtures / STUDY_DISEASES_FILE_NAME)


def test_processed_dir_used_when_no_fixture_dir(tmp_path):
    processed = tmp_path / "processed"
    resolved = resolve_study_diseases_path(processed)
    assert resolved == str(processed / STUDY_DISEASES_FILE_NAME)


def test_resolved_fixture_path_loads_through_the_reader(study_diseases_dir,
                                                        disease_matches, tmp_path):
    processed = tmp_path / "processed"
    resolved = resolve_study_diseases_path(processed, study_diseases_dir)
    assert load_study_diseases(resolved) == disease_matches


# --- header mismatch error names the file, no cell content (Req 2.6) -------------

def test_header_mismatch_names_file_without_cell_content(tmp_path):
    path = tmp_path / STUDY_DISEASES_FILE_NAME
    path.write_text("a,b,c\nSECRET,SECRET,SECRET\n", encoding="utf-8")
    with pytest.raises(PipelineError) as err:
        load_study_diseases(path)
    message = str(err.value)
    assert STUDY_DISEASES_FILE_NAME in message
    assert "header" in message
    assert "SECRET" not in message


def test_empty_file_is_a_header_mismatch(tmp_path):
    path = tmp_path / STUDY_DISEASES_FILE_NAME
    path.write_text("", encoding="utf-8")
    with pytest.raises(PipelineError, match="header"):
        load_study_diseases(path)


def test_studies_header_mismatch_names_file_without_cell_content(tmp_path):
    path = tmp_path / "studies.csv"
    path.write_text("x,y\nSECRET,SECRET\n", encoding="utf-8")
    with pytest.raises(PipelineError) as err:
        load_studies(path)
    message = str(err.value)
    assert "studies.csv" in message
    assert "header" in message
    assert "SECRET" not in message


# --- invalid-JSON list cell names file/column/nctId, never cell content (Req 2.4) ---

def _studies_bytes(overrides: dict[str, str]) -> str:
    """One studies.csv header + row; list columns default to a valid `[]` so a
    test can make exactly one cell invalid without tripping another column."""
    columns = COLUMNS["studies"]
    list_columns = LIST_COLUMNS["studies"]

    def cell(column: str) -> str:
        if column in overrides:
            return overrides[column]
        return "[]" if column in list_columns else ""

    header = ",".join(columns)
    row = ",".join(cell(column) for column in columns)
    return header + "\n" + row + "\n"


def test_invalid_json_list_cell_names_file_column_and_nctid(tmp_path):
    path = tmp_path / "studies.csv"
    path.write_text(
        _studies_bytes({"nctId": "NCT42", "phases": "SECRET"}),
        encoding="utf-8",
    )
    with pytest.raises(PipelineError) as err:
        load_studies(path)
    message = str(err.value)
    assert "studies.csv" in message
    assert "phases" in message
    assert "NCT42" in message
    assert "SECRET" not in message


def test_empty_list_cell_decodes_to_empty_list(tmp_path):
    path = tmp_path / "studies.csv"
    path.write_text(
        _studies_bytes({"nctId": "NCT7", "phases": "[]"}),
        encoding="utf-8",
    )
    rows = load_studies(path)
    assert rows[0].phases == []
