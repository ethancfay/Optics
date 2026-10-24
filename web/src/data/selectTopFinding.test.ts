// Feature: dashboard, Property 5: The home top finding is the lowest-midpoint disease, ties broken alphabetically
//
// Validates: Requirements 4.2, 4.3
//
// `selectTopFinding(entries)` must return the WhatEntry with the minimum `mid`,
// breaking ties by the case-insensitively smallest `condition`, and return
// `undefined` for an empty array. The generator deliberately draws `mid` from a
// small set so duplicate midpoints are common, exercising the tie-break.

import { describe, it, expect } from "vitest";
import fc from "fast-check";

import { selectTopFinding } from "./conditions";
import type { WhatEntry } from "./types";

// A WhatEntry arbitrary tuned for this property: `mid` is drawn from a small
// pool so ties are frequent, and `condition` strings vary in case so the
// case-insensitive tie-break is actually exercised. Fields irrelevant to
// selection are given simple in-bounds values.
const whatEntryArb: fc.Arbitrary<WhatEntry> = fc
  .record({
    condition: fc
      .string({ minLength: 1, maxLength: 8 })
      .filter((s) => s.trim().length > 0),
    measure_id: fc.string({ minLength: 1, maxLength: 6 }),
    mid: fc.integer({ min: 0, max: 5 }),
    low: fc.integer({ min: 0, max: 5 }),
    high: fc.integer({ min: 0, max: 5 }),
    t: fc.nat({ max: 50 }),
    affected_adults: fc.nat({ max: 1_000_000 }),
    p_low: fc.double({ min: 0.01, max: 0.5, noNaN: true }),
    p_high: fc.double({ min: 0.5, max: 1, noNaN: true }),
    ctgov_url: fc.constant("https://clinicaltrials.gov/"),
  })
  // Keep the documented low <= mid <= high invariant so the data is realistic;
  // selection only reads `mid` and `condition`, so this does not bias the test.
  .map((e) => ({
    ...e,
    low: Math.min(e.low, e.mid),
    high: Math.max(e.high, e.mid),
  }));

// Reference implementation of the selection rule, derived straight from the
// acceptance criteria rather than from the module under test.
function expectedTop(entries: readonly WhatEntry[]): WhatEntry | undefined {
  if (entries.length === 0) return undefined;
  return entries.reduce((best, entry) => {
    if (entry.mid < best.mid) return entry;
    if (entry.mid > best.mid) return best;
    // Equal mid: smaller case-insensitive condition wins; ties keep the
    // earlier entry (stable), matching the module's first-seen behaviour.
    return entry.condition.toLowerCase() < best.condition.toLowerCase()
      ? entry
      : best;
  });
}

describe("selectTopFinding (Property 5)", () => {
  it("returns undefined for the empty array", () => {
    expect(selectTopFinding([])).toBeUndefined();
  });

  it("returns the minimum-mid entry, ties broken by case-insensitive condition", () => {
    fc.assert(
      fc.property(fc.array(whatEntryArb, { minLength: 1 }), (entries) => {
        const result = selectTopFinding(entries);
        expect(result).toBeDefined();

        const minMid = Math.min(...entries.map((e) => e.mid));
        // The selected entry must sit at the minimum midpoint.
        expect(result!.mid).toBe(minMid);

        // Among all minimum-mid entries, the selected condition must be the
        // smallest case-insensitively.
        const smallestCondition = entries
          .filter((e) => e.mid === minMid)
          .map((e) => e.condition.toLowerCase())
          .reduce((a, b) => (a < b ? a : b));
        expect(result!.condition.toLowerCase()).toBe(smallestCondition);

        // And it must agree with an independent reference implementation
        // (identity-equal, confirming it returns an actual input entry and
        // does not mutate/clone).
        expect(result).toBe(expectedTop(entries));
      }),
      { numRuns: 100 }
    );
  });
});
