// Feature: dashboard, Property 3: All-omitted or empty input yields the empty state
//
// Validates: Requirements 3.5, 5.7
//
// For any JSON array that is either empty, or consists entirely of values the
// per-entry validator rejects, loadJson must return the empty state
// (`{ status: "empty" }`) — never a `ready` state carrying zero usable entries,
// and never an error. `fetch` is stubbed to serve the generated array; no real
// network request is made.

import { afterEach, expect, test, vi } from "vitest";
import fc from "fast-check";

import { loadJson } from "./loadJson";
import { validateWhatEntry } from "./validators";
import type { WhatEntry } from "./types";

afterEach(() => {
  vi.unstubAllGlobals();
});

/**
 * An arbitrary producing values that `validateWhatEntry` rejects. We cover a
 * spread of violations (non-object, missing fields, ordering break,
 * out-of-range probability, non-https url, negative count) and keep only those
 * the real validator actually rejects, so "invalid" truly means invalid.
 */
const invalidWhatEntry: fc.Arbitrary<unknown> = fc
  .oneof(
    fc.constant(null),
    fc.constant(42),
    fc.constant("not an object"),
    fc.constant([]),
    fc.constant({}),
    fc.record({ condition: fc.string() }), // partial object, missing most fields
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
    // probability out of range (p_low === 0)
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

/**
 * The input space for this property: either (a) an empty array, or (b) a
 * non-empty array consisting ENTIRELY of invalid WhatEntry values. In both
 * cases the top-level shape (a JSON array) is valid, so loadJson should not
 * error — it should report the empty state.
 */
const allOmittedOrEmptyArray: fc.Arbitrary<unknown[]> = fc.oneof(
  // (a) empty array
  fc.constant([] as unknown[]),
  // (b) array of only invalid entries
  fc.array(invalidWhatEntry, { minLength: 1, maxLength: 30 })
);

test("loadJson returns the empty state for all-omitted or empty input", async () => {
  await fc.assert(
    fc.asyncProperty(allOmittedOrEmptyArray, async (payload) => {
      // Stub fetch to serve the generated array; no real network I/O.
      vi.stubGlobal(
        "fetch",
        vi.fn(async () =>
          Promise.resolve({
            ok: true,
            json: async () => payload,
          } as Response)
        )
      );

      const state = await loadJson<WhatEntry>("what.json", validateWhatEntry);

      // Top-level shape is a valid array but no entry survives validation (or
      // the array was empty): loadJson must report the empty state exactly,
      // never a ready state with zero usable entries and never an error
      // (Req 3.5, 5.7).
      expect(state).toEqual({ status: "empty" });
    }),
    { numRuns: 100 }
  );
});
