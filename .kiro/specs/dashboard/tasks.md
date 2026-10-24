# Implementation Plan: Dashboard

## Overview

This plan builds the static Vite + React + TypeScript Dashboard in `web/` in test-driven, incremental steps. Scaffolding and the pure data layer come first (the JSON contract types, the palette, the shared constants, the per-type validators, `loadJson`, and the pure logic modules), each paired with its property-based test so correctness is locked down before any UI consumes it. React Context providers for all six data files follow, then the shared layout (Nav + Footer), then the two accessible visualizations (dot+whisker chart, county choropleth with an explicit "unknown" state), then the eight routed pages (Home, WHAT, Investigate, Evidence, WHERE, Method, Build, NotFound), and finally sample data fixtures, router/provider wiring, and a full build + test verification pass.

Every task builds on earlier ones and ends integrated into the app — no orphaned code. The Dashboard reads only six same-origin files from `/data/` (`what.json`, `investigate.json`, `evidence.json`, `where.json`, `sources.json`, `ma_counties.geojson`), never recomputes the index at runtime (it reads precomputed `low`/`mid`/`high`), and never uses any Forbidden_Terms. All property-based tests use fast-check at a minimum of 100 runs and are tagged `// Feature: dashboard, Property N: <text>`. Example/edge-case tests use @testing-library/react + jsdom with `fetch` mocked; no test makes a real network request.

## Tasks

- [x] 1. Scaffold the Vite + React + TypeScript project and tooling
  - Create the `web/` Vite + React + TypeScript app (`web/package.json`, `tsconfig.json`, `vite.config.ts`, `index.html`, `src/main.tsx`, `src/App.tsx` placeholder).
  - Add and configure the test stack: Vitest with jsdom environment, `@testing-library/react`, `@testing-library/jest-dom`, and `fast-check`; wire a `vitest.config.ts` (or `test` block in `vite.config.ts`) and a `test` npm script using `vitest --run`.
  - Add `web/vercel.json` with a SPA rewrite of all paths to `/index.html`, and document that the Vercel project root directory is `web`.
  - Add `react-router-dom` (v6) and `d3-geo` as pinned dependencies; create the base folder layout (`src/data/`, `src/components/`, `src/pages/`, `src/styles/`, `src/test/`).
  - _Requirements: 1.1, 1.3, 1.4, 14.3_

- [x] 2. Data contract types, palette, and shared constants
  - [x] 2.1 Define TypeScript types for the six-file JSON contract
    - Create `src/data/types.ts` with `WhatEntry` (incl. `t`, `p_low`, `p_high`, `ctgov_url`), `LabelCount`, `Finding`, `InvestigateEntry`, `NctRef`, `EvidenceEntry`, `WhereEntry` (`miles_to_nearest: number | null`, `has_verified_site: boolean`), `SourceEntry`, `SourcesData` (with optional `is_sample`), `CountyFeature`, and the `LoadState<T>` discriminated union exactly as in the design.
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 2.12_

  - [x] 2.2 Define the colour-blind-safe palette
    - Create `src/styles/palette.css` with the CSS custom properties (`--bg`, `--ink`, `--accent`, `--focus`, `--seq-1..5`, `--unknown`) from the design, verified for WCAG AA contrast on white.
    - _Requirements: 5.8, 9.5, 15.1, 15.2_

  - [x] 2.3 Define shared label and forbidden-term constants and the content-safety guard
    - Create `src/data/evidenceLabels.ts` exporting the `EvidenceLabel` union and the `EVIDENCE_LABELS` constant object (`possible`, `cannotDetermine`) as the single source of truth for the two permitted finding labels.
    - Create `src/data/forbiddenTerms.ts` exporting `FORBIDDEN_TERMS` (`neglected`, `underfunded`, `needs more trials`, `unmet need`, `optimal ratio`).
    - Create `src/data/contentSafety.ts` with `containsContactData(value)` scanning for email and North-American phone patterns, so validators and tests can enforce that no name/email/phone is ever exposed in data or UI.
    - _Requirements: 2.13, 7.3, 17.1, 17.2, 17.3, 17.4_

- [x] 3. Schema validators (pure)
  - [x] 3.1 Implement entry validators for all five entry types
    - Create `src/data/validators.ts` with hand-written type guards `validateWhatEntry`, `validateInvestigateEntry`, `validateEvidenceEntry`, `validateWhereEntry`, and `validateSourceEntry` (plus `validateSourcesData`), enforcing presence/type, non-empty strings, `https://` URL prefixes (and `https://clinicaltrials.gov/` for NCT urls), `>= 0` numbers, non-negative integers for count fields (`t`, `affected_adults`, `ma_studies`, `us_studies`, `count`), `0 < p <= 1` for `p_low`/`p_high`, `YYYY-MM-DD` dates, `^NCT\d{8}$` for `nct_id`, finding `label` ∈ `EVIDENCE_LABELS`, `low <= mid <= high` and `p_low <= p_high` for What entries, nullable `miles_to_nearest` for Where entries, and rejection of any string field containing contact data.
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 2.13, 3.4, 5.9, 7.3_

  - [x]* 3.2 Write property test for schema validation
    - **Property 1: Schema validation accepts valid entries and rejects invalid ones**
    - **Validates: Requirements 2.1, 2.2, 2.3, 2.4, 2.5, 3.4, 5.9**
    - Tag: `// Feature: dashboard, Property 1: ...`; fast-check arbitraries for valid entries of each type and each kind of violation; `numRuns: 100`.

- [x] 4. Data layer: loadJson and load states
  - [x] 4.1 Implement loadJson with timeout, validation, and state mapping
    - Create `src/data/loadJson.ts` implementing `loadJson<T>(path, validateEntry)`: `AbortController` with a 10 s timeout, same-origin relative `/data/` fetch, JSON parse, per-entry validation that omits invalid entries and counts them, all-omitted/empty → `empty`, otherwise `ready` with `omittedCount`; map network/404/abort → `error:"network"`/`"timeout"`, parse failure or wrong top-level shape → `error:"parse"`, each naming the file.
    - _Requirements: 1.7, 3.1, 3.2, 3.3, 3.4, 3.5, 3.6_

  - [x]* 4.2 Write property test for omit-invalid-and-preserve-order
    - **Property 2: Loading omits exactly the invalid entries and preserves order**
    - **Validates: Requirements 3.4, 5.9**
    - Tag: `// Feature: dashboard, Property 2: ...`; stub `fetch` with a generated mixed-validity array; `numRuns: 100`.

  - [x]* 4.3 Write property test for all-omitted/empty → empty state
    - **Property 3: All-omitted or empty input yields the empty state**
    - **Validates: Requirements 3.5, 5.7**
    - Tag: `// Feature: dashboard, Property 3: ...`; `numRuns: 100`.

  - [x]* 4.4 Write unit tests for loadJson error states across all six files
    - Network rejection, 404, malformed JSON / wrong top-level shape, and a >10 s timeout each produce the correct `error` state naming the file and render no numbers, exercised for each of `what.json`, `investigate.json`, `evidence.json`, `where.json`, `sources.json`, and `ma_counties.geojson`; `fetch` is mocked.
    - _Requirements: 1.7, 3.2, 3.3_

- [x] 5. Pure logic modules for pages and visualizations
  - [x] 5.1 Implement condition sort
    - Create `src/data/conditions.ts` with `sortConditions(entries)` (ascending `mid`, ties broken by ascending case-insensitive `condition`).
    - _Requirements: 5.3, 6.2, 16.1_

  - [x]* 5.2 Write property test for sort + text-alternative ordering
    - **Property 4: Diseases are sorted ascending by midpoint with alphabetical tie-break, and the text alternative matches**
    - **Validates: Requirements 5.2, 5.3, 6.1, 6.2, 16.1**
    - Tag: `// Feature: dashboard, Property 4: ...`; include datasets with duplicate `mid` values; `numRuns: 100`.

  - [x] 5.3 Implement top-finding selection
    - Add `selectTopFinding(entries)` to `src/data/conditions.ts`: the disease with the minimum `mid`, ties broken by case-insensitively smallest `condition`.
    - _Requirements: 4.2, 4.3_

  - [x]* 5.4 Write property test for top-finding selection
    - **Property 5: The home top finding is the lowest-midpoint disease, ties broken alphabetically**
    - **Validates: Requirements 4.2, 4.3**
    - Tag: `// Feature: dashboard, Property 5: ...`; `numRuns: 100`.

  - [x] 5.5 Implement chart scale
    - Create `src/data/chartScale.ts` with `chartScale(entries)` returning a linear scale mapping values to x positions such that `x(low) <= x(mid) <= x(high)` for every entry.
    - _Requirements: 5.1, 5.6_

  - [x]* 5.6 Write property test for chart scale / range display
    - **Property 6: Displayed index values always show the full low-high range, with the dot inside the whisker**
    - **Validates: Requirements 5.1, 5.6**
    - Tag: `// Feature: dashboard, Property 6: ...`; `numRuns: 100`.

  - [x] 5.7 Implement county state resolution
    - Create `src/data/where.ts` with `resolveCountyState(whereData, measureId, countyFips)` returning `{ kind: "bucket", miles, bucket }` when a matching entry exists and is not in the Unknown_Distance state, and `{ kind: "unknown" }` when no matching entry exists or the entry has `miles_to_nearest === null && has_verified_site === false` (never the zero-distance bucket, never blank).
    - _Requirements: 9.1, 9.3, 9.4_

  - [x]* 5.8 Write property test for county resolution
    - **Property 7: Every county resolves to its own distance bucket or an explicit unknown marker**
    - **Validates: Requirements 9.1, 9.3, 9.4, 10.1, 10.2**
    - Tag: `// Feature: dashboard, Property 7: ...`; generate Where_Data including Unknown_Distance entries and missing entries; `numRuns: 100`.

- [x] 6. Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 7. Data providers (React Context)
  - Create `src/data/providers.tsx` with `WhatDataProvider`, `InvestigateDataProvider`, `EvidenceDataProvider`, `WhereDataProvider`, `SourcesProvider`, and `CountyBoundariesProvider`, each fetching its file once per page view via `loadJson` and exposing the `LoadState` through a hook; derive the sample-data flag from `sources.json`'s `is_sample`.
  - Add shared loading/error/empty presentational helpers (loading indicator, "This data is currently unavailable" naming the file, "No valid data is available") used by all pages; degrade per file so one file's failure does not blank another's content.
  - _Requirements: 3.1, 3.2, 3.3, 3.5, 2.7, 16.3_

- [x] 8. Shared layout: Nav, Footer, SkipLink, focus management
  - [x] 8.1 Implement Layout, Nav, and SkipLink
    - Create `src/components/Layout.tsx` rendering `<SkipLink>`, `<Nav>`, `<main id="main">`, and `<Footer>`; `Nav` links to Home, WHAT, WHERE, Method, Build using `<NavLink>` with `aria-current="page"` and a visible active style; move keyboard focus to `#main` on route change.
    - _Requirements: 13.1, 14.1, 14.2, 14.4, 15.3, 15.4, 15.7_

  - [x] 8.2 Implement Footer
    - Create `src/components/Footer.tsx` consuming Sources_Data: always render the exact Disclaimer_Text "Not medical advice. Index, not prediction.", one named link per Source_Entry to its `url`, and the `data_as_of` value labeled "Data as of"; on Sources load failure still show the disclaimer and "Source information is unavailable" in place of links and date.
    - _Requirements: 13.1, 13.2, 13.3, 13.4, 13.5_

  - [x]* 8.3 Write property test for footer presence/disclaimer across routes
    - **Property 9: The footer and its disclaimer appear on every page**
    - **Validates: Requirements 13.1, 13.2**
    - Tag: `// Feature: dashboard, Property 9: ...`; render each route in the routing table; `numRuns: 100` over the route set.

  - [x]* 8.4 Write property test for source link rendering
    - **Property 8: Every source renders as a named link to its URL with its fetched date**
    - **Validates: Requirements 11.3, 13.3**
    - Tag: `// Feature: dashboard, Property 8: ...`; assert Footer and Method page render exactly one link per source (Method additionally shows the `fetched` date); `numRuns: 100`.

- [x] 9. DotWhiskerChart and its text alternative
  - [x] 9.1 Implement DotWhiskerChart (SVG) with text-alternative table
    - Create `src/components/DotWhiskerChart.tsx`: inline SVG with a whisker from `low` to `high` and a dot at `mid` per disease using `chartScale`, all diseases in a single chart (no tabs); axis label "distinct recruiting MA studies per 100,000 affected adults (18+)"; `role="img"` + `aria-describedby` pointing at a `TextAlternative` table (columns `condition`, `low`, `mid`, `high`, `t`, `affected_adults`) in chart order; missing cells show "unavailable"; each row is a keyboard-focusable control that navigates to the Investigate page by `measure_id`; palette colours with non-colour text labels; no Forbidden_Terms.
    - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.5, 5.6, 5.8, 5.11, 6.1, 6.2, 6.3, 6.5, 15.2, 15.5, 15.8_

  - [x]* 9.2 Write unit/edge tests for the chart and table
    - Empty data shows "No diseases are available" and the table shows headers with no rows plus a no-data note; `aria-describedby` links chart to table; missing cell shows "unavailable"; selecting a row navigates by `measure_id`.
    - _Requirements: 5.7, 6.3, 6.4, 6.5_

- [x] 10. CountyMap and its text alternative
  - [x] 10.1 Implement CountyMap (d3-geo SVG choropleth) with text-alternative table
    - Create `src/components/CountyMap.tsx`: render 14 county paths from `ma_counties.geojson` via a `d3-geo` projection fit to the collection; fill each county by `resolveCountyState` bucket using the sequential ramp, with a hatched "unknown" pattern (never zero, never blank) for counties in the Unknown_Distance state or with no matching entry; a `<select>` disease control updates map and table; `role="img"` + `aria-describedby` → table of each `county` label and its distance to the nearest verified recruiting site, showing "unknown" (not a number, not blank) for unknown counties; legend text conveys buckets including "unknown"; no Forbidden_Terms.
    - _Requirements: 9.1, 9.2, 9.3, 9.4, 9.5, 9.7, 10.1, 10.2, 10.3, 10.4, 15.2, 15.5, 15.8_

  - [x]* 10.2 Write unit/edge tests for the map and table
    - Zero Where_Data shows "No distance data is available"; a county with no matching entry and an Unknown_Distance county both render hatched "unknown" (not zero, not blank) in map and table; selector change updates map and table; `aria-describedby` association present.
    - _Requirements: 9.3, 9.4, 9.6, 10.2, 10.4_

- [x] 11. Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 12. Pages
  - [x] 12.1 Implement Home_Page
    - Create `src/pages/Home.tsx`: one-sentence problem statement (1-200 chars) framing the burden-vs-activity question; top finding from `selectTopFinding` naming the disease and its low-high range; a visible-text `<Link>` to `/what`; "no disease data available" message when there are zero valid entries; loading/error/empty states via the What provider; describe the finding as a discrepancy and use no Forbidden_Terms.
    - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5, 4.6, 4.7_

  - [x] 12.2 Implement What_View
    - Create `src/pages/What.tsx`: a single `DotWhiskerChart` of all diseases via `sortConditions` (no tabs); empty-data message; selecting a disease navigates to `/investigate/:measureId`.
    - _Requirements: 5.1, 5.2, 5.3, 5.5, 5.6, 5.7, 16.1_

  - [x] 12.3 Implement Investigate_Page
    - Create `src/pages/Investigate.tsx` for `:measureId`: render the four breakdowns (by overall status, study type, intervention type, phase) from each array's `label`/`count` pairs; show `ma_studies` labeled Massachusetts and `us_studies` labeled United States; render each `findings[]` entry with its Evidence_Label badge and never render a causal/uncertain statement without one of the two labels; a link to the Evidence page for the same `measure_id`; grade-8 copy with ≤20-word definitions for "interventional" and "prevalence" at first use; "disease not found" + link back to `/what` for an unknown id; no diagnosis/treatment/eligibility/enrollment text and no Forbidden_Terms.
    - _Requirements: 5.10, 7.1, 7.2, 7.3, 7.4, 7.5, 7.6, 7.7_

  - [x]* 12.4 Write unit tests for the Investigate page
    - Known id shows the four breakdowns from label/count pairs, MA vs US labeled counts, each finding with its Evidence_Label badge, and the definitions; every rendered finding carries a label; unknown id shows not-found + back link; no diagnosis/eligibility text.
    - _Requirements: 7.1, 7.2, 7.3, 7.5, 7.6, 7.7_

  - [x]* 12.5 Write property test for finding-label enforcement
    - **Property 11: Every Investigate finding carries exactly one Evidence_Label**
    - **Validates: Requirements 7.3**
    - Tag: `// Feature: dashboard, Property 11: ...`; generate valid Investigate_Entries and assert each rendered finding shows exactly one Evidence_Label; `numRuns: 100`.

  - [x] 12.6 Implement Evidence_Page
    - Create `src/pages/Evidence.tsx` for `:measureId`: render each `ncts[]` entry as a link to its `url` opening in a new context (`target="_blank" rel="noopener noreferrer"`); show `filters`, `mapping_choices`, `missing_data_notes`; show the `data_as_of` value from Sources_Data labeled "Data as of"; "no contributing studies are available" (no broken link) when `ncts` is empty; "disease not found" + link back to `/what` for an unknown id; no diagnosis/eligibility text and no Forbidden_Terms.
    - _Requirements: 8.1, 8.2, 8.3, 8.4, 8.5, 8.6_

  - [x]* 12.7 Write property test for Evidence NCT links
    - **Property 13: Every Evidence NCT renders as a link to a valid ClinicalTrials.gov URL**
    - **Validates: Requirements 8.1**
    - Tag: `// Feature: dashboard, Property 13: ...`; generate valid Evidence_Entries and assert each `nct_id` renders as a link to its `url`, every `url` begins with `https://clinicaltrials.gov/`, and every `nct_id` matches `^NCT\d{8}$`; `numRuns: 100`.

  - [x]* 12.8 Write unit tests for the Evidence page
    - Known id lists each NCT as a `target="_blank"` link to its url and shows filters/mapping_choices/missing_data_notes and the "Data as of" value; empty `ncts` shows the no-studies message with no broken link; unknown id shows not-found + back link.
    - _Requirements: 8.2, 8.3, 8.4, 8.5_

  - [x] 12.9 Implement Where_View
    - Create `src/pages/Where.tsx`: render `CountyMap` with the disease selector; loading/error/empty states via the Where and County-boundaries providers.
    - _Requirements: 9.1, 9.2, 9.6, 10.4_

  - [x] 12.10 Implement Method_Page
    - Create `src/pages/Method.tsx`: the formula `[T / (N * p_high), T / (N * p_low)] * 100,000` with `T` the distinct recruiting MA study count, `N` the adult (18+) denominator, `p_low`/`p_high` the CDC PLACES confidence limits; the crosswalk and filters; each Source_Entry as a named link with its `fetched` date; the CDC-PLACES-crude-prevalence/no-DALYs limit; the MA-activity-not-all-research limit; grade-8 copy and no Forbidden_Terms.
    - _Requirements: 11.1, 11.2, 11.3, 11.4, 11.5, 11.6_

  - [x] 12.11 Implement Build_Page and NotFoundPage
    - Create `src/pages/Build.tsx` titled "How we built it with Kiro" with full GitHub blob links (`https://github.com/ethancfay/research-gap-index/blob/main/...`) to the `.kiro/` spec and steering files and `KIRO_LOG.md`, plus a short Kiro-usage description; create `src/pages/NotFound.tsx` for unknown routes.
    - _Requirements: 12.1, 12.2, 12.3, 14.3_

- [x] 13. Create sample data fixtures
  - Create `web/public/data/what.json` with 3-5 entries with distinct in-scope `measure_id` (`CASTHMA`, `HIGHCHOL`, `BPHIGH`, `DIABETES`, `DEPRESSION`), all fields in bounds, `low <= mid <= high`, `0 < p_low <= p_high <= 1`, `https://clinicaltrials.gov/...` `ctgov_url`.
  - Create `web/public/data/investigate.json` with one entry per `measure_id` in `what.json`, each with ≥1 item in every breakdown array and ≥1 finding carrying each of the two Evidence_Label values.
  - Create `web/public/data/evidence.json` with one entry per `measure_id` in `what.json`, each with ≥1 NCT (`nct_id` matching `^NCT\d{8}$`, `url` under `https://clinicaltrials.gov/`), plus non-empty `filters`/`mapping_choices` and some `missing_data_notes`.
  - Create `web/public/data/where.json` with exactly one entry per each of the 14 MA `county_fips` for one disease, including ≥1 Unknown_Distance entry (`miles_to_nearest: null`, `has_verified_site: false`); optional extra entries for other diseases to exercise the selector.
  - Create `web/public/data/sources.json` with `data_as_of`, `is_sample: true`, and two Source_Entry items (ClinicalTrials.gov, CDC PLACES) with `https://` urls and `YYYY-MM-DD` `fetched` dates.
  - Create `web/public/data/ma_counties.geojson` as a FeatureCollection of exactly 14 Features, each `properties.county_fips` a 5-char string matching `where.json`, simplified to ≤ 300 KB.
  - No sample file exposes any name, email, or phone number.
  - _Requirements: 2.6, 2.7, 2.8, 2.9, 2.10, 2.11, 2.12, 2.13_

- [x] 14. Wire the router, providers, and sample-data label
  - [x] 14.1 Assemble AppRouter and mount providers
    - Update `src/App.tsx` / `src/main.tsx` to use `BrowserRouter` with the routing table (`/`, `/what`, `/investigate/:measureId`, `/evidence/:measureId`, `/where`, `/method`, `/build`, `*`), wrapping routes in `Layout` and the appropriate per-page providers; render the sample-data label in the header region (above the fold at 375 px) when `is_sample` is true.
    - _Requirements: 1.1, 2.7, 4.5, 14.1, 14.2, 14.3, 14.4_

  - [x]* 14.2 Write property test for runtime request confinement
    - **Property 10: Runtime data requests are same-origin and confined to the data directory**
    - **Validates: Requirements 1.2**
    - Tag: `// Feature: dashboard, Property 10: ...`; render page-view sequences across all six data files with `fetch` mocked and assert every request path is same-origin under `/data/` and none targets another origin; `numRuns: 100`.

  - [x]* 14.3 Write property test for no Forbidden_Terms in rendered copy
    - **Property 12: No rendered page copy contains a Forbidden_Term**
    - **Validates: Requirements 17.1, 17.2, 17.3, 17.4**
    - Tag: `// Feature: dashboard, Property 12: ...`; render every page with generated valid data and assert the rendered text contains none of `FORBIDDEN_TERMS` (case-insensitively); `numRuns: 100`.

  - [x]* 14.4 Write unit tests for routing, sample fixtures, and accessibility
    - Routing: navigation reaches every page without full reload, direct-URL entry renders each route including `/investigate/:measureId` and `/evidence/:measureId`, active page indicated, focus moves to `#main` on route change (Req 14, 15.7).
    - Sample fixtures: the six shipped files load with zero omitted entries; `what.json` has 3-5 distinct in-scope ids; one Investigate_Entry and one Evidence_Entry per id (each breakdown array non-empty, ≥1 finding per Evidence_Label, ≥1 NCT); exactly 14 distinct `county_fips` for the designated disease with ≥1 Unknown_Distance entry; 14 GeoJSON features ≤ 300 KB; matching FIPS between GeoJSON and `where.json`; sample-data label renders when `is_sample` is true and is absent otherwise (Req 2.6-2.12).
    - Content safety: no rendered page text and no sample-file string field matches an email or phone pattern (Req 2.13).
    - Accessibility/layout: `aria-describedby` chart/map ↔ table; keyboard-operable controls with visible focus and programmatic labels; palette contrast pairs meet WCAG AA; no horizontal overflow at 375 px and the three lowest-`mid` diseases appear first; one fetch per data file per page (Req 15, 16).
    - _Requirements: 2.6, 2.7, 2.8, 2.9, 2.10, 2.11, 2.12, 2.13, 14.1, 14.2, 14.3, 14.4, 15.1, 15.2, 15.3, 15.4, 15.5, 15.6, 15.7, 15.8, 16.1, 16.2, 16.3_

- [x] 15. Final checkpoint - Ensure the build and full test run pass
  - Run `npm run build` in `web/` and the full `vitest --run` suite; fix any failures; ensure all tests pass, ask the user if questions arise.

- [x] 16. Revise the Dashboard to match the updated product and data contract
  - Hide the WHERE view: remove the `/where` route from `src/App.tsx` and the WHERE link from `Layout` nav; delete `web/public/data/where.json` and `web/public/data/ma_counties.geojson` (county shapes need a source outside clinicaltrials.gov/data.cdc.gov). Keep `pages/Where.tsx`, `components/CountyMap.tsx`, and the Where/County-boundaries providers unused.
  - National comparison deferred: `us_studies` is always `null`. Change `InvestigateEntry.us_studies` to `number | null`, accept `null` in `validateInvestigateEntry`, and render "National comparison not included in this version" on the Investigate page when it is `null`.
  - Index definition text: clarify that `T` counts recruiting MA studies and that Investigate/Evidence cover all four fetched statuses; add optional `prevalence_year` to `WhatEntry` and show it next to the prevalence-derived column in the WHAT text-alternative table.
  - Evidence table: add `title`, `status`, `phases`, and `intervention_names` columns (from new optional `NctRef` keys), keeping the NCT link; show "unknown" for any omitted detail.
  - Add the Drug-count caption next to the intervention-type breakdown: "Drug means the study lists a drug intervention; it may be an existing drug, comparator or placebo." (Req 7.8).
  - Keep the visible "Sample data" banner shown when `sources.json` `is_sample` is true (Req 2.7).
  - Update the sample JSON files (`what.json`, `investigate.json`, `evidence.json`, `sources.json`) with the new/extra keys.
  - Keep all existing tests passing; add tests for the `null` us_studies message, the Drug caption, and the sample-data banner; update the WHERE/geojson-dependent tests for the hidden view.
  - _Requirements: 1.2, 2.1, 2.2, 2.3, 2.5, 2.6, 2.7, 6.1, 7.2, 7.8, 8.1, 9 (hidden), 13.1, 14.1_

- [x] 17. Replace invented sample NCTs with real records
  - Replace the hand-written NCTs in `web/public/data/evidence.json` (4 of 10 are real but unrelated trials — NCT05234567, NCT04776655, NCT04332211, NCT04221100 — and the other 6 do not exist) with real records copied verbatim from `pipeline/processed/studies.csv`, and make the Evidence page render ClinicalTrials.gov codes as readable labels. Spec docs (requirements.md Req 18, design.md sample-data plan + Evidence_Page section + Property 14) are already updated; this task implements them.
  - _Requirements: 18.1, 18.2, 18.3, 18.4, 18.5, 18.6, 18.7, 18.8, 8.1_

  - [x] 17.1 Confirm the spec reflects the plan (design.md + requirements.md)
    - Verify requirements.md Requirement 18 and design.md state: (a) `evidence.json` `ncts` are copied verbatim from `pipeline/processed/studies.csv` and never invented; (b) the Evidence page shows readable labels for ClinicalTrials.gov codes (RECRUITING→Recruiting, ACTIVE_NOT_RECRUITING→Active, not recruiting, PHASE2→Phase 2, NA→Not applicable, INTERVENTIONAL→Interventional, DRUG→Drug) and shows unknown codes unchanged.
    - This is the spec-change checkpoint: do not start 17.2-17.5 until the spec changes are approved.
    - _Requirements: 18.1, 18.2, 18.6, 18.7_

  - [x] 17.2 Add `formatCtgovLabel` and use it on the Evidence page
    - Create a pure `formatCtgovLabel(code: string): string` in `web/src/data/` with a fixed lookup table for the known status, study-type, phase, and intervention-type codes (at least RECRUITING, NOT_YET_RECRUITING, ACTIVE_NOT_RECRUITING, COMPLETED, INTERVENTIONAL, OBSERVATIONAL, PHASE1-4, NA, DRUG, BIOLOGICAL, DEVICE, BEHAVIORAL, PROCEDURE); return a non-empty string for every input and return any unknown code unchanged.
    - Use it in `web/src/pages/Evidence.tsx` for `status`, `study_type`, `phases`, and `intervention_types` (mapping each array element), keeping the existing "unknown" placeholder for omitted details.
    - Add unit tests (each known code maps to its label; an unknown code is returned unchanged) plus a property-based test tagged `// Feature: dashboard, Property 14: ...` at `numRuns: 100` asserting the output is never empty, known codes map to labels, and unknown codes are returned unchanged.
    - _Requirements: 18.6, 18.7, 18.8_

  - [x] 17.3 Rebuild `ncts[]` in `evidence.json` from real records
    - For each `measure_id`, pick up to 3 studies from `pipeline/processed/studies.csv` by exact list-item equality against the disease's MeSH heading (Asthma; Depressive Disorder; Hypertension; Diabetes Mellitus, Type 2; Hypercholesterolemia): a study qualifies when one of its `meshTerms` equals the heading exactly; only if fewer than 3 qualify on `meshTerms`, also admit studies with an exact `ancestorTerms` match. No substring/prefix match — e.g. "Hypertension, Pulmonary" and "Hypertension, Pregnancy-Induced" must NOT match "Hypertension". Prefer `overallStatus` = RECRUITING.
    - Only pick studies with at least one Massachusetts site in `pipeline/processed/sites.csv` (or confirm `studies.csv` is already MA-only and record in the notes how that was checked).
    - Exclude child-only studies: skip any study whose `stdAges` includes neither `ADULT` nor `OLDER_ADULT` (equivalently `maximumAge` < 18 years), matching Spec 2's inclusion rule.
    - If a disease has 0 qualifying studies, leave its `ncts` empty and add a `missing_data_notes` line saying no qualifying study was found; never invent or substitute.
    - Copy `nctId`, `briefTitle`, `overallStatus`, `studyType`, `phases`, `interventionTypes`, `interventionNames` exactly in ClinicalTrials.gov code form into `nct_id`, `title`, `status`, `study_type`, `phases`, `intervention_types`, `intervention_names`; set `url` = the row's `source_url`. Never write or paraphrase a title.
    - Parse the CSV's JSON-array string encoding for the multi-valued fields (`phases`, `interventionTypes`, `interventionNames`) and split into arrays of individual values.
    - Set each entry's `mapping_choices` to describe the exact-match MeSH-heading selection rule, and add the `missing_data_notes` entry "Sample: hand-picked from the 2026-10-24 fetch; replaced by the scoring export."
    - _Requirements: 18.1, 18.2, 18.3, 18.4, 18.5_

  - [x] 17.4 Update tests that reference specific NCT IDs
    - Find and update any test that asserts a now-removed NCT ID (e.g. NCT04123456) so tests reference the real records now in `evidence.json`; keep the existing Evidence-page and sample-fixture tests passing.
    - _Requirements: 8.1, 18.1_

  - [x] 17.5 Verify and commit in three separate commits
    - Run `tsc`, `npm test`, and `npm run build` in `web/`; fix any failures.
    - Commit as three separate commits: (1) the spec change (requirements.md, design.md, tasks.md); (2) the `formatCtgovLabel` helper plus its tests and the Evidence-page change; (3) the `evidence.json` data change and any updated tests.
    - _Requirements: 18.1, 18.2, 18.6_

  - [ ] 17.6 Exclude child-only studies from the selection
    - Extend the 17.3 selection to drop any study whose `stdAges` includes neither `ADULT` nor `OLDER_ADULT` (equivalently `maximumAge` < 18 years), matching Spec 2's inclusion rule, then re-run the selection and the verbatim check.
    - Update `mapping_choices` to note the adult-only (non-child-only) restriction; re-run `tsc`, `npm test`, `npm run build`; update any test whose expected NCT changed.
    - Commit as two commits: (1) the spec change (requirements.md, design.md, tasks.md); (2) the `evidence.json` data change and any updated tests.
    - _Requirements: 18.1, 18.2, 18.4_

## Notes

- Tasks marked with `*` are optional (tests) and can be skipped for a faster MVP, but they implement the 14 Correctness Properties and the design's example/edge-case coverage and are strongly recommended.
- Each property-based test is a single fast-check test at `numRuns: 100`, tagged `// Feature: dashboard, Property N: <text>`, targeting the pure logic modules (and small render harnesses for Properties 8-13) so generators stay cheap and in-memory.
- All tests mock `fetch`; a test that performs real network I/O must fail.
- The Dashboard reads precomputed `low`/`mid`/`high` and never recomputes the index formula at runtime; it reads only the six same-origin files under `/data/`.
- Each task references specific requirements for traceability; checkpoints provide incremental validation.

## Task Dependency Graph

```json
{
  "waves": [
    { "id": 0, "tasks": ["2.1", "2.2", "2.3"] },
    { "id": 1, "tasks": ["3.1", "5.1", "5.3", "5.5", "5.7"] },
    { "id": 2, "tasks": ["3.2", "4.1", "5.2", "5.4", "5.6", "5.8"] },
    { "id": 3, "tasks": ["4.2", "4.3", "4.4", "7"] },
    { "id": 4, "tasks": ["8.1", "8.2", "9.1", "10.1", "13"] },
    { "id": 5, "tasks": ["8.3", "8.4", "9.2", "10.2", "12.1", "12.2", "12.3", "12.6", "12.9", "12.10", "12.11"] },
    { "id": 6, "tasks": ["12.4", "12.5", "12.7", "12.8", "14.1"] },
    { "id": 7, "tasks": ["14.2", "14.3", "14.4"] },
    { "id": 8, "tasks": ["17.1"] },
    { "id": 9, "tasks": ["17.2", "17.3"] },
    { "id": 10, "tasks": ["17.4"] },
    { "id": 11, "tasks": ["17.5"] }
  ]
}
```
