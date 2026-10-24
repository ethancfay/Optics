// Pure logic for disease conditions (Req 4.2, 4.3, 5.3, 6.2, 16.1).
//
// This module holds small, pure, non-mutating functions over What_Data. They
// never fetch, never mutate their inputs, and never recompute the index — they
// operate on the precomputed low/mid/high values carried by each WhatEntry.

import type { WhatEntry } from "./types";

/**
 * Select the "top finding" for the Home page: the disease with the minimum
 * `mid`, with ties broken by the case-insensitively smallest `condition`
 * (Req 4.2, 4.3).
 *
 * Returns `undefined` when there are no entries, so callers can render the
 * "no disease data available" message.
 *
 * Pure and non-mutating: does not sort or otherwise modify `entries`.
 */
export function selectTopFinding(
  entries: readonly WhatEntry[]
): WhatEntry | undefined {
  let best: WhatEntry | undefined;
  for (const entry of entries) {
    if (best === undefined) {
      best = entry;
      continue;
    }
    if (entry.mid < best.mid) {
      best = entry;
      continue;
    }
    if (entry.mid === best.mid) {
      const a = entry.condition.toLowerCase();
      const b = best.condition.toLowerCase();
      if (a < b) {
        best = entry;
      }
    }
  }
  return best;
}

/**
 * Sort diseases ascending by their index midpoint `mid`, with ties broken by
 * the case-insensitively smallest `condition` (Req 5.3, 6.2, 16.1).
 *
 * Returns a NEW array; the input is never mutated (it is spread before
 * sorting), so callers can reuse the original order.
 */
export function sortConditions(
  entries: readonly WhatEntry[]
): WhatEntry[] {
  return [...entries].sort((a, b) => {
    if (a.mid !== b.mid) {
      return a.mid - b.mid;
    }
    const ca = a.condition.toLowerCase();
    const cb = b.condition.toLowerCase();
    if (ca < cb) return -1;
    if (ca > cb) return 1;
    return 0;
  });
}
