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
import { useSources } from "../data/providers";
import "./Layout.css";

/** The visible text of the sample-data label (Req 2.7). */
export const SAMPLE_DATA_LABEL = "Sample data — not real figures";

/**
 * Inline SVG icons for the Nav_Icon_Buttons (Req 4.2). Each icon is marked
 * `aria-hidden` and `focusable={false}` so it is ignored by assistive tech: the
 * accessible name comes from the button's `aria-label` and its visible text
 * label, never from the icon shape (Req 4.3). `currentColor` lets the icon
 * inherit the link colour so the active/hover/focus styles apply to it too.
 */
const ICON_PROPS = {
  className: "nav__icon",
  width: 20,
  height: 20,
  viewBox: "0 0 24 24",
  fill: "none",
  stroke: "currentColor",
  strokeWidth: 2,
  strokeLinecap: "round" as const,
  strokeLinejoin: "round" as const,
  "aria-hidden": true,
  focusable: false,
};

/** Home icon: a simple house outline. */
function HomeIcon() {
  return (
    <svg {...ICON_PROPS}>
      <path d="M3 10.5 12 3l9 7.5" />
      <path d="M5 9.5V21h14V9.5" />
    </svg>
  );
}

/** WHAT icon: a bar chart (Req 4.2). */
function ChartIcon() {
  return (
    <svg {...ICON_PROPS}>
      <path d="M3 21h18" />
      <rect x="5" y="12" width="3.5" height="6" />
      <rect x="10.25" y="8" width="3.5" height="10" />
      <rect x="15.5" y="4" width="3.5" height="14" />
    </svg>
  );
}

/** Method icon: a square-root-of-x radical sign (Req 4.2). */
function SquareRootIcon() {
  return (
    <svg {...ICON_PROPS}>
      <path d="M3 13l2.5 5L9 5h11" />
    </svg>
  );
}

/** Build icon: a wrench/tool outline. */
function BuildIcon() {
  return (
    <svg {...ICON_PROPS}>
      <path d="M14.5 5.5a3.5 3.5 0 0 0 4.6 4.6L21 12l-8 8-2-2-5.5 5.5" />
      <path d="M4 20l5.5-5.5" />
    </svg>
  );
}

/**
 * The top-level destinations in the persistent nav (Req 14.1, 4.1). Each entry
 * is a Nav_Icon_Button: an icon (Req 4.2) plus a visible text label and a
 * non-empty `aria-label` (Req 4.3). The WHERE view is hidden in this version:
 * county shapes would need a data source outside clinicaltrials.gov /
 * data.cdc.gov, so it is not routed or linked (data contract: where.json /
 * ma_counties.geojson deferred). The Where component code is kept but unused.
 */
const NAV_LINKS: ReadonlyArray<{
  to: string;
  label: string;
  icon: () => ReactNode;
}> = [
  { to: "/", label: "Home", icon: HomeIcon },
  { to: "/what", label: "WHAT", icon: ChartIcon },
  { to: "/method", label: "Method", icon: SquareRootIcon },
  { to: "/build", label: "Build", icon: BuildIcon },
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
 * Persistent primary navigation (Req 4.1, 4.3-4.6). Each destination is a
 * Nav_Icon_Button: a react-router <NavLink> so activation by click, Enter, or
 * Space navigates client-side with no full-document reload (Req 4.4). Each
 * button carries an icon (Req 4.2), a visible text label AND a title tooltip,
 * plus a non-empty `aria-label` (Req 4.3) — the label text matches the
 * aria-label so the accessible name is stable regardless of the icon shape.
 *
 * Active state (Req 4.5): NavLink sets `aria-current="page"` on the active link
 * by default; we add an `is-active` class whose active cue is NOT colour alone
 * — a bold label, an underline, and a leading "active" marker dot rendered via
 * CSS carry the state in addition to colour. The Home link uses `end` so it is
 * only active on the exact "/" route rather than on every path.
 *
 * Visible focus (Req 4.6) is provided by the `.nav__link:focus-visible` ring in
 * Layout.css.
 */
export function Nav() {
  return (
    <nav className="nav" aria-label="Primary">
      <ul className="nav__list">
        {NAV_LINKS.map(({ to, label, icon: Icon }) => (
          <li key={to} className="nav__item">
            <NavLink
              to={to}
              end={to === "/"}
              aria-label={label}
              title={label}
              className={({ isActive }) =>
                isActive ? "nav__link is-active" : "nav__link"
              }
            >
              <Icon />
              <span className="nav__label">{label}</span>
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
 * `useSources()` (which requires `SourcesProvider` in scope — the router wraps
 * the whole app in it for the Footer) and renders nothing unless the loaded
 * `sources.json` is flagged `is_sample: true`. It deliberately does not use the
 * cautious `useIsSample()`, which is also true while loading (Req 20.5).
 */
export function SampleDataBanner() {
  const sources = useSources();
  if (!(sources.status === "ready" && sources.isSample)) {
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
            Optics
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
