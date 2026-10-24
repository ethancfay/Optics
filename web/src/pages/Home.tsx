// Home_Page — route component for `/` (Req 7).
//
// Restyle/relayout of the Home page into the two mockup cards (Req 6.5, 7):
//   - a LEFT card titled "What is Research Gap Index?" holding exactly one
//     explanatory sentence (Req 7.1), and
//   - a RIGHT card titled "Top Finding" naming Top_Finding_Disease — the disease
//     whose precomputed Index_Value midpoint is lowest — with its low-high
//     Index_Value range (Req 7.2, 7.3).
//
// Top_Finding_Disease is computed with `selectTopFinding` (Data_Layer), never
// hard-coded (Req 7.3). A "See every disease" control navigates to the WHAT
// route with a react-router `<Link>`, so routing happens client-side without a
// full document reload (Req 7.4). With zero valid What entries the Top Finding
// card shows a no-disease-data message in place of its contents (Req 7.5).
//
// Copy frames the top finding strictly as a DISCREPANCY between measured burden
// and observed research activity — never a judgment — and uses no Forbidden_Terms
// (Req 20). The left-card explanatory sentence is one sentence, 1-200 characters.
//
// This is a restyle: data wiring is unchanged. Data comes from the What provider
// (`useWhatData`), which the router wraps in a `WhatDataProvider`. Loading /
// error / empty states are rendered via the shared `LoadStateView` helper so the
// Top Finding card never shows a partial number while a file is loading or has
// failed (Req 6.3, 6.4).

import { Link } from "react-router-dom";
import { useWhatData } from "../data/providers";
import { selectTopFinding } from "../data/conditions";
import { LoadStateView } from "../components/LoadStateView";
import Card from "../components/Card";
import type { WhatEntry } from "../data/types";
import "./Home.css";

/**
 * The single explanatory sentence shown in the "What is Research Gap Index?"
 * card (Req 7.1). One sentence, 1-200 characters, framing the result as a
 * discrepancy (not a judgment) and free of Forbidden_Terms (Req 20).
 */
export const WHAT_IS_SENTENCE =
  "Optics compares how common a disease is among Massachusetts adults with the amount of recruiting research activity measured for it, as an index and not a prediction.";

/** The exact no-data message shown when there are zero valid What entries (Req 7.5). */
export const NO_DISEASE_DATA_MESSAGE = "No disease data is available.";

/**
 * Render the top finding body: name the disease and its Index_Value as a
 * low-high range, framed as a discrepancy between measured burden and observed
 * research activity (Req 7.2, 7.3, 20.6).
 */
function TopFinding({ entries }: { entries: readonly WhatEntry[] }) {
  const top = selectTopFinding(entries);

  // `selectTopFinding` returns undefined only for an empty list; the `ready`
  // state already guarantees >= 1 entry, but guard so we never render a broken
  // sentence and fall back to the no-data message (Req 7.5).
  if (top === undefined) {
    return (
      <p role="status" className="home-no-data">
        {NO_DISEASE_DATA_MESSAGE}
      </p>
    );
  }

  return (
    <div className="home-top-finding">
      <p>
        For <strong className="home-top-finding__disease">{top.condition}</strong>,
        measured burden and observed recruiting research activity diverge the
        most. Its index value ranges from{" "}
        <strong className="home-top-finding__range">{top.low}</strong> to{" "}
        <strong className="home-top-finding__range">{top.high}</strong> distinct
        recruiting Massachusetts studies per 100,000 affected adults (18+).
      </p>
      <p className="home-finding-note">
        This range reflects a discrepancy between measured burden and the
        research activity observed in the public records, not a judgment about
        the disease or any organization.
      </p>
    </div>
  );
}

/**
 * Home_Page route component. Default export named for the route so the router
 * imports it as `Home`.
 */
export default function Home() {
  const state = useWhatData();

  return (
    <div className="home-page">
      <h1>Optics</h1>

      <div className="home-cards">
        <Card title="What is Optics?" className="home-card home-card--what-is">
          <p className="home-what-is">{WHAT_IS_SENTENCE}</p>
        </Card>

        <Card title="Top Finding" className="home-card home-card--top-finding">
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
            <Link to="/what">See every disease</Link>
          </p>
        </Card>
      </div>
    </div>
  );
}
