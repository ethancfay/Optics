// Pure selector for the Investigate page headline (Req 19.3, 19.5, 19.7).
//
// The headline count is the WHAT `t` for the same measure_id, read from
// What_Data so WHAT and Investigate share one source of truth. It is never
// taken from investigate.json. A missing entry yields `t: null` (shown as
// "unknown", never 0) and a missing/empty `prevalence_year` yields `null`
// (the year line is omitted).

import type { WhatEntry } from "./types";

export interface InvestigateHeadline {
  t: number | null;
  prevalenceYear: string | null;
}

export function selectInvestigateHeadline(
  whatEntries: readonly WhatEntry[],
  measureId: string | undefined
): InvestigateHeadline {
  const entry = whatEntries.find((e) => e.measure_id === measureId);
  if (entry === undefined) return { t: null, prevalenceYear: null };
  const year = entry.prevalence_year;
  return {
    t: entry.t,
    prevalenceYear: typeof year === "string" && year.trim().length > 0 ? year : null,
  };
}
