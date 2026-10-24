// Unit tests for the Build page restyle into a single card (Req 12.1).
//
// Covered:
//   - exactly one card titled "How we built it with Kiro" (Req 12.1); and
//   - the existing copy and GitHub links are preserved (spec files, steering
//     files, and the build log), unchanged by the restyle.
//
// Build is a static route component: it reads no providers and loads no data,
// so no mocking or router is required.

import { afterEach, describe, expect, it } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";

import Build from "./Build";

afterEach(() => {
  cleanup();
});

describe("Build page — single card (Req 12.1)", () => {
  it("renders exactly one card titled 'How we built it with Kiro'", () => {
    render(<Build />);
    expect(
      screen.getAllByRole("heading", { name: "How we built it with Kiro" })
    ).toHaveLength(1);
  });

  it("wraps the page content in a Card container", () => {
    const { container } = render(<Build />);
    const cards = container.querySelectorAll(".card");
    expect(cards).toHaveLength(1);
    const title = container.querySelector(".card-title");
    expect(title?.textContent).toBe("How we built it with Kiro");
  });
});

describe("Build page — preserved copy and links (Req 12.1)", () => {
  it("keeps the intro, section headings, and all GitHub blob links", () => {
    render(<Build />);

    // Section headings preserved.
    expect(screen.getByRole("heading", { name: "Spec files" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Steering files" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Build log" })).toBeInTheDocument();

    // Every link points at a GitHub blob URL on the repo's main branch and
    // opens in a new context.
    const links = screen.getAllByRole("link");
    expect(links.length).toBeGreaterThanOrEqual(8);
    for (const link of links) {
      const href = link.getAttribute("href") ?? "";
      expect(href).toMatch(
        /^https:\/\/github\.com\/ethancfay\/research-gap-index\/blob\/main\//
      );
      expect(link).toHaveAttribute("target", "_blank");
      expect(link).toHaveAttribute("rel", "noopener noreferrer");
    }

    // The build log link is present with its exact label.
    expect(screen.getByRole("link", { name: "KIRO_LOG.md" })).toHaveAttribute(
      "href",
      "https://github.com/ethancfay/research-gap-index/blob/main/KIRO_LOG.md"
    );
  });
});
