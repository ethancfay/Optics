// Cross-file consistency checks over the SHIPPED data files in web/public/data/
// (Req 2.1, 2.5, 19.1, 19.2, 19.9). These read files from disk; no network.
//
// Feature: dashboard, Property 16: The recruiting count never exceeds the all-statuses count
// Property 16 is an invariant of the shipped data (t_ids ⊆ eligible_ids in the
// scoring-export design), so it is a data test rather than a fast-check
// generator. If it fails, fix the sample numbers, not this test (Req 19.9).

import { readFileSync } from "node:fs";
import { resolve, dirname } from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";
import type { EvidenceEntry, InvestigateEntry, SourcesData, WhatEntry } from "./types";

const HERE = dirname(fileURLToPath(import.meta.url));
const DATA_DIR = resolve(HERE, "../../public/data");
const PLACES_CSV = resolve(HERE, "../../../pipeline/processed/places_ma.csv");

function readData<T>(file: string): T {
  return JSON.parse(readFileSync(resolve(DATA_DIR, file), "utf8")) as T;
}

const what = readData<WhatEntry[]>("what.json");
const investigate = readData<InvestigateEntry[]>("investigate.json");
const evidence = readData<EvidenceEntry[]>("evidence.json");
const sources = readData<SourcesData>("sources.json");

/**
 * Distinct `year` values per `measureid` in places_ma.csv. Columns are located
 * by header name; a minimal quote-aware splitter handles quoted `measure` text.
 */
function placesYearsByMeasure(): Map<string, Set<string>> {
  const lines = readFileSync(PLACES_CSV, "utf8").split("\n").filter((l) => l.length > 0);
  const split = (line: string): string[] => {
    const cells: string[] = [];
    let cur = "";
    let quoted = false;
    for (let i = 0; i < line.length; i++) {
      const ch = line[i];
      if (quoted) {
        if (ch === '"' && line[i + 1] === '"') {
          cur += '"';
          i++;
        } else if (ch === '"') quoted = false;
        else cur += ch;
      } else if (ch === '"') quoted = true;
      else if (ch === ",") {
        cells.push(cur);
        cur = "";
      } else cur += ch;
    }
    cells.push(cur);
    return cells;
  };
  const header = split(lines[0]);
  const mi = header.indexOf("measureid");
  const yi = header.indexOf("year");
  const out = new Map<string, Set<string>>();
  for (const line of lines.slice(1)) {
    const cells = split(line);
    const set = out.get(cells[mi]) ?? new Set<string>();
    set.add(cells[yi]);
    out.set(cells[mi], set);
  }
  return out;
}

describe("Prevalence year provenance (Req 2.1, 2.5, 19.1, 19.2)", () => {
  it("each what.json prevalence_year is the single PLACES `year` for that measure", () => {
    const years = placesYearsByMeasure();
    for (const entry of what) {
      const set = years.get(entry.measure_id);
      expect(set, `no PLACES rows for ${entry.measure_id}`).toBeDefined();
      expect([...set!], `${entry.measure_id} years`).toHaveLength(1);
      expect(entry.prevalence_year, entry.measure_id).toBe([...set!][0]);
    }
  });

  it("sources.json prevalence_years mirrors what.json exactly", () => {
    const expected: Record<string, string> = {};
    for (const entry of what) {
      if (entry.prevalence_year) expected[entry.measure_id] = entry.prevalence_year;
    }
    expect(sources.prevalence_years).toEqual(expected);
  });
});

describe("Property 16: what.t <= investigate.ma_studies for every measure (Req 19.9)", () => {
  it("recruiting MA studies never exceed all fetched MA studies", () => {
    const byId = new Map(investigate.map((e) => [e.measure_id, e]));
    const violations: string[] = [];
    for (const entry of what) {
      const inv = byId.get(entry.measure_id);
      if (inv === undefined) continue;
      if (!(entry.t <= inv.ma_studies)) {
        violations.push(`${entry.measure_id}: t=${entry.t} > ma_studies=${inv.ma_studies}`);
      }
    }
    expect(violations).toEqual([]);
  });

  it("every what.json measure has an investigate.json entry to compare against", () => {
    const ids = new Set(investigate.map((e) => e.measure_id));
    expect(what.map((e) => e.measure_id).filter((id) => !ids.has(id))).toEqual([]);
  });
});

// Feature: dashboard, Property 17: Every shipped data file covers the same measure_id set
// Data test over the shipped files (Req 2.8-2.10, 20.1). Fix the data, not this test.
describe("Property 17: shipped files cover exactly the same measure_id set (Req 20.1)", () => {
  const IN_SCOPE = ["CASTHMA", "DIABETES", "HIGHCHOL"];
  const sets: Record<string, string[]> = {
    "what.json": what.map((e) => e.measure_id),
    "investigate.json": investigate.map((e) => e.measure_id),
    "evidence.json": evidence.map((e) => e.measure_id),
    "sources.json prevalence_years": Object.keys(sources.prevalence_years ?? {}),
  };

  for (const [file, ids] of Object.entries(sets)) {
    it(`${file} has no duplicate measure_id`, () => {
      expect(new Set(ids).size).toBe(ids.length);
    });
    it(`${file} has exactly {CASTHMA, DIABETES, HIGHCHOL}`, () => {
      expect([...ids].sort()).toEqual(IN_SCOPE);
    });
  }
});

// Feature: dashboard, Property 18: Study-type and status breakdowns sum to ma_studies
// Data test over the shipped files (Req 20.2). Fix the data, not this test.
describe("Property 18: by_study_type and by_overall_status sum to ma_studies (Req 20.2)", () => {
  const sum = (items: { count: number }[]) => items.reduce((acc, i) => acc + i.count, 0);

  it("by_study_type sums to ma_studies for every disease", () => {
    const violations = investigate
      .filter((e) => sum(e.by_study_type) !== e.ma_studies)
      .map((e) => `${e.measure_id}: by_study_type=${sum(e.by_study_type)} ma_studies=${e.ma_studies}`);
    expect(violations).toEqual([]);
  });

  it("by_overall_status sums to ma_studies for every disease", () => {
    const violations = investigate
      .filter((e) => sum(e.by_overall_status) !== e.ma_studies)
      .map((e) => `${e.measure_id}: by_overall_status=${sum(e.by_overall_status)} ma_studies=${e.ma_studies}`);
    expect(violations).toEqual([]);
  });
});
