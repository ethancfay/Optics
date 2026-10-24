// Shared loading / error / empty presentational helpers for the data layer
// (Req 3.2, 3.3, 3.5, 3.6).
//
// Every page consumes one or more `LoadState`s from the providers in
// `../data/providers`. These three small components render the exact, plain-
// language, grade-8 messages the design specifies for the non-`ready` states,
// so error and empty copy is identical everywhere and lives in one place:
//
//   - loading -> a loading indicator (Req 3.2)
//   - error   -> "This data is currently unavailable" naming the file (Req 1.7, 3.3)
//   - empty   -> "No valid data is available" (Req 3.5)
//
// None of these render a partial, stale, or placeholder number for a failed
// file (Req 1.7, 3.6). Pages degrade PER FILE: each page region wraps only the
// one provider it depends on, so one file's failure never blanks another file's
// content (Req 3.6, 13.5).

import type { ReactNode } from "react";
import type { LoadState } from "../data/types";

/** The exact unavailable-data message; the file name is appended after it. */
export const DATA_UNAVAILABLE_MESSAGE = "This data is currently unavailable";

/** The exact empty-data message shown when every entry was omitted / none exist. */
export const NO_VALID_DATA_MESSAGE = "No valid data is available";

/**
 * Loading indicator shown in place of data content while a file is still being
 * fetched (Req 3.2). `role="status"` + `aria-live="polite"` announces the state
 * to assistive technology without stealing focus.
 */
export function LoadingIndicator({
  label = "Loading data",
}: {
  label?: string;
}) {
  return (
    <p role="status" aria-live="polite" className="load-state load-state--loading">
      {label}…
    </p>
  );
}

/**
 * Error message for a failed file load (Req 1.7, 3.3). Always names the specific
 * file that could not be loaded and renders no partial or placeholder numbers.
 * `role="alert"` surfaces the failure to assistive technology.
 */
export function DataUnavailable({ file }: { file: string }) {
  return (
    <p role="alert" className="load-state load-state--error">
      {DATA_UNAVAILABLE_MESSAGE} ({file}).
    </p>
  );
}

/**
 * Empty-state message shown when the file loaded but has no usable entries
 * (Req 3.5). Renders no empty chart/table/list — just the message.
 */
export function NoValidData() {
  return (
    <p role="status" className="load-state load-state--empty">
      {NO_VALID_DATA_MESSAGE}.
    </p>
  );
}

/**
 * Render helper that handles the three non-`ready` states uniformly and hands
 * the loaded data to `render` only once the state is `ready` (Req 3.2, 3.3, 3.5).
 *
 * Usage keeps each page region tied to a single file so failures degrade
 * independently (Req 3.6):
 *
 *   const state = useWhatData();
 *   return <LoadStateView state={state}>{(data) => <Chart data={data} />}</LoadStateView>;
 *
 * Optional slots let a caller override any state (e.g. a page-specific empty
 * message like "No diseases are available") while still reusing the shared
 * loading/error handling for the others.
 */
export function LoadStateView<T>({
  state,
  children,
  loading,
  empty,
  error,
}: {
  state: LoadState<T>;
  children: (data: T) => ReactNode;
  loading?: ReactNode;
  empty?: ReactNode;
  error?: (file: string, reason: "timeout" | "network" | "parse") => ReactNode;
}): ReactNode {
  switch (state.status) {
    case "loading":
      return loading ?? <LoadingIndicator />;
    case "error":
      return error
        ? error(state.file, state.reason)
        : <DataUnavailable file={state.file} />;
    case "empty":
      return empty ?? <NoValidData />;
    case "ready":
      return children(state.data);
  }
}
