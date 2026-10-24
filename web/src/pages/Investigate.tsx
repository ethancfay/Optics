// Investigate_Page — route /investigate/:measureId (Req 5.10, 7.1-7.7).
//
// Reads the :measureId route param and finds the matching Investigate_Entry in
// the Investigate_Data provider. It renders the four breakdowns (by overall
// status, study type, intervention type, phase) from each array's label/count
// pairs (Req 7.1), the study counts (Req 7.2, 19; see below), and every finding together with its
// Evidence_Label badge (Req 7.3) — a causal/uncertain statement is never shown
// without one of the two labels, which is guaranteed because every Finding in
// the contract carries a `label` and this component renders the badge for each
// finding it renders. It links to the Evidence page for the same measure_id
// (Req 7.4), uses grade-8 copy with ≤20-word definitions for "interventional"
// and "prevalence" at first use (Req 7.5), and shows a "disease not found"
// message with a link back to WHAT for an unknown id (Req 7.6, 5.10). It
// carries no diagnosis/treatment/eligibility/enrollment text and no
// Forbidden_Terms (Req 7.7).
//
// Loading / error / empty come from the shared LoadStateView wrapper over the
// Investigate provider (Req 3.2, 3.3, 3.5).

//
// Study counts (Req 7.2, 19.3-19.7): the headline is the WHAT `t` for this
// measure_id, read from What_Data (one source of truth with the WHAT view);
// `ma_studies` from Investigate_Data comes second; the US row renders only
// when `us_studies` is a number. The headline and the prevalence-year line
// depend only on What_Data, so a slow or failed what.json affects just that
// region while the breakdowns and findings still render (Req 19.6, 3.6).

import type { ReactNode } from "react";
import { Link, useParams } from "react-router-dom";
import {
  DataUnavailable,
  LoadStateView,
  LoadingIndicator,
} from "../components/LoadStateView";
import { useInvestigateData, useWhatData } from "../data/providers";
import {
  selectInvestigateHeadline,
  type InvestigateHeadline,
} from "../data/investigateHeadline";
import type { InvestigateEntry, LabelCount, LoadState, WhatEntry } from "../data/types";
import "./Investigate.css";

/** Label for the headline count (Req 19.3). */
export const HEADLINE_LABEL =
  "Recruiting studies in Massachusetts (used in the index)";

/** Label for the second count, `ma_studies` (Req 19.4). */
export const MA_STUDIES_LABEL =
  "Massachusetts studies, all fetched statuses";

/** The "Prevalence data year" line text for a given year (Req 19.7). */
export function prevalenceYearText(year: string): string {
  return `Prevalence data year: ${year} (CDC PLACES)`;
}

/**
 * Resolve the What_Data state into either a headline (ready/empty) or a node
 * to show in its place (loading/error naming what.json) (Req 19.5, 19.6).
 */
function resolveHeadline(
  state: LoadState<WhatEntry[]>,
  measureId: string
): { headline: InvestigateHeadline } | { pending: ReactNode } {
  switch (state.status) {
    case "ready":
      return { headline: selectInvestigateHeadline(state.data, measureId) };
    case "empty":
      return { headline: { t: null, prevalenceYear: null } };
    case "loading":
      return { pending: <LoadingIndicator /> };
    case "error":
      return { pending: <DataUnavailable file={state.file} /> };
  }
}

/**
 * One breakdown table built from an array of {label, count} pairs (Req 7.1).
 * An optional `caption` renders as a note beneath the table — used to carry the
 * Drug-count explanation next to the intervention-type breakdown (Req 7.1).
 */
function Breakdown({
  title,
  items,
  caption,
}: {
  title: string;
  items: readonly LabelCount[];
  caption?: string;
}) {
  return (
    <div className="inv-breakdown">
      <table className="inv-table">
        <caption>{title}</caption>
        <thead>
          <tr>
            <th scope="col">Category</th>
            <th scope="col">Studies</th>
          </tr>
        </thead>
        <tbody>
          {items.length === 0 ? (
            <tr>
              <td colSpan={2}>No categories are available.</td>
            </tr>
          ) : (
            items.map((item) => (
              <tr key={item.label}>
                <td>{item.label}</td>
                <td>{item.count}</td>
              </tr>
            ))
          )}
        </tbody>
      </table>
      {caption !== undefined && <p className="inv-caption">{caption}</p>}
    </div>
  );
}

/**
 * Caption shown next to any Drug intervention count. "Drug" is a study that
 * lists a drug-type intervention; it may be an existing drug, a comparator, or
 * a placebo, not necessarily a new treatment (Req 7.1, data contract).
 */
export const DRUG_COUNT_CAPTION =
  "Drug means the study lists a drug intervention; it may be an existing drug, comparator or placebo.";

/** The resolved Investigate_Entry view (Req 7.1-7.5). */
function InvestigateDetail({
  entry,
  whatState,
}: {
  entry: InvestigateEntry;
  whatState: LoadState<WhatEntry[]>;
}) {
  const what = resolveHeadline(whatState, entry.measure_id);
  return (
    <article>
      <h1>{entry.condition}</h1>
      <p>
        This page describes the Massachusetts studies counted for this disease
        and how they break down. The numbers come straight from public study
        records.
      </p>

      <h2>Study counts</h2>
      <p className="inv-definition">
        Prevalence means how common a disease is among adults in a place.
      </p>
      {"headline" in what && what.headline.prevalenceYear !== null && (
        <p className="inv-prevalence-year">
          {prevalenceYearText(what.headline.prevalenceYear)}
        </p>
      )}
      <ul className="inv-counts">
        <li className="inv-count-headline">
          {HEADLINE_LABEL}:{" "}
          {"headline" in what ? (
            <span className="inv-count-value inv-headline-value">
              {what.headline.t === null ? "unknown" : what.headline.t}
            </span>
          ) : (
            what.pending
          )}
        </li>
        <li className="inv-count-ma">
          {MA_STUDIES_LABEL}:{" "}
          <span className="inv-count-value">{entry.ma_studies}</span>{" "}
          (recruiting, not yet recruiting, active not recruiting, and recently
          updated completed).
        </li>
        {entry.us_studies !== null && (
          <li className="inv-count-us">
            United States:{" "}
            <span className="inv-count-value">{entry.us_studies}</span>
          </li>
        )}
      </ul>

      <h2>How the studies break down</h2>
      <p className="inv-definition">
        Interventional means a study that tests a change, such as a drug or
        device, rather than only observing.
      </p>
      <div className="inv-breakdowns">
        <Breakdown title="By overall status" items={entry.by_overall_status} />
        <Breakdown title="By study type" items={entry.by_study_type} />
        <Breakdown
          title="By intervention type"
          items={entry.by_intervention_type}
          caption={DRUG_COUNT_CAPTION}
        />
        <Breakdown title="By phase" items={entry.by_phase} />
      </div>

      <h2>What the records show</h2>
      {entry.findings.length === 0 ? (
        <p>No findings are available.</p>
      ) : (
        <ul className="inv-findings">
          {entry.findings.map((finding, index) => (
            <li key={index} className="inv-finding">
              <p>{finding.text}</p>
              {/*
                Every finding carries exactly one Evidence_Label in the data
                contract; render its badge so no causal/uncertain statement ever
                appears without a label (Req 7.3).
              */}
              <span className="inv-badge">{finding.label}</span>
            </li>
          ))}
        </ul>
      )}

      <p>
        <Link
          className="inv-evidence-link"
          to={`/evidence/${entry.measure_id}`}
        >
          See the studies behind these numbers
        </Link>
      </p>
    </article>
  );
}

/** "Disease not found" fallback with a link back to WHAT (Req 7.6, 5.10). */
function DiseaseNotFound() {
  return (
    <section>
      <h1>Disease not found</h1>
      <p>We could not find a disease for this address.</p>
      <p>
        <Link className="inv-back-link" to="/what">
          Back to all diseases
        </Link>
      </p>
    </section>
  );
}

/**
 * Investigate_Page route component. Resolves the Investigate_Entry for the
 * `:measureId` param once the provider is `ready`; an unknown id falls through
 * to the not-found view (Req 7.6, 5.10).
 */
export default function Investigate() {
  const { measureId } = useParams<{ measureId: string }>();
  const state = useInvestigateData();
  const whatState = useWhatData();

  return (
    <LoadStateView state={state}>
      {(entries) => {
        const entry = entries.find((e) => e.measure_id === measureId);
        return entry ? (
          <InvestigateDetail entry={entry} whatState={whatState} />
        ) : (
          <DiseaseNotFound />
        );
      }}
    </LoadStateView>
  );
}
