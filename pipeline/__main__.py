# Entry point: python -m pipeline [--offline]
#
# The version check below must stay first and must use only syntax that any
# Python 3 can parse, so that an old interpreter reaches it and exits cleanly
# before any pipeline import, network request, or file access (Req 14.2,
# design § Version check).
import sys
if sys.version_info < (3, 11):
    sys.stderr.write("Python %d.%d.%d detected; minimum is 3.11\n" % sys.version_info[:3])
    sys.exit(1)

import argparse
from dataclasses import dataclass
from pathlib import Path

from pipeline.data.ctgov_fetcher import is_allowed_state
from pipeline.errors import PipelineError

REPO_ROOT = Path(__file__).resolve().parent.parent


@dataclass(frozen=True)
class Paths:
    """Filesystem locations used by a run, rooted at a project directory."""

    root: Path

    @property
    def pipeline_dir(self) -> Path:
        return self.root / "pipeline"

    @property
    def raw(self) -> Path:
        return self.pipeline_dir / "raw"

    @property
    def processed(self) -> Path:
        return self.pipeline_dir / "processed"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m pipeline",
        description="Fetch ClinicalTrials.gov and CDC PLACES data and write pipeline/processed/.",
    )
    parser.add_argument(
        "--offline",
        action="store_true",
        help="rerun from the cached pages in pipeline/raw/ with no network requests",
    )
    return parser


def check_total_counts(pages_by_query: "dict[str, list[dict]]") -> None:
    """Req 1.10: each query's page 1 has an integer totalCount equal to its fetched records.

    `pages_by_query` maps "q1" and "q2" to that query's scrubbed pages, from a
    network fetch or the Raw_Store. Records are counted as received, so
    duplicates and records without an nctId count (design § Fetch checks).
    """
    for query, pages in pages_by_query.items():
        label = query.upper()
        total = pages[0].get("totalCount") if pages else None
        fetched = sum(len(page.get("studies", [])) for page in pages)
        if type(total) is not int:
            raise PipelineError(
                "%s: page 1 has no integer totalCount (fetched %d records)" % (label, fetched)
            )
        if fetched != total:
            raise PipelineError(
                "%s: fetched %d records but totalCount is %d; rerun the pipeline"
                % (label, fetched, total)
            )


def check_allowed_states(pages_by_query: "dict[str, list[dict]]") -> None:
    """Req 1.12: at least one record has a site whose state is in Allowed_States (Req 5.3)."""
    for pages in pages_by_query.values():
        for page in pages:
            for study in page.get("studies", []):
                for location in _locations(study):
                    if isinstance(location, dict) and is_allowed_state(location.get("state")):
                        return
    raise PipelineError(
        "no study has a site in Allowed_States (MA, RI, NH, CT, NY, VT); "
        "check parameter filter.geo"
    )


def _locations(study: object) -> list:
    node: object = study
    for key in ("protocolSection", "contactsLocationsModule", "locations"):
        if not isinstance(node, dict):
            return []
        node = node.get(key)
    return node if isinstance(node, list) else []


def _run_stages(args: argparse.Namespace, paths: Paths, client: object) -> None:
    """Run the pipeline stages. Wired up in task 11 (design § Data flow)."""
    raise PipelineError("pipeline stages are not implemented yet")


def run(argv: "list[str] | None", paths: Paths, client: object = None) -> int:
    """Parse arguments, run the pipeline, and return the process exit code.

    - PipelineError: message to stderr, exit code 1 (Req 14.8).
    - Any other exception: only the exception type name to stderr, exit
      code 1, no traceback, because a traceback could carry record content
      (design § Error model).
    - Argument errors: argparse prints usage and raises SystemExit(2).
    """
    args = build_parser().parse_args(argv)
    try:
        _run_stages(args, paths, client)
    except PipelineError as exc:
        sys.stderr.write("error: %s\n" % exc)
        return 1
    except Exception as exc:  # noqa: BLE001 - deliberate catch-all, see docstring
        sys.stderr.write("error: unexpected %s\n" % type(exc).__name__)
        return 1
    return 0


def main() -> int:
    return run(sys.argv[1:], Paths(REPO_ROOT), client=None)


if __name__ == "__main__":
    sys.exit(main())
