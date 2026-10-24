// Single source of truth for the two permitted finding (Evidence_Label) strings.
// Consumed by the Finding type, validators, and page/test code so they all agree
// on the exact spelling (Req 2.2, 7.3, 2.13).

export const EVIDENCE_LABELS = {
  possible: "possible explanation from available records",
  cannotDetermine: "cannot determine from public data",
} as const;

/**
 * The union of the two permitted Evidence_Label strings:
 * "possible explanation from available records" | "cannot determine from public data".
 */
export type EvidenceLabel = (typeof EVIDENCE_LABELS)[keyof typeof EVIDENCE_LABELS];
