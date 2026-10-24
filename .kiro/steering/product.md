# Product

Research Gap Index is a burden-first research intelligence prototype. It compares
how common selected diseases are among Massachusetts adults with observable
Massachusetts-associated clinical study activity, then decomposes that activity
(study type, drug interventions, status, phase) so researchers can see what the
public records do and do not explain about an apparent mismatch.

## User
Pharmaceutical and biotech R&D strategy and clinical-development professionals
doing exploratory research-landscape review. They use it to decide what to
investigate next, not to make investment or drug-development decisions.

## Core question
For common diseases with substantial adult prevalence in Massachusetts, what does
the composition of MA-associated clinical research look like, and which parts of
an apparent count-based mismatch can public records explain?

## What "gap" means
A descriptive discrepancy between adult prevalence and observed study activity.
It is NOT proof of underfunding, unmet medical need, need for a new drug,
commercial opportunity, or sponsor motives. Do not imply an optimal
burden-to-trial ratio. Index, never prediction or recommendation.

## Differentiation
Focus is the composition of therapeutic research relative to prevalence, with a
traceable drill-down to NCT records. Location/maps are not the hero feature. Do
not claim the general capability is industry-first.

## Scope
- Massachusetts only for all published metrics. The fetch covers a 150-mile
  radius and six states; only MA sites count toward MA metrics.
- 3,145 recruiting studies list a Massachusetts location (ClinicalTrials.gov v2,
  query.locn=Massachusetts, filter.overallStatus=RECRUITING, retrieved 2026-10-24).
- Diseases: start with 3 (asthma, high cholesterol, diabetes) using
  burden_test/inclusion_rules.md. Add high blood pressure / depression only if
  their precision check passes. Fallback: 3 -> 2 -> 1 fully demonstrated disease.
- Burden = CDC PLACES 2025 county crude prevalence, adults 18+ (totalpop18plus),
  with the data year per measure (2022 or 2023). DALYs/severity are not included;
  say so in the app.
- MA study activity does not represent all research relevant to MA patients.

## MVP features (user flow)
1. Select disease: MA adult crude prevalence, population-weighted across
   counties as sum(pop18 x prevalence) / sum(pop18), with data year; and distinct
   MA-associated studies (NCT IDs) per 100,000 affected adults as a low-high
   range [T/(N*p_high), T/(N*p_low)] x 100,000.
2. Decompose activity (distinct NCT IDs each): all eligible -> interventional
   -> DRUG intervention -> BIOLOGICAL (separate) -> by status (active vs
   recently updated completed) -> by reported phase (NA shown as NA; overlaps
   disclosed). "Drug" means a study lists a DRUG-type intervention; it may be an
   existing drug, comparator or placebo.
3. Evidence table: NCT ID, title, status, phases, reported intervention names,
   link. Every count links to its list of studies.
4. Limitations: observed patterns vs what public records cannot explain
   (funding, sponsor motives, unmet need). Prevalence, not severity.
5. Method & sources page: inclusion rules, filters, formulas, data years,
   validation results.

Deferred (not MVP): county map, US/national comparison, AI-generated text,
intervention-name normalization.

## Success
A researcher selects a disease and, in under 1 minute, sees prevalence vs
activity, the drug/status/phase breakdown, at least one record-supported
observation, and what remains unknown, with every number traceable to source.

## Non-goals
No drug efficacy prediction, diagnosis, treatment, eligibility or trial
recommendations; no claims a disease is neglected, underfunded or needs a new
drug; no inferring sponsor motives; no global pipeline; no rare-disease
ontology; no data sources beyond clinicaltrials.gov and data.cdc.gov.

## Counting rules
- Study count = distinct NCT IDs within each disease. A study may count for
  several diseases; totals across diseases need not equal total studies.
- Sites never count as studies; one MA study with several MA sites counts once.
- Site status is separate from overall study status; unknown site status is
  never treated as recruiting.
- Show "unknown" instead of 0 when a value cannot be computed.
- County joins use 5-character FIPS strings.

## Non-negotiable rules
- **No contact data, ever.** Never read, store, or log person names, emails, or phone numbers. Exclude `centralContacts`, `overallOfficials`, `locations[].contacts`, and `responsibleParty` investigator names from API requests, scrub them before anything touches disk, and check every output value against email and phone patterns before writing.
- Logs, errors, and `fetch_log.json` contain only identifiers, counts, URLs, field names, and timestamps.
- A failed run leaves existing files in `pipeline/processed/` byte-for-byte unchanged.
- Runs on a laptop only. No backend, database, or cloud service. Network access is limited to `clinicaltrials.gov` and `data.cdc.gov`.
- Offline reruns from cached raw data must produce byte-identical outputs.
- Every displayed number is computed from pipeline output, never hard-coded.