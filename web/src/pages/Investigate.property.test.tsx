// Feature: dashboard, Property 11: Every Investigate finding carries exactly one Evidence_Label
//
// Validates: Requirements 7.3
//
// For any valid Investigate_Entry, the Investigate page renders every finding
// with exactly one Evidence_Label badge: the number of rendered badges equals
// the number of findings in the entry, and each badge's text is exactly one of
// the two permitted EVIDENCE_LABELS values. No finding renders without a label,
// and no finding renders with more than one.

import { describe, expect, test, vi } from "vitest";
import fc from "fast-check";
import { render } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";

import { EVIDENCE_LABELS } from "../data/evidenceLabels";
import type {
  InvestigateEntry,
  LabelCount,
  Finding,
  LoadState,
} from "../data/types";

// Mock the Investigate provider hook so the page reads our generated entry
// instead of performing a (forbidden) real fetch. The property holds for the
// `ready` state carrying the generated entry; the mock is re-pointed per run.
const useInvestigateDataMock = vi.fn<() => LoadState<InvestigateEntry[]>>();
// The headline reads What_Data; an empty state is enough for this property.
vi.mock("../data/providers", () => ({
  useInvestigateData: () => useInvestigateDataMock(),
  useWhatData: (): LoadState<unknown[]> => ({ status: "empty" }),
}));

// Import AFTER the mock is registered so Investigate picks up the mocked hook.
import Investigate from "./Investigate";

const EVIDENCE_LABEL_VALUES = [
  EVIDENCE_LABELS.possible,
  EVIDENCE_LABELS.cannotDetermine,
] as const;

/** A minimal valid LabelCount: non-empty label, non-negative integer count. */
const labelCountArb: fc.Arbitrary<LabelCount> = fc.record({
  label: fc.string({ minLength: 1, maxLength: 12 }).filter((s) => s.trim().length > 0),
  count: fc.nat({ max: 1000 }),
});

/**
 * A minimal valid non-empty breakdown array. Labels are unique (as in the real
 * data) because the page keys breakdown rows by label; duplicates would trigger
 * React's duplicate-key warning (design "Generator hygiene", like Property 8).
 */
const breakdownArb: fc.Arbitrary<LabelCount[]> = fc.uniqueArray(labelCountArb, {
  minLength: 1,
  maxLength: 4,
  selector: (item) => item.label,
});

/** A Finding: non-empty text plus a label drawn from the two EVIDENCE_LABELS. */
const findingArb: fc.Arbitrary<Finding> = fc.record({
  text: fc.string({ minLength: 1, maxLength: 40 }).filter((s) => s.trim().length > 0),
  label: fc.constantFrom(...EVIDENCE_LABEL_VALUES),
});

/** A valid InvestigateEntry with 1+ findings and minimal valid breakdowns. */
const investigateEntryArb: fc.Arbitrary<InvestigateEntry> = fc.record({
  measure_id: fc.constantFrom("CASTHMA", "HIGHCHOL", "BPHIGH", "DIABETES"),
  condition: fc.string({ minLength: 1, maxLength: 24 }).filter((s) => s.trim().length > 0),
  ma_studies: fc.nat({ max: 1000 }),
  us_studies: fc.nat({ max: 1000 }),
  by_overall_status: breakdownArb,
  by_study_type: breakdownArb,
  by_intervention_type: breakdownArb,
  by_phase: breakdownArb,
  findings: fc.array(findingArb, { minLength: 1, maxLength: 8 }),
});

describe("Property 11: every Investigate finding carries exactly one Evidence_Label", () => {
  test("rendered badges match findings one-to-one and each is a valid label", () => {
    fc.assert(
      fc.property(investigateEntryArb, (entry) => {
        useInvestigateDataMock.mockReturnValue({
          status: "ready",
          data: [entry],
          omittedCount: 0,
          isSample: false,
        });

        const { container, unmount } = render(
          <MemoryRouter initialEntries={[`/investigate/${entry.measure_id}`]}>
            <Routes>
              <Route path="/investigate/:measureId" element={<Investigate />} />
            </Routes>
          </MemoryRouter>
        );

        try {
          // Each finding renders inside an .inv-finding list item; the label is
          // the single .inv-badge within it.
          const findingItems = Array.from(
            container.querySelectorAll(".inv-finding")
          );
          const badges = Array.from(container.querySelectorAll(".inv-badge"));

          // Exactly one badge per finding: counts match the entry's findings.
          expect(findingItems).toHaveLength(entry.findings.length);
          expect(badges).toHaveLength(entry.findings.length);

          // Every finding item contains exactly one badge (no finding without a
          // label, none with more than one).
          for (const item of findingItems) {
            const itemBadges = (item as HTMLElement).querySelectorAll(
              ".inv-badge"
            );
            expect(itemBadges).toHaveLength(1);
          }

          // Each rendered badge's text is exactly one of the two permitted
          // Evidence_Label values.
          for (const badge of badges) {
            expect(EVIDENCE_LABEL_VALUES).toContain(badge.textContent);
          }
        } finally {
          unmount();
        }
      }),
      { numRuns: 100 }
    );
  });
});
