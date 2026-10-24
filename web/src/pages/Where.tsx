// Where_View — route component for `/where` (Req 9, 10).
//
// The WHERE view answers "how far is the nearest VERIFIED recruiting site?" per
// Massachusetts county, for a selected disease. It composes TWO data files:
//
//   - Where_Data (`where.json`) via `useWhereData()` — the per-county distances.
//   - County_Boundaries (`ma_counties.geojson`) via `useCountyBoundaries()` —
//     the SVG geometry the choropleth is drawn from.
//
// The actual rendering (the SVG choropleth, the disease `<select>`, the text-
// alternative table, the legend, and the internal "No distance data is
// available" empty message) all live in `CountyMap`, which is purely
// presentational and never fetches. This page owns the providers' loading /
// error / empty wiring and hands both validated inputs to `CountyMap` only once
// BOTH files are ready (Req 9.1, 9.2, 9.6, 10.4).
//
// Degradation is PER FILE (Req 3.6, 13.5): the two LoadStates are evaluated
// independently, so if boundaries fail but where-data loads (or vice versa) the
// page shows the appropriate unavailable / loading / empty message naming the
// failing file via the shared `LoadStateView` helpers, and the map renders only
// when both files are ready. Neither failure blanks the other's status.
//
// The router (task 14) wraps this page in `WhereDataProvider` +
// `CountyBoundariesProvider`; the hooks throw if used outside those providers.

import { useWhereData, useCountyBoundaries } from "../data/providers";
import { LoadStateView } from "../components/LoadStateView";
import { CountyMap } from "../components/CountyMap";
import type { WhereEntry, CountyFeature } from "../data/types";

/**
 * Where_View route component. Default export named for the route so the router
 * (task 14) imports it as `Where`.
 *
 * The two LoadStates are composed by NESTING the shared `LoadStateView` helper:
 * the outer view resolves County_Boundaries, the inner view resolves Where_Data,
 * and `CountyMap` is rendered only in the innermost `ready`/`ready` branch. Each
 * helper independently renders the loading / error (naming its file) / empty
 * message for its own file, so a single file's failure degrades on its own.
 */
export default function Where() {
  const boundariesState = useCountyBoundaries();
  const whereState = useWhereData();

  return (
    <div className="where-page">
      <h1>Distance to the nearest verified recruiting site</h1>
      <p className="where-intro">
        For a selected disease, this map shows how far each Massachusetts county
        is from the nearest verified recruiting site. Counties with no distance
        data are shown as unknown.
      </p>

      <LoadStateView<CountyFeature[]> state={boundariesState}>
        {(features) => (
          <LoadStateView<WhereEntry[]> state={whereState}>
            {(whereData) => (
              <CountyMap features={features} whereData={whereData} />
            )}
          </LoadStateView>
        )}
      </LoadStateView>
    </div>
  );
}
