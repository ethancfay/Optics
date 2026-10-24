// Home_Page — route component for `/` (Req 4).
//
// The Home page frames the site's question in one sentence (Req 4.1), names the
// "top finding" — the disease whose precomputed index midpoint is lowest — and
// its low-high range (Req 4.2, 4.3), and links to the WHAT view with visible
// link text using a react-router `<Link>` so navigation happens without a full
// document reload (Req 4.4, 4.5). With zero valid What entries it shows a
// no-disease-data message instead of a top finding (Req 4.6).
//
// Copy frames the top finding strictly as a DISCREPANCY between measured burden
// and observed research activity — never a judgment — and uses no Forbidden_Terms
// (Req 4.7, 17). The problem statement below is one sentence, 1-200 characters.
//
// Data comes from the What provider (`useWhatData`), which the router wraps in a
// `WhatDataProvider` (task 14). Loading / error / empty states are rendered via
// the shared `LoadStateView` helper so this page never shows a partial number
// while a file is loading or has failed (Req 3.2, 3.3, 3.5).

import { Link } from "react-router-dom";
import { useWhatData } from "../data/providers";
import { selectTopFinding } from "../data/conditions";
import { LoadStateView } from "../components/LoadStateView";
import type { WhatEntry } from "../data/types";

/**
 * One-sentence framing of the question, 1-200 characters, describing the finding
 * as a discrepancy (not a judgment) and free of Forbidden_Terms (Req 4.1, 4.7).
 */
const PROBLEM_STATEMENT =
  "Where does the burden a disease places on people diverge from the amount of recruiting research activity measured for it?";

/** The exact no-data message shown when there are zero valid What entries (Req 4.6). */
const NO_DISEASE_DATA_MESSAGE = "No disease data is available.";

/**
 * Render the top finding: name the disease and its index value as a low-high
 * range, framed as a discrepancy between measured burden and observed research
 * activity (Req 4.2, 4.3, 4.7).
 */
function TopFinding({ entries }: { entries: readonly WhatEntry[] }) {
  const top = selectTopFinding(entries);

  // `selectTopFinding` returns undefined only for an empty list; the `ready`
  // state already guarantees >= 1 entry, but guard so we never render a broken
  // sentence and fall back to the no-data message (Req 4.6).
  if (top === undefined) {
    return (
      <p role="status" className="home-no-data">
        {NO_DISEASE_DATA_MESSAGE}
      </p>
    );
  }

  return (
    <section className="home-top-finding" aria-labelledby="home-top-finding-heading">
      <h2 id="home-top-finding-heading">Top finding</h2>
      <p>
        For <strong>{top.condition}</strong>, measured burden and observed
        recruiting research activity diverge the most: its index value ranges
        from <strong>{top.low}</strong> to <strong>{top.high}</strong> distinct
        recruiting Massachusetts studies per 100,000 affected adults (18+).
      </p>
      <p className="home-finding-note">
        This range reflects a discrepancy between measured burden and the
        research activity observed in the public records, not a judgment about
        the disease or any organization.
      </p>
    </section>
  );
}

/**
 * Home_Page route component. Default export named for the route so the router
 * (task 14) imports it as `Home`.
 */
export default function Home() {
  const state = useWhatData();

  return (
    <div className="home-page">
      <h1>Research Gap Index</h1>
      <p className="home-problem-statement">{PROBLEM_STATEMENT}</p>

      <LoadStateView
        state={state}
        empty={
          <p role="status" className="home-no-data">
            {NO_DISEASE_DATA_MESSAGE}
          </p>
        }
      >
        {(entries) => <TopFinding entries={entries} />}
      </LoadStateView>

      <p className="home-what-link">
        <Link to="/what">See every disease in the WHAT view</Link>
      </p>
    </div>
  );
}
