# Product

Research Gap Index shows which common health conditions get few clinical trial
opportunities in Massachusetts, relative to how many adults have them.

## User
Massachusetts patient advocacy organizations who push trial sponsors and
hospitals to open studies for their community's conditions.

## Problem
Massachusetts has ~3,100 recruiting studies, but nobody can see which common
conditions get few trial opportunities relative to how many adults have them.
A pre-build test found recruiting MA sites per 100,000 affected adults ranging
from ~260 (cancer) to under 2 (high cholesterol, asthma, high blood pressure).

## MVP features
1. WHAT view (main): per condition, recruiting MA trial sites per 100,000
   affected adults, shown as a low-high range from CDC PLACES confidence limits.
2. Condition detail: study count, affected adults, link to the matching
   ClinicalTrials.gov search, plain-language caveat.
3. WHERE view (supporting): MA county map of miles to the nearest recruiting
   site for a chosen condition, and affected adults living >30 miles away.
4. Method & sources page: formula, sources with dates, limits, recall check.

## Honest limits
- Compares trial opportunity with how common a condition is, not how severe it is.
- An index, not a prediction. Not medical advice.

## Success
An advocate names 3 under-served conditions in under 1 minute, on a phone.

## Non-goals
No trial matching for individuals, no user accounts, no health data collected,
no severity weighting, no states beyond MA in the MVP, no AI-generated text.

## Components
1. Data pipeline (spec: research-gap-data-pipeline): fetches ClinicalTrials.gov
   v2 and CDC PLACES 2025 county data, writes pipeline/processed/.
2. Condition grouping: maps studies to PLACES measures; must reach >=80% of
   ClinicalTrials.gov's own condition-search count per condition.
3. Scoring and export: computes ranges and distances, writes web/public/data/*.json.
4. Dashboard: static website on Vercel.

## Non-negotiable rules
- **No contact data, ever.** The pipeline never reads, stores, or logs person names, emails, or phone numbers. Exclude `centralContacts`, `overallOfficials`, `locations[].contacts`, and `responsibleParty` investigator names from API requests, scrub them before anything touches disk, and check every output value against email and phone patterns before writing.
- Logs, errors, and `fetch_log.json` contain only identifiers, counts, URLs, field names, and timestamps. Never include excerpts of API response bodies.
- A failed run leaves existing files in `pipeline/processed/` byte-for-byte unchanged.
- Runs on a laptop only. No backend, database, or cloud service. Network access is limited to `clinicaltrials.gov` and `data.cdc.gov`.
- Offline reruns from cached raw data must produce byte-identical outputs.