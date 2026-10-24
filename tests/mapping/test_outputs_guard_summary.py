"""PII_Guard and summary unit tests (task 5.5).

Condition-grouping Req 9.9, 12.6, 12.8 (design § Outputs and PII_Guard).
Tables are built with the real encoders: `outputs.encode_study_diseases`,
`precision_sampler.build` and `recall_checker.serialize`.
"""
from __future__ import annotations

import io
from datetime import date
from fractions import Fraction

import pytest

from pipeline.errors import PipelineError
from pipeline.mapping import outputs
from pipeline.mapping import precision_sampler as ps
from pipeline.mapping import recall_checker as rc
from pipeline.mapping.grouping_engine import StudyDiseaseRow
from pipeline.mapping.inputs import Study
from pipeline.mapping.rules_loader import Disease, RulesConfig, Term, normalize

EMAIL = "jane.doe@example.org"
PHONE = "(617) 555-0142"
HITS = [pytest.param(EMAIL, id="email"), pytest.param(PHONE, id="phone")]


def _disease(mid):
    return Disease(mid, mid.title(), "included", mid.title(),
                   (Term(mid.title(), normalize(mid.title()), "include", ""),))


RULES = RulesConfig(diseases=(_disease("CASTHMA"), _disease("COPD"), _disease("DIABETES")),
                    seed=42)


def _row(nct, mid, status="included", reason="", term="asthma"):
    return StudyDiseaseRow(nct, mid, mid.title(), status, reason, "condition_text", term)


def _study(nct, title="Title", conditions_cell='["Asthma"]'):
    return Study(nct, title, "RECRUITING", "false", "", ("Asthma",), (), (),
                 conditions_cell, "https://clinicaltrials.gov/study/" + nct)


def _sample(study):
    rows = [_row(study.nct_id, "CASTHMA")]
    return ps.build(RULES, rows, {study.nct_id: study}, {study.nct_id}, stderr=io.StringIO())


def _recall(label="Asthma", term="asthma"):
    entry = rc.RecallEntry("CASTHMA", label, term, 1, 1, 2, Fraction(1, 2), Fraction(1, 2),
                           True, rc.request_url(term))
    return rc.serialize(rc.RecallResult(date(2024, 1, 2), (entry,)))


def _raises(file_name, value, expected, secret):
    with pytest.raises(PipelineError) as err:
        outputs.pii_check(file_name, value)
    assert str(err.value) == expected
    assert secret not in str(err.value)
    assert "555" not in str(err.value) and "@" not in str(err.value)


# Clean real outputs pass the guard.
def test_clean_outputs_pass():
    outputs.pii_check("study_diseases.csv",
                      outputs.encode_study_diseases([_row("NCT00000001", "CASTHMA")]))
    outputs.pii_check("precision_sample.csv", _sample(_study("NCT00000001")))
    outputs.pii_check("recall_check.json", _recall())


# Req 9.9: study_diseases.csv hit names file, column and nctId only.
@pytest.mark.parametrize("secret", HITS)
def test_study_diseases_hit(secret):
    table = outputs.encode_study_diseases([
        _row("NCT00000001", "CASTHMA"),
        _row("NCT00000002", "CASTHMA", term="call " + secret),
    ])
    _raises("study_diseases.csv", table,
            "study_diseases.csv: column matched_term: nctId NCT00000002", secret)


# Req 9.9: precision_sample.csv hit in a plain cell.
@pytest.mark.parametrize("secret", HITS)
def test_precision_sample_hit_in_title(secret):
    table = _sample(_study("NCT00000003", title="Contact " + secret))
    _raises("precision_sample.csv", table,
            "precision_sample.csv: column briefTitle: nctId NCT00000003", secret)


# Req 9.9: a JSON-escaped "@" inside the conditions array is still caught.
def test_precision_sample_escaped_email_in_conditions():
    cell = '["jane.doe\\u0040example.org"]'
    assert "@" not in cell
    table = _sample(_study("NCT00000004", conditions_cell=cell))
    _raises("precision_sample.csv", table,
            "precision_sample.csv: column conditions: nctId NCT00000004", "jane.doe")


# Req 9.9: precision_sample.csv hit in the conditions array (plain text).
@pytest.mark.parametrize("secret", HITS)
def test_precision_sample_hit_in_conditions(secret):
    cell = '["Asthma", "%s"]' % secret
    table = _sample(_study("NCT00000005", conditions_cell=cell))
    _raises("precision_sample.csv", table,
            "precision_sample.csv: column conditions: nctId NCT00000005", secret)


# Req 9.9: recall_check.json hit names file, key and measureid only (bytes, str, parsed).
@pytest.mark.parametrize("secret", HITS)
def test_recall_check_hit_in_label(secret):
    doc = _recall(label="Asthma " + secret)
    expected = "recall_check.json: key disease_label: measureid CASTHMA"
    _raises("recall_check.json", doc, expected, secret)
    _raises("recall_check.json", doc.decode("utf-8"), expected, secret)


def test_recall_check_hit_in_query_term():
    _raises("recall_check.json", _recall(term="asthma " + PHONE),
            "recall_check.json: key recall_query_term: measureid CASTHMA", PHONE)


# Req 12.6: one block per disease sorted by measureid, zeros shown, reasons sorted.
def test_summary_format_with_zero_row_disease():
    rows = [
        _row("NCT1", "DIABETES"),
        _row("NCT2", "CASTHMA", "excluded", "child_only"),
        _row("NCT3", "CASTHMA", "questionable", "ancestor_only"),
        _row("NCT4", "CASTHMA"),
        _row("NCT5", "CASTHMA"),
        _row("NCT6", "CASTHMA", "excluded", "child_only"),
    ]
    assert outputs.summary(RULES, rows) == (
        "CASTHMA: included 2, questionable 1, excluded 2\n"
        "  ancestor_only: 1\n"
        "  child_only: 2\n"
        "COPD: included 0, questionable 0, excluded 0\n"
        "DIABETES: included 1, questionable 0, excluded 0\n"
    )


def test_summary_with_no_rows():
    assert outputs.summary(RULES, []) == (
        "CASTHMA: included 0, questionable 0, excluded 0\n"
        "COPD: included 0, questionable 0, excluded 0\n"
        "DIABETES: included 0, questionable 0, excluded 0\n"
    )
