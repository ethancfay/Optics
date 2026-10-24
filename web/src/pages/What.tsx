// What_View route (Req 5.1, 5.2, 5.3, 5.5, 5.6, 5.7, 16.1).
//
// The WHAT view is a single, tab-free dot+whisker chart of every disease
// (Req 5.2). It is a thin route component: it reads What_Data from the
// provider (the router wraps this page in `WhatDataProvider`, so the fetch
// happens exactly once per page view), sorts the surviving entries with
// `sortConditions` so the lowest-midpoint disease appears first (Req 5.3,
// 16.1), and hands them to `DotWhiskerChart`.
//
// The chart owns everything visual: the shared scale that keeps the dot inside
// its whisker (Req 5.1, 5.6), the text-alternative table, and the navigation to
// `/investigate/:measureId` when a disease is selected (via useNavigate inside
// the chart, Req 5.5). This page deliberately does NOT duplicate that
// navigation.
//
// Loading / error / empty states come from the provider through `LoadStateView`
// (Req 3.2, 3.3, 3.5). The `empty` slot is overridden with the WHAT-specific
// "No diseases are available" message so a dataset whose entries were all
// omitted surfaces an explicit, data-free message rather than an empty chart
// (Req 5.7).

import { useWhatData } from "../data/providers";
import { LoadStateView } from "../components/LoadStateView";
import DotWhiskerChart from "../components/DotWhiskerChart";
import { sortConditions } from "../data/conditions";

/** The WHAT view: one chart of all diseases, sorted lowest-midpoint first. */
export default function What() {
  const state = useWhatData();

  return (
    <section aria-labelledby="what-heading">
      <h1 id="what-heading">Burden versus research activity by disease</h1>
      <LoadStateView
        state={state}
        empty={<p role="status">No diseases are available</p>}
      >
        {(entries) => <DotWhiskerChart entries={sortConditions(entries)} />}
      </LoadStateView>
    </section>
  );
}
