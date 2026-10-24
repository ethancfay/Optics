"""Unit tests for pipeline/mapping/rules_loader.py (Req 2.4-2.9, 11.9)."""
import copy
import sys
import types

import pytest

from pipeline.errors import ConfigError, PipelineError
from pipeline.mapping import rules_loader
from pipeline.mapping.rules_loader import (
    Disease,
    RulesConfig,
    Term,
    load_rules,
    validate,
)


def _disease(measureid="DIABETES", **overrides):
    entry = {
        "measureid": measureid,
        "disease_label": "Diabetes",
        "ancestor_only_status": "questionable",
        "recall_query_term": "Diabetes",
        "include": ["Diabetes Mellitus", "diabetes"],
        "exclude": [("Diabetes, Gestational", "gestational")],
        "questionable": [("Diabetic Retinopathy", "complication_only")],
    }
    entry.update(overrides)
    return entry


def _errors(diseases, seed=1):
    with pytest.raises(ConfigError) as info:
        validate(diseases, seed)
    return info.value.lines


def test_config_error_is_pipeline_error_with_lines():
    err = ConfigError(["a", "b"])
    assert isinstance(err, PipelineError)
    assert err.lines == ["a", "b"]
    assert ConfigError("one").lines == ["one"]


def test_valid_config_builds_sorted_terms_and_diseases():
    cfg = validate([_disease("HIGHCHOL", include=["Hyperlipidemias"], exclude=[],
                             questionable=[]), _disease()], 7)
    assert isinstance(cfg, RulesConfig)
    assert cfg.seed == 7
    assert [d.measureid for d in cfg.diseases] == ["DIABETES", "HIGHCHOL"]
    diabetes = cfg.diseases[0]
    assert isinstance(diabetes, Disease)
    assert diabetes.terms[0] == Term("Diabetes Mellitus", "diabetes mellitus", "include", "")
    assert diabetes.terms[2] == Term("Diabetes, Gestational", "diabetes, gestational",
                                     "exclude", "gestational")
    assert diabetes.terms[3].kind == "questionable"


@pytest.mark.parametrize(
    "diseases, expected",
    [
        ([], "Rules_Config: must contain 1 to 5"),
        ([_disease(m) for m in ("CASTHMA", "HIGHCHOL", "DIABETES", "BPHIGH", "DEPRESSION")]
         + [_disease("CASTHMA")], "Rules_Config: must contain 1 to 5"),
        ("not a list", "Rules_Config: DISEASES must be a list"),
        ([_disease("COPD")], "Rules_Config: disease definition 1: measureid must be one of"),
        ([_disease(), _disease()], "DIABETES: measureid appears more than once"),
        ([_disease(disease_label="   ")], "DIABETES: disease_label"),
        ([_disease(disease_label="x" * 101)], "DIABETES: disease_label"),
        ([_disease(include=[])], "DIABETES: include must have at least one term"),
        ([_disease(include=["ok", " \t "])], "DIABETES: include term 2"),
        ([_disease(include=["x" * 201])], "DIABETES: include term 1"),
        ([_disease(exclude=[("", "gestational")])], "DIABETES: exclude term 1"),
        ([_disease(recall_query_term="")], "DIABETES: recall_query_term"),
        ([_disease(exclude=[("gdm", "Gestational")])], "DIABETES: exclude entry 1 reason code"),
        ([_disease(exclude=[("gdm", "1abc")])], "DIABETES: exclude entry 1 reason code"),
        ([_disease(exclude=[("gdm", "a" * 41)])], "DIABETES: exclude entry 1 reason code"),
        ([_disease(questionable=[("x", "")])], "DIABETES: questionable entry 1 reason code"),
        ([_disease(exclude=[("gdm", "child_only")])], "reserved reason code 'child_only'"),
        ([_disease(questionable=[("x", "ancestor_only")])], "reserved reason code 'ancestor_only'"),
        ([_disease(ancestor_only_status="excluded")], "DIABETES: ancestor_only_status"),
        ([_disease(include=["Asthma", "  ASTHMA "])], "DIABETES: duplicated term '  ASTHMA '"),
        ([_disease(exclude=[("diabetes", "gestational")])], "DIABETES: duplicated term 'diabetes'"),
        ([_disease(questionable=[("a", "x1"), ("A", "x2")])], "DIABETES: duplicated term 'A'"),
        ([_disease(exclude=[("gdm",)])], "DIABETES: exclude entry 1 must be a (term, reason)"),
        ([{k: v for k, v in _disease().items() if k != "include"}], "DIABETES: missing key 'include'"),
        ([_disease(extra=1)], "DIABETES: unknown key 'extra'"),
        ([["not", "a", "dict"]], "Rules_Config: disease definition 1 must be a dict"),
    ],
)
def test_each_failed_check_is_reported(diseases, expected):
    lines = _errors(diseases)
    assert any(expected in line for line in lines), lines


def test_several_failures_reported_together():
    lines = _errors(
        [_disease(include=[], ancestor_only_status="no"),
         _disease("HIGHCHOL", exclude=[("x", "child_only")])],
        seed=-1,
    )
    assert len(lines) == 4
    assert lines[0].startswith("Rules_Config: SAMPLE_SEED")
    assert any(line.startswith("DIABETES: include") for line in lines)
    assert any(line.startswith("DIABETES: ancestor_only_status") for line in lines)
    assert any(line.startswith("HIGHCHOL:") and "child_only" in line for line in lines)


@pytest.mark.parametrize("seed", [True, False, 1.0, "1", None, -1, 2**32])
def test_bad_seed_rejected(seed):
    lines = _errors([_disease()], seed=seed)
    assert lines == ["Rules_Config: SAMPLE_SEED must be an integer from 0 to 4294967295"]


@pytest.mark.parametrize("seed", [0, 2**32 - 1])
def test_seed_bounds_accepted(seed):
    assert validate([_disease()], seed).seed == seed


def test_validate_does_not_mutate_input():
    diseases = [_disease()]
    before = copy.deepcopy(diseases)
    validate(diseases, 1)
    assert diseases == before


def test_real_rules_py_loads():
    cfg = load_rules()
    assert [d.measureid for d in cfg.diseases] == ["CASTHMA", "DIABETES", "HIGHCHOL"]
    assert 0 <= cfg.seed <= 2**32 - 1
    statuses = {d.measureid: d.ancestor_only_status for d in cfg.diseases}
    assert statuses == {"CASTHMA": "included", "DIABETES": "questionable",
                        "HIGHCHOL": "questionable"}


def _fake_module(monkeypatch, name, **attrs):
    module = types.ModuleType(name)
    for key, value in attrs.items():
        setattr(module, key, value)
    monkeypatch.setitem(sys.modules, name, module)


def test_missing_module_reports_rules_py():
    with pytest.raises(ConfigError) as info:
        load_rules("pipeline.mapping.no_such_rules_module")
    assert info.value.lines == ["rules.py: file not found"]


def test_import_error_reports_rules_py(tmp_path, monkeypatch):
    (tmp_path / "broken_rules_mod.py").write_text("DISEASES = [\n", encoding="utf-8")
    monkeypatch.syspath_prepend(str(tmp_path))
    with pytest.raises(ConfigError) as info:
        load_rules("broken_rules_mod")
    assert info.value.lines == ["rules.py: cannot be imported (SyntaxError)"]


@pytest.mark.parametrize(
    "attrs, expected",
    [
        ({"SAMPLE_SEED": 1}, "rules.py: DISEASES is not defined"),
        ({"DISEASES": [_disease()]}, "rules.py: SAMPLE_SEED is not defined"),
        ({"DISEASES": (_disease(),), "SAMPLE_SEED": 1}, "rules.py: DISEASES must be a list"),
        ({"DISEASES": ["x"], "SAMPLE_SEED": 1}, "rules.py: every DISEASES entry must be a dict"),
        ({"DISEASES": [_disease()], "SAMPLE_SEED": "1"}, "rules.py: SAMPLE_SEED must be an int"),
        ({"DISEASES": [_disease()], "SAMPLE_SEED": True}, "rules.py: SAMPLE_SEED must be an int"),
    ],
)
def test_missing_or_ill_typed_names(monkeypatch, attrs, expected):
    _fake_module(monkeypatch, "fake_rules_mod", **attrs)
    with pytest.raises(ConfigError) as info:
        load_rules("fake_rules_mod")
    assert info.value.lines == [expected]


def test_load_rules_runs_validation(monkeypatch):
    _fake_module(monkeypatch, "fake_rules_mod", DISEASES=[_disease(include=[])], SAMPLE_SEED=2**32)
    with pytest.raises(ConfigError) as info:
        load_rules("fake_rules_mod")
    assert len(info.value.lines) == 2


def test_supported_and_reserved_constants():
    assert rules_loader.SUPPORTED_MEASURES == (
        "CASTHMA", "HIGHCHOL", "DIABETES", "BPHIGH", "DEPRESSION")
    assert rules_loader.RESERVED_REASONS == (
        "child_only", "unparseable_age", "healthy_volunteers_only", "ancestor_only")
