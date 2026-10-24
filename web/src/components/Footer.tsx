// Footer — present on every page via Layout (Req 13.1).
//
// The Footer consumes Sources_Data through the `useSources()` hook (a
// `LoadState<SourcesData>` exposed by `../data/providers`). Its contract is
// special compared to other data-dependent regions: the Disclaimer_Text must
// render in EVERY state — loading, error, empty, and ready — so the site is
// never presented without its disclaimer (Req 13.1, 13.2). Only the source
// links and the "Data as of" date depend on a successful load.
//
// This is why the Footer implements its own state handling rather than
// delegating to the shared `LoadStateView` helper: the non-ready fallback here
// is the specific message "Source information is unavailable" (Req 13.5), not
// the generic shared loading/error/empty strings, and the disclaimer sits
// OUTSIDE the state switch so it always shows.
//
//   - ready  -> one named link per Source_Entry + the `data_as_of` value
//               labeled "Data as of" (Req 13.3, 13.4).
//   - error  -> disclaimer + "Source information is unavailable" (Req 13.5).
//   - loading / empty -> same fallback as error: the disclaimer plus
//               "Source information is unavailable" in place of links and date,
//               so no partial or placeholder source information is ever shown.

import { useSources } from "../data/providers";

/** The exact Disclaimer_Text; shown in every Sources load state (Req 13.2). */
export const DISCLAIMER_TEXT = "Not medical advice. Index, not prediction.";

/** Shown in place of the links and date whenever Sources_Data is not ready (Req 13.5). */
export const SOURCE_INFO_UNAVAILABLE_MESSAGE =
  "Source information is unavailable";

/**
 * Site footer. Renders the disclaimer unconditionally, then either the live
 * source links + "Data as of" date (on a successful load) or the
 * source-unavailable message (while loading, when empty, or on error).
 */
export function Footer() {
  const sources = useSources();

  return (
    <footer className="footer">
      {/* Disclaimer is rendered regardless of the Sources load state (Req 13.1, 13.2). */}
      <p className="footer__disclaimer">{DISCLAIMER_TEXT}</p>

      {sources.status === "ready" ? (
        <div className="footer__sources">
          <ul className="footer__source-links">
            {sources.data.sources.map((source) => (
              <li key={source.url}>
                <a
                  href={source.url}
                  rel="noopener noreferrer"
                  target="_blank"
                >
                  {source.name}
                </a>
              </li>
            ))}
          </ul>
          <p className="footer__data-as-of">
            Data as of {sources.data.data_as_of}
          </p>
        </div>
      ) : (
        // loading / empty / error all degrade to the same fallback so no
        // partial or placeholder source information is ever shown (Req 13.5).
        <p className="footer__sources-unavailable">
          {SOURCE_INFO_UNAVAILABLE_MESSAGE}
        </p>
      )}
    </footer>
  );
}

// Export both a named and a default binding so Layout resolves whichever import
// form it uses (`import { Footer }` or `import Footer`).
export default Footer;
