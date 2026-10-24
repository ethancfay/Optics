import { describe, expect, test } from "vitest";
import fc from "fast-check";

import { chartScale } from "./chartScale";
import type { WhatEntry } from "./types";

// Feature: dashboard, Property 6: Displayed index values always show the full
// low-high range, with the dot inside the whisker
//
// Validates Requirements 5.1, 5.6.
//
// Every valid WhatEntry satisfies `low <= mid <= high`. The shared chart scale
// built from a dataset must map those values so the dot (at `mid`) always lies
// within the whisker drawn from `low` to `high` — i.e. `x(low) <= x(mid) <=
// x(high)` — and both the `low` and `high` endpoints must fall inside the
// chart's pixel range, so the full range is always displayed.

/**
 * An arbitrary for a WhatEntry whose numeric values satisfy the data-layer
 * invariants the chart relies on (`low <= mid <= high`, `0 < p_low <= p_high
 * <= 1`, non-negative counts). Only the geometry fields drive the scale; the
 * rest are filled with valid placeholders.
 */
const whatEntryArb: fc.Arbitrary<WhatEntry> = fc
  .record({
    low: fc.double({
      min: 0,
      max: 1e6,
      noNaN: true,
      noDefaultInfinity: true,
    }),
    // Non-negative offsets keep low <= mid <= high by construction.
    midOffset: fc.double({
      min: 0,
      max: 1e6,
      noNaN: true,
      noDefaultInfinity: true,
    }),
    highOffset: fc.double({
      min: 0,
      max: 1e6,
      noNaN: true,
      noDefaultInfinity: true,
    }),
    condition: fc.string({ minLength: 1, maxLength: 20 }),
    measure_id: fc.string({ minLength: 1, maxLength: 12 }),
    t: fc.nat({ max: 1000 }),
    affected_adults: fc.nat({ max: 10_000_000 }),
    p: fc.double({ min: 0.01, max: 1, noNaN: true, noDefaultInfinity: true }),
    pHighOffset: fc.double({
      min: 0,
      max: 0.5,
      noNaN: true,
      noDefaultInfinity: true,
    }),
  })
  .map(
    ({
      low,
      midOffset,
      highOffset,
      condition,
      measure_id,
      t,
      affected_adults,
      p,
      pHighOffset,
    }): WhatEntry => {
      const mid = low + midOffset;
      const high = mid + highOffset;
      const p_low = p;
      const p_high = Math.min(1, p + pHighOffset);
      return {
        condition,
        measure_id,
        low,
        mid,
        high,
        t,
        affected_adults,
        p_low,
        p_high,
        ctgov_url: "https://clinicaltrials.gov/",
      };
    },
  );

describe("chartScale — Property 6: range display and dot-inside-whisker", () => {
  test("x(low) <= x(mid) <= x(high) and endpoints lie within the pixel range", () => {
    fc.assert(
      fc.property(
        fc.array(whatEntryArb, { minLength: 1, maxLength: 30 }),
        (entries) => {
          const scale = chartScale(entries);
          const lo = Math.min(scale.rangeMin, scale.rangeMax);
          const hi = Math.max(scale.rangeMin, scale.rangeMax);

          for (const entry of entries) {
            const xLow = scale.x(entry.low);
            const xMid = scale.x(entry.mid);
            const xHigh = scale.x(entry.high);

            // The dot at `mid` lies within the whisker from `low` to `high`.
            expect(xLow).toBeLessThanOrEqual(xMid);
            expect(xMid).toBeLessThanOrEqual(xHigh);

            // Both endpoints of the whisker map inside the pixel range, so the
            // full low-high range is always displayed.
            expect(xLow).toBeGreaterThanOrEqual(lo);
            expect(xLow).toBeLessThanOrEqual(hi);
            expect(xHigh).toBeGreaterThanOrEqual(lo);
            expect(xHigh).toBeLessThanOrEqual(hi);
          }
        },
      ),
      { numRuns: 100 },
    );
  });
});
