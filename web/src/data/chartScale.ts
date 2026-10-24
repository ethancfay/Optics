// Pure logic for the DotWhiskerChart's shared horizontal scale.
//
// The chart draws, for every disease, a whisker from `low` to `high` and a dot
// at `mid` on a single shared linear scale (Req 5.1). Because every valid entry
// satisfies `low <= mid <= high` and this scale is monotonically
// non-decreasing, the mapped positions preserve that ordering:
// `x(low) <= x(mid) <= x(high)` for every entry (Req 5.6).
//
// This module is intentionally dependency-free and side-effect-free so the
// chart and its text alternative derive their geometry from the same
// deterministic mapping.

import type { WhatEntry } from "./types";

/**
 * A linear scale produced by {@link chartScale}.
 *
 * `x(value)` maps a data value in `[domainMin, domainMax]` to an x pixel
 * position in `[rangeMin, rangeMax]`. The mapping is monotonically
 * non-decreasing, so for any value triple with `low <= mid <= high` the mapped
 * positions satisfy `x(low) <= x(mid) <= x(high)`.
 */
export interface ChartScale {
  /** Maps a data value to its x pixel position. */
  x: (value: number) => number;
  /** Minimum of the data domain (min `low` across all entries). */
  domainMin: number;
  /** Maximum of the data domain (max `high` across all entries). */
  domainMax: number;
  /** Minimum of the output pixel range. */
  rangeMin: number;
  /** Maximum of the output pixel range. */
  rangeMax: number;
}

/** Default x pixel range used when no explicit range is supplied. */
const DEFAULT_RANGE: readonly [number, number] = [0, 100];

/**
 * Builds a linear {@link ChartScale} whose domain spans the full range of the
 * data — from the minimum `low` to the maximum `high` across every entry — and
 * maps that domain onto an x pixel range (default `[0, 100]`).
 *
 * The scale is pure: it does not mutate `entries` and has no side effects.
 *
 * Edge cases are handled gracefully (degenerate but non-crashing):
 * - Empty `entries` (or entries that yield no finite bounds): the domain
 *   collapses to `[0, 0]` and `x` maps every value to `rangeMin`.
 * - A zero-width domain (all values equal): `x` maps every value to `rangeMin`
 *   rather than dividing by zero.
 *
 * @param entries   The diseases to be plotted (read-only; not mutated).
 * @param range     Optional `[rangeMin, rangeMax]` x pixel range.
 */
export function chartScale(
  entries: readonly WhatEntry[],
  range: readonly [number, number] = DEFAULT_RANGE,
): ChartScale {
  const [rangeMin, rangeMax] = range;

  let domainMin = Number.POSITIVE_INFINITY;
  let domainMax = Number.NEGATIVE_INFINITY;

  for (const entry of entries) {
    if (Number.isFinite(entry.low) && entry.low < domainMin) {
      domainMin = entry.low;
    }
    if (Number.isFinite(entry.high) && entry.high > domainMax) {
      domainMax = entry.high;
    }
  }

  // No finite bounds found (empty input or all non-finite): degenerate domain.
  if (!Number.isFinite(domainMin) || !Number.isFinite(domainMax)) {
    domainMin = 0;
    domainMax = 0;
  }

  const domainSpan = domainMax - domainMin;

  const x = (value: number): number => {
    // Zero-width domain: avoid division by zero by pinning to rangeMin.
    if (domainSpan <= 0) {
      return rangeMin;
    }
    const t = (value - domainMin) / domainSpan;
    return rangeMin + t * (rangeMax - rangeMin);
  };

  return { x, domainMin, domainMax, rangeMin, rangeMax };
}
