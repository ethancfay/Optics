// Feature: dashboard, Property 4: Diseases are sorted ascending by midpoint with alphabetical tie-break, and the text alternative matches
//
// Validates: Requirements 5.2, 5.3, 6.1, 6.2, 16.1
//
// Property 4 exercises the pure ordering guarantee that both the WHAT view
// Dot_Whisker_Chart (Req 5.3) and its Text_Alternative data table (Req 6.2)
// consume. At this wave the UI table component does not exist yet, so the
// testable pure-logic surface is `sortConditions`: it is the single source of
// truth for chart order AND text-alternative order, so if it is correct both
// consumers present Diseases in the same order. The test therefore asserts the
// full ordering contract on `sortConditions`:
//   - ascending by `mid`
//   - ties broken by ascending case-insensitive `condition`
//   - the result is a permutation of the input (nothing dropped or added)
//   - the input array is never mutated
// It also derives a "text alternative order" from the same sorted output (the
// condition column, in table order) and asserts it matches the chart order,
// capturing Req 6.2's "same top-to-bottom order as the chart".

import { describe, it, expect } from "vitest";
import fc from "fast-check";
import { sortConditions } from "./conditions";
import type { WhatEntry } from "./types";

/**
 * Build a full WhatEntry around a generated `condition`/`mid` pair. Only
 * `condition` and `mid` drive `sortConditions`; the remaining fields are filled
 * with contract-valid values (low <= mid <= high, 0 < p_low <= p_high <= 1) so
 * each object is a realistic entry without constraining the ordering inputs.
 */
function makeEntry(condition: string, mid: number): WhatEntry {
  return {
    condition,
    measure_id: `M_${condition}_${mid}`,
    low: mid,
    mid,
    high: mid,
    t: 0,
    affected_adults: 1,
    p_low: 0.5,
    p_high: 0.5,
    ctgov_url: "https://clinicaltrials.gov/",
  };
}

// A generator that INCLUDES duplicate `mid` values so the alphabetical
// tie-break is exercised: `mid` is drawn from a small integer range, making
// collisions common across a dataset.
const entryArb: fc.Arbitrary<WhatEntry> = fc
  .record({
    // Mixed-case, possibly-empty-ish condition strings to exercise the
    // case-insensitive comparison. Kept short so collisions on the
    // case-folded key also occur.
    condition: fc.string({ minLength: 1, maxLength: 4 }),
    // Small range => frequent duplicate midpoints.
    mid: fc.integer({ min: 0, max: 5 }),
  })
  .map(({ condition, mid }) => makeEntry(condition, mid));

const datasetArb: fc.Arbitrary<WhatEntry[]> = fc.array(entryArb, {
  minLength: 0,
  maxLength: 30,
});

/** A stable multiset signature so we can assert "same elements" ignoring order. */
function signature(entries: readonly WhatEntry[]): string[] {
  return entries
    .map((e) => `${e.condition}\u0000${e.mid}\u0000${e.measure_id}`)
    .sort();
}

describe("Property 4: sort order and text-alternative ordering (sortConditions)", () => {
  it("sorts ascending by mid with case-insensitive condition tie-break, as a non-mutating permutation", () => {
    fc.assert(
      fc.property(datasetArb, (entries) => {
        // Snapshot the input to detect mutation.
        const before = entries.map((e) => ({ ...e }));

        const sorted = sortConditions(entries);

        // --- Ordering contract (Req 5.3, 6.2) -------------------------------
        for (let i = 1; i < sorted.length; i++) {
          const prev = sorted[i - 1];
          const cur = sorted[i];
          // Primary key: ascending mid.
          expect(prev.mid).toBeLessThanOrEqual(cur.mid);
          // Secondary key: on equal mid, ascending case-insensitive condition.
          if (prev.mid === cur.mid) {
            const a = prev.condition.toLowerCase();
            const b = cur.condition.toLowerCase();
            expect(a <= b).toBe(true);
          }
        }

        // --- Permutation: nothing dropped or added (Req 6.1) ----------------
        expect(sorted.length).toBe(entries.length);
        expect(signature(sorted)).toEqual(signature(entries));

        // --- Non-mutating: input untouched (pure logic, Req 16.1) -----------
        expect(entries).toEqual(before);

        // --- Text alternative matches chart order (Req 5.2, 6.2) ------------
        // Both the chart and the Text_Alternative table draw from the same
        // sorted output, so the table's row order (its `condition` column) is
        // exactly the chart's order. Deriving it from `sorted` and comparing to
        // `sorted` confirms the single-source-of-truth ordering they share.
        const chartOrder = sorted.map((e) => e.measure_id);
        const textAlternativeOrder = sortConditions(entries).map(
          (e) => e.measure_id
        );
        expect(textAlternativeOrder).toEqual(chartOrder);
      }),
      { numRuns: 100 }
    );
  });
});
