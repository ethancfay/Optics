# Data Readiness Report: MA Studies

**Source files:** pipeline/processed/studies.csv, pipeline/processed/sites.csv  
**fetch_date:** 2026-10-24T18:12:26Z  
**MA study definition:** Studies with at least one site whose state (stripped, casefolded) equals "massachusetts" or "ma".  
**Age parsing rule:** `<number> <unit>` where units are Years, Months, Weeks, Days, Hours, Minutes (case-insensitive, plural or singular). Converted to years: month = 1/12 y, week = 7/365.25 y, day = 1/365.25 y, hour = 1/(365.25×24) y, minute = 1/(365.25×24×60) y.

## Overall Counts

- Total distinct NCT IDs of MA studies: 10117
- Total studies in studies.csv: 16079

## StudyType Distribution (MA studies)

| studyType | Count |
|-----------|-------|
| INTERVENTIONAL | 8751 |
| OBSERVATIONAL | 1366 |

## INTERVENTIONAL MA Studies

- Total: 8751
- With at least one non-empty intervention type: 8751 (100.0% of INTERVENTIONAL MA studies)
- With DRUG: 5383
- With BIOLOGICAL: 974
- With both DRUG and BIOLOGICAL: 458

## Phases Distribution

### All MA studies

| Phase | Count |
|-------|-------|
| (empty list) | 1372 |
| EARLY_PHASE1 | 102 |
| NA | 2656 |
| PHASE1 | 1468 |
| PHASE2 | 2772 |
| PHASE3 | 2262 |
| PHASE4 | 316 |

- Studies with more than one phase: 831 (8.2% of MA studies)

### INTERVENTIONAL MA studies

| Phase | Count |
|-------|-------|
| (empty list) | 6 |
| EARLY_PHASE1 | 102 |
| NA | 2656 |
| PHASE1 | 1468 |
| PHASE2 | 2772 |
| PHASE3 | 2262 |
| PHASE4 | 316 |

- Studies with more than one phase: 831 (9.5% of INTERVENTIONAL MA studies)

## overallStatus Distribution (MA studies)

| overallStatus | Count |
|---------------|-------|
| ACTIVE_NOT_RECRUITING | 2350 |
| COMPLETED | 4345 |
| NOT_YET_RECRUITING | 278 |
| RECRUITING | 3144 |

## Child-Only Studies

- maximumAge present and < 18 years: 474
- Empty maximumAge (no upper limit): 6204
- Unparseable maximumAge values: 0 occurrences, 0 distinct

## healthyVolunteers Distribution (MA studies)

| Value | Count |
|-------|-------|
| "true" | 1307 |
| "false" | 8714 |
| empty | 96 |

## MA RECRUITING Sites

- MA studies with at least one MA site whose siteStatus is exactly RECRUITING: 2771
- Of those, INTERVENTIONAL: 2307
- This equals the Sanity_Checker Req 11.1 count: YES
- Req 11.1 threshold is 2000; this count is above the threshold.
