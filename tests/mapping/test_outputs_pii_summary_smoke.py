"""Smoke test for `outputs.pii_check` and `outputs.summary` (Req 9.9, 12.6).
Full unit tests are task 5.5."""
from __future__ import annotations
from dataclasses import dataclass
import pytest
from pipeline.errors import PipelineError
from pipeline.io.csv_writer import EncodedTable
from pipeline.mapping import outputs
from pipeline.mapping.rules_loader import load_rules


@dataclass(frozen=True)
class Row:
    nctId: str
    measureid: str
    match_status: str
    exclusion_reason: str = ""


def test_pii_check_smoke():
    clean = EncodedTable("precision_sample", ("nctId", "conditions"), [["NCT1", '["Asthma"]']])
    outputs.pii_check("precision_sample.csv", clean)
    hidden = EncodedTable("precision_sample", ("nctId", "conditions"),
                          [["NCT2", '["a\\u0040b.com"]']])
    with pytest.raises(PipelineError) as err:
        outputs.pii_check("precision_sample.csv", hidden)
    assert str(err.value) == "precision_sample.csv: column conditions: nctId NCT2"
    doc = b'{"diseases": [{"measureid": "CASTHMA", "recall_query_term": "617-555-1234"}]}'
    with pytest.raises(PipelineError) as err:
        outputs.pii_check("recall_check.json", doc)
    assert str(err.value) == "recall_check.json: key recall_query_term: measureid CASTHMA"
    assert "555" not in str(err.value)


def test_summary_smoke():
    rows = [Row("NCT1", "CASTHMA", "included"),
            Row("NCT2", "CASTHMA", "excluded", "child_only"),
            Row("NCT3", "CASTHMA", "questionable", "ancestor_only")]
    text = outputs.summary(load_rules(), rows)
    assert text.startswith("CASTHMA: included 1, questionable 1, excluded 1\n"
                           "  ancestor_only: 1\n  child_only: 1\n")
    assert "DIABETES: included 0, questionable 0, excluded 0\n" in text
