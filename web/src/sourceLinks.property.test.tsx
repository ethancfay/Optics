// Feature: dashboard, Property 8: Every source renders as a named link to its URL with its fetched date
//
// Validates: Requirements 11.3, 13.3
//
// For any valid Sources_Data, BOTH of the two source-link renderings hold:
//
//   - The FOOTER (Req 13.3) renders exactly one named link per Source_Entry
//     whose visible text is the source `name` and whose `href` is the source
//     `url`. The Footer does NOT show the fetched date.
//   - The METHOD page (Req 11.3) renders exactly one named link per Source_Entry
//     to its `url` AND additionally shows each source's `fetched` date.
//
// So each rendering contains exactly one link per source (text = name,
// href = url); the Method page additionally surfaces every source's fetched
// date. We supply the generated Sources_Data by MOCKING `useSources` so no
// router or fetch stub is needed for either component; both read `useSources`
// from `../data/providers`. The Footer and Method source links are plain <a>
// elements (no react-router <Link>), so no Router is required, but we keep a
// MemoryRouter wrapper as a harmless guard in case any nested context is needed.

import { afterEach, describe, expect, test, vi } from "vitest";
import fc from "fast-check";
import { cleanup, render, within } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import type { ReactElement } from "react";

import { Footer } from "./components/Footer";
import Method from "./pages/Method";
import type { LoadState, SourceEntry, SourcesData } from "./data/types";

// --- mock the Sources provider hook -----------------------------------------
//
// Both Footer and Method read `useSources()` from `../data/providers`. We mock
// the whole module and drive the hook from a mutable holder so each property run
// can install its own generated Sources_Data without re-mocking. `LoadStateView`
// lives in a different module (`../components/LoadStateView`) and only imports
// TYPES from providers, so mocking providers does not affect it.

let currentSourcesState: LoadState<SourcesData> = { status: "loading" };

vi.mock("./data/providers", () => ({
  useSources: () => currentSourcesState,
}));

afterEach(() => {
  cleanup();
});

// --- generators -------------------------------------------------------------

// A safe alphabet for source names: letters, digits, spaces, and a few
// punctuation marks. Deliberately excludes "@" and long digit runs so a
// generated name can never look like contact data (email / phone). We also
// strip generated values through `containsContactData` constraints implicitly
// by construction: no "@" means no email; names stay short of 10-digit runs.
const NAME_ALPHABET =
  "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz ().-";

const nameArb = fc
  .string({ unit: fc.constantFrom(...NAME_ALPHABET.split("")), minLength: 1, maxLength: 40 })
  .map((s) => s.trim())
  .filter((s) => s.length > 0);

// https URLs under a safe host/path alphabet. Distinct per source is guaranteed
// below by appending the array index, since the components key links by `url`.
const urlPathArb = fc.string({
  unit: fc.constantFrom(..."abcdefghijklmnopqrstuvwxyz0123456789-/".split("")),
  minLength: 0,
  maxLength: 30,
});

// fetched date in YYYY-MM-DD form.
const fetchedArb = fc
  .date({ min: new Date("2000-01-01T00:00:00Z"), max: new Date("2099-12-31T00:00:00Z") })
  .map((d) => d.toISOString().slice(0, 10));

const dataAsOfArb = fc
  .date({ min: new Date("2000-01-01T00:00:00Z"), max: new Date("2099-12-31T00:00:00Z") })
  .map((d) => d.toISOString().slice(0, 10));

// A Sources_Data with 1..N sources. URLs are made unique by appending the array
// index to the generated path so each Source_Entry has a distinct `url` (the
// components use `url` as the React key).
const sourcesDataArb: fc.Arbitrary<SourcesData> = fc
  .record({
    data_as_of: dataAsOfArb,
    is_sample: fc.option(fc.boolean(), { nil: undefined }),
    sources: fc.array(
      fc.record({ name: nameArb, url: urlPathArb, fetched: fetchedArb }),
      { minLength: 1, maxLength: 6 }
    ),
  })
  .map(({ data_as_of, is_sample, sources }) => ({
    data_as_of,
    ...(is_sample === undefined ? {} : { is_sample }),
    sources: sources.map((s, i) => ({
      name: s.name,
      url: `https://example.org/${s.url}#${i}`,
      fetched: s.fetched,
    })) as SourceEntry[],
  }));

// --- helpers ----------------------------------------------------------------

/** Render with a MemoryRouter guard (harmless for plain-<a> source links). */
function renderWithRouter(ui: ReactElement) {
  return render(<MemoryRouter>{ui}</MemoryRouter>);
}

// --- the property -----------------------------------------------------------

describe("Property 8: every source renders as a named link to its URL with its fetched date", () => {
  test("Footer and Method each render exactly one named link per source; Method also shows each fetched date", () => {
    fc.assert(
      fc.property(sourcesDataArb, (data) => {
        currentSourcesState = {
          status: "ready",
          data,
          omittedCount: 0,
          isSample: data.is_sample ?? false,
        };

        // --- FOOTER (Req 13.3): one named link per source, href = url, no date ---
        {
          const { container } = renderWithRouter(<Footer />);
          const list = container.querySelector(".footer__source-links");
          expect(list).not.toBeNull();
          const scope = within(list as HTMLElement);

          const links = scope.getAllByRole("link");
          // Exactly one link per source.
          expect(links.length).toBe(data.sources.length);

          data.sources.forEach((source) => {
            // Exactly one link whose accessible text is this source's name.
            const named = links.filter((a) => a.textContent === source.name);
            expect(named.length).toBe(1);
            // That link points at the source url.
            expect(named[0].getAttribute("href")).toBe(source.url);
          });

          // The Footer does not surface the fetched date (Req 13.3). The Footer
          // DOES render `data_as_of` ("Data as of <date>"), so a fetched date
          // that coincidentally equals `data_as_of` is excused — the point is
          // that the Footer never shows a source's fetched date as its own.
          const footerText = container.textContent ?? "";
          data.sources.forEach((source) => {
            if (source.fetched !== data.data_as_of) {
              expect(footerText.includes(source.fetched)).toBe(false);
            }
          });

          cleanup();
        }

        // --- METHOD (Req 11.3): one named link per source + each fetched date ---
        {
          const { container } = renderWithRouter(<Method />);
          const list = container.querySelector(".method-page__source-links");
          expect(list).not.toBeNull();
          const scope = within(list as HTMLElement);

          const links = scope.getAllByRole("link");
          // Exactly one link per source.
          expect(links.length).toBe(data.sources.length);

          data.sources.forEach((source) => {
            const named = links.filter((a) => a.textContent === source.name);
            expect(named.length).toBe(1);
            expect(named[0].getAttribute("href")).toBe(source.url);

            // Method additionally shows this source's fetched date, in the same
            // list item as its link (Req 11.3).
            const li = named[0].closest("li");
            expect(li).not.toBeNull();
            expect((li as HTMLElement).textContent ?? "").toContain(source.fetched);
          });

          cleanup();
        }
      }),
      { numRuns: 100 }
    );
  });
});
