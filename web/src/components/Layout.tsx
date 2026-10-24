// Shared application shell: SkipLink + Nav + <main> + Footer (Req 13.1, 14.1,
// 14.2, 14.4, 15.3, 15.4, 15.7).
//
// `Layout` is the single shell wrapped around every routed page, so the
// persistent navigation and the Footer (and its disclaimer) appear on all
// pages (Req 13.1, 14.1). It is designed to work either as a react-router
// route `element` (rendering the matched child route through <Outlet/>) OR as
// a plain wrapper around explicit `children` — whichever task 14 wires up.
//
// Three accessibility behaviours live here:
//   - SkipLink: a "skip to main content" link that is visually hidden until it
//     receives keyboard focus, letting keyboard/screen-reader users jump past
//     the nav straight to #main (Req 15.3, 15.4).
//   - Nav: react-router <NavLink>s that mark the active route with
//     aria-current="page" and a visible active style (Req 14.2, 14.4).
//   - Focus management: on every route change keyboard focus is moved to the
//     <main id="main"> element (made focusable with tabIndex={-1}) so keyboard
//     and screen-reader users land on the new page content, not stranded on the
//     previous page's control (Req 15.7).

import { useEffect, useRef } from "react";
import type { ReactNode } from "react";
import { Link, NavLink, Outlet, useLocation } from "react-router-dom";
import { Footer } from "./Footer";
import { useIsSample } from "../data/providers";
import "./Layout.css";

/** The visible text of the sample-data label (Req 2.7). */
export const SAMPLE_DATA_LABEL = "Sample data — not real figures";

/** The five top-level destinations in the persistent nav (Req 14.1). */
const NAV_LINKS: ReadonlyArray<{ to: string; label: string }> = [
  { to: "/", label: "Home" },
  { to: "/what", label: "WHAT" },
  { to: "/where", label: "WHERE" },
  { to: "/method", label: "Method" },
  { to: "/build", label: "Build" },
];

/**
 * A "skip to main content" link. It is the first focusable element on the page
 * and is visually hidden until focused (see Layout.css `.skip-link`), so
 * keyboard users can bypass the navigation and jump to `#main` (Req 15.3, 15.4).
 */
export function SkipLink() {
  return (
    <a className="skip-link" href="#main">
      Skip to main content
    </a>
  );
}

/**
 * Persistent primary navigation (Req 14.1, 14.2, 14.4). Each link is a
 * react-router <NavLink> so navigation is client-side with no full-document
 * reload. NavLink sets `aria-current="page"` on the active link by default
 * (Req 14.2); we add an `is-active` class for a visible active style (Req 14.4).
 * The Home link uses `end` so it is only active on the exact "/" route rather
 * than on every path.
 */
export function Nav() {
  return (
    <nav className="nav" aria-label="Primary">
      <ul className="nav__list">
        {NAV_LINKS.map(({ to, label }) => (
          <li key={to} className="nav__item">
            <NavLink
              to={to}
              end={to === "/"}
              className={({ isActive }) =>
                isActive ? "nav__link is-active" : "nav__link"
              }
            >
              {label}
            </NavLink>
          </li>
        ))}
      </ul>
    </nav>
  );
}

/**
 * The sample-data label (Req 2.7). Rendered in the header region, above the Nav,
 * so it is visible within the first screen at 375 px without scrolling. It reads
 * `useIsSample()` (which requires `SourcesProvider` in scope — the router wraps
 * the whole app in it for the Footer) and renders nothing unless the loaded
 * `sources.json` is flagged `is_sample: true`.
 */
export function SampleDataBanner() {
  const isSample = useIsSample();
  if (!isSample) {
    return null;
  }
  return (
    <p className="sample-banner" role="status">
      {SAMPLE_DATA_LABEL}
    </p>
  );
}

/**
 * The shared shell. Renders, in order, the SkipLink, the sample-data banner, the
 * Nav, the routed page inside `<main id="main" tabIndex={-1}>`, and the Footer.
 * If `children` are provided they are rendered inside `<main>`; otherwise the
 * matched child route is rendered through react-router's <Outlet/> (Req 13.1).
 *
 * Focus management: a ref on `<main>` plus an effect keyed to the current
 * pathname moves keyboard focus to `#main` after each route change (Req 15.7).
 */
export default function Layout({ children }: { children?: ReactNode }) {
  const location = useLocation();
  const mainRef = useRef<HTMLElement>(null);

  useEffect(() => {
    // Move keyboard focus to the main region on every route change so keyboard
    // and screen-reader users land on the new page's content (Req 15.7).
    mainRef.current?.focus();
  }, [location.pathname]);

  return (
    <div className="layout">
      <SkipLink />
      {/* Slim sample-data pill strip, above the header so it is above the fold
          at 375 px (Req 2.7). */}
      <SampleDataBanner />
      {/* Header bar: product name on the left, primary nav on the right. The
          brand is a Link (not a heading) so it never collides with a page's
          own <h1>. */}
      <header className="site-header">
        <div className="site-header__inner">
          <Link to="/" className="site-header__brand">
            Research Gap Index
          </Link>
          <Nav />
        </div>
      </header>
      <main id="main" tabIndex={-1} ref={mainRef} className="layout__main">
        {children ?? <Outlet />}
      </main>
      <Footer />
    </div>
  );
}
