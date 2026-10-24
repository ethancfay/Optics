// Unit test for the Method page national-comparison note (Req 11.7).
// No network: the Sources hook is mocked.

import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";

vi.mock("../data/providers", () => ({
  useSources: () => ({ status: "loading" }),
}));

import Method, { NATIONAL_COMPARISON_PLANNED } from "./Method";

describe("Method page — national comparison (Req 11.7)", () => {
  it("states once that a national comparison is planned", () => {
    render(<Method />);
    expect(screen.getAllByText(NATIONAL_COMPARISON_PLANNED)).toHaveLength(1);
    expect(NATIONAL_COMPARISON_PLANNED).toMatch(/planned/);
    expect(NATIONAL_COMPARISON_PLANNED).toMatch(/United States/);
  });
});
