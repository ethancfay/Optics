// Feature: dashboard, Property 10: Runtime data requests are same-origin and confined to the data directory
//
// Validates: Requirements 1.2
//
// For any order of page views across the app's routes (`/`, `/what`,
// `/investigate/:measureId`, `/evidence/:measureId`, `/where`, `/method`,
// `/build`), every file the app fetches at runtime is requested as a relative,
// same-origin path under the Data_Directory `/data/`. We mount the app's REAL
// routing table and providers under a MemoryRouter with `fetch` MOCKED to
// record every requested path, exercise a generated sequence of page views that
// collectively touches all six data files (what.json, investigate.json,
// evidence.json, where.json, sources.json, ma_counties.geojson), then assert
// that EVERY recorded path begins with `/data/` and that NONE targets another
// origin (no `http://`, no `https://`, no `//host`, no other scheme). No real
// network request is ever made.

import { afterEach, describe, expect, test, vi } from "vitest";
import fc from "fast-check";
import { render, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";

import { AppRoutes } from "./App";
import { SourcesProvider } from "./data/providers";

// --- minimal valid bodies, routed by file name ------------------------------
//
// Each body is the minimum that makes the corresponding provider reach a
// non-throwing terminal state (ready or empty). The property under test is
// about WHERE requests go, not WHAT they return, so bodies are intentionally
// tiny — they only need to keep providers from crashing mid-render.

const WHAT_BODY = [
  {
    condition: "Asthma",
    measure_id: "CASTHMA",
    low: 1,
    mid: 2,
    high: 3,
    t: 5,
    affected_adults: 1000,
    p_low: 0.1,
    p_high: 0.2,
    ctgov_url: "https://clinicaltrials.gov/search",
  },
];

const INVESTIGATE_BODY = [
  {
    measure_id: "CASTHMA",
    condition: "Asthma",
    ma_studies: 3,
    us_studies: 10,
    by_overall_status: [{ label: "Recruiting", count: 2 }],
    by_study_type: [{ label: "Interventional", count: 2 }],
    by_intervention_type: [{ label: "Drug", count: 2 }],
    by_phase: [{ label: "Phase 2", count: 2 }],
    findings: [{ text: "A finding.", label: "possible" }],
  },
];

const EVIDENCE_BODY = [
  {
    measure_id: "CASTHMA",
    condition: "Asthma",
    ncts: [
      { nct_id: "NCT01234567", url: "https://clinicaltrials.gov/study/NCT01234567" },
    ],
    filters: ["recruiting"],
    mapping_choices: ["CASTHMA -> asthma"],
    missing_data_notes: [],
  },
];

const WHERE_BODY = [
  {
    county_fips: "25025",
    county: "Suffolk",
    condition: "Asthma",
    measure_id: "CASTHMA",
    miles_to_nearest: 4,
    has_verified_site: true,
  },
];

const SOURCES_BODY = {
  data_as_of: "2024-01-01",
  is_sample: true,
  sources: [
    { name: "CDC PLACES", url: "https://www.cdc.gov/", fetched: "2024-01-01" },
  ],
};

const GEOJSON_BODY = {
  type: "FeatureCollection",
  features: [
    {
      type: "Feature",
      properties: { county_fips: "25025" },
      geometry: { type: "Polygon", coordinates: [[[0, 0], [1, 0], [1, 1], [0, 0]]] },
    },
  ],
};

/** Pick the right minimal body for a recorded path, by file name. */
function bodyForPath(path: string): unknown {
  if (path.endsWith("what.json")) return WHAT_BODY;
  if (path.endsWith("investigate.json")) return INVESTIGATE_BODY;
  if (path.endsWith("evidence.json")) return EVIDENCE_BODY;
  if (path.endsWith("where.json")) return WHERE_BODY;
  if (path.endsWith("sources.json")) return SOURCES_BODY;
  if (path.endsWith("ma_counties.geojson")) return GEOJSON_BODY;
  // Any unexpected path still resolves so a failed load never masks the real
  // assertion, which is about the path itself.
  return [];
}

/**
 * A route a page view can navigate to. Every entry is one of the app's declared
 * routes; the two id'd routes use a measure_id present in the sample bodies.
 */
const ROUTES = [
  "/",
  "/what",
  "/investigate/CASTHMA",
  "/evidence/CASTHMA",
  "/where",
  "/method",
  "/build",
] as const;

/**
 * True when `path` is a relative, same-origin path under `/data/`. We reject
 * anything carrying a scheme (`http:`, `https:`, `file:`, ...), a
 * protocol-relative `//host` prefix, or that does not start at the `/data/`
 * directory. A bare relative path under `/data/` resolves against the page's
 * own origin, so it can never leave the Dashboard's origin (Req 1.2).
 */
function isSameOriginDataPath(path: string): boolean {
  if (typeof path !== "string") return false;
  // No URL scheme (http://, https://, data:, file:, ...).
  if (/^[a-z][a-z0-9+.-]*:/i.test(path)) return false;
  // No protocol-relative absolute URL (//otherhost/...).
  if (path.startsWith("//")) return false;
  // Must be rooted at the same-origin Data_Directory.
  return path.startsWith("/data/");
}

/** Pull the request path out of a fetch() first argument (string or Request). */
function pathFromFetchArg(input: unknown): string {
  if (typeof input === "string") return input;
  if (input instanceof URL) return input.toString();
  if (input && typeof input === "object" && "url" in input) {
    return String((input as { url: unknown }).url);
  }
  return String(input);
}

afterEach(() => {
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
});

describe("Property 10: runtime data requests are same-origin and under /data/", () => {
  test("every fetched path is a same-origin /data/ path across page-view sequences", async () => {
    await fc.assert(
      fc.asyncProperty(
        // A page-view sequence that is the full route set in a generated order.
        // Using the whole set guarantees every file-fetching route is visited,
        // so all six data files are exercised on each run while the visit order
        // still varies run to run.
        fc.shuffledSubarray([...ROUTES], {
          minLength: ROUTES.length,
          maxLength: ROUTES.length,
        }),
        async (order) => {
          const recorded: string[] = [];

          vi.stubGlobal(
            "fetch",
            vi.fn((input: unknown) => {
              const path = pathFromFetchArg(input);
              recorded.push(path);
              return Promise.resolve({
                ok: true,
                json: async () => bodyForPath(path),
              } as unknown as Response);
            })
          );

          // Render each route in the generated order. Each navigation mounts the
          // route's providers fresh (SourcesProvider wraps the whole app, as in
          // App.tsx), so every provider runs its single real fetch through the
          // mock. We mount per-route and wait for its fetches to settle so the
          // recorded list reflects actual runtime requests.
          for (const route of order) {
            const { unmount } = render(
              <SourcesProvider>
                <MemoryRouter initialEntries={[route]}>
                  <AppRoutes />
                </MemoryRouter>
              </SourcesProvider>
            );
            // Let the providers' effects fire and their mocked fetches resolve.
            await waitFor(() => {
              expect(
                (fetch as unknown as ReturnType<typeof vi.fn>).mock.calls.length
              ).toBeGreaterThan(0);
            });
            // Flush any microtasks queued by the resolved fetch bodies.
            await Promise.resolve();
            unmount();
          }

          // The sequence must have produced at least the six data-file fetches
          // (sources is fetched on every mount; the file routes add the rest).
          const touched = new Set(
            recorded.map((p) => p.replace(/^.*\/data\//, ""))
          );
          expect(touched.has("what.json")).toBe(true);
          expect(touched.has("investigate.json")).toBe(true);
          expect(touched.has("evidence.json")).toBe(true);
          expect(touched.has("where.json")).toBe(true);
          expect(touched.has("sources.json")).toBe(true);
          expect(touched.has("ma_counties.geojson")).toBe(true);

          // The core property: every recorded path is same-origin under /data/,
          // and none targets another origin.
          for (const path of recorded) {
            expect(isSameOriginDataPath(path)).toBe(true);
            expect(path.startsWith("http://")).toBe(false);
            expect(path.startsWith("https://")).toBe(false);
            expect(path.startsWith("//")).toBe(false);
          }
        }
      ),
      { numRuns: 100 }
    );
  });
});
