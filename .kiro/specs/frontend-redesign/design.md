# Design Document: frontend-redesign

## Overview

This is a **restyle and relayout, not a rewrite**. The approach is a CSS retheme of the existing design tokens in `web/src/styles/palette.css` plus wrapping each page's existing content in card containers. Every existing component, all existing copy, data wiring (`web/src/data` providers and helpers), per-route focus management, and the existing test suite are reused and kept green (Req 1, Req 6). Because all component CSS (`Layout.css`, `DotWhiskerChart.css`, etc.) already reads the shared custom properties, retheming the tokens cascades everywhere. Only two kinds of behavioural change are added: Nav text links become accessible icon buttons (Req 4), and three small additive content pieces are introduced — per-bar value labels + caveats on the chart (Req 9.3, Req 10) and a client-side "no intervention listed" count on Investigate (Req 16). All source changes stay under `web/src` (Req 1.1); JSON stays read-only (Req 1.2).

## Architecture

Files that change (all under `web/src`):

- **`styles/palette.css`** — retheme the existing tokens to Palette_Tokens: `--surface`/page `#FBF8F3`, `--card` navy `#263342` with light text, nav + inner panels `#E3EEFB`, accents `#2F5C9A` / `#2E4A6E`, keep `--radius-card` ≥ 12px (large rounded corners). Add a comment recording that this palette supersedes the `visual-design.md` steering token palette for this feature (Req 2, Req 3.2). Chart marks (`--accent`/`--bg`) are re-tuned to stay legible on navy cards (Req 2.5).
- **`components/Card.tsx` + `Card.css`** (NEW, small, reusable) — the navy-card / light-inner-panel container with large radius, used to wrap page content. Restyle vehicle only; no data logic (Req 2.2, Req 6.5).
- **`components/Layout.tsx` + `Layout.css`** — Nav text links become Nav_Icon_Buttons (chart icon for WHAT, √x icon for Method) each with a visible label/tooltip **and** non-empty `aria-label`, active state not by colour alone, visible focus (Req 4). Shell, SkipLink, SampleDataBanner, header brand "Research Gap Index", Footer, per-route focus all reused unchanged (Req 6.1).
- **`components/DotWhiskerChart.tsx` + `.css`** — additive only: a direct low–high value label adjacent to each whisker (Req 9.3). Zero-based linear scale (`chartScale`), ticks (`axisTicks`), and the text-alternative table are unchanged (Req 9.1, 9.2, Req 8.4).
- **`pages/What.tsx`** — wrap chart in a "Burden vs. research activity by disease" card; render the two mandatory caveats in the card **next to** the chart (not inside the SVG), shown only while the chart is shown (Req 8.1, Req 10).
- **`pages/Home.tsx`, `Method.tsx`, `Build.tsx`, `Investigate.tsx`** — content wrapped in Cards with the mockup titles; data hooks and copy semantics unchanged (Req 6.5, Req 7, 11, 12, 13).
- **`pages/Investigate.tsx`** — additive: display No_Intervention_Count near the intervention-type panel, the intervention/phase overlap notes (Req 15), the F2 traceability limitation near Index_Numerator_T (Req 17), and "unknown" for `us_studies` (Req 18).
- **`data/noInterventionCount.ts`** (NEW helper) — the one new data computation (see Data handling).

Palette reconciliation (Req 3.2) is recorded in two committed places: this design's Architecture note above, plus a comment block in `palette.css`.

## Components and Interfaces

Compact map of each existing file, its change type (restyle-only vs. small additive change), and the requirement it serves. The one new data computation is flagged.

| File | Change type | Serves |
|------|-------------|--------|
| `styles/palette.css` | Restyle (retheme tokens) + reconciliation comment | Req 2, 3 |
| `components/Card.tsx` / `Card.css` | NEW restyle container | Req 2.2, 6.5 |
| `components/Layout.tsx` / `Layout.css` | Nav → icon buttons w/ accessible names; shell reused | Req 4, 6.1 |
| `components/Footer.tsx` | Restyle only (copy/sources/date unchanged) | Req 21 |
| `components/LoadStateView.tsx` | Reused unchanged | Req 6.3, 6.4 |
| `components/DotWhiskerChart.tsx` | Additive: per-bar value labels; scale/table unchanged | Req 9.1–9.3, 8.4 |
| `pages/Home.tsx` | Restyle into cards; top-finding via `selectTopFinding` | Req 7 |
| `pages/What.tsx` | Cards + caveat block next to chart | Req 8, 10 |
| `pages/Investigate.tsx` | Cards + No_Intervention_Count + overlap + F2 + F3 | Req 13–18 |
| `pages/Method.tsx` | Restyle into one card | Req 11 |
| `pages/Build.tsx` | Restyle into one card | Req 12 |
| `pages/NotFound.tsx`, `App.tsx` routing | Routes unchanged | Req 5 |
| `data/noInterventionCount.ts` | **NEW** computation | Req 16 (F1) |

**New data computation (F1):** `noInterventionCount(evidence)` counts the disease's Evidence_Data `ncts` whose `intervention_types` array is empty. It is the only new logic; everything else reuses `selectTopFinding`, `conditions.sortConditions`, `chartScale`, `axisTicks`, `investigateHeadline`, and `forbiddenTerms`.

## Data Models

No new data schemas are introduced. The redesign consumes the existing read-only JSON shapes unchanged — What_Data, Investigate_Data, Evidence_Data, Sources_Data (per the data-contract) — via the existing `web/src/data` types and providers. The only new derived value is `No_Intervention_Count: number` (F1), computed by `noInterventionCount(ncts)` from Evidence_Data and never persisted or read from Investigate_Data.

## Data Handling

- All four JSON files (`what.json`, `investigate.json`, `evidence.json`, `sources.json`) are read **read-only** through the existing providers; nothing under `web/public/data/` is written (Req 1.2).
- Investigate additionally subscribes to **Evidence_Data** (already provided on nearby routes) to compute No_Intervention_Count client-side; it is never read from an Investigate_Data field (Req 16.3). If Evidence_Data fails to load, show "unknown" (Req 16.4).
- `us_studies` is null for every disease → render the literal "unknown", never 0, never a fabricated number (Req 18, Req 1.6).
- Near Index_Numerator_T, render the fixed F2 statement that the specific studies composing it cannot be identified because no data field marks them, and render **no** control claiming to list exactly those studies (Req 17).
- No displayed number is hard-coded; every number comes from Data_Layer output (Req 1.5).

## Accessibility & Health-Safety

- Verify WCAG AA contrast on the new palette: navy cards use light text (≥ 4.5:1 normal / ≥ 3:1 large), and accent-on-card and chart marks-on-navy are checked (Req 2.5, Req 22.1).
- Each Nav_Icon_Button has a non-empty accessible name (visible label/tooltip + `aria-label`), is keyboard operable, and shows a visible focus indicator; active state uses more than colour (Req 4.3–4.6, Req 22.2, 22.3).
- All layouts work down to 375px with no horizontal scroll or clipping (Req 22.4).
- The chart's text-alternative table is retained (Req 8.4, Req 22.5).
- No count-up or value-interpolation animations; numbers render at final value (Req 19).
- Standard_Footer disclaimer, source links, and "Data as of" date kept on every page (Req 21).
- No contact data (names, emails, phone numbers) is read, stored, logged, or displayed; "index" framing only, no "prediction"/"recommendation" and no "neglected"/"underfunded"/"needs more trials" wording (Req 20).

## Correctness Properties

*A property is a characteristic or behavior that should hold true across all valid executions of a system — a formal statement about what the system should do, bridging human-readable specifications and machine-verifiable guarantees.*

This redesign is largely a CSS retheme, so most ACs are covered by example/snapshot/render tests (see Testing Strategy). The properties below cover the pure-logic and render-invariant pieces that vary meaningfully with input.

### Property 1: Top finding is the minimum-midpoint disease

*For any* non-empty list of What_Data entries, `selectTopFinding` returns an entry of that list whose `mid` equals the minimum `mid` across the list (no hard-coded disease name).

**Validates: Requirements 7.3**

### Property 2: No-intervention count is correct and bounded

*For any* list of Evidence_Data `ncts`, `noInterventionCount` equals the number of entries whose `intervention_types` array is empty, and the result is always `>= 0` and `<= ncts.length`.

**Validates: Requirements 16.1**

### Property 3: Chart scale is zero-based and monotonic

*For any* set of What_Data values, the DotWhiskerChart value scale maps `0` to the axis origin (left edge), is monotonically non-decreasing in value, and has a domain maximum at or above the largest `high` (no truncation).

**Validates: Requirements 9.1, 9.3**

### Property 4: Every nav icon button has a non-empty accessible name

*For any* Nav_Icon_Button rendered in the navigation, its `aria-label` is non-empty and a visible text label or tooltip is present.

**Validates: Requirements 4.3**

### Property 5: No forbidden health-safety terms in rendered text

*For any* rendered page, the visible text contains none of the forbidden terms ("neglected", "underfunded", "prediction", "recommendation", or wording implying a disease needs more trials/drugs), matched case-insensitively.

**Validates: Requirements 20.1, 20.3**

### Property 6: Null US comparison renders "unknown"

*For any* disease whose Investigate_Data `us_studies` is null, the rendered US comparison is the literal text "unknown" (never 0), and a numeric value is rendered only when read directly from `us_studies`.

**Validates: Requirements 18.1, 1.6**

## Error Handling

- **Data load failure**: each page keeps the existing `LoadStateView` — loading state while a file loads (Req 6.3), and a data-unavailable component naming the failed file on error (Req 6.4). Method renders this if Sources_Data fails (Req 11.3).
- **Missing/null values**: render "unknown" rather than 0 or a fabricated value at every display site — `us_studies` (Req 18), Index_Numerator_T when absent (Req 14.5), `data_as_of` when absent (Req 21.5), and No_Intervention_Count when Evidence_Data fails (Req 16.4).
- **Empty data**: no valid What_Data entries → no-disease-data message in place of the Top Finding card (Req 7.5) and the chart (Req 8.5); empty breakdown arrays → no-categories message in that panel (Req 13.6).
- **Unmatched routes**: unknown `measureId` → not-found message linking back to WHAT (Req 5.5); any unknown path → NotFound (Req 5.6).

## Testing Strategy

Reuse the existing vitest + Hypothesis-style property suite and keep every existing test passing; run `npm test` (vitest) after each task. Implement each of the six correctness properties above as a single property-based test (minimum 100 iterations), each tagged `// Feature: frontend-redesign, Property N: <text>`. Add focused unit/render tests for the restyle-specific and fixed-text pieces that are not input-varying: the new `Card` component, icon-nav accessible names and client-side navigation, per-bar chart value labels, the mandatory caveats' presence beside the chart (and absence when the chart is hidden), the `noInterventionCount` helper edge cases, the two distinct recruiting numbers and their definitions, overlap-disclosure and F2 traceability text, palette token contrast ratios (unit check over foreground/background token pairs), and a smoke check that Palette_Tokens are defined with card radius ≥ 12px. PBT is intentionally scoped to the pure-logic and render-invariant layer; routing, load/error wiring, and contrast are covered by integration, example, and unit tests respectively.
