// Unit tests for the chart's axis tick generation (pure logic, no DOM).
//
// The point of `axisTicks` is that the axis reads as round numbers while still
// spanning the real data domain, so these tests pin the values it picks for the
// actual WHAT data, the invariants that must hold for any domain, and the
// degenerate inputs the chart can genuinely receive (a single disease with a
// zero-width domain, or no finite bounds at all).

import { describe, it, expect } from "vitest";
import { axisTicks, formatAxisTick } from "./axisTicks";

describe("axisTicks", () => {
  it("labels the real WHAT domain with round numbers", () => {
    // The shipped data spans 1.33 (min low) to 5.24 (max high).
    expect(axisTicks(1.33, 5.24)).toEqual([2, 3, 4, 5]);
  });

  it("keeps every tick inside the domain and in ascending order", () => {
    const domains: readonly [number, number][] = [
      [1.33, 5.24],
      [0, 1],
      [0, 100],
      [12.5, 87.3],
      [0.001, 0.009],
      [1000, 4200],
      [-3, 7],
      [6.01, 6.99],
    ];

    for (const [min, max] of domains) {
      const ticks = axisTicks(min, max);
      expect(ticks.length).toBeGreaterThanOrEqual(2);
      expect(ticks.length).toBeLessThanOrEqual(6);
      for (const tick of ticks) {
        expect(tick).toBeGreaterThanOrEqual(min);
        expect(tick).toBeLessThanOrEqual(max);
      }
      expect([...ticks].sort((a, b) => a - b)).toEqual(ticks);
    }
  });

  it("returns one label for a zero-width domain (every value identical)", () => {
    expect(axisTicks(3, 3)).toEqual([3]);
  });

  it("returns no ticks when the domain is not finite", () => {
    expect(axisTicks(Number.NaN, 5)).toEqual([]);
    expect(axisTicks(0, Number.POSITIVE_INFINITY)).toEqual([]);
  });

  it("handles a reversed domain by normalising it", () => {
    expect(axisTicks(5.24, 1.33)).toEqual([2, 3, 4, 5]);
  });
});

describe("formatAxisTick", () => {
  it("renders integers plainly and fractions to one decimal", () => {
    expect(formatAxisTick(2)).toBe("2");
    expect(formatAxisTick(2.5)).toBe("2.5");
    expect(formatAxisTick(0.30000000000000004)).toBe("0.3");
    expect(formatAxisTick(Number.NaN)).toBe("");
  });
});
