# Requirements Document

## Introduction

The Dashboard is the public website of the Research Gap Index. It is a static Vite + React single-page application in `web/`, deployed on Vercel with the root directory set to `web/`. The Dashboard reads only precomputed JSON files from `web/public/data/` and sends no requests to any backend, database, API key service, or server-side function. The site has no backend and no AI-generated text.

The audience is pharmaceutical and biotech R&D strategy and clinical-development professionals doing early opportunity screening. They use the Dashboard to decide what to investigate next, not to make investment or drug-development decisions. To that end the Dashboard presents, per disease, the number of distinct recruiting Massachusetts studies (distinct ClinicalTrials.gov NCT IDs) per 100,000 affected adults (18+) as a low-high range, sorted so the diseases with the lowest observed research activity relative to measured burden are easiest to find, and lets the user investigate record-supported explanations for an apparent discrepancy.

The Dashboard never diagnoses, recommends, predicts, or implies eligibility. It describes a discrepancy between measured burden (how common a disease is among Massachusetts adults) and observed research activity; it does not claim a disease is neglected, underfunded, or needs more trials, does not imply an optimal burden-to-trial ratio, does not claim unmet therapeutic need, and does not infer pharmaceutical-company motives. Every page carries a footer disclaimer and source links, every number shown comes from the JSON data files, and every chart has a text alternative for screen readers.

The core metric is distinct studies per 100,000 affected adults, shown as a low-high range computed from CDC PLACES prevalence confidence limits as `[T / (N * p_high), T / (N * p_low)] * 100,000`, where `T` is the distinct recruiting Massachusetts study count for the disease, `N` is the adult (18+) population denominator, and `p_low` and `p_high` are the lower and upper CDC PLACES crude-prevalence confidence limits for that disease. The Investigate and Evidence views cover all four fetched statuses (recruiting, not yet recruiting, active not recruiting, and recently updated completed), whereas `T` counts recruiting Massachusetts studies only.

In this version the WHERE view (a per-county map of distance to the nearest verified recruiting site) is hidden: county shapes would require a data source outside clinicaltrials.gov / data.cdc.gov, so `where.json` and `ma_counties.geojson` are neither shipped nor fetched. The national (US) comparison in the Investigate view is also deferred (`us_studies` is always `null`). The `Where` page and `CountyMap` component code is retained unused so the view can be reinstated later.

This spec also defines sample placeholder JSON files so the site can be built and tested before the `research-gap-data-pipeline` spec produces the real data. The sample files follow the same schema as the real files.

### Open Items and Assumptions

1. The real `what.json`, `investigate.json`, `evidence.json`, `where.json`, and `sources.json` files are produced later by the `research-gap-data-pipeline` and `scoring-export` specs. This spec defines the JSON schema (the data contract) and sample placeholder files with that schema, clearly marked as sample data, so the Dashboard can be developed and tested independently.
2. The project steering files require a single lightweight chart library chosen in the dashboard spec; this document states the need for one library and its accessibility obligations but leaves the specific library name to design, since library selection is an implementation decision.
3. "Sorted by midpoint" (WHAT view) is interpreted as ascending order of the `mid` value, so the disease with the lowest distinct-studies-per-100,000 midpoint (the lowest observed research activity relative to measured burden) appears first.
4. The scope is a fixed set of 3 to 5 common diseases with a direct CDC PLACES prevalence match (candidates: asthma, high cholesterol, high blood pressure, diabetes, depression). All diseases are shown in a single WHAT chart; there is no separate tab.
5. The `data_as_of` date in `sources.json` is the single date shown in the footer "Data as of" label on every page.
6. "Affected adults" always refers to adults aged 18 and older, consistent with CDC PLACES crude prevalence, and the Dashboard labels it as such wherever a count of affected adults is shown.
7. A disease is identified by its `measure_id`; the human-readable `condition` label is used for display. Routes and links use the `measure_id` to select a disease so that display labels can change without breaking links.
8. The Index_Value low-high range is read from the precomputed `low`, `mid`, and `high` fields in `what.json`; the Dashboard does not recompute the formula at runtime. The `t`, `affected_adults`, `p_low`, and `p_high` fields are provided so the Dashboard can display the basis of the range, not so it can recompute it.
9. The Investigate page breakdown data and the Evidence page NCT list are each placed in their own same-origin JSON file (`investigate.json` and `evidence.json`) rather than embedded in `what.json`, so each page loads only the data it needs and the load/error/empty handling applies per file.

## Glossary

- **Dashboard**: The static Vite + React single-page web application in `web/` described by this document.
- **Data_Directory**: The directory `web/public/data/`, the only source of runtime data for the Dashboard.
- **What_Data**: The parsed contents of `web/public/data/what.json`.
- **Investigate_Data**: The parsed contents of `web/public/data/investigate.json`.
- **Evidence_Data**: The parsed contents of `web/public/data/evidence.json`.
- **Where_Data**: The parsed contents of `web/public/data/where.json`.
- **Sources_Data**: The parsed contents of `web/public/data/sources.json`.
- **County_Boundaries**: The parsed contents of `web/public/data/ma_counties.geojson`, the 14 Massachusetts county shapes from U.S. Census cartographic boundary files, simplified for web use.
- **What_Entry**: One element of the What_Data array, describing one disease's Index_Value and its basis.
- **Investigate_Entry**: One element of the Investigate_Data array, describing one disease's study breakdown by status, type, intervention type, and phase, and MA versus US study counts.
- **Evidence_Entry**: One element of the Evidence_Data array, describing one disease's contributing NCT IDs, applied filters, mapping choices, and missing-data notes.
- **Where_Entry**: One element of the Where_Data array, describing one county and disease pair.
- **Source_Entry**: One element of the sources array within Sources_Data, describing one external data source.
- **Disease**: A health condition in scope, identified by its `measure_id` and displayed by its `condition` label.
- **Measure_Id**: The stable identifier of a Disease, used in routes and links.
- **Index_Value**: The number of distinct recruiting Massachusetts studies (distinct NCT IDs) per 100,000 affected adults (18+) for a Disease, expressed as a low-high range with values `low`, `high`, and `mid`, where `low = T / (N * p_high) * 100,000`, `high = T / (N * p_low) * 100,000`, and `mid` is the midpoint value supplied in the data.
- **Distinct_Study_Count**: The number of distinct recruiting Massachusetts ClinicalTrials.gov NCT IDs attributed to a Disease, stored in the `t` field of a What_Entry.
- **Affected_Adults**: The adult (18+) population denominator used for a Disease, stored in the `affected_adults` field.
- **NCT_Id**: A ClinicalTrials.gov study identifier string matching the pattern `NCT` followed by exactly eight digits.
- **Home_Page**: The Dashboard page at the root route showing the problem statement, the top finding, and a link to the WHAT view.
- **What_View**: The Dashboard page showing the per-disease Index_Value chart for all diseases in scope.
- **Investigate_Page**: The Dashboard page showing, for a selected Disease, a breakdown of its studies by overall status, study type, intervention type, and phase, plus MA versus US study counts, with each explanatory finding labeled as either a possible explanation from available records or something that cannot be determined from public data.
- **Evidence_Page**: The Dashboard page showing, for a selected Disease, the list of contributing NCT IDs with links, the applied filters, the mapping choices, the missing-data notes, and the Data_As_Of date.
- **Where_View**: The Dashboard page showing a Massachusetts county map of miles to the nearest verified recruiting site for a selected Disease.
- **Method_Page**: The Dashboard page showing the crosswalk, filters, formula, and limits.
- **Build_Page**: The Dashboard page titled "How we built it with Kiro" linking to `.kiro/` files and `KIRO_LOG.md`.
- **Dot_Whisker_Chart**: A chart that draws, per Disease, a dot at the `mid` value and a whisker spanning from `low` to `high`.
- **County_Map**: The Massachusetts county map shown in the Where_View.
- **Unknown_Distance**: The state of a county and Disease pair for which no verified recruiting site exists, represented in the data and displayed as "unknown", distinct from a numeric distance of zero and from a blank value.
- **Evidence_Label**: One of exactly two labels applied to every explanatory finding on the Investigate_Page: "possible explanation from available records" or "cannot determine from public data".
- **Forbidden_Terms**: The claims the Dashboard must never make, namely that a Disease is "neglected", is "underfunded", or "needs more trials", together with any statement implying an optimal burden-to-trial ratio, claiming unmet therapeutic need, or inferring a pharmaceutical company's motives.
- **Text_Alternative**: A data table or descriptive text that conveys the same information as a chart or map to assistive technology users.
- **Footer**: The page region, present on every page, containing the disclaimer text, source links, and the "Data as of" date.
- **Disclaimer_Text**: The exact string "Not medical advice. Index, not prediction."
- **Data_As_Of**: The `data_as_of` date value in Sources_Data, shown in the Footer.
- **Mobile_Width**: A viewport width of 375 CSS pixels.
- **Colorblind_Safe_Palette**: A color palette chosen in design that remains distinguishable for common forms of color vision deficiency and meets WCAG AA contrast.

## Requirements

### Requirement 1: Static Site Architecture

**User Story:** As a project maintainer, I want the Dashboard to be a static site with no backend, so that it runs on Vercel with no hosting cost, no API keys, and no server-side code.

#### Acceptance Criteria

1. THE Dashboard SHALL be built with Vite and React and SHALL reside in the `web/` directory of the repository.
2. THE Dashboard SHALL read all runtime data only from `what.json`, `investigate.json`, `evidence.json`, and `sources.json` served from the same origin as the Dashboard in the Data_Directory, and SHALL issue zero network requests to any other origin at runtime. (With the Where_View hidden in this version, `where.json` and `ma_counties.geojson` are not fetched.) Fonts and chart code SHALL be bundled with the site. Outbound links that the user clicks (e.g. to ClinicalTrials.gov or a data source) are navigation, not runtime requests, and are allowed.
3. THE Dashboard SHALL run without any backend server, database server, server-side function, or API key.
4. WHERE the Dashboard is deployed on Vercel, THE Dashboard SHALL be configured with the project root directory set to `web`.
5. THE Dashboard SHALL display no text that is generated by an artificial intelligence model at runtime.
6. THE Dashboard SHALL display no third-party logo or brand asset.
7. IF any of `what.json`, `investigate.json`, `evidence.json`, or `sources.json` fails to load or cannot be parsed at runtime, THEN THE Dashboard SHALL display a visible error message indicating which data file could not be loaded and SHALL not display partial or stale data for the failed file.

### Requirement 2: Data Contract and Sample Files

**User Story:** As a dashboard developer, I want a defined JSON schema and sample data files, so that I can build and test the site before the pipeline produces real data.

#### Acceptance Criteria

1. THE Dashboard spec SHALL define `what.json` as a JSON array in which each What_Entry contains the fields `condition` (non-empty string), `measure_id` (non-empty string), `low` (number >= 0), `mid` (number >= 0), `high` (number >= 0), `t` (non-negative integer distinct study count of recruiting Massachusetts studies), `affected_adults` (non-negative integer), `p_low` (number greater than 0 and <= 1), `p_high` (number greater than 0 and <= 1), and `ctgov_url` (string beginning with `https://`), with `low` <= `mid` <= `high` and `p_low` <= `p_high`, and MAY contain the optional extra key `prevalence_year` (non-empty string, the CDC PLACES data year for the measure, e.g. "2023").
2. THE Dashboard spec SHALL define `investigate.json` as a JSON array in which each Investigate_Entry contains the fields `measure_id` (non-empty string), `condition` (non-empty string), `ma_studies` (non-negative integer; eligible Massachusetts studies across all four fetched statuses — recruiting, not yet recruiting, active not recruiting, and recently updated completed), `us_studies` (either the JSON value `null` or a non-negative integer; the national comparison is deferred in this version and is always `null`), `by_overall_status` (array of objects each with `label` non-empty string and `count` non-negative integer), `by_study_type` (array of objects each with `label` non-empty string and `count` non-negative integer), `by_intervention_type` (array of objects each with `label` non-empty string and `count` non-negative integer), `by_phase` (array of objects each with `label` non-empty string and `count` non-negative integer), `findings` (array of objects each with `text` non-empty string and `label` equal to one of the two Evidence_Label strings), and MAY contain the optional extra key `phase_overlap_studies` (non-negative integer).
3. THE Dashboard spec SHALL define `evidence.json` as a JSON array in which each Evidence_Entry contains the fields `measure_id` (non-empty string), `condition` (non-empty string), `ncts` (array of objects each with `nct_id` matching the NCT_Id pattern and `url` a string beginning with `https://clinicaltrials.gov/`), `filters` (array of non-empty strings describing the applied filters), `mapping_choices` (array of non-empty strings describing the crosswalk choices), and `missing_data_notes` (array of strings describing missing data). Each object in `ncts` MAY additionally contain the optional extra keys `title` (string), `status` (string), `study_type` (string), `phases` (array of strings), `intervention_types` (array of strings), and `intervention_names` (array of strings); when present each MUST be free of contact data.
4. THE Dashboard spec SHALL define `where.json` as a JSON array in which each Where_Entry contains the fields `county_fips` (non-empty string), `county` (non-empty string), `condition` (non-empty string), `measure_id` (non-empty string), `miles_to_nearest` (either a number >= 0 or the JSON value `null`), and `has_verified_site` (boolean), where a value of `null` for `miles_to_nearest` together with `has_verified_site` equal to false represents the Unknown_Distance state. NOTE: in this version the Where_View is hidden and `where.json` is not shipped or fetched (see Requirement 9); this schema definition is retained for when the view is reinstated.
5. THE Dashboard spec SHALL define `sources.json` as a JSON object containing a `sources` array in which each Source_Entry contains the fields `name` (non-empty string), `url` (string beginning with `https://`), and `fetched` (ISO 8601 date in `YYYY-MM-DD` form), a top-level `data_as_of` field (ISO 8601 date in `YYYY-MM-DD` form), an optional top-level `is_sample` field (boolean) that, WHEN present and true, indicates the accompanying data files are sample data, and MAY contain the optional extra key `prevalence_years` (object mapping each Measure_Id to its CDC PLACES data year string).
6. THE Dashboard SHALL include sample `what.json`, `investigate.json`, `evidence.json`, and `sources.json` files in the Data_Directory in which every required field is present, each value is of the type and within the bounds defined in criteria 1 through 5, and each file parses as valid JSON. (`where.json` and `ma_counties.geojson` are not shipped in this version because the Where_View is hidden — see Requirement 9.)
7. WHILE the Dashboard is serving data loaded from the sample files rather than real pipeline output, THE Dashboard SHALL display a text label, reachable within the first screen at Mobile_Width without scrolling, stating that the data shown is sample data.
8. THE sample `what.json` SHALL include at least three and at most five Disease entries, each with a distinct `measure_id` drawn from the diseases in scope, so that the WHAT view chart can be exercised.
9. THE sample `investigate.json` SHALL include one Investigate_Entry for each `measure_id` present in the sample `what.json`, each with at least one entry in every breakdown array and at least one finding carrying each of the two Evidence_Label values.
10. THE sample `evidence.json` SHALL include one Evidence_Entry for each `measure_id` present in the sample `what.json`, each with at least one NCT in its `ncts` array.
11. WHERE the Where_View is reinstated in a future version, THE sample `where.json` SHALL include, for one single Disease, exactly one Where_Entry for each of the 14 distinct Massachusetts `county_fips` values, and SHALL include at least one Where_Entry in the Unknown_Distance state, so that both a numeric county and an unknown county can be exercised on the map. (In this version `where.json` is not shipped.)
12. WHERE the Where_View is reinstated in a future version, THE Dashboard spec SHALL define `ma_counties.geojson` as a GeoJSON FeatureCollection of exactly 14 Features, one per Massachusetts county, each with a `county_fips` property (5-character string) that matches the `county_fips` values used in `where.json`, at no more than 300 KB. (In this version `ma_counties.geojson` is not shipped; county shapes would require a data source outside clinicaltrials.gov / data.cdc.gov.)
13. THE Dashboard SHALL expose no investigator name, contact name, official name, email address, or telephone number in any field of any data file or in any rendered page.

### Requirement 3: Data Loading and Error Handling

**User Story:** As a researcher, I want the site to show clear status when data is loading or unavailable, so that I am never shown blank or misleading content.

#### Acceptance Criteria

1. WHEN a Dashboard page that requires What_Data, Investigate_Data, Evidence_Data, Where_Data, or Sources_Data is opened, THE Dashboard SHALL load the required JSON file from the Data_Directory before rendering the page's data content.
2. WHILE a required JSON file is loading and fewer than 10 seconds have elapsed since the load began, THE Dashboard SHALL display a loading indicator in place of the data content.
3. IF a required JSON file cannot be retrieved within 10 seconds of the load beginning, cannot be retrieved due to a network or missing-file error, or cannot be parsed as the schema defined in Requirement 2, THEN THE Dashboard SHALL display an error message stating that the data is unavailable and SHALL display no partial or placeholder numeric values.
4. IF a What_Entry, Investigate_Entry, Evidence_Entry, Where_Entry, or Source_Entry is missing a field required by Requirement 2, THEN THE Dashboard SHALL omit that entry from charts, tables, and lists and SHALL display the remaining valid entries.
5. IF every entry for a required JSON file is omitted under criterion 4, THEN THE Dashboard SHALL display a message stating that no valid data is available and SHALL display no empty chart, table, or list.
6. THE Dashboard SHALL display only numeric values that are present in the loaded JSON data, and SHALL compute no new disease or trial numbers that are not derived solely from those values.

### Requirement 4: Home Page

**User Story:** As a researcher, I want a home page that states the question and the top finding, so that I understand the site's purpose within seconds.

#### Acceptance Criteria

1. WHEN the Home_Page finishes loading, THE Home_Page SHALL display a one-sentence statement, between 1 and 200 characters, of the question that the Research Gap Index addresses.
2. WHEN the Home_Page finishes loading AND What_Data contains at least one valid entry, THE Home_Page SHALL display the top finding as the Disease with the lowest `mid` value in What_Data, naming that Disease and its Index_Value as a low-high range.
3. IF two or more Diseases share the lowest `mid` value, THEN THE Home_Page SHALL select as the top finding the Disease whose name sorts first in case-insensitive ascending alphabetical order.
4. THE Home_Page SHALL display a link, labeled with visible text, that navigates to the What_View.
5. WHEN a user activates the link to the What_View, THE Dashboard SHALL navigate to the What_View within 1 second without issuing a full-document network reload.
6. IF What_Data contains zero valid entries, THEN THE Home_Page SHALL display a message indicating that no disease data is available instead of a top finding.
7. THE Home_Page SHALL describe the top finding as a discrepancy between measured burden and observed research activity and SHALL NOT use any Forbidden_Terms.

### Requirement 5: WHAT View Chart

**User Story:** As a researcher, I want to see each disease's distinct recruiting MA studies per 100,000 affected adults as a range, so that I can identify where observed research activity is low relative to measured burden.

#### Acceptance Criteria

1. WHEN the What_View finishes loading What_Data, THE What_View SHALL display a Dot_Whisker_Chart in which each Disease is drawn with a dot at its `mid` value and a whisker spanning from its `low` value to its `high` value.
2. THE What_View SHALL display all Diseases in What_Data in a single chart and SHALL NOT separate any Disease onto a distinct tab.
3. THE What_View SHALL sort the Diseases in ascending order of `mid` value, with ties broken by ascending case-insensitive `condition` label, so that the Disease with the lowest midpoint appears first.
4. THE What_View SHALL label the chart axis with the unit "distinct recruiting MA studies per 100,000 affected adults (18+)".
5. WHEN a user selects a Disease in the What_View, THE Dashboard SHALL navigate to the Investigate_Page for that Disease identified by its `measure_id`.
6. THE What_View SHALL display the Index_Value of each Disease as a low-high range and SHALL NOT display a single-number ranking without its range.
7. WHERE What_Data contains zero valid Diseases, THE What_View SHALL display a message that no diseases are available.
8. THE What_View SHALL render the Dot_Whisker_Chart using the Colorblind_Safe_Palette.
9. IF a What_Entry is missing any of `low`, `mid`, or `high`, or its values violate `low` <= `mid` <= `high`, THEN THE What_View SHALL omit that What_Entry from the Dot_Whisker_Chart and SHALL display the remaining valid Diseases.
10. IF a user selects a Disease whose `measure_id` has no Investigate_Entry, THEN THE Dashboard SHALL navigate to the Investigate_Page and display the Disease-not-found message defined in Requirement 7.
11. THE What_View SHALL NOT use any Forbidden_Terms when presenting or describing the ranking.

### Requirement 6: WHAT View Text Alternative

**User Story:** As a screen reader user, I want a text alternative to the WHAT view chart, so that I can read the same information without seeing the chart.

#### Acceptance Criteria

1. THE What_View SHALL provide a Text_Alternative that is a data table with one row per Disease and one column each for the `condition` label, the `low` value, the `mid` value, the `high` value, the `t` distinct study count, the `affected_adults` count, and the `prevalence_year` (the CDC PLACES data year shown next to the prevalence-derived affected-adults count).
2. THE Text_Alternative table SHALL present Diseases in the same top-to-bottom order as the Dot_Whisker_Chart, namely ascending `mid` value with ties broken by ascending case-insensitive `condition` label.
3. THE What_View SHALL associate the Text_Alternative with the Dot_Whisker_Chart in the accessibility tree so that assistive technology can reach the table from the chart.
4. WHERE What_Data contains zero valid Diseases, THE Text_Alternative SHALL display its column headers with no data rows and SHALL display a text indication that no data is available.
5. IF a displayed Disease is missing a value for a Text_Alternative column, THEN THE Text_Alternative SHALL display an unavailable indication in that cell rather than an empty cell.

### Requirement 7: Investigate Page

**User Story:** As a researcher, I want an investigate page per disease showing the study breakdown and MA versus US counts with labeled explanations, so that I can reach a record-supported explanation and see what remains unknown.

#### Acceptance Criteria

1. WHEN the Investigate_Page is opened for a Measure_Id, THE Investigate_Page SHALL display, for the Investigate_Entry with that `measure_id`, the breakdown of studies by overall status, by study type, by intervention type, and by phase, using the `label` and `count` pairs in the corresponding arrays.
2. THE Investigate_Page SHALL display the `ma_studies` count labeled as a Massachusetts count. IF `us_studies` is `null`, THEN THE Investigate_Page SHALL display the text "National comparison not included in this version" in place of a United States count; OTHERWISE it SHALL display the `us_studies` count labeled as a United States count.
3. THE Investigate_Page SHALL display each finding in the `findings` array together with its Evidence_Label, and SHALL NOT display any causal or uncertain explanatory statement that is not accompanied by one of the two Evidence_Label values.
4. THE Investigate_Page SHALL display a link to the Evidence_Page for the same Disease identified by its `measure_id`.
5. THE Investigate_Page SHALL present its explanatory text at a Flesch-Kincaid grade level no higher than United States grade 8 and SHALL define the terms "interventional" and "prevalence" with a defining phrase of at most 20 words at the first place each term appears.
6. IF no Investigate_Entry has the requested `measure_id`, THEN THE Investigate_Page SHALL display a message that the Disease was not found and SHALL offer a link back to the What_View.
7. THE Investigate_Page SHALL display no diagnosis, treatment, eligibility, or enrollment recommendation text, and SHALL NOT use any Forbidden_Terms.
8. THE Investigate_Page SHALL display, next to any Drug intervention count, the caption "Drug means the study lists a drug intervention; it may be an existing drug, comparator or placebo."

### Requirement 8: Evidence Page

**User Story:** As a researcher, I want an evidence page per disease listing the contributing NCT IDs, the filters, the mapping choices, and the missing-data notes, so that I can trace every number to its records.

#### Acceptance Criteria

1. WHEN the Evidence_Page is opened for a Measure_Id, THE Evidence_Page SHALL display, for the Evidence_Entry with that `measure_id`, each study in the `ncts` array as a table row with columns for the `nct_id`, `title`, `status`, `phases`, and `intervention_names`, where the `nct_id` is a link whose destination is that study's `url`, opening in a separate browser context so the Evidence_Page stays open. WHERE a study omits an optional detail (`title`, `status`, `phases`, or `intervention_names`), THE Evidence_Page SHALL display "unknown" for that cell rather than a blank cell.
2. THE Evidence_Page SHALL display the applied `filters`, the `mapping_choices`, and the `missing_data_notes` for that Disease.
3. THE Evidence_Page SHALL display the Data_As_Of value from Sources_Data labeled "Data as of".
4. IF the `ncts` array for that Disease is empty, THEN THE Evidence_Page SHALL display a message stating that no contributing studies are available and SHALL display no broken link.
5. IF no Evidence_Entry has the requested `measure_id`, THEN THE Evidence_Page SHALL display a message that the Disease was not found and SHALL offer a link back to the What_View.
6. THE Evidence_Page SHALL display no diagnosis, treatment, eligibility, or enrollment recommendation text, and SHALL NOT use any Forbidden_Terms.

### Requirement 9: WHERE View Map

**User Story:** As a researcher, I want a county map of distance to the nearest verified recruiting site for a disease, so that I can see where patients are far from a trial site.

> **Status in this version: HIDDEN.** The Where_View is not routed and carries no navigation link, and `where.json` / `ma_counties.geojson` are not shipped or fetched, because county shapes would require a data source outside clinicaltrials.gov / data.cdc.gov. The `Where` page and `CountyMap` component code is retained (unused) so the view can be reinstated without a rebuild. A direct request to `/where` falls through to the NotFound page. The acceptance criteria below (and Requirement 10) describe the behavior that MUST hold WHEN the view is reinstated.

#### Acceptance Criteria (apply only when the Where_View is reinstated)

1. THE Where_View SHALL display a County_Map of the 14 Massachusetts counties, shading each county by the `miles_to_nearest` value of the Where_Entry for the selected Disease and that county's `county_fips`.
2. THE Where_View SHALL provide a control that selects the Disease for which distances are shown, and SHALL update the County_Map when the selected Disease changes.
3. IF a Where_Entry for the selected Disease and a county is in the Unknown_Distance state, THEN THE Where_View SHALL mark that county as "unknown" on the County_Map and SHALL NOT shade it as zero miles and SHALL NOT leave it blank.
4. IF Where_Data contains no entry for the selected Disease and a county, THEN THE Where_View SHALL mark that county as "unknown" rather than shading it as zero miles.
5. THE Where_View SHALL render the County_Map using the Colorblind_Safe_Palette.
6. WHERE Where_Data contains zero entries, THE Where_View SHALL display a message that no distance data is available.
7. THE Where_View SHALL label the distances as miles to the nearest verified recruiting site and SHALL NOT use any Forbidden_Terms.

### Requirement 10: WHERE View Text Alternative

**User Story:** As a screen reader user, I want a text alternative to the county map, so that I can read the distance data without seeing the map.

> **Status in this version: HIDDEN** (see Requirement 9). The criteria below apply only when the Where_View is reinstated.

#### Acceptance Criteria (apply only when the Where_View is reinstated)

1. THE Where_View SHALL provide a Text_Alternative that is a data table listing, for the selected Disease, each county by its `county` label with its distance to the nearest verified recruiting site.
2. IF a county is in the Unknown_Distance state for the selected Disease, THEN THE Text_Alternative SHALL display "unknown" for that county's distance rather than a number or a blank cell.
3. THE Where_View SHALL associate the Text_Alternative with the County_Map so that assistive technology can reach the table from the map.
4. WHEN the selected Disease changes, THE Where_View SHALL update the Text_Alternative to list the distances for the newly selected Disease.

### Requirement 11: Method and Sources Page

**User Story:** As a researcher, I want a method and sources page, so that I can trust and cite the numbers.

#### Acceptance Criteria

1. THE Method_Page SHALL display the formula used to compute the Index_Value as `[T / (N * p_high), T / (N * p_low)] * 100,000`, where `T` is the distinct recruiting Massachusetts study count, `N` is the adult (18+) population denominator, and `p_low` and `p_high` are the CDC PLACES crude-prevalence confidence limits.
2. THE Method_Page SHALL display the crosswalk and filters used to attribute studies to each Disease.
3. THE Method_Page SHALL display each Source_Entry from Sources_Data as a named link to its `url`, together with that source's `fetched` date.
4. THE Method_Page SHALL display the limit that burden is measured as CDC PLACES crude prevalence for adults aged 18 and older and does not include disability-adjusted life years or any measure of severity.
5. THE Method_Page SHALL display the limit that Massachusetts trial activity does not represent all research relevant to Massachusetts patients.
6. THE Method_Page SHALL present its explanatory text at a reading level no higher than United States grade 8 and SHALL NOT use any Forbidden_Terms.

### Requirement 12: How We Built It With Kiro Page

**User Story:** As a judge or visitor, I want a page describing how the project was built with Kiro, so that I can see the development process and artifacts.

#### Acceptance Criteria

1. THE Build_Page SHALL be titled "How we built it with Kiro".
2. THE Build_Page SHALL display links, using full GitHub blob URLs, to the `.kiro/` specification and steering files and to `KIRO_LOG.md`.
3. THE Build_Page SHALL display a short description of how the Dashboard and pipeline were built using Kiro features.

### Requirement 13: Footer on Every Page

**User Story:** As a data steward, I want a consistent footer on every page, so that the site is never presented without its disclaimer, sources, and data date.

#### Acceptance Criteria

1. THE Dashboard SHALL display the Footer on the Home_Page, the What_View, the Investigate_Page, the Evidence_Page, the Method_Page, the Build_Page, and the NotFound page (the Where_View is hidden in this version — see Requirement 9).
2. THE Footer SHALL display the Disclaimer_Text exactly as "Not medical advice. Index, not prediction.".
3. THE Footer SHALL display a named link for each Source_Entry in Sources_Data to that source's `url`.
4. THE Footer SHALL display the Data_As_Of value labeled "Data as of".
5. IF Sources_Data cannot be loaded, THEN THE Footer SHALL still display the Disclaimer_Text and SHALL display a message that source information is unavailable in place of the source links and the Data_As_Of value.

### Requirement 14: Navigation

**User Story:** As a researcher, I want to move between pages quickly, so that I can reach a record-supported explanation in under a minute.

#### Acceptance Criteria

1. THE Dashboard SHALL provide navigation controls that reach the Home_Page, the What_View, the Method_Page, and the Build_Page from every page. THE Dashboard SHALL NOT provide a navigation control to the Where_View, which is hidden in this version (see Requirement 9).
2. WHEN a user activates a navigation control, THE Dashboard SHALL render the target page without a full page reload from the network.
3. WHEN a user navigates directly to the URL of any Dashboard page, THE Dashboard SHALL render that page.
4. THE Dashboard SHALL indicate which page is currently active in the navigation controls.

### Requirement 15: Accessibility

**User Story:** As a user with a disability, I want the site to meet accessibility standards, so that I can use it with a keyboard, a screen reader, or low vision.

#### Acceptance Criteria

1. THE Dashboard SHALL present all text and meaningful non-text content with a contrast ratio that meets WCAG 2.1 level AA.
2. THE Dashboard SHALL convey information using the Colorblind_Safe_Palette and SHALL NOT use color as the only means of conveying information.
3. THE Dashboard SHALL make every interactive control, link, tab, and Disease selector operable using only a keyboard.
4. WHILE an interactive control has keyboard focus, THE Dashboard SHALL display a visible focus indicator on that control.
5. THE Dashboard SHALL provide a Text_Alternative for the Dot_Whisker_Chart and for the County_Map.
6. THE Dashboard SHALL render every page and all content without horizontal scrolling at Mobile_Width.
7. WHEN a user navigates between pages, THE Dashboard SHALL move keyboard focus to a position from which the new page's main content is reachable.
8. THE Dashboard SHALL provide a programmatic label for every interactive control, image, and chart.

### Requirement 16: Performance on a Phone

**User Story:** As a researcher using a phone, I want the site to be responsive and quick to read, so that I can pick a disease, see burden versus activity, and reach a record-supported explanation plus what remains unknown in under one minute.

#### Acceptance Criteria

1. WHEN the What_View finishes loading What_Data, THE What_View SHALL display the Diseases sorted so that the three Diseases with the lowest `mid` value appear within the first screen of the chart or its Text_Alternative at Mobile_Width without scrolling past other Diseases.
2. THE Dashboard SHALL render all interactive content at Mobile_Width with touch targets operable by a single tap.
3. THE Dashboard SHALL load each JSON data file at most once per page view and SHALL reuse the loaded data for charts and their Text_Alternatives on the same page.

### Requirement 17: Forbidden Language and Framing

**User Story:** As a data steward, I want the site to never make neglect, underfunding, or unmet-need claims, so that the Research Gap Index stays a descriptive index and never implies medical or commercial judgment.

#### Acceptance Criteria

1. THE Dashboard SHALL NOT display, on any page, the word "neglected", the word "underfunded", or any statement that a Disease "needs more trials".
2. THE Dashboard SHALL NOT display any statement implying an optimal or correct ratio of burden to trials.
3. THE Dashboard SHALL NOT display any statement claiming unmet therapeutic need for a Disease.
4. THE Dashboard SHALL NOT display any statement inferring the motives of a pharmaceutical or biotechnology company.
5. THE Dashboard SHALL describe its output as a descriptive discrepancy between measured burden and observed research activity, as an index and not a prediction or recommendation.
6. THE Dashboard SHALL NOT display diagnosis, treatment, eligibility, or enrollment recommendation text on any page.

### Requirement 18: Real Sample Evidence Records and Readable Code Labels

**User Story:** As a data steward, I want the sample `evidence.json` to contain only real ClinicalTrials.gov records copied verbatim from the pipeline output and the Evidence page to show readable labels for ClinicalTrials.gov codes, so that the site never presents an invented study and a reader never has to decode raw API codes.

#### Acceptance Criteria

1. Every NCT entry in the sample `evidence.json` SHALL be copied verbatim from a row of `pipeline/processed/studies.csv`: its `nct_id`, `title` (the row's `briefTitle`), `status` (the row's `overallStatus`), `study_type` (the row's `studyType`), `phases`, `intervention_types`, and `intervention_names` SHALL equal the corresponding values of that row, and its `url` SHALL equal that row's `source_url`.
2. THE project SHALL NOT invent, paraphrase, edit, or fabricate any NCT identifier, study title, status, study type, phase, intervention type, or intervention name in the sample `evidence.json`; a value that is not present verbatim in `pipeline/processed/studies.csv` SHALL NOT appear.
3. Each multi-valued field copied from `pipeline/processed/studies.csv` (`phases`, `interventionTypes`, `interventionNames`) SHALL be split into a JSON array using the CSV's stored multi-value representation, so that each array element is an individual value and no element contains the delimiter or array-encoding characters.
4. For each `measure_id` in the sample `evidence.json`, THE project SHALL select up to three studies from `pipeline/processed/studies.csv`, each of which has at least one Massachusetts site in `pipeline/processed/sites.csv` (unless `studies.csv` is confirmed to already contain only Massachusetts-site studies, in which case that confirmation and how it was checked SHALL be recorded in the implementation notes), matching on exact list-item equality against that disease's MeSH heading (Asthma for CASTHMA; Depressive Disorder for DEPRESSION; Hypertension for BPHIGH; Diabetes Mellitus, Type 2 for DIABETES; Hypercholesterolemia for HIGHCHOL): a study qualifies when one of its `meshTerms` list items equals the heading exactly, and only when fewer than three studies qualify on `meshTerms` SHALL the project additionally admit studies one of whose `ancestorTerms` list items equals the heading exactly. A substring or prefix match SHALL NOT qualify a study; for BPHIGH in particular, a term such as "Hypertension, Pulmonary" or "Hypertension, Pregnancy-Induced" SHALL NOT be treated as matching "Hypertension". Among qualifying studies THE project SHALL prefer those whose `overallStatus` is RECRUITING, and the `mapping_choices` of that entry SHALL describe this exact-match MeSH-heading selection rule.
5. Each entry of the sample `evidence.json` whose studies were selected under criterion 4 SHALL include, in its `missing_data_notes`, the note "Sample: hand-picked from the 2026-10-24 fetch; replaced by the scoring export." IF a disease has zero qualifying studies under criterion 4, THEN its `ncts` array SHALL be left empty (the Evidence_Page already shows "No contributing studies are available" for an empty `ncts`), no study SHALL be invented or substituted, and its `missing_data_notes` SHALL include a line stating that no qualifying study was found in the fetch.
6. THE Evidence_Page SHALL display a readable label in place of each known ClinicalTrials.gov code it shows for a study's status, study type, phases, and intervention types, mapping at least RECRUITING to "Recruiting", ACTIVE_NOT_RECRUITING to "Active, not recruiting", PHASE2 to "Phase 2", NA to "Not applicable", INTERVENTIONAL to "Interventional", and DRUG to "Drug".
7. IF a status, study-type, phase, or intervention-type code shown on the Evidence_Page is not a known ClinicalTrials.gov code, THEN THE Evidence_Page SHALL display that code unchanged rather than blank or a placeholder.
8. THE code-to-label mapping used by the Evidence_Page SHALL be a pure function of the code string that returns a non-empty string for every input and returns its input unchanged for any unknown code.
