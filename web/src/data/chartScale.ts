// Pure logic for the DotWhiskerChart's shared horizontal scale (Req 5.1, 5.6,
// Req 22).
//
// The chart draws, for every disease, a whisker from `low` to `high` and a dot
// at `mid` on one shared scale. The shipped values span more than ten times
// (0.23 to 12.83), so a linear axis squeezes the smaller diseases against the
// left edge and exaggerates the gap between them. The scale is therefore
// base-10 logarithmic whenever every plotted `low` is above 0 (Req 22.1), and
// falls back to a linear axis starting at 0 when any `low` is 0 or less, e.g. a
// future disease with zero recruiting studies (Req 22.5).
//
// Both mappings are monotonically non-decreasing, so for every valid entry
// (`low <= mid <= high`) the mapped positions keep `x(low) <= x(mid) <=
// x(high)` (Req 22.6). The mode, domain and ticks are a pure function of the
// entries (Req 22.7), so the chart and its tests derive identical geometry.

import type { WhatEntry } from "./types";
import { axisTicks } from "./axisTicks";

/** Which kind of axis {@link chartScale} chose for the entries. */
export type ChartScaleKind = "log" | "linear";

/**
 * A scale produced by {@link chartScale}.
 *
 * `x(value)` maps a data value in `[domainMin, domainMax]` to an x pixel
 * position in `[rangeMin, rangeMax]`. The mapping is monotonically
 * non-decreasing in both modes.
 */
export interface ChartScale {
  /** "log" when every plotted `low > 0` (Req 22.1), otherwise "linear". */
  kind: ChartScaleKind;
  /** Maps a data value to its x pixel position. */
  x: (value: number) => number;
  /** Lower bound of the data domain. */
  domainMin: number;
  /** Upper bound of the data domain. */
  domainMax: number;
  /** Minimum of the output pixel range. */
  rangeMin: number;
  /** Maximum of the output pixel range. */
  rangeMax: number;
  /** Values at which the chart draws gridlines and tick labels. */
  ticks: readonly number[];
}

/** Default x pixel range used when no explicit range is supplied. */
const DEFAULT_RANGE: readonly [number, number] = [0, 100];

/** Headroom above the largest `high` in log mode (Req 22.2). */
const LOG_HEADROOM = 1.1;

/** Tolerance for floating-point noise in log10 and power-of-ten comparisons. */
const EPSILON = 1e-9;

/** 10^k without the binary noise of `10 ** -k` for negative k (0.1, 0.001). */
function powerOfTen(k: number): number {
  return k < 0 ? 1 / 10 ** -k : 10 ** k;
}

/**
 * The largest power of ten that is `<= value` (value > 0). The epsilon keeps an
 * exact power such as 0.1 from slipping a decade because `log10(0.1)` is not
 * exactly -1; the guard afterwards keeps the result from ever exceeding value.
 */
function floorPowerOfTen(value: number): number {
  let power = powerOfTen(Math.floor(Math.log10(value) + EPSILON));
  if (power > value) {
    power /= 10;
  }
  return power;
}

/** Every power of ten inside `[domainMin, domainMax]` (Req 22.3). */
function logTicks(domainMin: number, domainMax: number): number[] {
  const first = Math.floor(Math.log10(domainMin) - EPSILON);
  const last = Math.ceil(Math.log10(domainMax) + EPSILON);
  const ticks: number[] = [];
  for (let k = first; k <= last; k += 1) {
    const tick = powerOfTen(k);
    if (
      tick >= domainMin * (1 - EPSILON) &&
      tick <= domainMax * (1 + EPSILON)
    ) {
      ticks.push(tick);
    }
  }
  return ticks;
}

/**
 * Builds the shared {@link ChartScale} for the plotted entries and maps it onto
 * an x pixel range (default `[0, 100]`).
 *
 * - Log mode (every finite `low > 0`): domain from the largest power of ten
 *   `<= min(low)` to `1.1 * max(high)`; ticks at every power of ten inside it.
 * - Linear fallback (any `low <= 0`): domain `[0, max(high)]`; round ticks
 *   starting at 0. A zero-width domain (every value 0) pins every value to
 *   `rangeMin` rather than dividing by zero.
 * - No finite bounds (e.g. no entries): linear, domain `[0, 0]`, no ticks.
 *
 * Pure: it does not mutate `entries` and has no side effects.
 *
 * @param entries   The diseases to be plotted (read-only; not mutated).
 * @param range     Optional `[rangeMin, rangeMax]` x pixel range.
 */
export function chartScale(
  entries: readonly WhatEntry[],
  range: readonly [number, number] = DEFAULT_RANGE,
): ChartScale {
  const [rangeMin, rangeMax] = range;
  const rangeSpan = rangeMax - rangeMin;

  let minLow = Number.POSITIVE_INFINITY;
  let maxHigh = Number.NEGATIVE_INFINITY;
  for (const entry of entries) {
    if (Number.isFinite(entry.low) && entry.low < minLow) {
      minLow = entry.low;
    }
    if (Number.isFinite(entry.high) && entry.high > maxHigh) {
      maxHigh = entry.high;
    }
  }

  // No finite bounds: degenerate, non-crashing linear scale.
  if (!Number.isFinite(minLow) || !Number.isFinite(maxHigh)) {
    return {
      kind: "linear",
      x: () => rangeMin,
      domainMin: 0,
      domainMax: 0,
      rangeMin,
      rangeMax,
      ticks: [],
    };
  }

  if (minLow > 0) {
    // Log mode (Req 22.1, 22.2). maxHigh >= minLow > 0, and the headroom makes
    // domainMax strictly greater than domainMin, so the span is never zero.
    const domainMin = floorPowerOfTen(minLow);
    const domainMax = LOG_HEADROOM * maxHigh;
    const logMin = Math.log10(domainMin);
    const logSpan = Math.log10(domainMax) - logMin;

    const x = (value: number): number => {
      if (!(value > 0) || !Number.isFinite(value)) {
        return rangeMin;
      }
      // Clamp only guards float noise at the ends; in-domain values map inside.
      const t = Math.min(1, Math.max(0, (Math.log10(value) - logMin) / logSpan));
      return rangeMin + t * rangeSpan;
    };

    return {
      kind: "log",
      x,
      domainMin,
      domainMax,
      rangeMin,
      rangeMax,
      ticks: logTicks(domainMin, domainMax),
    };
  }

  // Linear fallback starting at 0 (Req 22.5).
  const domainMin = 0;
  const domainMax = Math.max(0, maxHigh);
  const domainSpan = domainMax - domainMin;

  const x = (value: number): number => {
    if (domainSpan <= 0) {
      return rangeMin;
    }
    return rangeMin + ((value - domainMin) / domainSpan) * rangeSpan;
  };

  return {
    kind: "linear",
    x,
    domainMin,
    domainMax,
    rangeMin,
    rangeMax,
    ticks: axisTicks(domainMin, domainMax),
  };
}
