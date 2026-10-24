// CountyMap — the WHERE view's accessible SVG choropleth of the 14 MA counties
// plus its text-alternative table (Req 9, 10, 15.2, 15.5, 15.8).
//
// This component is purely presentational: it receives the county boundaries
// (`features`, a validated GeoJSON FeatureCollection's features) and the
// Where_Data (`whereData`) as props from the Where page (task 12.9), which owns
// the providers and the loading / error / empty wiring. CountyMap never
// fetches.
//
// For a selected disease it renders, for every county feature, one SVG `<path>`
// projected with `d3-geo` and filled by `resolveCountyState` (../data/where):
//
//   - A county whose Where_Entry has a numeric distance to the nearest VERIFIED
//     recruiting site is shaded by its sequential-ramp bucket (`--seq-1`..`-5`,
//     nearest -> farthest) (Req 9.1).
//   - A county in the Unknown_Distance state OR with no matching Where_Entry for
//     the selected disease renders with a HATCHED "unknown" pattern — never the
//     zero-distance bucket colour, never blank (Req 9.3, 9.4). The pattern plus
//     the "unknown" legend/table text mean the unknown state is conveyed by more
//     than colour alone (Req 9.5, 15.2).
//
// A `<select>` disease control updates both the map and the text-alternative
// table (Req 9.2, 10.4). The SVG carries `role="img"` and `aria-describedby`
// pointing at a data table that lists each county's `county` label and its
// distance to the nearest verified recruiting site, showing the literal text
// "unknown" (not a number, not blank) for counties in the unknown state
// (Req 10.1, 10.2, 10.3, 15.5, 15.8). The legend text names every bucket
// including "unknown" (Req 9.5). No Forbidden_Terms appear in any label.

import { useId, useMemo, useState } from "react";
import { geoMercator, geoPath } from "d3-geo";
import type { ExtendedFeatureCollection } from "d3-geo";
import type { CountyFeature, WhereEntry } from "../data/types";
import {
  BUCKET_UPPER_BOUNDS_MILES,
  resolveCountyState,
  type CountyState,
  type DistanceBucket,
} from "../data/where";

/** Message shown when there is no Where_Data to drive the map (Req 9.6). */
export const NO_DISTANCE_DATA_MESSAGE = "No distance data is available";

/** The literal text shown for a county in the unknown state (Req 10.2). */
export const UNKNOWN_TEXT = "unknown";

/** Intrinsic SVG viewBox the projection is fit to; the SVG scales responsively. */
const MAP_WIDTH = 640;
const MAP_HEIGHT = 420;

/** CSS custom-property fill for each distance bucket (1 = nearest .. 5 = farthest). */
const BUCKET_FILL: Readonly<Record<DistanceBucket, string>> = {
  1: "var(--seq-1)",
  2: "var(--seq-2)",
  3: "var(--seq-3)",
  4: "var(--seq-4)",
  5: "var(--seq-5)",
};

/** A disease the selector can choose, identified by its stable `measure_id`. */
export interface DiseaseOption {
  measureId: string;
  condition: string;
}

export interface CountyMapProps {
  /** The 14 MA county features (a validated GeoJSON FeatureCollection's features). */
  features: readonly CountyFeature[];
  /** Where_Data entries for one or more diseases. */
  whereData: readonly WhereEntry[];
  /**
   * Optional explicit selectable diseases (e.g. derived from What_Data). When
   * omitted, the options are derived from the distinct `(measure_id, condition)`
   * pairs present in `whereData`, so the selector is self-contained.
   */
  diseaseOptions?: readonly DiseaseOption[];
}

/**
 * Human-readable label for a resolved county state, used by both the legend and
 * the text-alternative table. Numeric buckets are described as a miles-to-
 * nearest-verified-site range; the unknown state is the literal "unknown".
 */
function bucketRangeLabel(bucket: DistanceBucket): string {
  const bounds = BUCKET_UPPER_BOUNDS_MILES;
  // bucket 1 -> "0–10 mi"; middle buckets -> "10–25 mi"; last -> ">100 mi".
  if (bucket === 1) {
    return `0–${bounds[0]} mi`;
  }
  if (bucket <= bounds.length) {
    const lower = bounds[bucket - 2];
    const upper = bounds[bucket - 1];
    return `${lower}–${upper} mi`;
  }
  // bucket === bounds.length + 1 (the farthest, open-ended bucket).
  return `>${bounds[bounds.length - 1]} mi`;
}

/**
 * Derive the distinct selectable diseases from Where_Data, preserving first-seen
 * order and de-duplicating by `measure_id`.
 */
function deriveDiseaseOptions(
  whereData: readonly WhereEntry[]
): DiseaseOption[] {
  const seen = new Set<string>();
  const options: DiseaseOption[] = [];
  for (const entry of whereData) {
    if (!seen.has(entry.measure_id)) {
      seen.add(entry.measure_id);
      options.push({
        measureId: entry.measure_id,
        condition: entry.condition,
      });
    }
  }
  return options;
}

/**
 * The text for a county's distance cell in the text alternative: the miles to
 * the nearest verified recruiting site, or the literal "unknown" (Req 10.2).
 * Never blank, never a fabricated number.
 */
function distanceCellText(state: CountyState): string {
  if (state.kind === "unknown") {
    return UNKNOWN_TEXT;
  }
  const miles = state.miles;
  // Show whole miles plainly; keep a decimal only when it carries information.
  const rounded = Number.isInteger(miles) ? miles : Math.round(miles * 10) / 10;
  return `${rounded} mi`;
}

/**
 * Accessible choropleth of MA counties for the selected disease, with a disease
 * selector, a text legend (including the unknown state), and a text-alternative
 * table associated via `aria-describedby`.
 */
export function CountyMap({
  features,
  whereData,
  diseaseOptions,
}: CountyMapProps) {
  // Stable ids so the SVG, its describing table, and the hatch pattern are
  // uniquely addressable even if several maps mount on one page.
  const baseId = useId();
  const tableId = `${baseId}-table`;
  const hatchId = `${baseId}-hatch`;
  const selectId = `${baseId}-select`;

  const options = useMemo(
    () => diseaseOptions ?? deriveDiseaseOptions(whereData),
    [diseaseOptions, whereData]
  );

  // The selected disease defaults to the first option. Kept in state so the
  // `<select>` drives both the map and the table (Req 9.2, 10.4).
  const [selectedMeasureId, setSelectedMeasureId] = useState<string>(
    () => options[0]?.measureId ?? ""
  );

  // Guard against a selection that no longer exists (e.g. options changed):
  // fall back to the first available option.
  const activeMeasureId = options.some(
    (o) => o.measureId === selectedMeasureId
  )
    ? selectedMeasureId
    : options[0]?.measureId ?? "";

  const activeCondition =
    options.find((o) => o.measureId === activeMeasureId)?.condition ?? "";

  // Build the d3-geo projection fit to the whole collection, and a path
  // generator from it. Recomputed only when the features change.
  const pathFor = useMemo(() => {
    if (features.length === 0) {
      return null;
    }
    const collection: ExtendedFeatureCollection = {
      type: "FeatureCollection",
      features: features as CountyFeature[],
    };
    const projection = geoMercator().fitSize([MAP_WIDTH, MAP_HEIGHT], collection);
    return geoPath(projection);
  }, [features]);

  // Resolve each county's state once for the active disease; shared by the map
  // paths and the text-alternative rows so they can never disagree.
  const rows = useMemo(
    () =>
      features.map((feature) => {
        const fips = feature.properties.county_fips;
        const state = resolveCountyState(whereData, activeMeasureId, fips);
        const whereEntry = whereData.find(
          (e) => e.measure_id === activeMeasureId && e.county_fips === fips
        );
        return {
          fips,
          // County label comes from Where_Data (the GeoJSON carries only FIPS);
          // fall back to the FIPS code if no entry names the county.
          county: whereEntry?.county ?? fips,
          state,
          feature,
        };
      }),
    [features, whereData, activeMeasureId]
  );

  // No Where_Data at all: render the explicit empty message (Req 9.6). The page
  // also guards the empty state, but handling it here keeps the component total.
  if (whereData.length === 0) {
    return (
      <section className="county-map" aria-label="Distance to nearest verified recruiting site by county">
        <p role="status" className="county-map__empty">
          {NO_DISTANCE_DATA_MESSAGE}.
        </p>
      </section>
    );
  }

  const describedCondition =
    activeCondition.length > 0 ? ` for ${activeCondition}` : "";

  return (
    <section
      className="county-map"
      aria-label="Distance to nearest verified recruiting site by county"
    >
      <div className="county-map__controls">
        <label htmlFor={selectId}>Disease</label>{" "}
        <select
          id={selectId}
          className="county-map__select"
          value={activeMeasureId}
          onChange={(event) => setSelectedMeasureId(event.target.value)}
        >
          {options.map((option) => (
            <option key={option.measureId} value={option.measureId}>
              {option.condition}
            </option>
          ))}
        </select>
      </div>

      {/* Text legend: every bucket plus the unknown state, so meaning is never
          carried by colour alone (Req 9.5, 15.2). */}
      <ul className="county-map__legend" aria-label="Map legend">
        {([1, 2, 3, 4, 5] as DistanceBucket[]).map((bucket) => (
          <li key={bucket} className="county-map__legend-item">
            <span
              className="county-map__swatch"
              style={{ backgroundColor: BUCKET_FILL[bucket] }}
              aria-hidden="true"
            />
            <span>{bucketRangeLabel(bucket)}</span>
          </li>
        ))}
        <li className="county-map__legend-item">
          <span
            className="county-map__swatch county-map__swatch--unknown"
            aria-hidden="true"
          />
          <span>{UNKNOWN_TEXT}</span>
        </li>
      </ul>

      <svg
        className="county-map__svg"
        role="img"
        aria-describedby={tableId}
        aria-label={`Massachusetts counties shaded by distance to the nearest verified recruiting site${describedCondition}. Counties with no distance data are shown as unknown.`}
        viewBox={`0 0 ${MAP_WIDTH} ${MAP_HEIGHT}`}
        preserveAspectRatio="xMidYMid meet"
      >
        <defs>
          {/* Hatch pattern for the unknown state, paired with --unknown fill so
              the unknown county is distinguished by texture, not colour alone. */}
          <pattern
            id={hatchId}
            patternUnits="userSpaceOnUse"
            width="6"
            height="6"
            patternTransform="rotate(45)"
          >
            <rect width="6" height="6" fill="var(--unknown)" />
            <line
              x1="0"
              y1="0"
              x2="0"
              y2="6"
              stroke="var(--ink)"
              strokeWidth="1.5"
            />
          </pattern>
        </defs>

        {pathFor &&
          rows.map(({ fips, county, state, feature }) => {
            const d = pathFor(feature) ?? "";
            const fill =
              state.kind === "unknown"
                ? `url(#${hatchId})`
                : BUCKET_FILL[state.bucket];
            const label =
              state.kind === "unknown"
                ? `${county}: ${UNKNOWN_TEXT}`
                : `${county}: ${distanceCellText(state)} to nearest verified recruiting site`;
            return (
              <path
                key={fips}
                className="county-map__county"
                d={d}
                fill={fill}
                stroke="var(--ink)"
                strokeWidth={0.5}
              >
                <title>{label}</title>
              </path>
            );
          })}
      </svg>

      {/* Text alternative: one row per county with its distance to the nearest
          verified recruiting site, "unknown" (not a number, not blank) for the
          unknown state (Req 10.1, 10.2, 10.3). */}
      <table id={tableId} className="county-map__table">
        <caption>
          Distance to the nearest verified recruiting site by Massachusetts
          county
          {describedCondition}
        </caption>
        <thead>
          <tr>
            <th scope="col">County</th>
            <th scope="col">
              Distance to nearest verified recruiting site
            </th>
          </tr>
        </thead>
        <tbody>
          {rows.map(({ fips, county, state }) => (
            <tr key={fips}>
              <th scope="row">{county}</th>
              <td>{distanceCellText(state)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  );
}

// Export both a named and default binding so the Where page can import either form.
export default CountyMap;
