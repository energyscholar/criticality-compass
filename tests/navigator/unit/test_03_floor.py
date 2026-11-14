"""Test 3 (plan 1511 §3, §11.9): the floor predicate is a pure function of (n, k, tau) — it reads nothing else — and the needle
evaluates it ONCE at the handshake, before `where`; the loop is never entered."""
import pytest

from conftest import fake_server, honest_declared, honest_responder, make_configs
from navigator import needle as N


@pytest.mark.parametrize("n,k,tau,refuses", [
    (450, 6, 67, False), (402, 6, 67, False), (401, 6, 67, True), (50, 6, 67, True), (1, 1, 1, False), (0.5, 1, 1, True)])
def test_floor_predicate_is_n_below_k_tau(n, k, tau, refuses):
    assert N.refuses_at_floor(n, k, tau) is refuses


def test_floor_reads_only_n_k_tau():
    import inspect
    assert list(inspect.signature(N.refuses_at_floor).parameters) == ["n", "k", "tau"]


def run(tmp_path, n, u=0.0, declared=None):
    with fake_server(honest_responder(declared=declared)) as fs:
        v = N.run(make_configs(tmp_path, port=fs.port, needle=dict(n=n, u=u))["needle"])
        return v, fs


def test_below_floor_is_REFUSE_floor_before_where(tmp_path):
    v, fs = run(tmp_path, n=50)
    assert isinstance(v, N.Verdict) and (v.kind, v.reason) == ("REFUSE", "floor")
    assert v.rounds == [] and v.edge is None and v.declaration.k == 6
    assert fs.ops == ["declare"]  # `where` never asked; the loop never entered


def test_at_or_above_floor_enters_the_loop(tmp_path):
    v, fs = run(tmp_path, n=402)
    assert (v.kind, v.reason) == ("LINE", None) and len(v.rounds) == 8
    assert fs.ops[:3] == ["declare", "where", "set"]


def test_floor_precedes_u_range(tmp_path):
    v, fs = run(tmp_path, n=50, u=0.2)  # fails both: the floor wins
    assert (v.kind, v.reason) == ("REFUSE", "floor") and fs.ops == ["declare"]


def test_floor_uses_the_declared_k_and_tau_not_the_files(tmp_path):
    v, _ = run(tmp_path / "a", n=450, declared=honest_declared(tau=100, k=6))  # floor 600 > 450
    assert (v.kind, v.reason) == ("REFUSE", "floor")
    v, _ = run(tmp_path / "b", n=450, declared=honest_declared(tau=10, k=6))   # floor 60 < 450
    assert v.kind == "LINE"
