---
inclusion: fileMatch
fileMatchPattern: ["pipeline/**", "web/**", "tests/**"]
---
# Data contract between specs 2-4 (do not change without team agreement)

The dashboard (spec "dashboard", branch spec/dashboard) is already built against
the web JSON schema below. Spec 3 must produce exactly these files and keys.
Extra keys are allowed; renaming or removing keys is not.

## Definitions (apply everywhere)
- MA study: a study in studies.csv with >= 1 site in sites.csv whose state is
  Massachusetts. Counts are always distinct nctId, never sites or intervention strings.
- Eligible for a disease: match_status = "included" in study_diseases.csv.
- T (index numerator): eligible MA studies with overallStatus RECRUITING and at
  least one MA site whose site status is RECRUITING (unknown site status never
  counts as recruiting).
- Investigate/evidence scope: eligible MA studies across all fetched statuses
  (RECRUITING, NOT_YET_RECRUITING, ACTIVE_NOT_RECRUITING, COMPLETED updated in last 3 years).
- N = sum of PLACES totalpop18plus over the 14 MA counties.
- p, p_low, p_high = population-weighted MA crude prevalence and limits as
  FRACTIONS (0.102 = 10.2%): sum(pop18 x value/100) / sum(pop18).
- low = T / (N x p_high) x 100000; high = T / (N x p_low) x 100000;
  mid = T / (N x p) x 100000. Round to 2 decimals.
- Uncomputable values are null, never 0.

## Spec 2 output: pipeline/processed/study_diseases.csv
One row per (nctId, measureid) match. Many-to-many allowed.
Columns: nctId, measureid (CASTHMA/HIGHCHOL/DIABETES; later BPHIGH/DEPRESSION),
disease_label, match_status (included/questionable/excluded), exclusion_reason
(empty if included; e.g. child_only, gestational, healthy_volunteers_only),
matched_on (mesh/ancestor/condition_text), matched_term.

## Spec 3 output: web/public/data/ (the dashboard reads these)

### what.json  (array, one entry per disease)
{ "condition": "Asthma", "measure_id": "CASTHMA",
  "low": float|null, "mid": float|null, "high": float|null,
  "t": int,                       // T as defined above
  "affected_adults": int|null,    // round(N x p)
  "adults_18plus": int,           // N            (extra key)
  "p_low": float, "p_high": float, "p": float,  // fractions (p is extra)
  "prevalence_year": "2023",      // PLACES year for this measure (extra key)
  "ctgov_url": "https://clinicaltrials.gov/search?cond=<condition>&locStr=Massachusetts" }

### investigate.json  (array, one entry per disease)
{ "measure_id", "condition",
  "ma_studies": int,              // eligible MA studies, all fetched statuses
  "us_studies": null,             // national comparison deferred: always null
  "by_overall_status":   [{ "label": "Recruiting", "count": int }],
  "by_study_type":       [{ "label": "Interventional", "count": int }],
  "by_intervention_type":[{ "label": "Drug", "count": int }],  // Drug, Biological,
        // Device, Behavioral, Procedure, Dietary Supplement, Other...; distinct
        // nctId per label; a study with several types counts under each
  "by_phase":            [{ "label": "Phase 2", "count": int }], // incl. "Not applicable"
        // (NA) and "Not reported" (empty) as separate labels
  "phase_overlap_studies": int,   // studies listing >1 phase (extra key)
  "findings": [{ "text": str, "label": "possible explanation from available records"
                                   | "cannot determine from public data" }] }
Findings are rules-based text computed from these numbers (no AI). Never use
"neglected", "underfunded", "needs more trials/drugs". Always include one finding
labelled "cannot determine from public data" about funding/sponsor decisions.
"Drug" text must note it may include existing drugs, comparators or placebo.

### evidence.json  (array, one entry per disease)
{ "measure_id", "condition",
  "ncts": [{ "nct_id", "url",
             "title", "status", "study_type", "phases": [str],
             "intervention_types": [str], "intervention_names": [str] }],  // extra keys
  "filters": [str], "mapping_choices": [str], "missing_data_notes": [str] }

### sources.json
{ "data_as_of": "YYYY-MM-DD", "is_sample": false,
  "sources": [{ "name": "ClinicalTrials.gov", "url": "...", "fetched": "YYYY-MM-DD" },
              { "name": "CDC PLACES 2025 county release", "url": "https://data.cdc.gov/...swc5-untb", "fetched": "YYYY-MM-DD" }],
  "prevalence_years": { "CASTHMA": "2023", ... } }   // extra key

### where.json, ma_counties.geojson
DEFERRED. Spec 3 does not produce them. The dashboard hides the WHERE view
(county shapes would need a data source outside clinicaltrials.gov/data.cdc.gov).

## Sample vs real files
The dashboard branch ships SAMPLE files in web/public/data/ (sources.json has
"is_sample": true). When Spec 3 merges, Spec 3's real files replace them
(resolve merge conflicts by taking Spec 3's version). The UI must show a visible
"Sample data" banner whenever is_sample is true.
