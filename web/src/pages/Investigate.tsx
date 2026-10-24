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
import Card from "../components/Card";
import {
  DataUnavailable,
  LoadStateView,
  LoadingIndicator,
} from "../components/LoadStateView";
import {
  useEvidenceData,
  useInvestigateData,
  useIsSample,
  useWhatData,
} from "../data/providers";
import {
  selectInvestigateHeadline,
  type InvestigateHeadline,
} from "../data/investigateHeadline";
import { noInterventionCount } from "../data/noInterventionCount";
import type {
  EvidenceEntry,
  InvestigateEntry,
  LabelCount,
  LoadState,
  WhatEntry,
} from "../data/types";
import "./Investigate.css";

/** Intro sentence shown only for confirmed real data (`is_sample === false`, Req 20.5). */
export const INTRO_REAL_SENTENCE =
  "The numbers come straight from public study records.";

/** Cautious intro sentence for sample or not-yet-loaded sources (Req 20.5). */
export const INTRO_SAMPLE_SENTENCE =
  "These are sample numbers for layout; real counts come from the scoring export.";

/** Label for the headline count — Index_Numerator_T (Req 14.1, 19.3). */
export const HEADLINE_LABEL =
  "Recruiting studies in Massachusetts (used in the index)";

/** Label for the second count, `ma_studies` (Req 19.4). */
export const MA_STUDIES_LABEL =
  "Massachusetts studies, all fetched statuses";

/**
 * One-phrase definition of Index_Numerator_T: the recruiting MA-site count used
 * in the index (Req 14.1, 14.4).
 */
export const INDEX_NUMERATOR_DEFINITION =
  "Counts recruiting Massachusetts studies with a recruiting Massachusetts site.";

/** The label for Status_Recruiting_Count, the by_overall_status "Recruiting" entry. */
export const STATUS_RECRUITING_LABEL = "Recruiting";

/** Label for the study-level recruiting count — Status_Recruiting_Count (Req 14.2). */
export const STATUS_RECRUITING_COUNT_LABEL =
  "Recruiting studies in Massachusetts (study-level count)";

/**
 * One-phrase definition of Status_Recruiting_Count: the study-level count of
 * eligible MA studies whose overall status is recruiting (Req 14.2, 14.4).
 */
export const STATUS_RECRUITING_DEFINITION =
  "Counts the Massachusetts studies whose overall status is recruiting.";

/**
 * F2 traceability limitation shown next to Index_Numerator_T: the specific
 * studies that compose it cannot be identified because no data field marks them
 * (Req 17.1). No control claims to list exactly that set (Req 17.2).
 */
export const F2_TRACEABILITY_STATEMENT =
  "The specific studies that make up this count cannot be identified from the available data, because no data field marks them.";

/** Label for the US national-comparison row (Req 18.1). */
export const US_STUDIES_LABEL = "United States";

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

/**
 * Overlap disclosure shown next to the intervention-type panel: a study can
 * list several intervention types, so the type counts can overlap and must not
 * be added into a total (Req 15.2).
 */
export const INTERVENTION_OVERLAP_NOTE =
  "A study can list more than one intervention type, so these counts can overlap; do not add them into a total.";

/**
 * Overlap disclosure shown next to the phase panel only while
 * `phase_overlap_studies` is greater than zero: some studies report more than
 * one phase, so the phase counts can overlap (Req 15.1).
 */
export const PHASE_OVERLAP_NOTE =
  "Some studies report more than one phase, so these counts can overlap; do not add them into a total.";

/**
 * Prefix for the client-side No_Intervention_Count shown near the
 * intervention-type panel (Flag F1, Req 16.2). The value is "unknown" when
 * Evidence_Data fails or is still loading (Req 16.4).
 */
export const NO_INTERVENTION_LABEL =
  "Studies with no intervention type listed";

/**
 * Status_Recruiting_Count: the `by_overall_status` entry labelled "Recruiting",
 * i.e. the study-level count of eligible MA studies whose overall status is
 * recruiting. Distinct from Index_Numerator_T (Req 14.2, 14.3). Returns null
 * when no such label is present so the caller can show "unknown" (Req 1.6).
 */
export function selectStatusRecruitingCount(
  byOverallStatus: readonly LabelCount[]
): number | null {
  const match = byOverallStatus.find(
    (item) => item.label === STATUS_RECRUITING_LABEL
  );
  return match === undefined ? null : match.count;
}

/**
 * Resolve No_Intervention_Count for `measureId` from the Evidence_Data state,
 * computed client-side via `noInterventionCount` (Flag F1, Req 16.1-16.3).
 * Returns the count only when Evidence_Data is ready and carries a matching
 * entry; every other state (loading, error, empty, or no matching entry)
 * returns null so the caller renders "unknown" (Req 16.4, 1.6).
 */
export function selectNoInterventionCount(
  state: LoadState<EvidenceEntry[]>,
  measureId: string
): number | null {
  if (state.status !== "ready") return null;
  const entry = state.data.find((e) => e.measure_id === measureId);
  return entry === undefined ? null : noInterventionCount(entry.ncts);
}

/** The resolved Investigate_Entry view (Req 13, 14, 17, 18). */
function InvestigateDetail({
  entry,
  whatState,
  evidenceState,
}: {
  entry: InvestigateEntry;
  whatState: LoadState<WhatEntry[]>;
  evidenceState: LoadState<EvidenceEntry[]>;
}) {
  const what = resolveHeadline(whatState, entry.measure_id);
  const isSample = useIsSample();
  // Status_Recruiting_Count is the study-level "Recruiting" count; it is read
  // from by_overall_status and kept distinct from Index_Numerator_T (Req 14.3).
  const statusRecruiting = selectStatusRecruitingCount(entry.by_overall_status);
  // No_Intervention_Count is derived client-side from Evidence_Data (never read
  // from Investigate_Data); null -> "unknown" while evidence.json is loading or
  // failed (Flag F1, Req 16.1-16.4).
  const noIntervention = selectNoInterventionCount(
    evidenceState,
    entry.measure_id
  );
  // Phase counts can overlap only when phase_overlap_studies > 0; the note is
  // shown next to the phase panel only in that case (Req 15.1).
  const showPhaseOverlap =
    typeof entry.phase_overlap_studies === "number" &&
    entry.phase_overlap_studies > 0;
  return (
    <article>
      <h1>{entry.condition}</h1>
      <p className="inv-intro">
        This page describes the Massachusetts studies counted for this disease
        and how they break down.{" "}
        {isSample ? INTRO_SAMPLE_SENTENCE : INTRO_REAL_SENTENCE}
      </p>

      <Card title="Study Counts">
        <p className="inv-definition">
          Prevalence means how common a disease is among adults in a place.
        </p>
        {"headline" in what && what.headline.prevalenceYear !== null && (
          <p className="inv-prevalence-year">
            {prevalenceYearText(what.headline.prevalenceYear)}
          </p>
        )}
        <ul className="inv-counts">
          {/*
            Index_Numerator_T — the recruiting MA-site count used in the index
            (What `t`). Shown distinctly from Status_Recruiting_Count below, with
            its own one-phrase definition and the F2 traceability note; the two
            numbers are never combined (Req 14.1, 14.3, 14.4, 14.5, 17.1).
          */}
          <li className="inv-count-headline">
            {HEADLINE_LABEL}:{" "}
            {"headline" in what ? (
              <span className="inv-count-value inv-headline-value">
                {what.headline.t === null ? "unknown" : what.headline.t}
              </span>
            ) : (
              what.pending
            )}
            <span className="inv-definition-inline">
              {INDEX_NUMERATOR_DEFINITION}
            </span>
            {/*
              F2: the specific studies composing Index_Numerator_T cannot be
              identified because no data field marks them. No control claims to
              list exactly that set (Req 17.1, 17.2).
            */}
            <span className="inv-f2-note">{F2_TRACEABILITY_STATEMENT}</span>
          </li>
          {/*
            Status_Recruiting_Count — the study-level recruiting count from
            by_overall_status, labelled distinctly from the index numerator
            above (Req 14.2, 14.3, 14.4).
          */}
          <li className="inv-count-status-recruiting">
            {STATUS_RECRUITING_COUNT_LABEL}:{" "}
            <span className="inv-count-value">
              {statusRecruiting === null ? "unknown" : statusRecruiting}
            </span>
            <span className="inv-definition-inline">
              {STATUS_RECRUITING_DEFINITION}
            </span>
          </li>
          <li className="inv-count-ma">
            {MA_STUDIES_LABEL}:{" "}
            <span className="inv-count-value">{entry.ma_studies}</span>{" "}
            (recruiting, not yet recruiting, active not recruiting, and recently
            updated completed).
          </li>
          {/*
            US national comparison (F3): render the value only when it is read
            directly from `us_studies`; render the literal "unknown" when it is
            null (it is null for every disease in this version), never 0 and
            never a fabricated number (Req 18.1, 18.2, 1.6).
          */}
          <li className="inv-count-us">
            {US_STUDIES_LABEL}:{" "}
            <span className="inv-count-value">
              {entry.us_studies === null ? "unknown" : entry.us_studies}
            </span>
          </li>
        </ul>
      </Card>

      <Card title="Studies Breakdown">
        <p className="inv-definition">
          Interventional means a study that tests a change, such as a drug or
          device, rather than only observing.
        </p>
        <div className="inv-breakdowns">
          <Breakdown
            title="By overall status"
            items={entry.by_overall_status}
          />
          <Breakdown title="By study type" items={entry.by_study_type} />
          {/*
            Intervention-type panel — rendered exactly once (Req 13.3). The
            Drug-count caption stays attached here. Alongside this same panel we
            show the overlap disclosure (Req 15.2) and the client-side
            No_Intervention_Count derived from Evidence_Data (Flag F1, Req 16.2).
          */}
          <div className="inv-intervention-panel">
            <Breakdown
              title="By intervention type"
              items={entry.by_intervention_type}
              caption={DRUG_COUNT_CAPTION}
            />
            <p className="inv-overlap-note inv-intervention-overlap">
              {INTERVENTION_OVERLAP_NOTE}
            </p>
            {/*
              No_Intervention_Count: how many studies list no intervention type,
              computed client-side from Evidence_Data. "unknown" when evidence.json
              is still loading or failed (Req 16.2, 16.4).
            */}
            <p className="inv-no-intervention">
              {NO_INTERVENTION_LABEL}:{" "}
              <span className="inv-count-value">
                {noIntervention === null ? "unknown" : noIntervention}
              </span>
            </p>
          </div>
          {/*
            Phase panel. The phase overlap note is shown next to it only while
            phase_overlap_studies > 0 (Req 15.1).
          */}
          <div className="inv-phase-panel">
            <Breakdown title="By phase" items={entry.by_phase} />
            {showPhaseOverlap && (
              <p className="inv-overlap-note inv-phase-overlap">
                {PHASE_OVERLAP_NOTE}
              </p>
            )}
          </div>
        </div>
      </Card>

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
  // Evidence_Data drives the client-side No_Intervention_Count (Flag F1). A slow
  // or failed evidence.json degrades only that one line to "unknown" (Req 16.4).
  const evidenceState = useEvidenceData();

  return (
    <LoadStateView state={state}>
      {(entries) => {
        const entry = entries.find((e) => e.measure_id === measureId);
        return entry ? (
          <InvestigateDetail
            entry={entry}
            whatState={whatState}
            evidenceState={evidenceState}
          />
        ) : (
          <DiseaseNotFound />
        );
      }}
    </LoadStateView>
  );
}
