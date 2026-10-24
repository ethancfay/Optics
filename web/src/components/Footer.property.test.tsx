// Feature: dashboard, Property 9: The footer and its disclaimer appear on every page
//
// Validates: Requirements 13.1, 13.2
//
// The Footer is rendered by the shared Layout on EVERY route, and its
// Disclaimer_Text must appear on every page regardless of the Sources load
// state (Req 13.1, 13.2). We mount the app's REAL routing table (`AppRoutes`)
// and the app-wide `SourcesProvider` under a MemoryRouter — exactly the
// wiring `App.tsx` uses — and, for every route in the routing table, assert
// that the exact Footer Disclaimer_Text is present.
//
// The property generates over the route set (`numRuns: 100` across the routes:
// `/`, `/what`, `/investigate/:measureId`, `/evidence/:measureId`, `/where`,
// `/method`, `/build`, and an unknown `*`/NotFound path).
//
// `fetch` is MOCKED to NEVER resolve, so Sources_Data (and every other
// provider) stays in its `loading` state for the duration of the render. This
// makes the test the strongest form of the property: the disclaimer must show
// even while sources never load. No real network request is ever made.

import { afterEach, describe, expect, test, vi } from "vitest";
import fc from "fast-check";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";

import { AppRoutes } from "../App";
import { SourcesProvider } from "../data/providers";
// Import the real Disclaimer_Text constant — never hardcode it here, so the
// test stays in lock-step with the Footer's source of truth (Req 13.2).
import { DISCLAIMER_TEXT } from "./Footer";

/**
 * Every route in the app's routing table (see `AppRoutes` in `App.tsx`), plus
 * an unknown path that falls through to the `*` NotFound route. The id'd routes
 * use an arbitrary measure_id; because `fetch` never resolves, the pages render
 * their loading state and the exact id does not affect the Footer assertion.
 */
const ROUTES = [
  "/",
  "/what",
  "/investigate/CASTHMA",
  "/evidence/CASTHMA",
  "/where",
  "/method",
  "/build",
  "/this-route-does-not-exist", // -> `*` / NotFound
] as const;

afterEach(() => {
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
});

describe("Property 9: the footer disclaimer appears on every route", () => {
  test("every route in the routing table renders the exact Disclaimer_Text", () => {
    fc.assert(
      fc.property(fc.constantFrom(...ROUTES), (route) => {
        // A never-resolving fetch keeps Sources (and all providers) in the
        // loading state, proving the disclaimer renders independent of any
        // successful data load (Req 13.1, 13.2).
        vi.stubGlobal(
          "fetch",
          vi.fn(() => new Promise<Response>(() => {}))
        );

        const { unmount } = render(
          <SourcesProvider>
            <MemoryRouter initialEntries={[route]}>
              <AppRoutes />
            </MemoryRouter>
          </SourcesProvider>
        );

        try {
          // The exact Disclaimer_Text must be present on this route.
          expect(screen.getByText(DISCLAIMER_TEXT)).toBeInTheDocument();
        } finally {
          unmount();
          vi.unstubAllGlobals();
        }
      }),
      { numRuns: 100 }
    );
  });
});
