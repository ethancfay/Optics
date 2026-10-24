# Product

Research Gap Index is a burden-first research intelligence prototype. It compares
how common selected diseases are among Massachusetts adults with observable
clinical research activity, and helps researchers investigate why an apparent
mismatch appears in the available public data.

## User
Pharmaceutical and biotech R&D strategy and clinical-development professionals
doing early opportunity screening. They use it to decide what to investigate
next, not to make investment or drug-development decisions.

## Core question
Why might some diseases with substantial measured burden in Massachusetts show
comparatively limited observable clinical research activity?

## What "gap" means
A descriptive discrepancy between measured burden and observed research activity.
It is NOT proof of underfunding, unmet therapeutic need, commercial opportunity,
or a reason to develop a drug. Do not imply an optimal burden-to-trial ratio.

## Scope
- Massachusetts proof of concept. 3,145 recruiting studies list a Massachusetts
  location (ClinicalTrials.gov v2, query.locn=Massachusetts,
  filter.overallStatus=RECRUITING, retrieved 2026-10-24).
- 3-5 common diseases with a direct CDC PLACES measure match (candidates:
  asthma, high cholesterol, high blood pressure, diabetes, depression).
- Burden = CDC PLACES crude prevalence, adults 18+, county level. DALYs/severity
  are not included; say so in the app.
- MA trial activity does not represent all research relevant to MA patients.

## MVP features (user flow)
1. Burden vs activity (WHAT): per disease, distinct studies (NCT IDs) per 100,000
   affected adults as a low-high range from PLACES confidence limits:
   [T/(N*p_high), T/(N*p_low)] * 100,000. Sites shown as a local breakdown.
2. Investigate: for a selected disease, breakdown by overall status, study type,
   intervention type and phase, and MA vs US study counts (same filters).
   Label findings "possible explanation from available records" or
   "cannot determine from public data".
3. Evidence: list of contributing NCT IDs with links, filters, mapping choices,
   missing data and "Data as of" date.
4. WHERE (secondary): county map of miles to the nearest verified site for the
   disease; show "unknown" when no matching site exists, never 0.
5. Method page: crosswalk, filters, formulas, limits.

## Success
A researcher picks a disease, sees burden vs activity, and reaches at least one
record-supported explanation plus what remains unknown, in under 1 minute.

## Non-goals
No drug efficacy prediction, diagnosis or treatment advice; no claims a disease is
neglected or needs more trials; no inferring pharma motives; no global pipeline;
no rare-disease ontology; no openFDA in the MVP; no AI-generated text.

## Counting rules
- Study count = distinct NCT IDs within each disease. A study may count for
  several diseases; totals across diseases need not equal total studies.
- Site status is separate from overall study status.
- County joins use 5-character FIPS strings.

## Non-negotiable rules
- **No contact data, ever.** Never read, store, or log person names, emails, or phone numbers. Exclude `centralContacts`, `overallOfficials`, `locations[].contacts`, and `responsibleParty` investigator names from API requests, scrub them before anything touches disk, and check every output value against email and phone patterns before writing.
- Logs, errors, and `fetch_log.json` contain only identifiers, counts, URLs, field names, and timestamps.
- A failed run leaves existing files in `pipeline/processed/` byte-for-byte unchanged.
- Runs on a laptop only. No backend, database, or cloud service. Network access is limited to `clinicaltrials.gov` and `data.cdc.gov`.
- Offline reruns from cached raw data must produce byte-identical outputs.