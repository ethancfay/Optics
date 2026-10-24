// What_View route (Req 5.1, 5.2, 5.3, 5.5, 5.7, 8.1, 8.2, 8.3, 8.5, 10.1,
// 10.2, 10.3, 16.1).
//
// The WHAT view is a card-based layout around the single, tab-free dot+whisker
// chart of every disease (Req 5.2, 8.1). It is a thin route component: it reads
// What_Data from the provider (the router wraps this page in `WhatDataProvider`,
// so the fetch happens exactly once per page view), sorts the surviving entries
// with `sortConditions` so the lowest-midpoint disease appears first (Req 5.3,
// 16.1), and hands them to `DotWhiskerChart`.
//
// Two cards:
//   1. "Burden vs. research activity by disease" — wraps the chart. Alongside
//      the chart (not inside the SVG) sit the two MANDATORY caveats (Req 10.1,
//      10.2). They render ONLY while the chart is shown, so a failed/empty load
//      never surfaces the caveats in isolation (Req 10.3). The no-disease-data
//      message renders in place of the chart when What_Data has no valid
//      entries (Req 8.5).
//   2. "Index range per disease" — a disease picker whose options are exactly
//      the What_Data diseases (Req 8.2). Selecting one navigates to that
//      disease's Investigate route via client-side routing (Req 8.3).
//
// The chart owns everything visual: the shared scale that keeps the dot inside
// its whisker (Req 5.1, 5.6), the text-alternative table (Req 8.4), and the
// navigation to `/investigate/:measureId` when a disease row is selected (via
// useNavigate inside the chart, Req 5.5).
//
// Loading / error / empty states come from the provider through `LoadStateView`
// (Req 3.2, 3.3, 3.5). The `empty` slot is overridden with the WHAT-specific
// "No diseases are available" message so a dataset whose entries were all
// omitted surfaces an explicit, data-free message rather than an empty chart
// (Req 5.7, 8.5).

import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useWhatData } from "../data/providers";
import { LoadStateView } from "../components/LoadStateView";
import Card from "../components/Card";
import DotWhiskerChart from "../components/DotWhiskerChart";
import { sortConditions } from "../data/conditions";
import type { WhatEntry } from "../data/types";
import "./What.css";

/** Card title above the chart (Req 8.1). */
export const CHART_CARD_TITLE = "Burden vs. research activity by disease";

/** Card title above the disease picker (Req 8.2). */
export const PICKER_CARD_TITLE = "Index range per disease";

/**
 * The two MANDATORY caveats shown beside the chart (Req 10.1, 10.2). They are
 * exported so the tests assert the exact copy, and framed as record artefacts —
 * never a judgment — so they carry no Forbidden_Terms.
 */
export const CAVEAT_EXCLUSION =
  "High Cholesterol is lowest partly because trials studying heart disease on its own are excluded.";
export const CAVEAT_SMALL_COUNTS =
  "Asthma rests on 8 studies and High Cholesterol on 5 studies, so small changes move those results.";

/** The no-disease-data message shown in place of the chart (Req 5.7, 8.5). */
export const NO_DISEASE_DATA_MESSAGE = "No diseases are available";

/** Placeholder option value for the picker's unselected state. */
const PICKER_PLACEHOLDER = "";

/**
 * The chart card body: the DotWhiskerChart plus the two mandatory caveats next
 * to it. This component renders ONLY on the `ready` state, so the caveats exist
 * exactly when the chart does (Req 10.1, 10.2, 10.3).
 */
function ChartWithCaveats({ entries }: { entries: readonly WhatEntry[] }) {
  return (
    <div className="what-chart-block">
      <DotWhiskerChart entries={sortConditions(entries)} />
      {/* Caveats sit beside the chart, not inside the SVG (Req 10). */}
      <aside className="what-caveats" aria-label="Chart caveats">
        <p className="what-caveat">{CAVEAT_EXCLUSION}</p>
        <p className="what-caveat">{CAVEAT_SMALL_COUNTS}</p>
      </aside>
    </div>
  );
}

/**
 * The disease picker (Req 8.2, 8.3). A labelled <select> whose options are
 * exactly the What_Data diseases, in the same lowest-midpoint-first order as
 * the chart. Choosing a disease navigates to its Investigate route via
 * client-side routing (useNavigate), with no full document reload.
 */
function DiseasePicker({ entries }: { entries: readonly WhatEntry[] }) {
  const navigate = useNavigate();
  const [selected, setSelected] = useState<string>(PICKER_PLACEHOLDER);
  const diseases = sortConditions(entries);

  function handleChange(event: React.ChangeEvent<HTMLSelectElement>) {
    const measureId = event.target.value;
    setSelected(measureId);
    if (measureId !== PICKER_PLACEHOLDER) {
      navigate(`/investigate/${measureId}`);
    }
  }

  return (
    <div className="what-picker">
      <label className="what-picker-label" htmlFor="what-disease-picker">
        Choose a disease to investigate its studies
      </label>
      <select
        id="what-disease-picker"
        className="what-picker-select"
        value={selected}
        onChange={handleChange}
      >
        <option value={PICKER_PLACEHOLDER}>Select a disease…</option>
        {diseases.map((entry) => (
          <option key={entry.measure_id} value={entry.measure_id}>
            {entry.condition}
          </option>
        ))}
      </select>
    </div>
  );
}

/** The WHAT view: a chart card with caveats, then a disease-picker card. */
export default function What() {
  const state = useWhatData();

  return (
    <section aria-labelledby="what-heading">
      <h1 id="what-heading">Burden versus research activity by disease</h1>

      <Card title={CHART_CARD_TITLE}>
        <LoadStateView
          state={state}
          empty={
            <p role="status" className="what-no-data">
              {NO_DISEASE_DATA_MESSAGE}
            </p>
          }
        >
          {(entries) => <ChartWithCaveats entries={entries} />}
        </LoadStateView>
      </Card>

      <Card title={PICKER_CARD_TITLE}>
        <LoadStateView
          state={state}
          empty={
            <p role="status" className="what-no-data">
              {NO_DISEASE_DATA_MESSAGE}
            </p>
          }
        >
          {(entries) => <DiseasePicker entries={entries} />}
        </LoadStateView>
      </Card>
    </section>
  );
}
