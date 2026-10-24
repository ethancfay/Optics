# Requirements Document

## Introduction

The Dashboard is the public website of the Research Gap Index. It is a static Vite + React single-page application in `web/`, deployed on Vercel with the root directory set to `web/`. The Dashboard reads only precomputed JSON files from `web/public/data/` and sends no requests to any backend, database, API key service, or server-side function. The site has no backend and no AI-generated text.

The audience is Massachusetts patient advocacy organizations. The success criterion is that an advocate can name three under-served conditions in under one minute on a phone. To that end the Dashboard presents, per condition, the number of recruiting Massachusetts trial sites per 100,000 affected adults (18+) as a low-high range, sorted so the most under-served conditions are easiest to find.

The Dashboard never diagnoses, recommends, predicts, or implies eligibility. It is an index that compares trial opportunity with how common a condition is, not how severe it is. Every page carries a footer disclaimer and source links, every number shown comes from the JSON data files, and every chart has a text alternative for screen readers.

This spec also defines sample placeholder JSON files so the site can be built and tested before the `research-gap-data-pipeline` spec produces the real data. The sample files follow the same schema as the real files.

### Open Items and Assumptions

1. The real `what.json`, `where.json`, and `sources.json` files are produced later by the `research-gap-data-pipeline` and `scoring-export` specs. This spec defines the JSON schema (the data contract) and sample placeholder files with that schema, clearly marked as sample data, so the Dashboard can be developed and tested independently.
2. The project steering files require a single lightweight chart library chosen in the dashboard spec; this document states the need for one library and its accessibility obligations but leaves the specific library name to design, since library selection is an implementation decision.
3. "Sorted by midpoint" (WHAT view) is interpreted as ascending order of the `mid` value, so the lowest midpoint (most under-served) condition appears first.
4. "Cancer shown on a separate tab" is interpreted as a WHAT view with two tabs: a non-cancer tab containing all conditions whose `measure_id` is not a cancer measure, and a cancer tab containing cancer conditions, so the large cancer values do not compress the scale of the non-cancer chart.
5. The `data_as_of` date in `sources.json` is the single date shown in the footer "Data as of" label on every page.
6. "Affected adults" always refers to adults aged 18 and older, consistent with CDC PLACES prevalence, and the Dashboard labels it as such wherever a count of affected adults is shown.
7. A condition is identified by its `measure_id`; the human-readable `condition` label is used for display. Routes and links use the `measure_id` to select a condition so that display labels can change without breaking links.

## Glossary

- **Dashboard**: The static Vite + React single-page web application in `web/` described by this document.
- **Data_Directory**: The directory `web/public/data/`, the only source of runtime data for the Dashboard.
- **What_Data**: The parsed contents of `web/public/data/what.json`.
- **Where_Data**: The parsed contents of `web/public/data/where.json`.
- **Sources_Data**: The parsed contents of `web/public/data/sources.json`.
- **County_Boundaries**: The parsed contents of `web/public/data/ma_counties.geojson`, the 14 Massachusetts county shapes from U.S. Census cartographic boundary files, simplified for web use.
- **What_Entry**: One element of the What_Data array, describing one condition's index value.
- **Where_Entry**: One element of the Where_Data array, describing one county and condition pair.
- **Source_Entry**: One element of the sources array within Sources_Data, describing one external data source.
- **Condition**: A health condition identified by its `measure_id` and displayed by its `condition` label.
- **Measure_Id**: The stable identifier of a Condition, used in routes and links.
- **Index_Value**: The number of recruiting Massachusetts trial sites per 100,000 affected adults for a Condition, expressed as a low-high range with values `low`, `high`, and `mid`.
- **Cancer_Condition**: A Condition whose `measure_id` is in the set of cancer measures defined in design.
- **Home_Page**: The Dashboard page at the root route showing the problem statement, the top finding, and a link to the WHAT view.
- **What_View**: The Dashboard page showing the per-condition Index_Value chart with a non-cancer tab and a cancer tab.
- **Condition_Detail_Page**: The Dashboard page showing one Condition's study count, affected adults, ClinicalTrials.gov link, and caveat.
- **Where_View**: The Dashboard page showing a Massachusetts county map of miles to the nearest recruiting site for a selected Condition.
- **Method_Page**: The Dashboard page showing the formula, sources with dates, and limits.
- **Build_Page**: The Dashboard page titled "How we built it with Kiro" linking to `.kiro/` files and `KIRO_LOG.md`.
- **Dot_Whisker_Chart**: A chart that draws, per Condition, a dot at the `mid` value and a whisker spanning from `low` to `high`.
- **County_Map**: The Massachusetts county map shown in the Where_View.
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
2. THE Dashboard SHALL read all runtime data only from `what.json`, `where.json`, `sources.json`, and `ma_counties.geojson` served from the same origin as the Dashboard in the Data_Directory, and SHALL issue zero network requests to any other origin at runtime. Fonts, map boundaries, and chart code SHALL be bundled with the site. Outbound links that the user clicks (e.g. to ClinicalTrials.gov or a data source) are navigation, not runtime requests, and are allowed.
3. THE Dashboard SHALL run without any backend server, database server, server-side function, or API key.
4. WHERE the Dashboard is deployed on Vercel, THE Dashboard SHALL be configured with the project root directory set to `web`.
5. THE Dashboard SHALL display no text that is generated by an artificial intelligence model at runtime.
6. THE Dashboard SHALL display no third-party logo or brand asset.
7. IF any of `what.json`, `where.json`, `sources.json`, or `ma_counties.geojson` fails to load or cannot be parsed at runtime, THEN THE Dashboard SHALL display a visible error message indicating which data file could not be loaded and SHALL not display partial or stale data for the failed file.

### Requirement 2: Data Contract and Sample Files

**User Story:** As a dashboard developer, I want a defined JSON schema and sample data files, so that I can build and test the site before the pipeline produces real data.

#### Acceptance Criteria

1. THE Dashboard spec SHALL define `what.json` as a JSON array in which each What_Entry contains the fields `condition` (non-empty string), `measure_id` (non-empty string), `low` (number >= 0), `high` (number >= 0), `mid` (number >= 0), `studies` (non-negative integer), `sites` (non-negative integer), `affected_adults` (non-negative integer), and `ctgov_url` (string beginning with `https://`), with `low` <= `mid` <= `high`.
2. THE Dashboard spec SHALL define `where.json` as a JSON array in which each Where_Entry contains the fields `county_fips` (non-empty string), `county` (non-empty string), `condition` (non-empty string), `miles_to_nearest` (number >= 0), and `adults_over_30mi` (non-negative integer).
3. THE Dashboard spec SHALL define `sources.json` as a JSON object containing a `sources` array in which each Source_Entry contains the fields `name` (non-empty string), `url` (string beginning with `https://`), and `fetched` (ISO 8601 date in `YYYY-MM-DD` form), a top-level `data_as_of` field (ISO 8601 date in `YYYY-MM-DD` form), and an optional top-level `is_sample` field (boolean) that, WHEN present and true, indicates the accompanying data files are sample data.
4. THE Dashboard SHALL include sample `what.json`, `where.json`, and `sources.json` files in the Data_Directory in which every required field is present, each value is of the type and within the bounds defined in criteria 1 through 3, and each file parses as valid JSON.
5. WHILE the Dashboard is serving data loaded from the sample files rather than real pipeline output, THE Dashboard SHALL display a text label, reachable within the first screen at Mobile_Width without scrolling, stating that the data shown is sample data.
6. THE sample `what.json` SHALL include at least one Cancer_Condition entry and at least three non-cancer Condition entries, each with a distinct `measure_id`, so that both WHAT view tabs can be exercised.
7. THE sample `where.json` SHALL include, for one single Condition, exactly one Where_Entry for each of the 14 distinct Massachusetts `county_fips` values, so that the full County_Map can be exercised.
8. THE Dashboard spec SHALL define `ma_counties.geojson` as a GeoJSON FeatureCollection of exactly 14 Features, one per Massachusetts county, each with a `county_fips` property (5-character string) that matches the `county_fips` values used in `where.json`, and THE Data_Directory SHALL include this file at no more than 300 KB.

### Requirement 3: Data Loading and Error Handling

**User Story:** As an advocate, I want the site to show clear status when data is loading or unavailable, so that I am never shown blank or misleading content.

#### Acceptance Criteria

1. WHEN a Dashboard page that requires What_Data, Where_Data, or Sources_Data is opened, THE Dashboard SHALL load the required JSON file from the Data_Directory before rendering the page's data content.
2. WHILE a required JSON file is loading and fewer than 10 seconds have elapsed since the load began, THE Dashboard SHALL display a loading indicator in place of the data content.
3. IF a required JSON file cannot be retrieved within 10 seconds of the load beginning, cannot be retrieved due to a network or missing-file error, or cannot be parsed as the schema defined in Requirement 2, THEN THE Dashboard SHALL display an error message stating that the data is unavailable and SHALL display no partial or placeholder numeric values.
4. IF a What_Entry, Where_Entry, or Source_Entry is missing a field required by Requirement 2, THEN THE Dashboard SHALL omit that entry from charts, tables, and lists and SHALL display the remaining valid entries.
5. IF every What_Entry, Where_Entry, or Source_Entry for a required JSON file is omitted under criterion 4, THEN THE Dashboard SHALL display a message stating that no valid data is available and SHALL display no empty chart, table, or list.
6. THE Dashboard SHALL display only numeric values that are present in the loaded JSON data, and SHALL compute no new disease or trial numbers that are not derived solely from those values.

### Requirement 4: Home Page

**User Story:** As an advocate, I want a home page that states the problem and the top finding, so that I understand the site's purpose within seconds.

#### Acceptance Criteria

1. WHEN the Home_Page finishes loading, THE Home_Page SHALL display a one-sentence statement, between 1 and 200 characters, of the problem that the Research Gap Index addresses.
2. WHEN the Home_Page finishes loading AND What_Data contains at least one valid non-cancer entry, THE Home_Page SHALL display the top finding as the non-cancer Condition with the lowest `mid` value in What_Data, naming that Condition and its Index_Value as a low-high range.
3. IF two or more non-cancer Conditions share the lowest `mid` value, THEN THE Home_Page SHALL select as the top finding the Condition whose name sorts first in case-insensitive ascending alphabetical order.
4. THE Home_Page SHALL display a link, labeled with visible text, that navigates to the What_View.
5. WHEN a user activates the link to the What_View, THE Dashboard SHALL navigate to the What_View within 1 second without issuing a full-document network reload.
6. IF What_Data contains zero valid non-cancer entries, THEN THE Home_Page SHALL display a message indicating that no condition data is available instead of a top finding.

### Requirement 5: WHAT View Chart

**User Story:** As an advocate, I want to see each condition's recruiting trial sites per 100,000 affected adults as a range, so that I can identify under-served conditions quickly.

#### Acceptance Criteria

1. WHEN the What_View finishes loading What_Data, THE What_View SHALL display a Dot_Whisker_Chart in which each Condition is drawn with a dot at its `mid` value and a whisker spanning from its `low` value to its `high` value.
2. THE What_View SHALL provide a non-cancer tab that shows all non-cancer Conditions and a cancer tab that shows all Cancer_Condition entries, with the non-cancer tab selected by default.
3. THE What_View SHALL sort the Conditions within the active tab in ascending order of `mid` value, with ties broken by ascending case-insensitive `condition` label, so that the Condition with the lowest midpoint appears first.
4. THE What_View SHALL label the chart axis with the unit "recruiting MA trial sites per 100,000 affected adults (18+)".
5. WHEN a user selects a Condition in the What_View, THE Dashboard SHALL navigate to the Condition_Detail_Page for that Condition identified by its `measure_id`.
6. THE What_View SHALL display the Index_Value of each Condition as a low-high range and SHALL NOT display a single-number ranking without its range.
7. WHERE the active tab contains zero Conditions, THE What_View SHALL display a message that no conditions are available in that tab.
8. THE What_View SHALL render the Dot_Whisker_Chart using the Colorblind_Safe_Palette.
9. IF a What_Entry is missing any of `low`, `mid`, or `high`, or its values violate `low` <= `mid` <= `high`, THEN THE What_View SHALL omit that What_Entry from the Dot_Whisker_Chart and SHALL display the remaining valid Conditions.
10. IF a user selects a Condition whose `measure_id` has no What_Entry, THEN THE Dashboard SHALL navigate to the Condition_Detail_Page and display the Condition-not-found message defined in Requirement 7.

### Requirement 6: WHAT View Text Alternative

**User Story:** As a screen reader user, I want a text alternative to the WHAT view chart, so that I can read the same information without seeing the chart.

#### Acceptance Criteria

1. THE What_View SHALL provide a Text_Alternative that is a data table with one row per Condition in the active tab and one column each for the `condition` label, the `low` value, the `mid` value, the `high` value, the `studies` count, and the `affected_adults` count.
2. THE Text_Alternative table SHALL present Conditions in the same top-to-bottom order as the Dot_Whisker_Chart, namely ascending `mid` value with ties broken by ascending case-insensitive `condition` label.
3. THE What_View SHALL associate the Text_Alternative with the Dot_Whisker_Chart in the accessibility tree so that assistive technology can reach the table from the chart.
4. WHEN the active tab changes between the non-cancer tab and the cancer tab, THE What_View SHALL update the Text_Alternative within 500 milliseconds to list exactly the Conditions of the newly active tab.
5. WHERE the active tab contains zero Conditions, THE Text_Alternative SHALL display its column headers with no data rows and SHALL display a text indication that no data is available.
6. IF a displayed Condition is missing a value for a Text_Alternative column, THEN THE Text_Alternative SHALL display an unavailable indication in that cell rather than an empty cell.

### Requirement 7: Condition Detail Page

**User Story:** As an advocate, I want a detail page per condition with its counts, a trial search link, and a caveat, so that I can take the finding to a sponsor or hospital.

#### Acceptance Criteria

1. WHEN the Condition_Detail_Page is opened for a Measure_Id, THE Condition_Detail_Page SHALL display the `studies` count, the `sites` count, the `affected_adults` count labeled as adults aged 18 and older, and the Index_Value as a low-high range using the `low` and `high` values with the unit "recruiting MA trial sites per 100,000 affected adults (18+)", for the What_Entry with that `measure_id`.
2. THE Condition_Detail_Page SHALL display a link whose destination is the `ctgov_url` value of that What_Entry, labeled as a search on ClinicalTrials.gov, that opens in a separate browser context so the detail page stays open.
3. IF the `ctgov_url` value of that What_Entry is absent or empty, THEN THE Condition_Detail_Page SHALL display a message stating that the trial search link is unavailable and SHALL display no broken link.
4. THE Condition_Detail_Page SHALL display a plain-language caveat stating that the Index_Value compares trial opportunity with how common the Condition is, not how severe the Condition is.
5. THE Condition_Detail_Page SHALL present its explanatory text at a Flesch-Kincaid grade level no higher than United States grade 8 and SHALL define the terms "interventional" and "prevalence" with a defining phrase of at most 20 words at the first place each term appears.
6. IF no What_Entry has the requested `measure_id`, THEN THE Condition_Detail_Page SHALL display a message that the Condition was not found and SHALL offer a link back to the What_View.
7. THE Condition_Detail_Page SHALL display no diagnosis, treatment, eligibility, or enrollment recommendation text.

### Requirement 8: WHERE View Map

**User Story:** As an advocate, I want a county map of distance to the nearest recruiting site for a condition, so that I can show where patients must travel far for a trial.

#### Acceptance Criteria

1. THE Where_View SHALL display a County_Map of the 14 Massachusetts counties, shading each county by the `miles_to_nearest` value of the Where_Entry for the selected Condition and that county's `county_fips`.
2. THE Where_View SHALL provide a control that selects the Condition for which distances are shown, and SHALL update the County_Map when the selected Condition changes.
3. THE Where_View SHALL display, for the selected Condition, the number of affected adults living more than 30 miles from the nearest recruiting site as the sum of the `adults_over_30mi` values across all counties for that Condition.
4. THE Where_View SHALL render the County_Map using the Colorblind_Safe_Palette.
5. IF Where_Data contains no entry for the selected Condition and a county, THEN THE Where_View SHALL mark that county as having no data rather than shading it as zero miles.
6. WHERE Where_Data contains zero entries, THE Where_View SHALL display a message that no distance data is available.

### Requirement 9: WHERE View Text Alternative

**User Story:** As a screen reader user, I want a text alternative to the county map, so that I can read the distance data without seeing the map.

#### Acceptance Criteria

1. THE Where_View SHALL provide a Text_Alternative that is a data table listing, for the selected Condition, each county by its `county` label with its `miles_to_nearest` value and its `adults_over_30mi` value.
2. THE Where_View SHALL associate the Text_Alternative with the County_Map so that assistive technology can reach the table from the map.
3. WHEN the selected Condition changes, THE Where_View SHALL update the Text_Alternative to list the distances for the newly selected Condition.
4. THE Where_View SHALL display the total number of affected adults living more than 30 miles from the nearest recruiting site in both the County_Map region and the Text_Alternative.

### Requirement 10: Method and Sources Page

**User Story:** As an advocate, I want a method and sources page, so that I can trust and cite the numbers.

#### Acceptance Criteria

1. THE Method_Page SHALL display the formula used to compute the Index_Value as recruiting Massachusetts trial sites per 100,000 affected adults.
2. THE Method_Page SHALL display each Source_Entry from Sources_Data as a named link to its `url`, together with that source's `fetched` date.
3. THE Method_Page SHALL display the limit that the Index_Value compares how common a Condition is, not how severe the Condition is.
4. THE Method_Page SHALL display the limit that prevalence data covers only the conditions available in CDC PLACES and is for adults aged 18 and older.
5. THE Method_Page SHALL present its explanatory text at a reading level no higher than United States grade 8.

### Requirement 11: How We Built It With Kiro Page

**User Story:** As a judge or visitor, I want a page describing how the project was built with Kiro, so that I can see the development process and artifacts.

#### Acceptance Criteria

1. THE Build_Page SHALL be titled "How we built it with Kiro".
2. THE Build_Page SHALL display links to the `.kiro/` specification and steering files and to `KIRO_LOG.md`.
3. THE Build_Page SHALL display a short description of how the Dashboard and pipeline were built using Kiro features.

### Requirement 12: Footer on Every Page

**User Story:** As a data steward, I want a consistent footer on every page, so that the site is never presented without its disclaimer, sources, and data date.

#### Acceptance Criteria

1. THE Dashboard SHALL display the Footer on the Home_Page, the What_View, the Condition_Detail_Page, the Where_View, the Method_Page, and the Build_Page.
2. THE Footer SHALL display the Disclaimer_Text exactly as "Not medical advice. Index, not prediction.".
3. THE Footer SHALL display a named link for each Source_Entry in Sources_Data to that source's `url`.
4. THE Footer SHALL display the Data_As_Of value labeled "Data as of".
5. IF Sources_Data cannot be loaded, THEN THE Footer SHALL still display the Disclaimer_Text and SHALL display a message that source information is unavailable in place of the source links and the Data_As_Of value.

### Requirement 13: Navigation

**User Story:** As an advocate on a phone, I want to move between pages quickly, so that I can find what I need in under a minute.

#### Acceptance Criteria

1. THE Dashboard SHALL provide navigation controls that reach the Home_Page, the What_View, the Where_View, the Method_Page, and the Build_Page from every page.
2. WHEN a user activates a navigation control, THE Dashboard SHALL render the target page without a full page reload from the network.
3. WHEN a user navigates directly to the URL of any Dashboard page, THE Dashboard SHALL render that page.
4. THE Dashboard SHALL indicate which page is currently active in the navigation controls.

### Requirement 14: Accessibility

**User Story:** As a user with a disability, I want the site to meet accessibility standards, so that I can use it with a keyboard, a screen reader, or low vision.

#### Acceptance Criteria

1. THE Dashboard SHALL present all text and meaningful non-text content with a contrast ratio that meets WCAG 2.1 level AA.
2. THE Dashboard SHALL convey information using the Colorblind_Safe_Palette and SHALL NOT use color as the only means of conveying information.
3. THE Dashboard SHALL make every interactive control, link, tab, and Condition selector operable using only a keyboard.
4. WHILE an interactive control has keyboard focus, THE Dashboard SHALL display a visible focus indicator on that control.
5. THE Dashboard SHALL provide a Text_Alternative for the Dot_Whisker_Chart and for the County_Map.
6. THE Dashboard SHALL render every page and all content without horizontal scrolling at Mobile_Width.
7. WHEN a user navigates between pages, THE Dashboard SHALL move keyboard focus to a position from which the new page's main content is reachable.
8. THE Dashboard SHALL provide a programmatic label for every interactive control, image, and chart.

### Requirement 15: Performance on a Phone

**User Story:** As an advocate using a phone, I want the site to be responsive and quick to read, so that I can name three under-served conditions in under one minute.

#### Acceptance Criteria

1. WHEN the What_View finishes loading What_Data, THE What_View SHALL display the Conditions sorted so that the three most under-served non-cancer Conditions appear within the first screen of the chart or its Text_Alternative at Mobile_Width without scrolling past other Conditions.
2. THE Dashboard SHALL render all interactive content at Mobile_Width with touch targets operable by a single tap.
3. THE Dashboard SHALL load each JSON data file at most once per page view and SHALL reuse the loaded data for charts and their Text_Alternatives on the same page.
