// Feature: dashboard, Property 13: Every Evidence NCT renders as a link to a valid ClinicalTrials.gov URL
//
// Validates: Requirements 8.1
//
// For any valid Evidence_Entry, the Evidence page must render every NCT in the
// entry's `ncts` array as a link whose visible text is the `nct_id` and whose
// `href` is the NCT's `url`. Every rendered NCT href begins with
// "https://clinicaltrials.gov/" and every rendered nct_id matches ^NCT\d{8}$.
// (The last two are generator invariants, asserted here against the actual
// rendered DOM so the property holds end-to-end through the page.)
//
// The page is driven by its real providers: `fetch` is stubbed to return the
// generated Evidence_Entry (for evidence.json) and a minimal Sources_Data
// object (for sources.json, which the page reads for the "Data as of" date).
// No real network request is made. The `:measureId` route param is supplied
// via MemoryRouter and always matches the generated entry's measure_id so the
// entry resolves and its studies render.

import { afterEach, describe, expect, test, vi } from "vitest";
import { render, screen, within, cleanup } from "@testing-library/react";
import { MemoryRouter, Routes, Route } from "react-router-dom";
import fc from "fast-check";

import Evidence from "./Evidence";
import { EvidenceDataProvider, SourcesProvider } from "../data/providers";
import type { EvidenceEntry, NctRef } from "../data/types";

const NCT_PATTERN = /^NCT\d{8}$/;
const CTGOV_PREFIX = "https://clinicaltrials.gov/";

/** A valid nct_id matching ^NCT\d{8}$ built from exactly eight digits. */
const nctIdArb: fc.Arbitrary<string> = fc
  .integer({ min: 0, max: 99_999_999 })
  .map((n) => `NCT${String(n).padStart(8, "0")}`);

/**
 * A valid NctRef: nct_id matching ^NCT\d{8}$ and a url under
 * https://clinicaltrials.gov/. The url path is derived from the nct_id so the
 * generator exercises per-study distinct hrefs.
 */
const nctRefArb: fc.Arbitrary<NctRef> = nctIdArb.map((nct_id) => ({
  nct_id,
  url: `${CTGOV_PREFIX}study/${nct_id}`,
}));

/**
 * A valid Evidence_Entry with at least one NCT (so there is always a link to
 * assert on). nct_ids are de-duplicated: the page keys each <li> on nct_id, so
 * duplicate ids within one entry are not a meaningful rendering case and would
 * only create ambiguous link lookups.
 */
const evidenceEntryArb: fc.Arbitrary<EvidenceEntry> = fc
  .record({
    measure_id: fc.constantFrom("CASTHMA", "HIGHCHOL", "BPHIGH", "DIABETES"),
    condition: fc.constantFrom("Asthma", "High cholesterol", "Diabetes"),
    ncts: fc.uniqueArray(nctRefArb, {
      minLength: 1,
      maxLength: 6,
      selector: (n) => n.nct_id,
    }),
    filters: fc.array(fc.constantFrom("MA sites", "recruiting"), {
      minLength: 1,
      maxLength: 3,
    }),
    mapping_choices: fc.array(fc.constantFrom("ICD crosswalk", "condition map"), {
      minLength: 1,
      maxLength: 3,
    }),
    missing_data_notes: fc.array(fc.constantFrom("no phase data", ""), {
      maxLength: 3,
    }),
  })
  .map((e) => ({
    ...e,
    // Ensure filters/mapping_choices are non-empty strings (contract invariant).
    filters: e.filters.length > 0 ? e.filters : ["MA sites"],
    mapping_choices:
      e.mapping_choices.length > 0 ? e.mapping_choices : ["ICD crosswalk"],
  }));

/** Minimal valid Sources_Data the page reads for the "Data as of" date. */
const SOURCES_BODY = {
  data_as_of: "2024-01-01",
  is_sample: true,
  sources: [
    { name: "CDC PLACES", url: "https://www.cdc.gov/", fetched: "2024-01-01" },
  ],
};

/** A Response-like object good enough for loadJson / loadSources. */
function jsonResponse(body: unknown): Response {
  return { ok: true, json: async () => body } as unknown as Response;
}

/**
 * Stub `fetch` so evidence.json yields `[entry]` and sources.json yields the
 * minimal Sources_Data. Any other path rejects, which would surface as a load
 * error rather than a silent real request — no network is ever hit.
 */
function stubFetch(entry: EvidenceEntry) {
  vi.stubGlobal(
    "fetch",
    vi.fn((input: string) => {
      if (input.endsWith("/data/evidence.json")) {
        return Promise.resolve(jsonResponse([entry]));
      }
      if (input.endsWith("/data/sources.json")) {
        return Promise.resolve(jsonResponse(SOURCES_BODY));
      }
      return Promise.reject(new Error(`unexpected fetch: ${input}`));
    })
  );
}

afterEach(() => {
  vi.restoreAllMocks();
});

describe("Evidence page — Property 13: NCTs render as valid ClinicalTrials.gov links", () => {
  test("every nct_id renders as a link to its url under clinicaltrials.gov", async () => {
    await fc.assert(
      fc.asyncProperty(evidenceEntryArb, async (entry) => {
        stubFetch(entry);

        render(
          <MemoryRouter initialEntries={[`/evidence/${entry.measure_id}`]}>
            <EvidenceDataProvider>
              <SourcesProvider>
                <Routes>
                  <Route path="/evidence/:measureId" element={<Evidence />} />
                </Routes>
              </SourcesProvider>
            </EvidenceDataProvider>
          </MemoryRouter>
        );

        // Wait until the resolved entry's study list has rendered.
        const studiesHeading = await screen.findByRole("heading", {
          name: /contributing studies/i,
        });
        const studiesSection = studiesHeading.closest("section");
        expect(studiesSection).not.toBeNull();
        const scope = within(studiesSection as HTMLElement);

        // The rendered NCT links, scoped to the Contributing studies section.
        const links = scope.getAllByRole("link");
        expect(links).toHaveLength(entry.ncts.length);

        // Each nct_id renders as a link whose text is the nct_id and whose
        // href is the NCT's url (Req 8.1).
        for (const nct of entry.ncts) {
          const link = scope.getByRole("link", { name: nct.nct_id });
          expect(link).toHaveAttribute("href", nct.url);
        }

        // Every rendered nct link href begins with https://clinicaltrials.gov/
        // and every rendered nct_id matches ^NCT\d{8}$ (asserted on the DOM).
        for (const link of links) {
          const href = link.getAttribute("href") ?? "";
          expect(href.startsWith(CTGOV_PREFIX)).toBe(true);
          expect(NCT_PATTERN.test(link.textContent ?? "")).toBe(true);
        }

        // Clean up this iteration's render and fetch stub before the next run.
        cleanup();
        vi.restoreAllMocks();
      }),
      { numRuns: 100 }
    );
  });
});
