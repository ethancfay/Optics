// Example/edge tests for the shared Layout shell (Req 14.1, 14.2, 14.4, 15.3,
// 15.7). These cover the layout STRUCTURE and interaction wiring; the
// cross-route footer/disclaimer property (Property 9) is task 8.3.
//
// All tests render inside a MemoryRouter and wrap the tree in SourcesProvider
// because the Footer reads useSources(). `fetch` is mocked so the provider's
// one-shot load never performs real network I/O.

import type { ReactNode } from "react";
import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import Layout, { Nav, SkipLink } from "./Layout";
import { SourcesProvider } from "../data/providers";

function renderAt(path: string, children?: ReactNode) {
  return render(
    <SourcesProvider>
      <MemoryRouter initialEntries={[path]}>
        {children ? (
          <Layout>{children}</Layout>
        ) : (
          <Routes>
            <Route element={<Layout />}>
              <Route path="/" element={<p>home page</p>} />
              <Route path="/what" element={<p>what page</p>} />
              <Route path="/where" element={<p>where page</p>} />
            </Route>
          </Routes>
        )}
      </MemoryRouter>
    </SourcesProvider>
  );
}

describe("Layout", () => {
  beforeEach(() => {
    // Keep the SourcesProvider load from doing real I/O. A never-resolving
    // promise leaves it in the loading state; the Footer still renders its
    // disclaimer (Req 13.1), which is all these tests need.
    vi.stubGlobal(
      "fetch",
      vi.fn(() => new Promise<Response>(() => {}))
    );
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  it("renders SkipLink, Nav, a focusable #main, and the Footer in order", () => {
    renderAt("/", <p>page content</p>);

    const skip = screen.getByRole("link", { name: /skip to main content/i });
    expect(skip).toHaveAttribute("href", "#main");

    const main = document.getElementById("main");
    expect(main).not.toBeNull();
    expect(main?.tagName).toBe("MAIN");
    // #main is programmatically focusable for route-change focus (Req 15.7).
    expect(main).toHaveAttribute("tabindex", "-1");

    expect(screen.getByRole("navigation", { name: /primary/i })).toBeInTheDocument();
    expect(screen.getByText("page content")).toBeInTheDocument();
    expect(
      screen.getByText("Not medical advice. Index, not prediction.")
    ).toBeInTheDocument();
  });

  it("marks the active route with aria-current='page' and a visible active class", () => {
    renderAt("/what");

    const activeLink = screen.getByRole("link", { name: "WHAT" });
    expect(activeLink).toHaveAttribute("aria-current", "page");
    expect(activeLink).toHaveClass("is-active");

    // A non-active link has neither.
    const homeLink = screen.getByRole("link", { name: "Home" });
    expect(homeLink).not.toHaveAttribute("aria-current", "page");
    expect(homeLink).not.toHaveClass("is-active");
  });

  it("does not mark Home active on a non-root route (end-matching)", () => {
    renderAt("/where");
    const homeLink = screen.getByRole("link", { name: "Home" });
    expect(homeLink).not.toHaveClass("is-active");
    const whereLink = screen.getByRole("link", { name: "WHERE" });
    expect(whereLink).toHaveClass("is-active");
  });

  it("moves keyboard focus to #main after a route renders (Req 15.7)", async () => {
    renderAt("/", <p>focused page</p>);
    const main = document.getElementById("main");
    await waitFor(() => expect(document.activeElement).toBe(main));
  });

  it("Nav links to Home, WHAT, WHERE, Method, and Build", () => {
    render(
      <MemoryRouter>
        <Nav />
      </MemoryRouter>
    );
    expect(screen.getByRole("link", { name: "Home" })).toHaveAttribute("href", "/");
    expect(screen.getByRole("link", { name: "WHAT" })).toHaveAttribute("href", "/what");
    expect(screen.getByRole("link", { name: "WHERE" })).toHaveAttribute("href", "/where");
    expect(screen.getByRole("link", { name: "Method" })).toHaveAttribute("href", "/method");
    expect(screen.getByRole("link", { name: "Build" })).toHaveAttribute("href", "/build");
  });

  it("SkipLink targets #main", () => {
    render(
      <MemoryRouter>
        <SkipLink />
      </MemoryRouter>
    );
    expect(
      screen.getByRole("link", { name: /skip to main content/i })
    ).toHaveAttribute("href", "#main");
  });
});
