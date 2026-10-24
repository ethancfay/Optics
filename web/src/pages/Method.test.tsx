// Unit tests for the Method page: three-disease scope (Req 20.6), matching rules
// (Req 21) and the national-comparison note (Req 11.7).
// No network: the Sources hook is mocked.

import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import type { LoadState, SourcesData } from "../data/types";

// The Sources provider hook is the single data input; a module-level `state`
// lets each test drive the loading/ready/error case without a network request.
let sourcesState: LoadState<SourcesData> = { status: "loading" };
vi.mock("../data/providers", () => ({
  useSources: () => sourcesState,
}));

import Method, {
  CHILD_ONLY_NOTE,
  DISEASE_SCOPE,
  HIGHCHOL_HEART_DISEASE_NOTE,
  MATCHING_TERMS_NOTE,
  NATIONAL_COMPARISON_PLANNED,
  QUESTIONABLE_NOT_COUNTED,
} from "./Method";
import methodSource from "./Method.tsx?raw";
import { FORBIDDEN_TERMS } from "../data/forbiddenTerms";

/** Rough English syllable count: vowel groups, minus a silent final "e". */
function syllables(word: string): number {
  const w = word.toLowerCase().replace(/[^a-z]/g, "");
  if (w.length === 0) return 0;
  if (w.length <= 3) return 1;
  const groups = w.replace(/(?:[^laeiouy]es|ed|[^laeiouy]e)$/, "").replace(/^y/, "").match(/[aeiouy]{1,2}/g);
  return Math.max(1, groups?.length ?? 1);
}

/** Flesch-Kincaid grade level of a block of text. */
function fleschKincaidGrade(text: string): number {
  const sentences = text.split(/[.!?]+/).filter((s) => s.trim().length > 0).length;
  const words = text.split(/\s+/).filter((w) => /[a-z0-9]/i.test(w));
  const syl = words.reduce((sum, w) => sum + syllables(w), 0);
  return 0.39 * (words.length / sentences) + 11.8 * (syl / words.length) - 15.59;
}

const MATCHING_SENTENCES = [
  MATCHING_TERMS_NOTE,
  CHILD_ONLY_NOTE,
  HIGHCHOL_HEART_DISEASE_NOTE,
  QUESTIONABLE_NOT_COUNTED,
];

/** A ready Sources_Data fixture with two named sources, each with a fetched date. */
const READY_SOURCES: SourcesData = {
  data_as_of: "2026-10-24",
  is_sample: false,
  sources: [
    {
      name: "ClinicalTrials.gov",
      url: "https://clinicaltrials.gov/",
      fetched: "2026-10-24",
    },
    {
      name: "CDC PLACES 2025 county release",
      url: "https://data.cdc.gov/d/swc5-untb",
      fetched: "2026-10-20",
    },
  ],
};

function readySources(data: SourcesData): LoadState<SourcesData> {
  return { status: "ready", data, omittedCount: 0, isSample: false };
}

afterEach(() => {
  cleanup();
  sourcesState = { status: "loading" };
});

describe("Method page — single card (Req 11.1)", () => {
  it("renders exactly one card titled 'Method and Sources'", () => {
    sourcesState = readySources(READY_SOURCES);
    render(<Method />);
    expect(
      screen.getAllByRole("heading", { name: "Method and Sources" })
    ).toHaveLength(1);
  });
});

describe("Method page — sources wiring (Req 11.2, 11.3)", () => {
  it("renders one named source link per entry, each with its fetched date", () => {
    sourcesState = readySources(READY_SOURCES);
    render(<Method />);
    for (const source of READY_SOURCES.sources) {
      const link = screen.getByRole("link", { name: source.name });
      expect(link).toHaveAttribute("href", source.url);
      // The fetched date is shown next to the link in the same list item.
      const listItem = link.closest("li");
      expect(listItem).not.toBeNull();
      expect(listItem!.textContent).toContain(`fetched ${source.fetched}`);
    }
  });

  it("renders the data-unavailable component naming sources.json when Sources_Data fails", () => {
    sourcesState = { status: "error", reason: "network", file: "sources.json" };
    render(<Method />);
    const alert = screen.getByRole("alert");
    expect(alert.textContent).toContain("This data is currently unavailable");
    expect(alert.textContent).toContain("sources.json");
    // No source links render while the file is unavailable.
    expect(screen.queryByRole("link", { name: "ClinicalTrials.gov" })).toBeNull();
  });
});

describe("Method page — three-disease scope (Req 20.6)", () => {
  it("states the three diseases and how the deferred two can be added", () => {
    render(<Method />);
    expect(screen.getAllByText(DISEASE_SCOPE)).toHaveLength(1);
    expect(DISEASE_SCOPE).toMatch(/three diseases: asthma, diabetes and high cholesterol/);
    expect(DISEASE_SCOPE).toMatch(/High blood pressure and depression can be added/);
    expect(DISEASE_SCOPE).toMatch(/rules file, after review/);
  });

  it("states that heart-disease-only studies are not counted for high cholesterol", () => {
    render(<Method />);
    expect(screen.getAllByText(HIGHCHOL_HEART_DISEASE_NOTE)).toHaveLength(1);
    expect(HIGHCHOL_HEART_DISEASE_NOTE).toMatch(/heart attack/);
    expect(HIGHCHOL_HEART_DISEASE_NOTE).toMatch(/lower/);
  });
});

describe("Method page — matching rules (Req 21)", () => {
  it("renders each matching-rule sentence once in the matching section", () => {
    render(<Method />);
    const section = screen
      .getByRole("heading", { name: "How we match studies to a disease" })
      .closest("section");
    expect(section).not.toBeNull();
    for (const sentence of MATCHING_SENTENCES) {
      expect(screen.getAllByText(sentence)).toHaveLength(1);
      expect(section!.textContent).toContain(sentence);
    }
  });

  it("describes the include and rule-out word lists (Req 21.1)", () => {
    expect(MATCHING_TERMS_NOTE).toMatch(/words to look for/);
    expect(MATCHING_TERMS_NOTE).toMatch(/rule a study out/);
    expect(MATCHING_TERMS_NOTE).toMatch(/does not also name the disease/);
  });

  it("says child-only studies are not counted (Req 21.2)", () => {
    expect(CHILD_ONLY_NOTE).toMatch(/do not count studies that include only children/);
    expect(CHILD_ONLY_NOTE).toMatch(/under 18/);
    expect(CHILD_ONLY_NOTE).toMatch(/adults 18 and older/);
  });

  it("says questionable studies are not counted, with a real example (Req 21.4)", () => {
    expect(QUESTIONABLE_NOT_COUNTED).toMatch(/"questionable"/);
    expect(QUESTIONABLE_NOT_COUNTED).toMatch(/We do not count these studies\.$/);
    // "Lipid Disorders" is a HIGHCHOL broad_category Questionable_Term in rules.py.
    expect(QUESTIONABLE_NOT_COUNTED).toMatch(/"lipid disorders"/);
  });

  it("renders no crosswalk or to-do text, and the source has no TODO(scoring-export) (Req 21.5)", () => {
    const { container } = render(<Method />);
    const text = container.textContent ?? "";
    expect(text).not.toMatch(/crosswalk/i);
    expect(text).not.toMatch(/\bto do\b|\btodo\b/i);
    expect(methodSource).toContain("export const QUESTIONABLE_NOT_COUNTED"); // raw import is real
    expect(methodSource).not.toMatch(/TODO\(scoring-export\)/);
    expect(methodSource).not.toMatch(/crosswalk/i);
  });

  it("keeps the matching copy at grade 8 or lower with no Forbidden_Terms (Req 21.6)", () => {
    const copy = MATCHING_SENTENCES.join(" ");
    expect(fleschKincaidGrade(copy)).toBeLessThanOrEqual(8);
    for (const term of FORBIDDEN_TERMS) {
      expect(copy.toLowerCase()).not.toContain(term);
    }
  });
});

describe("Method page — national comparison (Req 11.7)", () => {
  it("states once that a national comparison is planned", () => {
    render(<Method />);
    expect(screen.getAllByText(NATIONAL_COMPARISON_PLANNED)).toHaveLength(1);
    expect(NATIONAL_COMPARISON_PLANNED).toMatch(/planned/);
    expect(NATIONAL_COMPARISON_PLANNED).toMatch(/United States/);
  });
});
