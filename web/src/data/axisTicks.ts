// Pure tick generation for the DotWhiskerChart's value axis.
//
// The chart's x scale is derived from the data (see `chartScale`), so the tick
// labels have to be derived from the same domain rather than hard-coded. Round
// numbers are what make an axis readable — the raw domain here is 1.33..5.24,
// which would give labels like "1.33, 3.29, 5.24". This module snaps the step to
// a "nice" 1/2/2.5/5 × 10^k value so the same axis reads 2, 3, 4, 5.
//
// Dependency-free and side-effect-free, like `chartScale`: the chart and any
// test derive the same ticks from the same domain deterministically.

/** Default number of ticks to aim for (the visual design asks for 4–5 labels). */
const TARGET_TICK_COUNT = 5;

/** Hard cap so a hostile domain can never emit an unbounded list of ticks. */
const MAX_TICKS = 12;

/**
 * Snap a raw step to the nearest "nice" step of 1, 2, 2.5 or 5 times a power of
 * ten, which is what makes the resulting labels read as round numbers.
 */
function niceStep(rawStep: number): number {
  const magnitude = 10 ** Math.floor(Math.log10(rawStep));
  const normalized = rawStep / magnitude;
  const nice =
    normalized <= 1
      ? 1
      : normalized <= 2
        ? 2
        : normalized <= 2.5
          ? 2.5
          : normalized <= 5
            ? 5
            : 10;
  return nice * magnitude;
}

/** Round away binary floating-point noise (0.30000000000000004 -> 0.3). */
function round(value: number): number {
  return Number(value.toFixed(10));
}

/**
 * Values to label along an axis spanning `domainMin..domainMax`.
 *
 * Returns at most {@link MAX_TICKS} values, all inside the domain, spaced by a
 * nice step. Degenerate inputs degrade gracefully rather than throwing:
 *
 * - non-finite bounds -> no ticks at all;
 * - a zero-width domain (every value identical) -> that single value;
 * - a domain too narrow for two nice ticks -> its two ends.
 *
 * @param domainMin    Lower bound of the axis domain (inclusive).
 * @param domainMax    Upper bound of the axis domain (inclusive).
 * @param targetCount  How many ticks to aim for; clamped to a sane range.
 */
export function axisTicks(
  domainMin: number,
  domainMax: number,
  targetCount: number = TARGET_TICK_COUNT,
): number[] {
  if (!Number.isFinite(domainMin) || !Number.isFinite(domainMax)) {
    return [];
  }

  const min = Math.min(domainMin, domainMax);
  const max = Math.max(domainMin, domainMax);
  const span = max - min;

  // A single value can only ever carry one label.
  if (span <= 0) {
    return [round(min)];
  }

  const desired = Math.max(2, Math.floor(targetCount));
  const step = niceStep(span / (desired - 1));

  // First nice multiple at or above the domain minimum. The epsilon keeps an
  // exact multiple (e.g. min = 2 with step 1) from being skipped by float error.
  const first = Math.ceil(min / step - 1e-9) * step;

  const ticks: number[] = [];
  for (let value = first; value <= max + step * 1e-6; value += step) {
    ticks.push(round(value));
    if (ticks.length >= MAX_TICKS) {
      return ticks;
    }
  }

  // Too narrow for two nice ticks: fall back to the domain ends so the reader
  // still gets the range, de-duplicated for the zero-width case.
  if (ticks.length < 2) {
    return [...new Set([round(min), round(max)])];
  }

  return ticks;
}

/** Fixed en-US grouping so tick labels do not depend on the browser locale. */
const INTEGER_FORMAT = new Intl.NumberFormat("en-US", {
  maximumFractionDigits: 0,
});

/**
 * Format a tick value for display in plain decimal form: integers with en-US
 * grouping ("2", "1,000"), fractional ticks of at least 0.1 with at most one
 * decimal ("2.5"), and smaller log-scale ticks with their own significant
 * digits ("0.01", "0.001") so they are never rounded to "0" (Req 22.3).
 */
export function formatAxisTick(value: number): string {
  if (!Number.isFinite(value)) {
    return "";
  }
  if (Number.isInteger(value)) {
    return INTEGER_FORMAT.format(value);
  }
  if (Math.abs(value) >= 0.1) {
    return String(Math.round(value * 10) / 10);
  }
  // Fixed-point with a few digits past the first significant one strips binary
  // noise (0.0010000000000000002 -> "0.001") and never uses exponent form.
  const digits = Math.min(20, 5 - Math.floor(Math.log10(Math.abs(value))));
  return value.toFixed(digits).replace(/0+$/, "");
}
