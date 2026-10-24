// TypeScript types encoding the exact six-file JSON contract (Req 2).
//
// These are type declarations only — no runtime validation lives here.
// The hand-written type guards that enforce the bounds documented in the
// comments below (so invalid entries are omitted) are implemented in the
// validators module (task 3). The invariant comments on each field exist as
// documentation of what those validators enforce.

// The two permitted finding labels (Req 2.2, 7.3).
// `EvidenceLabel` is defined in `./evidenceLabels` as the single source of
// truth so findings and validators agree on the exact spelling. We import the
// type here and re-export it so consumers of the data contract can reference it
// from this module. (evidenceLabels.ts is created in a sibling task; writing
// the import before that file exists is intentional.)
import type { EvidenceLabel } from "./evidenceLabels";
export type { EvidenceLabel };

// what.json — JSON array of WhatEntry (Req 2.1)
export interface WhatEntry {
  condition: string; // non-empty
  measure_id: string; // non-empty; stable id used in routes/links
  low: number; // >= 0
  mid: number; // >= 0; invariant: low <= mid <= high
  high: number; // >= 0
  t: number; // non-negative integer distinct study count
  affected_adults: number; // non-negative integer (adults 18+)
  p_low: number; // > 0 and <= 1; invariant: p_low <= p_high
  p_high: number; // > 0 and <= 1
  ctgov_url: string; // begins with "https://"
}

// investigate.json — JSON array of InvestigateEntry (Req 2.2)
export interface LabelCount {
  label: string; // non-empty
  count: number; // non-negative integer
}

export interface Finding {
  text: string; // non-empty
  label: EvidenceLabel; // exactly one of the two Evidence_Label strings
}

export interface InvestigateEntry {
  measure_id: string; // non-empty
  condition: string; // non-empty
  ma_studies: number; // non-negative integer
  us_studies: number; // non-negative integer
  by_overall_status: LabelCount[];
  by_study_type: LabelCount[];
  by_intervention_type: LabelCount[];
  by_phase: LabelCount[];
  findings: Finding[];
}

// evidence.json — JSON array of EvidenceEntry (Req 2.3)
export interface NctRef {
  nct_id: string; // matches ^NCT\d{8}$
  url: string; // begins with "https://clinicaltrials.gov/"
}

export interface EvidenceEntry {
  measure_id: string; // non-empty
  condition: string; // non-empty
  ncts: NctRef[];
  filters: string[]; // non-empty strings
  mapping_choices: string[]; // non-empty strings
  missing_data_notes: string[]; // plain strings
}

// where.json — JSON array of WhereEntry (Req 2.4)
export interface WhereEntry {
  county_fips: string; // non-empty (5-char MA county FIPS)
  county: string; // non-empty
  condition: string; // non-empty
  measure_id: string; // non-empty (matches a WhatEntry measure_id)
  miles_to_nearest: number | null; // number >= 0, or null
  has_verified_site: boolean; // unknown = (miles_to_nearest === null && has_verified_site === false)
}

// sources.json — JSON object (Req 2.5)
export interface SourceEntry {
  name: string; // non-empty
  url: string; // begins with "https://"
  fetched: string; // ISO 8601 YYYY-MM-DD
}

export interface SourcesData {
  data_as_of: string; // ISO 8601 YYYY-MM-DD
  is_sample?: boolean; // true in sample fixtures (drives sample-data label, Req 2.7)
  sources: SourceEntry[];
}

// ma_counties.geojson — FeatureCollection of exactly 14 Features (Req 2.12)
//
// Minimal inline GeoJSON geometry types. If @types/geojson is available in the
// project, these can be swapped for `GeoJSON.Polygon | GeoJSON.MultiPolygon`;
// the shapes here are a compatible subset of the GeoJSON spec.
export interface GeoJsonPolygon {
  type: "Polygon";
  coordinates: number[][][];
}

export interface GeoJsonMultiPolygon {
  type: "MultiPolygon";
  coordinates: number[][][][];
}

export interface CountyFeature {
  type: "Feature";
  properties: { county_fips: string /* 5 chars, matches where.json */ };
  geometry: GeoJsonPolygon | GeoJsonMultiPolygon;
}

// Discriminated union describing the outcome of loading one JSON file.
// The data layer is the single place that turns failures into this state
// (Req 3.x). `empty` means the top-level shape was valid but every entry was
// omitted (or the array was empty); `ready` carries the surviving entries plus
// how many were omitted and whether the file is sample data.
export type LoadState<T> =
  | { status: "loading" }
  | { status: "error"; reason: "timeout" | "network" | "parse"; file: string }
  | { status: "empty" } // all entries omitted (Req 3.5) / no entries
  | { status: "ready"; data: T; omittedCount: number; isSample: boolean };
