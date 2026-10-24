// Unit tests for noInterventionCount (Flag F1, Req 16.1, 16.3).
//
// No_Intervention_Count is the number of Evidence_Data `ncts` whose
// `intervention_types` array is empty. These example tests cover the empty
// `ncts` case, the all-empty `intervention_types` case, and a mix.

import { describe, it, expect } from "vitest";

import { noInterventionCount } from "./noInterventionCount";
import type { NctRef } from "./types";

/** A minimal valid NctRef with the given intervention_types. */
function nct(
  nct_id: string,
  intervention_types?: string[]
): NctRef {
  return {
    nct_id,
    url: `https://clinicaltrials.gov/study/${nct_id}`,
    ...(intervention_types === undefined ? {} : { intervention_types }),
  };
}

describe("noInterventionCount (Req 16.1)", () => {
  it("returns 0 for an empty ncts list", () => {
    expect(noInterventionCount([])).toBe(0);
  });

  it("counts every ref when all intervention_types arrays are empty", () => {
    const ncts: NctRef[] = [
      nct("NCT00000001", []),
      nct("NCT00000002", []),
      nct("NCT00000003", []),
    ];
    expect(noInterventionCount(ncts)).toBe(ncts.length);
  });

  it("counts a ref whose intervention_types key is absent as having none", () => {
    const ncts: NctRef[] = [nct("NCT00000001"), nct("NCT00000002")];
    expect(noInterventionCount(ncts)).toBe(2);
  });

  it("counts only the refs with no listed intervention type in a mix", () => {
    const ncts: NctRef[] = [
      nct("NCT00000001", ["Drug"]),
      nct("NCT00000002", []),
      nct("NCT00000003", ["Device", "Behavioral"]),
      nct("NCT00000004"),
    ];
    // Two refs (2 and 4) list no intervention type.
    expect(noInterventionCount(ncts)).toBe(2);
  });

  it("returns 0 when every ref lists at least one intervention type", () => {
    const ncts: NctRef[] = [
      nct("NCT00000001", ["Drug"]),
      nct("NCT00000002", ["Biological"]),
    ];
    expect(noInterventionCount(ncts)).toBe(0);
  });

  it("is always between 0 and ncts.length", () => {
    const ncts: NctRef[] = [
      nct("NCT00000001", ["Drug"]),
      nct("NCT00000002", []),
    ];
    const result = noInterventionCount(ncts);
    expect(result).toBeGreaterThanOrEqual(0);
    expect(result).toBeLessThanOrEqual(ncts.length);
  });
});
