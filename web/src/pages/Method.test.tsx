// Unit test for the Method page national-comparison note (Req 11.7).
// No network: the Sources hook is mocked.

import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";

vi.mock("../data/providers", () => ({
  useSources: () => ({ status: "loading" }),
}));

import Method, {
  DISEASE_SCOPE,
  HIGHCHOL_HEART_DISEASE_NOTE,
  NATIONAL_COMPARISON_PLANNED,
} from "./Method";

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

  it("renders nothing about the pending 'questionable' decision (code-only TODO)", () => {
    const { container } = render(<Method />);
    expect(container.textContent ?? "").not.toMatch(/questionable|to do|todo/i);
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
