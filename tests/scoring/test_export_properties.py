"""Property-based test for schema conformance (design § Correctness Properties).

Property 5 (Schema conformance) — every file produced by
`pipeline.scoring.export.build_outputs` validates against its data-contract
shape: all required keys are present and typed; `sources.json.is_sample` is
`False`; every `investigate.json` entry's `us_studies` is `None`; every
uncomputable numeric value is `null` (`None`), never `0`; and no output string
anywhere in the four structures matches the Email_Pattern or Phone_Pattern.

The shared `scoring_inputs` strategy (task 1.3) draws studies, sites, PLACES
rows, and disease matches from a tiny shared nctId pool using only lowercase /
safe text, so the only way a PII pattern could appear in output is a real bug in
assembly. A minimal `fetch_log` dict is constructed per example so `sources.json`
is built the way the entry point builds it.

**Validates: Requirements 9.6**
"""
from __future__ import annotations

from numbers import Real

from hypothesis import given

from pipeline.patterns import PATTERNS
from pipeline.scoring.export import build_outputs
from tests.strategies import scoring_inputs

# The three active measures, in the order build_outputs iterates them. Each of
# the three array files carries exactly one entry per measure.
ACTIVE_MEASURES = ("CASTHMA", "HIGHCHOL", "DIABETES")


def _fetch_log() -> dict[str, object]:
    """A minimal, well-formed fetch_log.json like `load_fetch_log` returns."""
    return {
        "fetch_date": "2026-10-24T18:12:26Z",
        "run_started_at": "2026-10-24T18:00:00Z",
        "urls": {
            "clinicaltrials_gov": ["https://clinicaltrials.gov/api/v2/studies"],
            "cdc_places": ["https://data.cdc.gov/resource/swc5-untb.json"],
        },
    }


def _assert_opt(value: object, types: tuple[type, ...]) -> None:
    """A value is either `None` or an instance of one of `types` (never `0` sham)."""
    assert value is None or isinstance(value, types)


def _assert_opt_number(value: object) -> None:
    """A numeric field is `None` or a real number; a `bool` is not a number here."""
    assert value is None or (isinstance(value, Real) and not isinstance(value, bool))


# --- Required-key / type schemas for each file --------------------------------
def _check_what_entry(entry: dict) -> None:
    """what.json entry: required keys present and typed; uncomputable numerics None."""
    required = {
        "condition", "measure_id", "low", "mid", "high", "t", "affected_adults",
        "adults_18plus", "p_low", "p_high", "p", "prevalence_year", "ctgov_url",
    }
    assert required <= set(entry)

    assert isinstance(entry["condition"], str)
    assert isinstance(entry["measure_id"], str)
    assert isinstance(entry["ctgov_url"], str)

    # t is always a computed integer (distinct nctId count), never None.
    assert isinstance(entry["t"], int) and not isinstance(entry["t"], bool)
    assert entry["t"] >= 0

    # low/mid/high and the prevalence fractions are float-or-None (null, not 0).
    for key in ("low", "mid", "high", "p_low", "p_high", "p"):
        _assert_opt_number(entry[key])

    # affected_adults and adults_18plus (N) are int-or-None.
    _assert_opt(entry["affected_adults"], (int,))
    assert not isinstance(entry["affected_adults"], bool)
    _assert_opt(entry["adults_18plus"], (int,))
    assert not isinstance(entry["adults_18plus"], bool)

    # prevalence_year is a string-or-None (the PLACES year, or null if absent).
    _assert_opt(entry["prevalence_year"], (str,))


def _check_label_count_list(breakdown: object) -> None:
    """A breakdown is a list of {label:str, count:int} objects."""
    assert isinstance(breakdown, list)
    for item in breakdown:
        assert isinstance(item, dict)
        assert isinstance(item["label"], str)
        assert isinstance(item["count"], int) and not isinstance(item["count"], bool)


def _check_investigate_entry(entry: dict) -> None:
    """investigate.json entry: us_studies is None; counts int; breakdowns & findings typed."""
    required = {
        "measure_id", "condition", "ma_studies", "us_studies",
        "by_overall_status", "by_study_type", "by_intervention_type", "by_phase",
        "phase_overlap_studies", "findings",
    }
    assert required <= set(entry)

    assert isinstance(entry["measure_id"], str)
    assert isinstance(entry["condition"], str)

    # us_studies is always null (national comparison deferred).
    assert entry["us_studies"] is None

    for key in ("ma_studies", "phase_overlap_studies"):
        assert isinstance(entry[key], int) and not isinstance(entry[key], bool)
        assert entry[key] >= 0

    for key in ("by_overall_status", "by_study_type", "by_intervention_type", "by_phase"):
        _check_label_count_list(entry[key])

    assert isinstance(entry["findings"], list)
    for finding in entry["findings"]:
        assert isinstance(finding, dict)
        assert isinstance(finding["text"], str)
        assert isinstance(finding["label"], str)


def _check_evidence_entry(entry: dict) -> None:
    """evidence.json entry: ncts rows carry the contract keys with correct types."""
    required = {
        "measure_id", "condition", "ncts", "filters", "mapping_choices",
        "missing_data_notes",
    }
    assert required <= set(entry)

    assert isinstance(entry["measure_id"], str)
    assert isinstance(entry["condition"], str)
    for key in ("filters", "mapping_choices", "missing_data_notes"):
        assert isinstance(entry[key], list)
        assert all(isinstance(note, str) for note in entry[key])

    assert isinstance(entry["ncts"], list)
    for row in entry["ncts"]:
        assert isinstance(row, dict)
        nct_required = {
            "nct_id", "url", "title", "status", "study_type",
            "phases", "intervention_types", "intervention_names",
        }
        assert nct_required <= set(row)
        for key in ("nct_id", "url", "title", "status", "study_type"):
            assert isinstance(row[key], str)
        for key in ("phases", "intervention_types", "intervention_names"):
            assert isinstance(row[key], list)
            assert all(isinstance(v, str) for v in row[key])


def _check_sources(sources: dict) -> None:
    """sources.json: object with is_sample identity-False, data_as_of, prevalence_years."""
    assert isinstance(sources, dict)
    required = {"data_as_of", "is_sample", "sources", "prevalence_years"}
    assert required <= set(sources)

    # is_sample must be the boolean False by identity, never 0 or a truthy value.
    assert sources["is_sample"] is False

    _assert_opt(sources["data_as_of"], (str,))

    assert isinstance(sources["sources"], list)
    for src in sources["sources"]:
        assert isinstance(src, dict)
        assert isinstance(src["name"], str)
        assert isinstance(src["url"], str)
        _assert_opt(src["fetched"], (str,))

    assert isinstance(sources["prevalence_years"], dict)
    for measure_id, year in sources["prevalence_years"].items():
        assert isinstance(measure_id, str)
        _assert_opt(year, (str,))


# --- PII scan over every string in every structure ----------------------------
def _assert_no_pii(value: object) -> None:
    """No string anywhere in `value` matches the Email_Pattern or Phone_Pattern."""
    if isinstance(value, str):
        for name, regex in PATTERNS:
            assert regex.search(value) is None, f"output string matched {name}"
    elif isinstance(value, dict):
        for child in value.values():
            _assert_no_pii(child)
    elif isinstance(value, (list, tuple)):
        for element in value:
            _assert_no_pii(element)


@given(scoring_inputs())
def test_schema_conformance(inputs: dict) -> None:
    """Every build_outputs file validates against its data-contract shape (Property 5)."""
    files = build_outputs(
        inputs["studies"],
        inputs["sites"],
        inputs["places"],
        inputs["diseases"],
        _fetch_log(),
    )

    assert set(files) == {
        "what.json", "investigate.json", "evidence.json", "sources.json",
    }

    what = files["what.json"]
    investigate = files["investigate.json"]
    evidence = files["evidence.json"]
    sources = files["sources.json"]

    # Each array file is a list with exactly one entry per active measure.
    for array in (what, investigate, evidence):
        assert isinstance(array, list)
        assert len(array) == len(ACTIVE_MEASURES)
        assert {e["measure_id"] for e in array} == set(ACTIVE_MEASURES)

    for entry in what:
        _check_what_entry(entry)
    for entry in investigate:
        _check_investigate_entry(entry)
    for entry in evidence:
        _check_evidence_entry(entry)
    _check_sources(sources)

    # No output string matches the email or phone pattern (Req 7.1).
    _assert_no_pii(files)
