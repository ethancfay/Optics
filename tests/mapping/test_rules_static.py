"""Static checks on the committed `pipeline/mapping/rules.py` (Spec 2, task 1.8).

These tests read the committed `rules.py` and `term_audit.md` read-only. They
check the Rules_Config content against Requirement 2 and the Term_Audit
dispositions against Requirement 14 criteria 7 to 9.
"""

import ast
import re
from pathlib import Path

import pytest

from pipeline.mapping import rules
from pipeline.mapping.term_audit import _UNESCAPED_PIPE

REPO_ROOT = Path(__file__).resolve().parents[2]
RULES_PATH = REPO_ROOT / "pipeline" / "mapping" / "rules.py"
AUDIT_PATH = REPO_ROOT / ".kiro" / "specs" / "condition-grouping" / "term_audit.md"

DISPOSITIONS = {"include", "exclude", "questionable", "not_disease"}
REASON_CODE = re.compile(r"^[a-z][a-z0-9_]{0,39}$")
TABLE_HEADING = re.compile(r"^## (.+) / (meshTerms|ancestorTerms|conditions) \(([A-Z]+)\)$")


def normalize(text: str) -> str:
    """Normalized_Text: case folded, whitespace runs collapsed, ends trimmed."""
    return " ".join(text.casefold().split())


def by_measure() -> dict[str, dict]:
    return {d["measureid"]: d for d in rules.DISEASES}


def entries(disease: dict) -> dict[str, dict[str, str | None]]:
    """Map list name -> {Normalized_Text: reason} (reason None for include)."""
    return {
        "include": {normalize(t): None for t in disease["include"]},
        "exclude": {normalize(t): r for t, r in disease["exclude"]},
        "questionable": {normalize(t): r for t, r in disease["questionable"]},
    }


def audit_rows() -> list[dict]:
    """Parse every table row of the committed `term_audit.md`."""
    rows = []
    heading = None
    for line_no, line in enumerate(AUDIT_PATH.read_text(encoding="utf-8").splitlines(), 1):
        stripped = line.strip()
        match = TABLE_HEADING.match(stripped)
        if match:
            heading = match.groups()
            continue
        if not stripped.startswith("|") or stripped.startswith("|---") \
                or stripped.startswith("| rank "):
            continue
        cells = [c.strip() for c in _UNESCAPED_PIPE.split(stripped)]
        assert len(cells) == 8, "line %d: expected 6 cells" % line_no
        assert heading is not None, "line %d: table row before a heading" % line_no
        _, rank, value, count, measureid, disposition, note, _ = cells
        assert measureid == heading[2], "line %d: measureid differs from heading" % line_no
        rows.append({
            "line": line_no,
            "keyword": heading[0],
            "column": heading[1],
            "value": value.replace("\\|", "|"),
            "measureid": measureid,
            "disposition": disposition,
            "note": note,
        })
    return rows


# --- Req 2.11: no import statement -------------------------------------------

def test_rules_has_no_import_statement():
    tree = ast.parse(RULES_PATH.read_text(encoding="utf-8"), filename=str(RULES_PATH))
    imports = [n for n in ast.walk(tree) if isinstance(n, (ast.Import, ast.ImportFrom))]
    assert imports == []


# --- Req 2.2, 2.8, 2.12: labels, Ancestor_Only_Status, recall terms ----------

@pytest.mark.parametrize("measureid, label, ancestor_status, recall_term", [
    ("CASTHMA", "Asthma", "included", "Asthma"),
    ("HIGHCHOL", "High cholesterol", "questionable",
     "hypercholesterolemia OR hyperlipidemia OR dyslipidemia OR LDL"),
    ("DIABETES", "Diabetes", "questionable", "Diabetes"),
])
def test_disease_definition_fields(measureid, label, ancestor_status, recall_term):
    disease = by_measure()[measureid]
    assert disease["disease_label"] == label
    assert disease["ancestor_only_status"] == ancestor_status
    assert disease["recall_query_term"] == recall_term


def test_each_measureid_defined_once():
    ids = [d["measureid"] for d in rules.DISEASES]
    assert sorted(ids) == ["CASTHMA", "DIABETES", "HIGHCHOL"]


# --- Req 2.3: minimum terms ---------------------------------------------------

MIN_INCLUDE = {
    "CASTHMA": ["Asthma"],
    "DIABETES": ["Diabetes Mellitus", "Diabetes Mellitus, Type 1",
                 "Diabetes Mellitus, Type 2", "diabetes"],
    "HIGHCHOL": ["Hypercholesterolemia", "hyperlipidemia", "dyslipidemia",
                 "Hyperlipoproteinemia Type II", "familial hypercholesterolemia"],
}

MIN_EXCLUDE = {
    "DIABETES": [
        ("Diabetes, Gestational", "gestational"),
        ("gestational diabetes", "gestational"),
        ("Prediabetic State", "prediabetes"),
        ("prediabetes", "prediabetes"),
        ("Diabetes Insipidus", "not_mellitus"),
        ("Diabetes Insipidus, Neurogenic", "not_mellitus"),
    ],
    "HIGHCHOL": [
        ("Myocardial Infarction", "ascvd_only"),
        ("ASCVD", "ascvd_only"),
    ],
}


@pytest.mark.parametrize("measureid, term", [
    (m, t) for m, terms in MIN_INCLUDE.items() for t in terms
])
def test_minimum_include_terms(measureid, term):
    assert normalize(term) in entries(by_measure()[measureid])["include"]


@pytest.mark.parametrize("measureid, term, reason", [
    (m, t, r) for m, pairs in MIN_EXCLUDE.items() for t, r in pairs
])
def test_minimum_exclude_terms(measureid, term, reason):
    assert entries(by_measure()[measureid])["exclude"].get(normalize(term)) == reason


def test_highchol_includes_elevated_ldl_and_lpa():
    include = entries(by_measure()["HIGHCHOL"])["include"]
    assert any("ldl" in t for t in include)
    assert any("lp(a)" in t or "lipoprotein(a)" in t for t in include)


def test_casthma_has_no_child_only_exclude_term():
    # The child-only exclusion is enforced by the age rule (Req 5), not a term.
    assert all(r != "child_only" for _, r in by_measure()["CASTHMA"]["exclude"])


# --- Req 2.6: no duplicated Normalized_Text within a disease -----------------

@pytest.mark.parametrize("measureid", ["CASTHMA", "DIABETES", "HIGHCHOL"])
def test_no_duplicate_normalized_text_within_disease(measureid):
    disease = by_measure()[measureid]
    terms = list(disease["include"]) \
        + [t for t, _ in disease["exclude"]] + [t for t, _ in disease["questionable"]]
    normalized = [normalize(t) for t in terms]
    duplicates = sorted({t for t in normalized if normalized.count(t) > 1})
    assert duplicates == []


# --- Req 14.7: every disposition filled --------------------------------------

def test_audit_has_rows():
    assert len(audit_rows()) > 0


def test_every_audit_disposition_filled():
    problems = []
    for row in audit_rows():
        where = "line %d (%s)" % (row["line"], row["value"])
        if row["disposition"] not in DISPOSITIONS:
            problems.append("%s: disposition %r" % (where, row["disposition"]))
        elif row["disposition"] in ("exclude", "questionable"):
            if not REASON_CODE.match(row["note"]):
                problems.append("%s: reason code %r" % (where, row["note"]))
        elif row["disposition"] == "not_disease":
            if not 1 <= len(row["note"]) <= 200:
                problems.append("%s: note length %d" % (where, len(row["note"])))
    assert problems == []


def test_same_value_has_same_disposition_across_tables():
    seen: dict[tuple[str, str], tuple[str, str]] = {}
    problems = []
    for row in audit_rows():
        key = (row["measureid"], normalize(row["value"]))
        reason = row["note"] if row["disposition"] in ("exclude", "questionable") else ""
        outcome = (row["disposition"], reason)
        if seen.setdefault(key, outcome) != outcome:
            problems.append("line %d: %s" % (row["line"], row["value"]))
    assert problems == []


# --- Req 14.8, 14.9: rules.py agrees with the audit --------------------------

def test_every_audit_value_is_in_matching_list():
    diseases = by_measure()
    problems = []
    for row in audit_rows():
        disposition = row["disposition"]
        if disposition == "not_disease":
            continue
        lists = entries(diseases[row["measureid"]])
        value = normalize(row["value"])
        where = "line %d %s: %r" % (row["line"], row["measureid"], row["value"])
        if value not in lists[disposition]:
            problems.append("%s missing from %s" % (where, disposition))
        elif disposition != "include" and lists[disposition][value] != row["note"]:
            problems.append("%s reason %r, audit %r"
                            % (where, lists[disposition][value], row["note"]))
    assert problems == []


def test_no_not_disease_value_in_any_list():
    diseases = by_measure()
    problems = []
    for row in audit_rows():
        if row["disposition"] != "not_disease":
            continue
        lists = entries(diseases[row["measureid"]])
        value = normalize(row["value"])
        for name, terms in lists.items():
            if value in terms:
                problems.append("line %d %r in %s" % (row["line"], row["value"], name))
    assert problems == []
