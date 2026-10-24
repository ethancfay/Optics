"""Property 10: study_diseases.csv round trip (condition-grouping design § Outputs).
Study_Disease_Rows whose cells may be empty or hold commas, double quotes,
CR, LF or non-ASCII text are encoded with `encode_study_diseases`, turned into
bytes by `csv_writer.serialize`, written to a file and read back with
`read_table`. Every row comes back with the same 7 cell strings, in the
written (sorted) order (Req 9.3, 9.4, 9.6).
"""
import os
import tempfile

from hypothesis import given, settings
from hypothesis import strategies as st

from pipeline.io.csv_reader import read_table
from pipeline.io.csv_writer import serialize
from pipeline.mapping.grouping_engine import StudyDiseaseRow
from pipeline.mapping.outputs import STUDY_DISEASES_HEADER, encode_study_diseases

# Fragments that stress CSV quoting and line handling, plus non-ASCII text.
_SPECIAL = st.sampled_from(
    ["", ",", '"', "\r", "\n", "\r\n", '""', '","', "é", "β-thalassémie", "中文", "😀", " "])
_PLAIN = st.text(min_size=0, max_size=8)  # any Unicode except surrogates
_cells = st.lists(st.one_of(_SPECIAL, _PLAIN), max_size=5).map("".join)

_rows = st.builds(StudyDiseaseRow, *([_cells] * len(STUDY_DISEASES_HEADER)))


# Feature: condition-grouping, Property 10: study_diseases.csv round trip
@settings(max_examples=200)
@given(st.lists(_rows, max_size=8))
def test_study_diseases_csv_round_trip(rows):
    """**Validates: Requirements 9.6, 9.4, 9.3**"""
    table = encode_study_diseases(rows)
    data = serialize(table)
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "study_diseases.csv")
        with open(path, "wb") as handle:
            handle.write(data)
        read_back = read_table(path, STUDY_DISEASES_HEADER, list_columns=frozenset())

    got = [[row[name] for name in STUDY_DISEASES_HEADER] for _, row in read_back]
    assert got == table.rows
    expected = sorted(
        [getattr(r, name) for name in STUDY_DISEASES_HEADER] for r in rows)
    assert got == expected
