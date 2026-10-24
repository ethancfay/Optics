# Probe Results (Task 1)

Probes are defined in design.md § Verify before building. They were run on 2026-10-24 between 16:41 and 16:44 UTC from a local laptop, using Python `urllib` (equivalent to the curl commands in the design).

Every response went through a filter that printed only HTTP status, counts, key names, types, and whitelisted values: `nctId`, status, date, state, `locationid`, `year`, and `geolocation`. No raw ClinicalTrials.gov body was printed or saved.

**Outcome:** all 10 probes passed, including the 4 core probes (V1, V3, V4, V5). `Q2_SERVER_CUTOFF = True`.

`$B` = `https://clinicaltrials.gov/api/v2/studies`. `$P` = `https://data.cdc.gov/resource/swc5-untb.json`.

| Probe | Core | Result | Observed |
|---|---|---|---|
| V1 `filter.geo` accepted | yes | **PASS** | HTTP 200, `totalCount` 44,627 with geo versus 608,415 without. `distance(42.3,-71.8)` with no radius returns HTTP **400**. |
| V2 `filter.overallStatus` multi-value | | **PASS** | Comma list: 9,095 = RECRUITING 5,092 + NOT_YET_RECRUITING 454 + ACTIVE_NOT_RECRUITING 3,549. The pipe-separated form also returns 9,095. The design uses commas. |
| V3 location sub-fields exclude contacts | yes | **PASS** | Sub-field `fields`, pageSize 20: 575 locations, 0 `contacts` keys, keys = `city, facility, geoPoint, state, status, zip`. Control (whole `locations`): 422 of 575 locations have `contacts`. Only counts were printed. No `centralContacts`, `overallOfficials`, or `responsibleParty` keys appeared in either case. |
| V4 `totalCount` on page 1 | yes | **PASS** | Q1 `totalCount` 9,095 (int), which gives 10 pages. Q2 `totalCount` 7,110 (int), which gives 8 pages. `pageSize=1000` returns 1,000 studies. Page 2 has **no** `totalCount` key, which is fine because the design reads page 1. |
| V5 PLACES MA `CrdPrv` and `locationid` | yes | **PASS** | HTTP 200. All 12 `$select` keys are present. `locationid` = `"25027"` (JSON string), `datavaluetypeid` = `CrdPrv`, `measure` is present. 14 counties (`25001`–`25027`, odd numbers) × 40 measures = 560 rows, so everything fits on 1 page. |
| V6 record shape | | **PASS** | `lastUpdatePostDateStruct.date` is a `YYYY-MM-DD` str. `healthyVolunteers` is bool. `geoPoint.lat` and `geoPoint.lon` are float. The site status key is `status`. `state` holds full names ("Connecticut"). `meshes[]` and `ancestors[]` are `{id, term}`. `interventions[]` is `{type, name}`. No keys outside the requested paths. |
| V7 pagination end marker | | **PASS, with a note** | A partly full last page has no `nextPageToken` key (542 of 1,000). **A last page that is exactly full still carries a token.** Following that token returns HTTP 200 with `studies: []` and no token. |
| V8 PLACES `geolocation` | | **PASS** | `{"type":"Point","coordinates":[-71.9077…, 42.3513…]}`, with longitude first (GeoJSON). |
| V9 PLACES `$order` with `:id` and `$offset` | | **PASS** | HTTP 200 with 1 record for `$order=locationname,measureid,:id&$offset=0`. |
| V10 Q2 server date filter | | **PASS** | `filter.advanced=AREA[LastUpdatePostDate]RANGE[2023-10-23,MAX]` with `COMPLETED` and geo: HTTP 200, `totalCount` 7,110 versus 27,496 unfiltered. Ascending sort gives an earliest date of 2023-10-23, so the lower bound is inclusive. Descending gives 2026-10-23. Every returned study is `COMPLETED`. Control `RANGE[MIN,2023-10-23]`: 20,407, latest 2023-10-23. |

## Request URLs

- V1: `$B?filter.geo=distance(42.3,-71.8,150mi)&pageSize=1&countTotal=true&fields=protocolSection.identificationModule.nctId`
- V1 (400 check): `$B?filter.geo=distance(42.3,-71.8)&pageSize=1&countTotal=true&fields=protocolSection.identificationModule.nctId`
- V2 / V4 (Q1): `$B?filter.geo=distance(42.3,-71.8,150mi)&filter.overallStatus=RECRUITING,NOT_YET_RECRUITING,ACTIVE_NOT_RECRUITING&pageSize=1&countTotal=true&fields=protocolSection.identificationModule.nctId`
- V3: `$B?filter.geo=distance(42.3,-71.8,150mi)&filter.overallStatus=RECRUITING&pageSize=20&fields=protocolSection.contactsLocationsModule.locations.{facility,city,state,zip,status,geoPoint}`. Each sub-field was listed in full in the actual request.
- V5: `$P?$select=locationname,locationid,measureid,measure,data_value,low_confidence_limit,high_confidence_limit,totalpop18plus,geolocation,year,stateabbr,datavaluetypeid&$where=stateabbr='MA' AND datavaluetypeid='CrdPrv'&$limit=1`
- V6: Q1 query with the full design `fields` list, `pageSize=20`.
- V7: `$B?filter.ids=<nctId>&pageSize=1` and `pageSize=2`, plus a narrow Q1 query: `filter.advanced=AREA[LastUpdatePostDate]RANGE[2026-10-20,MAX]&pageSize=1000`.
- V9: the V5 request plus `$order=locationname,measureid,:id&$offset=0`.
- V10 / V4 (Q2): `$B?filter.geo=distance(42.3,-71.8,150mi)&filter.overallStatus=COMPLETED&filter.advanced=AREA%5BLastUpdatePostDate%5DRANGE%5B2023-10-23,MAX%5D&sort=LastUpdatePostDate%3Aasc&pageSize=1&countTotal=true&fields=protocolSection.identificationModule.nctId,protocolSection.statusModule.overallStatus,protocolSection.statusModule.lastUpdatePostDateStruct`

## Findings that affect later tasks

1. **Expected volume.** Q1 is 9,095 and Q2 is 7,110, for 16,205 records over 18 pages. Without the date filter, Q2 would be 27,496 records. Both queries are far below the 100-page limit.
2. **Exactly full last page (V7).** If a query's Total_Count is a multiple of 1,000, the fetcher requests one extra page that comes back empty, with `studies: []` and no token. The design already handles this:
   - An empty `studies` array is valid under Req 1.6.
   - The page is scrubbed and stored like any other page.
   - The count check is unaffected.
   - Raw_Store completeness ("last page has no token") still holds.

   Task 5 should include a test for this case.
3. **Locations are worldwide (V6).** `filter.geo` selects studies, not sites. A study near Worcester returns all its sites, including Beijing and Buenos Aires. The Allowed_States site filter (Req 5.3) is required, as designed.
4. **Missing site status (V6).** Some locations have no `status`. These are written as an empty site status (Req 5.2).
5. **PLACES years (V5).** 490 rows are from 2023 and 70 from 2022. These are different measures, not duplicates: grouping by (`locationname`, `measureid`) with `count(*) > 1` returns 0 pairs. The keep-latest-year rule (Req 6.3) is not triggered by current data.
6. **PLACES values are strings.** `data_value`, the confidence limits, `totalpop18plus`, and `year` all arrive as JSON strings. This matches the design's choice to keep the source text.
7. **Q2 lower bound.** `RANGE` is inclusive. The cutoff − 1 day margin is harmless and stays in place, because the post-fetch filter removes the extra day.
