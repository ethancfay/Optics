// Method_Page — route component for `/method` (Req 11).
//
// The Method page lets a researcher trust and cite the numbers. It explains, in
// grade-8 plain language and with no Forbidden_Terms (Req 11.6, 17):
//
//   - the Index_Value formula and what each symbol means (Req 11.1);
//   - the crosswalk and filters used to attribute studies to each disease (Req 11.2);
//   - every Source_Entry as a NAMED link to its `url`, each shown WITH its
//     `fetched` date (Req 11.3) — this is the distinction from the Footer, which
//     renders the same source links WITHOUT a fetched date (checked by Property 8);
//   - the limit that burden is CDC PLACES crude prevalence for adults 18+ with no
//     disability-adjusted life years or severity measure (Req 11.4);
//   - the limit that Massachusetts trial activity does not represent all research
//     relevant to Massachusetts patients (Req 11.5);
//   - one sentence that a national comparison is planned (Req 11.7).
//
// The formula is rendered as plain inline markup (no external math library): the
// bracketed low-high expression times 100,000, followed by a short legend naming
// `T`, `N`, `p_low`, and `p_high`.
//
// Only the sources section depends on a loaded file. It reads Sources_Data via
// the `useSources()` hook and wraps that single region in the shared
// `LoadStateView` helper so the loading / error (naming `sources.json`) / empty
// states are handled in one place and never show a partial or placeholder source
// (Req 3.2, 3.3, 3.5). The static formula, crosswalk, filters, and limits remain
// visible regardless of the Sources load state, so one file's failure never
// blanks the rest of the page (Req 3.6). The router (task 14) wraps this page in
// `SourcesProvider`; `useSources` throws if used outside it.

import { useSources } from "../data/providers";
import { LoadStateView } from "../components/LoadStateView";
import type { SourcesData } from "../data/types";

/**
 * The two limitation statements, kept as named constants so tests and copy agree
 * on the exact wording (Req 11.4, 11.5). Both are plain grade-8 sentences and use
 * no Forbidden_Terms.
 */
export const CRUDE_PREVALENCE_LIMIT =
  "Burden here is CDC PLACES crude prevalence for adults aged 18 and older. " +
  "It does not include disability-adjusted life years (DALYs) or any measure of how severe a disease is.";

export const MA_ACTIVITY_LIMIT =
  "This measures Massachusetts trial activity. It does not stand for all research that matters to Massachusetts patients.";

/** The deferred national comparison, stated once (Req 11.7). */
export const NATIONAL_COMPARISON_PLANNED =
  "A national (United States) comparison is planned for a later version and is not included here.";

/** Disease scope today and how deferred diseases can be added (Req 20.6a). */
export const DISEASE_SCOPE =
  "This version covers three diseases: asthma, diabetes and high cholesterol. " +
  "High blood pressure and depression can be added later by editing the rules file, after review.";

/**
 * High-cholesterol exclusion of heart-disease-only studies (Req 20.6b). Mirrors
 * Spec 2's `ascvd_only` exclusion in pipeline/mapping/rules.py.
 */
export const HIGHCHOL_HEART_DISEASE_NOTE =
  "For high cholesterol, we do not count studies that only target heart disease, such as heart attack trials. " +
  "This makes its count lower.";

/**
 * Render the Sources section: one named link per Source_Entry to its `url`, each
 * paired with that source's `fetched` date (Req 11.3). This is the only part of
 * the page that depends on loaded data.
 */
function SourcesSection({ sources }: { sources: SourcesData }) {
  return (
    <ul className="method-page__source-links">
      {sources.sources.map((source) => (
        <li key={source.url}>
          <a href={source.url} rel="noopener noreferrer" target="_blank">
            {source.name}
          </a>{" "}
          <span className="method-page__fetched">
            (fetched {source.fetched})
          </span>
        </li>
      ))}
    </ul>
  );
}

/**
 * Method_Page route component. Default export named `Method` so the router
 * (task 14) imports it as `Method`.
 */
export default function Method() {
  const sourcesState = useSources();

  return (
    <div className="method-page">
      <h1>Method and sources</h1>
      <p className="method-page__intro">
        This page explains how we build the index and where the data comes from,
        so you can check and cite the numbers.
      </p>

      {/* --- The formula (Req 11.1) --- */}
      <section className="method-page__formula" aria-labelledby="method-formula-heading">
        <h2 id="method-formula-heading">How we build the index</h2>
        <p>
          For each disease we read a low-to-high range, not a single number. We
          compute the range like this:
        </p>
        <p className="method-page__equation">
          [ T / (N &times; p_high) , T / (N &times; p_low) ] &times; 100,000
        </p>
        <p>What each part means:</p>
        <ul>
          <li>
            <strong>T</strong> is the count of distinct recruiting Massachusetts
            studies for the disease.
          </li>
          <li>
            <strong>N</strong> is the number of adults aged 18 and older (the
            population denominator).
          </li>
          <li>
            <strong>p_low</strong> and <strong>p_high</strong> are the low and
            high CDC PLACES crude-prevalence confidence limits for the disease.
          </li>
        </ul>
        <p>
          A higher prevalence (p_high) makes the index lower, and a lower
          prevalence (p_low) makes it higher, so the two limits give the ends of
          the range. We multiply by 100,000 to read the range as studies per
          100,000 affected adults.
        </p>
      </section>

      {/* --- Crosswalk and filters (Req 11.2) --- */}
      <section className="method-page__crosswalk" aria-labelledby="method-crosswalk-heading">
        <h2 id="method-crosswalk-heading">How we match studies to a disease</h2>
        <p>
          We use a crosswalk to tie each disease to the studies that belong to
          it. The crosswalk maps the CDC PLACES measure for a disease to the
          clinical-trial condition terms for the same disease, so the studies we
          count line up with the prevalence we use.
        </p>
        <p>We then apply these filters to the studies we count:</p>
        <ul>
          <li>The study lists a Massachusetts recruiting location.</li>
          <li>The study is recruiting, so it is open to new participants.</li>
          <li>
            Each study is counted once, even when it has more than one
            Massachusetts site.
          </li>
          <li>
            The study condition matches the crosswalk terms for the disease.
          </li>
        </ul>
        <p className="method-page__scope">{DISEASE_SCOPE}</p>
        <p className="method-page__highchol">{HIGHCHOL_HEART_DISEASE_NOTE}</p>
        {/*
          TODO(scoring-export): explain how studies marked "questionable" by
          Spec 2 are treated (counted, excluded, or shown separately) once the
          scoring-export spec decides. Code-only; nothing is rendered (Req 20.6).
        */}
      </section>

      {/* --- Sources, each with its fetched date (Req 11.3) --- */}
      <section className="method-page__sources" aria-labelledby="method-sources-heading">
        <h2 id="method-sources-heading">Sources</h2>
        <p>
          Each source below links to the data we used, with the date we fetched
          it.
        </p>
        <LoadStateView<SourcesData> state={sourcesState}>
          {(sources) => <SourcesSection sources={sources} />}
        </LoadStateView>
      </section>

      {/* --- Limits (Req 11.4, 11.5) --- */}
      <section className="method-page__limits" aria-labelledby="method-limits-heading">
        <h2 id="method-limits-heading">What this index does not do</h2>
        <ul>
          <li>{CRUDE_PREVALENCE_LIMIT}</li>
          <li>{MA_ACTIVITY_LIMIT}</li>
          <li>{NATIONAL_COMPARISON_PLANNED}</li>
        </ul>
      </section>
    </div>
  );
}
