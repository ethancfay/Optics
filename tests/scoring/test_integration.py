"""End-to-end integration test for the Scoring & Export stage (task 11.1).

Wires every component together through the public entry point
`pipeline.scoring.export.run(processed_dir, web_data_dir, study_diseases_dir)`.
It builds a full input fixture set in a temp `processed/` directory — the three
Spec 1 CSVs (`studies.csv`, `sites.csv`, `places_ma.csv`), `fetch_log.json`, and
a Spec 2 `study_diseases.csv` — runs the exporter into a temp
`web/public/data/`, and asserts the stage's observable contract:

- the run exits 0 (Req 1.1, 1.2);
- exactly the four contract files land in `web/public/data/`
  (`what.json`, `investigate.json`, `evidence.json`, `sources.json`), and the
  Deferred_Files `where.json` / `ma_counties.geojson` are never written
  (Req 3.1, 3.3);
- the three array files are ordered ascending by `measure_id`
  (CASTHMA, DIABETES, HIGHCHOL), one entry per active measure (Req 3.1, 8.1);
- per-disease entries carry the expected shape: a measure with real MA
  included+recruiting studies and a full 14-county PLACES set has `t > 0` and
  computed burden numbers, while a measure absent from PLACES has `null` burden
  numbers and a `missing_data_notes` entry (Req 1.6, 4.9);
- `sources.json` is real output (`is_sample is False`; Req 3.2).

Input CSV bytes are produced from the Spec 1 row dataclasses via the shared
`pipeline.io.csv_writer` serialization, so headers and JSON-array list cells
match exactly what the Readers validate.
"""
from __future__ import annotations

import json
from pathlib import Path

from pipeline.io.csv_writer import encode_rows, serialize
from pipeline.scoring.export import run
from pipeline.transform.places_transformer import PlacesRow
from pipeline.transform.study_transformer import SiteRow, StudyRow

# The 14 Massachusetts counties (locationname / 5-digit County_FIPS). A full
# county set for a measure makes the scoring engine compute a real index.
MA_COUNTIES: tuple[tuple[str, str], ...] = (
    ("Barnstable", "25001"),
    ("Berkshire", "25003"),
    ("Bristol", "25005"),
    ("Dukes", "25007"),
    ("Essex", "25009"),
    ("Franklin", "25011"),
    ("Hampden", "25013"),
    ("Hampshire", "25015"),
    ("Middlesex", "25017"),
    ("Nantucket", "25019"),
    ("Norfolk", "25021"),
    ("Plymouth", "25023"),
    ("Suffolk", "25025"),
    ("Worcester", "25027"),
)

CONTRACT_FILES = ("what.json", "investigate.json", "evidence.json", "sources.json")
DEFERRED_FILES = ("where.json", "ma_counties.geojson")


# --------------------------------------------------------------------------- #
# Row builders — state only the fields each fixture row exercises.
# --------------------------------------------------------------------------- #
def _study(
    nct_id: str,
    *,
    overall_status: str = "RECRUITING",
    study_type: str = "INTERVENTIONAL",
    phases: list[str] | None = None,
    intervention_types: list[str] | None = None,
    intervention_names: list[str] | None = None,
    brief_title: str = "a study",
) -> StudyRow:
    return StudyRow(
        nctId=nct_id,
        briefTitle=brief_title,
        overallStatus=overall_status,
        studyType=study_type,
        phases=phases if phases is not None else [],
        healthyVolunteers="",
        minimumAge="",
        maximumAge="",
        stdAges=[],
        conditions=[],
        interventionTypes=intervention_types if intervention_types is not None else [],
        interventionNames=intervention_names if intervention_names is not None else [],
        meshTerms=[],
        meshIds=[],
        ancestorTerms=[],
        ancestorIds=[],
        lastUpdatePostDate="",
        source_url="https://clinicaltrials.gov/study/" + nct_id,
    )


def _site(
    nct_id: str,
    *,
    state: str = "Massachusetts",
    site_status: str = "RECRUITING",
    facility: str = "a clinic",
    city: str = "boston",
    zip_code: str = "02115",
) -> SiteRow:
    return SiteRow(
        nctId=nct_id,
        facility=facility,
        city=city,
        state=state,
        zip=zip_code,
        latitude="42.0",
        longitude="-71.0",
        siteStatus=site_status,
        location_quality="ok",
    )


def _places_row(
    county: tuple[str, str],
    measure_id: str,
    *,
    data_value: str,
    low: str,
    high: str,
    pop18: str,
    year: str = "2023",
) -> PlacesRow:
    locationname, fips = county
    return PlacesRow(
        locationname=locationname,
        locationid=fips,
        measureid=measure_id,
        measure="crude prevalence",
        data_value=data_value,
        low_confidence_limit=low,
        high_confidence_limit=high,
        totalpop18plus=pop18,
        latitude="42.0",
        longitude="-71.0",
        year=year,
    )


def _full_county_set(
    measure_id: str, *, data_value: str, low: str, high: str, pop18: str
) -> list[PlacesRow]:
    """A PLACES row for every one of the 14 MA counties for one measure."""
    return [
        _places_row(county, measure_id, data_value=data_value, low=low, high=high, pop18=pop18)
        for county in MA_COUNTIES
    ]


# --------------------------------------------------------------------------- #
# Fixture fabrication — write the five input files into a processed dir.
# --------------------------------------------------------------------------- #
def _write_csv(path: Path, kind: str, rows: list[object]) -> None:
    """Serialize rows through the Spec 1 CSV_Writer so headers/list cells match."""
    path.write_bytes(serialize(encode_rows(kind, rows)))


def _build_inputs(processed_dir: Path) -> None:
    """Write studies.csv, sites.csv, places_ma.csv, fetch_log.json, study_diseases.csv.

    Coverage, by measure:
    - CASTHMA : one MA included+recruiting study with a RECRUITING MA site, plus
      a full 14-county PLACES set -> t == 1 and a computed burden index.
    - DIABETES: one MA included+recruiting study (multi-phase, DRUG intervention)
      with a RECRUITING MA site, plus a full 14-county PLACES set -> t == 1.
    - HIGHCHOL: one MA included study, but the measure is ABSENT from PLACES ->
      null burden numbers and a missing_data_notes entry.
    A questionable match and a non-MA study are included as negative controls
    that must not appear in any eligible scope.
    """
    studies = [
        _study("NCT00000001"),                                   # CASTHMA eligible+T
        _study(
            "NCT00000002",
            phases=["PHASE2", "PHASE3"],
            intervention_types=["DRUG"],
            intervention_names=["metformin"],
        ),                                                       # DIABETES eligible+T
        _study("NCT00000003"),                                   # HIGHCHOL eligible (no PLACES)
        _study("NCT00000004"),                                   # questionable -> not eligible
        _study("NCT00000005"),                                   # non-MA -> not eligible
    ]

    sites = [
        _site("NCT00000001"),                                    # recruiting MA site
        _site("NCT00000002"),                                    # recruiting MA site
        _site("NCT00000003", site_status="NOT_YET_RECRUITING"),  # MA site, not recruiting
        _site("NCT00000004"),                                    # MA site (match is questionable)
        _site("NCT00000005", state="California", site_status="RECRUITING"),  # non-MA
    ]

    # DIABETES and CASTHMA present with a full 14-county set; HIGHCHOL absent.
    places = _full_county_set(
        "CASTHMA", data_value="10.0", low="9.0", high="11.0", pop18="100000"
    ) + _full_county_set(
        "DIABETES", data_value="8.0", low="7.0", high="9.0", pop18="100000"
    )

    disease_rows = [
        ("NCT00000001", "CASTHMA", "Asthma", "included", "", "mesh", "Asthma"),
        ("NCT00000002", "DIABETES", "Diabetes", "included", "", "mesh", "Diabetes Mellitus"),
        ("NCT00000003", "HIGHCHOL", "High Cholesterol", "included", "", "mesh", "Hypercholesterolemia"),
        ("NCT00000004", "CASTHMA", "Reactive Airway", "questionable", "", "ancestor", "Hypersensitivity"),
        ("NCT00000005", "DIABETES", "Diabetes", "included", "", "mesh", "Diabetes Mellitus"),
    ]

    _write_csv(processed_dir / "studies.csv", "studies", studies)
    _write_csv(processed_dir / "sites.csv", "sites", sites)
    _write_csv(processed_dir / "places_ma.csv", "places", places)

    header = "nctId,measureid,disease_label,match_status,exclusion_reason,matched_on,matched_term"
    lines = [header] + [",".join(row) for row in disease_rows]
    (processed_dir / "study_diseases.csv").write_text(
        "\n".join(lines) + "\n", encoding="utf-8"
    )

    fetch_log = {
        "fetch_date": "2026-10-24T18:12:26Z",
        "run_started_at": "2026-10-24T18:38:40Z",
        "urls": {
            "clinicaltrials_gov": ["https://clinicaltrials.gov/api/v2/studies?x=1"],
            "cdc_places": ["https://data.cdc.gov/resource/swc5-untb.json?y=2"],
        },
    }
    (processed_dir / "fetch_log.json").write_text(
        json.dumps(fetch_log), encoding="utf-8"
    )


def _load(web_data_dir: Path, name: str) -> object:
    return json.loads((web_data_dir / name).read_text(encoding="utf-8"))


# --------------------------------------------------------------------------- #
# The end-to-end test.
# --------------------------------------------------------------------------- #
def test_end_to_end_export_writes_four_ordered_files(tmp_path: Path) -> None:
    processed_dir = tmp_path / "processed"
    processed_dir.mkdir()
    web_data_dir = tmp_path / "web" / "public" / "data"

    _build_inputs(processed_dir)

    # study_diseases.csv lives in processed_dir, so no separate fixture dir.
    exit_code = run(processed_dir, web_data_dir)

    # --- Req 1.1, 1.2: the run succeeds. ------------------------------------
    assert exit_code == 0

    # --- Req 3.1, 3.3: exactly the four contract files, no Deferred_Files. ---
    for name in CONTRACT_FILES:
        assert (web_data_dir / name).is_file(), f"{name} should be written"
    for name in DEFERRED_FILES:
        assert not (web_data_dir / name).exists(), f"{name} must not be written"
    assert {p.name for p in web_data_dir.iterdir()} == set(CONTRACT_FILES)

    what = _load(web_data_dir, "what.json")
    investigate = _load(web_data_dir, "investigate.json")
    evidence = _load(web_data_dir, "evidence.json")
    sources = _load(web_data_dir, "sources.json")

    # --- Req 3.1, 8.1: three arrays, one entry per measure, ordered. --------
    expected_order = ["CASTHMA", "DIABETES", "HIGHCHOL"]
    for array in (what, investigate, evidence):
        assert isinstance(array, list)
        assert [entry["measure_id"] for entry in array] == expected_order

    what_by_id = {entry["measure_id"]: entry for entry in what}
    investigate_by_id = {entry["measure_id"]: entry for entry in investigate}
    evidence_by_id = {entry["measure_id"]: entry for entry in evidence}

    # --- CASTHMA: full PLACES + recruiting MA study -> t>0, computed index. --
    casthma = what_by_id["CASTHMA"]
    assert casthma["condition"] == "Asthma"
    assert casthma["t"] == 1
    assert casthma["adults_18plus"] == 14 * 100000
    assert casthma["p"] is not None
    assert casthma["low"] is not None
    assert casthma["mid"] is not None
    assert casthma["high"] is not None
    assert casthma["low"] <= casthma["mid"] <= casthma["high"]
    assert casthma["affected_adults"] is not None

    # --- DIABETES: full PLACES + recruiting multi-phase DRUG study. ----------
    diabetes = what_by_id["DIABETES"]
    assert diabetes["condition"] == "Diabetes"
    assert diabetes["t"] == 1
    assert diabetes["adults_18plus"] == 14 * 100000
    assert diabetes["mid"] is not None
    diabetes_inv = investigate_by_id["DIABETES"]
    assert diabetes_inv["us_studies"] is None
    assert diabetes_inv["ma_studies"] == 1
    assert diabetes_inv["phase_overlap_studies"] == 1
    drug_labels = {row["label"] for row in diabetes_inv["by_intervention_type"]}
    assert "Drug" in drug_labels
    # every investigate entry has exactly one mandatory funding finding
    for entry in investigate:
        labels = [f["label"] for f in entry["findings"]]
        assert labels.count("cannot determine from public data") == 1

    # --- HIGHCHOL: absent from PLACES -> null burden, missing_data_notes. ----
    highchol = what_by_id["HIGHCHOL"]
    assert highchol["condition"] == "High Cholesterol"
    assert highchol["adults_18plus"] is None
    assert highchol["p"] is None
    assert highchol["low"] is None and highchol["mid"] is None and highchol["high"] is None
    assert highchol["affected_adults"] is None
    # its MA site is NOT_YET_RECRUITING, so it never counts toward T (Req 4.2):
    # t is a real count of 0, never null.
    assert highchol["t"] == 0
    highchol_ev = evidence_by_id["HIGHCHOL"]
    assert len(highchol_ev["missing_data_notes"]) == 1
    assert "HIGHCHOL" in highchol_ev["missing_data_notes"][0]
    # present measures carry no missing-data note.
    assert evidence_by_id["CASTHMA"]["missing_data_notes"] == []
    assert evidence_by_id["DIABETES"]["missing_data_notes"] == []

    # --- evidence ncts list the eligible MA studies. ------------------------
    assert [row["nct_id"] for row in evidence_by_id["CASTHMA"]["ncts"]] == ["NCT00000001"]
    assert [row["nct_id"] for row in evidence_by_id["DIABETES"]["ncts"]] == ["NCT00000002"]
    assert [row["nct_id"] for row in evidence_by_id["HIGHCHOL"]["ncts"]] == ["NCT00000003"]

    # --- Req 3.2: sources.json is real output. ------------------------------
    assert sources["is_sample"] is False
    assert sources["data_as_of"] == "2026-10-24"
    assert set(sources["prevalence_years"]) == {"CASTHMA", "DIABETES", "HIGHCHOL"}
