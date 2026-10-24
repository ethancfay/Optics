# Requirements Document

## Introduction

The frontend-redesign feature is a restyle and relayout of the existing React static site in `web/`. It changes only presentation and layout in `web/src`; it does not change the pipeline, scoring, exports, or the four existing specs (research-gap-data-pipeline, condition-grouping, scoring-export, dashboard). The redesign reads the four already-produced JSON files in `web/public/data/` (`what.json`, `investigate.json`, `evidence.json`, `sources.json`) read-only. Every displayed number is computed from that pipeline output; no number is invented or hard-coded.

The redesign introduces a card-based visual system with a specified palette, icon navigation with accessible labels, and restructured page layouts for Home, WHAT, Method, Build, and the per-disease Investigate and Evidence pages. It preserves all existing routes and all existing accessibility behaviour, keeps the WHAT comparison chart (DotWhiskerChart) on a linear zero-based axis while adding direct per-bar value labels and mandatory caveats, discloses count overlaps, computes a "no intervention listed" count client-side from `evidence.json`, and states three data limitations (F1-F3) explicitly rather than fabricating missing fields.

## Glossary

- **Redesign_Site**: The React application in `web/src` after this redesign. The system that renders all pages and components covered by this document.
- **Data_Layer**: The existing read-only data wiring in `web/src/data` (providers, `loadJson`, validators, `conditions.sortConditions`, `selectTopFinding`, `chartScale`, `axisTicks`, `investigateHeadline`). Reused unchanged except where this document requires a new client-side computation.
- **What_Data**: The parsed contents of `web/public/data/what.json`: one entry per disease with `condition`, `measure_id`, `low`, `mid`, `high`, `t`, `affected_adults`, `adults_18plus`, `p`, `p_low`, `p_high`, `prevalence_year`, `ctgov_url`.
- **Investigate_Data**: The parsed contents of `web/public/data/investigate.json`: one entry per disease with `measure_id`, `condition`, `ma_studies`, `us_studies`, `by_overall_status`, `by_study_type`, `by_intervention_type`, `by_phase`, `phase_overlap_studies`, `findings`.
- **Evidence_Data**: The parsed contents of `web/public/data/evidence.json`: one entry per disease with `measure_id`, `condition`, `ncts` (each with `nct_id`, `url`, `title`, `status`, `study_type`, `phases`, `intervention_types`, `intervention_names`), `filters`, `mapping_choices`, `missing_data_notes`.
- **Sources_Data**: The parsed contents of `web/public/data/sources.json`: `data_as_of`, `is_sample`, `sources`, `prevalence_years`.
- **DotWhiskerChart**: The existing SVG range chart that renders each disease as a whisker from `low` to `high` with a dot at `mid`, on a linear zero-based axis. Has an existing text-alternative table.
- **Index_Value**: The distinct MA-associated studies per 100,000 affected adults for a disease, shown as a low-high range `[low, high]` with a midpoint `mid`, from What_Data. Called an index, never a prediction or recommendation.
- **Index_Numerator_T**: The What_Data `t` value for a disease: eligible MA studies that are recruiting with at least one MA site whose site status is recruiting. Used in the index. Distinct from the study-level recruiting count below.
- **Status_Recruiting_Count**: The Investigate_Data `by_overall_status` entry labelled "Recruiting": the study-level count of eligible MA studies with overall status recruiting. Distinct from Index_Numerator_T.
- **No_Intervention_Count**: The count of a disease's Evidence_Data `ncts` whose `intervention_types` array is empty. Computed client-side from Evidence_Data. Not a key in Investigate_Data.
- **Top_Finding_Disease**: The disease with the lowest Index_Value midpoint across What_Data. In the current real data this is High Cholesterol (mid 0.25, range 0.23-0.27).
- **Palette_Tokens**: The CSS custom properties defining the redesign colours: cream page background `#FBF8F3`, dark navy cards `#263342`, light blue nav bar and inner panels `#E3EEFB`, and blue accents `#2F5C9A` and `#2E4A6E`.
- **Visual_Design_Steering**: The workspace steering file `.kiro/steering/visual-design.md`, which defines a different token palette (`--surface: #F6F8FB`, etc.).
- **Review_Notes**: The file `design/ui-review-notes.md`, which specifies mandatory chart, caveat, overlap, and animation rules for this redesign.
- **Standard_Footer**: The footer rendered on every page containing the text "Not medical advice. Index, not prediction.", source links from Sources_Data, and the "Data as of" date from Sources_Data `data_as_of`.
- **Nav_Icon_Button**: A top-navigation control for one of Home, WHAT, Method, or Build, rendered with an icon.

## Requirements

### Requirement 1: Scope boundary

**User Story:** As a maintainer, I want the redesign confined to the web presentation layer, so that the pipeline, scoring, exports, and other specs stay unchanged.

#### Acceptance Criteria

1. THE Redesign_Site SHALL confine all source-code changes to files under `web/src`.
2. THE Redesign_Site SHALL read `web/public/data/what.json`, `investigate.json`, `evidence.json`, and `sources.json` as read-only input and SHALL NOT write to any file under `web/public/data/`.
3. THE Redesign_Site SHALL leave the pipeline, scoring, and export code byte-for-byte unchanged.
4. THE Redesign_Site SHALL leave the four existing specs (research-gap-data-pipeline, condition-grouping, scoring-export, dashboard) byte-for-byte unchanged.
5. THE Redesign_Site SHALL render every displayed number from Data_Layer output and SHALL NOT display a hard-coded or invented number.
6. IF a value required for display is null or absent in the source JSON, THEN THE Redesign_Site SHALL display "unknown" rather than 0 or a fabricated value.

### Requirement 2: Palette and visual system

**User Story:** As a researcher, I want a calm card-based interface with a consistent palette, so that the tool reads as a professional research instrument.

#### Acceptance Criteria

1. THE Redesign_Site SHALL define Palette_Tokens with cream page background `#FBF8F3`, dark navy cards `#263342`, light blue nav bar and inner panels `#E3EEFB`, and blue accents `#2F5C9A` and `#2E4A6E`.
2. THE Redesign_Site SHALL render primary content sections as cards with a corner radius of at least 12px.
3. THE Redesign_Site SHALL display the product brand name as the exact string "Research Gap Index".
4. WHERE any label would read "TOBEDETERMINED", THE Redesign_Site SHALL display "Research Gap Index" instead.
5. THE Redesign_Site SHALL render all normal-size text and interactive elements at a contrast ratio of at least 4.5:1, and large-scale text at at least 3:1, against their background.
6. THE Redesign_Site SHALL convey every data encoding through a channel in addition to colour (text label, shape, or position), so meaning is never carried by colour alone.

### Requirement 3: Palette reconciliation with steering

**User Story:** As a maintainer, I want the palette conflict with the visual-design steering file recorded as a deliberate decision, so that the chosen colours are a conscious choice rather than an accidental divergence.

#### Acceptance Criteria

1. THE Redesign_Site SHALL use Palette_Tokens from the redesign mockups as the authoritative palette for this feature, taking precedence over the token palette in Visual_Design_Steering.
2. THE Redesign_Site SHALL record the reconciliation that Palette_Tokens supersede the Visual_Design_Steering token palette for this feature in a committed document.
3. WHILE using Palette_Tokens, THE Redesign_Site SHALL preserve WCAG AA contrast (per Req 2.5) and the non-colour encoding requirement (per Req 2.6).

### Requirement 4: Navigation with accessible icon buttons

**User Story:** As a keyboard and screen-reader user, I want the icon navigation to be labelled and operable, so that I can reach every page without relying on icon shape alone.

#### Acceptance Criteria

1. THE Redesign_Site SHALL render a top navigation bar with a Nav_Icon_Button for each of Home, WHAT, Method, and Build.
2. THE Redesign_Site SHALL render the WHAT Nav_Icon_Button with a chart icon and the Method Nav_Icon_Button with a square-root-of-x icon.
3. THE Redesign_Site SHALL give each Nav_Icon_Button both a visible text label or tooltip AND a non-empty `aria-label`.
4. WHEN a user activates a Nav_Icon_Button by click, Enter, or Space, THE Redesign_Site SHALL navigate to the corresponding route via client-side routing without a full document reload.
5. THE Redesign_Site SHALL render the active route's Nav_Icon_Button in a visually distinct state that does not rely on colour alone.
6. WHEN a Nav_Icon_Button receives keyboard focus, THE Redesign_Site SHALL render a visible focus indicator on it.

### Requirement 5: Preserve all existing routes

**User Story:** As a user, I want every existing page to keep working, so that bookmarks and in-app links continue to resolve.

#### Acceptance Criteria

1. THE Redesign_Site SHALL keep the routes `/` (Home), `/what` (WHAT), `/method` (Method), `/build` (Build), `/investigate/:measureId` (Investigate), `/evidence/:measureId` (Evidence), and `*` (NotFound).
2. THE Redesign_Site SHALL keep the WHERE view unrouted.
3. WHEN a user opens `/investigate/:measureId` where `measureId` matches a `measure_id` in Investigate_Data, THE Redesign_Site SHALL render that disease's Investigate page.
4. WHEN a user opens `/evidence/:measureId` where `measureId` matches a `measure_id` in Evidence_Data, THE Redesign_Site SHALL render that disease's Evidence page.
5. IF a user opens an Investigate or Evidence route whose `measureId` matches no entry, THEN THE Redesign_Site SHALL render a not-found message with a link back to WHAT.
6. WHEN a user opens a path matching no defined route, THE Redesign_Site SHALL render the NotFound page.

### Requirement 6: Reuse existing shell and data wiring

**User Story:** As a maintainer, I want the redesign to reuse the existing layout shell and data layer, so that accessibility behaviour and data flow stay intact.

#### Acceptance Criteria

1. THE Redesign_Site SHALL reuse the existing Layout shell, including the skip link, navigation, header, footer, and per-route focus management.
2. THE Redesign_Site SHALL reuse the existing Data_Layer for all data loading and sorting.
3. WHILE a page's data file is loading, THE Redesign_Site SHALL render the existing loading-state component.
4. IF a page's data file fails to load, THEN THE Redesign_Site SHALL render the existing data-unavailable component naming the file.
5. THE Redesign_Site SHALL restructure the Home, Investigate, Method, and Build page markup into cards without changing those pages' data wiring.

### Requirement 7: Home page

**User Story:** As a first-time visitor, I want a short explanation and the top finding, so that I understand the tool and can jump to the full comparison.

#### Acceptance Criteria

1. THE Redesign_Site SHALL render on Home a left card titled "What is Research Gap Index?" containing exactly one explanatory sentence.
2. WHEN What_Data is ready, THE Redesign_Site SHALL render on Home a right card titled "Top Finding" showing Top_Finding_Disease with its low-high Index_Value range.
3. THE Redesign_Site SHALL select Top_Finding_Disease as the What_Data disease with the lowest Index_Value midpoint and SHALL NOT hard-code the disease name.
4. WHEN a user activates the "See every disease" control, THE Redesign_Site SHALL navigate to the WHAT route via client-side routing.
5. IF What_Data has no valid entries, THEN THE Redesign_Site SHALL render a no-disease-data message in place of the Top Finding card contents.

### Requirement 8: WHAT page

**User Story:** As a researcher, I want to compare burden against research activity and then drill into one disease, so that I can see the overall picture and investigate a specific condition.

#### Acceptance Criteria

1. THE Redesign_Site SHALL render on WHAT a top card titled "Burden vs. research activity by disease" containing the DotWhiskerChart.
2. THE Redesign_Site SHALL render on WHAT a bottom card titled "Index range per disease" with a disease picker whose options are exactly the What_Data diseases.
3. WHEN a user selects a disease in the disease picker, THE Redesign_Site SHALL navigate to that disease's Investigate route via client-side routing.
4. THE Redesign_Site SHALL keep the DotWhiskerChart's existing text-alternative table.
5. IF What_Data has no valid entries, THEN THE Redesign_Site SHALL render a no-disease-data message in place of the chart.

### Requirement 9: Chart axis and direct bar labels

**User Story:** As a researcher, I want an undistorted chart with each bar labelled, so that I can read small and large values without a truncated scale.

#### Acceptance Criteria

1. THE DotWhiskerChart SHALL render a linear value axis whose domain starts at zero and ends at or above the largest What_Data `high`, with no truncation.
2. THE DotWhiskerChart SHALL render each disease as a whisker from its What_Data `low` to `high` with a dot at its `mid`.
3. THE DotWhiskerChart SHALL render each disease's low-high value directly adjacent to its whisker, in addition to the axis tick labels.

### Requirement 10: Mandatory chart caveats

**User Story:** As a researcher, I want the fragility of the headline result shown beside the chart, so that I do not read the lowest index as a settled conclusion.

#### Acceptance Criteria

1. WHEN the DotWhiskerChart is displayed, THE Redesign_Site SHALL display, next to it, a caveat stating that High Cholesterol is lowest partly because heart-disease-only trials are excluded.
2. WHEN the DotWhiskerChart is displayed, THE Redesign_Site SHALL display, next to it, a caveat stating that Asthma rests on 8 studies and High Cholesterol on 5 studies.
3. IF the DotWhiskerChart is not displayed, THEN THE Redesign_Site SHALL NOT display the caveats in isolation.

### Requirement 11: Method page

**User Story:** As a researcher, I want the method and sources on one page, so that I can check how every number was produced.

#### Acceptance Criteria

1. WHEN the Method page renders, THE Redesign_Site SHALL render exactly one card titled "Method and Sources".
2. THE Redesign_Site SHALL render the source links and fetched dates on Method from Sources_Data.
3. IF Sources_Data fails to load, THEN THE Redesign_Site SHALL render the existing data-unavailable component on Method.

### Requirement 12: Build page

**User Story:** As a judge, I want a summary of how the project was built with Kiro, so that I can evaluate the development process.

#### Acceptance Criteria

1. WHEN the Build page renders, THE Redesign_Site SHALL render exactly one card titled "How we built it with Kiro" summarizing the content of `KIRO_USAGE.md`.

### Requirement 13: Disease (Investigate) page cards

**User Story:** As a researcher, I want study counts and a breakdown for one disease, so that I can see the composition of its research activity.

#### Acceptance Criteria

1. WHEN an Investigate page renders for a valid disease, THE Redesign_Site SHALL render a card titled "Study Counts".
2. WHEN an Investigate page renders for a valid disease, THE Redesign_Site SHALL render a card titled "Studies Breakdown" with one panel each for `by_overall_status`, `by_study_type`, `by_intervention_type`, and `by_phase` from Investigate_Data.
3. THE Redesign_Site SHALL render the intervention-type panel exactly once.
4. WHEN an Investigate page renders for a valid disease, THE Redesign_Site SHALL render a card titled "What the records show" presenting the Investigate_Data `findings`, each with its label badge.
5. WHEN an Investigate page renders for a valid disease, THE Redesign_Site SHALL render a final card linking to that disease's Evidence route.
6. IF a breakdown array is empty, THEN THE Redesign_Site SHALL render a no-categories message in that panel.

### Requirement 14: Two distinct recruiting numbers

**User Story:** As a researcher, I want the two recruiting figures labelled distinctly, so that I do not mistake one for the other.

#### Acceptance Criteria

1. THE Redesign_Site SHALL display Index_Numerator_T labelled as the recruiting MA-site count used in the index.
2. THE Redesign_Site SHALL display Status_Recruiting_Count labelled as the study-level recruiting count.
3. THE Redesign_Site SHALL present Index_Numerator_T and Status_Recruiting_Count as distinct values and SHALL NOT combine them into a single number.
4. THE Redesign_Site SHALL display a one-phrase definition for each of Index_Numerator_T and Status_Recruiting_Count.
5. IF Index_Numerator_T is null or absent for a disease, THEN THE Redesign_Site SHALL display "unknown" in its place.

### Requirement 15: Overlap disclosures

**User Story:** As a researcher, I want to know that phase and intervention counts can overlap, so that I do not add them into a false total.

#### Acceptance Criteria

1. WHILE the phase panel is displayed and Investigate_Data `phase_overlap_studies` is greater than zero, THE Redesign_Site SHALL display text near the phase panel stating that phase counts can overlap.
2. WHILE the intervention-type panel is displayed, THE Redesign_Site SHALL display text near it stating that intervention-type counts can overlap.

### Requirement 16: Derived "no intervention listed" count (Flag F1)

**User Story:** As a researcher, I want to see how many studies list no intervention, so that the breakdown accounts for records with none.

#### Acceptance Criteria

1. THE Redesign_Site SHALL compute No_Intervention_Count for a disease as the number of Evidence_Data `ncts` whose `intervention_types` array has zero elements.
2. WHEN an Investigate page renders for a valid disease, THE Redesign_Site SHALL display No_Intervention_Count near the intervention-type panel.
3. THE Redesign_Site SHALL compute No_Intervention_Count client-side from Evidence_Data and SHALL NOT read it from any Investigate_Data field.
4. IF Evidence_Data for the disease fails to load, THEN THE Redesign_Site SHALL display "unknown" in place of No_Intervention_Count.

### Requirement 17: Traceability limitation (Flag F2)

**User Story:** As a researcher, I want to know that the exact studies behind the index cannot be listed, so that I do not expect a false drill-down.

#### Acceptance Criteria

1. WHERE Index_Numerator_T is displayed, THE Redesign_Site SHALL render a visible statement that the specific studies composing Index_Numerator_T cannot be identified from the available data because no data field marks those studies.
2. THE Redesign_Site SHALL NOT render any link, button, or filter whose label or action claims to display exactly the set of studies that compose Index_Numerator_T.

### Requirement 18: US comparison unavailable (Flag F3)

**User Story:** As a researcher, I want an honest placeholder when a national comparison is missing, so that I am not shown a fabricated figure.

#### Acceptance Criteria

1. WHERE a US national comparison is referenced for a disease, THE Redesign_Site SHALL render the literal text "unknown" in place of a US comparison value, because Investigate_Data `us_studies` is null for every disease.
2. THE Redesign_Site SHALL NOT render any numeric US comparison value that is not read directly from Investigate_Data `us_studies`.

### Requirement 19: No count-up number animations

**User Story:** As a researcher, I want numbers shown as-is, so that no animation displays values that are not in the data.

#### Acceptance Criteria

1. WHEN a displayed number first becomes visible, THE Redesign_Site SHALL render it at its final data value with no intermediate value shown.
2. THE Redesign_Site SHALL NOT apply any count-up, incrementing, or value-interpolation animation to a displayed number.

### Requirement 20: Health-safety language and framing

**User Story:** As a user, I want safe, non-clinical framing throughout, so that the tool is not mistaken for medical advice.

#### Acceptance Criteria

1. THE Redesign_Site SHALL refer to the computed result as an "index" and SHALL NOT use the words "prediction" or "recommendation" to describe it.
2. THE Redesign_Site SHALL NOT use diagnosis, treatment, eligibility, or trial-recommendation language, including statements directing a user to join, enroll in, or qualify for a trial.
3. THE Redesign_Site SHALL NOT use the terms "neglected" or "underfunded", and SHALL NOT use wording that states or implies a disease needs more trials or drugs.
4. THE Redesign_Site SHALL render a visible statement that the index compares trial opportunity with how common a condition is and does not measure how severe the condition is.
5. WHERE affected adults are shown, THE Redesign_Site SHALL render a statement that the prevalence figure covers adults aged 18 and older.
6. WHERE Index_Value is shown, THE Redesign_Site SHALL render it as a low-high range with both bounds and SHALL NOT render it as a bare single-number ranking.
7. THE Redesign_Site SHALL NOT read, store, log, or display contact data, including person names, email addresses, and phone numbers.

### Requirement 21: Footer on every page

**User Story:** As a user, I want a consistent safety footer with sources and a data date, so that every page carries the disclaimer and provenance.

#### Acceptance Criteria

1. WHEN any page of the Redesign_Site is rendered, THE Redesign_Site SHALL render the Standard_Footer on that page.
2. THE Standard_Footer SHALL display the literal text "Not medical advice. Index, not prediction.".
3. THE Standard_Footer SHALL render one source link for each source entry present in Sources_Data.
4. THE Standard_Footer SHALL display a "Data as of" date read from Sources_Data `data_as_of`.
5. IF Sources_Data `data_as_of` is null or absent, THEN THE Standard_Footer SHALL display "unknown" in place of the date.

### Requirement 22: Accessibility

**User Story:** As a user with assistive technology or a small screen, I want the redesign to stay accessible, so that I can use every page by keyboard and screen reader at phone width.

#### Acceptance Criteria

1. THE Redesign_Site SHALL render all normal-size text and interactive elements at a contrast ratio of at least 4.5:1, and all large-scale text (at least 18pt, or 14pt bold) at at least 3:1, against their background.
2. THE Redesign_Site SHALL allow every interactive control to be reached and operated using only the keyboard.
3. WHEN a focusable control receives keyboard focus, THE Redesign_Site SHALL render a visible focus indicator on it.
4. THE Redesign_Site SHALL render all page content and controls without horizontal scrolling and without clipped content at viewport widths down to and including 375px.
5. THE Redesign_Site SHALL provide a text alternative, as a data table or summary sentence, for every chart.
6. WHEN navigation changes the active route, THE Redesign_Site SHALL move keyboard focus per the existing per-route focus management and SHALL continue to provide the existing skip link.
