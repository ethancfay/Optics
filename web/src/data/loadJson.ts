// The single place that turns a same-origin JSON fetch into a typed LoadState
// (Req 1.7, 3.1-3.6). Every provider (task 7) delegates here so error handling,
// the 10-second timeout, per-entry validation/omission, and the empty/ready
// mapping all live in one spot.
//
// Runtime request policy (Req 1.2): callers pass a bare file name (e.g.
// "what.json") and this module fetches it as a relative, same-origin path under
// the Data_Directory `/data/`. It never constructs an absolute URL to another
// origin, so no runtime request can leave the Dashboard's own origin.

import type { LoadState, SourcesData } from "./types";
import { validateSourcesData } from "./validators";

/** Same-origin directory every data file is served from (Req 1.2). */
const DATA_DIRECTORY = "/data/";

/** Abort a slow fetch after this many milliseconds (Req 3.2, 3.3). */
const TIMEOUT_MS = 10_000;

/**
 * A per-entry type guard: narrows an unknown parsed value to the entry type `E`.
 * This is exactly the signature exported by every validator in `./validators`
 * (e.g. `validateWhatEntry`), so they can be passed straight through.
 */
type EntryGuard<E> = (value: unknown) => value is E;

/**
 * Build the same-origin request path for a data file. Accepts either a bare
 * file name ("what.json") or an already-rooted "/data/..." path and always
 * returns a relative path under the Data_Directory, never an absolute URL to
 * another origin (Req 1.2).
 */
function toDataPath(file: string): string {
  if (file.startsWith(DATA_DIRECTORY)) {
    return file;
  }
  return DATA_DIRECTORY + file.replace(/^\/+/, "");
}

/**
 * Fetch `file` with a 10-second abort timeout and return the parsed JSON body,
 * or a mapped error state. On network failure / 404 / a non-timeout abort this
 * returns `error:"network"`; when the request is aborted because it exceeded
 * the timeout it returns `error:"timeout"`; on invalid JSON it returns
 * `error:"parse"`. Each error names the file (Req 1.7, 3.2, 3.3).
 *
 * The timer is always cleared in a `finally` so a fast, successful load never
 * leaves a dangling abort timer running against an already-settled request.
 */
async function fetchJson(
  file: string
): Promise<{ ok: true; body: unknown } | { ok: false; state: LoadState<never> }> {
  const controller = new AbortController();
  let timedOut = false;
  const timer = setTimeout(() => {
    timedOut = true;
    controller.abort();
  }, TIMEOUT_MS);

  let response: Response;
  try {
    response = await fetch(toDataPath(file), { signal: controller.signal });
  } catch {
    // fetch rejected: a genuine network failure, or an abort. An abort caused
    // by our timeout is reported as "timeout"; anything else is "network"
    // (Req 3.2, 3.3).
    return {
      ok: false,
      state: {
        status: "error",
        reason: timedOut ? "timeout" : "network",
        file,
      },
    };
  } finally {
    clearTimeout(timer);
  }

  // A 404 (or any non-2xx) is treated as the file being unavailable (Req 1.7, 3.3).
  if (!response.ok) {
    return {
      ok: false,
      state: { status: "error", reason: "network", file },
    };
  }

  try {
    const body: unknown = await response.json();
    return { ok: true, body };
  } catch {
    // Body is not valid JSON (Req 3.3).
    return {
      ok: false,
      state: { status: "error", reason: "parse", file },
    };
  }
}

/**
 * Load a same-origin array-of-entries JSON file (what.json, investigate.json,
 * evidence.json, where.json) and map it to a `LoadState<E[]>` (Req 3.1-3.6).
 *
 * Steps:
 *   1. Fetch `file` under `/data/` with a 10-second timeout.
 *   2. On network/404/abort -> `error:"network"` ("timeout" when aborted by the
 *      timeout); on invalid JSON or a non-array top-level shape -> `error:"parse"`.
 *   3. Validate each element with `validateEntry`, keeping the valid ones in
 *      their original order and counting the omitted ones as `omittedCount`.
 *   4. If every entry was omitted (or the array was empty) -> `empty`.
 *   5. Otherwise -> `ready` with the surviving entries, `omittedCount`, and
 *      `isSample: false` (the sample flag lives only in sources.json; see
 *      `loadSources`).
 *
 * `file` is a bare file name such as "what.json"; it is always fetched as a
 * relative same-origin path and never as a URL to another origin (Req 1.2).
 */
export async function loadJson<E>(
  file: string,
  validateEntry: EntryGuard<E>
): Promise<LoadState<E[]>> {
  const result = await fetchJson(file);
  if (!result.ok) {
    return result.state;
  }

  // Wrong top-level shape: these files must be a JSON array (Req 3.3).
  if (!Array.isArray(result.body)) {
    return { status: "error", reason: "parse", file };
  }

  // Per-entry validation: omit invalid entries, preserve order, count omissions
  // (Req 3.4). A single malformed entry never blanks the whole file.
  const valid: E[] = [];
  let omittedCount = 0;
  for (const entry of result.body) {
    if (validateEntry(entry)) {
      valid.push(entry);
    } else {
      omittedCount += 1;
    }
  }

  // Top-level shape was valid but nothing survived (or it was empty): the empty
  // state, never a `ready` state carrying zero usable entries (Req 3.5).
  if (valid.length === 0) {
    return { status: "empty" };
  }

  return {
    status: "ready",
    data: valid,
    omittedCount,
    isSample: false,
  };
}

/**
 * Load sources.json, whose top-level shape is a single object
 * (`{ data_as_of, is_sample?, sources: [...] }`) rather than an array
 * (Req 2.5). It is validated as a whole with `validateSourcesData`:
 *
 *   - network/404/abort -> `error:"network"` / `"timeout"`;
 *   - invalid JSON or a shape that fails `validateSourcesData` -> `error:"parse"`;
 *   - a valid object with no sources -> `empty`;
 *   - otherwise -> `ready` carrying the whole `SourcesData` object, with
 *     `isSample` taken from the file's optional `is_sample` flag (Req 2.7) and
 *     `omittedCount: 0` (sources are validated as one object, not per entry).
 */
export async function loadSources(
  file = "sources.json"
): Promise<LoadState<SourcesData>> {
  const result = await fetchJson(file);
  if (!result.ok) {
    return result.state;
  }

  // Wrong top-level shape (not a valid SourcesData object) -> parse error (Req 3.3).
  if (!validateSourcesData(result.body)) {
    return { status: "error", reason: "parse", file };
  }

  const data = result.body;
  if (data.sources.length === 0) {
    return { status: "empty" };
  }

  return {
    status: "ready",
    data,
    omittedCount: 0,
    isSample: data.is_sample === true,
  };
}
