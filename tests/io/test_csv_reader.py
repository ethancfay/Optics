"""CSV round-trip property P5 and CSV_Reader examples (Req 7.6, 7.7, 13.4)."""
import json
from dataclasses import asdict

import pytest
from hypothesis import given

from pipeline.errors import PipelineError
from pipeline.io.csv_reader import read_csv
from pipeline.io.csv_writer import COLUMNS, encode_rows, serialize
from tests.strategies import csv_rows


def _canon(row: dict) -> str:
    return json.dumps(row, sort_keys=True, ensure_ascii=False)


def _round_trip(tmp_path, kind, rows):
    path = tmp_path / ("%s.csv" % kind)
    path.write_bytes(serialize(encode_rows(kind, rows)))
    return read_csv(path, kind)


# --- Property P5 (Req 7.7, 13.4) -------------------------------------------------
# Values include "", [], [""], |, \, [, ], JSON-looking strings, commas, quotes,
# CR, LF, non-ASCII text (design § Correctness Properties P5).

@pytest.mark.parametrize("kind", ["studies", "sites", "places"])
def test_p5_csv_round_trip(tmp_path_factory, kind):
    """**Validates: Requirements 7.7, 13.4**"""

    @given(rows=csv_rows(kind))
    def prop(rows):
        tmp_path = tmp_path_factory.mktemp("p5")
        read = _round_trip(tmp_path, kind, rows)
        assert len(read) == len(rows)
        for row in read:
            assert tuple(row) == COLUMNS[kind]
        assert sorted(_canon(r) for r in read) == sorted(_canon(asdict(r)) for r in rows)

    prop()


# --- Examples ----------------------------------------------------------------------

def test_header_only_file_reads_as_no_rows(tmp_path):
    """Req 7.6, 7.9."""
    assert _round_trip(tmp_path, "sites", []) == []


def test_reader_rejects_wrong_header(tmp_path):
    path = tmp_path / "sites.csv"
    path.write_bytes(b"a,b\n1,2\n")
    with pytest.raises(PipelineError, match="sites.csv: header row"):
        read_csv(path, "sites")


def test_reader_rejects_bad_list_cell_without_content(tmp_path):
    """Req 7.6; the message names file, line and column but no cell text (Req 3.3)."""
    header = ",".join(COLUMNS["studies"])
    cells = ["NCT1"] + ["SECRET"] * (len(COLUMNS["studies"]) - 1)
    path = tmp_path / "studies.csv"
    path.write_bytes((header + "\n" + ",".join(cells) + "\n").encode())
    with pytest.raises(PipelineError) as err:
        read_csv(path, "studies")
    assert "line 2 column phases" in str(err.value)
    assert "SECRET" not in str(err.value)
