// Build_Page — route component for `/build` (Req 12).
//
// The Build page shows how this site was made with Kiro. Its title is exactly
// "How we built it with Kiro" (Req 12.1). It links to the project's spec files
// under `.kiro/`, the steering files under `.kiro/steering/`, and `KIRO_LOG.md`
// at the repository root, using full GitHub blob URLs of the form
// `https://github.com/ethancfay/research-gap-index/blob/main/<path>` (Req 12.2).
//
// Absolute GitHub URLs are required because Vercel serves only the `web/` root
// and does not serve the repository's `.kiro/` directory or `KIRO_LOG.md`, so
// site-relative paths would 404. These are outbound navigation links rendered
// with `target="_blank" rel="noopener noreferrer"`, not runtime data fetches,
// so they are allowed under the same-origin runtime policy (Req 1.2). A short
// grade-8 description explains how Kiro was used, with no Forbidden_Terms
// (Req 12.3, 17).
//
// This is a static route component: it reads no providers and loads no data.
//
// Restyle (Req 12.1): the page content is wrapped in a single reusable Card
// titled exactly "How we built it with Kiro"; all existing copy and links are
// preserved unchanged.

import Card from "../components/Card";

/** Base for every GitHub blob link; the repo's default branch is `main`. */
const REPO_BLOB_BASE = "https://github.com/ethancfay/research-gap-index/blob/main";

/** A single documentation link: the repo-relative path and its visible text. */
interface RepoLink {
  /** Path within the repository, used to build the full GitHub blob URL. */
  readonly path: string;
  /** Visible link text shown to the reader. */
  readonly label: string;
}

/** The dashboard spec files that describe what the site should do and how. */
const SPEC_LINKS: readonly RepoLink[] = [
  { path: ".kiro/specs/dashboard/requirements.md", label: "Dashboard requirements" },
  { path: ".kiro/specs/dashboard/design.md", label: "Dashboard design" },
  { path: ".kiro/specs/dashboard/tasks.md", label: "Dashboard tasks" },
];

/** The steering files that set the project's shared rules and conventions. */
const STEERING_LINKS: readonly RepoLink[] = [
  { path: ".kiro/steering/product.md", label: "Product steering" },
  { path: ".kiro/steering/tech.md", label: "Tech steering" },
  { path: ".kiro/steering/structure.md", label: "Structure steering" },
  { path: ".kiro/steering/health-safety.md", label: "Health and safety steering" },
];

/** The build log kept at the repository root. */
const LOG_LINK: RepoLink = { path: "KIRO_LOG.md", label: "KIRO_LOG.md" };

/** Build the full GitHub blob URL for a repo-relative path. */
function blobUrl(path: string): string {
  return `${REPO_BLOB_BASE}/${path}`;
}

/** Render one outbound GitHub link that opens in a new context. */
function BlobLink({ link }: { link: RepoLink }) {
  return (
    <a href={blobUrl(link.path)} target="_blank" rel="noopener noreferrer">
      {link.label}
    </a>
  );
}

/** Render a labeled list of GitHub links. */
function LinkList({ links }: { links: readonly RepoLink[] }) {
  return (
    <ul className="build-page__links">
      {links.map((link) => (
        <li key={link.path}>
          <BlobLink link={link} />
        </li>
      ))}
    </ul>
  );
}

/**
 * Build_Page route component. Default export named `Build` so the router
 * (task 14) imports it as `Build`.
 */
export default function Build() {
  return (
    <div className="build-page">
      <Card title="How we built it with Kiro" className="build-page__card">
      <p className="build-page__intro">
        We built this site with Kiro, an AI coding tool. We started by writing
        the requirements, the design, and a task list, then let Kiro work
        through the tasks to build the data pipeline and this dashboard. The
        files below show that plan and the steps we took along the way.
      </p>

      <section className="build-page__specs" aria-labelledby="build-specs-heading">
        <h2 id="build-specs-heading">Spec files</h2>
        <p>These files describe what the site should do and how it is built.</p>
        <LinkList links={SPEC_LINKS} />
      </section>

      <section className="build-page__steering" aria-labelledby="build-steering-heading">
        <h2 id="build-steering-heading">Steering files</h2>
        <p>These files set the shared rules Kiro followed across the project.</p>
        <LinkList links={STEERING_LINKS} />
      </section>

      <section className="build-page__log" aria-labelledby="build-log-heading">
        <h2 id="build-log-heading">Build log</h2>
        <p>This log notes how we used Kiro while building the project.</p>
        <ul className="build-page__links">
          <li>
            <BlobLink link={LOG_LINK} />
          </li>
        </ul>
      </section>
      </Card>
    </div>
  );
}
