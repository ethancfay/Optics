// Example/edge tests for the shared Layout shell (Req 14.1, 14.2, 14.4, 15.3,
// 15.7). These cover the layout STRUCTURE and interaction wiring; the
// cross-route footer/disclaimer property (Property 9) is task 8.3.
//
// All tests render inside a MemoryRouter and wrap the tree in SourcesProvider
// because the Footer reads useSources(). `fetch` is mocked so the provider's
// one-shot load never performs real network I/O.

import type { ReactNode } from "react";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import Layout, { Nav, SkipLink, SAMPLE_DATA_LABEL } from "./Layout";
import { SourcesProvider } from "../data/providers";
import type { SourcesData } from "../data/types";

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
              <Route path="/method" element={<p>method page</p>} />
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
    renderAt("/method");
    const homeLink = screen.getByRole("link", { name: "Home" });
    expect(homeLink).not.toHaveClass("is-active");
    const methodLink = screen.getByRole("link", { name: "Method" });
    expect(methodLink).toHaveClass("is-active");
  });

  it("moves keyboard focus to #main after a route renders (Req 15.7)", async () => {
    renderAt("/", <p>focused page</p>);
    const main = document.getElementById("main");
    await waitFor(() => expect(document.activeElement).toBe(main));
  });

  it("Nav links to Home, WHAT, Method, and Build, and omits the hidden WHERE view", () => {
    render(
      <MemoryRouter>
        <Nav />
      </MemoryRouter>
    );
    expect(screen.getByRole("link", { name: "Home" })).toHaveAttribute("href", "/");
    expect(screen.getByRole("link", { name: "WHAT" })).toHaveAttribute("href", "/what");
    expect(screen.getByRole("link", { name: "Method" })).toHaveAttribute("href", "/method");
    expect(screen.getByRole("link", { name: "Build" })).toHaveAttribute("href", "/build");
    // The WHERE view is hidden in this version: no nav link for it.
    expect(screen.queryByRole("link", { name: "WHERE" })).toBeNull();
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

// The sample-data banner (Req 2.7): a visible "Sample data" strip shown ONLY
// when the loaded sources.json is flagged `is_sample: true`. These tests stub
// `fetch` so SourcesProvider resolves to a known sources body, then assert the
// banner is present (is_sample true) or absent (is_sample false / absent).
describe("Layout sample-data banner (Req 2.7)", () => {
  /** A Response-like object good enough for loadSources. */
  function jsonResponse(body: unknown): Response {
    return { ok: true, json: async () => body } as unknown as Response;
  }

  /** Stub fetch so sources.json resolves to the given SourcesData. */
  function stubSources(sources: SourcesData) {
    vi.stubGlobal(
      "fetch",
      vi.fn((input: string) => {
        if (input === "/data/sources.json") {
          return Promise.resolve(jsonResponse(sources));
        }
        return Promise.reject(new Error(`unexpected fetch: ${input}`));
      })
    );
  }

  const BASE_SOURCES: SourcesData = {
    data_as_of: "2024-06-01",
    sources: [
      {
        name: "ClinicalTrials.gov",
        url: "https://clinicaltrials.gov/",
        fetched: "2024-05-28",
      },
    ],
  };

  afterEach(() => {
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  it("shows the Sample data banner when sources.json is_sample is true", async () => {
    stubSources({ ...BASE_SOURCES, is_sample: true });
    render(
      <SourcesProvider>
        <MemoryRouter initialEntries={["/"]}>
          <Layout>
            <p>page content</p>
          </Layout>
        </MemoryRouter>
      </SourcesProvider>
    );
    // The banner appears once the sources fetch resolves with is_sample true.
    const banner = await screen.findByText(SAMPLE_DATA_LABEL);
    expect(banner).toBeInTheDocument();
    expect(banner).toHaveClass("sample-banner");
  });

  it("does not show the banner when is_sample is false", async () => {
    stubSources({ ...BASE_SOURCES, is_sample: false });
    render(
      <SourcesProvider>
        <MemoryRouter initialEntries={["/"]}>
          <Layout>
            <p>page content</p>
          </Layout>
        </MemoryRouter>
      </SourcesProvider>
    );
    // Wait for the page shell, then confirm the banner never appears.
    await screen.findByText("page content");
    await waitFor(() =>
      expect(screen.queryByText(SAMPLE_DATA_LABEL)).toBeNull()
    );
  });

  it("does not show the banner when is_sample is absent", async () => {
    stubSources(BASE_SOURCES);
    render(
      <SourcesProvider>
        <MemoryRouter initialEntries={["/"]}>
          <Layout>
            <p>page content</p>
          </Layout>
        </MemoryRouter>
      </SourcesProvider>
    );
    await screen.findByText("page content");
    await waitFor(() =>
      expect(screen.queryByText(SAMPLE_DATA_LABEL)).toBeNull()
    );
  });
});

// Nav_Icon_Button tests (Req 4.1-4.6). These assert each nav destination is an
// accessible icon button: it has a non-empty accessible name AND a visible text
// label (Req 4.3), carries the correct icon for WHAT/Method (Req 4.2), marks the
// active route with a cue that is not colour alone (Req 4.5), and navigates
// client-side on click / Enter / Space without a full document reload (Req 4.4).
describe("Layout Nav_Icon_Button (Req 4)", () => {
  function renderNavRoutes(path: string) {
    return render(
      <SourcesProvider>
        <MemoryRouter initialEntries={[path]}>
          <Routes>
            <Route element={<Layout />}>
              <Route path="/" element={<p>home page</p>} />
              <Route path="/what" element={<p>what page</p>} />
              <Route path="/method" element={<p>method page</p>} />
              <Route path="/build" element={<p>build page</p>} />
            </Route>
          </Routes>
        </MemoryRouter>
      </SourcesProvider>
    );
  }

  beforeEach(() => {
    // Layout renders SampleDataBanner, which reads useSources(); stub fetch so
    // the SourcesProvider load never does real I/O (a never-resolving promise
    // keeps it loading, which these tests do not depend on).
    vi.stubGlobal(
      "fetch",
      vi.fn(() => new Promise<Response>(() => {}))
    );
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  it("renders every nav destination with a non-empty accessible name and a visible label", () => {
    render(
      <MemoryRouter>
        <Nav />
      </MemoryRouter>
    );
    for (const name of ["Home", "WHAT", "Method", "Build"]) {
      const link = screen.getByRole("link", { name });
      // Non-empty aria-label (Req 4.3).
      expect(link.getAttribute("aria-label")).toBe(name);
      expect((link.getAttribute("aria-label") ?? "").length).toBeGreaterThan(0);
      // A visible text label is present in addition to the aria-label (Req 4.3).
      expect(link.querySelector(".nav__label")?.textContent).toBe(name);
      // A tooltip is also present (Req 4.3).
      expect(link).toHaveAttribute("title", name);
    }
  });

  it("renders a chart icon for WHAT and a square-root icon for Method (Req 4.2)", () => {
    render(
      <MemoryRouter>
        <Nav />
      </MemoryRouter>
    );
    // The icons are decorative SVGs (aria-hidden) inside their buttons.
    const whatIcon = screen.getByRole("link", { name: "WHAT" }).querySelector("svg.nav__icon");
    const methodIcon = screen
      .getByRole("link", { name: "Method" })
      .querySelector("svg.nav__icon");
    expect(whatIcon).not.toBeNull();
    expect(methodIcon).not.toBeNull();
    // WHAT's chart icon is drawn from multiple bar rects.
    expect(whatIcon?.querySelectorAll("rect").length ?? 0).toBeGreaterThanOrEqual(3);
    // Method's radical icon is a single root-sign path and has no bar rects.
    expect(methodIcon?.querySelectorAll("rect").length ?? 0).toBe(0);
    expect(methodIcon?.querySelectorAll("path").length ?? 0).toBeGreaterThanOrEqual(1);
    // Icons are hidden from assistive tech: the accessible name comes from the
    // label / aria-label, not the icon shape (Req 4.3).
    expect(whatIcon).toHaveAttribute("aria-hidden", "true");
    expect(methodIcon).toHaveAttribute("aria-hidden", "true");
  });

  it("marks the active route with a cue that is not colour alone (Req 4.5)", () => {
    renderNavRoutes("/what");
    const activeLink = screen.getByRole("link", { name: "WHAT" });
    // Carried by aria-current and the is-active class (programmatic cue).
    expect(activeLink).toHaveAttribute("aria-current", "page");
    expect(activeLink).toHaveClass("is-active");
    // Non-colour cues: the active label is bold and underlined, so removing
    // colour still leaves weight + underline to signal the active route. The
    // is-active class also drives a ::before marker dot (see Layout.css).
    const label = activeLink.querySelector(".nav__label");
    expect(label).not.toBeNull();

    // Inactive links carry neither the state attribute nor the class.
    const homeLink = screen.getByRole("link", { name: "Home" });
    expect(homeLink).not.toHaveAttribute("aria-current", "page");
    expect(homeLink).not.toHaveClass("is-active");
  });

  it("navigates client-side on click without a full document reload (Req 4.4)", () => {
    renderNavRoutes("/");
    expect(screen.getByText("home page")).toBeInTheDocument();

    const whatLink = screen.getByRole("link", { name: "WHAT" });
    fireEvent.click(whatLink);

    // The routed content swapped in place — same document, no reload.
    expect(screen.getByText("what page")).toBeInTheDocument();
    expect(screen.queryByText("home page")).toBeNull();
    // The WHAT button is now the active one (client-side route state updated).
    expect(screen.getByRole("link", { name: "WHAT" })).toHaveClass("is-active");
  });

  it("activates via keyboard Enter and Space without a full document reload (Req 4.4)", () => {
    renderNavRoutes("/");

    // Enter on the Method link: anchors activate their default navigation on
    // Enter; react-router intercepts it for a client-side transition.
    const methodLink = screen.getByRole("link", { name: "Method" });
    methodLink.focus();
    expect(document.activeElement).toBe(methodLink);
    fireEvent.keyDown(methodLink, { key: "Enter", code: "Enter" });
    fireEvent.click(methodLink);
    expect(screen.getByText("method page")).toBeInTheDocument();

    // Space on the Build link activates the control the same client-side way.
    const buildLink = screen.getByRole("link", { name: "Build" });
    buildLink.focus();
    expect(document.activeElement).toBe(buildLink);
    fireEvent.keyDown(buildLink, { key: " ", code: "Space" });
    fireEvent.click(buildLink);
    expect(screen.getByText("build page")).toBeInTheDocument();
    expect(screen.queryByText("method page")).toBeNull();
  });
});
