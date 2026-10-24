// Feature: dashboard, Property 15: The Investigate headline count equals the WHAT `t` for the same disease
//
// Validates: Requirements 7.2, 19.3, 19.5
//
// For any generated What_Data / Investigate_Data pair and any measure_id in the
// Investigate_Data, the headline rendered on the Investigate page equals the
// `t` of the What_Entry with that measure_id, or "unknown" when What_Data has
// no such entry. `t`, `ma_studies`, and `us_studies` are drawn independently,
// so a page that read the headline from investigate.json would fail.

import { describe, expect, test, vi } from "vitest";
import fc from "fast-check";
import { render } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";

import { EVIDENCE_LABELS } from "../data/evidenceLabels";
import type { InvestigateEntry, LoadState, WhatEntry } from "../data/types";

// Mock both provider hooks so no fetch happens; re-pointed per run.
const useInvestigateDataMock = vi.fn<() => LoadState<InvestigateEntry[]>>();
const useWhatDataMock = vi.fn<() => LoadState<WhatEntry[]>>();
vi.mock("../data/providers", () => ({
  useInvestigateData: () => useInvestigateDataMock(),
  useWhatData: () => useWhatDataMock(),
}));

// Import AFTER the mock is registered.
import Investigate from "./Investigate";

const MEASURE_IDS = ["CASTHMA", "HIGHCHOL", "BPHIGH", "DIABETES", "DEPRESSION"] as const;

const whatEntryArb = (measure_id: string): fc.Arbitrary<WhatEntry> =>
  fc
    .record({
      t: fc.nat({ max: 5000 }),
      year: fc.option(fc.constantFrom("2022", "2023"), { nil: undefined }),
    })
    .map(({ t, year }) => ({
      condition: measure_id,
      measure_id,
      low: 1,
      mid: 2,
      high: 3,
      t,
      affected_adults: 1000,
      p_low: 0.1,
      p_high: 0.2,
      ...(year === undefined ? {} : { prevalence_year: year }),
      ctgov_url: "https://clinicaltrials.gov/",
    }));

const investigateEntryArb = (measure_id: string): fc.Arbitrary<InvestigateEntry> =>
  fc
    .record({
      ma_studies: fc.nat({ max: 5000 }),
      us_studies: fc.option(fc.nat({ max: 50000 }), { nil: null }),
    })
    .map(({ ma_studies, us_studies }) => ({
      measure_id,
      condition: measure_id,
      ma_studies,
      us_studies,
      by_overall_status: [{ label: "Recruiting", count: 1 }],
      by_study_type: [{ label: "Interventional", count: 1 }],
      by_intervention_type: [{ label: "Drug", count: 1 }],
      by_phase: [{ label: "Phase 2", count: 1 }],
      findings: [{ text: "A finding.", label: EVIDENCE_LABELS.possible }],
    }));

/** Distinct measure_id subsets for each file, plus one id to open. */
const scenarioArb = fc
  .record({
    whatIds: fc.subarray([...MEASURE_IDS]),
    invIds: fc.subarray([...MEASURE_IDS], { minLength: 1 }),
  })
  .chain(({ whatIds, invIds }) =>
    fc.record({
      what: fc.tuple(...whatIds.map(whatEntryArb)),
      investigate: fc.tuple(...invIds.map(investigateEntryArb)),
      openId: fc.constantFrom(...invIds),
    })
  );

describe("Property 15: Investigate headline equals what.t for the measure_id", () => {
  test("headline renders what.t (or 'unknown'), never ma_studies", () => {
    fc.assert(
      fc.property(scenarioArb, ({ what, investigate, openId }) => {
        useWhatDataMock.mockReturnValue(
          what.length === 0
            ? { status: "empty" }
            : { status: "ready", data: what, omittedCount: 0, isSample: false }
        );
        useInvestigateDataMock.mockReturnValue({
          status: "ready",
          data: investigate,
          omittedCount: 0,
          isSample: false,
        });

        const { container, unmount } = render(
          <MemoryRouter initialEntries={[`/investigate/${openId}`]}>
            <Routes>
              <Route path="/investigate/:measureId" element={<Investigate />} />
            </Routes>
          </MemoryRouter>
        );
        try {
          const value = container.querySelector(".inv-count-headline .inv-headline-value");
          expect(value).not.toBeNull();
          const match = what.find((w) => w.measure_id === openId);
          expect(value!.textContent).toBe(match ? String(match.t) : "unknown");
        } finally {
          unmount();
        }
      }),
      { numRuns: 100 }
    );
  });
});
