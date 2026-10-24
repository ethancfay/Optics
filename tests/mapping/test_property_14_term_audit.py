"""Property 14: Term_Audit determinism (condition-grouping design § Term_Audit).

`render(audit_tables(rows))` is byte-identical across repeated runs and across
permutations of the data rows, and every table is ordered by (-count, value).
Pure functions only; no file is read or written.
"""
from hypothesis import given
from hypothesis import strategies as st

from pipeline.mapping import term_audit

# Values built around the Audit_Keywords, with case and whitespace variants,
# a `|`, keyword-free values and whitespace-only values (which must be skipped).
_STEMS = ("Asthma", "asthma", "ASTHMA ", "Cholesterol", "LDL Cholesterol", "VLDL",
          "Lipid Metabolism", "lipid", "Lipoprotein(a)", "Diabetes Mellitus, Type 2",
          "diabetic retinopathy", "Diabetes  Insipidus", "a|b asthma", "Hypertension",
          "Obesity", "  ", "")
_values = st.one_of(
    st.sampled_from(_STEMS),
    # Many distinct keyword values, so some tables exceed TOP_N = 40.
    st.builds(lambda stem, n: "%s %d" % (stem, n),
              st.sampled_from(("asthma", "diabet", "LDL")), st.integers(0, 60)),
)
_lists = st.lists(_values, max_size=8)
_rows = st.lists(
    st.fixed_dictionaries({c: _lists for c in term_audit.AUDIT_COLUMNS}),
    max_size=40,
)
_sha = st.text(alphabet="0123456789abcdef", min_size=64, max_size=64)


def _qualifying_counts(rows, keyword, column):
    """Every value the table may list, with its distinct-study count (Req 14.1, 14.2)."""
    counts = {}
    for row in rows:
        for value in set(row[column]):
            if " ".join(value.casefold().split()) and keyword.casefold() in value.casefold():
                counts[value] = counts.get(value, 0) + 1
    return counts


# Feature: condition-grouping, Property 14: Term_Audit determinism
@given(rows=_rows, sha=_sha, data=st.data())
def test_term_audit_determinism(rows, sha, data):
    """**Validates: Requirements 14.6, 14.3**"""
    tables = term_audit.audit_tables(rows)
    first = term_audit.render(sha, len(rows), tables)

    # Repeated run on the same input gives identical bytes.
    assert term_audit.render(sha, len(rows), term_audit.audit_tables(rows)) == first

    # Any permutation of the data rows (and of each list) gives identical bytes.
    permuted = [
        {c: data.draw(st.permutations(row[c])) for c in term_audit.AUDIT_COLUMNS}
        for row in data.draw(st.permutations(rows))
    ]
    assert term_audit.render(sha, len(permuted), term_audit.audit_tables(permuted)) == first

    # Each table is ordered by (-count, value) and holds the first TOP_N in that order.
    assert [(t.keyword, t.column) for t in tables] == [
        (k, c) for k, _ in term_audit.AUDIT_KEYWORDS for c in term_audit.AUDIT_COLUMNS]
    for table in tables:
        keys = [(-count, value) for value, count in table.entries]
        assert keys == sorted(keys)
        expected = sorted(((-n, v) for v, n in
                           _qualifying_counts(rows, table.keyword, table.column).items()))
        assert keys == expected[:term_audit.TOP_N]
