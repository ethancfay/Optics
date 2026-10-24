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
  F2_TRACEABILITY_STATEMENT,
  HEADLINE_LABEL,
  INDEX_NUMERATOR_DEFINITION,
  INTERVENTION_OVERLAP_NOTE,
  INTRO_REAL_SENTENCE,
  INTRO_SAMPLE_SENTENCE,
  MA_STUDIES_LABEL,
  NO_INTERVENTION_LABEL,
  PHASE_OVERLAP_NOTE,
  STATUS_RECRUITING_COUNT_LABEL,
  STATUS_RECRUITING_DEFINITION,
  US_STUDIES_LABEL,
  prevalenceYearText,
} from "./Investigate";
import {
  EvidenceDataProvider,
  InvestigateDataProvider,
  SourcesProvider,
  WhatDataProvider,
} from "../data/providers";
import { EVIDENCE_LABELS } from "../data/evidenceLabels";
import type { EvidenceEntry, InvestigateEntry, WhatEntry } from "../data/types";

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
 * A matching Evidence_Data entry for CASTHMA. Two of the four `ncts` have an
 * empty `intervention_types` array, so No_Intervention_Count is 2 and a page
 * that read it from Investigate_Data (which has no such key) would differ.
 */
const EVIDENCE_CASTHMA: EvidenceEntry = {
  measure_id: "CASTHMA",
  condition: "Asthma",
  ncts: [
    {
      nct_id: "NCT00000001",
      url: "https://clinicaltrials.gov/study/NCT00000001",
      intervention_types: ["Drug"],
    },
    {
      nct_id: "NCT00000002",
      url: "https://clinicaltrials.gov/study/NCT00000002",
      intervention_types: [],
    },
    {
      nct_id: "NCT00000003",
      url: "https://clinicaltrials.gov/study/NCT00000003",
      intervention_types: ["Device", "Behavioral"],
    },
    {
      nct_id: "NCT00000004",
      url: "https://clinicaltrials.gov/study/NCT00000004",
      intervention_types: [],
    },
  ],
  filters: ["Massachusetts sites"],
  mapping_choices: ["CASTHMA mapped from asthma MeSH"],
  missing_data_notes: [],
};

const EVIDENCE_PAYLOAD: EvidenceEntry[] = [EVIDENCE_CASTHMA];

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
/** A sources.json payload; `is_sample` is set per scenario (Req 20.5). */
function sourcesPayload(isSample: boolean | undefined): unknown {
  return {
    data_as_of: "2026-10-24",
    ...(isSample === undefined ? {} : { is_sample: isSample }),
    sources: [
      { name: "ClinicalTrials.gov", url: "https://clinicaltrials.gov/", fetched: "2026-10-24" },
    ],
  };
}

/**
 * `sources` controls sources.json: a payload, an Error (load fails), or the
 * string "pending" (the fetch never resolves, so Sources_Data stays loading).
 */
function stubData(
  investigate: unknown = PAYLOAD,
  what: unknown | Error = [WHAT_CASTHMA],
  sources: unknown | Error | "pending" = sourcesPayload(false),
  evidence: unknown | Error | "pending" = EVIDENCE_PAYLOAD
): void {
  (fetch as unknown as ReturnType<typeof vi.fn>).mockImplementation(
    (input: string) => {
      if (input.endsWith("/data/sources.json")) {
        if (sources === "pending") return new Promise<Response>(() => {});
        return sources instanceof Error
          ? Promise.reject(sources)
          : Promise.resolve(jsonResponse(sources));
      }
      if (input.endsWith("/data/investigate.json"))
        return Promise.resolve(jsonResponse(investigate));
      if (input.endsWith("/data/what.json"))
        return what instanceof Error
          ? Promise.reject(what)
          : Promise.resolve(jsonResponse(what));
      if (input.endsWith("/data/evidence.json")) {
        if (evidence === "pending") return new Promise<Response>(() => {});
        return evidence instanceof Error
          ? Promise.reject(evidence)
          : Promise.resolve(jsonResponse(evidence));
      }
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
    <SourcesProvider>
      <MemoryRouter initialEntries={[`/investigate/${measureId}`]}>
        <WhatDataProvider>
          <InvestigateDataProvider>
            <EvidenceDataProvider>
              <Routes>
                <Route
                  path="/investigate/:measureId"
                  element={<Investigate />}
                />
              </Routes>
            </EvidenceDataProvider>
          </InvestigateDataProvider>
        </WhatDataProvider>
      </MemoryRouter>
    </SourcesProvider>
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

  it("shows index t, then the study-level recruiting count, ma_studies, and the US value (Req 14, 19.3, 19.4)", async () => {
    const { container } = renderInvestigate("CASTHMA");
    await screen.findByRole("heading", { level: 1, name: "Asthma" });
    const headline = await resolvedHeadline(container);

    const items = countItems(container);
    expect(items).toHaveLength(4);
    // 1. Index_Numerator_T: WHAT `t`, labeled, not ma_studies.
    expect(items[0]).toBe(headline);
    expect(headline).toHaveTextContent(`${HEADLINE_LABEL}: ${WHAT_CASTHMA.t}`);
    expect(within(headline).queryByText(String(CASTHMA.ma_studies))).toBeNull();
    // 2. Status_Recruiting_Count: the study-level "Recruiting" count from
    //    by_overall_status (37), labelled distinctly from the index numerator.
    expect(items[1]).toBe(
      container.querySelector(".inv-count-status-recruiting")
    );
    expect(items[1]).toHaveTextContent(
      `${STATUS_RECRUITING_COUNT_LABEL}: ${CASTHMA.by_overall_status[0].count}`
    );
    // 3. ma_studies, labeled as all fetched statuses.
    expect(items[2]).toHaveTextContent(`${MA_STUDIES_LABEL}: ${CASTHMA.ma_studies}`);
    // 4. US row, a numeric value because us_studies is a number here.
    expect(items[3]).toHaveTextContent(`${US_STUDIES_LABEL}: ${CASTHMA.us_studies}`);
  });

  it("presents the two recruiting numbers as distinct values, never combined (Req 14.1-14.3)", async () => {
    const { container } = renderInvestigate("CASTHMA");
    await screen.findByRole("heading", { level: 1, name: "Asthma" });
    const headline = await resolvedHeadline(container);

    const statusRow = container.querySelector<HTMLElement>(
      ".inv-count-status-recruiting"
    )!;
    // Two distinct DOM nodes carry the two counts.
    expect(headline).not.toBe(statusRow);
    // Index_Numerator_T uses WHAT `t` (21); Status_Recruiting_Count uses the
    // by_overall_status "Recruiting" count (37). They differ, so a page that
    // combined or confused them would fail here.
    expect(headline).toHaveTextContent(`${HEADLINE_LABEL}: ${WHAT_CASTHMA.t}`);
    expect(statusRow).toHaveTextContent(
      `${STATUS_RECRUITING_COUNT_LABEL}: ${CASTHMA.by_overall_status[0].count}`
    );
  });

  it("shows a one-phrase definition for each recruiting number (Req 14.4)", async () => {
    const { container } = renderInvestigate("CASTHMA");
    await screen.findByRole("heading", { level: 1, name: "Asthma" });
    await resolvedHeadline(container);

    const headline = container.querySelector<HTMLElement>(
      ".inv-count-headline"
    )!;
    const statusRow = container.querySelector<HTMLElement>(
      ".inv-count-status-recruiting"
    )!;
    expect(
      within(headline).getByText(INDEX_NUMERATOR_DEFINITION)
    ).toBeInTheDocument();
    expect(
      within(statusRow).getByText(STATUS_RECRUITING_DEFINITION)
    ).toBeInTheDocument();
  });

  it("renders the F2 traceability statement next to Index_Numerator_T and no 'list those studies' control (Req 17.1, 17.2)", async () => {
    const { container } = renderInvestigate("CASTHMA");
    await screen.findByRole("heading", { level: 1, name: "Asthma" });
    await resolvedHeadline(container);

    const headline = container.querySelector<HTMLElement>(
      ".inv-count-headline"
    )!;
    // The statement sits within the Index_Numerator_T row.
    expect(
      within(headline).getByText(F2_TRACEABILITY_STATEMENT)
    ).toBeInTheDocument();
    // No link/button claims to list exactly the studies composing the index.
    for (const control of [
      ...screen.queryAllByRole("link"),
      ...screen.queryAllByRole("button"),
    ]) {
      expect(control.textContent ?? "").not.toMatch(
        /list .*studies.*(in the index|used in the index|that make up)/i
      );
    }
  });

  it("renders the Study Counts and Studies Breakdown card titles (Req 13.1, 13.2)", async () => {
    renderInvestigate("CASTHMA");
    await screen.findByRole("heading", { level: 1, name: "Asthma" });

    expect(
      screen.getByRole("heading", { name: "Study Counts" })
    ).toBeInTheDocument();
    expect(
      screen.getByRole("heading", { name: "Studies Breakdown" })
    ).toBeInTheDocument();
  });

  it("renders the intervention-type panel exactly once (Req 13.3)", async () => {
    renderInvestigate("CASTHMA");
    await screen.findByRole("heading", { level: 1, name: "Asthma" });

    expect(screen.getAllByText("By intervention type")).toHaveLength(1);
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

describe("Investigate page — us_studies is null (national comparison deferred, Req 18.1)", () => {
  /** CASTHMA with the national comparison deferred (us_studies: null). */
  const NO_US: InvestigateEntry = { ...CASTHMA, us_studies: null };

  beforeEach(() => {
    stubData([NO_US]);
  });

  it("renders the US row with the literal 'unknown' (never 0 or a fabricated value)", async () => {
    const { container } = renderInvestigate("CASTHMA");
    await screen.findByRole("heading", { level: 1, name: "Asthma" });
    await resolvedHeadline(container);

    const usRow = container.querySelector<HTMLElement>(".inv-count-us");
    expect(usRow).not.toBeNull();
    expect(usRow).toHaveTextContent(`${US_STUDIES_LABEL}: unknown`);
    // No fabricated numeric US value when us_studies is null (Req 18.2).
    expect(within(usRow as HTMLElement).queryByText("0")).toBeNull();
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

describe("Investigate page — empty breakdown arrays (Req 13.6)", () => {
  /** CASTHMA with an empty by_phase array to exercise the no-categories path. */
  const NO_PHASES: InvestigateEntry = { ...CASTHMA, by_phase: [] };

  beforeEach(() => {
    stubData([NO_PHASES]);
  });

  it("renders a no-categories message in an empty breakdown panel", async () => {
    renderInvestigate("CASTHMA");
    await screen.findByRole("heading", { level: 1, name: "Asthma" });

    const phaseTable = breakdownTable("By phase");
    expect(
      within(phaseTable).getByText("No categories are available.")
    ).toBeInTheDocument();
    // The other panels still render their categories.
    const statusTable = breakdownTable("By overall status");
    expect(within(statusTable).getByText("Recruiting")).toBeInTheDocument();
  });
});

describe("Investigate page — Status_Recruiting_Count missing from by_overall_status (Req 1.6)", () => {
  /** CASTHMA with no "Recruiting" status label at all. */
  const NO_RECRUITING: InvestigateEntry = {
    ...CASTHMA,
    by_overall_status: [
      { label: "Active, not recruiting", count: 12 },
      { label: "Completed", count: 58 },
    ],
  };

  beforeEach(() => {
    stubData([NO_RECRUITING]);
  });

  it("renders 'unknown' for the study-level recruiting count", async () => {
    const { container } = renderInvestigate("CASTHMA");
    await screen.findByRole("heading", { level: 1, name: "Asthma" });
    await resolvedHeadline(container);

    const statusRow = container.querySelector<HTMLElement>(
      ".inv-count-status-recruiting"
    )!;
    expect(statusRow).toHaveTextContent(
      `${STATUS_RECRUITING_COUNT_LABEL}: unknown`
    );
  });
});

describe("Investigate page — intro sentence follows the sample flag (Req 20.5)", () => {
  /** The intro paragraph once the page has rendered. */
  async function intro(): Promise<HTMLElement> {
    await screen.findByRole("heading", { name: "Asthma" });
    return document.querySelector<HTMLElement>(".inv-intro")!;
  }

  it("shows the real-data sentence only when sources.json has is_sample: false", async () => {
    stubData(PAYLOAD, [WHAT_CASTHMA], sourcesPayload(false));
    renderInvestigate("CASTHMA");
    const p = await intro();
    await waitFor(() => expect(p).toHaveTextContent(INTRO_REAL_SENTENCE));
    expect(p).not.toHaveTextContent(INTRO_SAMPLE_SENTENCE);
  });

  it("shows the sample sentence when sources.json has is_sample: true", async () => {
    stubData(PAYLOAD, [WHAT_CASTHMA], sourcesPayload(true));
    renderInvestigate("CASTHMA");
    const p = await intro();
    expect(p).toHaveTextContent(INTRO_SAMPLE_SENTENCE);
    expect(p).not.toHaveTextContent(INTRO_REAL_SENTENCE);
  });

  it("shows the sample sentence while sources.json is not loaded", async () => {
    stubData(PAYLOAD, [WHAT_CASTHMA], "pending");
    renderInvestigate("CASTHMA");
    const p = await intro();
    expect(p).toHaveTextContent(INTRO_SAMPLE_SENTENCE);
    expect(p).not.toHaveTextContent(INTRO_REAL_SENTENCE);
  });

  it("shows the sample sentence when sources.json fails to load", async () => {
    stubData(PAYLOAD, [WHAT_CASTHMA], new Error("network down"));
    renderInvestigate("CASTHMA");
    const p = await intro();
    // Give the failed sources fetch time to settle; the sentence must not flip.
    await new Promise((r) => setTimeout(r, 0));
    expect(p).toHaveTextContent(INTRO_SAMPLE_SENTENCE);
    expect(p).not.toHaveTextContent(INTRO_REAL_SENTENCE);
  });
});

describe("Investigate page — intervention-type overlap note (Req 15.2)", () => {
  beforeEach(() => {
    stubData();
  });

  it("renders the overlap note inside the intervention-type panel", async () => {
    renderInvestigate("CASTHMA");
    await screen.findByRole("heading", { level: 1, name: "Asthma" });

    const note = screen.getByText(INTERVENTION_OVERLAP_NOTE);
    expect(note).toBeInTheDocument();

    // It sits in the same panel as the "By intervention type" table.
    const interventionTable = breakdownTable("By intervention type");
    const panel = interventionTable.closest(".inv-intervention-panel");
    expect(panel).not.toBeNull();
    expect(
      within(panel as HTMLElement).getByText(INTERVENTION_OVERLAP_NOTE)
    ).toBeInTheDocument();
  });
});

describe("Investigate page — No_Intervention_Count (Flag F1, Req 16.1, 16.2)", () => {
  beforeEach(() => {
    stubData();
  });

  it("shows the client-side count near the intervention-type panel", async () => {
    renderInvestigate("CASTHMA");
    await screen.findByRole("heading", { level: 1, name: "Asthma" });

    const interventionTable = breakdownTable("By intervention type");
    const panel = interventionTable.closest(
      ".inv-intervention-panel"
    ) as HTMLElement;

    // Two of EVIDENCE_CASTHMA's four ncts have empty intervention_types.
    await waitFor(() => {
      const line = panel.querySelector<HTMLElement>(".inv-no-intervention");
      expect(line).not.toBeNull();
      expect(line).toHaveTextContent(`${NO_INTERVENTION_LABEL}: 2`);
    });
  });
});

describe("Investigate page — No_Intervention_Count when evidence.json fails (Req 16.4)", () => {
  beforeEach(() => {
    stubData(PAYLOAD, [WHAT_CASTHMA], sourcesPayload(false), new Error("down"));
  });

  it("renders 'unknown' in place of the count", async () => {
    renderInvestigate("CASTHMA");
    await screen.findByRole("heading", { level: 1, name: "Asthma" });

    const interventionTable = breakdownTable("By intervention type");
    const panel = interventionTable.closest(
      ".inv-intervention-panel"
    ) as HTMLElement;

    await waitFor(() => {
      const line = panel.querySelector<HTMLElement>(".inv-no-intervention");
      expect(line).not.toBeNull();
      expect(line).toHaveTextContent(`${NO_INTERVENTION_LABEL}: unknown`);
    });
  });
});

describe("Investigate page — phase overlap note (Req 15.1)", () => {
  it("shows the phase overlap note when phase_overlap_studies > 0", async () => {
    stubData([{ ...CASTHMA, phase_overlap_studies: 4 }]);
    renderInvestigate("CASTHMA");
    await screen.findByRole("heading", { level: 1, name: "Asthma" });

    const note = screen.getByText(PHASE_OVERLAP_NOTE);
    expect(note).toBeInTheDocument();

    // It sits next to the "By phase" table.
    const phaseTable = breakdownTable("By phase");
    const panel = phaseTable.closest(".inv-phase-panel");
    expect(panel).not.toBeNull();
    expect(
      within(panel as HTMLElement).getByText(PHASE_OVERLAP_NOTE)
    ).toBeInTheDocument();
  });

  it("omits the phase overlap note when phase_overlap_studies is 0", async () => {
    stubData([{ ...CASTHMA, phase_overlap_studies: 0 }]);
    renderInvestigate("CASTHMA");
    await screen.findByRole("heading", { level: 1, name: "Asthma" });

    expect(screen.queryByText(PHASE_OVERLAP_NOTE)).toBeNull();
  });

  it("omits the phase overlap note when phase_overlap_studies is absent", async () => {
    stubData([CASTHMA]);
    renderInvestigate("CASTHMA");
    await screen.findByRole("heading", { level: 1, name: "Asthma" });

    expect(screen.queryByText(PHASE_OVERLAP_NOTE)).toBeNull();
  });
});
