# Tech Stack

## Runtime

- Python 3.11 or newer. The pipeline must exit with an error on Python < 3.11 before doing network or file I/O.
- Local command-line program, started by a single command from the repository root.
- Third-party packages are pinned to exact versions (`package==1.2.3`) in one dependency file (`requirements.txt`). Installing that file into a fresh 3.11+ environment must be enough to run the pipeline. Add every new import there.

## Libraries

- **Hypothesis** for property-based tests (required). Each property runs with at least 100 examples.
- **pytest** as the test runner.
- HTTP: standard library `urllib.request` (no third-party HTTP client). 60 s per-attempt timeout and the retry policy below.
- **pandas** is allowed for scoring/export, not required in the fetch step.
- Prefer the standard library (`csv`, `json`, `re`, `pathlib`) where it is enough.

## External APIs

- ClinicalTrials.gov v2: `https://clinicaltrials.gov/api/v2/studies`. Two queries are sent, Q1 first and then Q2. Both use `filter.geo=distance(42.3,-71.8,150mi)`, all study types, `pageSize=1000`, `countTotal=true`, an explicit `fields` list, and `pageToken` pagination.
  - **Q1:** `filter.overallStatus=RECRUITING,NOT_YET_RECRUITING,ACTIVE_NOT_RECRUITING`.
  - **Q2:** `filter.overallStatus=COMPLETED` plus `filter.advanced=AREA[LastUpdatePostDate]RANGE[<cutoff − 1 day>,MAX]`, where the cutoff is the fetch date minus 3 years.
  - Results are merged (Q1 first) and deduplicated by `nctId`. The 3-year `lastUpdatePostDate` rule for COMPLETED is applied again after the fetch.
  - Each query has a hard limit of 100 pages, a repeated token is an error, and the studies fetched must equal that query's `totalCount`.
  - Probes on 2026-10-24 returned Q1 = 9,095 and Q2 = 7,110 (see `.kiro/specs/research-gap-data-pipeline/probe_results.md`).
  - Study-type and status filtering for metrics happens in scoring, not fetching.

## Conventions

- Retry policy: retry on connection errors, timeouts, HTTP 429, and 5xx, waiting 1 s, 2 s, then 4 s (4 attempts max per request). Do not retry other 4xx errors.
- CSV output: UTF-8 without BOM, LF line endings, one header row, fixed column order, quote a cell only when needed. Multi-valued fields are stored as a JSON array string in one cell (e.g. `["PHASE2","PHASE3"]`) so they round-trip exactly. Rows are sorted by Unicode code point for deterministic output.
- Errors go to stderr with a non-zero exit code. Sanity-check warnings also go to stderr, but the run still exits 0.
- Write outputs atomically so a failure never leaves partial or modified files in `pipeline/processed/`.
- Tests make no network requests. A test that tries one must fail and report the URL.

## Website

- Static site: Vite + React, in `web/`. Reads precomputed JSON from `web/public/data/` only.
- Deployed on Vercel (root directory `web`). No backend, no API keys, no server functions.
- Charts: a single lightweight chart library chosen in the dashboard spec; every chart has a text alternative.
- Accessibility: WCAG AA contrast, colour-blind-safe palette, keyboard navigation, visible focus, works at 375 px width.
- Every page shows a footer: "Not medical advice. Index, not prediction." plus source links (ClinicalTrials.gov, CDC PLACES) and a "Data as of" date.
- No third-party logos or brand assets in the UI.

## Common commands

Run from the repository root:

```sh
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# Pipeline: python -m pipeline [--offline]
python -m pipeline            # network run: fetch, then write pipeline/processed/
python -m pipeline --offline  # rerun from pipeline/raw/ with no network requests

# Tests
pytest

# Website
cd web && npm install && npm run dev
```
