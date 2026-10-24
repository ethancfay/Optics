// Card — the reusable navy card container with light inner panels and a large
// corner radius (Req 2.2, Req 6.5).
//
// This is a RESTYLE VEHICLE ONLY: a presentational wrapper with no data logic.
// It wraps page content in a navy card (`--card`) with a large rounded corner
// (`--radius-card`, >= 12px) and optional light inner panels. Pages compose
// their existing content and copy inside Card; data wiring stays in the pages.
//
// Colour is never the sole carrier of meaning here: the card is a container,
// and its optional title is plain text. All colours reference the palette
// custom properties in `src/styles/palette.css` (single source of truth).

import type { ReactNode } from "react";
import "./Card.css";

/** Props for {@link Card}. */
export interface CardProps {
  /**
   * Optional card title. When provided, it renders as a heading at the top of
   * the card. Accepts a string or arbitrary nodes so a page can supply its own
   * heading element if it needs a specific level.
   */
  title?: ReactNode;
  /** Page content wrapped by the card. */
  children?: ReactNode;
  /** Optional extra class names appended to the base `card` class. */
  className?: string;
}

/**
 * A navy card container. Renders an optional title above the wrapped children.
 * Presentational only — it holds no state and performs no data loading.
 */
export default function Card({ title, children, className }: CardProps) {
  const classes = className ? `card ${className}` : "card";
  return (
    <section className={classes}>
      {title !== undefined && title !== null && title !== "" ? (
        <h2 className="card-title">{title}</h2>
      ) : null}
      <div className="card-body">{children}</div>
    </section>
  );
}
