# Implementation Plan: Scoring & Export (Spec 3)

## Overview

This plan implements the local, offline Scoring & Export stage described in
`design.md` and `requirements.md`, with `data-contract.md` as the source of
truth for every key, definition, and formula. Implementation language is
Python 3.11 (per `tech.md` and the design's Part B notation).

The plan is incremental and test-driven where practical: it starts with shared
types and Hypothesis strategies, then builds each of the eight design components
(Readers, MA_Index_Builder, Scoring_Engine, Decomposer, Findings_Generator,
Evidence_Builder, Sources_Builder, PII_Check + Atomic_JSON_Writer), and ends by
wiring them into the `python -m pipeline.scoring.export` entry point with no
orphaned code. Modules live under `pipeline/scoring/`; tests mirror them under
`tests/scoring/`. Existing conventions are reused throughout:
`pipeline.errors.PipelineError`, `pipeline.patterns`, `pipeline.io.csv_reader`,
`pipeline.io.atomic`, the Spec 1 row dataclasses (`StudyRow`, `SiteRow`,
`PlacesRow`), and `pipeline.transform.pii_guard`.

Tasks marked with `*` are optional test sub-tasks and can be skipped for a
faster first pass; the five property-based tests implement Requirement 9.

## Tasks

- [ ] 1. Set up scoring package, shared types, and the study_diseases fixture
  - [ ] 1.1 Create the `pipeline/scoring/` package and shared data models
    - Add `pipeline/scoring/__init__.py` and `pipeline/scoring/models.py`
    - Define the frozen dataclasses `DiseaseMatch` (study_diseases.csv row: `nctId`, `measureid`, `disease_label`, `match_status`, `exclusion_reason`, `matched_on`, `matched_term`), `Prevalence` (`p`, `p_low`, `p_high`, `year`), and `DiseaseScope` (`measure_id`, `condition`, `eligible_ids: set[str]`, `t_ids: set[str]`, `studies_by_id: dict[str, StudyRow]`) exactly as in design § Data Models
    - Define the active `MEASURE_IDS` set (`CASTHMA`, `HIGHCHOL`, `DIABETES`) and the `measure_id -> condition` label map used for `condition` and `ctgov_url`
    - _Requirements: 2.2, 3.1_

  - [ ] 1.2 Create the `tests/scoring/` test package and a `study_diseases.csv` fixture
    - Add `tests/scoring/__init__.py`
    - Write a fixture file (and/or a pytest fixture) producing a `study_diseases.csv` with exactly the data-contract header `nctId,measureid,disease_label,match_status,exclusion_reason,matched_on,matched_term`, one row per `(nctId, measureid)` match, covering `included`, `questionable`, and `excluded` rows
    - Place the fixture in a test directory (any directory) so scoring is testable before Spec 2 lands
    - _Requirements: 2.1, 2.2_

  - [ ]* 1.3 Extend `tests/strategies.py` with scoring input strategies
    - Add Hypothesis strategies that build lists of Spec 1 `StudyRow` / `SiteRow` / `PlacesRow` and `DiseaseMatch` from a small shared `nctId` pool so duplicate study rows, multiple MA sites per study, and many-to-many disease matches are common
    - Vary site `state` (Massachusetts / `ma` / other / blank), site status, `overallStatus`, `phases` (empty, single, multi, "NA"), `interventionTypes` (empty, single, repeated, multi), `studyType`, and PLACES `totalpop18plus` / `data_value` / `low_confidence_limit` / `high_confidence_limit` / `year` with confidence limits ordered so `p_low <= p <= p_high` is reachable, plus degenerate cases (missing measure, zero population, county count != 14)
    - Only lowercase/safe text and non-PII values so generated output never matches the email/phone patterns by chance
    - _Requirements: 9.1, 9.2, 9.3, 9.4, 9.5_

- [ ] 2. Implement the Readers
  - [ ] 2.1 Implement `pipeline/scoring/readers.py`
    - Implement `load_studies`, `load_sites`, `load_places` reusing `pipeline.io.csv_reader` conventions (header validation + JSON-array list columns)
    - Implement `load_study_diseases(path)` with a dedicated reader validating exactly the contract columns and decoding one row to a `DiseaseMatch`; when the file is absent, raise `PipelineError` naming `study_diseases.csv`; accept a configured fixture directory that takes precedence over `pipeline/processed/`
    - Implement `load_fetch_log(path)` loading `fetch_log.json`
    - On header mismatch or a list cell that is not valid JSON, raise `PipelineError` naming the file, column, and nctId without quoting cell content; leave `web/public/data/` unchanged
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 2.6, 1.6_

  - [ ]* 2.2 Write unit tests for the Readers
    - Test fixture load success, absent `study_diseases.csv` error, fixture-directory precedence, header mismatch error, and invalid-JSON list-cell error (message names file/column/nctId, never cell content)
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 2.6_

- [ ] 3. Implement the MA_Index_Builder
  - [ ] 3.1 Implement `pipeline/scoring/index.py`
    - Implement `ma_study_ids(studies, sites)` using the MA study definition (case-insensitive `massachusetts`/`ma`, matching `sanity_checker` MA-state handling)
    - Implement `recruiting_ma_site_ids(sites)` returning studies with >=1 MA site whose own site status is `RECRUITING` (absent/empty/other site status never counts)
    - Implement `build_scopes(studies, sites, diseases) -> dict[str, DiseaseScope]`: eligible = MA studies with `match_status == "included"` per measure; `t_ids` = eligible studies with `overallStatus == "RECRUITING"` intersected with recruiting MA sites; populate `studies_by_id`
    - _Requirements: 4.1, 4.2, 5.1, 5.7_

  - [ ]* 3.2 Write unit tests for the MA_Index_Builder
    - Test MA detection, `included`-only eligibility, T-eligible subset rules, and that unknown/blank site status never contributes to `t_ids`
    - _Requirements: 4.1, 4.2, 5.1_

- [ ] 4. Implement the Scoring_Engine
  - [ ] 4.1 Implement `pipeline/scoring/scoring.py`
    - Implement `compute_T(scope)` as `len(scope.t_ids)` (distinct nctId)
    - Implement `compute_N(places, measure_id)` summing `totalpop18plus` over distinct MA counties present, returning `None` when the measure is absent
    - Implement `compute_prevalence(places, measure_id)` returning population-weighted fractions `p`, `p_low`, `p_high` via `sum(pop18 * value/100)/sum(pop18)` and the measure's `year`; return `None` when the measure is absent or total pop is 0
    - Implement `population_weighted_index(T, N, prev)` with `low = T/(N*p_high)*100000`, `high = T/(N*p_low)*100000`, `mid = T/(N*p)*100000`, each rounded to 2 decimals round-half-to-even; return `None` for any value whose divisor is 0 or when N/prev is `None` (never 0)
    - Implement `build_what_entry(scope, places, condition)` assembling the contract `what.json` entry including `affected_adults = round(N*p)` (round-half-to-even) or `null`, `adults_18plus`, `p`/`p_low`/`p_high`, `prevalence_year`, and the `ctgov_url`
    - _Requirements: 4.3, 4.4, 4.5, 4.6, 4.7, 4.8, 4.11, 1.6, 3.6_

  - [ ]* 4.2 Write property test for index ordering
    - **Property 1: Index ordering** — for every `what.json` entry where `low`, `mid`, `high` are all non-null, assert `low <= mid <= high`
    - **Validates: Requirements 9.1** (data-contract low/mid/high; `low` uses `p_high`, `high` uses `p_low`)
    - Use the strategies from 1.3; >=100 examples
    - _Requirements: 9.1, 4.5_

  - [ ]* 4.3 Write property test for prevalence bounds
    - **Property 2: Prevalence bounds** — for every entry where `p_low`, `p`, `p_high` are non-null, assert `0 <= p_low <= p <= p_high <= 1`
    - **Validates: Requirements 9.3** (population-weighted prevalence and limits as fractions)
    - >=100 examples
    - _Requirements: 9.3, 4.4_

  - [ ]* 4.4 Write unit tests for null propagation and rounding
    - Test absent measure (all prevalence/index/affected_adults `null`), zero-divisor cases, round-half-to-even on `low`/`mid`/`high`/`affected_adults`, and that `null` is written rather than `0`
    - _Requirements: 4.6, 4.7, 4.8, 9.2, 1.6, 3.6_

- [ ] 5. Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 6. Implement the Decomposer
  - [ ] 6.1 Implement `pipeline/scoring/decompose.py`
    - Implement the shared `by_label(scope, extract)` helper counting distinct nctIds per label (a study counts once per label; distinct labels within a study), sorted by label (Unicode code point), excluding labels with count 0
    - Implement `by_overall_status`, `by_study_type`, `by_intervention_type` (distinct nctId per type; a study with several types counts under each), and `by_phase` (empty/missing -> "Not reported", "NA"/not applicable -> "Not applicable", each a separate label)
    - Implement `phase_overlap_studies(scope)` (studies whose `phases` list has >1 element) and `ma_studies` (distinct eligible nctIds across all fetched statuses)
    - Implement `build_investigate_entry(scope, ...)` assembling the entry with `us_studies = null`
    - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.5, 5.6, 5.7, 5.8, 3.4_

  - [ ]* 6.2 Write property test for distinct-count integrity
    - **Property 3: Distinct-count integrity** — every breakdown `count`, `t`, and `ma_studies` equals the size of a set of distinct nctIds; no count exceeds `ma_studies`; duplicate study rows and multiple MA sites never change a count
    - **Validates: Requirements 9.4** (counts are always distinct nctId, never sites or intervention strings)
    - >=100 examples, using duplicate-heavy strategies from 1.3
    - _Requirements: 9.4, 5.1, 5.8_

  - [ ]* 6.3 Write unit tests for decomposition labels
    - Test multi-intervention counting, "Not reported"/"Not applicable" phase labels, zero-count label exclusion, and `phase_overlap_studies`
    - _Requirements: 5.2, 5.3, 5.4, 5.5, 5.6_

- [ ] 7. Implement the Findings_Generator
  - [ ] 7.1 Implement `pipeline/scoring/findings.py`
    - Define the two allowed `Finding_Label` strings and a `generate_findings(scope, what, breakdowns)` returning rules-based `Finding{text, label}` objects derived solely from the computed numbers (no AI/ML/LLM)
    - Apply deterministic rules: add a "Drug" finding (noting the drug may be an existing drug, a comparator, or a placebo) when the `Drug` intervention count >= 1; add other record-grounded `"possible explanation from available records"` findings gated on numeric conditions
    - Always append exactly one `"cannot determine from public data"` finding about funding levels or sponsor decisions, so every entry has at least one finding and exactly one such label
    - Exclude every Forbidden_Term (case-insensitive) from all finding text
    - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.5, 6.6_

  - [ ]* 7.2 Write property test for findings label validity
    - **Property 4: Findings label validity** — every finding has exactly one of the two valid labels; each `investigate.json` entry has exactly one `"cannot determine from public data"` finding; no finding text contains a Forbidden_Term (case-insensitive)
    - **Validates: Requirements 9.5** (findings rules; mandatory funding finding; forbidden-term ban)
    - >=100 examples
    - _Requirements: 9.5, 6.2, 6.3, 6.4, 6.6_

  - [ ]* 7.3 Write unit tests for the Drug finding and forbidden-term absence
    - Test that a `Drug` count >= 1 produces the drug/comparator/placebo finding and that no finding emits "neglected"/"underfunded"/"needs more trials"/"needs more drugs"
    - _Requirements: 6.5, 6.6_

- [ ] 8. Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 9. Implement the Evidence_Builder and Sources_Builder
  - [ ] 9.1 Implement `pipeline/scoring/evidence.py`
    - Implement `build_evidence_entry(scope, condition)` producing `ncts` (per eligible nctId: `nct_id`, `url`, `title`, `status`, `study_type`, `phases`, `intervention_types`, `intervention_names`), plus `filters`, `mapping_choices`, and `missing_data_notes`
    - Add a `missing_data_notes` entry when a measure is absent from `places_ma.csv`, continuing to the next measure without terminating
    - _Requirements: 3.1, 4.9_

  - [ ] 9.2 Implement `pipeline/scoring/sources.py`
    - Implement `build_sources(fetch_log)` producing `sources.json` as a single object with `is_sample = false`, `data_as_of` and each `sources[].fetched` as `YYYY-MM-DD`, and one `prevalence_years` entry per measure present in `what.json`
    - _Requirements: 3.1, 3.2_

  - [ ]* 9.3 Write unit tests for Evidence_Builder and Sources_Builder
    - Test NCT row shape, `missing_data_notes` on an absent measure, `is_sample == false`, date formats, and `prevalence_years` coverage
    - _Requirements: 3.2, 4.9_

- [ ] 10. Implement PII_Check, deterministic serialization, and atomic writing
  - [ ] 10.1 Implement serialization and PII_Check in `pipeline/scoring/export.py`
    - Implement a recursive `scan_strings` that walks every string value (including nested arrays/objects) in all four output structures and checks each against `pipeline.patterns.PATTERNS` (reusing the `pii_guard` approach); on a match raise `PipelineError` naming file/field/pattern without quoting the matched text
    - Add a Forbidden_Term scan over every output string (case-insensitive substring) raising `PipelineError` naming file/field without quoting matched text
    - Implement `serialize(obj)` producing deterministic bytes: top-level arrays ordered by `measure_id` (byte-string), object keys sorted, `ensure_ascii=False`, `indent=2`, UTF-8 without BOM, single trailing LF; order `investigate.json` breakdown arrays by `label` and `evidence.json` `ncts` by `nct_id`
    - _Requirements: 7.1, 7.2, 7.3, 7.4, 7.5, 8.1, 8.2, 8.3, 8.4_

  - [ ] 10.2 Implement atomic `write_all` and the `__main__` entry point
    - Implement `write_all(web_data_dir, files)` mirroring `pipeline/io/atomic.py`: stage all four files in a sibling `.staging-*` dir, fsync, `os.replace` each into `web/public/data/`, and remove staging in a `finally`; run the PII_Check and Forbidden_Term scan before any file is written, and never write a partial file
    - Implement the entry point: exit non-zero with a version message on Python < 3.11 before any I/O; load inputs; build scopes; build the four files in `measure_id` order (CASTHMA, HIGHCHOL, DIABETES); warn to stderr (exit 0) when a measure's county count != 14; do not produce `where.json` or `ma_counties.geojson`; exit 0 on success, non-zero leaving `web/public/data/` unchanged on any error
    - Make the module runnable as `python -m pipeline.scoring.export`; add any new third-party import to `requirements.txt` pinned to an exact version
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 3.1, 3.3, 3.7, 4.10, 7.5, 8.5, 8.6_

  - [ ]* 10.3 Write property test for schema conformance
    - **Property 5: Schema conformance** — every generated file validates against its data-contract shape: all required keys present and typed, `sources.json.is_sample is False`, every `investigate.json` entry's `us_studies is None`, uncomputable numeric values are `null` (never `0`), and no output string matches the email or phone pattern
    - **Validates: Requirements 9.6** (data-contract JSON schemas; is_sample false; null never 0; no PII)
    - >=100 examples
    - _Requirements: 9.6, 3.5, 7.1_

  - [ ]* 10.4 Write unit tests for PII_Check, determinism, and atomic rollback
    - Test PII/forbidden-term abort leaves `web/public/data/` unchanged (no file written), byte-identical output on byte-identical input, sorted ordering, trailing LF, and staged-file cleanup on a simulated write failure
    - _Requirements: 7.2, 7.5, 8.1, 8.4, 8.5, 8.6_

- [ ] 11. Integration wiring and network-block confirmation
  - [ ] 11.1 Write an end-to-end integration test wiring all components
    - Build a full input fixture set (studies, sites, places, fetch_log, study_diseases), run the exporter, and assert the four files land in a temp `web/public/data/` with correct per-disease entries ordered by `measure_id` and no `where.json`/`ma_counties.geojson`
    - _Requirements: 1.1, 1.2, 3.1, 3.3_

  - [ ]* 11.2 Confirm no network access during scoring
    - Add a scoring test under `tests/scoring/` relying on the autouse `network_block` fixture (reusing `tests/test_network_block.py` conventions) to assert a full export run makes zero network requests
    - _Requirements: 1.4_

- [ ] 12. Final checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional test sub-tasks and can be skipped for a faster MVP; the five property tests (4.2, 4.3, 6.2, 7.2, 10.3) implement Requirement 9.
- Each task references specific requirement sub-clauses for traceability.
- Checkpoints (5, 8, 12) ensure incremental validation.
- Property tests validate the five universal correctness properties from design § Correctness Properties; unit tests validate specific examples and edge cases.
- All modules live under `pipeline/scoring/`; tests mirror them under `tests/scoring/`. The entry point is `python -m pipeline.scoring.export`.
- Reuse `pipeline.errors.PipelineError`, `pipeline.patterns`, `pipeline.io.csv_reader`, `pipeline.io.atomic`, the Spec 1 row dataclasses, and `pipeline.transform.pii_guard` rather than reimplementing them.

## Task Dependency Graph

```json
{
  "waves": [
    { "id": 0, "tasks": ["1.1"] },
    { "id": 1, "tasks": ["1.2", "1.3", "2.1"] },
    { "id": 2, "tasks": ["2.2", "3.1"] },
    { "id": 3, "tasks": ["3.2", "4.1"] },
    { "id": 4, "tasks": ["4.2", "4.3", "4.4", "6.1", "9.1", "9.2"] },
    { "id": 5, "tasks": ["6.2", "6.3", "7.1", "9.3"] },
    { "id": 6, "tasks": ["7.2", "7.3", "10.1"] },
    { "id": 7, "tasks": ["10.2"] },
    { "id": 8, "tasks": ["10.3", "10.4", "11.1"] },
    { "id": 9, "tasks": ["11.2"] }
  ]
}
```
