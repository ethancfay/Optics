// Feature: dashboard, Property 2: Loading omits exactly the invalid entries and preserves order
//
// Validates: Requirements 3.4, 5.9
//
// For any JSON array mixing valid and invalid WhatEntry objects, loadJson must
// return a `ready` state whose `data` is exactly the valid entries in their
// original relative order, and whose `omittedCount` equals the number of
// invalid entries removed. `fetch` is stubbed to serve a generated mixed array;
// no real network request is made.

import { afterEach, expect, test, vi } from "vitest";
import fc from "fast-check";

import { loadJson } from "./loadJson";
import { validateWhatEntry } from "./validators";
import type { WhatEntry } from "./types";

afterEach(() => {
  vi.unstubAllGlobals();
});

/**
 * An arbitrary producing valid WhatEntry objects that `validateWhatEntry`
 * accepts: non-empty safe strings, >= 0 low/mid/high with low <= mid <= high,
 * non-negative integer counts, 0 < p_low <= p_high <= 1, and an https URL.
 */
const validWhatEntry: fc.Arbitrary<WhatEntry> = fc
  .record({
    condition: fc
      .string({ minLength: 1, maxLength: 20 })
      .filter((s) => s.trim().length > 0),
    measure_id: fc
      .string({ minLength: 1, maxLength: 12 })
      .filter((s) => s.trim().length > 0),
    // three non-negative values sorted into low <= mid <= high
    bounds: fc
      .tuple(
        fc.double({ min: 0, max: 1000, noNaN: true }),
        fc.double({ min: 0, max: 1000, noNaN: true }),
        fc.double({ min: 0, max: 1000, noNaN: true })
      )
      .map(([a, b, c]) => [a, b, c].sort((x, y) => x - y) as [number, number, number]),
    t: fc.nat({ max: 10_000 }),
    affected_adults: fc.nat({ max: 10_000_000 }),
    // two probabilities in (0,1] sorted into p_low <= p_high
    probs: fc
      .tuple(
        fc.double({ min: Math.fround(1e-6), max: 1, noNaN: true }),
        fc.double({ min: Math.fround(1e-6), max: 1, noNaN: true })
      )
      .map(([a, b]) => (a <= b ? ([a, b] as const) : ([b, a] as const))),
  })
  .map(({ condition, measure_id, bounds, t, affected_adults, probs }) => ({
    condition: `cond ${condition}`,
    measure_id: `id ${measure_id}`,
    low: bounds[0],
    mid: bounds[1],
    high: bounds[2],
    t,
    affected_adults,
    p_low: probs[0],
    p_high: probs[1],
    ctgov_url: "https://clinicaltrials.gov/study/NCT00000000",
  }))
  // Guard the generator against any edge (e.g. a string that trims empty): keep
  // only values the real validator accepts, so "valid" truly means valid.
  .filter((entry) => validateWhatEntry(entry));

/**
 * An arbitrary producing values that `validateWhatEntry` rejects. We cover a
 * spread of violations (missing field, wrong type, ordering break, out-of-range
 * probability, non-https url, non-object) and keep only those the real
 * validator actually rejects, so "invalid" truly means invalid.
 */
const invalidWhatEntry: fc.Arbitrary<unknown> = fc
  .oneof(
    fc.constant(null),
    fc.constant(42),
    fc.constant("not an object"),
    fc.constant([]),
    fc.constant({}),
    // valid-ish but low > mid (ordering violation)
    fc.constant({
      condition: "x",
      measure_id: "y",
      low: 5,
      mid: 1,
      high: 10,
      t: 1,
      affected_adults: 1,
      p_low: 0.1,
      p_high: 0.2,
      ctgov_url: "https://clinicaltrials.gov/",
    }),
    // probability out of range
    fc.constant({
      condition: "x",
      measure_id: "y",
      low: 1,
      mid: 2,
      high: 3,
      t: 1,
      affected_adults: 1,
      p_low: 0,
      p_high: 0.5,
      ctgov_url: "https://clinicaltrials.gov/",
    }),
    // non-https url
    fc.constant({
      condition: "x",
      measure_id: "y",
      low: 1,
      mid: 2,
      high: 3,
      t: 1,
      affected_adults: 1,
      p_low: 0.1,
      p_high: 0.2,
      ctgov_url: "http://example.com",
    }),
    // negative / non-integer count
    fc.constant({
      condition: "x",
      measure_id: "y",
      low: 1,
      mid: 2,
      high: 3,
      t: -1,
      affected_adults: 1,
      p_low: 0.1,
      p_high: 0.2,
      ctgov_url: "https://clinicaltrials.gov/",
    })
  )
  .filter((value) => !validateWhatEntry(value));

/** A single element tagged with whether it is valid, for order-tracking. */
const taggedEntry: fc.Arbitrary<{ valid: boolean; value: unknown }> = fc.oneof(
  validWhatEntry.map((value) => ({ valid: true, value })),
  invalidWhatEntry.map((value) => ({ valid: false, value }))
);

test("loadJson omits exactly the invalid entries and preserves order", async () => {
  await fc.assert(
    fc.asyncProperty(
      // An interleaving of valid and invalid entries so order preservation is
      // meaningfully exercised.
      fc.array(taggedEntry, { minLength: 1, maxLength: 30 }),
      async (tagged) => {
        const mixed = tagged.map((t) => t.value);
        const expectedValid = tagged
          .filter((t) => t.valid)
          .map((t) => t.value as WhatEntry);
        const expectedOmitted = tagged.filter((t) => !t.valid).length;

        // Stub fetch to serve the generated mixed array; no real network I/O.
        vi.stubGlobal(
          "fetch",
          vi.fn(async () =>
            Promise.resolve({
              ok: true,
              json: async () => mixed,
            } as Response)
          )
        );

        const state = await loadJson<WhatEntry>("what.json", validateWhatEntry);

        if (expectedValid.length === 0) {
          // Every entry omitted (or none valid) -> empty state (Property 3's
          // boundary); here we only assert loadJson did not fabricate a ready
          // state with zero usable entries.
          expect(state.status).toBe("empty");
          return;
        }

        expect(state.status).toBe("ready");
        if (state.status !== "ready") return;

        // Exactly the valid subset, in original relative order.
        expect(state.data).toEqual(expectedValid);
        // Reference-identity order check: each surviving entry is the same
        // object instance that was valid, in the same sequence.
        expect(state.data).toHaveLength(expectedValid.length);
        state.data.forEach((entry, i) => {
          expect(entry).toBe(expectedValid[i]);
        });
        // omittedCount equals the number of invalid entries removed.
        expect(state.omittedCount).toBe(expectedOmitted);
      }
    ),
    { numRuns: 100 }
  );
});
