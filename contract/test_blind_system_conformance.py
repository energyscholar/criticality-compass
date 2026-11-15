"""Plan 1525 — TRACK-S acceptance (the BLIND System face). Launches the REAL blind server and drives it over a raw
socket (contract/SCHEMA-1525.md). FROZEN: the Generator makes this green; it does not edit this file.

What it pins:
  1. the blind face has exactly two ops (declare, measure); `where` and every Stage-1/2 op are `nev` — the truth is
     unreachable from the wire, not merely uncalled; the declaration carries no K_c and no w;
  2. `measure` is IDENTICAL to a direct computation from the vendored sampler, burned at K_start (never K_c),
     including the 20-block jackknife — so the moments are the declared physics, not a look-alike;
  3. `measure` is total and does not clamp: any invalid field ⇒ nev, index unchanged, nothing stepped;
  4. the truth exists only as <run_dir>/edge.json.

RED until `environment/blind_server.py` exists (the subprocess exits at once: no such module).
Run from the repo root:  python contract/test_blind_system_conformance.py   (or pytest)
"""
import json
import math
import socket
import subprocess
import sys
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
VENDOR = ROOT / "system-instantiated" / "plugins" / "at" / "vendor"
KNOBS = (0.20, 0.50)
L_BLOCKS, L4, BURN, SEED, NLEV = 3, 0.14, 5, 7, 2      # L = 9: structural, fast
K_START = 0.20                                         # the disordered knob end, far from K_c ≈ 0.349
N_EQ, S, SKIP = 3, 40, 1
KS = [0.30, 0.40]
DECLARED_KEYS = {"op", "knobs_K", "ordered_side", "L", "tau", "k", "index_unit", "index_kind", "observable", "nlev"}


def _free_port():
    s = socket.socket(); s.bind(("127.0.0.1", 0)); p = s.getsockname()[1]; s.close(); return p


def _write_cfgs(tmp, port):
    at_dir = tmp / "plugins_at"; at_dir.mkdir(parents=True, exist_ok=True)
    env_path, at_path = tmp / "environment.toml", at_dir / "at-blind.toml"
    env_path.write_text(f'system = "at"\nport = {port}\nrun_dir_root = "{tmp / "runs"}"\n')
    at_path.write_text(
        f"L_blocks = {L_BLOCKS}\nL4 = {L4}\nburn = {BURN}\nseed = {SEED}\nk = 1\nnlev = {NLEV}\n"
        f"knobs_K = [{KNOBS[0]}, {KNOBS[1]}]\nK_start = {K_START}\n"
        'index_unit = "sweep"\nindex_kind = "sample_counter"\n')
    (at_dir / "tau-v0.toml").write_text("value = 1.0\n")
    return env_path, at_path


def _launch(env_path, at_path, run_dir, port):
    proc = subprocess.Popen([sys.executable, "-m", "environment.blind_server", "--env", str(env_path), "--at", str(at_path),
                             "--run-dir", str(run_dir)], cwd=str(ROOT), stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    for _ in range(600):
        if proc.poll() is not None:
            out, err = proc.communicate()
            raise AssertionError(f"blind server exited early rc={proc.returncode}\nstderr={err}")
        try:
            socket.create_connection(("127.0.0.1", port), timeout=0.2).close(); return proc
        except OSError:
            time.sleep(0.05)
    proc.kill(); raise AssertionError("blind server never bound the port")


class _Conn:
    def __init__(self, port):
        self.s = socket.create_connection(("127.0.0.1", port), timeout=30)
        self.rf = self.s.makefile("r", encoding="utf-8", newline="\n")

    def ask(self, msg):
        self.s.sendall((json.dumps(msg) + "\n").encode())
        line = self.rf.readline(); assert line, "server closed unexpectedly"
        return json.loads(line)

    def close(self):
        try:
            self.s.close()
        except OSError:
            pass


def _server(tmp):
    port = _free_port(); env_path, at_path = _write_cfgs(tmp, port)
    run_dir = tmp / "run"
    return _launch(env_path, at_path, run_dir, port), _Conn(port), run_dir


def _stop(proc, conn):
    conn.close(); proc.terminate(); proc.wait(timeout=10)


def _expected_moments():
    """the declared computation (SCHEMA-1525), straight from the vendored sampler."""
    sys.path.insert(0, str(VENDOR))
    import lattice_at, observables_at  # noqa: E401,E402
    L, N, B = 3 * L_BLOCKS, (3 * L_BLOCKS) ** 2, 20
    rng = np.random.default_rng(SEED)
    Ss, Ts = lattice_at.at_sw(L, K_START, L4, 1, 0, BURN, rng)
    s, t = Ss[0], Ts[0]
    out = []
    for K in KS:
        for _ in range(N_EQ):
            s, t = lattice_at._step(s, t, K, L4, rng)
        E2, G = np.empty(S), np.empty((S, NLEV))
        for i in range(S):
            for _ in range(SKIP):
                s, t = lattice_at._step(s, t, K, L4, rng)
            e2, _, gs, _ = observables_at.observables(s[None, :, :], t[None, :, :], NLEV)
            E2[i], G[i] = e2[0], gs[0]
        blocks = np.array_split(np.arange(S), B)

        def jk(f):
            loo = np.array([f(np.setdiff1d(np.arange(S), b)) for b in blocks])
            return math.sqrt((B - 1) / B * float(((loo - loo.mean()) ** 2).sum()))
        C = float(E2.var() / N)
        C_err = jk(lambda idx: E2[idx].var() / N)
        Gs = [float(G[:, l].mean()) for l in range(NLEV)]
        Gs_err = [jk(lambda idx, l=l: G[idx, l].mean()) for l in range(NLEV)]
        out.append((C, C_err, Gs, Gs_err))
    return out


def _close(a, b):
    return abs(a - b) <= 1e-12 * max(1.0, abs(b))


def _float_list(v, n):
    assert isinstance(v, list) and len(v) == n, f"expected a {n}-list, got {v!r}"
    for x in v:
        assert isinstance(x, float) and not isinstance(x, bool), f"non-float element {x!r}"


def test_blind_face_has_two_ops(tmp_path):
    proc, c, _ = _server(tmp_path)
    try:
        d = c.ask({"op": "declare"})
        assert d["op"] == "declared", d
        assert set(d) == DECLARED_KEYS, f"declaration keys {sorted(d)} != {sorted(DECLARED_KEYS)} (no K_c, no w)"
        assert d["observable"] == "moments" and d["nlev"] == NLEV and d["L"] == 3 * L_BLOCKS, d
        for msg in ({"op": "where"}, {"op": "set", "K": 0.3}, {"op": "step", "n": 1}, {"op": "sense"},
                    {"op": "probe", "Ks": [0.3], "n": 1}, {"op": "edge"}, {"op": "nope"}):
            r = c.ask(msg)
            assert r == {"op": "nev", "index": 0}, f"{msg} must be nev at index 0 on the blind face, got {r}"
    finally:
        _stop(proc, c)


def test_measure_matches_the_declared_computation(tmp_path):
    proc, c, _ = _server(tmp_path)
    try:
        c.ask({"op": "declare"})
        r = c.ask({"op": "measure", "Ks": KS, "n_eq": N_EQ, "S": S, "skip": SKIP})
        assert r["op"] == "moments", r
        assert r["index"] == len(KS) * (N_EQ + S * SKIP), r
        m = len(KS)
        _float_list(r["C"], m); _float_list(r["C_err"], m)
        assert isinstance(r["Gs"], list) and len(r["Gs"]) == m and isinstance(r["Gs_err"], list) and len(r["Gs_err"]) == m
        for g, ge in zip(r["Gs"], r["Gs_err"]):
            _float_list(g, NLEV); _float_list(ge, NLEV)
        for i, (C, C_err, Gs, Gs_err) in enumerate(_expected_moments()):
            assert _close(r["C"][i], C), ("C", i, r["C"][i], C)
            assert _close(r["C_err"][i], C_err), ("C_err", i, r["C_err"][i], C_err)
            for l in range(NLEV):
                assert _close(r["Gs"][i][l], Gs[l]), ("Gs", i, l, r["Gs"][i][l], Gs[l])
                assert _close(r["Gs_err"][i][l], Gs_err[l]), ("Gs_err", i, l, r["Gs_err"][i][l], Gs_err[l])
    finally:
        _stop(proc, c)


def test_measure_is_total_no_clamp(tmp_path):
    proc, c, _ = _server(tmp_path)
    try:
        c.ask({"op": "declare"})
        good = {"op": "measure", "Ks": KS, "n_eq": N_EQ, "S": S, "skip": SKIP}
        bad = [dict(good, Ks=[0.30, 0.70]), dict(good, Ks=[0.10]), dict(good, Ks=[]), dict(good, Ks=[1]),
               dict(good, Ks=[True]), dict(good, Ks=0.3), dict(good, n_eq=0), dict(good, n_eq=True),
               dict(good, S=39), dict(good, S=40.0), dict(good, skip=0), dict(good, skip=False),
               {k: v for k, v in good.items() if k != "S"}]
        for msg in bad:
            r = c.ask(msg)
            assert r == {"op": "nev", "index": 0}, f"{msg} must be nev, index unchanged, nothing stepped; got {r}"
        r = c.ask(good)  # nothing was stepped by the rejected calls, so the first valid measure starts at index 0
        assert r["op"] == "moments" and r["index"] == len(KS) * (N_EQ + S * SKIP), r
        for i, (C, _, _, _) in enumerate(_expected_moments()):
            assert _close(r["C"][i], C), ("rejected calls must not touch the state", i, r["C"][i], C)
    finally:
        _stop(proc, c)


def test_truth_lives_only_in_edge_json(tmp_path):
    proc, c, run_dir = _server(tmp_path)
    try:
        edge = json.loads((run_dir / "edge.json").read_text())
        sys.path.insert(0, str(VENDOR)); import lattice_at  # noqa: E401,E402
        assert set(edge) == {"K_c"} and _close(edge["K_c"], float(lattice_at.self_dual_K(L4))), edge
    finally:
        _stop(proc, c)
    perf = json.loads((run_dir / "perf.json").read_text())
    assert isinstance(perf, list), perf


if __name__ == "__main__":
    import tempfile
    _tests = [test_blind_face_has_two_ops, test_measure_matches_the_declared_computation, test_measure_is_total_no_clamp,
              test_truth_lives_only_in_edge_json]
    _fail = 0
    for _t in _tests:
        with tempfile.TemporaryDirectory() as _d:
            try:
                _t(Path(_d)); print(f"PASS {_t.__name__}")
            except Exception as _e:  # noqa: BLE001
                _fail += 1; print(f"FAIL {_t.__name__}: {type(_e).__name__}: {_e}")
    print(f"{len(_tests) - _fail}/{len(_tests)} passed")
    sys.exit(1 if _fail else 0)
