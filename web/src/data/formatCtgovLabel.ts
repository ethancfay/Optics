// Pure code-to-label formatting for ClinicalTrials.gov vocabulary (Req 18.6,
// 18.7, 18.8).
//
// The sample `evidence.json` holds each study's `status`, `study_type`,
// `phases`, and `intervention_types` verbatim in ClinicalTrials.gov code form
// (e.g. "RECRUITING", "INTERVENTIONAL", "PHASE2", "NA", "DRUG") so the data
// stays a byte-for-byte copy of `pipeline/processed/studies.csv` and nothing is
// invented. The Evidence page therefore needs a presentation-time mapping that
// turns those codes into readable labels without ever mutating the data.
//
// `formatCtgovLabel` is that mapping: a pure, total function of a single code
// string. It is a lookup over the known status, study-type, phase, and
// intervention-type codes; any code not in the table is returned unchanged so a
// value the pipeline later adds is shown as-is rather than blanked (Req 18.7),
// and the function never returns an empty string for a non-empty input
// (Req 18.8). It is dependency- and side-effect-free so the page and its tests
// derive the same label for the same code deterministically.

/**
 * The fixed code -> readable-label table. Keys are the exact ClinicalTrials.gov
 * codes as they appear in `studies.csv`; values are the human-readable labels
 * shown on the Evidence page. Covers overall status, study type, phase, and
 * intervention type — the four fields the Evidence table renders.
 */
const CTGOV_LABELS: Readonly<Record<string, string>> = {
  // Overall status
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

  // Study type
  INTERVENTIONAL: "Interventional",
  OBSERVATIONAL: "Observational",
  EXPANDED_ACCESS: "Expanded access",

  // Phase
  NA: "Not applicable",
  EARLY_PHASE1: "Early Phase 1",
  PHASE1: "Phase 1",
  PHASE2: "Phase 2",
  PHASE3: "Phase 3",
  PHASE4: "Phase 4",

  // Intervention type
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

/**
 * Map one ClinicalTrials.gov code to its readable label.
 *
 * Total and pure: known codes map to their label; any other string is returned
 * unchanged. Never returns an empty string for a non-empty input (an unknown
 * code is echoed back as-is), so a rendered cell is never blanked by this
 * function (Req 18.6, 18.7, 18.8).
 *
 * @param code A single ClinicalTrials.gov code (e.g. "RECRUITING", "PHASE2").
 * @returns The readable label for a known code, otherwise `code` unchanged.
 */
export function formatCtgovLabel(code: string): string {
  return Object.prototype.hasOwnProperty.call(CTGOV_LABELS, code)
    ? CTGOV_LABELS[code]
    : code;
}
