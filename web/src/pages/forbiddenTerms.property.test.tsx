// Feature: dashboard, Property 12: No rendered page copy contains a Forbidden_Term
//
// Validates: Requirements 17.1, 17.2, 17.3, 17.4
//
// For EVERY page in the app — Home (`/`), WHAT (`/what`),
// Investigate (`/investigate/:measureId`), Evidence (`/evidence/:measureId`),
// WHERE (`/where`), Method (`/method`), Build (`/build`), and the NotFound
// catch-all (`*`) — the rendered page text must contain NONE of the
// Forbidden_Terms, matched case-insensitively.
//
// Each run renders one route from the full routing table, driven by the REAL
// providers so the app's own copy (nav, footer, headings, chart/table/map
// labels, the resolved entries, the legend, the disclaimer, etc.) is what gets
// asserted. `fetch` is stubbed per file name to return GENERATED VALID data, so
// every data-backed page reaches its `ready` state and renders real copy; no
// real network request is ever made.
//
// IMPORTANT — the property is about the APP's OWN copy, not the generated data.
// Every string arbitrary is constrained to a safe alphabet (letters, digits,
// spaces, a few punctuation marks) so a generator can never inject a
// Forbidden_Term into the data and cause a false failure. FORBIDDEN_TERMS is
// imported from the real source module; it is never hard-coded here.

import { afterEach, describe, expect, test, vi } from "vitest";
import { render, cleanup, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import fc from "fast-check";

import { AppRoutes } from "../App";
import { SourcesProvider } from "../data/providers";
import { FORBIDDEN_TERMS } from "../data/forbiddenTerms";
import { EVIDENCE_LABELS } from "../data/evidenceLabels";
import type {
  WhatEntry,
  InvestigateEntry,
  EvidenceEntry,
  WhereEntry,
  LabelCount,
  Finding,
  NctRef,
} from "../data/types";

// --- safe string arbitraries ------------------------------------------------
//
// A deliberately small, "safe" alphabet. It excludes any character sequence
// that could form a Forbidden_Term, and the validators also reject contact
// data, so generated strings are always valid AND free of forbidden phrases.
// The point is that the ONLY place a forbidden term could appear in the output
// is the app's own hard-coded copy — which is exactly what we are testing.

const SAFE_WORDS = [
  "Alpha",
  "Beta",
  "Gamma",
  "Delta",
  "Omega",
  "Sigma",
  "Zeta",
  "study",
  "group",
  "record",
  "value",
  "range",
];

/** A short, safe, non-empty phrase built from safe words. */
const safePhraseArb: fc.Arbitrary<string> = fc
  .array(fc.constantFrom(...SAFE_WORDS), { minLength: 1, maxLength: 4 })
  .map((words) => words.join(" "));

// --- data generators (all VALID per the validators) -------------------------

const EVIDENCE_LABEL_VALUES = [
  EVIDENCE_LABELS.possible,
  EVIDENCE_LABELS.cannotDetermine,
] as const;

/** Distinct in-scope measure ids used across all files so routes resolve. */
const MEASURE_IDS = ["CASTHMA", "HIGHCHOL", "BPHIGH", "DIABETES"] as const;

/** 14 distinct 5-char MA county FIPS codes, matching the generated GeoJSON. */
const COUNTY_FIPS = [
  "25001",
  "25003",
  "25005",
  "25007",
  "25009",
  "25011",
  "25013",
  "25015",
  "25017",
  "25019",
  "25021",
  "25023",
  "25025",
  "25027",
] as const;

/** A valid WhatEntry with low <= mid <= high and 0 < p_low <= p_high <= 1. */
function whatEntryArb(measure_id: string): fc.Arbitrary<WhatEntry> {
  return fc
    .record({
      condition: safePhraseArb,
      low: fc.integer({ min: 0, max: 50 }),
      span1: fc.integer({ min: 0, max: 50 }),
      span2: fc.integer({ min: 0, max: 50 }),
      t: fc.nat({ max: 500 }),
      affected_adults: fc.nat({ max: 1_000_000 }),
      pA: fc.integer({ min: 1, max: 100 }),
      pB: fc.integer({ min: 1, max: 100 }),
    })
    .map((r) => {
      const low = r.low;
      const mid = low + r.span1;
      const high = mid + r.span2;
      const p_low = Math.min(r.pA, r.pB) / 100;
      const p_high = Math.max(r.pA, r.pB) / 100;
      return {
        condition: r.condition,
        measure_id,
        low,
        mid,
        high,
        t: r.t,
        affected_adults: r.affected_adults,
        p_low,
        p_high,
        ctgov_url: `https://clinicaltrials.gov/search?cond=${measure_id}`,
      };
    });
}

/** A valid non-empty LabelCount breakdown array with safe labels. */
const breakdownArb: fc.Arbitrary<LabelCount[]> = fc.array(
  fc.record({ label: safePhraseArb, count: fc.nat({ max: 1000 }) }),
  { minLength: 1, maxLength: 4 }
);

/** A valid Finding: safe text plus exactly one permitted Evidence_Label. */
const findingArb: fc.Arbitrary<Finding> = fc.record({
  text: safePhraseArb,
  label: fc.constantFrom(...EVIDENCE_LABEL_VALUES),
});

/** A valid InvestigateEntry for a given measure id. */
function investigateEntryArb(measure_id: string): fc.Arbitrary<InvestigateEntry> {
  return fc.record({
    measure_id: fc.constant(measure_id),
    condition: safePhraseArb,
    ma_studies: fc.nat({ max: 1000 }),
    us_studies: fc.nat({ max: 1000 }),
    by_overall_status: breakdownArb,
    by_study_type: breakdownArb,
    by_intervention_type: breakdownArb,
    by_phase: breakdownArb,
    findings: fc.array(findingArb, { minLength: 1, maxLength: 5 }),
  });
}

/** A valid nct_id matching ^NCT\d{8}$. */
const nctIdArb: fc.Arbitrary<string> = fc
  .integer({ min: 0, max: 99_999_999 })
  .map((n) => `NCT${String(n).padStart(8, "0")}`);

/** A valid NctRef: nct_id + a url under https://clinicaltrials.gov/. */
const nctRefArb: fc.Arbitrary<NctRef> = nctIdArb.map((nct_id) => ({
  nct_id,
  url: `https://clinicaltrials.gov/study/${nct_id}`,
}));

/** A valid EvidenceEntry for a given measure id. */
function evidenceEntryArb(measure_id: string): fc.Arbitrary<EvidenceEntry> {
  return fc.record({
    measure_id: fc.constant(measure_id),
    condition: safePhraseArb,
    ncts: fc.uniqueArray(nctRefArb, {
      minLength: 1,
      maxLength: 4,
      selector: (n) => n.nct_id,
    }),
    filters: fc.array(safePhraseArb, { minLength: 1, maxLength: 3 }),
    mapping_choices: fc.array(safePhraseArb, { minLength: 1, maxLength: 3 }),
    missing_data_notes: fc.array(safePhraseArb, { maxLength: 2 }),
  });
}

/**
 * A valid WhereEntry for a county. Roughly half the time it is in the
 * Unknown_Distance state (miles null + no verified site) so the map and table
 * exercise the explicit "unknown" rendering path.
 */
function whereEntryArb(
  measure_id: string,
  county_fips: string
): fc.Arbitrary<WhereEntry> {
  return fc
    .record({
      county: safePhraseArb,
      unknown: fc.boolean(),
      miles: fc.integer({ min: 0, max: 200 }),
      verified: fc.boolean(),
    })
    .map((r) => ({
      county_fips,
      county: r.county,
      condition: measure_id,
      measure_id,
      miles_to_nearest: r.unknown ? null : r.miles,
      has_verified_site: r.unknown ? false : r.verified,
    }));
}

/**
 * A GeoJSON FeatureCollection of 14 MA county Features whose
 * `properties.county_fips` match COUNTY_FIPS. Each geometry is a tiny valid
 * square polygon — enough for the d3-geo projection and the county paths/rows.
 */
function makeGeoJson(): unknown {
  return {
    type: "FeatureCollection",
    features: COUNTY_FIPS.map((fips, i) => ({
      type: "Feature",
      properties: { county_fips: fips },
      geometry: {
        type: "Polygon",
        coordinates: [
          [
            [-71 + i * 0.1, 42],
            [-71 + i * 0.1 + 0.05, 42],
            [-71 + i * 0.1 + 0.05, 42.05],
            [-71 + i * 0.1, 42.05],
            [-71 + i * 0.1, 42],
          ],
        ],
      },
    })),
  };
}

/** The six files' bodies, generated valid, for one property run. */
interface DataSet {
  what: WhatEntry[];
  investigate: InvestigateEntry[];
  evidence: EvidenceEntry[];
  where: WhereEntry[];
  sources: unknown;
  geojson: unknown;
}

/** Build a complete, internally consistent, valid dataset across all six files. */
const dataSetArb: fc.Arbitrary<DataSet> = fc
  .record({
    what: fc.tuple(...MEASURE_IDS.map((id) => whatEntryArb(id))),
    investigate: fc.tuple(...MEASURE_IDS.map((id) => investigateEntryArb(id))),
    evidence: fc.tuple(...MEASURE_IDS.map((id) => evidenceEntryArb(id))),
    // One Where_Entry per county for the FIRST disease (so the map has a full
    // set of 14 counties for the default selection).
    where: fc.tuple(
      ...COUNTY_FIPS.map((fips) => whereEntryArb(MEASURE_IDS[0], fips))
    ),
    sourceName1: safePhraseArb,
    sourceName2: safePhraseArb,
  })
  .map((r) => ({
    what: r.what as WhatEntry[],
    investigate: r.investigate as InvestigateEntry[],
    evidence: r.evidence as EvidenceEntry[],
    where: r.where as WhereEntry[],
    sources: {
      data_as_of: "2024-01-01",
      is_sample: true,
      sources: [
        { name: r.sourceName1, url: "https://clinicaltrials.gov/", fetched: "2024-01-01" },
        { name: r.sourceName2, url: "https://www.cdc.gov/places/", fetched: "2024-01-01" },
      ],
    },
    geojson: makeGeoJson(),
  }));

// --- fetch stub -------------------------------------------------------------

/** A Response-like object good enough for loadJson / loadSources / loadCountyBoundaries. */
function jsonResponse(body: unknown): Response {
  return { ok: true, json: async () => body } as unknown as Response;
}

/**
 * Stub `fetch` so each of the six same-origin `/data/` files returns its
 * generated valid body. Any other path rejects, which would surface as a load
 * error rather than a silent real request — no network is ever hit.
 */
function stubFetch(data: DataSet) {
  vi.stubGlobal(
    "fetch",
    vi.fn((input: string) => {
      if (input.endsWith("/data/what.json")) return Promise.resolve(jsonResponse(data.what));
      if (input.endsWith("/data/investigate.json")) return Promise.resolve(jsonResponse(data.investigate));
      if (input.endsWith("/data/evidence.json")) return Promise.resolve(jsonResponse(data.evidence));
      if (input.endsWith("/data/where.json")) return Promise.resolve(jsonResponse(data.where));
      if (input.endsWith("/data/sources.json")) return Promise.resolve(jsonResponse(data.sources));
      if (input.endsWith("/data/ma_counties.geojson")) return Promise.resolve(jsonResponse(data.geojson));
      return Promise.reject(new Error(`unexpected fetch: ${input}`));
    })
  );
}

// --- the routes to cover ----------------------------------------------------
//
// Every page in the routing table. `:measureId` routes use a generated id that
// exists in the data (so the entry resolves and real copy renders); the `*`
// route uses a nonsense path so the NotFound page renders.
const ROUTE_ARB: fc.Arbitrary<string> = fc.constantFrom(
  "/",
  "/what",
  `/investigate/${MEASURE_IDS[0]}`,
  `/evidence/${MEASURE_IDS[0]}`,
  "/where",
  "/method",
  "/build",
  "/no-such-page"
);

/** Lowercased FORBIDDEN_TERMS for case-insensitive containment checks. */
const LOWER_FORBIDDEN = FORBIDDEN_TERMS.map((t) => t.toLowerCase());

/** The first forbidden term present in `text` (case-insensitive), or undefined. */
function findForbidden(text: string): string | undefined {
  const haystack = text.toLowerCase();
  return LOWER_FORBIDDEN.find((term) => haystack.includes(term));
}

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

describe("Property 12: no rendered page copy contains a Forbidden_Term", () => {
  test("every page renders with none of FORBIDDEN_TERMS in its visible text", async () => {
    await fc.assert(
      fc.asyncProperty(dataSetArb, ROUTE_ARB, async (data, route) => {
        stubFetch(data);

        const { container } = render(
          <SourcesProvider>
            <MemoryRouter initialEntries={[route]}>
              <AppRoutes />
            </MemoryRouter>
          </SourcesProvider>
        );

        // Wait until the providers have resolved and the page has rendered past
        // its loading indicator, so we assert against the page's real copy
        // rather than the transient "Loading data…" placeholder.
        await waitFor(() => {
          const text = container.textContent ?? "";
          expect(text.includes("Loading data")).toBe(false);
          // Also require some substantive content so we never assert on an
          // empty tree.
          expect(text.trim().length).toBeGreaterThan(0);
        });

        const text = container.textContent ?? "";
        const hit = findForbidden(text);
        expect(
          hit,
          hit
            ? `route ${route} rendered copy containing the Forbidden_Term "${hit}"`
            : undefined
        ).toBeUndefined();

        cleanup();
        vi.restoreAllMocks();
      }),
      { numRuns: 100 }
    );
  });
});
