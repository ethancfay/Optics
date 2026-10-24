"""Term_Audit example tests (condition-grouping Req 14.1, 14.2, 14.4, 14.5, 14.11-14.13).

Every test builds its own `studies.csv` under `tmp_path`; committed data is never read.
"""
import hashlib
import json
import os
import sys
from pathlib import Path

import pytest

from pipeline.mapping import term_audit

KEYWORDS = ("asthma", "cholesterol", "lipid", "LDL", "lipoprotein", "diabet")
MEASURES = {"asthma": "CASTHMA", "cholesterol": "HIGHCHOL", "lipid": "HIGHCHOL",
            "LDL": "HIGHCHOL", "lipoprotein": "HIGHCHOL", "diabet": "DIABETES"}
COLUMNS = ("meshTerms", "ancestorTerms", "conditions")


def _csv_line(cells):
    return ",".join('"%s"' % c.replace('"', '""') for c in cells)


def _studies_bytes(rows):
    """rows: list of dicts with optional `conditions`, `meshTerms`, `ancestorTerms` lists."""
    lines = [",".join(term_audit.STUDIES_HEADER)]
    for i, row in enumerate(rows):
        cells = {c: "" for c in term_audit.STUDIES_HEADER}
        for c in ("phases", "stdAges", "interventionTypes", "interventionNames",
                  "meshIds", "ancestorIds"):
            cells[c] = "[]"
        cells["nctId"] = "NCT%08d" % i
        for c in COLUMNS:
            cells[c] = row[c] if isinstance(row.get(c), str) else json.dumps(row.get(c, []))
        lines.append(_csv_line(cells[c] for c in term_audit.STUDIES_HEADER))
    return ("\n".join(lines) + "\n").encode("utf-8")


def _write(root, data):
    path = root / term_audit.STUDIES_RELPATH
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return path


def _run(root, rows):
    _write(root, _studies_bytes(rows))
    assert term_audit.main([], root=root) == 0
    return (root / term_audit.AUDIT_RELPATH).read_text(encoding="utf-8")


def _section(text, keyword, column):
    """The body of one `## keyword / column (measureid)` section."""
    head = "## %s / %s (%s)\n\n" % (keyword, column, MEASURES[keyword])
    start = text.index(head) + len(head)
    end = text.find("\n## ", start)
    return text[start:] if end == -1 else text[start:end + 1]


def _rows(section):
    """(rank, value, count, measureid, disposition, note) per table row."""
    out = []
    for line in section.splitlines()[2:]:
        if not line.startswith("| "):
            continue
        cells = [c.strip() for c in term_audit._UNESCAPED_PIPE.split(line)[1:-1]]
        out.append(tuple(cells))
    return out


# --- Listing and counting (Req 14.1, 14.2, 14.4) ---------------------------

def test_ldl_lists_ldl_cholesterol_and_vldl(tmp_path):
    text = _run(tmp_path, [
        {"meshTerms": ["LDL Cholesterol", "Cholesterol, LDL"]},
        {"meshTerms": ["VLDL"]},
        {"meshTerms": ["LDL Cholesterol", "Asthma"]},
    ])
    rows = _rows(_section(text, "LDL", "meshTerms"))
    assert [(r[1], r[2]) for r in rows] == [
        ("LDL Cholesterol", "2"), ("Cholesterol, LDL", "1"), ("VLDL", "1")]
    assert all(r[3] == "HIGHCHOL" for r in rows)
    assert "Asthma" not in [r[1] for r in rows]


def test_diabet_lists_diabetic_retinopathy(tmp_path):
    text = _run(tmp_path, [
        {"conditions": ["Diabetic Retinopathy", "Diabetes Mellitus, Type 2"]},
        {"conditions": ["Diabetes Mellitus, Type 2"]},
    ])
    rows = _rows(_section(text, "diabet", "conditions"))
    assert [(r[0], r[1], r[2], r[3]) for r in rows] == [
        ("1", "Diabetes Mellitus, Type 2", "2", "DIABETES"),
        ("2", "Diabetic Retinopathy", "1", "DIABETES")]


def test_duplicates_within_one_study_count_once(tmp_path):
    text = _run(tmp_path, [
        {"ancestorTerms": ["Asthma", "Asthma", "Asthma"]},
        {"ancestorTerms": ["Asthma"]},
    ])
    assert _rows(_section(text, "asthma", "ancestorTerms")) == [
        ("1", "Asthma", "2", "CASTHMA", "", "")]


def test_case_and_whitespace_variants_counted_separately(tmp_path):
    text = _run(tmp_path, [
        {"conditions": ["Asthma", "asthma", "ASTHMA", "asthma "]},
        {"conditions": ["asthma"]},
    ])
    rows = _rows(_section(text, "asthma", "conditions"))
    # ties broken by ascending code point: "ASTHMA" < "Asthma" < "asthma "
    assert [(r[1], r[2]) for r in rows] == [
        ("asthma", "2"), ("ASTHMA", "1"), ("Asthma", "1"), ("asthma", "1")]
    raw = _section(text, "asthma", "conditions")
    assert "| 4 | asthma  | 1 | CASTHMA |  |  |" in raw   # value written as-is


def test_more_than_40_values_truncated(tmp_path):
    rows = [{"meshTerms": ["asthma v%02d" % i]} for i in range(45)]
    rows.append({"meshTerms": ["asthma v44"]})   # v44 now has count 2 and ranks first
    text = _run(tmp_path, rows)
    listed = _rows(_section(text, "asthma", "meshTerms"))
    assert len(listed) == term_audit.TOP_N == 40
    assert [r[0] for r in listed] == [str(i) for i in range(1, 41)]
    assert listed[0][1:3] == ("asthma v44", "2")
    assert [r[1] for r in listed[1:]] == ["asthma v%02d" % i for i in range(39)]


def test_no_values_table(tmp_path):
    text = _run(tmp_path, [{"conditions": ["Asthma"]}])
    for keyword in KEYWORDS:
        for column in COLUMNS:
            if (keyword, column) == ("asthma", "conditions"):
                continue
            assert _section(text, keyword, column).strip() == "no values"


def test_pipe_in_value_is_escaped(tmp_path):
    text = _run(tmp_path, [{"conditions": ["asthma | COPD", "a|b|lipid"]}])
    assert "| 1 | asthma \\| COPD | 1 | CASTHMA |  |  |" in text
    assert "| 1 | a\\|b\\|lipid | 1 | HIGHCHOL |  |  |" in text
    assert term_audit.filled_cells(text) == 0


# --- Output format (Req 14.5) ----------------------------------------------

def test_header_and_exact_output_format(tmp_path):
    data = _studies_bytes([{"meshTerms": ["Asthma"]}, {"meshTerms": ["Asthma"]}])
    _write(tmp_path, data)
    assert term_audit.main([], root=tmp_path) == 0
    out = (tmp_path / term_audit.AUDIT_RELPATH).read_bytes()

    lines = ["# Term audit (condition-grouping, Requirement 14)", "",
             "- Source: pipeline/processed/studies.csv",
             "- SHA-256: %s" % hashlib.sha256(data).hexdigest(),
             "- Data rows: 2"]
    for keyword in KEYWORDS:
        for column in COLUMNS:
            lines += ["", "## %s / %s (%s)" % (keyword, column, MEASURES[keyword]), ""]
            if (keyword, column) == ("asthma", "meshTerms"):
                lines += ["| rank | value | count | measureid | disposition | reason_or_note |",
                          "|---|---|---|---|---|---|",
                          "| 1 | Asthma | 2 | CASTHMA |  |  |"]
            else:
                lines.append("no values")
    assert out == ("\n".join(lines) + "\n").encode("utf-8")
    assert not out.startswith(b"\xef\xbb\xbf") and b"\r" not in out


# --- Input errors (Req 14.12) ----------------------------------------------

EXISTING = b"# old audit\n\n| 1 | Asthma | 2 | CASTHMA |  |  |\n"


def _with_existing(root):
    path = root / term_audit.AUDIT_RELPATH
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(EXISTING)
    return path


def _bad_header():
    return _studies_bytes([{}]).replace(b"source_url", b"sourceUrl", 1)


def _bad_cell(column):
    def build():
        return _studies_bytes([{column: ["Asthma"]},
                               {column: '["SECRETVALUE", 7]'}])
    return build


@pytest.mark.parametrize("build, expected", [
    (None, "studies.csv: file is missing"),
    (lambda: b"nctId\n\xff\xfe\n", "studies.csv: file is not valid UTF-8"),
    (_bad_header, "studies.csv: header row does not match"),
    (_bad_cell("meshTerms"), "studies.csv: line 3 column meshTerms is not a JSON array"),
    (_bad_cell("ancestorTerms"), "studies.csv: line 3 column ancestorTerms is not a JSON array"),
    (_bad_cell("conditions"), "studies.csv: line 3 column conditions is not a JSON array"),
], ids=["missing", "non_utf8", "bad_header", "bad_mesh", "bad_ancestor", "bad_conditions"])
def test_input_error_leaves_existing_audit_unchanged(tmp_path, capsys, build, expected):
    audit = _with_existing(tmp_path)
    if build is not None:
        _write(tmp_path, build())
    assert term_audit.main([], root=tmp_path) != 0
    err = capsys.readouterr().err
    assert expected in err
    assert "SECRETVALUE" not in err
    assert audit.read_bytes() == EXISTING
    assert sorted(p.name for p in audit.parent.iterdir()) == ["term_audit.md"]


# --- Filled-file refusal and file access (Req 14.11, 14.13) ----------------

@pytest.mark.parametrize("filled_row, count", [
    ("| 1 | Asthma | 2 | CASTHMA | include |  |", 1),
    ("| 1 | Asthma | 2 | CASTHMA |  | a note |", 1),
    ("| 1 | a\\|b | 2 | CASTHMA | exclude | gestational |", 2),
])
def test_filled_file_refused_and_unchanged(tmp_path, capsys, filled_row, count):
    _write(tmp_path, _studies_bytes([{"conditions": ["Asthma"]}]))
    audit = tmp_path / term_audit.AUDIT_RELPATH
    audit.parent.mkdir(parents=True, exist_ok=True)
    audit.write_bytes(("# audit\n\n%s\n" % filled_row).encode("utf-8"))
    before = audit.read_bytes()
    assert term_audit.main([], root=tmp_path) == 1
    assert audit.read_bytes() == before
    err = capsys.readouterr().err
    assert "term_audit.md" in err and "%d filled" % count in err


_OPENED: "list[tuple[str, str]] | None" = None


def _audit_hook(event, args):
    if event == "open" and _OPENED is not None and isinstance(args[0], (str, bytes, os.PathLike)):
        _OPENED.append((os.fsdecode(args[0]), str(args[1])))


sys.addaudithook(_audit_hook)


def test_reads_only_studies_and_writes_only_audit(tmp_path):
    global _OPENED
    _write(tmp_path, _studies_bytes([{"conditions": ["Asthma"]}]))
    sites = tmp_path / "pipeline" / "processed" / "sites.csv"
    sites.write_bytes(b"untouched\n")
    before = {p: p.read_bytes() for p in tmp_path.rglob("*") if p.is_file()}

    _OPENED = []
    try:
        assert term_audit.main([], root=tmp_path) == 0
        opened = list(_OPENED)
    finally:
        _OPENED = None

    studies = (tmp_path / term_audit.STUDIES_RELPATH).resolve()
    audit = (tmp_path / term_audit.AUDIT_RELPATH).resolve()
    root = tmp_path.resolve()
    for name, mode in opened:
        path = Path(name).resolve()
        if root not in path.parents:
            continue
        if path == studies:
            assert "w" not in mode and "a" not in mode and "+" not in mode
        else:
            assert path == audit or (path.parent == audit.parent
                                     and path.name.startswith(".tmp-")), path
    assert studies in {Path(n).resolve() for n, _ in opened}

    after = {p: p.read_bytes() for p in tmp_path.rglob("*") if p.is_file()}
    assert set(after) - set(before) == {tmp_path / term_audit.AUDIT_RELPATH}
    assert all(after[p] == data for p, data in before.items())
