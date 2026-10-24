// Feature: dashboard, Property 7: Every county resolves to its own distance bucket or an explicit unknown marker
//
// Validates: Requirements 9.1, 9.3, 9.4, 10.1, 10.2
//
// For any Where_Data (including Unknown_Distance entries and queries with no
// matching entry), resolveCountyState must always return one of the two
// discriminated-union cases — never undefined or a blank. A matching,
// non-Unknown_Distance entry resolves to `{ kind: "bucket", miles, bucket }`
// with `miles === entry.miles_to_nearest` and `bucket` the correct bucket for
// that distance; a missing entry or an Unknown_Distance entry resolves to
// `{ kind: "unknown" }`. An unknown county is never assigned the zero-distance
// bucket.

import { describe, expect, test } from "vitest";
import fc from "fast-check";

import {
  BUCKET_UPPER_BOUNDS_MILES,
  resolveCountyState,
} from "./where";
import type { WhereEntry } from "./types";

/**
 * Expected bucket for a non-negative distance, derived from the exported
 * thresholds (not a hardcoded copy). A distance that is `<=` a threshold falls
 * in that bucket (1-indexed); anything beyond the last threshold is bucket 5.
 */
function expectedBucket(miles: number): 1 | 2 | 3 | 4 | 5 {
  for (let i = 0; i < BUCKET_UPPER_BOUNDS_MILES.length; i++) {
    if (miles <= BUCKET_UPPER_BOUNDS_MILES[i]) {
      return (i + 1) as 1 | 2 | 3 | 4 | 5;
    }
  }
  return 5;
}

/** Small pools so generated queries can collide with generated entries. */
const measureIdArb = fc.constantFrom("m1", "m2", "m3", "m4");
const countyFipsArb = fc.constantFrom(
  "25001",
  "25003",
  "25005",
  "25017",
  "25025"
);

/**
 * A WhereEntry that is NOT Unknown_Distance: a concrete non-negative distance
 * (including 0, which must still map to a bucket, never to unknown) and a
 * verified site. `max` spans past the last threshold so bucket 5 is reachable.
 */
const bucketEntryArb: fc.Arbitrary<WhereEntry> = fc
  .record({
    county_fips: countyFipsArb,
    measure_id: measureIdArb,
    miles: fc.double({ min: 0, max: 250, noNaN: true, noDefaultInfinity: true }),
  })
  .map(
    ({ county_fips, measure_id, miles }): WhereEntry => ({
      county_fips,
      county: `county ${county_fips}`,
      condition: `cond ${measure_id}`,
      measure_id,
      miles_to_nearest: miles,
      has_verified_site: true,
    })
  );

/**
 * A WhereEntry in the Unknown_Distance state: `miles_to_nearest === null` and
 * `has_verified_site === false`.
 */
const unknownEntryArb: fc.Arbitrary<WhereEntry> = fc
  .record({
    county_fips: countyFipsArb,
    measure_id: measureIdArb,
  })
  .map(
    ({ county_fips, measure_id }): WhereEntry => ({
      county_fips,
      county: `county ${county_fips}`,
      condition: `cond ${measure_id}`,
      measure_id,
      miles_to_nearest: null,
      has_verified_site: false,
    })
  );

const whereEntryArb: fc.Arbitrary<WhereEntry> = fc.oneof(
  bucketEntryArb,
  unknownEntryArb
);

describe("resolveCountyState — Property 7: bucket or explicit unknown", () => {
  test("every (measureId, countyFips) resolves to a bucket or an explicit unknown, never blank", () => {
    fc.assert(
      fc.property(
        // Where_Data mixing bucket and Unknown_Distance entries (may be empty,
        // so the no-matching-entry case is also exercised).
        fc.array(whereEntryArb, { minLength: 0, maxLength: 20 }),
        // The queried pair may or may not match any entry.
        measureIdArb,
        countyFipsArb,
        (whereData, measureId, countyFips) => {
          const state = resolveCountyState(whereData, measureId, countyFips);

          // Always one of the two discriminated-union cases — never
          // undefined/blank (Req 9.1, 10.1, 10.2).
          expect(state).toBeDefined();
          expect(state.kind === "bucket" || state.kind === "unknown").toBe(true);

          // `find` mirrors the resolver: first matching entry on both keys.
          const match = whereData.find(
            (entry) =>
              entry.measure_id === measureId &&
              entry.county_fips === countyFips
          );

          const isUnknownDistance =
            match !== undefined &&
            match.miles_to_nearest === null &&
            match.has_verified_site === false;

          if (match !== undefined && !isUnknownDistance) {
            // A matching, non-Unknown_Distance entry -> concrete bucket with
            // miles echoed from the entry and the correct bucket (Req 9.1).
            expect(state.kind).toBe("bucket");
            if (state.kind !== "bucket") return;
            expect(state.miles).toBe(match.miles_to_nearest);
            expect(state.bucket).toBe(
              expectedBucket(match.miles_to_nearest as number)
            );
          } else {
            // No matching entry, OR an Unknown_Distance entry -> explicit
            // unknown (Req 9.3, 9.4). An unknown county is never assigned a
            // bucket (and so never the zero-distance bucket 1).
            expect(state.kind).toBe("unknown");
            expect(state).not.toHaveProperty("bucket");
          }
        }
      ),
      { numRuns: 100 }
    );
  });
});
