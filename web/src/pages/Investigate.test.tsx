// Example/unit tests for the Investigate_Page (Req 7.1-7.7, 11.7 n/a, 19.3-19.7).
//
// No real network: `fetch` is mocked in every test and routed by path so the
// real WhatDataProvider and InvestigateDataProvider resolve from in-memory
// what.json / investigate.json payloads.
// The page is rendered inside a MemoryRouter + Routes so the `:measureId`
// route param resolves, matching the live router shape.

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor, within } from "@testing-library/react";
import { MemoryRouter, Routes, Route } from "react-router-dom";
import Investigate, {
  DRUG_COUNT_CAPTION,
  HEADLINE_LABEL,
  MA_STUDIES_LABEL,
  prevalenceYearText,
} from "./Investigate";
import { InvestigateDataProvider, WhatDataProvider } from "../data/providers";
import { EVIDENCE_LABELS } from "../data/evidenceLabels";
import type { InvestigateEntry, WhatEntry } from "../data/types";

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
 * The matching What_Entry. `t` (21) is deliberately different from
 * `ma_studies` (37) and `us_studies` (412) so a page that read the headline
 * from investigate.json would fail (Req 19.3).
 */
const WHAT_CASTHMA: WhatEntry = {
  condition: "Asthma",
  measure_id: "CASTHMA",
  low: 0.4,
  mid: 0.45,
  high: 0.5,
  t: 21,
  affected_adults: 600000,
  p_low: 0.1,
  p_high: 0.11,
  prevalence_year: "2023",
  ctgov_url: "https://clinicaltrials.gov/search?cond=Asthma&locStr=Massachusetts",
};

/**
 * Route the mocked fetch by path. `what` may be an Error to simulate a failed
 * what.json load (Req 19.6).
 */
function stubData(
  investigate: unknown = PAYLOAD,
  what: unknown | Error = [WHAT_CASTHMA]
): void {
  (fetch as unknown as ReturnType<typeof vi.fn>).mockImplementation(
    (input: string) => {
      if (input.endsWith("/data/investigate.json"))
        return Promise.resolve(jsonResponse(investigate));
      if (input.endsWith("/data/what.json"))
        return what instanceof Error
          ? Promise.reject(what)
          : Promise.resolve(jsonResponse(what));
      return Promise.reject(new Error(`unexpected fetch: ${input}`));
    }
  );
}

/**
 * Render the Investigate page for `measureId` inside the real providers (with a
 * mocked fetch) and a MemoryRouter whose route declares the `:measureId` param.
 */
function renderInvestigate(measureId: string) {
  return render(
    <MemoryRouter initialEntries={[`/investigate/${measureId}`]}>
      <WhatDataProvider>
        <InvestigateDataProvider>
          <Routes>
            <Route path="/investigate/:measureId" element={<Investigate />} />
          </Routes>
        </InvestigateDataProvider>
      </WhatDataProvider>
    </MemoryRouter>
  );
}

/** The counts list items, in rendered order. */
function countItems(container: HTMLElement): HTMLElement[] {
  return Array.from(container.querySelectorAll<HTMLElement>(".inv-counts > li"));
}

/**
 * The headline <li> once What_Data has resolved (its value span is present,
 * or an error/loading message is shown in its place).
 */
async function resolvedHeadline(container: HTMLElement): Promise<HTMLElement> {
  await waitFor(() => {
    const li = container.querySelector(".inv-count-headline");
    if (!li || !li.querySelector(".inv-headline-value, [role='alert']")) {
      throw new Error("headline not resolved yet");
    }
  });
  return container.querySelector<HTMLElement>(".inv-count-headline")!;
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
    stubData();
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

  it("shows headline t from what.json, then ma_studies, then a numeric US count (Req 7.2, 19.3, 19.4)", async () => {
    const { container } = renderInvestigate("CASTHMA");
    await screen.findByRole("heading", { level: 1, name: "Asthma" });
    const headline = await resolvedHeadline(container);

    const items = countItems(container);
    expect(items).toHaveLength(3);
    // 1. Headline: WHAT `t`, labeled, not ma_studies.
    expect(items[0]).toBe(headline);
    expect(headline).toHaveTextContent(`${HEADLINE_LABEL}: ${WHAT_CASTHMA.t}`);
    expect(within(headline).queryByText(String(CASTHMA.ma_studies))).toBeNull();
    // 2. ma_studies, labeled as all fetched statuses.
    expect(items[1]).toHaveTextContent(`${MA_STUDIES_LABEL}: ${CASTHMA.ma_studies}`);
    // 3. US row, only because us_studies is a number here.
    expect(items[2]).toHaveTextContent(`United States: ${CASTHMA.us_studies}`);
  });

  it("shows the prevalence data year directly below the prevalence definition (Req 19.7)", async () => {
    renderInvestigate("CASTHMA");
    const line = await screen.findByText(prevalenceYearText("2023"));
    expect(line).toHaveTextContent("Prevalence data year: 2023 (CDC PLACES)");
    const definition = screen.getByText(/Prevalence means/i);
    expect(definition.nextElementSibling).toBe(line);
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
    stubData();
  });

  it("renders exactly one badge per finding, each a permitted Evidence_Label", async () => {
    const { container } = renderInvestigate("CASTHMA");
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
    stubData();
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
    stubData();
  });

  it("renders no diagnosis, treatment, eligibility, or enrollment text", async () => {
    const { container } = renderInvestigate("CASTHMA");
    await screen.findByRole("heading", { level: 1, name: "Asthma" });

    const text = (container.textContent ?? "").toLowerCase();
    for (const forbidden of ["diagnos", "treatment", "eligib", "enroll"]) {
      expect(text).not.toContain(forbidden);
    }
  });
});

describe("Investigate page — us_studies is null (national comparison deferred)", () => {
  /** CASTHMA with the national comparison deferred (us_studies: null). */
  const NO_US: InvestigateEntry = { ...CASTHMA, us_studies: null };

  beforeEach(() => {
    stubData([NO_US]);
  });

  it("renders no United States row at all (Req 7.2)", async () => {
    const { container } = renderInvestigate("CASTHMA");
    await screen.findByRole("heading", { level: 1, name: "Asthma" });
    await resolvedHeadline(container);

    // Only the headline and ma_studies rows; no US row and no placeholder.
    expect(countItems(container)).toHaveLength(2);
    expect(container.querySelector(".inv-count-us")).toBeNull();
    expect(screen.queryByText(/United States/)).toBeNull();
    expect(screen.queryByText(/National comparison/i)).toBeNull();
  });
});

describe("Investigate page — headline when What_Data lacks the disease (Req 19.5, 19.7)", () => {
  it("shows 'unknown' (not 0, not ma_studies) and omits the year line", async () => {
    stubData(PAYLOAD, [{ ...WHAT_CASTHMA, measure_id: "HIGHCHOL" }]);
    const { container } = renderInvestigate("CASTHMA");
    await screen.findByRole("heading", { level: 1, name: "Asthma" });
    const headline = await resolvedHeadline(container);

    expect(within(headline).getByText("unknown")).toBeInTheDocument();
    expect(headline).not.toHaveTextContent(/\d/);
    expect(screen.queryByText(/Prevalence data year/)).toBeNull();
  });

  it("omits the year line when prevalence_year is missing but still shows t", async () => {
    const { prevalence_year: _omit, ...noYear } = WHAT_CASTHMA;
    stubData(PAYLOAD, [noYear]);
    const { container } = renderInvestigate("CASTHMA");
    await screen.findByRole("heading", { level: 1, name: "Asthma" });
    const headline = await resolvedHeadline(container);

    expect(headline).toHaveTextContent(`${HEADLINE_LABEL}: ${WHAT_CASTHMA.t}`);
    expect(screen.queryByText(/Prevalence data year/)).toBeNull();
  });
});

describe("Investigate page — what.json fails (Req 19.6)", () => {
  it("names what.json in the headline region while the breakdowns still render", async () => {
    stubData(PAYLOAD, new Error("network down"));
    const { container } = renderInvestigate("CASTHMA");
    await screen.findByRole("heading", { level: 1, name: "Asthma" });
    const headline = await resolvedHeadline(container);

    expect(within(headline).getByRole("alert")).toHaveTextContent("what.json");
    expect(container.querySelector(".inv-headline-value")).toBeNull();
    expect(screen.queryByText(/Prevalence data year/)).toBeNull();
    // Investigate_Data content is unaffected.
    expect(breakdownTable("By phase")).toBeInTheDocument();
    expect(countItems(container)[1]).toHaveTextContent(String(CASTHMA.ma_studies));
  });
});

describe("Investigate page — Drug intervention caption (Req 7.1)", () => {
  beforeEach(() => {
    stubData();
  });

  it("renders the Drug caption alongside the intervention-type breakdown", async () => {
    renderInvestigate("CASTHMA");
    await screen.findByRole("heading", { level: 1, name: "Asthma" });

    // The caption text is shown.
    const caption = screen.getByText(DRUG_COUNT_CAPTION);
    expect(caption).toBeInTheDocument();

    // It sits in the same breakdown block as the "By intervention type" table,
    // i.e. next to the Drug count — not next to another breakdown.
    const interventionTable = breakdownTable("By intervention type");
    const block = interventionTable.closest(".inv-breakdown");
    expect(block).not.toBeNull();
    expect(within(block as HTMLElement).getByText(DRUG_COUNT_CAPTION)).toBeInTheDocument();
    // Confirm the Drug row is in that same block.
    expect(within(block as HTMLElement).getByText("Drug")).toBeInTheDocument();
  });
});
