// Feature: dashboard, Property 1: Schema validation accepts valid entries and rejects invalid ones
//
// Validates: Requirements 2.1, 2.2, 2.3, 2.4, 2.5, 3.4, 5.9
//
// A single fast-check property (numRuns: 100) that generates VALID entries of
// each of the five entry types (What, Investigate, Evidence, Where, Source) and
// asserts the matching validator returns true; and generates each kind of
// VIOLATION and asserts the validator returns false.

import { describe, expect, test } from "vitest";
import fc from "fast-check";
import {
  validateWhatEntry,
  validateInvestigateEntry,
  validateEvidenceEntry,
  validateWhereEntry,
  validateSourceEntry,
} from "./validators";
import { EVIDENCE_LABELS } from "./evidenceLabels";

const NUM_RUNS = 100;

// --- shared arbitraries ----------------------------------------------------

// A non-empty string that is free of email/phone contact data. Alphanumeric
// plus spaces keeps it safe for every "safe non-empty string" field.
const safeText = fc
  .stringMatching(/^[A-Za-z][A-Za-z0-9 ]{0,30}$/)
  .filter((s) => s.trim().length > 0);

// A non-negative integer suitable for count fields.
const nonNegInt = fc.integer({ min: 0, max: 1_000_000 });

// A non-negative finite number.
const nonNegNum = fc.double({ min: 0, max: 1_000_000, noNaN: true });

// A probability in (0, 1].
const probability = fc.double({
  min: 0,
  max: 1,
  noNaN: true,
  minExcluded: true, // exclude 0 so values satisfy 0 < p <= 1
});

// An https URL with no contact data.
const httpsUrl = safeText.map((s) => `https://example.org/${encodeURIComponent(s)}`);

// A ClinicalTrials.gov URL.
const ctgovUrl = safeText.map(
  (s) => `https://clinicaltrials.gov/study/${encodeURIComponent(s)}`,
);

// A valid NCT id matching ^NCT\d{8}$.
const nctId = fc
  .integer({ min: 0, max: 99_999_999 })
  .map((n) => `NCT${String(n).padStart(8, "0")}`);

// A valid YYYY-MM-DD date string (real calendar dates).
const isoDate = fc
  .date({
    min: new Date(Date.UTC(1990, 0, 1)),
    max: new Date(Date.UTC(2099, 11, 31)),
    noInvalidDate: true,
  })
  .map((d) => d.toISOString().slice(0, 10));

// Email / phone strings the content-safety guard must reject.
const contactData = fc.oneof(
  safeText.map((s) => `${s.replace(/\s/g, "")}@example.com`),
  fc.constant("call 617-555-0100 now"),
  fc.constant("(212) 555 0199"),
);

// A low <= mid <= high triple of non-negative numbers.
const sortedTriple = fc
  .tuple(nonNegNum, nonNegNum, nonNegNum)
  .map((xs) => [...xs].sort((a, b) => a - b) as [number, number, number]);

// A p_low <= p_high pair of probabilities.
const sortedProbs = fc
  .tuple(probability, probability)
  .map((xs) => [...xs].sort((a, b) => a - b) as [number, number]);

const evidenceLabel = fc.constantFrom(
  EVIDENCE_LABELS.possible,
  EVIDENCE_LABELS.cannotDetermine,
);

// --- valid entry arbitraries -----------------------------------------------

const validWhat = fc
  .record({
    condition: safeText,
    measure_id: safeText,
    triple: sortedTriple,
    t: nonNegInt,
    affected_adults: nonNegInt,
    probs: sortedProbs,
    ctgov_url: ctgovUrl,
  })
  .map(({ triple, probs, ...rest }) => ({
    ...rest,
    low: triple[0],
    mid: triple[1],
    high: triple[2],
    p_low: probs[0],
    p_high: probs[1],
  }));

const validLabelCount = fc.record({ label: safeText, count: nonNegInt });
const validFinding = fc.record({ text: safeText, label: evidenceLabel });

const validInvestigate = fc.record({
  measure_id: safeText,
  condition: safeText,
  ma_studies: nonNegInt,
  us_studies: nonNegInt,
  by_overall_status: fc.array(validLabelCount, { maxLength: 4 }),
  by_study_type: fc.array(validLabelCount, { maxLength: 4 }),
  by_intervention_type: fc.array(validLabelCount, { maxLength: 4 }),
  by_phase: fc.array(validLabelCount, { maxLength: 4 }),
  findings: fc.array(validFinding, { maxLength: 4 }),
});

const validNctRef = fc.record({ nct_id: nctId, url: ctgovUrl });

const validEvidence = fc.record({
  measure_id: safeText,
  condition: safeText,
  ncts: fc.array(validNctRef, { maxLength: 4 }),
  filters: fc.array(safeText, { maxLength: 4 }),
  mapping_choices: fc.array(safeText, { maxLength: 4 }),
  // missing_data_notes may be empty strings but must be contact-free.
  missing_data_notes: fc.array(
    fc.stringMatching(/^[A-Za-z0-9 ]{0,30}$/),
    { maxLength: 4 },
  ),
});

const validWhere = fc.record({
  county_fips: safeText,
  county: safeText,
  condition: safeText,
  measure_id: safeText,
  miles_to_nearest: fc.oneof(nonNegNum, fc.constant(null)),
  has_verified_site: fc.boolean(),
});

const validSource = fc.record({
  name: safeText,
  url: httpsUrl,
  fetched: isoDate,
});

describe("Property 1: schema validation accepts valid entries and rejects invalid ones", () => {
  test("validators return true for valid entries and false for each violation", () => {
    fc.assert(
      fc.property(
        validWhat,
        validInvestigate,
        validEvidence,
        validWhere,
        validSource,
        // selector picks which violation kind to exercise this run
        fc.integer({ min: 0, max: 13 }),
        contactData,
        safeText,
        (what, investigate, evidence, where, source, violation, contact, bad) => {
          // --- VALID: every validator accepts its well-formed entry ---------
          expect(validateWhatEntry(what)).toBe(true);
          expect(validateInvestigateEntry(investigate)).toBe(true);
          expect(validateEvidenceEntry(evidence)).toBe(true);
          expect(validateWhereEntry(where)).toBe(true);
          expect(validateSourceEntry(source)).toBe(true);

          // --- INVALID: each violation kind must be rejected ---------------
          switch (violation) {
            case 0: {
              // missing field (delete a required key on each type)
              const w = { ...what } as Record<string, unknown>;
              delete w.mid;
              expect(validateWhatEntry(w)).toBe(false);

              const i = { ...investigate } as Record<string, unknown>;
              delete i.findings;
              expect(validateInvestigateEntry(i)).toBe(false);

              const e = { ...evidence } as Record<string, unknown>;
              delete e.ncts;
              expect(validateEvidenceEntry(e)).toBe(false);

              const wh = { ...where } as Record<string, unknown>;
              delete wh.has_verified_site;
              expect(validateWhereEntry(wh)).toBe(false);

              const s = { ...source } as Record<string, unknown>;
              delete s.url;
              expect(validateSourceEntry(s)).toBe(false);
              break;
            }
            case 1: {
              // wrong type (number where string expected, and vice versa)
              expect(validateWhatEntry({ ...what, condition: 42 })).toBe(false);
              expect(
                validateInvestigateEntry({ ...investigate, ma_studies: "lots" }),
              ).toBe(false);
              expect(validateWhereEntry({ ...where, has_verified_site: "yes" })).toBe(
                false,
              );
              expect(validateSourceEntry({ ...source, name: 7 })).toBe(false);
              break;
            }
            case 2: {
              // empty string in a required string field
              expect(validateWhatEntry({ ...what, measure_id: "   " })).toBe(false);
              expect(validateInvestigateEntry({ ...investigate, condition: "" })).toBe(
                false,
              );
              expect(validateWhereEntry({ ...where, county: "" })).toBe(false);
              expect(validateSourceEntry({ ...source, name: "" })).toBe(false);
              break;
            }
            case 3: {
              // bad URL prefix (http instead of https, wrong host for NCT)
              expect(
                validateWhatEntry({ ...what, ctgov_url: "http://example.org/x" }),
              ).toBe(false);
              expect(validateSourceEntry({ ...source, url: "ftp://example.org" })).toBe(
                false,
              );
              expect(
                validateEvidenceEntry({
                  ...evidence,
                  ncts: [{ nct_id: "NCT00000001", url: "https://example.org/x" }],
                }),
              ).toBe(false);
              break;
            }
            case 4: {
              // negative number where >= 0 is required
              expect(validateWhatEntry({ ...what, low: -1, mid: -1, high: -1 })).toBe(
                false,
              );
              expect(
                validateWhereEntry({ ...where, miles_to_nearest: -5 }),
              ).toBe(false);
              break;
            }
            case 5: {
              // non-integer count field
              expect(validateWhatEntry({ ...what, t: 1.5 })).toBe(false);
              expect(
                validateInvestigateEntry({ ...investigate, us_studies: 2.7 }),
              ).toBe(false);
              expect(
                validateInvestigateEntry({
                  ...investigate,
                  by_phase: [{ label: "I", count: 3.5 }],
                }),
              ).toBe(false);
              break;
            }
            case 6: {
              // out-of-range probability (> 1 and <= 0)
              expect(validateWhatEntry({ ...what, p_high: 1.5 })).toBe(false);
              expect(validateWhatEntry({ ...what, p_low: 0 })).toBe(false);
              expect(validateWhatEntry({ ...what, p_low: -0.1 })).toBe(false);
              break;
            }
            case 7: {
              // malformed date
              expect(validateSourceEntry({ ...source, fetched: "2024-13-40" })).toBe(
                false,
              );
              expect(validateSourceEntry({ ...source, fetched: "01-01-2024" })).toBe(
                false,
              );
              expect(validateSourceEntry({ ...source, fetched: "not-a-date" })).toBe(
                false,
              );
              break;
            }
            case 8: {
              // bad nct_id (wrong prefix / wrong digit count)
              expect(
                validateEvidenceEntry({
                  ...evidence,
                  ncts: [
                    { nct_id: "NCT1234", url: "https://clinicaltrials.gov/study/x" },
                  ],
                }),
              ).toBe(false);
              expect(
                validateEvidenceEntry({
                  ...evidence,
                  ncts: [
                    { nct_id: "ABC12345678", url: "https://clinicaltrials.gov/study/x" },
                  ],
                }),
              ).toBe(false);
              break;
            }
            case 9: {
              // invalid finding label (not one of the two Evidence_Labels)
              expect(
                validateInvestigateEntry({
                  ...investigate,
                  findings: [{ text: "something", label: "made up label" }],
                }),
              ).toBe(false);
              break;
            }
            case 10: {
              // low <= mid <= high ordering violation (mid outside [low, high])
              const hi = what.high + 1;
              expect(validateWhatEntry({ ...what, mid: hi, high: what.high })).toBe(
                false,
              );
              // low greater than mid
              expect(
                validateWhatEntry({ ...what, low: what.high + 2, mid: what.mid }),
              ).toBe(false);
              break;
            }
            case 11: {
              // p_low > p_high ordering violation (both still in range)
              expect(
                validateWhatEntry({ ...what, p_low: 1, p_high: 0.5 }),
              ).toBe(false);
              break;
            }
            case 12: {
              // contact data in a string field
              expect(validateWhatEntry({ ...what, condition: contact })).toBe(false);
              expect(
                validateInvestigateEntry({ ...investigate, condition: contact }),
              ).toBe(false);
              expect(validateSourceEntry({ ...source, name: contact })).toBe(false);
              expect(validateWhereEntry({ ...where, county: contact })).toBe(false);
              break;
            }
            default: {
              // not an object at all
              expect(validateWhatEntry(null)).toBe(false);
              expect(validateInvestigateEntry([])).toBe(false);
              expect(validateEvidenceEntry(bad)).toBe(false);
              expect(validateWhereEntry(123)).toBe(false);
              expect(validateSourceEntry(undefined)).toBe(false);
              break;
            }
          }
        },
      ),
      { numRuns: NUM_RUNS },
    );
  });
});
