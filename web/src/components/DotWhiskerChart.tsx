// DotWhiskerChart + its Text_Alternative table (Req 5.1-5.6, 5.8, 5.11, 6.1-6.3,
// 6.5, 15.2, 15.5, 15.8).
//
// A pure, presentational component: it takes the diseases to plot as a prop and
// never fetches. The caller (What_View, task 12.2) sorts the entries via
// sortConditions before passing them, so this component renders them in the
// exact order received and keeps the chart and its text alternative in lockstep.
//
// It draws a single inline-SVG chart (no tabs): for every disease a horizontal
// whisker from `low` to `high` and a dot at `mid`, positioned with the shared
// `chartScale`. Each disease owns one row band, split into a left name column
// (vertically centred on the same row as its whisker) and the plot, which
// carries light gridlines and round numeric tick labels so a value can be read
// off the chart rather than estimated. Colour is never the sole carrier of
// meaning — every row also shows its text label and numeric values, and the SVG
// is programmatically associated (role="img" + aria-describedby) with a complete
// data table whose rows are keyboard-focusable controls that navigate to the
// Investigate page.

import { useId } from "react";
import { useNavigate } from "react-router-dom";
import type { WhatEntry } from "../data/types";
import { chartScale } from "../data/chartScale";
import { formatAxisTick } from "../data/axisTicks";
import "./DotWhiskerChart.css";

/** Props for {@link DotWhiskerChart}. Entries arrive already sorted by the caller. */
export interface DotWhiskerChartProps {
  /** Diseases to plot, in the exact order to render (chart and table). */
  entries: readonly WhatEntry[];
}

/** The fixed axis unit label (Req 5.4). */
export const AXIS_LABEL =
  "distinct recruiting MA studies per 100,000 affected adults (18+)";

/** Suffix added to the axis label while the log scale is in use (Req 22.4). */
export const LOG_SCALE_SUFFIX = " (log scale)";

/** Sentence added to the chart's accessible title in log mode (Req 22.4). */
export const LOG_SCALE_TITLE_NOTE =
  "The axis uses a log scale: each labeled step is ten times the one before.";

/** Placeholder text shown for any missing/unavailable table cell (Req 6.5). */
const UNAVAILABLE = "unavailable";

// SVG geometry. Each disease occupies one row band of height ROW_HEIGHT, split
// into a left NAME COLUMN (sized to the longest label, so no name is truncated)
// and the horizontal plot area. Putting the name and its whisker in the same
// band — name right-aligned into the gutter, whisker vertically centred beside
// it — is what lets a reader trace a value without a legend.
const PLOT_WIDTH = 640;
const PLOT_RIGHT = 16;
const ROW_HEIGHT = 32;
const TOP_PAD = 16;
const BOTTOM_PAD = 52; // tick labels + the axis unit label
const DOT_RADIUS = 5;

/** Name-column bounds (px in the SVG user space). */
const NAME_COLUMN_MIN = 96;
const NAME_COLUMN_MAX = 188;
/** Clearance between a name's right edge and the plot's left edge. */
const NAME_GAP = 14;
/** Conservative advance width of one character at the 12px row-label size. */
const NAME_CHAR_WIDTH = 6.8;

/**
 * Render a number for display, or the "unavailable" placeholder when the value
 * is missing or not a finite number (Req 6.5). Kept local so the SVG and the
 * table agree on what counts as unavailable.
 */
function displayNumber(value: number | null | undefined): string {
  if (value === null || value === undefined || !Number.isFinite(value)) {
    return UNAVAILABLE;
  }
  return String(value);
}

/**
 * Render a condition label for display, or the "unavailable" placeholder when
 * it is missing/empty (Req 6.5).
 */
function displayText(value: string | null | undefined): string {
  if (value === null || value === undefined || value.trim() === "") {
    return UNAVAILABLE;
  }
  return value;
}

export default function DotWhiskerChart({ entries }: DotWhiskerChartProps) {
  const navigate = useNavigate();

  // Stable, unique ids so the SVG can point at its text-alternative table and
  // the table can be used as an accessible description (Req 6.3, 15.5, 15.8).
  const baseId = useId();
  const tableId = `${baseId}-table`;
  const titleId = `${baseId}-title`;

  // Empty state: no diseases to plot (Req 5.7, 6.4). Still render the table
  // headers with no rows plus an explicit no-data note.
  if (entries.length === 0) {
    return (
      <section aria-label="Disease index chart">
        <p role="status">No diseases are available</p>
        <TextAlternative entries={[]} tableId={tableId} onSelect={() => {}} />
      </section>
    );
  }

  // The name column tracks the longest label, so a longer disease name widens
  // the gutter instead of colliding with its own whisker.
  const longestLabel = entries.reduce(
    (longest, entry) => Math.max(longest, displayText(entry.condition).length),
    0,
  );
  const nameColumnWidth = Math.min(
    NAME_COLUMN_MAX,
    Math.max(
      NAME_COLUMN_MIN,
      Math.round(longestLabel * NAME_CHAR_WIDTH) + NAME_GAP + 8,
    ),
  );

  // Shared horizontal scale mapping index values to x pixel positions so that
  // x(low) <= x(mid) <= x(high) for every disease (Req 5.1, 5.6, 22.6). It is
  // log10 when every low > 0 and linear from 0 otherwise (Req 22.1, 22.5). The
  // pixel range starts at the plot's left edge, i.e. right of the name column.
  const scale = chartScale(entries, [
    nameColumnWidth,
    nameColumnWidth + PLOT_WIDTH,
  ]);

  const width = nameColumnWidth + PLOT_WIDTH + PLOT_RIGHT;
  const plotTop = TOP_PAD;
  const plotBottom = TOP_PAD + entries.length * ROW_HEIGHT;
  const tickLabelY = plotBottom + 20;
  const axisLabelY = plotBottom + 42;
  const height = plotBottom + BOTTOM_PAD;

  // Ticks come with the scale: powers of ten in log mode (0.1, 1, 10 for the
  // shipped data), round linear values from 0 in the fallback (Req 22.3, 22.5).
  const ticks = scale.ticks;
  const isLog = scale.kind === "log";
  const axisLabel = isLog ? AXIS_LABEL + LOG_SCALE_SUFFIX : AXIS_LABEL;

  const handleSelect = (measureId: string) => {
    navigate(`/investigate/${measureId}`);
  };

  return (
    <section aria-label="Disease index chart">
      {/* The plot never shrinks below a legible width: on a phone the panel
          scrolls horizontally instead of shrinking its labels to a few pixels. */}
      <div className="dw-chart-scroll">
        <svg
          className="dw-chart"
          role="img"
          aria-labelledby={titleId}
          aria-describedby={tableId}
          viewBox={`0 0 ${width} ${height}`}
        >
          <title id={titleId}>
            {"Index range per disease, lowest midpoint first. Each disease " +
              "shows a whisker from its low to high value and a dot at its " +
              "midpoint." +
              (isLog ? ` ${LOG_SCALE_TITLE_NOTE}` : "")}
          </title>

          {/* Axis furniture, drawn first so every mark sits on top of it. The
              gridlines are decoration: the tick labels spell out the values they
              encode, and the text alternative carries the numbers themselves. */}
          <g aria-hidden="true">
            {ticks.map((tick) => (
              <line
                key={tick}
                className="dw-axis-grid"
                x1={scale.x(tick)}
                y1={plotTop}
                x2={scale.x(tick)}
                y2={plotBottom}
              />
            ))}
            {/* Baseline the tick labels hang from. */}
            <line
              className="dw-axis-baseline"
              x1={nameColumnWidth}
              y1={plotBottom}
              x2={nameColumnWidth + PLOT_WIDTH}
              y2={plotBottom}
            />
            {/* Divider between the name column and the plot. */}
            <line
              className="dw-axis-divider"
              x1={nameColumnWidth}
              y1={plotTop}
              x2={nameColumnWidth}
              y2={plotBottom}
            />
          </g>

          {entries.map((entry, index) => {
            const rowY = TOP_PAD + index * ROW_HEIGHT;
            const centerY = rowY + ROW_HEIGHT / 2;

            const hasLow = Number.isFinite(entry.low);
            const hasHigh = Number.isFinite(entry.high);
            const hasMid = Number.isFinite(entry.mid);

            const xLow = hasLow ? scale.x(entry.low) : undefined;
            const xHigh = hasHigh ? scale.x(entry.high) : undefined;
            const xMid = hasMid ? scale.x(entry.mid) : undefined;

            const label = displayText(entry.condition);
            const rangeText = `${displayNumber(entry.low)} to ${displayNumber(
              entry.high
            )}, midpoint ${displayNumber(entry.mid)}`;

            return (
              <g key={entry.measure_id ?? index}>
                {/* Whisker from low to high (Req 5.1). */}
                {xLow !== undefined && xHigh !== undefined && (
                  <line
                    x1={xLow}
                    y1={centerY}
                    x2={xHigh}
                    y2={centerY}
                    stroke="var(--accent)"
                    strokeWidth={2}
                    strokeLinecap="round"
                  />
                )}
                {/* End caps so the span reads clearly without colour. */}
                {xLow !== undefined && (
                  <line
                    x1={xLow}
                    y1={centerY - 5}
                    x2={xLow}
                    y2={centerY + 5}
                    stroke="var(--accent)"
                    strokeWidth={2}
                  />
                )}
                {xHigh !== undefined && (
                  <line
                    x1={xHigh}
                    y1={centerY - 5}
                    x2={xHigh}
                    y2={centerY + 5}
                    stroke="var(--accent)"
                    strokeWidth={2}
                  />
                )}
                {/* Dot at the midpoint (Req 5.1). */}
                {xMid !== undefined && (
                  <circle
                    cx={xMid}
                    cy={centerY}
                    r={DOT_RADIUS}
                    fill="var(--accent)"
                    stroke="var(--bg)"
                    strokeWidth={1}
                  />
                )}
                {/* Non-colour text label so meaning never relies on colour alone
                    (Req 5.8, 15.2): the condition name sits in the left column,
                    vertically centred on the very row as its whisker. */}
                <text
                  className="dw-row-label"
                  x={nameColumnWidth - NAME_GAP}
                  y={centerY}
                  textAnchor="end"
                  dominantBaseline="central"
                >
                  {label}
                </text>
                {/* SVG-only description of this row for assistive tech. */}
                <desc>{`${label}: ${rangeText}`}</desc>
              </g>
            );
          })}

          {/* Numeric tick labels along the value axis, so a whisker's length can
              be read as a number without consulting the table below. */}
          {ticks.map((tick) => (
            <text
              key={tick}
              className="dw-axis-tick"
              x={scale.x(tick)}
              y={tickLabelY}
              textAnchor="middle"
            >
              {formatAxisTick(tick)}
            </text>
          ))}

          {/* Axis label (Req 5.4, 22.4), centred under the plot it describes. */}
          <text
            className="dw-axis-label"
            x={nameColumnWidth + PLOT_WIDTH / 2}
            y={axisLabelY}
            textAnchor="middle"
          >
            {axisLabel}
          </text>
        </svg>
      </div>

      <TextAlternative
        entries={entries}
        tableId={tableId}
        onSelect={handleSelect}
      />
    </section>
  );
}

interface TextAlternativeProps {
  entries: readonly WhatEntry[];
  tableId: string;
  onSelect: (measureId: string) => void;
}

/**
 * The visually-complete data table that conveys the same information as the
 * chart (Req 6.1, 6.2, 6.3). Columns are, in order: condition, low, mid, high,
 * t, affected_adults. Rows render in the same order as `entries` (the caller's
 * sort order). Each row's condition cell is a keyboard-focusable control that
 * navigates to the Investigate page for that disease's `measure_id`
 * (Req 5.5, 15.3). Missing cells show "unavailable" (Req 6.5).
 */
function TextAlternative({ entries, tableId, onSelect }: TextAlternativeProps) {
  return (
    <div className="dw-table-scroll">
      <table id={tableId} className="dw-table">
        <caption>
          Index range per disease. Select a disease to investigate its studies.
        </caption>
        <thead>
          <tr>
            <th scope="col">condition</th>
            <th scope="col">low</th>
            <th scope="col">mid</th>
            <th scope="col">high</th>
            <th scope="col">t</th>
            <th scope="col">affected_adults</th>
            <th scope="col">prevalence_year</th>
          </tr>
        </thead>
        <tbody>
          {entries.length === 0 ? (
            <tr>
              <td colSpan={7}>No diseases are available</td>
            </tr>
          ) : (
            entries.map((entry, index) => {
              const label = displayText(entry.condition);
              const hasMeasureId =
                typeof entry.measure_id === "string" &&
                entry.measure_id.trim() !== "";
              return (
                <tr key={entry.measure_id ?? index}>
                  <th scope="row">
                    {hasMeasureId ? (
                      <button
                        type="button"
                        className="dw-row-button"
                        onClick={() => onSelect(entry.measure_id)}
                      >
                        {label}
                      </button>
                    ) : (
                      label
                    )}
                  </th>
                  <td>{displayNumber(entry.low)}</td>
                  <td>{displayNumber(entry.mid)}</td>
                  <td>{displayNumber(entry.high)}</td>
                  <td>{displayNumber(entry.t)}</td>
                  <td>{displayNumber(entry.affected_adults)}</td>
                  <td>{displayText(entry.prevalence_year)}</td>
                </tr>
              );
            })
          )}
        </tbody>
      </table>
    </div>
  );
}
