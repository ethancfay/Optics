# Implementation Plan: frontend-redesign

## Overview

This plan is a restyle and relayout of the existing React site in `web/`, not a rewrite. Every task reuses existing components, copy semantics, and data wiring, and keeps the existing vitest suite green. Tasks are ordered to match the user's explicit priority order (1-5), with everything beyond priority 5 marked OPTIONAL. All changes stay under `web/src`; the JSON in `web/public/data/` is read-only; no pipeline, scoring, export, or other-spec files are touched.

Every task ends with a sub-step to run the frontend test suite from `web/` (`npm test`, vitest non-watch) and keep all existing tests passing. Run the type check / build too when it is quick.

## Tasks

### Priority 1 — Palette, card styles, and nav

- [-] 1. Retheme the palette tokens to Palette_Tokens
  - Edit `web/src/styles/palette.css` to set the redesign tokens: cream page background `#FBF8F3`, navy cards `#263342` with light text, light-blue `#E3EEFB` for the nav bar and inner panels, accents `#2F5C9A` and `#2E4A6E`, and keep `--radius-card` at >= 12px
  - Re-tune chart mark tokens (`--accent` / `--bg` equivalents) so marks stay legible on navy cards, preserving the non-colour encoding requirement
  - Add a comment block recording the reconciliation that Palette_Tokens supersede the `.kiro/steering/visual-design.md` token palette for this feature
  - Add or adjust a unit test asserting the Palette_Tokens are defined and that the card radius is >= 12px, and a unit check over foreground/background token pairs for AA contrast
  - Run `npm test` (vitest, non-watch) from `web/` and ensure all tests pass; run the type check / build if quick
  - _Requirements: 2.1, 2.2, 2.5, 2.6, 3.1, 3.2, 3.3_

- [-] 2. Create the reusable Card component
  - Create `web/src/components/Card.tsx` and `web/src/components/Card.css`: a navy card container with light inner panels and large corner radius (>= 12px); presentational only, with no data logic
  - Expose a title prop/slot and children for page content wrapping
  - Add a render test for the Card (renders title, renders children, applies the card class)
  - Run `npm test` (vitest, non-watch) from `web/` and ensure all tests pass
  - _Requirements: 2.2, 6.5_

- [x] 3. Convert Layout nav links into accessible icon buttons
  - Edit `web/src/components/Layout.tsx` and `web/src/components/Layout.css` to render a Nav_Icon_Button for each of Home, WHAT, Method, and Build: WHAT uses a chart icon, Method uses a square-root-of-x icon
  - Give each Nav_Icon_Button both a visible text label or tooltip AND a non-empty `aria-label`, a visible focus indicator, and an active-route state that does not rely on colour alone
  - Preserve client-side routing (no full reload), the SkipLink, SampleDataBanner, header brand "Research Gap Index", Footer, and per-route focus management unchanged
  - Update or add Layout tests asserting each button's accessible name, the not-colour-alone active state, and client-side navigation on click/Enter/Space
  - Run `npm test` (vitest, non-watch) from `web/` and ensure all tests pass
  - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5, 4.6, 6.1_

### Priority 2 — WHAT chart direct labels and caveats

- [x] 4. Add direct low-high value labels to the DotWhiskerChart
  - Edit `web/src/components/DotWhiskerChart.tsx` and `web/src/components/DotWhiskerChart.css` to render each disease's low-high value directly adjacent to its whisker (additive)
  - Keep the zero-based linear scale (`chartScale`), the axis ticks (`axisTicks`), and the existing text-alternative table unchanged
  - Update the DotWhiskerChart test to assert a per-bar low-high label is present for each disease
  - Run `npm test` (vitest, non-watch) from `web/` and ensure all tests pass
  - _Requirements: 9.2, 9.3, 8.4_

- [x] 5. Wrap the WHAT chart in a card with caveats and add the index-range picker card
  - Edit `web/src/pages/What.tsx` to wrap the chart in a top card titled "Burden vs. research activity by disease"
  - Render, next to the chart (not inside the SVG), the two mandatory caveats: High Cholesterol is lowest partly because heart-disease-only trials are excluded; Asthma rests on 8 studies and High Cholesterol on 5 studies. Render the caveats only while the chart is shown
  - Add a bottom card titled "Index range per disease" with a disease picker whose options are exactly the What_Data diseases; selecting a disease navigates to that disease's Investigate route via client-side routing
  - Render the no-disease-data message in place of the chart when What_Data has no valid entries
  - Add tests for caveat presence while the chart shows, caveat absence when the chart is hidden, and picker navigation to the Investigate route
  - Run `npm test` (vitest, non-watch) from `web/` and ensure all tests pass
  - _Requirements: 8.1, 8.2, 8.3, 8.5, 10.1, 10.2, 10.3_

### Priority 3 — Home cards and Top Finding

- [x] 6. Restyle Home into the two mockup cards
  - Edit `web/src/pages/Home.tsx` to render a left card titled "What is Research Gap Index?" containing exactly one explanatory sentence, and a right card titled "Top Finding"
  - Compute Top_Finding_Disease via `selectTopFinding` (lowest Index_Value midpoint, not hard-coded) and show it with its low-high Index_Value range
  - Add a "See every disease" control that navigates to the WHAT route via client-side routing
  - Render a no-disease-data message in place of the Top Finding card contents when What_Data has no valid entries; keep copy semantics unchanged
  - Add or adjust Home tests for the two card titles, the `selectTopFinding`-driven disease and range, the navigation control, and the no-data fallback
  - Run `npm test` (vitest, non-watch) from `web/` and ensure all tests pass
  - _Requirements: 6.5, 7.1, 7.2, 7.3, 7.4, 7.5_

### Priority 4 — Disease (Investigate) page cards and overlap notes

- [x] 7. Restyle Investigate into Study Counts and Studies Breakdown cards
  - Edit `web/src/pages/Investigate.tsx` to render a "Study Counts" card and a "Studies Breakdown" card, reusing existing data hooks and copy
  - In Study Counts, present Index_Numerator_T and Status_Recruiting_Count as two distinct recruiting numbers, each with a one-phrase definition, never combined; render "unknown" when Index_Numerator_T is null/absent; render the F2 traceability statement near Index_Numerator_T (the specific studies composing it cannot be identified because no data field marks them) and render no control claiming to list exactly those studies; render "unknown" for `us_studies`
  - In Studies Breakdown, render one panel each for `by_overall_status`, `by_study_type`, `by_intervention_type` (exactly once), and `by_phase`; render a no-categories message for any empty breakdown array
  - Update or add Investigate render tests for the two distinct recruiting numbers and definitions, the single intervention-type panel, the "unknown" US value, the F2 statement, and the no-categories fallback
  - Run `npm test` (vitest, non-watch) from `web/` and ensure all tests pass
  - _Requirements: 13.1, 13.2, 13.3, 13.6, 14.1, 14.2, 14.3, 14.4, 14.5, 17.1, 17.2, 18.1, 18.2_

- [x] 8. Add the client-side no-intervention count and overlap disclosure notes
  - Create `web/src/data/noInterventionCount.ts` computing No_Intervention_Count as the number of Evidence_Data `ncts` whose `intervention_types` array is empty
  - Wire `web/src/pages/Investigate.tsx` to read Evidence_Data and display No_Intervention_Count near the intervention-type panel, computed client-side (never read from an Investigate_Data field); display "unknown" when Evidence_Data fails to load
  - Add the intervention-type overlap note near the intervention-type panel, and the phase overlap note near the phase panel only when `phase_overlap_studies` > 0
  - Add unit tests for `noInterventionCount` (including empty `ncts` and all-empty `intervention_types`) and render tests for the two overlap notes and the displayed count
  - Run `npm test` (vitest, non-watch) from `web/` and ensure all tests pass
  - _Requirements: 15.1, 15.2, 16.1, 16.2, 16.3, 16.4_

### Priority 5 — Method and Build cards

- [x] 9. Restyle Method and Build into single cards
  - Edit `web/src/pages/Method.tsx` to render exactly one card titled "Method and Sources", keeping the source links and fetched dates wired from Sources_Data and the existing data-unavailable component when Sources_Data fails
  - Edit `web/src/pages/Build.tsx` to render exactly one card titled "How we built it with Kiro" summarizing `KIRO_USAGE.md`, keeping all existing copy and links
  - Update or add Method and Build tests for the single card titles and preserved sources wiring
  - Run `npm test` (vitest, non-watch) from `web/` and ensure all tests pass
  - _Requirements: 11.1, 11.2, 11.3, 12.1_

- [x] 10. Priority checkpoint — all priority 1-5 work verified
  - Ensure all tests pass, ask the user if questions arise.

### OPTIONAL (beyond priority 5 — may be skipped under the time box)

- [ ] 11. Optional property-based tests for the design's correctness properties
  - [ ]* 11.1 Property test: top finding is the minimum-midpoint disease
    - **Property 1: Top finding is the minimum-midpoint disease** — for any non-empty What_Data list, `selectTopFinding` returns an entry whose `mid` equals the minimum `mid` (no hard-coded name); minimum 100 iterations; tag `// Feature: frontend-redesign, Property 1`
    - **Validates: Requirements 7.3**
  - [ ]* 11.2 Property test: no-intervention count is correct and bounded
    - **Property 2: No-intervention count is correct and bounded** — for any `ncts` list, `noInterventionCount` equals the number with empty `intervention_types` and is always `>= 0` and `<= ncts.length`; minimum 100 iterations; tag `// Feature: frontend-redesign, Property 2`
    - **Validates: Requirements 16.1**
  - [ ]* 11.3 Property test: chart scale is zero-based and monotonic
    - **Property 3: Chart scale is zero-based and monotonic** — for any What_Data values, the scale maps 0 to the origin, is monotonically non-decreasing, and has a domain max at or above the largest `high`; minimum 100 iterations; tag `// Feature: frontend-redesign, Property 3`
    - **Validates: Requirements 9.1, 9.3**
  - [ ]* 11.4 Property test: every nav icon button has a non-empty accessible name
    - **Property 4: Every nav icon button has a non-empty accessible name** — for any Nav_Icon_Button rendered, its `aria-label` is non-empty and a visible label or tooltip is present; minimum 100 iterations; tag `// Feature: frontend-redesign, Property 4`
    - **Validates: Requirements 4.3**
  - [ ]* 11.5 Property test: no forbidden health-safety terms in rendered text
    - **Property 5: No forbidden health-safety terms in rendered text** — for any rendered page, visible text contains none of the forbidden terms (case-insensitive), reusing `forbiddenTerms`; minimum 100 iterations; tag `// Feature: frontend-redesign, Property 5`
    - **Validates: Requirements 20.1, 20.3**
  - [ ]* 11.6 Property test: null US comparison renders "unknown"
    - **Property 6: Null US comparison renders "unknown"** — for any disease whose `us_studies` is null, the rendered US comparison is the literal "unknown" (never 0), and a numeric value renders only when read directly from `us_studies`; minimum 100 iterations; tag `// Feature: frontend-redesign, Property 6`
    - **Validates: Requirements 18.1, 1.6**
  - Run `npm test` (vitest, non-watch) from `web/` and ensure all tests pass

- [ ] 12. Optional 375px responsive and contrast audit pass
  - [ ]* 12.1 Add render/layout checks that pages have no horizontal scroll or clipped content at 375px, and audit AA contrast token pairs across all pages
    - Run `npm test` (vitest, non-watch) from `web/` and ensure all tests pass
    - _Requirements: 22.1, 22.4_

- [ ] 13. Optional Evidence page restyle for card consistency
  - [ ]* 13.1 Wrap the Evidence page content in Cards for visual consistency, keeping the `/evidence/:measureId` route and all data wiring working
    - Run `npm test` (vitest, non-watch) from `web/` and ensure all tests pass
    - _Requirements: 5.4, 6.5_

## Notes

- Tasks marked with `*` are optional and can be skipped under the time box; everything beyond Priority 5 (tasks 11-13) is OPTIONAL.
- This is a restyle and relayout: reuse existing components and copy semantics; do not change data wiring or existing tests' expectations unless a test must adapt to new markup.
- Every task references specific requirement sub-clauses for traceability and includes an explicit "Run `npm test` and ensure all tests pass" step.
- All source changes stay under `web/src`; JSON in `web/public/data/` is read-only; no pipeline/scoring/export/other-spec changes.
- Property-based tests use the existing vitest + Hypothesis-style suite at a minimum of 100 iterations and are tagged with their property text.

## Task Dependency Graph

```json
{
  "waves": [
    { "id": 0, "tasks": ["1", "2"] },
    { "id": 1, "tasks": ["3", "4"] },
    { "id": 2, "tasks": ["5", "6", "7"] },
    { "id": 3, "tasks": ["8", "9"] },
    { "id": 4, "tasks": ["11.1", "11.2", "11.3", "11.4", "11.5", "11.6", "12.1", "13.1"] }
  ]
}
```
