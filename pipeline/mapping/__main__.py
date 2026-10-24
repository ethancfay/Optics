# Entry point: python -m pipeline.mapping [--offline] [--resample]
#
# The version check below must stay first and must use only syntax that any
# Python 3 can parse, so that an old interpreter reaches it and exits cleanly
# before any pipeline import or file access (condition-grouping Req 1.5).
import sys
if sys.version_info < (3, 11):
    sys.stderr.write("Python %d.%d.%d detected; minimum is 3.11\n" % sys.version_info[:3])
    sys.exit(1)
import argparse
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Callable, TextIO
from pipeline.errors import ConfigError, PipelineError
from pipeline.io import csv_writer
from pipeline.io.atomic import write_files_atomically
from pipeline.mapping import outputs, precision_sampler, recall_checker
from pipeline.mapping.grouping_engine import group
from pipeline.mapping.inputs import InputPaths, read_inputs
from pipeline.mapping.rules_loader import load_rules

REPO_ROOT = Path(__file__).resolve().parents[2]
RULES_MODULE = "pipeline.mapping.rules"


@dataclass(frozen=True)
class Paths:
    """Input and output locations of a run, rooted at a repository directory (Req 12.2)."""
    root: Path
    rules_module: str = RULES_MODULE

    @property
    def processed(self) -> Path:
        return self.root / "pipeline" / "processed"

    @property
    def burden_test(self) -> Path:
        return self.root / "burden_test"

    @property
    def studies(self) -> Path:
        return self.processed / "studies.csv"

    @property
    def sites(self) -> Path:
        return self.processed / "sites.csv"

    @property
    def study_diseases(self) -> Path:
        return self.processed / "study_diseases.csv"

    @property
    def recall_check(self) -> Path:
        return self.processed / "recall_check.json"

    @property
    def precision_sample(self) -> Path:
        return self.burden_test / "precision_sample.csv"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m pipeline.mapping",
        description="Group studies into PLACES measures and write study_diseases.csv, "
                    "recall_check.json and burden_test/precision_sample.csv.",
        allow_abbrev=False,
    )
    parser.add_argument("--offline", action="store_true",
                        help="skip the recall check (no network); keep recall_check.json")
    parser.add_argument("--resample", action="store_true",
                        help="write a new precision_sample.csv even if correct cells are filled")
    return parser


def _utc_today() -> date:
    return datetime.now(timezone.utc).date()


def _as_utc_date(value: "date | datetime") -> date:
    """The clock may return a date (used as is) or a datetime (converted to UTC, Open Item 10)."""
    if isinstance(value, datetime):
        if value.tzinfo is not None:
            value = value.astimezone(timezone.utc)
        return value.date()
    return value


def _changed(path: Path, data: bytes) -> bool:
    """True unless `path` already holds exactly `data`."""
    try:
        return path.read_bytes() != data
    except FileNotFoundError:
        return True
    except OSError:
        return True  # let the atomic writer report the OS error for this file


def _run_stages(args: argparse.Namespace, paths: Paths, client: object,
                clock: "Callable[[], date | datetime]", stdout: TextIO, stderr: TextIO) -> None:
    rules = load_rules(paths.rules_module)                                     # Req 2
    studies, ma_ids = read_inputs(InputPaths(paths.studies, paths.sites), stderr)  # Req 1.1
    rows = group(studies, rules)                                               # Req 4-8

    recall_bytes: "bytes | None" = None
    if args.offline:                                                           # Req 10.8
        if not paths.recall_check.exists():
            print("notice: recall check skipped (--offline); no recall_check.json exists",
                  file=stderr)                                                 # Req 10.9
    else:
        if client is None:
            from pipeline.data.http_client import HttpClient
            client = HttpClient()
        result = recall_checker.check(rules, rows, studies, ma_ids, client,
                                      _as_utc_date(clock()))
        recall_bytes = recall_checker.serialize(result)

    decision, _ = precision_sampler.existing_state(paths.precision_sample, args.resample,
                                                   stderr)                     # Req 11.6-11.8
    sample_table = None
    if decision == "write":
        sample_table = precision_sampler.build(rules, rows, studies, ma_ids, stderr)

    # PII_Guard on the final content of every file to be written (Req 9.9, 9.10).
    study_table = outputs.encode_study_diseases(rows)
    outputs.pii_check("study_diseases.csv", study_table)
    files: "list[tuple[Path, bytes]]" = [(paths.study_diseases, csv_writer.serialize(study_table))]
    if recall_bytes is not None:
        outputs.pii_check("recall_check.json", recall_bytes)
        files.append((paths.recall_check, recall_bytes))
    if sample_table is not None:
        outputs.pii_check("precision_sample.csv", sample_table)
        files.append((paths.precision_sample, csv_writer.serialize(sample_table)))

    to_write = [(path, data) for path, data in files if _changed(path, data)]
    if to_write:
        write_files_atomically(to_write)                                       # Req 9.11, 9.12

    if recall_bytes is not None:
        recall_checker.emit_warnings(result, stderr)                           # Req 10.6
    stdout.write(outputs.summary(rules, rows))                                 # Req 12.6


def run(argv: "list[str] | None", paths: Paths, client: object = None,
        clock: "Callable[[], date | datetime] | None" = None,
        stdout: "TextIO | None" = None, stderr: "TextIO | None" = None) -> int:
    """Parse arguments, run every step, and return the exit code.

    - Usage errors: argparse writes usage to stderr and raises SystemExit(2)
      before any file is read (Req 12.4).
    - ConfigError: one `error:` line per failed check; PipelineError: its
      message; exit 1 (Req 2.7, 12.5).
    - Any other exception: only its type name, no traceback, exit 1 (Req 12.5).
    """
    out = sys.stdout if stdout is None else stdout
    err = sys.stderr if stderr is None else stderr
    args = build_parser().parse_args(argv)
    try:
        _run_stages(args, paths, client, clock or _utc_today, out, err)
    except ConfigError as exc:
        for line in exc.lines:
            err.write("error: %s\n" % line)
        return 1
    except PipelineError as exc:
        err.write("error: %s\n" % exc)
        return 1
    except Exception as exc:  # noqa: BLE001 - deliberate catch-all, see docstring
        err.write("error: unexpected %s\n" % type(exc).__name__)
        return 1
    return 0


def main() -> int:
    return run(sys.argv[1:], Paths(REPO_ROOT))


if __name__ == "__main__":
    sys.exit(main())
