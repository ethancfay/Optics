// Example/edge-case tests for DotWhiskerChart and its Text_Alternative table
// (Req 5.7, 6.3, 6.4, 6.5). These use @testing-library/react + jsdom and make
// no network request. The component is pure/presentational; navigation is
// exercised through a real MemoryRouter + Routes so clicking a row control
// lands on /investigate/:measureId.

import { describe, it, expect } from "vitest";
import { render, screen, fireEvent, within } from "@testing-library/react";
import { MemoryRouter, Routes, Route, useParams } from "react-router-dom";
import DotWhiskerChart, {
  AXIS_LABEL,
  LOG_SCALE_SUFFIX,
  LOG_SCALE_TITLE_NOTE,
} from "./DotWhiskerChart";
import type { WhatEntry } from "../data/types";
import { sortConditions } from "../data/conditions";
import shippedWhat from "../../public/data/what.json";

/** The shipped sample what.json, sorted the way the What_View passes it. */
const SHIPPED: readonly WhatEntry[] = sortConditions(shippedWhat as WhatEntry[]);

/** A fully-valid entry; individual tests override fields as needed. */
function makeEntry(overrides: Partial<WhatEntry> = {}): WhatEntry {
  return {
    condition: "Asthma",
    measure_id: "CASTHMA",
    low: 1,
    mid: 2,
    high: 3,
    t: 4,
    affected_adults: 500000,
    p_low: 0.1,
    p_high: 0.2,
    ctgov_url: "https://clinicaltrials.gov/",
    ...overrides,
  };
}

/** Probe element rendered by the /investigate/:measureId route. */
function MeasureProbe() {
  const { measureId } = useParams();
  return <div data-testid="route-probe">investigate:{measureId}</div>;
}

/** Render the chart inside a router with a probe route for navigation. */
function renderChart(entries: readonly WhatEntry[]) {
  return render(
    <MemoryRouter initialEntries={["/what"]}>
      <Routes>
        <Route path="/what" element={<DotWhiskerChart entries={entries} />} />
        <Route path="/investigate/:measureId" element={<MeasureProbe />} />
      </Routes>
    </MemoryRouter>
  );
}

describe("DotWhiskerChart", () => {
  it("shows the no-data message and an empty table (headers, no rows, note) when there are zero entries", () => {
    renderChart([]);

    // The no-diseases message appears (Req 5.7).
    const statuses = screen.getAllByText("No diseases are available");
    expect(statuses.length).toBeGreaterThanOrEqual(1);
    expect(screen.getByRole("status")).toHaveTextContent(
      "No diseases are available"
    );

    // The table still renders all seven column headers (Req 6.4).
    const table = screen.getByRole("table");
    const headers = within(table).getAllByRole("columnheader");
    expect(headers.map((h) => h.textContent)).toEqual([
      "condition",
      "low",
      "mid",
      "high",
      "t",
      "affected_adults",
      "prevalence_year",
    ]);

    // No data rows: no condition buttons exist in the empty state.
    expect(screen.queryByRole("button")).toBeNull();

    // An explicit no-data note occupies the table body (Req 6.4).
    const bodyNote = within(table).getAllByText("No diseases are available");
    expect(bodyNote.length).toBeGreaterThanOrEqual(1);
  });

  it("associates the chart SVG with the text-alternative table via aria-describedby (Req 6.3)", () => {
    renderChart([makeEntry()]);

    const svg = screen.getByRole("img");
    const describedBy = svg.getAttribute("aria-describedby");
    expect(describedBy).toBeTruthy();

    const table = screen.getByRole("table");
    expect(table.id).toBeTruthy();
    expect(describedBy).toBe(table.id);
  });

  it('shows "unavailable" for a missing/non-finite numeric cell (Req 6.5)', () => {
    // mid is intentionally missing; the component guards with Number.isFinite.
    const entry = makeEntry({ mid: undefined as unknown as number });
    renderChart([entry]);

    const table = screen.getByRole("table");
    const row = within(table).getAllByRole("row")[1]; // first data row (after header)
    const cells = within(row).getAllByRole("cell");
    // Columns after the row header: low, mid, high, t, affected_adults.
    // mid is the 2nd cell and should read "unavailable".
    expect(cells[1]).toHaveTextContent("unavailable");
    // Other finite cells are not "unavailable".
    expect(cells[0]).toHaveTextContent("1"); // low
    expect(cells[2]).toHaveTextContent("3"); // high
  });

  it("uses the log scale for the shipped data: ticks 0.1, 1, 10, '(log scale)' label, title note (Req 22.3, 22.4)", () => {
    renderChart(SHIPPED);

    const svg = screen.getByRole("img");
    const tickLabels = Array.from(svg.querySelectorAll("text.dw-axis-tick")).map(
      (node) => node.textContent
    );
    expect(tickLabels).toEqual(["0.1", "1", "10"]);
    expect(svg.querySelectorAll("line.dw-axis-grid")).toHaveLength(3);

    expect(svg.querySelector("text.dw-axis-label")?.textContent).toBe(
      AXIS_LABEL + LOG_SCALE_SUFFIX
    );
    expect(AXIS_LABEL + LOG_SCALE_SUFFIX).toBe(
      "distinct recruiting MA studies per 100,000 affected adults (18+) (log scale)"
    );
    expect(svg.querySelector("title")?.textContent).toContain(LOG_SCALE_TITLE_NOTE);

    // aria-describedby still names the text-alternative table (Req 22.8).
    expect(svg.getAttribute("aria-describedby")).toBe(screen.getByRole("table").id);
  });

  it("falls back to a linear scale from 0 when a disease has zero studies (Req 22.5, 22.8)", () => {
    const zero = makeEntry({
      condition: "Zero Study Disease",
      measure_id: "ZERO",
      low: 0,
      mid: 0,
      high: 0,
      t: 0,
    });
    renderChart([zero, ...SHIPPED]);

    const svg = screen.getByRole("img");
    const tickLabels = Array.from(svg.querySelectorAll("text.dw-axis-tick")).map(
      (node) => node.textContent
    );
    expect(tickLabels[0]).toBe("0");
    expect(tickLabels.length).toBeGreaterThanOrEqual(2);

    expect(svg.querySelector("text.dw-axis-label")?.textContent).toBe(AXIS_LABEL);
    expect(svg.querySelector("title")?.textContent).not.toContain(
      LOG_SCALE_TITLE_NOTE
    );

    // Every disease is still drawn: one dot per row.
    expect(svg.querySelectorAll("circle")).toHaveLength(4);
    expect(svg.getAttribute("aria-describedby")).toBe(screen.getByRole("table").id);
  });

  it("renders without error when every value is 0, all marks at the plot's left edge (Req 22.5)", () => {
    renderChart([
      makeEntry({ low: 0, mid: 0, high: 0 }),
      makeEntry({ condition: "Other", measure_id: "OTHER", low: 0, mid: 0, high: 0 }),
    ]);

    const svg = screen.getByRole("img");
    const dots = Array.from(svg.querySelectorAll("circle"));
    expect(dots).toHaveLength(2);
    const xs = new Set(dots.map((dot) => dot.getAttribute("cx")));
    expect(xs.size).toBe(1);
    const divider = svg.querySelector("line.dw-axis-divider");
    expect([...xs][0]).toBe(divider?.getAttribute("x1"));
  });

  it("navigates to /investigate/:measureId when a row's condition button is activated (Req 5.5, 6.3)", () => {
    const entry = makeEntry({ condition: "High Cholesterol", measure_id: "HIGHCHOL" });
    renderChart([entry]);

    // Before activation, the probe route is not mounted.
    expect(screen.queryByTestId("route-probe")).toBeNull();

    const rowButton = screen.getByRole("button", { name: "High Cholesterol" });
    fireEvent.click(rowButton);

    // Navigation landed on the investigate route for this measure_id.
    const probe = screen.getByTestId("route-probe");
    expect(probe).toHaveTextContent("investigate:HIGHCHOL");
  });
});
