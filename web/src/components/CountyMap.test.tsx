// Example/edge-case tests for CountyMap (task 10.2).
//
// Covers: the zero-Where_Data empty message (Req 9.6); the unknown state —
// both a county with NO matching entry and a county in the Unknown_Distance
// state render the hatched "unknown" fill in the map and the literal "unknown"
// (never zero, never blank) in the text-alternative table (Req 9.3, 9.4,
// 10.2); the disease `<select>` updating both the map and the table
// (Req 10.4); and the SVG's `aria-describedby` association to the table
// (Req 10.2). jsdom + @testing-library/react; no network.
//
// Requirements: 9.3, 9.4, 9.6, 10.2, 10.4

import { describe, it, expect } from "vitest";
import { render, screen, fireEvent, within } from "@testing-library/react";
import CountyMap, {
  NO_DISTANCE_DATA_MESSAGE,
  UNKNOWN_TEXT,
} from "./CountyMap";
import type { CountyFeature, WhereEntry } from "../data/types";

// --- Fixtures ---------------------------------------------------------------

// A trivial 1x1 square polygon; the exact geometry does not matter for these
// tests, only that d3-geo can project a valid closed ring for each county.
function squarePolygon(ox: number, oy: number): CountyFeature["geometry"] {
  return {
    type: "Polygon",
    coordinates: [
      [
        [ox, oy],
        [ox + 1, oy],
        [ox + 1, oy + 1],
        [ox, oy + 1],
        [ox, oy],
      ],
    ],
  };
}

function county(fips: string, ox: number, oy: number): CountyFeature {
  return {
    type: "Feature",
    properties: { county_fips: fips },
    geometry: squarePolygon(ox, oy),
  };
}

// Three MA counties. Geometry offsets keep the projection non-degenerate.
const FEATURES: readonly CountyFeature[] = [
  county("25001", -71, 41),
  county("25003", -73, 42),
  county("25005", -71, 42),
];

const ASTHMA = { measureId: "CASTHMA", condition: "Asthma" } as const;
const DIABETES = { measureId: "DIABETES", condition: "Diabetes" } as const;

// Disease A (Asthma):
//   25001 Barnstable -> numeric bucket (10 mi)
//   25003 Berkshire  -> Unknown_Distance (null + has_verified_site false)
//   25005 Bristol    -> NO entry at all (missing)
//
// Disease B (Diabetes):
//   25001 Barnstable -> Unknown_Distance (flips from bucket -> unknown)
//   25003 Berkshire  -> numeric bucket (20 mi) (flips unknown -> bucket)
//   25005 Bristol    -> numeric bucket (5 mi)  (flips missing -> bucket)
const WHERE_DATA: readonly WhereEntry[] = [
  {
    county_fips: "25001",
    county: "Barnstable",
    condition: "Asthma",
    measure_id: "CASTHMA",
    miles_to_nearest: 10,
    has_verified_site: true,
  },
  {
    county_fips: "25003",
    county: "Berkshire",
    condition: "Asthma",
    measure_id: "CASTHMA",
    miles_to_nearest: null,
    has_verified_site: false,
  },
  // Note: no CASTHMA entry for 25005 Bristol -> missing -> unknown.

  {
    county_fips: "25001",
    county: "Barnstable",
    condition: "Diabetes",
    measure_id: "DIABETES",
    miles_to_nearest: null,
    has_verified_site: false,
  },
  {
    county_fips: "25003",
    county: "Berkshire",
    condition: "Diabetes",
    measure_id: "DIABETES",
    miles_to_nearest: 20,
    has_verified_site: true,
  },
  {
    county_fips: "25005",
    county: "Bristol",
    condition: "Diabetes",
    measure_id: "DIABETES",
    miles_to_nearest: 5,
    has_verified_site: true,
  },
];

// --- Helpers ----------------------------------------------------------------

// Find the <tr> whose row-header matches `countyName`, and return its distance
// <td> text. The table has one <th scope="row"> (county) + one <td> (distance).
function distanceCellFor(countyName: string): string {
  const rowHeader = screen.getByRole("rowheader", { name: countyName });
  const row = rowHeader.closest("tr");
  expect(row).not.toBeNull();
  const cell = within(row as HTMLTableRowElement).getByRole("cell");
  return cell.textContent ?? "";
}

// Return the fill attribute of the county <path> whose <title> names the county.
function pathFillFor(countyName: string): string {
  const titles = Array.from(document.querySelectorAll("title"));
  const title = titles.find((t) =>
    (t.textContent ?? "").startsWith(`${countyName}:`)
  );
  expect(title, `expected a <title> for ${countyName}`).toBeTruthy();
  const path = title!.closest("path");
  expect(path, `expected a <path> for ${countyName}`).not.toBeNull();
  return (path as SVGPathElement).getAttribute("fill") ?? "";
}

// --- Tests ------------------------------------------------------------------

describe("CountyMap", () => {
  it("shows the no-distance-data message when whereData is empty (Req 9.6)", () => {
    render(
      <CountyMap
        features={FEATURES}
        whereData={[]}
        diseaseOptions={[ASTHMA, DIABETES]}
      />
    );

    expect(
      screen.getByText(new RegExp(NO_DISTANCE_DATA_MESSAGE))
    ).toBeInTheDocument();
    // No map image and no table when there is no data to drive them.
    expect(screen.queryByRole("img")).toBeNull();
    expect(screen.queryByRole("table")).toBeNull();
  });

  it("renders unknown (hatched + literal 'unknown') for both a missing entry and an Unknown_Distance county (Req 9.3, 9.4, 10.2)", () => {
    render(<CountyMap features={FEATURES} whereData={WHERE_DATA} />);

    // The default selected disease is the first option derived from whereData,
    // which is Asthma (first-seen measure_id).
    expect(screen.getByRole("combobox", { name: "Disease" })).toHaveValue(
      "CASTHMA"
    );

    // 25003 Berkshire is in the Unknown_Distance state for Asthma.
    expect(distanceCellFor("Berkshire")).toBe(UNKNOWN_TEXT);
    // 25005 has NO Asthma entry at all; with no entry to name it, the row is
    // labeled by its FIPS (the component's documented fallback) -> also unknown.
    expect(distanceCellFor("25005")).toBe(UNKNOWN_TEXT);

    // Neither unknown cell is a number (not zero, not blank).
    expect(distanceCellFor("Berkshire")).not.toMatch(/\d/);
    expect(distanceCellFor("Berkshire")).not.toBe("");
    // The missing-entry row's label is its FIPS, but its distance cell is the
    // literal "unknown" — assert the distance text, not the FIPS label.
    expect(distanceCellFor("25005")).not.toBe("");

    // The numeric county keeps its mileage text, distinct from "unknown".
    expect(distanceCellFor("Barnstable")).toBe("10 mi");

    // Map: both unknown counties use the hatch pattern fill (url(#...hatch)).
    expect(pathFillFor("Berkshire")).toMatch(/^url\(#.*hatch.*\)$/);
    expect(pathFillFor("25005")).toMatch(/^url\(#.*hatch.*\)$/);
    // The numeric county does NOT use the hatch fill (it uses a bucket colour).
    expect(pathFillFor("Barnstable")).not.toMatch(/hatch/);
    expect(pathFillFor("Barnstable")).toContain("var(--seq-");
  });

  it("updates both the map and the table when the disease selector changes (Req 10.4)", () => {
    render(<CountyMap features={FEATURES} whereData={WHERE_DATA} />);

    const select = screen.getByRole("combobox", { name: "Disease" });

    // --- Before: Asthma selected. ---
    // Barnstable is a numeric bucket; Berkshire is unknown.
    expect(distanceCellFor("Barnstable")).toBe("10 mi");
    expect(pathFillFor("Barnstable")).toContain("var(--seq-");
    expect(distanceCellFor("Berkshire")).toBe(UNKNOWN_TEXT);
    expect(pathFillFor("Berkshire")).toMatch(/hatch/);

    // --- Switch to Diabetes. ---
    fireEvent.change(select, { target: { value: "DIABETES" } });
    expect(select).toHaveValue("DIABETES");

    // Barnstable flips bucket -> unknown; Berkshire flips unknown -> bucket;
    // Bristol flips missing -> bucket. Both map and table reflect the change.
    expect(distanceCellFor("Barnstable")).toBe(UNKNOWN_TEXT);
    expect(pathFillFor("Barnstable")).toMatch(/hatch/);

    expect(distanceCellFor("Berkshire")).toBe("20 mi");
    expect(pathFillFor("Berkshire")).toContain("var(--seq-");

    // 25005 had no Asthma entry (labeled by FIPS, unknown) and now has a
    // Diabetes entry naming it "Bristol" with a numeric distance.
    expect(distanceCellFor("Bristol")).toBe("5 mi");
    expect(pathFillFor("Bristol")).toContain("var(--seq-");
  });

  it("associates the SVG image with the text-alternative table via aria-describedby (Req 10.2)", () => {
    render(<CountyMap features={FEATURES} whereData={WHERE_DATA} />);

    const svg = screen.getByRole("img");
    const describedBy = svg.getAttribute("aria-describedby");
    expect(describedBy).toBeTruthy();

    const table = screen.getByRole("table");
    expect(table.id).toBe(describedBy);
  });
});
