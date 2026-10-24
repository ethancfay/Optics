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
