# Requirements Document

## Introduction

The Research Gap Index data pipeline fetches clinical studies of all study types with an Allowed_Overall_Status near central Massachusetts from the ClinicalTrials.gov v2 API. It uses two queries: one for active statuses and one for recently updated `COMPLETED` studies. It also fetches Massachusetts county health prevalence data from the CDC PLACES 2025 county release. Filtering by study type and site status happens later, in scoring, not in this pipeline. The pipeline normalizes both sources into CSV files and a fetch log under `pipeline/processed/`. The pipeline runs on a local laptop with Python 3.11 or newer and has no backend service. Raw API responses are cached under `pipeline/raw/` so that reruns can work offline. The pipeline never reads, stores, or logs contact names, email addresses, or phone numbers.

### Open Items and Assumptions

1. ClinicalTrials.gov v2 study records include contact data in `protocolSection.contactsLocationsModule.centralContacts`, `protocolSection.contactsLocationsModule.overallOfficials`, `protocolSection.contactsLocationsModule.locations[].contacts`, and the investigator name fields of `protocolSection.sponsorCollaboratorsModule.responsibleParty`. Requirement 3 addresses this by restricting the fields requested from the API and by stripping any contact data before raw responses are written to disk.
2. "MA studies" in the sanity check (Requirement 11, criterion 1) is interpreted as the count of distinct rows in `studies.csv` whose `studyType` is `INTERVENTIONAL` and that have at least one row in `sites.csv` with site status `RECRUITING` and a state equal to "Massachusetts" or "MA" (compared in the same way as the Allowed_States filtering of Requirement 5, criterion 3).
3. "Retry up to 3 times" is interpreted as 1 initial attempt plus up to 3 retries (4 attempts total).
4. Sites lacking a geoPoint are kept in `sites.csv` with empty latitude and longitude values and a Location_Quality of `missing_geo`, and are listed in `fetch_log.json`.
5. Site state filtering compares against both full state names (as returned by ClinicalTrials.gov, for example "Massachusetts") and the two-letter abbreviations MA, RI, NH, CT, NY, VT.

## Glossary

- **Pipeline**: The Python 3.11-or-newer command-line program described by this document, run locally on a laptop.
- **CTGov_Fetcher**: The Pipeline component that requests study data from the ClinicalTrials.gov v2 API.
- **PLACES_Fetcher**: The Pipeline component that requests county data from the CDC PLACES Socrata API.
- **HTTP_Client**: The Pipeline component that performs HTTP requests and applies the retry policy for both fetchers.
- **Raw_Store**: The Pipeline component that writes raw API responses to, and reads them from, the `pipeline/raw/` directory.
- **Contact_Scrubber**: The Pipeline component that removes contact data from API responses before any other component uses or stores them.
- **Study_Transformer**: The Pipeline component that converts ClinicalTrials.gov study records into study rows and site rows.
- **PLACES_Transformer**: The Pipeline component that converts CDC PLACES records into county-measure rows.
- **CSV_Writer**: The Pipeline component that serializes rows to CSV files in `pipeline/processed/`.
- **CSV_Reader**: The Pipeline component (used by tests and downstream code) that parses CSV files written by the CSV_Writer back into rows.
- **PII_Guard**: The Pipeline component that checks every output value for Email_Pattern and Phone_Pattern matches before output files are written.
- **Sanity_Checker**: The Pipeline component that compares output counts against expected thresholds and emits warnings.
- **Fetch_Log_Writer**: The Pipeline component that writes `fetch_log.json`.
- **CTGov_Studies_URL**: `https://clinicaltrials.gov/api/v2/studies`.
- **CTGov_Query_Active (Q1)**: The query parameters `filter.geo=distance(42.3,-71.8,150mi)`, `filter.overallStatus=RECRUITING,NOT_YET_RECRUITING,ACTIVE_NOT_RECRUITING`, `pageSize=1000`, and `countTotal=true`, plus `pageToken` when following pagination. No study type filter is sent.
- **CTGov_Query_Completed (Q2)**: The query parameters `filter.geo=distance(42.3,-71.8,150mi)`, `filter.overallStatus=COMPLETED`, `filter.advanced=AREA[LastUpdatePostDate]RANGE[<Q2_Lower_Bound>,MAX]`, `pageSize=1000`, and `countTotal=true`, plus `pageToken` when following pagination. No study type filter is sent. The date filter only reduces download size. Retention is decided by Requirement 4, criterion 1.
- **Q2_Lower_Bound**: The Recent_Completed_Cutoff minus 1 day, written as `YYYY-MM-DD`.
- **CTGov_Queries**: Q1 and Q2. Q1 is always sent first, and Q2 is sent after Q1 has finished paging.
- **Allowed_Overall_Status**: One of the study `overallStatus` values `RECRUITING`, `NOT_YET_RECRUITING`, `ACTIVE_NOT_RECRUITING`, or `COMPLETED`.
- **Recent_Completed_Cutoff**: The UTC calendar date of the Fetch_Date minus 3 years (same month and day; February 29 maps to February 28). A `COMPLETED` study is recent if its `lastUpdatePostDate` is on or after this date.
- **Total_Count**: For each of the CTGov_Queries, the `totalCount` value returned in the first response page of that query, because `countTotal=true` was requested.
- **Source_URL**: `https://clinicaltrials.gov/study/<nctId>`, with `<nctId>` replaced by the study's `nctId`.
- **Location_Quality**: A Site_Row value that is `ok` when the site has a numeric geoPoint latitude and longitude within the ranges of Requirement 5, criterion 6; `missing_geo` when the geoPoint, its latitude, or its longitude is absent or non-numeric; and `out_of_range` when both are numeric but at least one is outside those ranges.
- **County_FIPS**: The PLACES `locationid` written as a string of exactly 5 decimal digits, left-padded with zeros when the source value has fewer than 5 digits, so that leading zeros are kept.
- **PLACES_Dataset**: The CDC PLACES county data 2025 release, data.cdc.gov dataset identifier `swc5-untb`.
- **Crude_Prevalence**: PLACES records whose data value type is crude prevalence (`datavaluetypeid` equal to `CrdPrv`).
- **Allowed_States**: Massachusetts (MA), Rhode Island (RI), New Hampshire (NH), Connecticut (CT), New York (NY), and Vermont (VT).
- **Contact_Data**: Any person name, email address, or phone number associated with a study contact, location contact, official, or responsible party, including the `centralContacts`, `overallOfficials`, and `locations[].contacts` structures and the `responsibleParty` investigator name fields (such as `investigatorFullName`) of a ClinicalTrials.gov record.
- **Email_Pattern**: A regular expression matching strings of the form `local-part@domain.tld`.
- **Phone_Pattern**: A regular expression matching North American phone numbers of 10 digits with optional country code `1`, optional parentheses around the area code, and separators of space, hyphen, or period (for example `617-555-0100`, `(617) 555-0100`, `+1 617.555.0100`).
- **Study_Row**: One row of `studies.csv`, representing one retained study.
- **Site_Row**: One row of `sites.csv`, representing one retained study-site pair.
- **PLACES_Row**: One row of `places_ma.csv`, representing one county and measure pair.
- **JSON_Array_Cell**: The encoding of a multi-valued field in one CSV cell as a JSON array of strings, written with no whitespace between tokens and with non-ASCII characters written as UTF-8 rather than `\u` escapes (for example `["PHASE2","PHASE3"]`). A list with zero elements is written as `[]`.
- **Offline_Mode**: A Pipeline run option in which all source data is read from the Raw_Store and no network requests are made.
- **Fetch_Date**: The UTC timestamp, in ISO 8601 format, at which a network fetch run started.

## Requirements

### Requirement 1: Fetch Studies from ClinicalTrials.gov

**User Story:** As a Research Gap Index analyst, I want all studies with an Allowed_Overall_Status within 150 miles of central Massachusetts fetched from ClinicalTrials.gov, so that the index reflects the complete current and recent trial activity in the region.

#### Acceptance Criteria

1. WHEN the Pipeline starts a run without Offline_Mode, THE CTGov_Fetcher SHALL send, for each of the CTGov_Queries in turn (Q1 first, then Q2), one first-page GET request through the HTTP_Client to the CTGov_Studies_URL with that query's parameters and the `fields` parameter of Requirement 3, without a `pageToken` parameter.
2. WHEN a ClinicalTrials.gov response contains a non-empty `nextPageToken` value, THE CTGov_Fetcher SHALL send the next GET request with query parameters identical to the first request of the same query plus `pageToken` set to that `nextPageToken` value.
3. WHEN a ClinicalTrials.gov response has no `nextPageToken` field, or has a `nextPageToken` value that is null or an empty string, THE CTGov_Fetcher SHALL stop requesting further pages of that query. Once both queries have stopped, it SHALL pass the study records to the Contact_Scrubber: the Q1 records first, then the Q2 records, each in page order. A response with an empty `studies` array is a valid page.
4. THE CTGov_Fetcher SHALL record, in the order the requests were sent, the full URL including query string of every ClinicalTrials.gov request sent during the run, for inclusion in `fetch_log.json`, with exactly one recorded URL per page requested.
5. IF a ClinicalTrials.gov response returns a `nextPageToken` value already used earlier in the same query, THEN THE CTGov_Fetcher SHALL stop the run with a non-zero exit code and an error message identifying the repeated token, and SHALL leave previously written files in `pipeline/processed/` unchanged.
6. IF a ClinicalTrials.gov response with an HTTP 2xx status has a body that is not valid JSON or lacks a `studies` array, THEN THE CTGov_Fetcher SHALL stop the run with a non-zero exit code and an error message containing the request URL and the page number, and SHALL leave previously written files in `pipeline/processed/` unchanged.
7. IF the CTGov_Fetcher has received 100 pages for one of the CTGov_Queries and that query's 100th response contains a non-empty `nextPageToken` value, THEN THE CTGov_Fetcher SHALL stop the run with a non-zero exit code and an error message stating the page limit of 100, and SHALL leave previously written files in `pipeline/processed/` unchanged.
8. WHEN the CTGov_Fetcher sends the first ClinicalTrials.gov request of a run, THE CTGov_Fetcher SHALL record the Fetch_Date as the UTC time at which that run started.
9. WHEN the CTGov_Fetcher receives the first response page of each of the CTGov_Queries, THE CTGov_Fetcher SHALL record that query's Total_Count for inclusion in `fetch_log.json`.
10. IF, for either of the CTGov_Queries, the first response page has no integer `totalCount`, or the number of study records received across all pages of that query differs from that query's Total_Count, THEN THE Pipeline SHALL stop the run with a non-zero exit code and an error message naming the query and stating the fetched count and the Total_Count, and SHALL leave previously written files in `pipeline/processed/` unchanged. This check applies in network runs and, using the raw pages, in Offline_Mode.
11. IF a ClinicalTrials.gov request returns HTTP status 400, THEN THE Pipeline SHALL stop the run with a non-zero exit code and an error message containing the request URL, the status 400, and the parameter name `filter.geo` (for a Q2 request, `filter.geo` and `filter.advanced`), and SHALL leave previously written files in `pipeline/processed/` unchanged.
12. IF, after all ClinicalTrials.gov pages of a run are received and scrubbed, no study record has a site whose state matches one of the Allowed_States as compared in Requirement 5, criterion 3, THEN THE Pipeline SHALL stop the run with a non-zero exit code and an error message stating that no study has a site in Allowed_States and naming the parameter `filter.geo`, and SHALL leave previously written files in `pipeline/processed/` unchanged.

### Requirement 2: Fetch Massachusetts County Data from CDC PLACES

**User Story:** As a Research Gap Index analyst, I want Massachusetts county crude prevalence data from CDC PLACES 2025, so that I can compare disease burden with trial availability.

#### Acceptance Criteria

1. WHEN the Pipeline runs without Offline_Mode, THE PLACES_Fetcher SHALL send GET requests to the PLACES_Dataset (dataset identifier `swc5-untb`) on data.cdc.gov, filtered so that only records with `stateabbr` equal to `MA` and `datavaluetypeid` equal to `CrdPrv` are returned.
2. THE PLACES_Fetcher SHALL request the fields `locationname`, `locationid`, `measureid`, `measure`, `data_value`, `low_confidence_limit`, `high_confidence_limit`, `totalpop18plus`, `geolocation`, and `year`, plus the fields `stateabbr` and `datavaluetypeid`, and SHALL request no other fields.
3. THE PLACES_Fetcher SHALL request each page with a page size of 1,000 records, an offset that starts at 0 and increases by 1,000 for each later page, and the same sort order by `locationname` then `measureid` on every page, so that pages do not overlap or skip records.
4. WHEN a PLACES page contains exactly 1,000 records, THE PLACES_Fetcher SHALL request the next page using the same filters, fields, and sort order with the offset increased by 1,000.
5. WHEN a PLACES page contains fewer than 1,000 records, including 0 records on a page after the first, THE PLACES_Fetcher SHALL stop requesting further pages and pass the records of all received pages to the PLACES_Transformer.
6. THE PLACES_Fetcher SHALL record the full URL, including query string, of every PLACES request sent during the run, in the order sent, for inclusion in `fetch_log.json`.
7. IF the first PLACES page contains 0 records, THEN THE PLACES_Fetcher SHALL stop the run with a non-zero exit code and an error message containing the request URL and stating that no PLACES records were returned, and SHALL leave any previously written files in `pipeline/processed/` unchanged.
8. IF a PLACES response body cannot be parsed as a list of records, THEN THE PLACES_Fetcher SHALL stop the run with a non-zero exit code and an error message containing the request URL and stating that the response format was invalid, and SHALL leave any previously written files in `pipeline/processed/` unchanged.
9. IF the PLACES_Fetcher has requested 100 pages in one run and the 100th page contains exactly 1,000 records, THEN THE PLACES_Fetcher SHALL stop the run with a non-zero exit code and an error message stating that the 100-page limit was reached, and SHALL leave any previously written files in `pipeline/processed/` unchanged.

### Requirement 3: Exclude Contact Data

**User Story:** As a data steward, I want the pipeline to never read, store, or log contact names, emails, or phone numbers, so that the project handles no personal contact information.

#### Acceptance Criteria

1. WHEN the CTGov_Fetcher builds a ClinicalTrials.gov request, THE CTGov_Fetcher SHALL set the API `fields` parameter to list only the fields needed by Requirements 4 and 5, and SHALL leave out the `centralContacts`, `overallOfficials`, `locations.contacts`, and `responsibleParty` investigator name fields from that list.
2. WHEN a ClinicalTrials.gov response page is received, THE Contact_Scrubber SHALL remove every `centralContacts`, `overallOfficials`, and `locations[].contacts` structure and every `responsibleParty` investigator name field from the page, at whatever nesting depth it appears, before the Raw_Store writes the page and before any other Pipeline component reads the page.
3. THE Pipeline SHALL limit the content of console log messages, error messages, and `fetch_log.json` entries to identifiers, counts, URLs, field names, and timestamps, and SHALL include no Contact_Data values and no excerpts of ClinicalTrials.gov response bodies.
4. WHEN the Contact_Scrubber finishes scrubbing a ClinicalTrials.gov response page, THE Contact_Scrubber SHALL record, for `fetch_log.json`, the number of removed structures for each of `centralContacts`, `overallOfficials`, `locations[].contacts`, and `responsibleParty` investigator name fields, recording zero for each type with no removals, and SHALL leave the removed values out of the record.
5. IF a ClinicalTrials.gov response page cannot be parsed as JSON or the Contact_Scrubber cannot finish scrubbing it, THEN THE Pipeline SHALL stop the run with a non-zero exit code, SHALL write no part of that page to the Raw_Store, SHALL leave existing files in `pipeline/processed/` unchanged, and SHALL report an error message giving the page number and the request URL without any response body content.
6. WHERE Offline_Mode is selected, WHEN a ClinicalTrials.gov raw file is read from the Raw_Store, THE Contact_Scrubber SHALL scrub the file content as described in criterion 2 and record removal counts as described in criterion 4 before any other Pipeline component reads the content.

### Requirement 4: Build Study Rows

**User Story:** As a Research Gap Index analyst, I want one row per study with its status, type, phase, volunteer, intervention, and condition data, so that I can classify studies by disease area and filter them during scoring.

#### Acceptance Criteria

1. THE Study_Transformer SHALL retain only studies whose `overallStatus` equals, exactly and case-sensitively, one of the Allowed_Overall_Status values, and SHALL retain a study whose `overallStatus` is `COMPLETED` only if its `lastUpdatePostDate` is a valid `YYYY-MM-DD` date on or after the Recent_Completed_Cutoff. THE Study_Transformer SHALL retain studies of every `studyType`, including an empty or absent `studyType`; filtering by study type happens in scoring, not in this pipeline.
2. THE Study_Transformer SHALL produce one Study_Row per retained study containing the fields `nctId`, `briefTitle`, `overallStatus`, `studyType`, `phases`, `healthyVolunteers`, `conditions`, intervention types from `protocolSection.armsInterventionsModule.interventions[].type`, intervention names from `protocolSection.armsInterventionsModule.interventions[].name`, MeSH terms from `derivedSection.conditionBrowseModule.meshes`, MeSH identifiers from `derivedSection.conditionBrowseModule.meshes`, MeSH terms from `derivedSection.conditionBrowseModule.ancestors`, MeSH identifiers from `derivedSection.conditionBrowseModule.ancestors`, `lastUpdatePostDate` from `protocolSection.statusModule.lastUpdatePostDateStruct.date`, and `source_url`, with each value copied unchanged from the source record except `source_url`, which SHALL equal the Source_URL for the study's `nctId`.
3. THE Study_Transformer SHALL retain only studies that have at least one Site_Row after the site rules of Requirement 5 are applied.
4. IF a retained study lacks `briefTitle`, `studyType`, `phases`, `healthyVolunteers`, `conditions`, `interventions`, `meshes`, `ancestors`, or `lastUpdatePostDate`, or has an empty list for any of these fields, THEN THE Study_Transformer SHALL write an empty value (for a multi-valued field, an empty list) for each affected field in the Study_Row and SHALL still produce the Study_Row.
5. IF two or more study records share the same `nctId`, THEN THE Study_Transformer SHALL produce exactly one Study_Row for that `nctId`, built from the first such record in API response order (Q1 pages, then Q2 pages, each in page order, then by position within the page), and SHALL discard the later records with that `nctId` together with their sites.
6. THE Study_Transformer SHALL produce Study_Rows whose `nctId` values are unique within `studies.csv`.
7. THE Study_Transformer SHALL represent `phases`, `conditions`, the intervention type and name lists, the MeSH term lists, and the MeSH identifier lists as multi-valued fields that keep the element order of the source record, so that the Nth intervention type and the Nth intervention name refer to the same intervention, and the Nth MeSH term and the Nth MeSH identifier from the same source list refer to the same MeSH entry. IF an intervention lacks a `type` or a `name`, THEN THE Study_Transformer SHALL write an empty string at that position so the two lists keep equal length.
8. THE Study_Transformer SHALL write `healthyVolunteers` as `true` or `false` when the source value is present, matching the source boolean value.
9. IF a study record has an absent or empty `nctId`, THEN THE Study_Transformer SHALL exclude that record and SHALL produce no Study_Row and no Site_Row for it.

### Requirement 5: Build Site Rows

**User Story:** As a Research Gap Index analyst, I want one row per study-site with location, status, and location quality, so that I can map where trials are available.

#### Acceptance Criteria

1. THE Study_Transformer SHALL produce one Site_Row for each site of a study retained under Requirement 4, criterion 1, that meets criterion 3, containing `nctId`, `facility`, `city`, `state`, `zip`, geoPoint latitude, geoPoint longitude, site status, and `location_quality`, with each text value written as returned by ClinicalTrials.gov after removing leading and trailing whitespace.
2. THE Study_Transformer SHALL keep every site regardless of site status, SHALL write the site status as returned by ClinicalTrials.gov after removing leading and trailing whitespace, and SHALL write an empty site status when the source value is missing or empty. Site status is separate from the study's `overallStatus`; filtering by site status happens in scoring, not in this pipeline.
3. THE Study_Transformer SHALL retain only sites whose state, after removing leading and trailing whitespace and ignoring letter case, equals the full name or the two-letter abbreviation of one of the Allowed_States, and SHALL exclude sites whose state is missing or empty.
4. IF a retained site lacks a geoPoint, or its geoPoint lacks a numeric latitude or a numeric longitude, THEN THE Study_Transformer SHALL write empty latitude and longitude values and a `location_quality` of `missing_geo` in the Site_Row and record the site's `nctId` and `facility` as missing a geoPoint for `fetch_log.json`.
5. THE Study_Transformer SHALL produce Site_Rows whose `nctId` equals the `nctId` of exactly one Study_Row.
6. THE Study_Transformer SHALL produce Site_Rows whose non-empty latitude is between -90 and 90 inclusive and whose non-empty longitude is between -180 and 180 inclusive.
7. IF a retained site's geoPoint latitude or longitude is outside the valid range of criterion 6, THEN THE Study_Transformer SHALL write empty latitude and longitude values and a `location_quality` of `out_of_range` in the Site_Row and record the site's `nctId` and `facility` as missing a geoPoint for `fetch_log.json`.
8. WHEN a retained site has a numeric geoPoint latitude and longitude within the valid range of criterion 6, THE Study_Transformer SHALL write a `location_quality` of `ok` in the Site_Row.
9. IF a retained site lacks a value for `facility`, `city`, or `zip`, THEN THE Study_Transformer SHALL write an empty value for that field in the Site_Row and SHALL keep the Site_Row.
10. IF two or more retained sites share the same `nctId`, `facility`, `city`, `state`, and `zip`, including sites that come from duplicate study records with the same `nctId`, THEN THE Study_Transformer SHALL produce exactly one Site_Row for that combination.
11. THE Study_Transformer SHALL record in `fetch_log.json` only those sites missing a geoPoint that are retained by criterion 3, with each site listed at most once.

### Requirement 6: Build PLACES Rows

**User Story:** As a Research Gap Index analyst, I want one row per Massachusetts county and measure, so that I can join prevalence data to trial locations by county.

#### Acceptance Criteria

1. THE PLACES_Transformer SHALL produce exactly one PLACES_Row for each distinct pair of County_FIPS and `measureid` among the retained PLACES records, containing `locationname`, `locationid` written as the County_FIPS, `measureid`, `measure` (the measure label), `data_value`, `low_confidence_limit`, `high_confidence_limit`, `totalpop18plus`, `geolocation` latitude, `geolocation` longitude, and `year`, with each numeric value written without rounding relative to the source record.
2. THE PLACES_Transformer SHALL retain only Crude_Prevalence records with `stateabbr` equal to `MA`, and SHALL exclude all other records before the duplicate check of criterion 3 is applied.
3. IF two or more retained PLACES records share the same County_FIPS and `measureid`, THEN THE PLACES_Transformer SHALL keep only the record with the highest numeric `year` (treating a missing or non-numeric `year` as older than any numeric year, and keeping the first in fetch order when more than one record has that year), SHALL record the County_FIPS, `measureid`, kept `year`, and number of discarded records for `fetch_log.json`, and SHALL continue the run.
4. IF a retained PLACES record has a `data_value`, `low_confidence_limit`, or `high_confidence_limit` that is missing, empty, non-numeric, or outside 0 to 100 inclusive, or has a `totalpop18plus` that is missing, empty, non-numeric, or less than 0, THEN THE PLACES_Transformer SHALL write an empty value for that field in the PLACES_Row and SHALL still write the PLACES_Row.
5. IF a retained PLACES record has a missing `geolocation`, a `geolocation` latitude outside -90 to 90 inclusive, or a `geolocation` longitude outside -180 to 180 inclusive, THEN THE PLACES_Transformer SHALL write empty latitude and longitude values in the PLACES_Row and SHALL still write the PLACES_Row.
6. IF a retained PLACES record has an empty or missing `locationname`, `locationid`, or `measureid`, or a `locationid` that is not 1 to 5 decimal digits and so cannot be written as a County_FIPS, THEN THE PLACES_Transformer SHALL stop the run with a non-zero exit code and an error message identifying the field and the record's `locationname` and `measureid` where present, and THE Pipeline SHALL NOT write `places_ma.csv` during that run.
7. IF zero PLACES records remain after the filtering of criterion 2, THEN THE PLACES_Transformer SHALL stop the run with a non-zero exit code and an error message indicating that no Massachusetts Crude_Prevalence records were found, and THE Pipeline SHALL NOT write `places_ma.csv` during that run.
8. THE PLACES_Transformer SHALL write every PLACES_Row `locationid` as a string of exactly 5 characters, keeping leading zeros, and SHALL never write it as a number.

### Requirement 7: Write CSV Outputs

**User Story:** As a downstream developer, I want consistent CSV files with stable columns, so that the index and visualizations can load them without custom parsing.

#### Acceptance Criteria

1. WHEN the transformers have produced all rows for a run, THE CSV_Writer SHALL write Study_Rows to `pipeline/processed/studies.csv`, Site_Rows to `pipeline/processed/sites.csv`, and PLACES_Rows to `pipeline/processed/places_ma.csv`, replacing any file of the same name from an earlier run.
2. THE CSV_Writer SHALL write each CSV file as UTF-8 without a byte order mark, with LF line endings, exactly one header row as the first line, and the columns in the order the fields are listed in Requirements 4, 5, and 6 for Study_Rows, Site_Rows, and PLACES_Rows respectively, so that the header row of each file is identical across runs.
3. THE CSV_Writer SHALL enclose a cell in double quotes, and double each double-quote character inside it, if and only if the cell value contains a comma, a double quote, a carriage return, or a line feed.
4. THE CSV_Writer SHALL write each multi-valued field as a JSON_Array_Cell in a single cell, preserving element order, and SHALL write `[]` for a multi-valued field whose list has zero elements. The CSV_Writer SHALL apply no custom delimiter or escape scheme; JSON string escaping and the CSV quoting of criterion 3 are the only escaping used.
5. THE CSV_Writer SHALL encode every element of a multi-valued field as a JSON string, so that elements containing `|`, `,`, `"`, `\`, `[`, `]`, line breaks, or non-ASCII characters are recovered exactly by the CSV_Reader.
6. WHEN the CSV_Reader parses a CSV file written by the CSV_Writer, THE CSV_Reader SHALL return one row per data line, with the same field names as the header row, decoding each multi-valued cell as a JSON array of strings and returning an empty list for a `[]` cell.
7. FOR ALL valid Study_Rows, Site_Rows, and PLACES_Rows, writing with the CSV_Writer then reading with the CSV_Reader SHALL produce rows with equal field names, equal scalar values, and equal multi-valued lists in the same order (round-trip property). A row is valid if every multi-valued list element is a string and every value is free of Contact_Data.
8. THE CSV_Writer SHALL sort Study_Rows by `nctId`, Site_Rows by `nctId` then `facility` then `zip`, and PLACES_Rows by `locationname` then `measureid` then `locationid`, each in ascending order by Unicode code point, so that identical inputs produce byte-identical files.
9. IF a row set to be written contains zero rows, THEN THE CSV_Writer SHALL write a file that contains only the header row.
10. IF the CSV_Writer cannot write any of the three CSV files, THEN THE Pipeline SHALL stop the run with a non-zero exit code and an error message naming the file that failed, and SHALL leave any existing file of that name from an earlier run unchanged.

### Requirement 8: Guard Outputs Against Contact Patterns

**User Story:** As a data steward, I want every output checked for email and phone patterns, so that contact information cannot leak into published files even if the source format changes.

#### Acceptance Criteria

1. WHEN the Study_Transformer and the PLACES_Transformer have produced all Study_Rows, Site_Rows, and PLACES_Rows for the run, THE PII_Guard SHALL check every field value of every Study_Row, Site_Row, and PLACES_Row against the Email_Pattern and the Phone_Pattern before the CSV_Writer writes any output file. The PII_Guard SHALL check each value in the exact string form the CSV_Writer will write, including multi-valued fields encoded as JSON_Array_Cells, SHALL also check each decoded element of every multi-valued field, and SHALL count a value as a match if any substring of the value matches either pattern.
2. IF one or more output values match the Email_Pattern or the Phone_Pattern, THEN THE PII_Guard SHALL stop the run with a non-zero exit code before the CSV_Writer writes `studies.csv`, `sites.csv`, or `places_ma.csv` and before the Fetch_Log_Writer writes `fetch_log.json`, and SHALL leave any previously written files in `pipeline/processed/` unchanged.
3. FOR ALL generated source records, including records with email addresses and phone numbers injected into any field, THE Pipeline SHALL produce one of exactly two outcomes (property): (a) the run stops with a non-zero exit code, and no file in `pipeline/processed/` is created or modified; or (b) the run completes, and no value in `studies.csv`, `sites.csv`, or `places_ma.csv` contains a substring matching the Email_Pattern or the Phone_Pattern.
4. IF one or more output values match the Email_Pattern or the Phone_Pattern, THEN THE PII_Guard SHALL print an error message that states the total match count and lists every match, not only the first. Each entry SHALL give the target file name, the row identifier, the field name, and which pattern matched (email or phone), and SHALL NOT include the matched value or any part of it. The row identifier is the `nctId` for a Study_Row, the `nctId` plus the 1-based row position in `sites.csv` for a Site_Row, and the `locationname` plus `measureid` for a PLACES_Row.
5. WHEN the PII_Guard finds no output value matching the Email_Pattern or the Phone_Pattern, THE PII_Guard SHALL let the CSV_Writer write `studies.csv`, `sites.csv`, and `places_ma.csv` without changing any row value.
6. FOR ALL generated ClinicalTrials.gov source records in which email addresses and phone numbers are injected only into Contact_Data structures (`centralContacts`, `overallOfficials`, `locations[].contacts`, and `responsibleParty` investigator name fields), THE Pipeline SHALL complete the run with a zero exit code, and no value in the output CSV files SHALL contain a substring matching the Email_Pattern or the Phone_Pattern (property).

### Requirement 9: Retry Failed Requests

**User Story:** As a pipeline operator, I want transient network failures retried and persistent failures reported clearly, so that runs either succeed or fail visibly.

#### Acceptance Criteria

1. IF a request attempt fails with a connection error, a timeout, an HTTP 429 status, or an HTTP 5xx status, THEN THE HTTP_Client SHALL retry the request up to 3 times, waiting 1 second before the first retry, 2 seconds before the second retry, and 4 seconds before the third retry, for a maximum of 4 attempts per request.
2. THE HTTP_Client SHALL count retries separately for each request, so that each paginated CTGov_Studies_URL request and each PLACES_Dataset request has its own limit of 4 attempts.
3. IF the 4th attempt of a request fails with a connection error, a timeout, an HTTP 429 status, or an HTTP 5xx status, THEN THE HTTP_Client SHALL make no further requests and SHALL stop the run with a non-zero exit code and an error message on standard error containing the request URL, the final HTTP status or error type, and the attempt count of 4.
4. IF a request attempt fails with an HTTP 4xx status other than 429, THEN THE HTTP_Client SHALL make no retry and no further requests, and SHALL stop the run with a non-zero exit code and an error message on standard error containing the request URL and the HTTP status.
5. THE HTTP_Client SHALL apply a timeout of 60 seconds to each request attempt, measured from the moment the request is sent until the complete response is received, and SHALL treat an attempt that exceeds 60 seconds as a timeout failure under criterion 1.
6. IF the Pipeline stops because of a request failure, THEN THE Pipeline SHALL leave every file that existed in `pipeline/processed/` before the run byte-for-byte unchanged and SHALL create no new files in `pipeline/processed/`.
7. WHEN a request attempt returns an HTTP 2xx status, THE HTTP_Client SHALL return the response to the requesting fetcher without further retries, and the Pipeline SHALL continue the run.

### Requirement 10: Store and Reuse Raw Responses

**User Story:** As a pipeline operator, I want raw API responses saved locally, so that I can rerun transformations offline and reproduce results.

#### Acceptance Criteria

1. WHEN a ClinicalTrials.gov response has passed the Contact_Scrubber or a PLACES response is received, THE Raw_Store SHALL write the response body to `pipeline/raw/` as one file per page, under a file name that identifies the source (ClinicalTrials.gov Q1, ClinicalTrials.gov Q2, or PLACES) and the 1-based page number within that source, before the next page is requested.
2. THE Pipeline SHALL include a `.gitignore` entry that excludes `pipeline/raw/` from version control.
3. WHERE Offline_Mode is selected, THE Pipeline SHALL read all ClinicalTrials.gov and PLACES source data from the Raw_Store and send zero network requests during the run.
4. IF Offline_Mode is selected and the Raw_Store does not hold a complete prior fetch, THEN THE Pipeline SHALL stop the run before writing any output file, exit with a non-zero exit code, and print an error message naming each source (ClinicalTrials.gov, PLACES, or both) whose raw files are missing or incomplete, where a complete prior fetch means a network run that wrote every page of both sources, ending with a page with no `nextPageToken` for each of the CTGov_Queries and a PLACES page with fewer records than the requested page size, plus the saved Fetch_Date and the saved list of request URLs of that run.
5. WHERE Offline_Mode is selected, THE Pipeline SHALL produce `studies.csv`, `sites.csv`, `places_ma.csv`, and `fetch_log.json` byte-identical to the files produced by the network run that wrote the raw files, with `fetch_log.json` reporting the Fetch_Date of that network run, and differing only in fields that record the current run's own start time or whether Offline_Mode was used.
6. THE Raw_Store SHALL write raw files that contain no `centralContacts`, `overallOfficials`, or `locations[].contacts` structures and no other Contact_Data.
7. WHEN a network run completes fetching both sources, THE Raw_Store SHALL save in `pipeline/raw/`, alongside the raw files it wrote, the Fetch_Date of that run and every request URL recorded by the CTGov_Fetcher and the PLACES_Fetcher during that run, grouped by source and in the order sent.
8. WHEN a network run starts writing raw files, THE Raw_Store SHALL ensure that no raw file from an earlier run remains in `pipeline/raw/` once the run completes, so that a later Offline_Mode run reads only pages from a single network run.
9. IF the Raw_Store fails to write a raw file, THEN THE Pipeline SHALL stop the run with a non-zero exit code, print an error message naming the file that could not be written, and treat the Raw_Store as lacking a complete prior fetch for any later Offline_Mode run.

### Requirement 11: Sanity Checks

**User Story:** As a Research Gap Index analyst, I want warnings when counts look implausible, so that I notice incomplete fetches or upstream data changes.

#### Acceptance Criteria

1. IF the number of distinct Study_Rows whose `studyType` equals `INTERVENTIONAL` and that have at least one Site_Row whose state equals "Massachusetts" or "MA" (the same state values used for Allowed_States filtering) and whose site status equals `RECRUITING` is less than 2,000, THEN THE Sanity_Checker SHALL print one warning to standard error stating the observed count and the threshold of 2,000. A count of exactly 2,000 or more SHALL NOT produce this warning.
2. IF the number of distinct `locationname` values across all PLACES_Rows is not equal to 14, including the case where there are zero PLACES_Rows, THEN THE Sanity_Checker SHALL print one warning to standard error stating the observed distinct county count and the expected count of 14.
3. WHEN the Sanity_Checker emits a warning, THE Fetch_Log_Writer SHALL record the full warning text as one entry in the warnings list of `fetch_log.json` for that run, with one entry per warning emitted.
4. WHEN the Sanity_Checker emits one or more warnings, THE Pipeline SHALL complete the run, write `studies.csv`, `sites.csv`, `places_ma.csv`, and `fetch_log.json`, and exit with status code 0.
5. WHEN the Study_Transformer and PLACES_Transformer have produced all rows for a run, THE Sanity_Checker SHALL evaluate criteria 1 and 2 against those rows before the Fetch_Log_Writer writes `fetch_log.json`. This applies both in network runs and in Offline_Mode.
6. IF neither the Massachusetts study check nor the county count check fails, THEN THE Sanity_Checker SHALL print no warning, and THE Fetch_Log_Writer SHALL record an empty warnings list in `fetch_log.json`.

### Requirement 12: Write Fetch Log

**User Story:** As a pipeline operator, I want a machine-readable log of each run, so that I can audit what was fetched and spot data quality gaps.

#### Acceptance Criteria

1. WHEN the CSV_Writer has finished writing `studies.csv`, `sites.csv`, and `places_ma.csv` for a run, THE Fetch_Log_Writer SHALL write `pipeline/processed/fetch_log.json` as a single valid JSON document that replaces any `fetch_log.json` written by a prior run.
2. THE Fetch_Log_Writer SHALL include in `fetch_log.json` a separate row count for each of `studies.csv`, `sites.csv`, and `places_ma.csv`, each identified by its file name.
3. THE Fetch_Log_Writer SHALL include in `fetch_log.json` the count of Site_Rows missing a geoPoint and the list of those sites, each identified by `nctId` and `facility` and giving its `location_quality`, where the count equals the number of list entries, and where a run with no such sites produces a count of 0 and an empty list.
4. THE Fetch_Log_Writer SHALL include in `fetch_log.json` the Fetch_Date of the network fetch that produced the raw data, which is the start time of the current run for a run without Offline_Mode and the Fetch_Date stored in the Raw_Store by the prior network run for a run in Offline_Mode.
5. THE Fetch_Log_Writer SHALL include in `fetch_log.json` every API URL recorded by the CTGov_Fetcher and the PLACES_Fetcher, grouped by source (ClinicalTrials.gov or CDC PLACES) and listed in the order the requests were sent, using the URLs saved in the Raw_Store by the prior network run (Requirement 10, criterion 7) for a run in Offline_Mode.
6. THE Fetch_Log_Writer SHALL include in `fetch_log.json` the list of sanity warnings emitted by the Sanity_Checker under Requirement 11 (an empty list when no warnings are emitted) and the run totals of the per-type removal counts recorded by the Contact_Scrubber under Requirement 3, criterion 4, with one count each for `centralContacts`, `overallOfficials`, `locations[].contacts`, and `responsibleParty` investigator name fields (0 for each type with no removals).
7. THE Fetch_Log_Writer SHALL write row counts in `fetch_log.json` equal to the number of data rows, excluding the header row, in the corresponding CSV file as written in the same run.
8. THE Fetch_Log_Writer SHALL include in `fetch_log.json` a run mode value indicating whether the run used Offline_Mode or network fetching.
9. IF the Pipeline stops with a non-zero exit code before all three output CSV files are written, THEN THE Fetch_Log_Writer SHALL leave any existing `pipeline/processed/fetch_log.json` unchanged.
10. IF writing `fetch_log.json` fails, THEN THE Pipeline SHALL stop the run with a non-zero exit code and an error message naming `fetch_log.json` and the failure reason.
11. THE Fetch_Log_Writer SHALL include in `fetch_log.json`, separately for each of the CTGov_Queries, the Total_Count recorded under Requirement 1, criterion 9, and the number of study records fetched by that query.
12. THE Fetch_Log_Writer SHALL include in `fetch_log.json` the list of duplicate PLACES County_FIPS and `measureid` pairs resolved under Requirement 6, criterion 3, each with the kept `year` and the number of discarded records (an empty list when there are none).

### Requirement 13: Property-Based Test Suite

**User Story:** As a developer, I want property-based tests with Hypothesis, so that privacy and integrity rules hold across varied inputs and not only on today's data.

#### Acceptance Criteria

1. THE Pipeline SHALL include a Hypothesis property test asserting the two-outcome property of Requirement 8, criterion 3, for generated study and PLACES records that include email addresses and phone numbers injected into Contact_Data structures and into any other string field: either the run stops with a non-zero exit code and no file in `pipeline/processed/` is created or modified, or the run completes and no value in `studies.csv`, `sites.csv`, or `places_ma.csv` contains a substring matching the Email_Pattern or the Phone_Pattern.
2. THE Pipeline SHALL include a Hypothesis property test asserting that every Site_Row `nctId` equals the `nctId` of a Study_Row, for generated study records that include studies with zero sites, studies with more than one site, and studies that the Study_Transformer excludes from `studies.csv`.
3. THE Pipeline SHALL include a Hypothesis property test asserting that every non-empty Site_Row latitude is between -90 and 90 inclusive and every non-empty Site_Row longitude is between -180 and 180 inclusive, for generated study records that include missing geoPoints, out-of-range geoPoints, and geoPoints exactly at the boundary values -90, 90, -180, and 180.
4. THE Pipeline SHALL include a Hypothesis property test asserting the CSV round-trip property of Requirement 7, criterion 7, for generated Study_Rows, Site_Rows, and PLACES_Rows whose values include empty strings, empty multi-valued lists, empty-string list elements, `|` characters, backslashes, square brackets, strings that look like JSON arrays, commas, double quotes, line breaks, and non-ASCII characters.
5. THE Pipeline SHALL run the property test suite using only recorded data from the Raw_Store or Hypothesis-generated data, with no network requests.
6. IF any test in the property test suite attempts a network request, THEN THE Pipeline SHALL fail that test and report the attempted request URL.
7. THE Pipeline SHALL run each Hypothesis property test with at least 100 generated examples.
8. IF a Hypothesis property test fails, THEN THE Pipeline SHALL report the name of the failed property and the shrunk falsifying example, and SHALL exit the test run with a non-zero exit code.
9. THE Pipeline SHALL include a Hypothesis property test asserting the property of Requirement 8, criterion 6, for generated ClinicalTrials.gov records in which email addresses and phone numbers are injected only into Contact_Data structures: the run completes with a zero exit code and no value in `studies.csv`, `sites.csv`, or `places_ma.csv` contains a substring matching the Email_Pattern or the Phone_Pattern.
10. THE Pipeline SHALL include a Hypothesis property test asserting that, for generated ClinicalTrials.gov response pages with Contact_Data placed at any nesting depth, the output of the Contact_Scrubber contains no `centralContacts`, `overallOfficials`, or `locations[].contacts` structure, no `responsibleParty` investigator name field (such as `investigatorFullName`), and none of the injected names, email addresses, or phone numbers anywhere in the scrubbed page, and that the recorded removal counts equal the number of structures injected for each type.
11. THE Pipeline SHALL include a Hypothesis property test asserting that every PLACES_Row `locationid` is a string of exactly 5 decimal digits that equals the source `locationid` left-padded with zeros, for generated PLACES records whose `locationid` values include numbers, strings with leading zeros, and values with fewer than 5 digits.
12. THE Pipeline SHALL include a Hypothesis property test asserting that `nctId` values are unique across all rows of `studies.csv`, for generated study records that include repeated `nctId` values within a page and across pages.

### Requirement 14: Runtime Environment

**User Story:** As a pipeline operator, I want the pipeline to run on my laptop without a server, so that I can produce the data with no hosting cost.

#### Acceptance Criteria

1. THE Pipeline SHALL run as a local command-line program, started by a single command from the repository root, on a Python interpreter of version 3.11 or newer.
2. IF the Pipeline is started on a Python interpreter whose version is lower than 3.11, THEN THE Pipeline SHALL stop before sending any network request or reading or writing any file, exit with a non-zero exit code, and print an error message stating the detected Python version and the minimum version 3.11. THE Pipeline SHALL NOT stop because the version is newer than 3.11.
3. THE Pipeline SHALL send network requests only to the clinicaltrials.gov and data.cdc.gov hosts, and SHALL run without starting, connecting to, or requiring any backend server, database server, or other cloud service.
4. WHERE Offline_Mode is selected, THE Pipeline SHALL complete a run with no network connection available.
5. THE Pipeline SHALL declare every third-party Python package it imports, each pinned to one exact version (for example `package==1.2.3`), in a single dependency file in the repository, such that installing only that file into a fresh Python 3.11-or-newer environment is sufficient to run the Pipeline.
6. WHEN the Pipeline completes a run in which all output files in `pipeline/processed/` have been written, THE Pipeline SHALL exit with code 0 and print to standard output the file name and data row count (excluding the header row) of each of `studies.csv`, `sites.csv`, and `places_ma.csv`.
7. WHEN the Pipeline completes a run in which the Sanity_Checker emitted one or more warnings, THE Pipeline SHALL still exit with code 0.
8. IF the Pipeline stops a run because of any error defined in these requirements, THEN THE Pipeline SHALL exit with a non-zero exit code, print the error message to standard error, and not print the output row count summary.
