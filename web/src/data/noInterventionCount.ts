// Pure client-side selector for No_Intervention_Count (Flag F1, Req 16.1, 16.3).
//
// No_Intervention_Count is the number of a disease's Evidence_Data `ncts` whose
// `intervention_types` array has zero elements. It is derived on the client from
// evidence.json and is never read from any Investigate_Data field (Req 16.3) —
// investigate.json carries no such key. A study whose `intervention_types` key
// is absent (optional extra key in the contract) is treated as having no listed
// intervention type, so it counts toward No_Intervention_Count.

import type { NctRef } from "./types";

/**
 * Count the Evidence_Data `ncts` with an empty `intervention_types` array.
 *
 * A reference is counted when its `intervention_types` is missing/undefined or
 * is an array of length zero. The result is always `>= 0` and `<= ncts.length`.
 */
export function noInterventionCount(ncts: readonly NctRef[]): number {
  return ncts.filter(
    (nct) =>
      nct.intervention_types === undefined ||
      nct.intervention_types.length === 0
  ).length;
}
