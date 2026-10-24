"""Smoke tests for the generators in `tests/mapping/strategies.py`."""
from hypothesis import given
from hypothesis import strategies as st

from pipeline.io.csv_writer import encode_list_cell
from pipeline.mapping.age_parser import NO_LIMIT, UNPARSEABLE, parse_max_age
from pipeline.mapping.rules_loader import SUPPORTED_MEASURES, RulesConfig, normalize, validate
from tests.mapping import strategies as S


@given(S.rules_dicts())
def test_rules_dicts_pass_validate(pair):
    diseases, seed = pair
    config = validate(diseases, seed)
    assert 1 <= len(config.diseases) <= 5
    assert [d.measureid for d in config.diseases] == sorted(d["measureid"] for d in diseases)


@given(S.rules_configs())
def test_rules_configs_are_valid(config):
    assert isinstance(config, RulesConfig)
    for disease in config.diseases:
        assert disease.measureid in SUPPORTED_MEASURES
        assert any(t.kind == "include" for t in disease.terms)
        assert len({t.norm for t in disease.terms}) == len(disease.terms)


@given(S.study_lists(max_size=6).flatmap(lambda ss: st.tuples(st.just(ss), S.ma_site_ids(ss))))
def test_studies_and_ma_sites(pair):
    study_list, ma = pair
    ids = [s.nct_id for s in study_list]
    assert len(ids) == len(set(ids))
    assert ma <= set(ids)
    for s in study_list:
        assert s.healthy_volunteers in ("true", "false", "")
        assert s.conditions_cell == encode_list_cell(list(s.conditions))


@given(S.studies_with_ma(), S.overall_statuses, S.max_ages)
def test_single_values(pair, status, age):
    assert isinstance(status, str)
    assert parse_max_age(age) is not None
    assert pair[1] <= {s.nct_id for s in pair[0]}


@given(st.sampled_from(S.VOCABULARY).flatmap(lambda t: st.tuples(st.just(t), S.perturb(t))))
def test_perturb_keeps_normalized_text(pair):
    original, perturbed = pair
    assert normalize(perturbed) == normalize(original)


def test_max_ages_cover_every_outcome():
    seen = set()

    @given(S.max_ages)
    def collect(age):
        result = parse_max_age(age)
        seen.add(result if result in (NO_LIMIT, UNPARSEABLE) else "age")

    collect()
    assert seen == {NO_LIMIT, UNPARSEABLE, "age"}
