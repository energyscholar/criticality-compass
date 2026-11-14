"""Test 2 (plan 1511 §3, §11.6): two total parses. Any Malformed is a value, never a filled default."""
import pytest

from conftest import GOLDEN_AT, GOLDEN_NEEDLE, GOLDEN_TAU, honest_declared
from navigator import reader as R

DECL_FIELDS = ["knobs_K", "ordered_side", "L", "tau", "k", "index_unit", "index_kind", "observable"]


def test_declared_honest_parses():
    d = R.parse_declared(honest_declared())
    assert isinstance(d, R.Declaration)
    assert (d.L, d.tau, d.k, d.knobs_K) == (27, 67, 6, (0.20, 0.50))


@pytest.mark.parametrize("field", DECL_FIELDS)
def test_declared_missing_field_is_malformed_naming_it(field):
    m = R.parse_declared(honest_declared(drop=[field]))
    assert isinstance(m, R.Malformed) and m.field == field


@pytest.mark.parametrize("bad", [
    dict(L=28), dict(L=0), dict(L="27"), dict(L=True), dict(tau=-1), dict(tau=0), dict(tau="67"),
    dict(k=0), dict(k=1.5), dict(knobs_K=[0.5, 0.2]), dict(knobs_K=[0.2]), dict(knobs_K="x"), dict(ordered_side=3),
    dict(index_unit=None), dict(observable=7)])
def test_declared_ill_typed_or_out_of_range_is_malformed(bad):
    m = R.parse_declared(honest_declared(**bad))
    assert isinstance(m, R.Malformed) and m.field == next(iter(bad))


def test_declared_does_not_carry_w():
    assert isinstance(R.parse_declared(honest_declared()), R.Declaration)
    assert not hasattr(R.parse_declared(honest_declared()), "w")


def test_declared_non_object_is_malformed():
    assert isinstance(R.parse_declared([1, 2]), R.Malformed)


def test_edge_honest_and_malformed():
    e = R.parse_edge({"op": "edge", "K_c": 0.34888, "w": 0.02, "index": 0})
    assert isinstance(e, R.Edge) and (e.K_c, e.w, e.index) == (0.34888, 0.02, 0)
    for bad in [dict(K_c="x"), dict(w=0), dict(w=-0.1), dict(index="0"), dict(K_c=None), dict(index=True)]:
        m = R.parse_edge({"op": "edge", "K_c": 0.34888, "w": 0.02, "index": 0, **bad})
        assert isinstance(m, R.Malformed) and m.field == next(iter(bad)), bad
    for f in ("K_c", "w", "index"):
        d = {"op": "edge", "K_c": 0.34888, "w": 0.02, "index": 0}
        del d[f]
        m = R.parse_edge(d)
        assert isinstance(m, R.Malformed) and m.field == f
    assert isinstance(R.parse_edge({"op": "nev", "index": 0}), R.Malformed)


def test_obs_is_a_total_parse_beside_parse_edge():
    o = R.parse_obs({"op": "obs", "E2": -100.0, "index": 3})
    assert isinstance(o, R.Obs) and o.E2 == -100.0 and o.index == 3
    for bad in [dict(E2="x"), dict(E2=None), dict(E2=3), dict(E2=True), dict(index="3")]:
        m = R.parse_obs({"op": "obs", "E2": -100.0, "index": 3, **bad})
        assert isinstance(m, R.Malformed) and m.field == next(iter(bad)), bad
    assert isinstance(R.parse_obs({"op": "nev", "index": 3}), R.Malformed)
    assert isinstance(R.parse_obs([1]), R.Malformed)
    assert R.parse_obs({"op": "obs", "index": 3}).field == "E2"


NEEDLE_BAD = [dict(u=-0.1), dict(du=0), dict(du=-0.01), dict(N=0), dict(n=0), dict(n=1.5), dict(port=0), dict(port="x"),
              dict(host=3), dict(needle_structure="other-v9"), dict(u="0")]


@pytest.mark.parametrize("bad", NEEDLE_BAD)
def test_needle_cfg_negative_or_ill_typed_is_malformed(bad):
    m = R.parse_needle_cfg({**GOLDEN_NEEDLE, **bad})
    assert isinstance(m, R.Malformed) and m.field == next(iter(bad))


@pytest.mark.parametrize("field", list(GOLDEN_NEEDLE))
def test_needle_cfg_missing_field_is_malformed_not_defaulted(field):
    d = dict(GOLDEN_NEEDLE)
    del d[field]
    m = R.parse_needle_cfg(d)
    assert isinstance(m, R.Malformed) and m.field == field


def test_needle_cfg_honest():
    c = R.parse_needle_cfg(dict(GOLDEN_NEEDLE))
    assert isinstance(c, R.NeedleConfig) and (c.u, c.du, c.N, c.n) == (0.0, 0.01, 8, 450)


AT_BAD = [dict(L_blocks=0), dict(L4=0), dict(L4=-0.1), dict(burn=0), dict(seed=1.5), dict(seed="22"), dict(k=0),
          dict(nlev=0), dict(knobs_K=[0.5, 0.2]), dict(w=0), dict(w=-0.02), dict(index_unit=5)]


@pytest.mark.parametrize("bad", AT_BAD)
def test_at_cfg_bad_is_malformed(bad):
    m = R.parse_at_cfg({**GOLDEN_AT, **bad})
    assert isinstance(m, R.Malformed) and m.field == next(iter(bad))


@pytest.mark.parametrize("field", list(GOLDEN_AT))
def test_at_cfg_missing_field_is_malformed_not_defaulted(field):
    d = dict(GOLDEN_AT)
    del d[field]
    m = R.parse_at_cfg(d)
    assert isinstance(m, R.Malformed) and m.field == field


def test_at_cfg_honest():
    c = R.parse_at_cfg(dict(GOLDEN_AT))
    assert isinstance(c, R.AtConfig) and c.L == 27 and c.seed == 22


def test_tau_cfg():
    assert isinstance(R.parse_tau_cfg(dict(GOLDEN_TAU)), R.TauConfig)
    for bad in (dict(value=0), dict(value=-1), dict(value="67")):
        m = R.parse_tau_cfg({**GOLDEN_TAU, **bad})
        assert isinstance(m, R.Malformed) and m.field == "value"
    d = dict(GOLDEN_TAU)
    del d["value"]
    assert isinstance(R.parse_tau_cfg(d), R.Malformed)
