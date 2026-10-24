// App-integration unit/example tests (task 14.4).
//
// Covers four areas against the SHIPPED app and the REAL sample files under
// `web/public/data/` (read from disk here, then served through a path-routed
// `fetch` mock so NO real network request is ever made):
//
//   1. Routing (Req 14, 15.7)           — navigation without full reload, direct-URL
//                                           entry for every route incl. the two
//                                           :measureId routes, active-page indication,
//                                           and focus moving to #main on route change.
//   2. Sample fixtures (Req 2.6-2.12)   — the six real files load with ZERO omitted
//                                           entries through the real loaders/validators,
//                                           plus the per-file shape assertions.
//   3. Content safety (Req 2.13)        — no sample-file string field and no rendered
//                                           page text matches an email/phone pattern.
//   4. Accessibility / layout (Req 15,16) — chart/map <-> table aria-describedby,
//                                           keyboard-operable named controls, lowest-mid
//                                           ordering, and one fetch per data file per page.
//
// This file is intentionally separate from the per-page test files. All `fetch`
// is mocked; a test that performed real network I/O would fail (the mock rejects
// unexpected paths).

import { readFileSync } from "node:fs";
import { resolve, dirname } from "node:path";
import { fileURLToPath } from "node:url";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { AppRoutes } from "./App";
import { SourcesProvider } from "./data/providers";
import {
  validateWhatEntry,
  validateInvestigateEntry,
  validateEvidenceEntry,
  validateSourcesData,
} from "./data/validators";
import { loadJson, loadSources } from "./data/loadJson";
import { containsContactData } from "./data/contentSafety";
import { sortConditions } from "./data/conditions";
import { SAMPLE_DATA_LABEL } from "./components/Layout";
import type {
  WhatEntry,
  InvestigateEntry,
  EvidenceEntry,
  SourcesData,
} from "./data/types";

// --- read the REAL shipped files from disk ----------------------------------

const HERE = dirname(fileURLToPath(import.meta.url));
const DATA_DIR = resolve(HERE, "../public/data");

/** Read and parse a real shipped data file from `web/public/data`. */
function readData<T>(file: string): T {
  return JSON.parse(readFileSync(resolve(DATA_DIR, file), "utf8")) as T;
}

const whatRaw = readData<unknown[]>("what.json");
const investigateRaw = readData<unknown[]>("investigate.json");
const evidenceRaw = readData<unknown[]>("evidence.json");
const sourcesRaw = readData<unknown>("sources.json");

// The WHERE view is hidden in this version: where.json and ma_counties.geojson
// are no longer shipped or fetched, so this file no longer reads or serves them.

/** The disease whose Investigate/Evidence entries the :measureId routes use. */
const DESIGNATED_MEASURE_ID = "CASTHMA";

// --- fetch mock that serves the REAL files, routed by path -------------------

/** Build a Response-like object good enough for loadJson / loadSources. */
function jsonResponse(body: unknown): Response {
  return { ok: true, json: async () => body } as unknown as Response;
}

/**
 * Stub `fetch` to serve each real file by its `/data/...` path. Returns a
 * `calls` map counting requests per path so tests can assert one fetch per file
 * per page view (Req 16.3). Any unexpected path rejects, surfacing both stray
 * requests and accidental real-network attempts as test failures.
 */
function stubFetchWithRealFiles() {
  const calls = new Map<string, number>();
  const bodies: Record<string, unknown> = {
    "/data/what.json": whatRaw,
    "/data/investigate.json": investigateRaw,
    "/data/evidence.json": evidenceRaw,
    "/data/sources.json": sourcesRaw,
  };
  const fetchMock = vi.fn((input: string) => {
    calls.set(input, (calls.get(input) ?? 0) + 1);
    if (input in bodies) {
      return Promise.resolve(jsonResponse(bodies[input]));
    }
    return Promise.reject(new Error(`unexpected fetch: ${input}`));
  });
  vi.stubGlobal("fetch", fetchMock);
  return { calls, fetchMock };
}

/** Render the whole app (AppRoutes under Layout) at a given URL. */
function renderApp(initialPath: string) {
  return render(
    <SourcesProvider>
      <MemoryRouter initialEntries={[initialPath]}>
        <AppRoutes />
      </MemoryRouter>
    </SourcesProvider>
  );
}

afterEach(() => {
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
});

// ============================================================================
// 1. ROUTING (Req 14.1, 14.2, 14.3, 15.7)
// ============================================================================

describe("Routing (Req 14, 15.7)", () => {
  beforeEach(() => {
    stubFetchWithRealFiles();
  });

  it("navigation via Nav links reaches every top-level page without a full reload", async () => {
    renderApp("/");

    // Home resolves.
    expect(
      await screen.findByRole("heading", { name: "Research Gap Index" })
    ).toBeInTheDocument();

    // Each click is client-side (react-router <NavLink>); the target page's
    // unique content appears without the document being reloaded.
    fireEvent.click(screen.getByRole("link", { name: "WHAT" }));
    expect(
      await screen.findByRole("heading", {
        name: "Burden versus research activity by disease",
      })
    ).toBeInTheDocument();

    // The WHERE view is hidden in this version: there is no WHERE nav link.
    expect(screen.queryByRole("link", { name: "WHERE" })).toBeNull();

    fireEvent.click(screen.getByRole("link", { name: "Method" }));
    expect(
      await screen.findByRole("heading", { name: "Method and sources" })
    ).toBeInTheDocument();

    fireEvent.click(screen.getByRole("link", { name: "Build" }));
    expect(
      await screen.findByRole("heading", { name: "How we built it with Kiro" })
    ).toBeInTheDocument();

    fireEvent.click(screen.getByRole("link", { name: "Home" }));
    expect(
      await screen.findByRole("heading", { name: "Research Gap Index" })
    ).toBeInTheDocument();
  });

  it("direct-URL entry renders each static route", async () => {
    const cases: Array<{ path: string; heading: string }> = [
      { path: "/", heading: "Research Gap Index" },
      { path: "/what", heading: "Burden versus research activity by disease" },
      { path: "/method", heading: "Method and sources" },
      { path: "/build", heading: "How we built it with Kiro" },
      { path: "/does-not-exist", heading: "Page not found" },
      // The hidden WHERE view has no route: a direct hit falls through to NotFound.
      { path: "/where", heading: "Page not found" },
    ];
    for (const { path, heading } of cases) {
      const { unmount } = renderApp(path);
      expect(
        await screen.findByRole("heading", { name: heading })
      ).toBeInTheDocument();
      unmount();
    }
  });

  it("direct-URL entry renders the /investigate/:measureId route", async () => {
    renderApp(`/investigate/${DESIGNATED_MEASURE_ID}`);
    // Asthma is the condition for CASTHMA in the real investigate.json.
    expect(
      await screen.findByRole("heading", { name: "Asthma" })
    ).toBeInTheDocument();
    // A known Investigate breakdown category confirms the entry resolved.
    expect(screen.getByText("By overall status")).toBeInTheDocument();
  });

  it("direct-URL entry renders the /evidence/:measureId route", async () => {
    renderApp(`/evidence/${DESIGNATED_MEASURE_ID}`);
    // The first NCT for CASTHMA in the real evidence.json renders as a link.
    expect(
      await screen.findByRole("link", { name: "NCT04123456" })
    ).toBeInTheDocument();
  });

  it("marks the active page with aria-current=page on the Nav link", async () => {
    renderApp("/what");
    await screen.findByRole("heading", {
      name: "Burden versus research activity by disease",
    });
    const whatLink = screen.getByRole("link", { name: "WHAT" });
    expect(whatLink).toHaveAttribute("aria-current", "page");
    // A non-active link does not carry aria-current.
    expect(screen.getByRole("link", { name: "Method" })).not.toHaveAttribute(
      "aria-current"
    );
  });

  it("moves keyboard focus to #main on route change (Req 15.7)", async () => {
    renderApp("/");
    const main = document.querySelector("#main") as HTMLElement;
    await waitFor(() => expect(main).toHaveFocus());

    fireEvent.click(screen.getByRole("link", { name: "WHAT" }));
    await screen.findByRole("heading", {
      name: "Burden versus research activity by disease",
    });
    await waitFor(() => expect(document.querySelector("#main")).toHaveFocus());
  });
});

// ============================================================================
// 2. SAMPLE FIXTURES (Req 2.6 - 2.12)
// ============================================================================

describe("Sample fixtures load with zero omissions (Req 2.6-2.12)", () => {
  beforeEach(() => {
    stubFetchWithRealFiles();
  });

  it("what.json loads with zero omitted entries and 3-5 distinct in-scope ids (Req 2.6, 2.8)", async () => {
    const state = await loadJson<WhatEntry>("what.json", validateWhatEntry);
    expect(state.status).toBe("ready");
    if (state.status !== "ready") return;
    // Every raw entry survived validation: nothing omitted.
    expect(state.omittedCount).toBe(0);
    expect(state.data.length).toBe(whatRaw.length);

    const inScope = new Set([
      "CASTHMA",
      "HIGHCHOL",
      "BPHIGH",
      "DIABETES",
      "DEPRESSION",
    ]);
    const ids = state.data.map((e) => e.measure_id);
    expect(new Set(ids).size).toBe(ids.length); // distinct
    expect(ids.length).toBeGreaterThanOrEqual(3);
    expect(ids.length).toBeLessThanOrEqual(5);
    for (const id of ids) {
      expect(inScope.has(id)).toBe(true);
    }
  });

  it("investigate.json: one entry per what id, every breakdown non-empty, >=1 finding per label (Req 2.9)", async () => {
    const what = await loadJson<WhatEntry>("what.json", validateWhatEntry);
    const inv = await loadJson<InvestigateEntry>(
      "investigate.json",
      validateInvestigateEntry
    );
    expect(inv.status).toBe("ready");
    if (inv.status !== "ready" || what.status !== "ready") return;
    expect(inv.omittedCount).toBe(0);

    const whatIds = what.data.map((e) => e.measure_id).sort();
    const invIds = inv.data.map((e) => e.measure_id).sort();
    // Exactly one Investigate_Entry per What id.
    expect(invIds).toEqual(whatIds);
    expect(new Set(invIds).size).toBe(invIds.length);

    for (const entry of inv.data) {
      expect(entry.by_overall_status.length).toBeGreaterThan(0);
      expect(entry.by_study_type.length).toBeGreaterThan(0);
      expect(entry.by_intervention_type.length).toBeGreaterThan(0);
      expect(entry.by_phase.length).toBeGreaterThan(0);
      const labels = new Set(entry.findings.map((f) => f.label));
      // >= 1 finding carrying each of the two Evidence_Label values.
      expect(labels.has("possible explanation from available records")).toBe(true);
      expect(labels.has("cannot determine from public data")).toBe(true);
    }
  });

  it("evidence.json: one entry per what id, each with >=1 NCT (Req 2.9)", async () => {
    const what = await loadJson<WhatEntry>("what.json", validateWhatEntry);
    const ev = await loadJson<EvidenceEntry>(
      "evidence.json",
      validateEvidenceEntry
    );
    expect(ev.status).toBe("ready");
    if (ev.status !== "ready" || what.status !== "ready") return;
    expect(ev.omittedCount).toBe(0);

    const whatIds = what.data.map((e) => e.measure_id).sort();
    const evIds = ev.data.map((e) => e.measure_id).sort();
    expect(evIds).toEqual(whatIds);

    for (const entry of ev.data) {
      expect(entry.ncts.length).toBeGreaterThanOrEqual(1);
      for (const nct of entry.ncts) {
        expect(nct.nct_id).toMatch(/^NCT\d{8}$/);
        expect(nct.url.startsWith("https://clinicaltrials.gov/")).toBe(true);
      }
    }
  });

  it("evidence.json: at least one study carries the Spec-3 detail keys (title/status/phases/interventions)", async () => {
    const ev = await loadJson<EvidenceEntry>(
      "evidence.json",
      validateEvidenceEntry
    );
    expect(ev.status).toBe("ready");
    if (ev.status !== "ready") return;

    // The evidence table reads title, status, phases, and intervention_names.
    // The sample fixture supplies them for at least one study, and when present
    // every value is of the expected type (so the table never renders [object]).
    const allNcts = ev.data.flatMap((e) => e.ncts);
    expect(allNcts.some((n) => typeof n.title === "string" && n.title.length > 0)).toBe(true);
    expect(allNcts.some((n) => typeof n.status === "string" && n.status.length > 0)).toBe(true);
    expect(allNcts.some((n) => Array.isArray(n.phases))).toBe(true);
    expect(allNcts.some((n) => Array.isArray(n.intervention_names))).toBe(true);
    for (const n of allNcts) {
      if (n.phases !== undefined) expect(Array.isArray(n.phases)).toBe(true);
      if (n.intervention_names !== undefined)
        expect(Array.isArray(n.intervention_names)).toBe(true);
    }
  });

  it("sources.json loads and is flagged is_sample (Req 2.7)", async () => {
    expect(validateSourcesData(sourcesRaw)).toBe(true);
    const state = await loadSources("sources.json");
    expect(state.status).toBe("ready");
    if (state.status !== "ready") return;
    expect(state.isSample).toBe(true);
    expect(state.data.sources.length).toBeGreaterThan(0);
  });

  it("renders the sample-data label when is_sample is true and omits it otherwise (Req 2.7)", async () => {
    // is_sample true (the real sources.json): the banner shows.
    const first = renderApp("/build");
    expect(await screen.findByText(SAMPLE_DATA_LABEL)).toBeInTheDocument();
    first.unmount();

    // is_sample absent: the banner is not rendered. Re-stub fetch with a
    // sources body that has no is_sample flag, routed by path.
    vi.restoreAllMocks();
    vi.unstubAllGlobals();
    const notSample: SourcesData = {
      data_as_of: "2024-06-01",
      sources: [
        { name: "ClinicalTrials.gov", url: "https://clinicaltrials.gov/", fetched: "2024-05-28" },
      ],
    };
    vi.stubGlobal(
      "fetch",
      vi.fn((input: string) => {
        if (input === "/data/sources.json") {
          return Promise.resolve(jsonResponse(notSample));
        }
        return Promise.reject(new Error(`unexpected fetch: ${input}`));
      })
    );

    const { findByRole } = renderApp("/build");
    await findByRole("heading", { name: "How we built it with Kiro" });
    // Give the Sources fetch a tick to resolve, then assert the banner is gone.
    await waitFor(() =>
      expect(screen.queryByText(SAMPLE_DATA_LABEL)).toBeNull()
    );
  });
});

// ============================================================================
// 3. CONTENT SAFETY (Req 2.13)
// ============================================================================

describe("Content safety — no contact data (Req 2.13)", () => {
  beforeEach(() => {
    stubFetchWithRealFiles();
  });

  /** Recursively collect every string value from a parsed JSON value. */
  function collectStrings(value: unknown, out: string[]): void {
    if (typeof value === "string") {
      out.push(value);
    } else if (Array.isArray(value)) {
      for (const item of value) collectStrings(item, out);
    } else if (value !== null && typeof value === "object") {
      for (const v of Object.values(value)) collectStrings(v, out);
    }
  }

  it("no sample-file string field matches an email or phone pattern", () => {
    const strings: string[] = [];
    for (const raw of [
      whatRaw,
      investigateRaw,
      evidenceRaw,
      sourcesRaw,
    ]) {
      collectStrings(raw, strings);
    }
    expect(strings.length).toBeGreaterThan(0);
    const offenders = strings.filter((s) => containsContactData(s));
    expect(offenders).toEqual([]);
  });

  /**
   * Collect each contiguous run of visible text as a user would read it: the
   * data of every individual Text node. Scanning per text node (rather than an
   * element's fully-concatenated `textContent`) avoids false positives where
   * adjacent table cells like "...3.91" + "142" + "1720000" would merge into a
   * spurious 10-digit run. Each returned string is one contiguous UI string.
   */
  function visibleTextRuns(root: HTMLElement): string[] {
    const runs: string[] = [];
    const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
    let node = walker.nextNode();
    while (node) {
      const text = node.textContent ?? "";
      if (text.trim().length > 0) {
        runs.push(text);
      }
      node = walker.nextNode();
    }
    return runs;
  }

  it("no rendered page text matches an email or phone pattern", async () => {
    const paths = [
      "/",
      "/what",
      `/investigate/${DESIGNATED_MEASURE_ID}`,
      `/evidence/${DESIGNATED_MEASURE_ID}`,
      "/method",
      "/build",
    ];
    for (const path of paths) {
      const { container, unmount } = renderApp(path);
      // Let each page resolve its data before scanning.
      await screen.findAllByRole("heading");
      await waitFor(() =>
        expect(container.querySelector(".load-state--loading")).toBeNull()
      );
      const offenders = visibleTextRuns(container).filter((run) =>
        containsContactData(run)
      );
      expect(offenders, `contact-data match on ${path}`).toEqual([]);
      unmount();
    }
  });
});

// ============================================================================
// 4. ACCESSIBILITY / LAYOUT (Req 15, 16)
// ============================================================================

describe("Accessibility and layout (Req 15, 16)", () => {
  beforeEach(() => {
    stubFetchWithRealFiles();
  });

  it("WHAT chart SVG is associated with its text-alternative table via aria-describedby (Req 15.5, 15.8)", async () => {
    const { container } = renderApp("/what");
    const svg = await waitFor(() => {
      const el = container.querySelector('svg[role="img"]');
      expect(el).not.toBeNull();
      return el as SVGElement;
    });
    const tableId = svg.getAttribute("aria-describedby");
    expect(tableId).toBeTruthy();
    const table = document.getElementById(tableId as string);
    expect(table).not.toBeNull();
    expect(table?.tagName.toLowerCase()).toBe("table");
  });

  it("WHAT table rows are keyboard-operable buttons with accessible names (Req 15.3, 15.5)", async () => {
    renderApp("/what");
    await screen.findByRole("heading", {
      name: "Burden versus research activity by disease",
    });
    // Every real condition renders as a focusable <button> (keyboard operable)
    // with its condition name as the accessible name.
    for (const entry of whatRaw as WhatEntry[]) {
      const button = await screen.findByRole("button", {
        name: entry.condition,
      });
      expect(button.tagName.toLowerCase()).toBe("button");
    }
  });

  it("the three lowest-mid diseases appear first, in order, in the WHAT chart/table (Req 16.1)", async () => {
    renderApp("/what");
    await screen.findByRole("heading", {
      name: "Burden versus research activity by disease",
    });

    // Expected order is the real data sorted ascending by mid (alpha tie-break).
    const expectedOrder = sortConditions(whatRaw as WhatEntry[]).map(
      (e) => e.condition
    );
    const lowestThree = expectedOrder.slice(0, 3);

    // The row-button accessible names, read in DOM order, are the table order.
    const buttons = screen.getAllByRole("button");
    const renderedOrder = buttons
      .map((b) => b.textContent?.trim() ?? "")
      .filter((name) => expectedOrder.includes(name));
    expect(renderedOrder.slice(0, 3)).toEqual(lowestThree);
    // Sanity: the overall rendered order matches the full sorted order.
    expect(renderedOrder).toEqual(expectedOrder);
  });

  it("the palette CSS custom properties are defined (Req 15.1, 15.2)", () => {
    // jsdom cannot compute true WCAG contrast or 375px overflow; those require
    // a real browser. What IS feasible here: confirm the palette tokens the
    // chart/map/focus styles depend on are declared as :root custom properties.
    const css = readFileSync(
      resolve(HERE, "./styles/palette.css"),
      "utf8"
    );
    for (const token of [
      "--bg",
      "--ink",
      "--accent",
      "--focus",
      "--seq-1",
      "--seq-2",
      "--seq-3",
      "--seq-4",
      "--seq-5",
      "--unknown",
    ]) {
      expect(css).toContain(`${token}:`);
    }
  });

  it("fetches each data file exactly once per page view (Req 16.3)", async () => {
    // WHAT reads exactly one file: what.json. Sources is loaded once app-wide by
    // the top-level SourcesProvider. (The WHERE view, which used to read
    // where.json + ma_counties.geojson, is hidden in this version.)
    const { calls } = stubFetchWithRealFiles();
    const { unmount } = renderApp("/what");
    await screen.findByRole("heading", {
      name: "Burden versus research activity by disease",
    });
    await waitFor(() => {
      expect(calls.get("/data/what.json")).toBe(1);
      expect(calls.get("/data/sources.json")).toBe(1);
    });
    // No page other than WHAT's own file (plus app-wide sources) was requested.
    expect(calls.get("/data/investigate.json")).toBeUndefined();
    expect(calls.get("/data/evidence.json")).toBeUndefined();
    expect(calls.get("/data/where.json")).toBeUndefined();
    expect(calls.get("/data/ma_counties.geojson")).toBeUndefined();
    unmount();
  });
});
