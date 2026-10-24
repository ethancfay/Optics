// React Context data layer for the Dashboard (Req 3.1, 3.2, 3.3, 3.5, 2.7, 16.3).
//
// Each of the six same-origin data files has its own provider that fetches that
// file exactly ONCE per page view (on mount) and exposes the resulting
// `LoadState` through a dedicated hook. One provider per file means a failure
// loading one file degrades independently: e.g. a failed `where.json` never
// blanks the Footer, which depends only on `sources.json` (Req 3.6, 13.5).
//
// All fetching goes through `loadJson` / `loadSources` (task 4), so the
// 10-second timeout, same-origin `/data/` path policy, per-entry
// validation/omission, and the loading -> ready/empty/error mapping all live in
// one place. The county-boundaries file is a GeoJSON FeatureCollection (an
// object, not a top-level array), so it uses a dedicated loader in this module
// that still fetches same-origin under `/data/` and maps to the same
// `LoadState` shape.

import {
  createContext,
  useContext,
  useEffect,
  useState,
  type ReactNode,
} from "react";
import { loadJson, loadSources } from "./loadJson";
import {
  validateWhatEntry,
  validateInvestigateEntry,
  validateEvidenceEntry,
  validateWhereEntry,
} from "./validators";
import type {
  LoadState,
  WhatEntry,
  InvestigateEntry,
  EvidenceEntry,
  WhereEntry,
  SourcesData,
  CountyFeature,
} from "./types";

// --- generic provider/hook factory -----------------------------------------

/**
 * Build a `{ Provider, useData }` pair around a loader that resolves to a
 * `LoadState<T>`. The provider:
 *   - starts in the `loading` state (Req 3.2),
 *   - runs the loader exactly once on mount (Req 16.3),
 *   - guards against a late `setState` after unmount with a `mounted` flag so a
 *     slow fetch that settles after the page view ends never warns or leaks.
 *
 * The returned hook throws a clear, named error when used outside its provider,
 * so a mis-wired page fails loudly in development rather than silently reading
 * a stale default.
 */
function createDataContext<T>(
  displayName: string,
  hookName: string,
  load: () => Promise<LoadState<T>>
) {
  const Context = createContext<LoadState<T> | null>(null);
  Context.displayName = displayName;

  function Provider({ children }: { children: ReactNode }) {
    const [state, setState] = useState<LoadState<T>>({ status: "loading" });

    useEffect(() => {
      let mounted = true;
      // Fetch exactly once per mount (page view). We intentionally do not pass
      // the loader in the dependency array: it is a stable module-level
      // function and we want a single fetch for the life of this provider
      // instance (Req 16.3).
      load().then((next) => {
        if (mounted) {
          setState(next);
        }
      });
      return () => {
        mounted = false;
      };
    }, []);

    return <Context.Provider value={state}>{children}</Context.Provider>;
  }
  Provider.displayName = displayName;

  function useData(): LoadState<T> {
    const value = useContext(Context);
    if (value === null) {
      throw new Error(
        `${hookName} must be used within a ${displayName}. Wrap the page in <${displayName}> before reading its data.`
      );
    }
    return value;
  }

  return { Context, Provider, useData };
}

// --- county boundaries (GeoJSON FeatureCollection) loader -------------------

/** Same-origin directory every data file is served from (mirrors loadJson). */
const DATA_DIRECTORY = "/data/";

/** Abort a slow fetch after this many milliseconds (mirrors loadJson). */
const GEOJSON_TIMEOUT_MS = 10_000;

/** True when `v` is a plain (non-null, non-array) object we can index by key. */
function isRecord(v: unknown): v is Record<string, unknown> {
  return typeof v === "object" && v !== null && !Array.isArray(v);
}

/**
 * Guard a single GeoJSON Feature against the `CountyFeature` contract (Req 2.12):
 * `type: "Feature"`, a non-empty `properties.county_fips` string, and a
 * Polygon/MultiPolygon geometry carrying a `coordinates` array. Invalid
 * features are dropped so one malformed feature never blanks the whole map.
 */
function validateCountyFeature(value: unknown): value is CountyFeature {
  if (!isRecord(value)) return false;
  if (value.type !== "Feature") return false;
  if (!isRecord(value.properties)) return false;
  const fips = value.properties.county_fips;
  if (typeof fips !== "string" || fips.trim().length === 0) return false;
  if (!isRecord(value.geometry)) return false;
  const geomType = value.geometry.type;
  if (geomType !== "Polygon" && geomType !== "MultiPolygon") return false;
  if (!Array.isArray(value.geometry.coordinates)) return false;
  return true;
}

/**
 * Load `ma_counties.geojson` and map it to a `LoadState<CountyFeature[]>`.
 *
 * `loadJson` can't be reused here because its top-level shape is a JSON array,
 * whereas GeoJSON is a `{ type: "FeatureCollection", features: [...] }` object.
 * This loader mirrors loadJson's behavior: same-origin `/data/` fetch, a 10 s
 * abort timeout, network/404/abort -> `error:"network"`/`"timeout"`, invalid
 * JSON or a non-FeatureCollection shape -> `error:"parse"`, per-feature
 * validation that omits invalid features and counts them, all-omitted/empty ->
 * `empty`, otherwise `ready` (Req 3.1-3.6).
 */
async function loadCountyBoundaries(
  file = "ma_counties.geojson"
): Promise<LoadState<CountyFeature[]>> {
  const controller = new AbortController();
  let timedOut = false;
  const timer = setTimeout(() => {
    timedOut = true;
    controller.abort();
  }, GEOJSON_TIMEOUT_MS);

  let response: Response;
  try {
    response = await fetch(DATA_DIRECTORY + file, {
      signal: controller.signal,
    });
  } catch {
    return {
      status: "error",
      reason: timedOut ? "timeout" : "network",
      file,
    };
  } finally {
    clearTimeout(timer);
  }

  if (!response.ok) {
    return { status: "error", reason: "network", file };
  }

  let body: unknown;
  try {
    body = await response.json();
  } catch {
    return { status: "error", reason: "parse", file };
  }

  // Wrong top-level shape: must be a FeatureCollection with a features array.
  if (
    !isRecord(body) ||
    body.type !== "FeatureCollection" ||
    !Array.isArray(body.features)
  ) {
    return { status: "error", reason: "parse", file };
  }

  const valid: CountyFeature[] = [];
  let omittedCount = 0;
  for (const feature of body.features) {
    if (validateCountyFeature(feature)) {
      valid.push(feature);
    } else {
      omittedCount += 1;
    }
  }

  if (valid.length === 0) {
    return { status: "empty" };
  }

  return { status: "ready", data: valid, omittedCount, isSample: false };
}

// --- the six providers + hooks ----------------------------------------------

const whatContext = createDataContext<WhatEntry[]>(
  "WhatDataProvider",
  "useWhatData()",
  () => loadJson("what.json", validateWhatEntry)
);
export const WhatDataProvider = whatContext.Provider;
/** Read the What_Data LoadState. Throws if used outside `WhatDataProvider`. */
export const useWhatData = whatContext.useData;

const investigateContext = createDataContext<InvestigateEntry[]>(
  "InvestigateDataProvider",
  "useInvestigateData()",
  () => loadJson("investigate.json", validateInvestigateEntry)
);
export const InvestigateDataProvider = investigateContext.Provider;
/** Read the Investigate_Data LoadState. Throws outside `InvestigateDataProvider`. */
export const useInvestigateData = investigateContext.useData;

const evidenceContext = createDataContext<EvidenceEntry[]>(
  "EvidenceDataProvider",
  "useEvidenceData()",
  () => loadJson("evidence.json", validateEvidenceEntry)
);
export const EvidenceDataProvider = evidenceContext.Provider;
/** Read the Evidence_Data LoadState. Throws if used outside `EvidenceDataProvider`. */
export const useEvidenceData = evidenceContext.useData;

const whereContext = createDataContext<WhereEntry[]>(
  "WhereDataProvider",
  "useWhereData()",
  () => loadJson("where.json", validateWhereEntry)
);
export const WhereDataProvider = whereContext.Provider;
/** Read the Where_Data LoadState. Throws if used outside `WhereDataProvider`. */
export const useWhereData = whereContext.useData;

const sourcesContext = createDataContext<SourcesData>(
  "SourcesProvider",
  "useSources()",
  () => loadSources("sources.json")
);
export const SourcesProvider = sourcesContext.Provider;
/** Read the Sources_Data LoadState. Throws if used outside `SourcesProvider`. */
export const useSources = sourcesContext.useData;

const countyBoundariesContext = createDataContext<CountyFeature[]>(
  "CountyBoundariesProvider",
  "useCountyBoundaries()",
  () => loadCountyBoundaries("ma_counties.geojson")
);
export const CountyBoundariesProvider = countyBoundariesContext.Provider;
/** Read the County_Boundaries LoadState. Throws outside `CountyBoundariesProvider`. */
export const useCountyBoundaries = countyBoundariesContext.useData;

/**
 * Cautious sample-data flag (Req 20.5). Returns `false` ONLY when Sources_Data
 * has loaded and the file's `is_sample` is exactly `false`; every other state
 * (loading / error / empty / `is_sample` true or absent) returns `true`, so copy
 * that claims real numbers is shown only when we are certain the data is real.
 *
 * The sample-data banner (Req 2.7) does NOT use this hook: it reads
 * `useSources()` directly and shows only for a loaded `is_sample: true`.
 * Must be used within `SourcesProvider` (throws otherwise).
 */
export function useIsSample(): boolean {
  const sources = useSources();
  return !(sources.status === "ready" && sources.data.is_sample === false);
}
