// Example/unit tests for the What_View route (Req 8.1, 8.2, 8.3, 8.5, 10.1,
// 10.2, 10.3).
//
// No real network: `fetch` is mocked in every test and routed by path so the
// real WhatDataProvider resolves from an in-memory what.json payload. The page
// is rendered inside a MemoryRouter + Routes so that selecting a disease in the
// picker can be observed navigating to the `/investigate/:measureId` route.

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { MemoryRouter, Routes, Route } from "react-router-dom";
import What, {
  CAVEAT_EXCLUSION,
  CAVEAT_SMALL_COUNTS,
  CHART_CARD_TITLE,
  NO_DISEASE_DATA_MESSAGE,
  PICKER_CARD_TITLE,
} from "./What";
import { WhatDataProvider } from "../data/providers";
import type { WhatEntry } from "../data/types";

/** Build a Response-like object good enough for loadJson. */
function jsonResponse(body: unknown, ok = true): Response {
  return {
    ok,
    json: async () => body,
  } as unknown as Response;
}

/** Two valid What entries so the chart, caveats, and picker all render. */
const ASTHMA: WhatEntry = {
  condition: "Asthma",
  measure_id: "CASTHMA",
  low: 0.9,
  mid: 1.22,
  high: 1.5,
  t: 8,
  affected_adults: 600000,
  p_low: 0.1,
  p_high: 0.12,
  prevalence_year: "2023",
  ctgov_url: "https://clinicaltrials.gov/search?cond=Asthma&locStr=Massachusetts",
};

const HIGHCHOL: WhatEntry = {
  condition: "High Cholesterol",
  measure_id: "HIGHCHOL",
  low: 0.23,
  mid: 0.25,
  high: 0.27,
  t: 5,
  affected_adults: 1500000,
  p_low: 0.3,
  p_high: 0.33,
  prevalence_year: "2023",
  ctgov_url:
    "https://clinicaltrials.gov/search?cond=High+Cholesterol&locStr=Massachusetts",
};

const PAYLOAD: WhatEntry[] = [ASTHMA, HIGHCHOL];

/**
 * Route the mocked fetch by path. `what` may be an array payload, an Error (to
 * simulate a failed what.json load), or an empty array (all entries omitted ->
 * empty state).
 */
function stubWhat(what: unknown | Error = PAYLOAD): void {
  (fetch as unknown as ReturnType<typeof vi.fn>).mockImplementation(
    (input: string) => {
      if (input.endsWith("/data/what.json")) {
        return what instanceof Error
          ? Promise.reject(what)
          : Promise.resolve(jsonResponse(what));
      }
      return Promise.reject(new Error(`unexpected fetch: ${input}`));
    }
  );
}

/**
 * Render the WHAT page inside the real WhatDataProvider (with a mocked fetch)
 * and a MemoryRouter. A sentinel route for `/investigate/:measureId` lets a
 * test observe client-side navigation out of the picker.
 */
function renderWhat() {
  return render(
    <MemoryRouter initialEntries={["/what"]}>
      <WhatDataProvider>
        <Routes>
          <Route path="/what" element={<What />} />
          <Route
            path="/investigate/:measureId"
            element={<div data-testid="investigate-route" />}
          />
        </Routes>
      </WhatDataProvider>
    </MemoryRouter>
  );
}

beforeEach(() => {
  vi.stubGlobal("fetch", vi.fn());
});

afterEach(() => {
  vi.restoreAllMocks();
});

describe("What page — cards and caveats (Req 8.1, 8.2, 10.1, 10.2)", () => {
  beforeEach(() => {
    stubWhat();
  });

  it("renders the chart card and the picker card titles", async () => {
    renderWhat();
    expect(
      await screen.findByRole("heading", { name: CHART_CARD_TITLE })
    ).toBeInTheDocument();
    expect(
      screen.getByRole("heading", { name: PICKER_CARD_TITLE })
    ).toBeInTheDocument();
  });

  it("shows both mandatory caveats while the chart is displayed", async () => {
    renderWhat();
    // Wait for the chart (the SVG with role="img") — and so the caveats — to
    // appear once What_Data resolves.
    await screen.findByRole("img");

    expect(screen.getByText(CAVEAT_EXCLUSION)).toBeInTheDocument();
    expect(screen.getByText(CAVEAT_SMALL_COUNTS)).toBeInTheDocument();
  });
});

describe("What page — caveats absent when the chart is hidden (Req 10.3)", () => {
  it("renders neither caveat while What_Data is still loading", async () => {
    stubWhat(); // resolves, but assertions run before the fetch settles
    renderWhat();

    // Loading indicator is shown; the chart (and so the caveats) is not.
    expect(screen.getAllByText(/Loading data/i).length).toBeGreaterThan(0);
    expect(screen.queryByText(CAVEAT_EXCLUSION)).toBeNull();
    expect(screen.queryByText(CAVEAT_SMALL_COUNTS)).toBeNull();
    expect(screen.queryByRole("img")).toBeNull();

    // Let the pending fetch settle so the provider's state update is flushed
    // inside act() rather than warning after the test ends.
    await screen.findByRole("img");
  });

  it("renders no caveats and the no-data message when What_Data is empty (Req 8.5, 10.3)", async () => {
    stubWhat([]); // valid shape, zero entries -> empty state

    renderWhat();

    // The no-disease-data message stands in for the chart (one per card).
    const messages = await screen.findAllByText(NO_DISEASE_DATA_MESSAGE);
    expect(messages.length).toBeGreaterThan(0);

    // Neither caveat is shown and no chart is drawn.
    expect(screen.queryByText(CAVEAT_EXCLUSION)).toBeNull();
    expect(screen.queryByText(CAVEAT_SMALL_COUNTS)).toBeNull();
    expect(screen.queryByRole("img")).toBeNull();
  });

  it("renders no caveats when What_Data fails to load (Req 10.3)", async () => {
    stubWhat(new Error("network down"));

    renderWhat();

    // The data-unavailable component names the file; no chart, no caveats.
    await screen.findAllByText(/This data is currently unavailable/i);
    expect(screen.queryByText(CAVEAT_EXCLUSION)).toBeNull();
    expect(screen.queryByText(CAVEAT_SMALL_COUNTS)).toBeNull();
    expect(screen.queryByRole("img")).toBeNull();
  });
});

describe("What page — disease picker (Req 8.2, 8.3)", () => {
  beforeEach(() => {
    stubWhat();
  });

  it("lists exactly the What_Data diseases as picker options", async () => {
    renderWhat();
    const picker = (await screen.findByRole("combobox", {
      name: /Choose a disease to investigate/i,
    })) as HTMLSelectElement;

    const optionNames = Array.from(picker.querySelectorAll("option")).map(
      (o) => o.textContent
    );
    expect(optionNames).toContain("Asthma");
    expect(optionNames).toContain("High Cholesterol");
    // Placeholder + the two diseases, nothing extra.
    expect(picker.querySelectorAll("option")).toHaveLength(PAYLOAD.length + 1);
  });

  it("navigates to the Investigate route for the selected disease (Req 8.3)", async () => {
    renderWhat();
    const picker = (await screen.findByRole("combobox", {
      name: /Choose a disease to investigate/i,
    })) as HTMLSelectElement;

    fireEvent.change(picker, { target: { value: "HIGHCHOL" } });

    // Client-side navigation lands on the Investigate sentinel route.
    expect(await screen.findByTestId("investigate-route")).toBeInTheDocument();
    // The WHAT chart card heading is gone, confirming the route changed.
    expect(screen.queryByRole("heading", { name: CHART_CARD_TITLE })).toBeNull();
  });
});
