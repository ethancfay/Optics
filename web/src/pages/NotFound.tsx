// NotFoundPage — route component for the `*` catch-all (Req 14.3).
//
// When a reader opens a URL that matches no known route, the app degrades
// gracefully: it shows a clear "page not found" message and a react-router
// `<Link>` back to Home (`/`) so navigation happens without a full document
// reload. This is a static route component that reads no providers.

import { Link } from "react-router-dom";

/**
 * NotFoundPage route component. Default export named `NotFound` so the router
 * (task 14) imports it as `NotFound`.
 */
export default function NotFound() {
  return (
    <div className="not-found-page">
      <h1>Page not found</h1>
      <p>
        We could not find the page you asked for. The link may be out of date,
        or the address may have a typo.
      </p>
      <p className="not-found-page__home-link">
        <Link to="/">Go back to the home page</Link>
      </p>
    </div>
  );
}
