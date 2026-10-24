// AppRouter — wires the routing table, the shared Layout, and the per-page data
// providers (Req 1.1, 2.7, 4.5, 14.1, 14.2, 14.3, 14.4).
//
// Provider placement (per design "Data layer" + the per-page notes):
//   - SourcesProvider wraps the WHOLE app. The Footer (rendered by Layout on
//     every page) and the sample-data label both read Sources_Data, so it must
//     be in scope on every route (Req 13.1, 2.7). It is the one file whose
//     provider lives above the routes.
//   - Every OTHER file's provider wraps only the route(s) that need it, placed
//     on the route `element`. React Router mounts a route element fresh on each
//     navigation to that path, so each of those providers runs its single fetch
//     once per page view (fetch-once-per-page, Req 16.3) and unmounts when you
//     leave the page.
//
// Routing uses `BrowserRouter` for the app entry (tests mount routes under
// `MemoryRouter` separately). Layout is used as a layout route: it renders the
// shared shell and the matched child route through its <Outlet/>. All in-app
// navigation is via react-router <Link>/<NavLink> inside the pages/Nav, so no
// full-document reload occurs (Req 4.5, 14.2). Unknown paths fall through to the
// `*` route and render NotFound; `web/vercel.json` rewrites deep links to
// index.html so direct-URL entry resolves (Req 14.3).

import { BrowserRouter, Routes, Route } from "react-router-dom";
import Layout from "./components/Layout";
import {
  SourcesProvider,
  WhatDataProvider,
  InvestigateDataProvider,
  EvidenceDataProvider,
} from "./data/providers";
import type { ReactNode } from "react";

import Home from "./pages/Home";
import What from "./pages/What";
import Investigate from "./pages/Investigate";
import Evidence from "./pages/Evidence";
// The WHERE view is hidden in this version (no county-shape data source inside
// clinicaltrials.gov / data.cdc.gov). `pages/Where`, `components/CountyMap`,
// and the Where/CountyBoundaries providers are intentionally kept but unrouted.
import Method from "./pages/Method";
import Build from "./pages/Build";
import NotFound from "./pages/NotFound";

/**
 * The routing table (design "Routing table"). Declared as a standalone element
 * tree so both `App` (with `BrowserRouter`) and tests (with `MemoryRouter`) can
 * mount the same routes. Each page element is wrapped in exactly the providers
 * that its hooks read, so navigating to a page mounts its provider fresh and
 * fetches its file once per page view (Req 16.3). The whole table is nested
 * under the `Layout` layout route, which supplies the Nav + Footer shell and
 * renders the matched page through its <Outlet/>.
 */
export function AppRoutes() {
  return (
    <Routes>
      <Route element={<Layout />}>
        {/* Home and WHAT both read What_Data. */}
        <Route path="/" element={withProvider(WhatDataProvider, <Home />)} />
        <Route path="/what" element={withProvider(WhatDataProvider, <What />)} />

        {/* Investigate reads Investigate_Data by :measureId, What_Data for the
            headline `t` and prevalence_year (Req 19.3, 19.7), and Evidence_Data
            for the client-side No_Intervention_Count (Flag F1, Req 16.1). */}
        <Route
          path="/investigate/:measureId"
          element={withProvider(
            WhatDataProvider,
            withProvider(
              InvestigateDataProvider,
              withProvider(EvidenceDataProvider, <Investigate />)
            )
          )}
        />

        {/* Evidence reads Evidence_Data (the NCT list) and Sources_Data (the
            "Data as of" date). Sources is already in scope app-wide, so only
            EvidenceDataProvider is added here. */}
        <Route
          path="/evidence/:measureId"
          element={withProvider(EvidenceDataProvider, <Evidence />)}
        />

        {/* The WHERE view is hidden in this version: no route and no nav link
            (county shapes need a data source outside clinicaltrials.gov /
            data.cdc.gov). A direct hit on /where falls through to NotFound. */}

        {/* Method reads Sources_Data, already in scope app-wide. */}
        <Route path="/method" element={<Method />} />

        {/* Build needs no data file. */}
        <Route path="/build" element={<Build />} />

        {/* Any unknown path renders the NotFound page (Req 14.3). */}
        <Route path="*" element={<NotFound />} />
      </Route>
    </Routes>
  );
}

/** Wrap a page element in a single data provider. */
function withProvider(
  Provider: ({ children }: { children: ReactNode }) => ReactNode,
  page: ReactNode
): ReactNode {
  return <Provider>{page}</Provider>;
}

/**
 * The application root. `SourcesProvider` wraps the entire router so the Footer
 * and the sample-data label (both rendered by `Layout` on every page) always
 * have Sources_Data in scope (Req 13.1, 2.7). `BrowserRouter` provides
 * client-side routing with direct-URL entry (Req 14.3).
 */
export default function App() {
  return (
    <SourcesProvider>
      <BrowserRouter>
        <AppRoutes />
      </BrowserRouter>
    </SourcesProvider>
  );
}
