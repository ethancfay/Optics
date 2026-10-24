# Requirements Document

## Introduction

The Scoring & Export stage (Spec 3) is the local, offline step of the Research Gap Index that turns the processed CSVs from the data pipeline (Spec 1) and the disease-to-measure matches from condition grouping (Spec 2) into the four JSON files the dashboard (Spec 4) reads. It reads `studies.csv`, `sites.csv`, `places_ma.csv`, `fetch_log.json`, and `study_diseases.csv` from `pipeline/processed/`, computes the burden-versus-activity index and activity decomposition per disease, generates rules-based findings, and writes `what.json`, `investigate.json`, `evidence.json`, and `sources.json` to `web/public/data/`.

`data-contract.md` is the source of truth for every output key, definition, and formula in this document; where this document states a formula, column name, or JSON shape, it restates the data contract and does not change it. The stage performs no network requests, produces byte-identical output from byte-identical input, writes atomically so a failed run never corrupts the committed dashboard data, never emits contact data (PII), and never emits the forbidden claim language of `product.md` and `health-safety.md`.

The entry point is `python -m pipeline.scoring.export`, run from the repository root on Python 3.11 or newer.

### Open Items and Assumptions

1. `study_diseases.csv` is produced by Spec 2 (condition grouping), which has not yet landed. In a production run the file is absent, so the Scoring_Exporter raises a clear error naming the file. Tests supply a fixture with the data-contract columns (any directory) so the stage is fully testable now (Requirement 2).
2. "Massachusetts" for the MA study definition is compared case-insensitively against the full state name `massachusetts` and the abbreviation `ma`, matching the `Sanity_Checker` MA-state handling in Spec 1.
3. A site counts toward T only when its own site status field (separate from the study `overallStatus`) is `RECRUITING`; a site whose status is absent or any other value never counts as recruiting (data-contract T definition; `product.md` counting rules).
4. "Forbidden terms" means the claim words banned by `product.md` and `health-safety.md`: "neglected", "underfunded", "needs more trials", "needs more drugs", and any diagnosis, treatment, eligibility, "you should join", recommendation, or prediction wording.
5. The 14 MA counties are those present in `places_ma.csv` for a measure; if a measure has a county count other than 14, the stage warns but still exits 0 and computes N from the counties present (data-contract N definition; `Sanity_Checker` style of Spec 1).
6. `prevalence_years` in `sources.json` and `prevalence_year` in `what.json` are the PLACES data year per measure (`2022` or `2023`), taken from the PLACES rows for that measure.

## Glossary

- **Scoring_Exporter**: The Python 3.11-or-newer module described by this document, run locally as `python -m pipeline.scoring.export` from the repository root. It performs no network requests.
- **Readers**: The Scoring_Exporter component that loads and types the five input files from `pipeline/processed/` (or a test fixture directory for `study_diseases.csv`).
- **MA_Index_Builder**: The Scoring_Exporter component that applies the data-contract definitions once and produces one Disease_Scope per measure.
- **Scoring_Engine**: The Scoring_Exporter component that computes the `what.json` numbers (T, N, p, p_low, p_high, low, mid, high, affected_adults).
- **Decomposer**: The Scoring_Exporter component that builds the `investigate.json` breakdown arrays and `phase_overlap_studies`, each count being distinct nctId.
- **Findings_Generator**: The Scoring_Exporter component that produces rules-based finding sentences from the computed numbers, with no AI, ML, or LLM.
- **Evidence_Builder**: The Scoring_Exporter component that builds the `evidence.json` per-disease NCT list and method notes.
- **Sources_Builder**: The Scoring_Exporter component that builds `sources.json` from `fetch_log.json`.
- **PII_Check**: The Scoring_Exporter component that scans every output string value against the Email_Pattern and Phone_Pattern before any file is written.
- **Atomic_JSON_Writer**: The Scoring_Exporter component that serializes the output deterministically and stages then commits all four files atomically.
- **Input_Files**: The five input files `studies.csv`, `sites.csv`, `places_ma.csv`, `fetch_log.json`, and `study_diseases.csv`.
- **Output_Files**: The four output files `what.json`, `investigate.json`, `evidence.json`, and `sources.json` in `web/public/data/`.
- **Web_Data_Dir**: The output directory `web/public/data/`.
- **MA_Study**: A study in `studies.csv` that has at least one site in `sites.csv` whose state is Massachusetts (data-contract MA study definition).
- **Eligible_Study**: For a given measure, an MA_Study whose `study_diseases.csv` row for that measure has `match_status` equal to `included` (data-contract "eligible for a disease").
- **Measure_Id**: A PLACES measure identifier used as the disease key: `CASTHMA`, `HIGHCHOL`, or `DIABETES`, and later `BPHIGH` or `DEPRESSION` (data-contract).
- **Disease_Scope**: The per-measure set of Eligible_Study nctIds, the T-eligible subset, and the study rows indexed by nctId, produced by the MA_Index_Builder.
- **T**: The index numerator for a measure: the count of distinct nctIds that are Eligible_Study, have `overallStatus` equal to `RECRUITING`, and have at least one MA site whose site status is `RECRUITING` (data-contract T definition).
- **N**: The sum of PLACES `totalpop18plus` over the (up to 14) MA counties for a measure, each county counted once (data-contract N definition).
- **Prevalence**: The population-weighted MA crude prevalence for a measure, as fractions where 0.102 means 10.2%: `p = sum(pop18 * value/100) / sum(pop18)`, with `p_low` and `p_high` computed the same way from the county `low_confidence_limit` and `high_confidence_limit` (data-contract p, p_low, p_high).
- **Index_Low / Index_Mid / Index_High**: Distinct MA studies per 100,000 affected adults: `low = T / (N * p_high) * 100000`, `high = T / (N * p_low) * 100000`, `mid = T / (N * p) * 100000`, each rounded to 2 decimals (data-contract). `low` uses `p_high` and `high` uses `p_low`.
- **Affected_Adults**: `round(N * p)` for a measure, or null when N or Prevalence is unavailable (data-contract `affected_adults`).
- **Distinct_Count**: A count whose value is the size of a set of distinct nctIds; sites, intervention strings, phases, or repeated condition rows never inflate it (data-contract; `product.md` counting rules).
- **Breakdown**: One `investigate.json` array of `{ "label": str, "count": int }` objects, one of `by_overall_status`, `by_study_type`, `by_intervention_type`, or `by_phase`, each count being a Distinct_Count.
- **Finding**: One `investigate.json` object `{ "text": str, "label": Finding_Label }` produced by the Findings_Generator.
- **Finding_Label**: Exactly one of the two strings `"possible explanation from available records"` or `"cannot determine from public data"` (data-contract).
- **Forbidden_Term**: Any of the banned claim words of `product.md` and `health-safety.md`: "neglected", "underfunded", "needs more trials", "needs more drugs", and any diagnosis, treatment, eligibility, "you should join", recommendation, or prediction wording.
- **Email_Pattern**: The email regular expression reused from `pipeline.patterns`, matching strings of the form `local-part@domain.tld`.
- **Phone_Pattern**: The phone regular expression reused from `pipeline.patterns`, matching North American phone numbers.
- **Is_Sample**: The `sources.json` boolean flag; the Scoring_Exporter always sets it to `false` for real output (data-contract).
- **Deferred_Files**: `where.json` and `ma_counties.geojson`, which this stage does not produce (data-contract WHERE view deferral).

## Requirements

### Requirement 1: Entry Point and Offline Execution

**User Story:** As a Research Gap Index analyst, I want the scoring stage to run locally and offline from a single command, so that I can regenerate dashboard data on a laptop without network access.

#### Acceptance Criteria

1. WHEN a user runs `python -m pipeline.scoring.export` from the repository root on Python 3.11 or newer, THE Scoring_Exporter SHALL read the Input_Files, compute the per-disease metrics, and write the Output_Files to the Web_Data_Dir.
2. WHEN the Scoring_Exporter has written all Output_Files for a run without error, THE Scoring_Exporter SHALL terminate with exit code 0.
3. IF the Scoring_Exporter runs on a Python version earlier than 3.11, THEN THE Scoring_Exporter SHALL stop with a non-zero exit code and an error message naming the required minimum version 3.11, before reading any Input_File or writing any Output_File.
4. WHEN the Scoring_Exporter performs a run, THE Scoring_Exporter SHALL complete that run without sending any network request.
5. THE Scoring_Exporter SHALL import only packages pinned to exact versions in `requirements.txt`.
6. WHEN the Scoring_Exporter writes an Output_File value that cannot be computed from the Input_Files, THE Scoring_Exporter SHALL write `null` for that value rather than `0`.

### Requirement 2: Read Processed Inputs

**User Story:** As a Research Gap Index analyst, I want the scoring stage to load the processed pipeline outputs and the disease matches, so that every published number is derived from pipeline data and not hard-coded.

#### Acceptance Criteria

1. WHEN the Scoring_Exporter starts a run, THE Readers SHALL load exactly these five Input_Files: `studies.csv`, `sites.csv`, `places_ma.csv`, and `fetch_log.json` from `pipeline/processed/`, and `study_diseases.csv` from `pipeline/processed/` or, when a fixture directory is configured, from that fixture directory which takes precedence.
2. WHEN the Readers load `study_diseases.csv`, THE Readers SHALL read exactly the data-contract columns `nctId`, `measureid`, `disease_label`, `match_status`, `exclusion_reason`, `matched_on`, and `matched_term`, treating one row as one `(nctId, measureid)` match.
3. WHEN the Readers decode a multi-valued CSV column (`phases`, `interventionTypes`, `interventionNames`, `conditions`, `stdAges`, `meshTerms`, `meshIds`, `ancestorTerms`, `ancestorIds`), THE Readers SHALL parse that cell as a JSON array of zero or more strings, decoding an empty cell as an empty array.
4. IF a multi-valued column cell is not valid JSON, THEN THE Scoring_Exporter SHALL stop with a non-zero exit code and an error message naming the file, column, and nctId without quoting the cell content, and SHALL leave the Web_Data_Dir unchanged.
5. IF a required Input_File is absent, including `study_diseases.csv` in a production run before Spec 2 has landed, THEN THE Scoring_Exporter SHALL stop with a non-zero exit code and an error message naming the missing file, and SHALL leave the Web_Data_Dir unchanged.
6. IF an Input_File header does not match the expected column set, THEN THE Scoring_Exporter SHALL stop with a non-zero exit code and an error message naming the file and the column mismatch without quoting any cell content, and SHALL leave the Web_Data_Dir unchanged.

### Requirement 3: Produce Dashboard JSON Files

**User Story:** As a dashboard developer, I want the scoring stage to write exactly the four contract JSON files with the exact keys, so that the already-built dashboard can read real data without code changes.

#### Acceptance Criteria

1. WHEN a run completes successfully, THE Scoring_Exporter SHALL write `what.json`, `investigate.json`, `evidence.json`, and `sources.json` to the Web_Data_Dir, each conforming to its data-contract JSON shape, with `what.json`, `investigate.json`, and `evidence.json` each containing exactly one entry per active disease measure (CASTHMA, HIGHCHOL, and DIABETES), the entries ordered ascending by `measure_id`, and `sources.json` written as a single JSON object.
2. THE Scoring_Exporter SHALL set `is_sample` to `false` in `sources.json`, SHALL write `data_as_of` and each `sources[].fetched` as a `YYYY-MM-DD` calendar date, and SHALL write one `prevalence_years` entry for each disease measure present in `what.json`.
3. THE Scoring_Exporter SHALL NOT produce either of the Deferred_Files `where.json` or `ma_counties.geojson`.
4. THE Scoring_Exporter SHALL write `us_studies` as `null` in every `investigate.json` entry.
5. WHERE the Scoring_Exporter emits keys beyond the required data-contract keys, THE Scoring_Exporter SHALL preserve every required contract key with its contract name and type.
6. WHERE a per-disease numeric value defined by the data contract (such as `low`, `mid`, `high`, or `affected_adults`) cannot be computed, THE Scoring_Exporter SHALL write that value as `null` and SHALL NOT write `0` in its place.
7. IF the Scoring_Exporter cannot fully produce all four contract files during a run, THEN THE Scoring_Exporter SHALL stop the run with a non-zero exit code and an error message naming the file that could not be produced, SHALL write no partial or truncated contract file, and SHALL leave any contract files from an earlier run in the Web_Data_Dir unchanged.

### Requirement 4: Compute Scoring Metrics

**User Story:** As a Research Gap Index analyst, I want T, N, prevalence, and the low/mid/high index computed exactly per the data contract, so that the published index is correct and reproducible.

#### Acceptance Criteria

1. WHEN the Scoring_Engine computes `t` for a measure, THE Scoring_Engine SHALL set it to the Distinct_Count of nctIds that are Eligible_Study for that measure, have `overallStatus` equal to `RECRUITING`, and have at least one MA site whose site status is `RECRUITING`, counting each nctId at most once.
2. IF a site's status is absent, empty, or any value other than `RECRUITING`, THEN THE Scoring_Engine SHALL NOT count that site as recruiting when computing `t`.
3. WHEN the Scoring_Engine computes `adults_18plus` (N) for a measure, THE Scoring_Engine SHALL set N to the sum of `totalpop18plus` over the MA counties present for that measure in `places_ma.csv`, counting each distinct county once, where the complete MA county set is exactly 14 counties.
4. WHEN the Scoring_Engine computes prevalence for a measure, THE Scoring_Engine SHALL compute `p`, `p_low`, and `p_high` as population-weighted fractions in the closed range 0.0 to 1.0 using `sum(totalpop18plus * value / 100) / sum(totalpop18plus)` over the counties present, with `value` taken from the county `data_value`, `low_confidence_limit`, and `high_confidence_limit` respectively.
5. WHEN the Scoring_Engine computes the index for a measure and all divisors are non-zero, THE Scoring_Engine SHALL set `low = T / (N * p_high) * 100000`, `high = T / (N * p_low) * 100000`, and `mid = T / (N * p) * 100000`, each rounded to exactly 2 decimal places using round-half-to-even.
6. IF N is unavailable, prevalence (`p`, `p_low`, or `p_high`) is unavailable, or an index divisor equals 0 for a measure, THEN THE Scoring_Engine SHALL write `null` for each affected `low`, `mid`, `high`, or `affected_adults` value rather than `0`, and SHALL leave unaffected values computed.
7. WHEN both N and `p` are available and non-null for a measure, THE Scoring_Engine SHALL set `affected_adults` to `N * p` rounded to the nearest integer using round-half-to-even.
8. IF a measure is absent from `places_ma.csv`, THEN THE Scoring_Engine SHALL write `null` for that measure's `p`, `p_low`, `p_high`, `low`, `mid`, `high`, and `affected_adults`.
9. WHEN a measure is absent from `places_ma.csv`, THE Evidence_Builder SHALL add a `missing_data_notes` entry identifying that measure, and the run SHALL continue to the next measure without terminating.
10. IF the county count for a measure in `places_ma.csv` is not exactly 14, THEN THE Scoring_Exporter SHALL write a warning to stderr identifying the measure and the observed county count, SHALL exit with status code 0, and SHALL compute N and prevalence from the counties present.
11. WHEN the Scoring_Engine emits a measure's record, THE Scoring_Engine SHALL set `prevalence_year` to the PLACES data year associated with that measure's county rows in `places_ma.csv`.

### Requirement 5: Decompose Activity by Distinct Studies

**User Story:** As a Research Gap Index analyst, I want the activity decomposition where every count is distinct studies, so that sites and intervention strings never inflate a count.

#### Acceptance Criteria

1. WHEN the Decomposer builds `by_overall_status`, `by_study_type`, `by_intervention_type`, or `by_phase` for a measure, THE Decomposer SHALL set each Breakdown count to the Distinct_Count of unique Eligible_Study nctIds (match_status = included, across all fetched statuses) carrying that label.
2. THE Decomposer SHALL emit only labels with a count of 1 or more, excluding any label whose Distinct_Count is 0.
3. WHEN a study lists more than one intervention type, THE Decomposer SHALL count that study once under each of its distinct intervention-type labels.
4. WHEN a study has no reported phase, THE Decomposer SHALL assign it the single `by_phase` label "Not reported".
5. WHEN a study's phase is not applicable, THE Decomposer SHALL assign it the single `by_phase` label "Not applicable".
6. WHEN the Decomposer sets `phase_overlap_studies` for a measure, THE Decomposer SHALL set it to the Distinct_Count of Eligible_Study nctIds whose `phases` list has 2 or more elements.
7. WHEN the Decomposer sets `ma_studies` for a measure, THE Decomposer SHALL set it to the Distinct_Count of Eligible_Study nctIds across the fetched statuses RECRUITING, NOT_YET_RECRUITING, ACTIVE_NOT_RECRUITING, and COMPLETED updated in the last 3 years.
8. IF a study has multiple MA sites or appears in multiple rows, THEN THE Decomposer SHALL count that study once per label and SHALL NOT let the repetition change any count.

### Requirement 6: Generate Rules-Based Findings

**User Story:** As a Research Gap Index analyst, I want record-grounded findings generated only from the computed numbers, so that no interpretation is invented and the funding limitation is always stated.

#### Acceptance Criteria

1. THE Findings_Generator SHALL derive every Finding solely from the numbers already computed for that disease's `investigate.json` entry, applying fixed deterministic rules only, and SHALL NOT invoke any AI, machine-learning, or large-language-model component.
2. THE Findings_Generator SHALL assign each Finding exactly one Finding_Label, and that label SHALL be one of exactly the two values `"possible explanation from available records"` or `"cannot determine from public data"`.
3. THE Findings_Generator SHALL include in every `investigate.json` entry at least one Finding.
4. THE Findings_Generator SHALL include in every `investigate.json` entry exactly one Finding whose Finding_Label is `"cannot determine from public data"` and whose text concerns funding levels or sponsor decisions.
5. WHERE a disease's `by_intervention_type` array contains a label `"Drug"` with a count of 1 or more, THE Findings_Generator SHALL include a Finding whose text states that the drug may be an existing drug, a comparator, or a placebo.
6. WHEN the Findings_Generator emits any Finding text, THE Findings_Generator SHALL exclude every Forbidden_Term, where a Forbidden_Term is any case-insensitive occurrence of `"neglected"`, `"underfunded"`, or a phrase stating that the disease needs more trials or more drugs.

### Requirement 7: Protect Against Forbidden Terms and Contact Data

**User Story:** As a Research Gap Index maintainer, I want every output string scanned for banned language and contact data before writing, so that no PII or prohibited claim ever reaches the dashboard.

#### Acceptance Criteria

1. WHEN the Scoring_Exporter has assembled the Output_Files (`what.json`, `investigate.json`, `evidence.json`, `sources.json`) and before any file is written to the Web_Data_Dir, THE PII_Check SHALL scan every string value in every Output_File, including strings nested inside arrays and objects, against the Email_Pattern and the Phone_Pattern.
2. IF any scanned string value matches the Email_Pattern or the Phone_Pattern, THEN THE Scoring_Exporter SHALL stop with a non-zero exit code, SHALL emit an error message naming the file, the field, and which pattern matched without quoting the matched text, and SHALL leave the Web_Data_Dir unchanged with no Output_File written.
3. THE Scoring_Exporter SHALL emit only identifiers, titles, statuses, counts, phases, intervention types, intervention names, URLs, and timestamps, and SHALL NOT emit any person name, email address, or phone number.
4. WHEN the Scoring_Exporter has assembled the Output_Files and before any file is written to the Web_Data_Dir, THE Scoring_Exporter SHALL scan every string value in every Output_File for Forbidden_Terms using case-insensitive substring matching.
5. IF any scanned string value contains a Forbidden_Term, THEN THE Scoring_Exporter SHALL stop with a non-zero exit code, SHALL emit an error message naming the file and the field without quoting the matched text, and SHALL leave the Web_Data_Dir unchanged with no Output_File written.

### Requirement 8: Deterministic and Atomic Output

**User Story:** As a Research Gap Index maintainer, I want deterministic, sorted output written atomically, so that reruns on identical input are byte-identical and a failed run never corrupts committed data.

#### Acceptance Criteria

1. WHEN the Scoring_Exporter serializes `what.json`, `investigate.json`, or `evidence.json`, THE Scoring_Exporter SHALL order the top-level array by `measure_id` using byte-string comparison, serialize JSON object keys in sorted order with non-ASCII characters preserved, encode the file as UTF-8 without a byte order mark, and end the file with a single trailing LF newline.
2. WHEN the Scoring_Exporter serializes `investigate.json`, THE Scoring_Exporter SHALL order each of `by_overall_status`, `by_study_type`, `by_intervention_type`, and `by_phase` by `label` using byte-string comparison.
3. WHEN the Scoring_Exporter serializes `evidence.json`, THE Scoring_Exporter SHALL order each entry's `ncts` array by `nct_id` using byte-string comparison.
4. WHEN the Scoring_Exporter is given byte-identical Input_Files, THE Scoring_Exporter SHALL produce byte-identical Output_Files.
5. WHEN the Scoring_Exporter commits the Output_Files, THE Atomic_JSON_Writer SHALL stage each file and then replace each target file with a single atomic rename, such that no target file is ever observed partially written.
6. IF an error occurs during reading, computation, the PII_Check, or writing, THEN THE Scoring_Exporter SHALL stop with a non-zero exit code, SHALL leave every file in the Web_Data_Dir byte-for-byte unchanged, and SHALL remove any staged temporary files.

### Requirement 9: Correctness Properties

**User Story:** As a Research Gap Index maintainer, I want the scoring stage's universal correctness properties verified by property-based tests, so that the index ordering, prevalence bounds, distinct counting, findings labelling, and schema conformance hold across all generated inputs.

#### Acceptance Criteria

1. WHERE a `what.json` entry has non-null `low`, `mid`, and `high`, THE Scoring_Exporter SHALL produce values, each rounded to exactly 2 decimal places, satisfying `low <= mid <= high`.
2. IF `t`, `N`, `p`, `p_low`, or `p_high` is unavailable for a measure, or an index denominator equals 0, THEN THE Scoring_Exporter SHALL write that measure's `low`, `mid`, `high`, and `affected_adults` as `null` rather than `0`.
3. WHERE a `what.json` entry has non-null `p_low`, `p`, and `p_high`, THE Scoring_Exporter SHALL produce fraction values satisfying `0 <= p_low <= p <= p_high <= 1`.
4. THE Scoring_Exporter SHALL produce every `t`, `ma_studies`, and Breakdown count as an integer that is a Distinct_Count of nctIds, greater than or equal to 0 and less than or equal to `ma_studies`, unchanged by duplicate study rows or multiple MA sites.
5. THE Scoring_Exporter SHALL produce findings such that every Finding has exactly one valid Finding_Label (one of the two allowed values) and each `investigate.json` entry contains exactly one Finding labelled `"cannot determine from public data"`, with no Finding text containing a Forbidden_Term under case-insensitive matching.
6. THE Scoring_Exporter SHALL produce Output_Files that validate against their data-contract shapes, with every required key present and correctly typed, `sources.json.is_sample` equal to `false`, every `investigate.json` entry's `us_studies` equal to `null`, uncomputable numeric values written as `null` rather than `0`, and no output string matching the Email_Pattern or Phone_Pattern.
