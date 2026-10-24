import { describe, expect, it, test } from "vitest";
import fc from "fast-check";
import { readFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

import { chartScale } from "./chartScale";
import type { WhatEntry } from "./types";

/** A fully-valid entry; individual tests override the geometry fields. */
function makeEntry(overrides: Partial<WhatEntry> = {}): WhatEntry {
  return {
    condition: "Asthma",
    measure_id: "CASTHMA",
    low: 1,
    mid: 2,
    high: 3,
    t: 4,
    affected_adults: 500000,
    p_low: 0.1,
    p_high: 0.2,
    ctgov_url: "https://clinicaltrials.gov/",
    ...overrides,
  };
}

/** The shipped sample what.json, read from disk (no network). */
function shippedWhat(): WhatEntry[] {
  const here = dirname(fileURLToPath(import.meta.url));
  const path = resolve(here, "../../public/data/what.json");
  return JSON.parse(readFileSync(path, "utf8")) as WhatEntry[];
}

/** True when `value` is an exact-enough power of ten. */
function isPowerOfTen(value: number): boolean {
  const k = Math.round(Math.log10(value));
  return Math.abs(value / 10 ** k - 1) < 1e-9;
}

// Feature: dashboard, Property 6: Displayed index values always show the full
// low-high range, with the dot inside the whisker, on either scale
//
// Validates Requirements 5.1, 5.6, 22.1, 22.2, 22.3, 22.5, 22.6.
//
// `low` is drawn across six decades (1e-3 .. 1e3) so the log scale is
// exercised over wide spreads, and is sometimes exactly 0 so the linear
// fallback is exercised too. Offsets are non-negative, keeping
// low <= mid <= high by construction.

const decadeValue = fc
  .double({ min: -3, max: 3, noNaN: true, noDefaultInfinity: true })
  .map((exponent) => 10 ** exponent);

const offset = fc.oneof(
  fc.constant(0),
  fc.double({ min: 0, max: 1e3, noNaN: true, noDefaultInfinity: true }),
);

const whatEntryArb: fc.Arbitrary<WhatEntry> = fc
  .record({
    low: fc.oneof(
      { weight: 1, arbitrary: fc.constant(0) },
      { weight: 6, arbitrary: decadeValue },
    ),
    midOffset: offset,
    highOffset: offset,
  })
  .map(({ low, midOffset, highOffset }) => {
    const mid = low + midOffset;
    return makeEntry({ low, mid, high: mid + highOffset });
  });

describe("chartScale — Property 6: range display on log and linear scales", () => {
  test("mode follows min(low); x(low) <= x(mid) <= x(high) inside the range; log ticks are powers of ten", () => {
    fc.assert(
      fc.property(
        fc.array(whatEntryArb, { minLength: 1, maxLength: 30 }),
        (entries) => {
          const scale = chartScale(entries);
          const lo = Math.min(scale.rangeMin, scale.rangeMax);
          const hi = Math.max(scale.rangeMin, scale.rangeMax);
          const allPositive = entries.every((e) => e.low > 0);

          // Log iff every low > 0 (Req 22.1); otherwise linear from 0 (Req 22.5).
          expect(scale.kind).toBe(allPositive ? "log" : "linear");
          if (scale.kind === "linear") {
            expect(scale.domainMin).toBe(0);
          } else {
            const minLow = Math.min(...entries.map((e) => e.low));
            const maxHigh = Math.max(...entries.map((e) => e.high));
            // Domain: largest power of ten <= min low, to 1.1 x max high (Req 22.2).
            expect(isPowerOfTen(scale.domainMin)).toBe(true);
            expect(scale.domainMin).toBeLessThanOrEqual(minLow);
            expect(scale.domainMin * 10).toBeGreaterThan(minLow);
            expect(scale.domainMax).toBeCloseTo(1.1 * maxHigh, 9);
            // Every power of ten inside the domain, and nothing else (Req 22.3).
            expect(scale.ticks.length).toBeGreaterThan(0);
            for (const tick of scale.ticks) {
              expect(isPowerOfTen(tick)).toBe(true);
              expect(tick).toBeGreaterThanOrEqual(scale.domainMin * (1 - 1e-9));
              expect(tick).toBeLessThanOrEqual(scale.domainMax * (1 + 1e-9));
            }
            const expectedCount =
              Math.floor(Math.log10(scale.domainMax) + 1e-9) -
              Math.round(Math.log10(scale.domainMin)) +
              1;
            expect(scale.ticks.length).toBe(expectedCount);
          }

          for (const entry of entries) {
            const xLow = scale.x(entry.low);
            const xMid = scale.x(entry.mid);
            const xHigh = scale.x(entry.high);

            // The dot at `mid` lies within the whisker (Req 5.1, 22.6).
            expect(xLow).toBeLessThanOrEqual(xMid);
            expect(xMid).toBeLessThanOrEqual(xHigh);

            // Every mark is inside the plot's range, so the full low-high
            // range is always displayed (Req 5.6, 22.6).
            for (const position of [xLow, xMid, xHigh]) {
              expect(position).toBeGreaterThanOrEqual(lo);
              expect(position).toBeLessThanOrEqual(hi);
            }
          }
        },
      ),
      { numRuns: 100 },
    );
  });
});

describe("chartScale — log scale on the shipped data (Req 22.1-22.3)", () => {
  it("uses log10 with domain [0.1, 1.1 x max high] and ticks exactly 0.1, 1, 10", () => {
    const entries = shippedWhat();
    const scale = chartScale(entries, [0, 100]);

    expect(scale.kind).toBe("log");
    expect(scale.domainMin).toBe(0.1);
    expect(scale.domainMax).toBeCloseTo(1.1 * 12.83, 9);
    expect(scale.ticks).toEqual([0.1, 1, 10]);
  });

  it("positions are linear in log10(value), so equal ratios get equal distances", () => {
    const scale = chartScale([makeEntry({ low: 0.1, mid: 1, high: 10 })], [0, 100]);
    const decade = scale.x(1) - scale.x(0.1);
    expect(scale.x(10) - scale.x(1)).toBeCloseTo(decade, 9);
  });

  it("does not slip a decade when min low is exactly or just below a power of ten", () => {
    expect(chartScale([makeEntry({ low: 0.1, mid: 0.2, high: 0.3 })]).domainMin).toBe(0.1);
    expect(chartScale([makeEntry({ low: 1, mid: 2, high: 3 })]).domainMin).toBe(1);
    const justBelow = chartScale([
      makeEntry({ low: 0.09999999999, mid: 0.2, high: 0.3 }),
    ]);
    expect(justBelow.domainMin).toBeCloseTo(0.01, 12);
    expect(justBelow.domainMin).toBeLessThanOrEqual(0.09999999999);
  });
});

describe("chartScale — linear fallback when any low <= 0 (Req 22.5)", () => {
  it("falls back to a linear scale from 0 when one disease has zero studies", () => {
    const entries = [
      ...shippedWhat(),
      makeEntry({ condition: "Zero", measure_id: "ZERO", low: 0, mid: 0, high: 0, t: 0 }),
    ];
    const scale = chartScale(entries, [0, 100]);

    expect(scale.kind).toBe("linear");
    expect(scale.domainMin).toBe(0);
    expect(scale.domainMax).toBe(12.83);
    expect(scale.ticks[0]).toBe(0);
    expect(scale.x(0)).toBe(0);
    expect(scale.x(12.83)).toBe(100);
  });

  it("pins every mark to rangeMin when every value is 0", () => {
    const scale = chartScale(
      [
        makeEntry({ low: 0, mid: 0, high: 0 }),
        makeEntry({ measure_id: "B", low: 0, mid: 0, high: 0 }),
      ],
      [20, 120],
    );
    expect(scale.kind).toBe("linear");
    expect(scale.x(0)).toBe(20);
    expect(Number.isFinite(scale.x(0))).toBe(true);
  });

  it("returns a degenerate linear scale with no ticks for no entries", () => {
    const scale = chartScale([], [5, 50]);
    expect(scale.kind).toBe("linear");
    expect(scale.ticks).toEqual([]);
    expect(scale.x(3)).toBe(5);
  });
});
