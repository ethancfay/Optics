// Hand-written runtime type guards for the six-file JSON contract (Req 2, 3.4, 5.9, 7.3).
//
// These guards are the single place that turns unknown parsed JSON into the
// typed contract declared in `./types`. Each guard returns a TypeScript type
// predicate (`value is T`) and enforces the bounds documented as invariants on
// the contract types:
//   - presence and primitive type of every field
//   - non-empty strings where required
//   - "https://" URL prefixes (and "https://clinicaltrials.gov/" for NCT urls)
//   - numbers >= 0; non-negative integers for count fields
//   - 0 < p <= 1 for p_low / p_high
//   - YYYY-MM-DD dates (fetched, data_as_of)
//   - ^NCT\d{8}$ for nct_id
//   - finding label in EVIDENCE_LABELS
//   - low <= mid <= high and p_low <= p_high for What entries
//   - nullable miles_to_nearest (number >= 0 or null) for Where entries
//   - rejection of any string field containing contact data (Req 2.13, 7.3)
//
// The loader (task 4) uses these to omit invalid entries rather than throw, so
// one malformed entry never blanks an entire file.

import type {
  WhatEntry,
  InvestigateEntry,
  EvidenceEntry,
  WhereEntry,
  SourceEntry,
  SourcesData,
  LabelCount,
  Finding,
  NctRef,
} from "./types";
import { EVIDENCE_LABELS } from "./evidenceLabels";
import type { EvidenceLabel } from "./evidenceLabels";
import { containsContactData } from "./contentSafety";

// --- primitive helpers -----------------------------------------------------

/** True when `v` is a plain (non-null, non-array) object we can index by key. */
function isRecord(v: unknown): v is Record<string, unknown> {
  return typeof v === "object" && v !== null && !Array.isArray(v);
}

/**
 * A string that is present, non-empty (after trimming), and free of contact
 * data (email / phone). Used for every required string field so a name, email,
 * or phone number can never slip through (Req 2.13, 7.3).
 */
function isSafeNonEmptyString(v: unknown): v is string {
  return (
    typeof v === "string" &&
    v.trim().length > 0 &&
    !containsContactData(v)
  );
}

/**
 * A string that may be empty but, if present, must be free of contact data.
 * Used for optional free-text fields such as `missing_data_notes` entries.
 */
function isSafeString(v: unknown): v is string {
  return typeof v === "string" && !containsContactData(v);
}

/** A finite number (rejects NaN and Infinity). */
function isFiniteNumber(v: unknown): v is number {
  return typeof v === "number" && Number.isFinite(v);
}

/** A finite number >= 0. */
function isNonNegativeNumber(v: unknown): v is number {
  return isFiniteNumber(v) && v >= 0;
}

/** A non-negative integer (count fields: t, affected_adults, ma_studies, ...). */
function isNonNegativeInteger(v: unknown): v is number {
  return Number.isInteger(v) && (v as number) >= 0;
}

/** A probability in (0, 1]: 0 < p <= 1 (p_low / p_high). */
function isProbability(v: unknown): v is number {
  return isFiniteNumber(v) && v > 0 && v <= 1;
}

/** True when `v` begins with the required URL prefix and carries no contact data. */
function isHttpsUrl(v: unknown, prefix: string): v is string {
  return (
    typeof v === "string" &&
    v.startsWith(prefix) &&
    !containsContactData(v)
  );
}

// YYYY-MM-DD with a real calendar date (rejects 2024-13-40 etc.).
const DATE_PATTERN = /^\d{4}-\d{2}-\d{2}$/;
function isIsoDate(v: unknown): v is string {
  if (typeof v !== "string" || !DATE_PATTERN.test(v)) {
    return false;
  }
  const [year, month, day] = v.split("-").map(Number);
  if (month < 1 || month > 12 || day < 1 || day > 31) {
    return false;
  }
  const d = new Date(Date.UTC(year, month - 1, day));
  return (
    d.getUTCFullYear() === year &&
    d.getUTCMonth() === month - 1 &&
    d.getUTCDate() === day
  );
}

const NCT_PATTERN = /^NCT\d{8}$/;
function isNctId(v: unknown): v is string {
  return typeof v === "string" && NCT_PATTERN.test(v);
}

function isEvidenceLabel(v: unknown): v is EvidenceLabel {
  return v === EVIDENCE_LABELS.possible || v === EVIDENCE_LABELS.cannotDetermine;
}

/** Validate every element of an unknown value as an array of `T`. */
function isArrayOf<T>(
  v: unknown,
  guard: (item: unknown) => item is T,
): v is T[] {
  return Array.isArray(v) && v.every(guard);
}

// --- nested shapes ---------------------------------------------------------

/** A { label, count } pair: non-empty safe label, non-negative integer count. */
export function validateLabelCount(value: unknown): value is LabelCount {
  if (!isRecord(value)) return false;
  return isSafeNonEmptyString(value.label) && isNonNegativeInteger(value.count);
}

/** A finding: non-empty safe text plus exactly one permitted Evidence_Label. */
export function validateFinding(value: unknown): value is Finding {
  if (!isRecord(value)) return false;
  return isSafeNonEmptyString(value.text) && isEvidenceLabel(value.label);
}

/** An NCT reference: nct_id matches ^NCT\d{8}$, url under clinicaltrials.gov. */
export function validateNctRef(value: unknown): value is NctRef {
  if (!isRecord(value)) return false;
  return (
    isNctId(value.nct_id) &&
    isHttpsUrl(value.url, "https://clinicaltrials.gov/")
  );
}

// --- entry validators ------------------------------------------------------

/**
 * WhatEntry (what.json): non-empty condition/measure_id, >= 0 low/mid/high with
 * low <= mid <= high, non-negative-integer t/affected_adults, 0 < p_low <= p_high <= 1,
 * and an https ctgov_url.
 */
export function validateWhatEntry(value: unknown): value is WhatEntry {
  if (!isRecord(value)) return false;
  if (!isSafeNonEmptyString(value.condition)) return false;
  if (!isSafeNonEmptyString(value.measure_id)) return false;
  if (!isNonNegativeNumber(value.low)) return false;
  if (!isNonNegativeNumber(value.mid)) return false;
  if (!isNonNegativeNumber(value.high)) return false;
  if (!(value.low <= value.mid && value.mid <= value.high)) return false;
  if (!isNonNegativeInteger(value.t)) return false;
  if (!isNonNegativeInteger(value.affected_adults)) return false;
  if (!isProbability(value.p_low)) return false;
  if (!isProbability(value.p_high)) return false;
  if (!(value.p_low <= value.p_high)) return false;
  if (!isHttpsUrl(value.ctgov_url, "https://")) return false;
  return true;
}

/**
 * InvestigateEntry (investigate.json): ids/condition present, non-negative-integer
 * ma_studies/us_studies, four LabelCount breakdown arrays, and findings each
 * carrying exactly one Evidence_Label.
 */
export function validateInvestigateEntry(
  value: unknown,
): value is InvestigateEntry {
  if (!isRecord(value)) return false;
  if (!isSafeNonEmptyString(value.measure_id)) return false;
  if (!isSafeNonEmptyString(value.condition)) return false;
  if (!isNonNegativeInteger(value.ma_studies)) return false;
  if (!isNonNegativeInteger(value.us_studies)) return false;
  if (!isArrayOf(value.by_overall_status, validateLabelCount)) return false;
  if (!isArrayOf(value.by_study_type, validateLabelCount)) return false;
  if (!isArrayOf(value.by_intervention_type, validateLabelCount)) return false;
  if (!isArrayOf(value.by_phase, validateLabelCount)) return false;
  if (!isArrayOf(value.findings, validateFinding)) return false;
  return true;
}

/**
 * EvidenceEntry (evidence.json): ids/condition present, ncts each a valid
 * ClinicalTrials.gov reference, non-empty filters/mapping_choices strings, and
 * missing_data_notes plain (possibly empty) safe strings.
 */
export function validateEvidenceEntry(value: unknown): value is EvidenceEntry {
  if (!isRecord(value)) return false;
  if (!isSafeNonEmptyString(value.measure_id)) return false;
  if (!isSafeNonEmptyString(value.condition)) return false;
  if (!isArrayOf(value.ncts, validateNctRef)) return false;
  if (!isArrayOf(value.filters, isSafeNonEmptyString)) return false;
  if (!isArrayOf(value.mapping_choices, isSafeNonEmptyString)) return false;
  if (!isArrayOf(value.missing_data_notes, isSafeString)) return false;
  return true;
}

/**
 * WhereEntry (where.json): fips/county/condition/measure_id present,
 * miles_to_nearest is either a number >= 0 or null (Unknown_Distance), and
 * has_verified_site is a boolean.
 */
export function validateWhereEntry(value: unknown): value is WhereEntry {
  if (!isRecord(value)) return false;
  if (!isSafeNonEmptyString(value.county_fips)) return false;
  if (!isSafeNonEmptyString(value.county)) return false;
  if (!isSafeNonEmptyString(value.condition)) return false;
  if (!isSafeNonEmptyString(value.measure_id)) return false;
  if (!(value.miles_to_nearest === null || isNonNegativeNumber(value.miles_to_nearest)))
    return false;
  if (typeof value.has_verified_site !== "boolean") return false;
  return true;
}

/**
 * SourceEntry (sources.json entries): non-empty safe name, https url, and a
 * YYYY-MM-DD fetched date.
 */
export function validateSourceEntry(value: unknown): value is SourceEntry {
  if (!isRecord(value)) return false;
  if (!isSafeNonEmptyString(value.name)) return false;
  if (!isHttpsUrl(value.url, "https://")) return false;
  if (!isIsoDate(value.fetched)) return false;
  return true;
}

/**
 * SourcesData (sources.json top-level object): a YYYY-MM-DD data_as_of, an
 * optional boolean is_sample, and an array of valid SourceEntry items.
 */
export function validateSourcesData(value: unknown): value is SourcesData {
  if (!isRecord(value)) return false;
  if (!isIsoDate(value.data_as_of)) return false;
  if (value.is_sample !== undefined && typeof value.is_sample !== "boolean")
    return false;
  if (!isArrayOf(value.sources, validateSourceEntry)) return false;
  return true;
}
