"""Smoke test for the Term_Audit entry point (full example tests are task 1.5)."""
import json

from pipeline.mapping import term_audit


def _write_studies(root, rows):
    path = root / term_audit.STUDIES_RELPATH
    path.parent.mkdir(parents=True)
    lines = [",".join(term_audit.STUDIES_HEADER)]
    for i, (conditions, mesh) in enumerate(rows):
        cells = {c: "" for c in term_audit.STUDIES_HEADER}
        cells.update(nctId="NCT%08d" % i, conditions=json.dumps(conditions),
                     meshTerms=json.dumps(mesh), ancestorTerms="[]")
        lines.append(",".join('"%s"' % cells[c].replace('"', '""')
                              for c in term_audit.STUDIES_HEADER))
    path.write_bytes(("\n".join(lines) + "\n").encode("utf-8"))


def test_writes_audit_then_refuses_when_filled(tmp_path, capsys):
    _write_studies(tmp_path, [
        (["Asthma", "asthma", "Asthma"], ["LDL Cholesterol"]),
        (["Asthma"], ["VLDL", "a|b ldl"]),
    ])
    assert term_audit.main([], root=tmp_path) == 0
    out = (tmp_path / term_audit.AUDIT_RELPATH).read_text(encoding="utf-8")
    assert "| 1 | Asthma | 2 | CASTHMA |  |  |\n| 2 | asthma | 1 | CASTHMA |  |  |" in out
    assert "| a\\|b ldl | 1 | HIGHCHOL |" in out
    assert "## diabet / conditions (DIABETES)\n\nno values\n" in out
    assert term_audit.filled_cells(out) == 0

    path = tmp_path / term_audit.AUDIT_RELPATH
    filled = out.replace("| 1 | Asthma | 2 | CASTHMA |  |  |",
                         "| 1 | Asthma | 2 | CASTHMA | include |  |")
    path.write_text(filled, encoding="utf-8")
    before = path.read_bytes()
    assert term_audit.main([], root=tmp_path) == 1
    assert path.read_bytes() == before
    assert "1 filled" in capsys.readouterr().err


def test_missing_studies_names_file(tmp_path, capsys):
    assert term_audit.main([], root=tmp_path) == 1
    assert "studies.csv: file is missing" in capsys.readouterr().err
    assert not (tmp_path / term_audit.AUDIT_RELPATH).exists()
