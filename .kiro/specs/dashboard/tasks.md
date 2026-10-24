# Implementation Plan: Dashboard

## Overview

This plan builds the static Vite + React + TypeScript Dashboard in `web/` in test-driven, incremental steps. Scaffolding and the pure data layer come first (types, validators, `loadJson`, and the pure logic modules), each paired with its property-based test so correctness is locked down before any UI consumes it. Shared layout (Nav + Footer) and the two accessible visualizations (dot+whisker chart, county choropleth) come next, then the six routed pages, and finally wiring, sample data fixtures, and a full build + test verification pass.

Every task builds on earlier ones and ends integrated into the app — no orphaned code. All property-based tests use fast-check at a minimum of 100 runs and are tagged `// Feature: dashboard, Property N: <text>`. Example/edge-case tests use @testing-library/react + jsdom with `fetch` mocked; no test makes a real network request.

## Tasks

- [ ] 1. Scaffold the Vite + React + TypeScript project and tooling
  - Create the `web/` Vite + React + TypeScript app (`web/package.json`, `tsconfig.json`, `vite.config.ts`, `index.html`, `src/main.tsx`, `src/App.tsx` placeholder).
  - Add and configure the test stack: Vitest with jsdom environment, `@testing-library/react`, `@testing-library/jest-dom`, and `fast-check`; wire a `vitest.config.ts` (or `test` block in `vite.config.ts`) and a `test` npm script using `vitest --run`.
  - Add `web/vercel.json` with a SPA rewrite of all paths to `/index.html`, and document that the Vercel project root directory is `web`.
  - Add `react-router-dom` (v6) and `d3-geo` as pinned dependencies; create the base folder layout (`src/data/`, `src/components/`, `src/pages/`, `src/styles/`, `src/test/`).
  - _Requirements: 1.1, 1.3, 1.4, 13.3_

- [ ] 2. Data contract types, palette, and cancer-measure set
  - [ ] 2.1 Define TypeScript types for the JSON contract
    - Create `src/data/types.ts` with `WhatEntry`, `WhereEntry`, `SourceEntry`, `SourcesData`, `CountyFeature`, and the `LoadState<T>` discriminated union exactly as in the design.
    - _Requirements: 2.1, 2.2, 2.3, 2.8_

  - [ ] 2.2 Define the colour-blind-safe palette and cancer-measure set
    - Create `src/styles/palette.css` with the CSS custom properties (`--bg`, `--ink`, `--accent`, `--focus`, `--seq-1..5`, `--nodata`) from the design.
    - Create `src/data/cancerMeasures.ts` exporting `CANCER_MEASURE_IDS` (a `ReadonlySet<string>` seeded with `"CANCER"`) and `isCancerCondition(measureId)`.
    - _Requirements: 5.8, 8.4, 14.1, 14.2, 5.2_

- [ ] 3. Schema validators (pure)
  - [ ] 3.1 Implement entry validators
    - Create `src/data/validators.ts` with hand-written type guards `validateWhatEntry`, `validateWhereEntry`, `validateSourceEntry`, and `validateSourcesData`, enforcing presence/type, non-empty strings, `https://` URL prefixes, `>= 0` numbers, non-negative integers for count fields, `YYYY-MM-DD` dates, and `low <= mid <= high` for What entries.
    - _Requirements: 2.1, 2.2, 2.3, 3.4, 5.9_

  - [ ]* 3.2 Write property test for schema validation
    - **Property 1: Schema validation accepts valid entries and rejects invalid ones**
    - **Validates: Requirements 2.1, 2.2, 2.3, 3.4, 5.9**
    - Tag: `// Feature: dashboard, Property 1: ...`; fast-check arbitraries for valid entries and each kind of violation; `numRuns: 100`.

- [ ] 4. Data layer: loadJson and load states
  - [ ] 4.1 Implement loadJson with timeout, validation, and state mapping
    - Create `src/data/loadJson.ts` implementing `loadJson<T>(path, validateEntry)`: `AbortController` with a 10 s timeout, same-origin relative `/data/` fetch, JSON parse, per-entry validation that omits invalid entries and counts them, all-omitted/empty → `empty`, otherwise `ready` with `omittedCount` and `isSample`; map network/404/abort → `error:"network"`/`"timeout"`, parse failure → `error:"parse"`, each naming the file.
    - _Requirements: 1.7, 3.1, 3.2, 3.3, 3.4, 3.5, 3.6, 15.3_

  - [ ]* 4.2 Write property test for omit-invalid-and-preserve-order
    - **Property 2: Loading omits exactly the invalid entries and preserves order**
    - **Validates: Requirements 3.4, 5.9**
    - Tag: `// Feature: dashboard, Property 2: ...`; stub `fetch` with a generated mixed-validity array; `numRuns: 100`.

  - [ ]* 4.3 Write property test for all-omitted/empty → empty state
    - **Property 3: All-omitted or empty input yields the empty state**
    - **Validates: Requirements 3.5, 5.7**
    - Tag: `// Feature: dashboard, Property 3: ...`; `numRuns: 100`.

  - [ ]* 4.4 Write unit tests for loadJson error states
    - Network rejection, 404, malformed JSON / wrong top-level shape, and a >10 s timeout each produce the correct `error` state naming the file and render no numbers; `fetch` is mocked.
    - _Requirements: 1.7, 3.2, 3.3_

- [ ] 5. Pure logic modules for pages and visualizations
  - [ ] 5.1 Implement condition partition and sort
    - Create `src/data/conditions.ts` with `partitionByCancer(entries)` (cancer vs non-cancer using `CANCER_MEASURE_IDS`) and `sortConditions(entries)` (ascending `mid`, ties broken by ascending case-insensitive `condition`).
    - _Requirements: 5.2, 5.3, 6.2, 6.4, 15.1_

  - [ ]* 5.2 Write property test for the tab partition
    - **Property 5: The tab split is a disjoint, covering partition that matches the cancer-measure set**
    - **Validates: Requirements 5.2, 6.4**
    - Tag: `// Feature: dashboard, Property 5: ...`; `numRuns: 100`.

  - [ ]* 5.3 Write property test for sort + text-alternative ordering
    - **Property 4: Conditions are sorted ascending by midpoint with alphabetical tie-break, and the text alternative matches**
    - **Validates: Requirements 5.3, 6.1, 6.2, 15.1**
    - Tag: `// Feature: dashboard, Property 4: ...`; include datasets with duplicate `mid` values; `numRuns: 100`.

  - [ ] 5.4 Implement top-finding selection
    - Add `selectTopFinding(entries)` to `src/data/conditions.ts`: the non-cancer condition with the minimum `mid`, ties broken by case-insensitively smallest `condition`.
    - _Requirements: 4.2, 4.3_

  - [ ]* 5.5 Write property test for top-finding selection
    - **Property 6: The home top finding is the lowest-midpoint non-cancer condition, ties broken alphabetically**
    - **Validates: Requirements 4.2, 4.3**
    - Tag: `// Feature: dashboard, Property 6: ...`; `numRuns: 100`.

  - [ ] 5.6 Implement chart scale
    - Create `src/data/chartScale.ts` with `chartScale(entries)` returning a linear scale mapping values to x positions such that `x(low) <= x(mid) <= x(high)` for every entry.
    - _Requirements: 5.1, 5.6_

  - [ ]* 5.7 Write property test for chart scale / range display
    - **Property 7: Displayed index values always show the full low-high range, with the dot inside the whisker**
    - **Validates: Requirements 5.1, 5.6**
    - Tag: `// Feature: dashboard, Property 7: ...`; `numRuns: 100`.

  - [ ] 5.8 Implement county state resolution and over-30-miles aggregation
    - Create `src/data/where.ts` with `resolveCountyState(whereData, measureId, countyFips)` returning a distance bucket when a matching entry exists and an explicit no-data marker otherwise (never the zero bucket), and `sumAdultsOver30mi(whereData, measureId)` summing `adults_over_30mi` over exactly that condition's entries.
    - _Requirements: 8.1, 8.5, 9.1, 8.3, 9.4_

  - [ ]* 5.9 Write property test for county resolution
    - **Property 8: Every county resolves to its own distance bucket or an explicit no-data marker**
    - **Validates: Requirements 8.1, 8.5, 9.1**
    - Tag: `// Feature: dashboard, Property 8: ...`; `numRuns: 100`.

  - [ ]* 5.10 Write property test for the over-30-miles total
    - **Property 9: The over-30-miles total equals the sum across counties for the selected condition**
    - **Validates: Requirements 8.3, 9.4**
    - Tag: `// Feature: dashboard, Property 9: ...`; `numRuns: 100`.

- [ ] 6. Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 7. Data providers (React Context)
  - Create `src/data/providers.tsx` with `WhatDataProvider`, `WhereDataProvider`, `SourcesProvider`, and `CountyBoundariesProvider`, each fetching its file once per page view via `loadJson` and exposing the `LoadState` through a hook; derive `isSample` from `sources.json`'s `is_sample`.
  - Add shared loading/error/empty presentational helpers (loading indicator, "This data is currently unavailable" naming the file, "No valid data is available") used by all pages.
  - _Requirements: 3.1, 3.2, 3.3, 3.5, 15.3, 2.5_

- [ ] 8. Shared layout: Nav, Footer, SkipLink, focus management
  - [ ] 8.1 Implement Layout, Nav, and SkipLink
    - Create `src/components/Layout.tsx` rendering `<SkipLink>`, `<Nav>`, `<main id="main">`, and `<Footer>`; `Nav` links to Home, WHAT, WHERE, Method, Build using `<NavLink>` with `aria-current="page"` and a visible active style; move keyboard focus to `#main` on route change.
    - _Requirements: 12.1, 13.1, 13.2, 13.4, 14.3, 14.4, 14.7_

  - [ ] 8.2 Implement Footer
    - Create `src/components/Footer.tsx` consuming Sources_Data: always render the exact Disclaimer_Text "Not medical advice. Index, not prediction.", one named link per Source_Entry to its `url`, and the `data_as_of` value labeled "Data as of"; on Sources load failure still show the disclaimer and "Source information is unavailable" in place of links and date.
    - _Requirements: 12.1, 12.2, 12.3, 12.4, 12.5_

  - [ ]* 8.3 Write property test for footer presence/disclaimer across routes
    - **Property 11: The footer and its disclaimer appear on every page**
    - **Validates: Requirements 12.1, 12.2**
    - Tag: `// Feature: dashboard, Property 11: ...`; render each route in the routing table; `numRuns: 100` over the route set.

  - [ ]* 8.4 Write property test for source link rendering
    - **Property 10: Every source renders as a named link to its URL with its fetched date**
    - **Validates: Requirements 10.2, 12.3**
    - Tag: `// Feature: dashboard, Property 10: ...`; assert Footer and Method page render exactly one link per source; `numRuns: 100`.

- [ ] 9. DotWhiskerChart and its text alternative
  - [ ] 9.1 Implement DotWhiskerChart (SVG) with text-alternative table
    - Create `src/components/DotWhiskerChart.tsx`: inline SVG with a whisker from `low` to `high` and a dot at `mid` per condition using `chartScale`; axis label "recruiting MA trial sites per 100,000 affected adults (18+)"; `role="img"` + `aria-describedby` pointing at a `TextAlternative` table (columns `condition`, `low`, `mid`, `high`, `studies`, `affected_adults`) in chart order; missing cells show "unavailable"; each row is a keyboard-focusable control that navigates to the detail page by `measure_id`; palette colours with non-colour text labels.
    - _Requirements: 5.1, 5.3, 5.4, 5.5, 5.6, 5.8, 5.9, 6.1, 6.2, 6.3, 6.6, 14.2, 14.5, 14.8_

  - [ ]* 9.2 Write unit/edge tests for the chart and table
    - Empty tab shows "No conditions are available in this tab" and the table shows headers with no rows plus a no-data note; `aria-describedby` links chart to table; missing cell shows "unavailable"; tab switch updates both within budget.
    - _Requirements: 5.7, 6.3, 6.4, 6.5, 6.6_

- [ ] 10. CountyMap and its text alternative
  - [ ] 10.1 Implement CountyMap (d3-geo SVG choropleth) with text-alternative table
    - Create `src/components/CountyMap.tsx`: render 14 county paths from `ma_counties.geojson` via a `d3-geo` projection fit to the collection; fill each county by `resolveCountyState` bucket using the sequential ramp, with a hatched "no data" pattern for counties lacking an entry; a `<select>` condition control updates map and table; show `sumAdultsOver30mi` total in both the map region and the table; `role="img"` + `aria-describedby` → table of each `county`, `miles_to_nearest`, `adults_over_30mi`; legend text conveys buckets.
    - _Requirements: 8.1, 8.2, 8.3, 8.4, 8.5, 9.1, 9.2, 9.3, 9.4, 14.2, 14.5, 14.8_

  - [ ]* 10.2 Write unit/edge tests for the map and table
    - Zero Where_Data shows "No distance data is available"; county with no matching entry renders hatched (not zero); selector change updates table; `aria-describedby` association present.
    - _Requirements: 8.5, 8.6, 9.2, 9.3_

- [ ] 11. Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 12. Pages
  - [ ] 12.1 Implement Home_Page
    - Create `src/pages/Home.tsx`: one-sentence problem statement (1-200 chars); top finding from `selectTopFinding` naming the condition and its low-high range; a visible-text `<Link>` to `/what`; "no condition data available" message when there are zero valid non-cancer entries; loading/error/empty states via the What provider.
    - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5, 4.6_

  - [ ] 12.2 Implement What_View
    - Create `src/pages/What.tsx`: non-cancer tab (default) and cancer tab using `partitionByCancer` + `sortConditions`, rendering `DotWhiskerChart`; empty-tab message; selecting a condition navigates to `/condition/:measureId`.
    - _Requirements: 5.1, 5.2, 5.3, 5.5, 5.6, 5.7, 6.4, 15.1_

  - [ ] 12.3 Implement Condition_Detail_Page
    - Create `src/pages/ConditionDetail.tsx` for `:measureId`: show `studies`, `sites`, `affected_adults` (labeled 18+), and the low-high Index_Value with the unit string; a ClinicalTrials.gov link to `ctgov_url` opening in a new context (`target="_blank" rel="noopener noreferrer"`) or an "unavailable" message when `ctgov_url` is absent/empty; the severity-vs-commonness caveat; grade-8 copy with ≤20-word definitions for "interventional" and "prevalence" at first use; no diagnosis/eligibility text; "condition not found" + link back to `/what` for an unknown id.
    - _Requirements: 5.10, 7.1, 7.2, 7.3, 7.4, 7.5, 7.6, 7.7_

  - [ ]* 12.4 Write unit tests for the detail page
    - Known id shows exact counts and unit string; unknown id shows not-found + back link; absent `ctgov_url` shows unavailable message; definitions present; no diagnosis/eligibility text.
    - _Requirements: 5.10, 7.1, 7.2, 7.3, 7.5, 7.6, 7.7_

  - [ ] 12.5 Implement Where_View
    - Create `src/pages/Where.tsx`: render `CountyMap` with the condition selector and the over-30-miles total; loading/error/empty states via the Where and County-boundaries providers.
    - _Requirements: 8.1, 8.2, 8.3, 8.6, 9.1, 9.3, 9.4_

  - [ ] 12.6 Implement Method_Page
    - Create `src/pages/Method.tsx`: the formula (sites per 100,000 affected adults 18+); each Source_Entry as a named link with its `fetched` date; the severity-vs-commonness limit; the PLACES-coverage/18+ limit; grade-8 copy.
    - _Requirements: 10.1, 10.2, 10.3, 10.4, 10.5_

  - [ ] 12.7 Implement Build_Page and NotFoundPage
    - Create `src/pages/Build.tsx` titled "How we built it with Kiro" with full GitHub blob links (`https://github.com/ethancfay/research-gap-index/blob/main/...`) to the `.kiro/` spec and steering files and `KIRO_LOG.md`, plus a short Kiro-usage description; create `src/pages/NotFound.tsx` for unknown routes.
    - _Requirements: 11.1, 11.2, 11.3, 13.3_

- [ ] 13. Create sample data fixtures
  - Create `web/public/data/what.json` with ≥4 entries with distinct `measure_id` (≥1 cancer `"CANCER"` and ≥3 non-cancer), all nine fields in bounds, `low <= mid <= high`, `https://clinicaltrials.gov/...` `ctgov_url`.
  - Create `web/public/data/where.json` with exactly one entry per each of the 14 MA `county_fips` for one condition (plus optional extra conditions for the selector).
  - Create `web/public/data/sources.json` with `data_as_of`, `is_sample: true`, and two Source_Entry items (ClinicalTrials.gov, CDC PLACES) with `https://` urls and `YYYY-MM-DD` `fetched` dates.
  - Create `web/public/data/ma_counties.geojson` as a FeatureCollection of exactly 14 Features, each `properties.county_fips` a 5-char string matching `where.json`, simplified to ≤ 300 KB.
  - _Requirements: 2.4, 2.5, 2.6, 2.7, 2.8_

- [ ] 14. Wire the router, providers, and sample-data label
  - [ ] 14.1 Assemble AppRouter and mount providers
    - Update `src/App.tsx` / `src/main.tsx` to use `BrowserRouter` with the routing table (`/`, `/what`, `/condition/:measureId`, `/where`, `/method`, `/build`, `*`), wrapping routes in `Layout` and the appropriate per-page providers; render the sample-data label in the header region (above the fold at 375 px) when `is_sample` is true.
    - _Requirements: 1.1, 2.5, 4.5, 13.1, 13.2, 13.3, 13.4_

  - [ ]* 14.2 Write property test for runtime request confinement
    - **Property 12: Runtime data requests are same-origin and confined to the data directory**
    - **Validates: Requirements 1.2**
    - Tag: `// Feature: dashboard, Property 12: ...`; render page-view sequences with `fetch` mocked and assert every request path is same-origin under `/data/`; `numRuns: 100`.

  - [ ]* 14.3 Write unit tests for routing, sample fixtures, and accessibility
    - Routing: navigation reaches every page without full reload, direct-URL entry renders each route, active page indicated, focus moves to `#main` on route change (Req 13, 14.7).
    - Sample fixtures: shipped files load with zero omitted entries, ≥1 cancer + ≥3 distinct non-cancer ids, exactly 14 distinct `county_fips` for the designated condition, 14 GeoJSON features ≤ 300 KB, matching FIPS between GeoJSON and `where.json`; sample-data label renders when `is_sample` is true and is absent otherwise (Req 2.4-2.8).
    - Accessibility/layout: `aria-describedby` chart/map ↔ table; keyboard-operable controls with visible focus and programmatic labels; palette contrast pairs meet WCAG AA; no horizontal overflow at 375 px and the three lowest-`mid` non-cancer conditions appear first; one fetch per data file per page (Req 14, 15.1, 15.3).
    - _Requirements: 2.4, 2.5, 2.6, 2.7, 2.8, 13.1, 13.2, 13.3, 13.4, 14.1, 14.2, 14.3, 14.4, 14.5, 14.6, 14.7, 14.8, 15.1, 15.3_

- [ ] 15. Final checkpoint - Ensure the build and full test run pass
  - Run `npm run build` in `web/` and the full `vitest --run` suite; fix any failures; ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional (tests) and can be skipped for a faster MVP, but they implement the 12 Correctness Properties and the design's example/edge-case coverage and are strongly recommended.
- Each property-based test is a single fast-check test at `numRuns: 100`, tagged `// Feature: dashboard, Property N: <text>`, targeting the pure logic modules so generators stay cheap and in-memory.
- All tests mock `fetch`; a test that performs real network I/O must fail.
- Each task references specific requirements for traceability; checkpoints provide incremental validation.

## Task Dependency Graph

```json
{
  "waves": [
    { "id": 0, "tasks": ["2.1", "2.2"] },
    { "id": 1, "tasks": ["3.1", "5.1", "5.4", "5.6", "5.8"] },
    { "id": 2, "tasks": ["3.2", "4.1", "5.2", "5.3", "5.5", "5.7", "5.9", "5.10"] },
    { "id": 3, "tasks": ["4.2", "4.3", "4.4", "7"] },
    { "id": 4, "tasks": ["8.1", "8.2", "9.1", "10.1", "13"] },
    { "id": 5, "tasks": ["8.3", "8.4", "9.2", "10.2", "12.1", "12.2", "12.3", "12.5", "12.6", "12.7"] },
    { "id": 6, "tasks": ["12.4", "14.1"] },
    { "id": 7, "tasks": ["14.2", "14.3"] }
  ]
}
```
