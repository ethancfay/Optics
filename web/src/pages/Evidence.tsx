// Evidence_Page route (Req 8.1, 8.2, 8.3, 8.4, 8.5, 8.6, 17).
//
// For the `:measureId` in the URL, this page finds the one Evidence_Entry whose
// `measure_id` matches and shows the record-level provenance behind that
// disease's Index_Value: the contributing ClinicalTrials.gov studies, the
// filters applied to attribute them, the crosswalk/mapping choices, and what
// data is missing. It carries no diagnosis, treatment, eligibility, or
// enrollment text and uses none of the Forbidden_Terms (Req 8.6, 17).
//
// Two providers feed this page, each wrapped by the router around this route so
// each file is fetched exactly once per page view:
//   - EvidenceDataProvider -> `useEvidenceData()` for the Evidence_Entry list.
//   - SourcesProvider       -> `useSources()` for the `data_as_of` date (Req 8.3).
// They degrade independently through `LoadStateView`: a failed `sources.json`
// never blanks the evidence content and vice versa (Req 3.6).
//
// Each `ncts[]` entry renders as a link to its `url` opening in a separate
// browser context (`target="_blank"`, `rel="noopener noreferrer"`) so the
// Evidence page stays open (Req 8.1). These are outbound navigation links the
// user clicks, not runtime data fetches, so they are permitted under the
// same-origin runtime policy. When `ncts` is empty the page shows "no
// contributing studies are available" and renders NO link element at all, so
// there is never a broken/empty link (Req 8.4). When no entry matches the
// requested id, the page shows "disease not found" with a <Link> back to the
// WHAT view, navigating without a full reload (Req 8.5).

import { useParams, Link } from "react-router-dom";
import { useEvidenceData, useSources } from "../data/providers";
import { LoadStateView } from "../components/LoadStateView";
import type { EvidenceEntry } from "../data/types";

/** Shown when no Evidence_Entry matches the requested `measure_id` (Req 8.5). */
const DISEASE_NOT_FOUND_MESSAGE = "Disease not found.";

/** Shown in place of the study list when `ncts` is empty (Req 8.4). */
const NO_CONTRIBUTING_STUDIES_MESSAGE =
  "No contributing studies are available.";

/**
 * The Evidence page. Reads the `:measureId` route param, resolves it against
 * the loaded Evidence_Data, and renders the matching entry's provenance. The
 * `data_as_of` date comes from Sources_Data in its own load-state region.
 */
export default function Evidence() {
  const { measureId } = useParams<{ measureId: string }>();
  const evidenceState = useEvidenceData();

  return (
    <section aria-labelledby="evidence-heading">
      <h1 id="evidence-heading">Evidence and data provenance</h1>

      <LoadStateView state={evidenceState}>
        {(entries) => {
          const entry = entries.find((e) => e.measure_id === measureId);
          if (entry === undefined) {
            // Unknown id: explicit not-found message + a link back to WHAT
            // that navigates client-side without a full document reload.
            return (
              <div role="status">
                <p>{DISEASE_NOT_FOUND_MESSAGE}</p>
                <Link to="/what">Back to all diseases</Link>
              </div>
            );
          }
          return <EvidenceDetails entry={entry} />;
        }}
      </LoadStateView>
    </section>
  );
}

/** Render one resolved Evidence_Entry plus the "Data as of" date region. */
function EvidenceDetails({ entry }: { entry: EvidenceEntry }) {
  return (
    <article aria-label={`Evidence for ${entry.condition}`}>
      <h2>{entry.condition}</h2>

      <DataAsOf />

      <section aria-labelledby="evidence-studies-heading">
        <h3 id="evidence-studies-heading">Contributing studies</h3>
        {entry.ncts.length === 0 ? (
          // No studies: a message and NO link element, so nothing is broken (Req 8.4).
          <p role="status">{NO_CONTRIBUTING_STUDIES_MESSAGE}</p>
        ) : (
          <ul>
            {entry.ncts.map((nct) => (
              <li key={nct.nct_id}>
                <a href={nct.url} target="_blank" rel="noopener noreferrer">
                  {nct.nct_id}
                </a>
              </li>
            ))}
          </ul>
        )}
      </section>

      <StringListSection
        headingId="evidence-filters-heading"
        heading="Applied filters"
        items={entry.filters}
      />
      <StringListSection
        headingId="evidence-mapping-heading"
        heading="Mapping choices"
        items={entry.mapping_choices}
      />
      <StringListSection
        headingId="evidence-missing-heading"
        heading="Missing data notes"
        items={entry.missing_data_notes}
      />
    </article>
  );
}

/**
 * The "Data as of" region (Req 8.3). Reads the date from Sources_Data in its
 * own `LoadStateView` so a failed/absent `sources.json` degrades on its own
 * without blanking the evidence content.
 */
function DataAsOf() {
  const sourcesState = useSources();
  return (
    <LoadStateView state={sourcesState}>
      {(sources) => <p>Data as of {sources.data_as_of}</p>}
    </LoadStateView>
  );
}

/**
 * A labeled list of plain strings (filters / mapping choices / missing-data
 * notes). An empty array renders only the heading and no empty list, so no
 * placeholder content appears.
 */
function StringListSection({
  headingId,
  heading,
  items,
}: {
  headingId: string;
  heading: string;
  items: string[];
}) {
  return (
    <section aria-labelledby={headingId}>
      <h3 id={headingId}>{heading}</h3>
      {items.length > 0 && (
        <ul>
          {items.map((item, index) => (
            <li key={`${index}-${item}`}>{item}</li>
          ))}
        </ul>
      )}
    </section>
  );
}
