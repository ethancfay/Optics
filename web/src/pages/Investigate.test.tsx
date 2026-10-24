// Example/unit tests for the Investigate_Page (Req 7.1, 7.2, 7.3, 7.5, 7.6, 7.7).
//
// No real network: `fetch` is mocked in every test so the real
// InvestigateDataProvider resolves from an in-memory investigate.json payload.
// The page is rendered inside a MemoryRouter + Routes so the `:measureId`
// route param resolves, matching the live router shape.

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen, within } from "@testing-library/react";
import { MemoryRouter, Routes, Route } from "react-router-dom";
import Investigate from "./Investigate";
import { InvestigateDataProvider } from "../data/providers";
import { EVIDENCE_LABELS } from "../data/evidenceLabels";
import type { InvestigateEntry } from "../data/types";

/** Build a Response-like object good enough for loadJson. */
function jsonResponse(body: unknown, ok = true): Response {
  return {
    ok,
    json: async () => body,
  } as unknown as Response;
}

/** The two permitted Evidence_Label strings. */
const LABELS = [EVIDENCE_LABELS.possible, EVIDENCE_LABELS.cannotDetermine];

/**
 * A valid Investigate_Data payload with a known entry (CASTHMA). Every
 * breakdown array is non-empty and each finding carries one of the two
 * Evidence_Label values, mirroring the shipped investigate.json fixture.
 */
const CASTHMA: InvestigateEntry = {
  measure_id: "CASTHMA",
  condition: "Asthma",
  ma_studies: 37,
  us_studies: 412,
  by_overall_status: [
    { label: "Recruiting", count: 37 },
    { label: "Active, not recruiting", count: 12 },
    { label: "Completed", count: 58 },
  ],
  by_study_type: [
    { label: "Interventional", count: 44 },
    { label: "Observational", count: 11 },
  ],
  by_intervention_type: [
    { label: "Drug", count: 29 },
    { label: "Device", count: 6 },
    { label: "Behavioral", count: 9 },
  ],
  by_phase: [
    { label: "Phase 2", count: 15 },
    { label: "Phase 3", count: 10 },
    { label: "Not applicable", count: 12 },
  ],
  findings: [
    {
      text: "Most recruiting studies are interventional drug trials.",
      label: EVIDENCE_LABELS.possible,
    },
    {
      text: "Whether this matches demand across the state is not established here.",
      label: EVIDENCE_LABELS.cannotDetermine,
    },
  ],
};

const PAYLOAD: InvestigateEntry[] = [CASTHMA];

/**
 * Render the Investigate page for `measureId` inside the real provider (with a
 * mocked fetch) and a MemoryRouter whose route declares the `:measureId` param.
 */
function renderInvestigate(measureId: string): void {
  render(
    <MemoryRouter initialEntries={[`/investigate/${measureId}`]}>
      <InvestigateDataProvider>
        <Routes>
          <Route path="/investigate/:measureId" element={<Investigate />} />
        </Routes>
      </InvestigateDataProvider>
    </MemoryRouter>
  );
}

/** Find the breakdown table whose <caption> matches `caption`. */
function breakdownTable(caption: string): HTMLElement {
  const cap = screen.getByText(caption);
  const table = cap.closest("table");
  if (!table) throw new Error(`No table found for caption "${caption}"`);
  return table as HTMLElement;
}

beforeEach(() => {
  vi.stubGlobal("fetch", vi.fn());
});

afterEach(() => {
  vi.restoreAllMocks();
});

describe("Investigate page — known measureId (Req 7.1, 7.2, 7.3, 7.5)", () => {
  beforeEach(() => {
    (fetch as unknown as ReturnType<typeof vi.fn>).mockResolvedValue(
      jsonResponse(PAYLOAD)
    );
  });

  it("renders the condition heading once data resolves", async () => {
    renderInvestigate("CASTHMA");
    expect(
      await screen.findByRole("heading", { level: 1, name: "Asthma" })
    ).toBeInTheDocument();
  });

  it("renders all four breakdowns from their label/count pairs (Req 7.1)", async () => {
    renderInvestigate("CASTHMA");
    await screen.findByRole("heading", { level: 1, name: "Asthma" });

    const cases: Array<[string, ReadonlyArray<{ label: string; count: number }>]> = [
      ["By overall status", CASTHMA.by_overall_status],
      ["By study type", CASTHMA.by_study_type],
      ["By intervention type", CASTHMA.by_intervention_type],
      ["By phase", CASTHMA.by_phase],
    ];

    for (const [caption, items] of cases) {
      const table = breakdownTable(caption);
      for (const { label, count } of items) {
        expect(within(table).getByText(label)).toBeInTheDocument();
        expect(within(table).getByText(String(count))).toBeInTheDocument();
      }
    }
  });

  it("shows Massachusetts and United States labeled counts (Req 7.2)", async () => {
    renderInvestigate("CASTHMA");
    await screen.findByRole("heading", { level: 1, name: "Asthma" });

    const ma = screen.getByText(/Massachusetts:/).closest("li");
    const us = screen.getByText(/United States:/).closest("li");
    expect(ma).not.toBeNull();
    expect(us).not.toBeNull();
    expect(within(ma as HTMLElement).getByText(String(CASTHMA.ma_studies))).toBeInTheDocument();
    expect(within(us as HTMLElement).getByText(String(CASTHMA.us_studies))).toBeInTheDocument();
  });

  it("renders each finding WITH its Evidence_Label badge (Req 7.3)", async () => {
    renderInvestigate("CASTHMA");
    await screen.findByRole("heading", { level: 1, name: "Asthma" });

    for (const finding of CASTHMA.findings) {
      const item = screen.getByText(finding.text).closest("li");
      expect(item).not.toBeNull();
      // The badge carries the exact Evidence_Label text for this finding.
      const badge = (item as HTMLElement).querySelector(".inv-badge");
      expect(badge).not.toBeNull();
      expect(badge).toHaveTextContent(finding.label);
    }
  });

  it("renders the interventional and prevalence definitions (Req 7.5)", async () => {
    renderInvestigate("CASTHMA");
    await screen.findByRole("heading", { level: 1, name: "Asthma" });

    expect(screen.getByText(/Interventional means/i)).toBeInTheDocument();
    expect(screen.getByText(/Prevalence means/i)).toBeInTheDocument();
  });
});

describe("Investigate page — every finding carries a label (Req 7.3)", () => {
  beforeEach(() => {
    (fetch as unknown as ReturnType<typeof vi.fn>).mockResolvedValue(
      jsonResponse(PAYLOAD)
    );
  });

  it("renders exactly one badge per finding, each a permitted Evidence_Label", async () => {
    const { container } = render(
      <MemoryRouter initialEntries={["/investigate/CASTHMA"]}>
        <InvestigateDataProvider>
          <Routes>
            <Route path="/investigate/:measureId" element={<Investigate />} />
          </Routes>
        </InvestigateDataProvider>
      </MemoryRouter>
    );
    await screen.findByRole("heading", { level: 1, name: "Asthma" });

    const badges = Array.from(container.querySelectorAll(".inv-badge"));
    // One badge per finding — no finding is rendered without a label.
    expect(badges).toHaveLength(CASTHMA.findings.length);
    // Every badge text is one of the two permitted Evidence_Labels.
    for (const badge of badges) {
      expect(LABELS).toContain(badge.textContent);
    }
  });
});

describe("Investigate page — unknown measureId (Req 7.6)", () => {
  beforeEach(() => {
    (fetch as unknown as ReturnType<typeof vi.fn>).mockResolvedValue(
      jsonResponse(PAYLOAD)
    );
  });

  it("shows the not-found message with a back link to /what", async () => {
    renderInvestigate("NOT_A_REAL_ID");

    expect(
      await screen.findByRole("heading", { level: 1, name: /Disease not found/i })
    ).toBeInTheDocument();

    const backLink = screen.getByRole("link", { name: /Back to all diseases/i });
    expect(backLink).toHaveAttribute("href", "/what");
  });
});

describe("Investigate page — content safety (Req 7.7)", () => {
  beforeEach(() => {
    (fetch as unknown as ReturnType<typeof vi.fn>).mockResolvedValue(
      jsonResponse(PAYLOAD)
    );
  });

  it("renders no diagnosis, treatment, eligibility, or enrollment text", async () => {
    const { container } = render(
      <MemoryRouter initialEntries={["/investigate/CASTHMA"]}>
        <InvestigateDataProvider>
          <Routes>
            <Route path="/investigate/:measureId" element={<Investigate />} />
          </Routes>
        </InvestigateDataProvider>
      </MemoryRouter>
    );
    await screen.findByRole("heading", { level: 1, name: "Asthma" });

    const text = (container.textContent ?? "").toLowerCase();
    for (const forbidden of ["diagnos", "treatment", "eligib", "enroll"]) {
      expect(text).not.toContain(forbidden);
    }
  });
});
