# Implementation Plan: condition-grouping (Spec 2)

## Overview

Python 3.11+, pytest + Hypothesis (already pinned, no new packages). The plan follows the design's six-task mapping. Task 1 builds the Term_Audit and writes `rules.py` from its dispositions. Tasks 2 to 5 build the pipeline modules bottom-up and wire them into `python -m pipeline.mapping`. Task 6 runs the pipeline on real data and commits the outputs. Task 7 adds questionable masking (Req 4.1, Open Item 15) and the new HIGHCHOL recall term (Req 2.12, Open Item 16), reruns the pipeline and commits the result.

Two shared helpers move earlier than the design's mapping table shows, because the Term_Audit in task 1 already uses them: `csv_reader.read_table` (design: task 2) and `atomic.write_files_atomically` (design: task 5) are built in task 1. Task 5 adds the end-to-end atomic-failure tests through the CLI.

Every top-level task is done only when the whole `pytest` suite (Spec 1 tests included) passes from the repository root with no network access. All tests use files under `tmp_path`, never the committed `pipeline/processed/` or `burden_test/` files (Req 13.8). Each Hypothesis property test runs at least 100 examples and carries the comment `# Feature: condition-grouping, Property <n>: <title>`.

## Tasks

- [x] 1. Term_Audit, shared I/O helpers and `rules.py`
  - Done when: `term_audit.md` has every disposition filled, `rules.py` agrees with it, and the full `pytest` suite passes.
  - [x] 1.1 Add `read_table(path, header, list_columns)` to `pipeline/io/csv_reader.py`
    - Return `list[tuple[int, dict]]` with each record's first line number (`reader.line_num + 1` before each record, so multi-line quoted cells report the start line)
    - Error messages name file, line and column only, never cell content
    - Rewrite `read_csv(path, kind)` as a thin wrapper that drops line numbers; Spec 1 behaviour and tests unchanged
    - Add unit tests in `tests/io/test_read_table.py`: header mismatch, bad list cell (line/column), multi-line cell start line, wrong cell count, `read_csv` still matches Spec 1
    - _Requirements: 1.3, 1.4, 1.6, 14.12_

  - [x] 1.2 Add `write_files_atomically(files: list[tuple[Path, bytes]])` to `pipeline/io/atomic.py`
    - Temp file per target in its own directory (`mkstemp(dir=target.parent, prefix=".tmp-")`), write + fsync via `_write_bytes`
    - Save original bytes (or absence) of each target, `os.replace` in list order, roll back targets 1..k-1 if replace k fails, raise `PipelineError("could not write <file> (<OSError type>)")`
    - Remove leftover temp files in `finally`; leave `write_outputs` unchanged
    - Add unit tests in `tests/io/test_write_files_atomically.py`: two directories, temp-write failure leaves all targets untouched, second-replace failure restores the first target (existing and previously absent), no `.tmp-` files remain
    - _Requirements: 9.11, 9.12, 14.11_

  - [x] 1.3 Implement `pipeline/mapping/term_audit.py`
    - Create `pipeline/mapping/__init__.py` (empty) and `tests/mapping/__init__.py`
    - `AUDIT_KEYWORDS`, `AUDIT_COLUMNS`, `TOP_N = 40`; pure `audit_tables(rows)` and `render(sha256_hex, row_count, tables)`; `filled_cells(existing_md)` splitting on unescaped `|`; `main(argv=None, root=REPO_ROOT)`
    - Read `studies.csv` with `read_table(..., list_columns={"meshTerms","ancestorTerms","conditions"})`; SHA-256 over the same bytes parsed; wrap missing / unopenable / non-UTF-8 as `PipelineError` naming the file
    - Count per study with a `set`, skip empty Normalized_Text, sort `(-count, value)`, keep first 40, `no values` for empty tables, escape `|` as `\|`, no timestamp
    - Refuse (stderr notice with filled count, exit 1, file unchanged) when existing `term_audit.md` has filled cells; otherwise write through `write_files_atomically`
    - _Requirements: 14.1, 14.2, 14.3, 14.4, 14.5, 14.10, 14.11, 14.12, 14.13_

  - [x]* 1.4 Write property test for Term_Audit determinism
    - **Property 14: Term_Audit determinism**
    - File `tests/mapping/test_property_14_term_audit.py`; generated rows, repeated runs and row permutations give identical bytes, tables ordered by (-count, value)
    - **Validates: Requirements 14.6, 14.3**

  - [x] 1.5 Write Term_Audit example tests in `tests/mapping/test_term_audit.py`
    - `LDL` lists "LDL Cholesterol" and "VLDL"; `diabet` lists "Diabetic Retinopathy"; duplicates within one study count once; case variants counted separately; more than 40 values truncated; `no values` table; `|` escaping; header and output format
    - Errors: missing file, non-UTF-8, bad header, bad list cell in one of the three columns (line and column, no content); exit ≠ 0 and existing `term_audit.md` unchanged
    - Filled-file refusal leaves bytes unchanged and exits 1; reads only `studies.csv`, writes only `term_audit.md` (both under `tmp_path`)
    - _Requirements: 14.1, 14.2, 14.4, 14.5, 14.11, 14.12, 14.13_

  - [x] 1.6 Run the Term_Audit and fill dispositions
    - Run `python -m pipeline.mapping.term_audit` on the committed `pipeline/processed/studies.csv` to write `.kiro/specs/condition-grouping/term_audit.md`
    - Fill every disposition (`include` / `exclude` / `questionable` / `not_disease`) by applying `burden_test/inclusion_rules.md`; reason code for every `exclude` and `questionable` row (for example `gestational`, `prediabetes`, `not_mellitus`, `ascvd_only`, `complication_only`, `broad_category`, `lab_value_only`, `monogenic_or_rare`, `secondary_cause`); a 1-200 character note for every `not_disease` row
    - Ambiguous values get `questionable` with a reason code; the same Normalized_Text under one measureid gets the same disposition and reason in every table
    - _Requirements: 14.7, 14.9_

  - [x] 1.7 Write `pipeline/mapping/rules.py`
    - Plain data only, no import statement; `SAMPLE_SEED` (int in 0..4,294,967,295) and `DISEASES` (list of dicts with `measureid`, `disease_label`, `ancestor_only_status`, `recall_query_term`, `include` list of str, `exclude` and `questionable` lists of `(term, reason)` tuples)
    - CASTHMA "Asthma" / `included` / "Asthma"; HIGHCHOL "High cholesterol" / `questionable` / "High Cholesterol"; DIABETES "Diabetes" / `questionable` / "Diabetes"
    - Req 2.3 minimum terms, including "Diabetes Insipidus" and "Diabetes Insipidus, Neurogenic" (`not_mellitus`), "Hyperlipoproteinemia Type II", "familial hypercholesterolemia" and every other HIGHCHOL MeSH descriptor marked `include` in the audit, ASCVD and myocardial infarction excludes (`ascvd_only`)
    - MeSH_Form and at least one Free_Text_Form per concept where Normalized_Text differs; one entry where it is the same; every audit disposition mapped to the matching list with its reason; no `not_disease` value listed
    - _Requirements: 2.1, 2.2, 2.3, 2.8, 2.10, 2.11, 2.12, 14.8, 14.9_

  - [x] 1.8 Write static tests for `rules.py` in `tests/mapping/test_rules_static.py`
    - Parse `rules.py` with `ast`: no `Import` / `ImportFrom` node
    - Req 2.3 minimum terms, Req 2.8 Ancestor_Only_Status values, Req 2.12 recall query terms and Req 2.2 labels present
    - Read the committed `term_audit.md` (read-only): every disposition is filled; every `include` / `exclude` / `questionable` value has an entry with the same Normalized_Text and reason in the matching list for its measureid; no `not_disease` value appears in any list; no Normalized_Text duplicated within a disease
    - _Requirements: 2.2, 2.3, 2.8, 2.11, 2.12, 14.7, 14.8, 14.9_

- [x] 2. Rules loader, inputs, Age_Parser and Term_Matcher
  - Done when: the real `rules.py` loads without errors, the committed inputs read without errors in a test copy, and the full `pytest` suite passes.
  - [x] 2.1 Implement `pipeline/mapping/rules_loader.py`
    - `SUPPORTED_MEASURES`, `RESERVED_REASONS`, frozen dataclasses `Term`, `Disease`, `RulesConfig` (diseases sorted by measureid)
    - `load_rules(module_name)`: import errors and missing or ill-typed `DISEASES` / `SAMPLE_SEED` raise `ConfigError("rules.py: ...")`
    - Pure `validate(diseases_obj, seed_obj)` collects every failed Req 2.5 / 2.6 check into one `ConfigError(lines)`, each line naming the measureid or `Rules_Config`; `type(seed) is int` and range check; reason regex `^[a-z][a-z0-9_]{0,39}$`; reserved reasons rejected; duplicates compared as Normalized_Text within and across lists
    - Add `ConfigError(PipelineError)` with `lines: list[str]` in `pipeline/errors.py`
    - Unit tests in `tests/mapping/test_rules_loader.py`: one failing config per check, several failures reported together, `True` seed rejected, seed bounds, duplicate across include/exclude, real `rules.py` loads
    - _Requirements: 2.4, 2.5, 2.6, 2.7, 2.9, 11.9_

  - [x] 2.2 Implement `pipeline/mapping/age_parser.py`
    - `parse_max_age(text) -> Fraction | NO_LIMIT | UNPARSEABLE`, `fullmatch` of `[0-9]+ [A-Za-z]+` after `strip()`, unit `casefold()`, singular and plural, exact `Fraction` years per unit; `is_child_only(text)` as exact `< 18`
    - Example tests in `tests/mapping/test_age_parser.py`: child-only "17 Years", "215 Months", "939 Weeks", "6574 Days", "157787 Hours", "0 Years"; not child-only "18 Years", "216 Months", "940 Weeks", "6575 Days", "157788 Hours"; empty and whitespace → no limit; "-1 Years", "1.5 Years", "17Years", "17 Decades", non-ASCII digits → unparseable
    - _Requirements: 5.1, 5.2, 5.4, 5.6, 5.7, 13.3_

  - [x] 2.3 Write property test for the age threshold
    - **Property 5: Exact age threshold**
    - File `tests/mapping/test_property_05_age_threshold.py`; any n ≥ 0, any of the 12 units in random letter case; child-only exactly when n × d < 18 × u as integers
    - **Validates: Requirements 5.1, 5.6**

  - [x] 2.4 Implement `pipeline/mapping/term_matcher.py`
    - `normalize`, `exact_match`, `phrase_match` (every occurrence via `str.find` loop, boundary = string edge or non-alphanumeric), frozen ordered `Match`, `find_matches(study, disease) -> frozenset[Match]`
    - `meshTerms` → `mesh`, `ancestorTerms` → `ancestor` (Exact_Match); `conditions` → `condition_text` (Phrase_Match); skip empty Normalized_Text; only these three columns are searched
    - Example tests in `tests/mapping/test_term_matcher.py`: Req 3.1 and 3.2 examples ("Diabetes Mellitus" vs "Diabetes Mellitus, Type 2", "Severe Asthma", "Asthma, Exercise-Induced", not "Asthmatic Bronchitis", "Type  2 Diabetes Mellitus"), value recorded as written, duplicate list values give one match, `[]` and terms only in `briefTitle` give no match
    - _Requirements: 3.1, 3.2, 3.3, 3.5, 3.6_

  - [x] 2.5 Write Hypothesis generators in `tests/mapping/strategies.py`
    - Rules configs with 1-5 diseases from a small vocabulary (`asthma`, `type 2 diabetes`, `gestational diabetes`, `ldl`, ...), random Ancestor_Only_Status, valid reason codes, random letter case, no Normalized_Text duplicates
    - Studies from the vocabulary plus noise words and boundary cases (`asthmatic`), empty and whitespace-only values, mixed case and extra spaces
    - `maximumAge`: empty, whitespace, each of the 12 units in mixed case near the 18-year boundary, malformed strings; `healthyVolunteers`: `true`, `false`, empty
    - _Requirements: 13.1, 13.2_

  - [x] 2.6 Write property test for case-insensitive matching
    - **Property 1: Case- and whitespace-insensitive matching**
    - File `tests/mapping/test_property_01_case_insensitive.py`; case and whitespace perturbations of study values and terms keep the same (measureid, kind, normalized term, source) set
    - **Validates: Requirements 3.4, 3.1, 3.2**

  - [x] 2.7 Implement `pipeline/mapping/inputs.py`
    - `STUDIES_HEADER`, `SITES_HEADER` from `csv_writer.COLUMNS`; frozen `Study` dataclass incl. `conditions_cell` re-encoded with `encode_list_cell`
    - `read_inputs(paths) -> (dict[str, Study], frozenset[str])` via `read_table`; wrap `FileNotFoundError` / `OSError` / `UnicodeDecodeError` as `PipelineError` naming the file; zero rows, empty or duplicate `nctId` (first offending line, only the nctId); `healthyVolunteers` not in `{"true","false",""}` (file, line, column)
    - MA_Site = `state` in {"Massachusetts", "MA"}; orphan site rows ignored with one stderr warning giving the count
    - Unit tests in `tests/mapping/test_inputs.py` covering each error, the orphan warning, MA_Site detection and `conditions_cell` byte-identity with the source cell
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.6, 1.7, 6.6, 11.4_

- [x] 3. Grouping_Engine and `study_diseases.csv` encoding
  - Done when: grouping the real data in a test copy succeeds, every listed property and example passes, and the full `pytest` suite passes.
  - [x] 3.1 Implement `pipeline/mapping/grouping_engine.py`
    - `SOURCE_ORDER`, `dm_key`, `pick`, frozen `StudyDiseaseRow`, `decide(study, disease, matches)` and `group(studies, rules)` sorted by (nctId, measureid)
    - Status rules in design order: masked values, 1 child_only, 2 healthy_volunteers_only, 3a ancestor-include with direct exclude, 3b term exclude, 4 unparseable_age, 5 included (direct, or ancestor under `included`), 6 questionable (Questionable_Term reason or `ancestor_only`); assert rule 6 has candidates
    - Determining_Match per Req 8.6 cases (a)-(g) and 8.8 order; `matched_on = DM.source`, `matched_term = DM.value`; reason from the Rules_Config pairing for cases (c), (d), (f)
    - _Requirements: 3.7, 4.1, 4.2, 4.3, 4.4, 4.5, 5.3, 5.4, 6.1, 6.2, 6.3, 6.4, 6.5, 7.1, 7.2, 7.3, 7.4, 7.5, 7.6, 8.1, 8.2, 8.3, 8.4, 8.5, 8.6, 8.8_

  - [x] 3.2 Create `pipeline/mapping/outputs.py` with `encode_study_diseases`
    - `STUDY_DISEASES_HEADER`; `encode_study_diseases(rows) -> EncodedTable(kind="study_diseases", ...)` sorted by (nctId, measureid), serialized only through `csv_writer.serialize`
    - Unit test in `tests/mapping/test_outputs_study_diseases.py`: header-only file for no rows, quoting of comma / quote / CR / LF, no quotes on empty cells, LF endings, no BOM, sort order
    - _Requirements: 9.1, 9.2, 9.3, 9.4, 9.5_

  - [x] 3.3 Write per-reason example tests in `tests/mapping/test_grouping_examples.py`
    - Use the loaded `rules.py`; one representative study per reason code (`child_only`, `unparseable_age`, `healthy_volunteers_only`, `ancestor_only`, and every Exclude/Questionable reason enumerated from `rules.py`, so a new reason without an example fails), plus one `included` study per disease; assert `match_status`, `exclusion_reason`, `matched_on`, `matched_term`
    - Named examples: "Gestational Diabetes" + ancestor "Diabetes Mellitus" → `excluded`/`gestational` (Req 4.3); "Type 2 Diabetes" + "Gestational Diabetes" → included (Req 4.4); HIGHCHOL "Myocardial Infarction" only → `excluded`/`ascvd_only` (Req 4.2); questionable beats term exclude without ancestor include (Open Item 9); healthy-volunteer asthma study with "Asthma" in conditions → included (Req 6.4)
    - _Requirements: 13.4, 4.2, 4.3, 4.4, 5.3, 5.4, 6.1, 6.4, 7.1, 7.2, 7.4_

  - [x] 3.4 Write property test for no-evidence studies
    - **Property 2: No include evidence, never included**
    - File `tests/mapping/test_property_02_no_evidence.py`
    - **Validates: Requirements 4.6, 7.8, 4.1**

  - [x] 3.5 Write property test for exclude monotonicity
    - **Property 3: Exclude monotonicity**
    - File `tests/mapping/test_property_03_exclude_monotonic.py`
    - **Validates: Requirements 4.7**

  - [x] 3.6 Write property test for child-only studies
    - **Property 4: Child-only studies are never included**
    - File `tests/mapping/test_property_04_child_only.py`
    - **Validates: Requirements 5.5, 5.3**

  - [x] 3.7 Write property test for the healthy-volunteer rule
    - **Property 6: Healthy-volunteer rule**
    - File `tests/mapping/test_property_06_healthy_volunteers.py`
    - **Validates: Requirements 6.7, 6.4, 6.5, 6.1**

  - [x] 3.8 Write property test for row validity and questionable reasons
    - **Property 7: Row values are valid**
    - File `tests/mapping/test_property_07_row_values.py`
    - **Validates: Requirements 7.7, 8.2, 8.3, 8.4**

  - [x] 3.9 Write property test for row existence and referential integrity
    - **Property 8: Rows exist exactly for matched pairs**
    - File `tests/mapping/test_property_08_rows_exist.py`
    - **Validates: Requirements 8.1, 8.7, 3.7, 2.4**

  - [x] 3.10 Write property test for match consistency
    - **Property 9: Match consistency**
    - File `tests/mapping/test_property_09_match_consistency.py`
    - **Validates: Requirements 8.9, 8.5**

  - [x] 3.11 Write property test for the `study_diseases.csv` round trip
    - **Property 10: study_diseases.csv round trip**
    - File `tests/mapping/test_property_10_round_trip.py`; cells with empty, comma, quote, CR, LF and non-ASCII text, read back with `read_table`
    - **Validates: Requirements 9.6, 9.4, 9.3**

  - [x] 3.12 Write property test for deterministic, order-independent output
    - **Property 11: Deterministic, order-independent output**
    - File `tests/mapping/test_property_11_determinism.py`; repeated runs, study order permutations and list-element permutations give identical bytes
    - **Validates: Requirements 9.7, 9.8, 8.8, 9.5**

- [x] 4. Recall_Checker
  - Done when: stub-client tests and the ratio property pass, no test sends a network request, and the full `pytest` suite passes.
  - [x] 4.1 Implement `pipeline/mapping/recall_checker.py`
    - `ACTIVE`, `found_count` (any match_status) and `included_count` (`included` only), both over distinct nctIds with Active_Status and at least one MA_Site
    - `request_url(term)` via `ctgov_fetcher.build_url` with the Req 10.2 parameters; `rounded_ratio` exact half-up to 3 decimals, `None` on ctgov 0, no cap; `is_flagged(ratio_found)` only
    - `check(rules, rows, studies, ma_ids, client, today)` sends one `client.get` per disease in measureid order; `PipelineError`, invalid JSON, missing / `bool` / non-int / negative `totalCount` → `PipelineError("recall check failed for <measureid>: <url> (<type>)")` with no body
    - `serialize(result)`: fixed key order, `indent=2`, `ensure_ascii=False`, trailing LF, ratios as `float` or `null`; one stderr warning line per flagged disease with measureid, found_count, included_count, ctgov_count, ratio_found
    - _Requirements: 10.1, 10.2, 10.3, 10.4, 10.5, 10.6, 10.7_

  - [x] 4.2 Write property test for ratio rounding and flag
    - **Property 12: Ratio rounding and flag depend only on ratio_found**
    - File `tests/mapping/test_property_12_ratio.py`
    - **Validates: Requirements 10.3, 10.4, 13.5**

  - [x] 4.3 Write stub-client unit tests in `tests/mapping/test_recall_checker.py`
    - Stub client returning a configured `totalCount`; assert URL parameters, request order, `found_count` counts included + questionable + excluded rows, `included_count` counts included only, non-active and non-MA studies excluded, one count per study with several MA_Sites
    - Ratios: 0.7995 → 0.8 not flagged, 0.7994 → 0.799 flagged, 0.8 not flagged, null on ctgov 0 (flagged), ratio_found 0.9 with ratio_included 0.1 not flagged, ratio above 1.0 kept
    - Failure stubs (raised `PipelineError`, non-JSON body, missing / `bool` / negative `totalCount`) raise with measureid and URL and no body text; JSON layout byte-exact; warning line format
    - _Requirements: 13.5, 10.1, 10.2, 10.3, 10.4, 10.5, 10.6, 10.7_

- [x] 5. Precision_Sampler, PII_Guard, summary and CLI
  - Done when: `python -m pipeline.mapping --offline` runs end to end in tests under a temporary root, and the full `pytest` suite passes.
  - [x] 5.1 Implement `pipeline/mapping/precision_sampler.py`
    - `HEADER`, `candidates` (included rows with an MA_Site, sorted by nctId), `select` with a fresh `random.Random(seed)` per disease and `min(20, n)`, `build` sorted (measureid, nctId) copying `briefTitle`, `conditions_cell`, `source_url`, `matched_term`, empty `correct`
    - `existing_state(path, resample)`: `write` on `--resample` or missing file; otherwise `read_table(path, HEADER, frozenset())`, read or header failure → `PipelineError` naming the file; non-whitespace `correct` → `keep` plus notice with the count
    - stderr warning with measureid and count for fewer than 20 candidates
    - _Requirements: 11.1, 11.2, 11.3, 11.4, 11.6, 11.7, 11.8_

  - [x] 5.2 Write property test for the deterministic sample
    - **Property 13: Deterministic precision sample**
    - File `tests/mapping/test_property_13_sample.py`; repeated calls, min(20, n) distinct candidates, unchanged selection when other diseases are added or removed, copied cells equal their source
    - **Validates: Requirements 11.5, 11.1, 11.4**

  - [x] 5.3 Write sampler unit tests in `tests/mapping/test_precision_sampler.py`
    - Fewer than 20 and zero candidates (warning, no rows), header-only file, `keep` with a filled `correct` cell, `write` when all `correct` cells are blank, unreadable file and wrong header raise naming the file
    - _Requirements: 11.2, 11.3, 11.6, 11.7, 11.8_

  - [x] 5.4 Add `pii_check` and `summary` to `pipeline/mapping/outputs.py`
    - `pii_check` uses `patterns.PATTERNS` on every cell, the decoded `conditions` elements of `precision_sample.csv`, and every string value of `recall_check.json`; error names file, column or key, and nctId or measureid, with no content
    - `summary(rules, rows)`: one block per disease sorted by measureid, included / questionable / excluded counts with 0s, per-reason counts sorted by reason code
    - _Requirements: 9.9, 9.10, 12.6, 12.8_

  - [x] 5.5 Write PII_Guard and summary unit tests in `tests/mapping/test_outputs_guard_summary.py`
    - Email and phone hits in each of the three files raise without echoing the value; summary format with a disease that has zero rows
    - _Requirements: 9.9, 12.6, 12.8_

  - [x] 5.6 Implement `pipeline/mapping/__main__.py`
    - Copy the Spec 1 version check as the first lines, before any pipeline import
    - `build_parser()` with `prog="python -m pipeline.mapping"`, `allow_abbrev=False`, `--offline` and `--resample` as `store_true`
    - `Paths(root)` rooted at `REPO_ROOT = Path(__file__).resolve().parents[2]`; `run(argv, paths, client=None, clock=None, stdout, stderr) -> int` in the order rules → inputs → group → recall (skipped under `--offline`, notice when no recall file exists, no client built) → sampler → encode + PII_Guard → `write_files_atomically` (only files that change) → summary → 0
    - `PipelineError` / `ConfigError` lines to stderr, exit 1; other exceptions → `error: unexpected <TypeName>`, exit 1, no traceback; do not import `term_audit`
    - _Requirements: 1.1, 1.5, 9.10, 10.8, 10.9, 11.6, 11.7, 12.1, 12.2, 12.3, 12.4, 12.5, 12.6, 12.7, 12.8, 12.9, 14.10_

  - [x] 5.7 Write CLI integration tests in `tests/mapping/test_main.py`
    - Usage errors (unknown option, `--off`, positional) exit 2 before any I/O; both options in either order accepted
    - Config error and missing `rules.py` exit 1 before inputs are read and with no network; input errors leave outputs unchanged
    - Recall stub failures (raised error, no integer `totalCount`) exit ≠ 0, measureid and URL on stderr, all three outputs byte-for-byte unchanged (Req 13.6); flagged ratio still exits 0
    - PII hit and simulated `os.replace` failure on the second target leave all outputs unchanged, temp files removed
    - `--offline` with and without an existing `recall_check.json`; filled `correct` cell kept without `--resample`, regenerated with `--resample` (Req 13.8); two runs give identical outputs; running from another working directory uses the same files; unexpected exception prints only the type name; `term_audit` not in `sys.modules` after `run`; `requirements.txt` gains no new package
    - _Requirements: 9.7, 9.10, 9.12, 10.6, 10.7, 10.8, 10.9, 11.6, 11.7, 11.8, 12.2, 12.3, 12.4, 12.5, 12.7, 12.9, 13.6, 13.7, 13.8, 14.10_

- [x] 6. Full run, verification and commit
  - Done when: the four artifacts are committed, `KIRO_LOG.md` has the entry, the full `pytest` suite passes, and the recall ratios are reported. A flagged `ratio_found` is reported as a warning, not a stop condition.
  - [x] 6.1 Run `python -m pipeline.mapping` with network access
    - Confirm exit code 0; capture the stdout summary and every stderr warning (flagged ratios, fewer than 20 candidates)
    - Verify outputs: `study_diseases.csv` header, sort order and status/reason values; `recall_check.json` has one entry per disease with both ratios; `precision_sample.csv` has up to 20 rows per disease with empty `correct`
    - Run `pytest` and confirm the committed `pipeline/processed/` and `burden_test/` files are unchanged by it
    - _Requirements: 9.1, 9.5, 10.5, 10.6, 11.3, 12.6, 12.7, 13.1, 13.8_

  - [x] 6.2 Add a `KIRO_LOG.md` entry
    - Record the run date, per-disease summary counts, `found_count`, `included_count`, `ctgov_count`, `ratio_found`, `ratio_included`, which diseases are flagged, and the number of Questionable_Terms awaiting bio teammate review
    - _Requirements: 10.6, 12.6_

  - [x] 6.3 Commit outputs and code
    - Stage by name: `pipeline/processed/study_diseases.csv`, `pipeline/processed/recall_check.json`, `burden_test/precision_sample.csv`, `.kiro/specs/condition-grouping/term_audit.md`, `KIRO_LOG.md`, plus the new code and tests if not yet committed; commit with a message naming Spec 2
    - Report the recall ratios and any flagged diseases with their counts to the user
    - _Requirements: 9.7, 10.5, 11.3, 14.5_

- [ ] 7. Questionable masking and HIGHCHOL recall term
  - Done when: the six studies of Req 4.8 have the expected rows, the HIGHCHOL recall term is in `recall_check.json`, `KIRO_LOG.md` has before/after counts, and the full `pytest` suite passes.
  - [x] 7.1 Mask questionable values for include evidence in `pipeline/mapping/grouping_engine.py`
    - Add `qmasked` (values with a Questionable_Term match) and build `incNM`, `direct` and `anc` from `masked | qmasked`; keep `masked` exclude-only and keep `qNM` filtered by `masked` alone, so rules 3a/3b keep their exclude precedence and questionable matches stay rule 6 candidates with unchanged reason codes (design § Grouping_Engine)
    - Update the unit and example tests whose expected rows change in `tests/mapping/test_grouping_engine.py` and `tests/mapping/test_grouping_examples.py`
    - Update the oracles in `tests/mapping/test_property_02_no_evidence.py` and `tests/mapping/test_property_06_healthy_volunteers.py` to use the widened masking (Properties 2 and 6)
    - Add example tests in `tests/mapping/test_grouping_examples.py`: "Pediatric Asthma" only → `questionable`/`pediatric_label`; "Pediatric Asthma" + "Asthma" → `included`; `healthyVolunteers` = `true` with only "Pediatric Asthma" → `excluded`/`healthy_volunteers_only`
    - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.6, 6.1, 6.3, 6.4, 6.7, 7.1, 7.3, 7.4, 7.8, 8.6, 13.4_

  - [x] 7.2 Write property test for questionable masking
    - **Property 15: Questionable-masked include evidence is never included**
    - File `tests/mapping/test_property_15_questionable_mask.py`; generators (extend `tests/mapping/strategies.py` if needed) produce condition values that phrase-match both an Include_Term and a Questionable_Term, for example "pediatric asthma" with include "asthma"; check both halves of the property
    - **Validates: Requirements 4.1, 4.4, 4.6, 7.4, 7.8**

  - [x] 7.3 Set the HIGHCHOL recall query term
    - In `pipeline/mapping/rules.py` set HIGHCHOL `recall_query_term` to exactly "hypercholesterolemia OR hyperlipidemia OR dyslipidemia OR LDL"
    - Update the Req 2.12 check in `tests/mapping/test_rules_static.py`
    - _Requirements: 2.12_

  - [x] 7.4 Rerun the pipeline and verify
    - Record before counts from the committed outputs: per-disease summary counts from `pipeline/processed/study_diseases.csv` and every `recall_check.json` entry (`found_count`, `included_count`, `ctgov_count`, `ratio_found`, `ratio_included`, `flagged`)
    - Run `python -m pipeline.mapping` with network access; confirm exit code 0 and capture stdout and stderr warnings
    - Verify the Req 4.8 rows: NCT06538376 CASTHMA `questionable`/`overlap_syndrome`; NCT05723445, NCT06449677, NCT07688070 DIABETES `questionable`/`secondary_cause`; NCT04278404 and NCT06903897 CASTHMA `excluded`/`healthy_volunteers_only`; NCT06903897 DIABETES and HIGHCHOL still `included`
    - Confirm the HIGHCHOL entry in `recall_check.json` carries the new `recall_query_term` and `request_url`; a HIGHCHOL `ratio_found` above 1.0 is expected (Open Item 16)
    - Run `pytest` and confirm the committed `pipeline/processed/` and `burden_test/` files are unchanged by it; report before/after counts
    - _Requirements: 2.12, 4.8, 10.1, 10.5, 12.6, 13.1, 13.8_

  - [x] 7.5 Add a `KIRO_LOG.md` entry
    - Record the run date, the two changes (questionable masking, HIGHCHOL recall term), before/after per-disease summary counts and before/after recall values, and the Req 4.8 verification result
    - _Requirements: 4.8, 10.6, 12.6_

  - [-] 7.6 Commit
    - Stage by name: `pipeline/mapping/grouping_engine.py`, `pipeline/mapping/rules.py`, the changed and new test files under `tests/mapping/`, `.kiro/specs/condition-grouping/requirements.md`, `design.md`, `tasks.md` and `tasks.meta.json`, `pipeline/processed/study_diseases.csv`, `pipeline/processed/recall_check.json`, `burden_test/precision_sample.csv` (only if it changed), and `KIRO_LOG.md`; commit with a message naming Spec 2 questionable masking and the HIGHCHOL recall term
    - _Requirements: 2.12, 4.1, 9.7, 10.5_

## Notes

- Tasks marked with `*` are optional. Only Property 14 (Term_Audit determinism) is optional; the user did not ask for it and Req 13 does not require it. Every property the user requested stays required.
- `read_table` and `write_files_atomically` are built in task 1 because the Term_Audit uses them; the design's mapping table lists them under tasks 2 and 5.
- Each property test lives in its own file so property sub-tasks can run in parallel without editing the same file.
- Task 1.6 edits only `term_audit.md`; dispositions are not reviewed before `rules.py` is written (Open Item 13).
- Every task references specific requirement clauses for traceability.

## Task Dependency Graph

```json
{
  "waves": [
    { "id": 0, "tasks": ["1.1", "1.2"] },
    { "id": 1, "tasks": ["1.3"] },
    { "id": 2, "tasks": ["1.4", "1.5"] },
    { "id": 3, "tasks": ["1.6"] },
    { "id": 4, "tasks": ["1.7"] },
    { "id": 5, "tasks": ["1.8", "2.1", "2.2", "2.7"] },
    { "id": 6, "tasks": ["2.3", "2.4"] },
    { "id": 7, "tasks": ["2.5"] },
    { "id": 8, "tasks": ["2.6", "3.1", "3.2"] },
    { "id": 9, "tasks": ["3.3", "3.4", "3.5", "3.6", "3.7", "3.8", "3.9", "3.10", "3.11", "3.12", "4.1"] },
    { "id": 10, "tasks": ["4.2", "4.3", "5.1"] },
    { "id": 11, "tasks": ["5.2", "5.3", "5.4"] },
    { "id": 12, "tasks": ["5.5", "5.6"] },
    { "id": 13, "tasks": ["5.7"] },
    { "id": 14, "tasks": ["6.1"] },
    { "id": 15, "tasks": ["6.2"] },
    { "id": 16, "tasks": ["6.3"] },
    { "id": 17, "tasks": ["7.1", "7.3"] },
    { "id": 18, "tasks": ["7.2"] },
    { "id": 19, "tasks": ["7.4"] },
    { "id": 20, "tasks": ["7.5"] },
    { "id": 21, "tasks": ["7.6"] }
  ]
}
```
