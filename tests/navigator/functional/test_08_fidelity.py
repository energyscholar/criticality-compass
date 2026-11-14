"""Test 8 (plan 1511 §3, §11.3): instantiation fidelity — the live path is byte-identical to the frozen at_sw oracle.
8a: E2 sequence over the socket == E2 from a direct in-process _step loop (same seeded init, same K_c, 5 steps).
8b: that direct loop's state == at_sw(L,K_c,L4,1,5,burn,default_rng(seed)) snapshot (np.array_equal)."""
import sys

import numpy as np

from conftest import GOLDEN_AT, PLUGIN_DIR, Wire, make_configs, real_server

sys.path.insert(0, str(PLUGIN_DIR / "vendor"))
import lattice_at  # noqa: E402
import observables_at  # noqa: E402

L = 3 * GOLDEN_AT["L_blocks"]
L4, BURN, SEED = GOLDEN_AT["L4"], GOLDEN_AT["burn"], GOLDEN_AT["seed"]


def direct(n_steps=5):
    """the frozen path by hand: its own rng stream, burn, then n_steps _step sweeps. -> (s, t, E2)"""
    rng1 = np.random.default_rng(SEED)
    K_c = float(lattice_at.self_dual_K(L4))
    S, T = lattice_at.at_sw(L, K_c, L4, 1, 0, BURN, rng1)
    s, t = S[0], T[0]
    for _ in range(n_steps):
        s, t = lattice_at._step(s, t, K_c, L4, rng1)
    E2 = float(observables_at.observables(s[None], t[None], 1)[0][0])
    return s, t, E2, K_c


def test_8a_socket_E2_equals_direct_step_loop(tmp_path):
    cfg = make_configs(tmp_path)
    s, t, E2_direct, K_c = direct(5)
    with real_server(cfg):
        w = Wire(cfg["port"])
        try:
            K = w.call({"op": "where"})["K_c"]
            assert K == K_c
            assert w.call({"op": "set", "K": K})["op"] == "ok"
            assert w.call({"op": "step", "n": 5}) == {"op": "ok", "index": 5}
            obs = w.call({"op": "sense"})
        finally:
            w.close()
    assert obs == {"op": "obs", "E2": E2_direct, "index": 5}


def test_8b_direct_loop_state_equals_at_sw_snapshot():
    s, t, _, K_c = direct(5)
    S, T = lattice_at.at_sw(L, K_c, L4, 1, 5, BURN, np.random.default_rng(SEED))
    assert np.array_equal(s, S[0]) and np.array_equal(t, T[0])


def test_8c_plugin_state_equals_at_sw_snapshot():
    """the plugin itself (no socket) after set(K_c), step(5): state identical to the at_sw oracle."""
    from environment import config as C
    from navigator import reader as R
    plugin = C.load_plugin("at")
    st = plugin.init(R.parse_at_cfg(dict(GOLDEN_AT)))
    K_c = plugin.edge(st)["K_c"]
    plugin.set(st, K_c)
    plugin.step(st, 5)
    S, T = lattice_at.at_sw(L, K_c, L4, 1, 5, BURN, np.random.default_rng(SEED))
    assert np.array_equal(st.s, S[0]) and np.array_equal(st.t, T[0]) and st.index == 5
