// Pure logic for resolving per-county map state in the WHERE view
// (Req 9.1, 9.3, 9.4).
//
// This module holds small, pure, non-mutating functions over Where_Data. They
// never fetch, never mutate their inputs, and never recompute the index — they
// read the precomputed `miles_to_nearest` / `has_verified_site` fields carried
// by each WhereEntry and classify a county into a distance bucket or the
// explicit "unknown" state used by both the map fill and its text alternative.

import type { WhereEntry } from "./types";

/**
 * A distance bucket index into the five-step sequential choropleth ramp
 * (`--seq-1` .. `--seq-5`, light -> dark). `1` is the nearest (shortest
 * distance) bucket; `5` is the farthest.
 */
export type DistanceBucket = 1 | 2 | 3 | 4 | 5;

/**
 * The outcome of resolving one (disease, county) pair. A county is either
 * shaded by a concrete distance bucket derived from its miles to the nearest
 * verified recruiting site, or marked explicitly "unknown" (Req 9.3, 9.4).
 *
 * This discriminated union guarantees that an unknown county can never be
 * mistaken for the zero-distance bucket: the two cases carry different `kind`
 * tags, and the `"unknown"` case carries no `bucket` field at all.
 */
export type CountyState =
  | { kind: "bucket"; miles: number; bucket: DistanceBucket }
  | { kind: "unknown" };

/**
 * Inclusive upper bounds (in miles) for buckets 1 through 4. A distance that is
 * `<=` a threshold falls in that bucket; anything greater than the last
 * threshold falls in bucket 5. The ramp is chosen for Massachusetts-county
 * distances to the nearest verified recruiting site:
 *
 *   bucket 1: 0 <= miles <= 10   (very near)
 *   bucket 2: 10 < miles <= 25
 *   bucket 3: 25 < miles <= 50
 *   bucket 4: 50 < miles <= 100
 *   bucket 5: miles > 100        (farthest)
 *
 * Exported so the map legend and text alternative can describe the exact same
 * boundaries (Req 9.5).
 */
export const BUCKET_UPPER_BOUNDS_MILES: readonly [
  number,
  number,
  number,
  number,
] = [10, 25, 50, 100];

/**
 * Map a non-negative distance in miles to its sequential-ramp bucket (1..5).
 * Zero miles maps to bucket 1 (the nearest bucket) — never to the "unknown"
 * state, which is reserved for the Unknown_Distance / no-entry cases.
 */
function bucketForMiles(miles: number): DistanceBucket {
  for (let i = 0; i < BUCKET_UPPER_BOUNDS_MILES.length; i++) {
    if (miles <= BUCKET_UPPER_BOUNDS_MILES[i]) {
      return (i + 1) as DistanceBucket;
    }
  }
  return 5;
}

/**
 * Resolve the map/table state for one disease and county.
 *
 * Returns `{ kind: "unknown" }` when there is no WhereEntry matching both
 * `measureId` and `countyFips`, or when the matching entry is in the
 * Unknown_Distance state (`miles_to_nearest === null && has_verified_site ===
 * false`). Otherwise returns `{ kind: "bucket", miles, bucket }` with `bucket`
 * derived from `miles_to_nearest` (Req 9.1, 9.3, 9.4).
 *
 * It never returns the zero-distance bucket for an unknown county and never
 * returns a blank/undefined result — every county resolves to exactly one of
 * the two cases.
 *
 * Pure and non-mutating: does not modify `whereData`.
 */
export function resolveCountyState(
  whereData: readonly WhereEntry[],
  measureId: string,
  countyFips: string
): CountyState {
  const match = whereData.find(
    (entry) =>
      entry.measure_id === measureId && entry.county_fips === countyFips
  );

  // No entry for this (disease, county) pair -> explicit unknown (Req 9.4).
  if (match === undefined) {
    return { kind: "unknown" };
  }

  // Unknown_Distance state -> explicit unknown, never zero (Req 9.3).
  if (match.miles_to_nearest === null && match.has_verified_site === false) {
    return { kind: "unknown" };
  }

  // A null distance without the Unknown_Distance flag pairing is not a valid
  // numeric bucket either; treat it as unknown rather than fabricating a
  // number. (validateWhereEntry allows null only in the Unknown_Distance case,
  // but guarding here keeps the function total and never returns a blank.)
  if (match.miles_to_nearest === null) {
    return { kind: "unknown" };
  }

  const miles = match.miles_to_nearest;
  return { kind: "bucket", miles, bucket: bucketForMiles(miles) };
}
