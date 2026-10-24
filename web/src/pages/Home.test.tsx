// Unit tests for the Home page restyle into the two mockup cards (Req 6.5, 7).
//
// Covered:
//   - the two card titles "What is Research Gap Index?" and "Top Finding"
//     (Req 7.1, 7.2);
//   - the left card holds exactly one explanatory sentence (Req 7.1);
//   - Top_Finding_Disease is driven by `selectTopFinding` — the lowest-midpoint
//     disease — and its low-high Index_Value range is shown, with no hard-coded
//     disease name (Req 7.2, 7.3);
//   - the "See every disease" control navigates to the WHAT route client-side
//     (Req 7.4); and
//   - the no-disease-data fallback replaces the Top Finding card contents when
//     What_Data has no valid entries (Req 7.5).
//
// No network: the What provider hook is mocked. `selectTopFinding` is the REAL
// Data_Layer helper so the test verifies the actual selection, not a copy.

import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import type { LoadState, WhatEntry } from "../data/types";
import { selectTopFinding } from "../data/conditions";

// The What provider hook is the single data input; a module-level `state` lets
// each test drive the loading/ready/empty case without a network request.
let whatState: LoadState<WhatEntry[]> = { status: "loading" };
vi.mock("../data/providers", () => ({
  useWhatData: () => whatState,
}));

import Home, {
  WHAT_IS_SENTENCE,
  NO_DISEASE_DATA_MESSAGE,
} from "./Home";

/** Build a WhatEntry with sensible defaults; override only what a test needs. */
function entry(partial: Partial<WhatEntry> & { condition: string; mid: number }): WhatEntry {
  return {
    measure_id: partial.condition.toUpperCase(),
    low: partial.mid - 0.02,
    high: partial.mid + 0.02,
    t: 5,
    affected_adults: 100000,
    p_low: 0.1,
    p_high: 0.12,
    ctgov_url: "https://clinicaltrials.gov/search?cond=x",
    ...partial,
  };
}

/** Three diseases whose lowest midpoint is unambiguously "High Cholesterol". */
const THREE_DISEASES: WhatEntry[] = [
  entry({ condition: "Asthma", mid: 1.1, low: 1.0, high: 1.2 }),
  entry({ condition: "Diabetes", mid: 0.8, low: 0.7, high: 0.9 }),
  entry({ condition: "High Cholesterol", mid: 0.25, low: 0.23, high: 0.27 }),
];

function ready(data: WhatEntry[]): LoadState<WhatEntry[]> {
  return { status: "ready", data, omittedCount: 0, isSample: false };
}

/** Render Home at `/` with a visible WHAT route so we can assert navigation. */
function renderHome() {
  return render(
    <MemoryRouter initialEntries={["/"]}>
      <Routes>
        <Route path="/" element={<Home />} />
        <Route path="/what" element={<h1>WHAT view</h1>} />
      </Routes>
    </MemoryRouter>
  );
}

afterEach(() => {
  cleanup();
  whatState = { status: "loading" };
});

describe("Home — two mockup cards (Req 7.1, 7.2)", () => {
  it("renders the left and right card titles", () => {
    whatState = ready(THREE_DISEASES);
    renderHome();
    expect(
      screen.getByRole("heading", { name: "What is Optics?" })
    ).toBeInTheDocument();
    expect(
      screen.getByRole("heading", { name: "Top Finding" })
    ).toBeInTheDocument();
  });

  it("left card holds exactly one explanatory sentence (Req 7.1)", () => {
    whatState = ready(THREE_DISEASES);
    renderHome();
    expect(screen.getByText(WHAT_IS_SENTENCE)).toBeInTheDocument();
    // Exactly one sentence: a single terminal period, 1-200 characters.
    const terminators = WHAT_IS_SENTENCE.match(/[.!?]/g) ?? [];
    expect(terminators).toHaveLength(1);
    expect(WHAT_IS_SENTENCE.length).toBeGreaterThanOrEqual(1);
    expect(WHAT_IS_SENTENCE.length).toBeLessThanOrEqual(200);
  });
});

describe("Home — Top_Finding_Disease via selectTopFinding (Req 7.2, 7.3)", () => {
  it("shows the lowest-midpoint disease and its low-high range, not hard-coded", () => {
    whatState = ready(THREE_DISEASES);
    renderHome();

    const top = selectTopFinding(THREE_DISEASES)!;
    expect(top.condition).toBe("High Cholesterol");

    // The top-finding card names the selected disease and both range bounds.
    const topCard = screen
      .getByRole("heading", { name: "Top Finding" })
      .closest("section")!;
    expect(topCard.textContent).toContain(top.condition);
    expect(topCard.textContent).toContain(String(top.low));
    expect(topCard.textContent).toContain(String(top.high));
  });

  it("re-selects a different disease when the data changes (no hard-coding)", () => {
    // Make Diabetes the lowest midpoint; the card must follow selectTopFinding.
    const data: WhatEntry[] = [
      entry({ condition: "Asthma", mid: 1.1, low: 1.0, high: 1.2 }),
      entry({ condition: "Diabetes", mid: 0.05, low: 0.04, high: 0.06 }),
      entry({ condition: "High Cholesterol", mid: 0.25, low: 0.23, high: 0.27 }),
    ];
    whatState = ready(data);
    renderHome();

    const top = selectTopFinding(data)!;
    expect(top.condition).toBe("Diabetes");
    const topCard = screen
      .getByRole("heading", { name: "Top Finding" })
      .closest("section")!;
    expect(topCard.textContent).toContain("Diabetes");
    expect(topCard.textContent).not.toContain("High Cholesterol");
  });
});

describe("Home — See every disease control (Req 7.4)", () => {
  it("navigates to the WHAT route client-side on activation", () => {
    whatState = ready(THREE_DISEASES);
    renderHome();

    const link = screen.getByRole("link", { name: "See every disease" });
    expect(link).toHaveAttribute("href", "/what");

    fireEvent.click(link);

    // Content swapped in place (client-side), not a full reload.
    expect(
      screen.getByRole("heading", { name: "WHAT view" })
    ).toBeInTheDocument();
    expect(
      screen.queryByRole("heading", { name: "Top Finding" })
    ).toBeNull();
  });
});

describe("Home — no-disease-data fallback (Req 7.5)", () => {
  it("shows the no-data message in place of the Top Finding contents when empty", () => {
    whatState = { status: "empty" };
    renderHome();

    // The Top Finding card still renders, but its body is the no-data message.
    expect(
      screen.getByRole("heading", { name: "Top Finding" })
    ).toBeInTheDocument();
    expect(screen.getByText(NO_DISEASE_DATA_MESSAGE)).toBeInTheDocument();
  });
});
