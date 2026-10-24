import { describe, expect, test } from "vitest";
import fc from "fast-check";

import { formatCtgovLabel } from "./formatCtgovLabel";

// Unit tests for formatCtgovLabel (Req 18.6, 18.7, 18.8).
//
// The sample evidence data carries ClinicalTrials.gov codes verbatim; the
// Evidence page humanizes them at render time with this pure function. These
// examples pin the known mappings called out in Requirement 18.6 and the
// unknown-code passthrough of Requirement 18.7.

describe("formatCtgovLabel", () => {
  // The exact mappings named in Req 18.6, plus a representative from each of
  // the four code families so a regression in any family is caught.
  test.each([
    ["RECRUITING", "Recruiting"],
    ["ACTIVE_NOT_RECRUITING", "Active, not recruiting"],
    ["PHASE2", "Phase 2"],
    ["NA", "Not applicable"],
    ["INTERVENTIONAL", "Interventional"],
    ["DRUG", "Drug"],
    ["NOT_YET_RECRUITING", "Not yet recruiting"],
    ["COMPLETED", "Completed"],
    ["OBSERVATIONAL", "Observational"],
    ["PHASE1", "Phase 1"],
    ["PHASE3", "Phase 3"],
    ["PHASE4", "Phase 4"],
    ["BIOLOGICAL", "Biological"],
    ["DEVICE", "Device"],
    ["BEHAVIORAL", "Behavioral"],
    ["PROCEDURE", "Procedure"],
  ])("maps the known code %s to %s", (code, label) => {
    expect(formatCtgovLabel(code)).toBe(label);
  });

  test("returns an unknown code unchanged (Req 18.7)", () => {
    expect(formatCtgovLabel("SOME_FUTURE_STATUS")).toBe("SOME_FUTURE_STATUS");
    expect(formatCtgovLabel("Phase 2")).toBe("Phase 2"); // already-humanized input passes through
    expect(formatCtgovLabel("recruiting")).toBe("recruiting"); // case-sensitive: lower-case is unknown
  });

  test("does not match inherited Object.prototype keys as codes", () => {
    // Guard against a naive `table[code]` lookup treating "toString",
    // "constructor", etc. as known codes; they must pass through unchanged.
    expect(formatCtgovLabel("toString")).toBe("toString");
    expect(formatCtgovLabel("constructor")).toBe("constructor");
    expect(formatCtgovLabel("hasOwnProperty")).toBe("hasOwnProperty");
  });

  test("returns the empty string unchanged for empty input", () => {
    expect(formatCtgovLabel("")).toBe("");
  });
});

// Feature: dashboard, Property 14: Code-to-label formatting is total, maps
// known codes, and passes unknown codes through
//
// Validates Requirements 18.6, 18.7, 18.8.
//
// For any string code, formatCtgovLabel returns a non-empty string whenever the
// input is non-empty; for a code in the known table it returns that code's
// readable label; and for a code not in the table it returns the input
// unchanged. We mirror the known table here as an independent oracle so the
// property checks behavior rather than re-importing the implementation's map.

const KNOWN: Readonly<Record<string, string>> = {
  RECRUITING: "Recruiting",
  NOT_YET_RECRUITING: "Not yet recruiting",
  ACTIVE_NOT_RECRUITING: "Active, not recruiting",
  ENROLLING_BY_INVITATION: "Enrolling by invitation",
  COMPLETED: "Completed",
  SUSPENDED: "Suspended",
  TERMINATED: "Terminated",
  WITHDRAWN: "Withdrawn",
  WITHHELD: "Withheld",
  UNKNOWN: "Unknown status",
  AVAILABLE: "Available",
  NO_LONGER_AVAILABLE: "No longer available",
  TEMPORARILY_NOT_AVAILABLE: "Temporarily not available",
  APPROVED_FOR_MARKETING: "Approved for marketing",
  INTERVENTIONAL: "Interventional",
  OBSERVATIONAL: "Observational",
  EXPANDED_ACCESS: "Expanded access",
  NA: "Not applicable",
  EARLY_PHASE1: "Early Phase 1",
  PHASE1: "Phase 1",
  PHASE2: "Phase 2",
  PHASE3: "Phase 3",
  PHASE4: "Phase 4",
  DRUG: "Drug",
  BIOLOGICAL: "Biological",
  DEVICE: "Device",
  BEHAVIORAL: "Behavioral",
  PROCEDURE: "Procedure",
  RADIATION: "Radiation",
  DIETARY_SUPPLEMENT: "Dietary supplement",
  GENETIC: "Genetic",
  DIAGNOSTIC_TEST: "Diagnostic test",
  COMBINATION_PRODUCT: "Combination product",
  OTHER: "Other",
};

const knownCodes = Object.keys(KNOWN);

describe("Property 14: formatCtgovLabel totality and passthrough", () => {
  test("known codes map to labels, unknown codes pass through, output never empty for non-empty input", () => {
    fc.assert(
      fc.property(
        // Bias the generator toward the known codes while still covering
        // arbitrary strings so the unknown-passthrough branch is exercised.
        fc.oneof(fc.constantFrom(...knownCodes), fc.string()),
        (code) => {
          const result = formatCtgovLabel(code);
          if (Object.prototype.hasOwnProperty.call(KNOWN, code)) {
            expect(result).toBe(KNOWN[code]);
          } else {
            expect(result).toBe(code);
          }
          // Totality: a non-empty input never yields an empty label.
          if (code.length > 0) {
            expect(result.length).toBeGreaterThan(0);
          }
        },
      ),
      { numRuns: 100 },
    );
  });
});
