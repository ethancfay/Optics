// Example/unit tests for the Evidence_Page (Req 8.2, 8.3, 8.4, 8.5).
//
// No real network: `fetch` is mocked per-file (routed by request path) in every
// test so nothing ever leaves the test process. The page reads TWO files through
// its providers — `evidence.json` via EvidenceDataProvider and `sources.json`
// via SourcesProvider — so the mock answers both `/data/evidence.json` and
// `/data/sources.json`. The route is driven with a MemoryRouter so the
// `:measureId` param resolves exactly as it would in the running app.

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor, within } from "@testing-library/react";
import { MemoryRouter, Routes, Route } from "react-router-dom";
import Evidence from "./Evidence";
import { EvidenceDataProvider, SourcesProvider } from "../data/providers";
import type { EvidenceEntry, SourcesData } from "../data/types";

/** Build a Response-like object good enough for loadJson / loadSources. */
function jsonResponse(body: unknown, ok = true): Response {
  return {
    ok,
    json: async () => body,
  } as unknown as Response;
}

const DATA_AS_OF = "2024-06-01";

const sources: SourcesData = {
  data_as_of: DATA_AS_OF,
  is_sample: true,
  sources: [
    { name: "ClinicalTrials.gov", url: "https://clinicaltrials.gov/", fetched: "2024-05-28" },
  ],
};

/** A known Evidence_Entry with two NCTs and non-empty provenance lists. */
const asthma: EvidenceEntry = {
  measure_id: "CASTHMA",
  condition: "Asthma",
  ncts: [
    { nct_id: "NCT04123456", url: "https://clinicaltrials.gov/study/NCT04123456" },
    { nct_id: "NCT05234567", url: "https://clinicaltrials.gov/study/NCT05234567" },
  ],
  filters: ["Recruiting status only", "Located in Massachusetts"],
  mapping_choices: ["CDC PLACES measure CASTHMA mapped to asthma condition terms"],
  missing_data_notes: ["Trials without a recorded Massachusetts site are excluded."],
};

/** A known Evidence_Entry with NO contributing studies (empty `ncts`). */
const noStudies: EvidenceEntry = {
  measure_id: "DEPRESSION",
  condition: "Depression",
  ncts: [],
  filters: ["Recruiting status only"],
  mapping_choices: ["Behavioral and drug interventions both included"],
  missing_data_notes: ["Broader mental-health terms are not counted."],
};

/**
 * Route `fetch` by request path to the right fixture so the two providers each
 * resolve independently. Any unexpected path rejects, surfacing accidental
 * extra requests as test failures.
 */
function mockFetchByPath(evidence: EvidenceEntry[]) {
  vi.stubGlobal(
    "fetch",
    vi.fn((input: string) => {
      if (input === "/data/evidence.json") {
        return Promise.resolve(jsonResponse(evidence));
      }
      if (input === "/data/sources.json") {
        return Promise.resolve(jsonResponse(sources));
      }
      return Promise.reject(new Error(`unexpected fetch: ${input}`));
    })
  );
}

/** Render the Evidence page at a given measureId URL, wired with both providers. */
function renderAt(measureId: string) {
  return render(
    <MemoryRouter initialEntries={[`/evidence/${measureId}`]}>
      <EvidenceDataProvider>
        <SourcesProvider>
          <Routes>
            <Route path="/evidence/:measureId" element={<Evidence />} />
            <Route path="/what" element={<div>WHAT view</div>} />
          </Routes>
        </SourcesProvider>
      </EvidenceDataProvider>
    </MemoryRouter>
  );
}

afterEach(() => {
  vi.restoreAllMocks();
});

describe("Evidence page — known measureId (Req 8.2, 8.3)", () => {
  beforeEach(() => {
    mockFetchByPath([asthma, noStudies]);
  });

  it("lists each NCT as a new-tab link to its url (Req 8.2)", async () => {
    renderAt("CASTHMA");

    // Wait for the resolved entry to render.
    await screen.findByText("Asthma");

    for (const nct of asthma.ncts) {
      const link = screen.getByRole("link", { name: nct.nct_id });
      expect(link).toHaveAttribute("href", nct.url);
      expect(link).toHaveAttribute("target", "_blank");
      expect(link).toHaveAttribute("rel", "noopener noreferrer");
    }
  });

  it("shows filters, mapping_choices, and missing_data_notes (Req 8.2)", async () => {
    renderAt("CASTHMA");
    await screen.findByText("Asthma");

    for (const item of [
      ...asthma.filters,
      ...asthma.mapping_choices,
      ...asthma.missing_data_notes,
    ]) {
      expect(screen.getByText(item)).toBeInTheDocument();
    }
  });

  it("shows the 'Data as of' value from Sources_Data (Req 8.3)", async () => {
    renderAt("CASTHMA");
    await screen.findByText("Asthma");

    await waitFor(() =>
      expect(screen.getByText(`Data as of ${DATA_AS_OF}`)).toBeInTheDocument()
    );
  });
});

describe("Evidence page — empty ncts (Req 8.4)", () => {
  beforeEach(() => {
    mockFetchByPath([asthma, noStudies]);
  });

  it("shows the no-studies message and renders NO link (no broken link)", async () => {
    renderAt("DEPRESSION");
    await screen.findByText("Depression");

    expect(
      screen.getByText("No contributing studies are available.")
    ).toBeInTheDocument();

    // No NCT link is rendered inside the contributing-studies section, so there
    // is never a broken/empty link (Req 8.4).
    const studiesHeading = screen.getByRole("heading", {
      name: "Contributing studies",
    });
    const studiesSection = studiesHeading.closest("section");
    expect(studiesSection).not.toBeNull();
    expect(
      within(studiesSection as HTMLElement).queryByRole("link")
    ).toBeNull();
  });
});

describe("Evidence page — unknown measureId (Req 8.5)", () => {
  beforeEach(() => {
    mockFetchByPath([asthma, noStudies]);
  });

  it("shows the not-found message and a back link to /what", async () => {
    renderAt("DOES_NOT_EXIST");

    expect(await screen.findByText("Disease not found.")).toBeInTheDocument();

    const backLink = screen.getByRole("link", { name: /back to all diseases/i });
    expect(backLink).toHaveAttribute("href", "/what");
  });
});
