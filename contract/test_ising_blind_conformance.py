"""Plan 1546 — the 2-D Ising System on the FROZEN stage-3a blind wire (contract/SCHEMA-1546.md §5-§9).
Launches the REAL server `environment.blind_server2` and drives it over a raw socket.
FROZEN: the Generator makes this green; it does not edit this file.

What it pins:
  b01  the face has exactly the two stage-3a ops; the declaration's keys, exactly; no truth, no field, no system name;
       `roles` has the shape frozen in SCHEMA-1545 (a list: one `crossing` entry with its `ordered_sign`, one `peak`);
  b02  `measure` is IDENTICAL to a direct computation from the declared update, burned at K_start (never at K_c),
       including the 20-block jackknife; the reply's keys are the Ising names;
  b03  `measure` is total and does not clamp (the frozen wire's own validation);
  b04  the truth lives only in <run_dir>/edge.json: a critical point for h = 0, NO transition for a field world;
  b05  nothing on the wire tells a field world from a critical one, or carries K_c; the observable names are ones the
       stage-3a/stage-2 needle never contained;
  b06  every start fault is a refusal (a busy port included): exit 2, one stderr line, no run artifact;
  b07  the frozen needle reads the declaration but finds no observable it knows (not evaluated, a REFUSE stream), while
       the frozen narrowing rule and step table read the reply correctly (a bracketing grid is `narrow` under the
       declared ordered side) when the two names are taken from the declared ROLES;
  b08  nothing frozen moved; the three shipped worlds (critical, easy decoy, hard decoy) and the declared tau.

RED until `environment/blind_server2.py` and `system-instantiated/plugins/ising/` exist.
Run from the repo root:  python contract/test_ising_blind_conformance.py   (or pytest). About 15 seconds on a quiet host.
"""
import ast
import hashlib
import importlib.util
import io
import json
import math
import re
import socket
import subprocess
import sys
import time
import tokenize
import tomllib
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
ISING = ROOT / "system-instantiated" / "plugins" / "ising"
KC = math.log(1.0 + math.sqrt(2.0)) / 2.0
KNOBS = (0.20, 0.60)
L, NLEV, BURN, SEED, K_START = 9, 2, 5, 7, 0.20
N_EQ, S, SKIP = 3, 40, 1
KS = [0.30, 0.45]
DECLARED_KEYS = {"op", "knobs_K", "ordered_side", "L", "tau", "k", "index_unit", "index_kind", "observable", "nlev",
                 "roles", "update"}
ROLES = [{"name": "U4", "role": "crossing", "ordered_sign": "+"}, {"name": "chi", "role": "peak"}]   # SCHEMA-1545's shape
H_PER_UNIT = 100000                      # the declared tick: h = h_ticks / 100000
MOMENT_KEYS = {"op", "chi", "chi_err", "U4", "U4_err", "index"}
HARD_TICKS = 90                      # the shipped HARD decoy's field, in ticks
SHIPPED = {"L": 81, "burn": 400, "seed": 190, "k": 6, "nlev": 2, "knobs_K": [0.42, 0.55], "K_start": 0.42,
           "index_unit": "sweep", "index_kind": "sample_counter"}   # the three shipped worlds share these nine keys
AT_NAMES = {"C", "C_err", "Gs", "Gs_err", "D", "A", "B", "E2", "E4", "Gp", "g1"}
FROZEN = {
    "navigator/__init__.py": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
    "navigator/estimate.py": "00df2977cf05d2f26fa8de82b7a6fff25ca2d58e9ef04b89cb8fe8d3269a6ea5",
    "navigator/needle.py": "02f8d60e00e76684bcf9483529e8bbe42224979e6a60bc13ac7e3b18816f2f3b",
    "navigator/reader.py": "0f655fbfcc0cb4be7f9bd7ed89c9e94222830968d148f57d1f59a1194cfd54f8",
    "navigator/recover.py": "fc96da0b0a0e2f50fd1dceed4164aef0c7db8bfae0ee10b5fd98e355b771a3d0",
    "navigator/recover2.py": "d150ad30e686f3eec2e27cd7288cabc246c40de9bdca1dd5bc2cf89d1b79fb0e",
    "navigator/report2.py": "2658a7f9dbae33de982ed066021c5f7f9cf1541635aa6740f4459693401e1a31",
    "navigator/steer.py": "229dbad1443291db8f49de5961f5e5fdf7324e64ca6c2720c3648f4b0676ccf5",
    "environment/blind_server.py": "b814ad13891571172bad4bae1198640f89eef6e30589308c9ab5f468837f324b",
    "environment/blind_wire.py": "d146e7b3566d0f9740822fc912fbd1b66d89bb52c3705574b21f4ac9733a0b16",
    "environment/blind_config.py": "f5eb9d19e2a0c25ec635247a95f6efecf6dca92faf49dbce7c195267e42927f5",
    "environment/config.py": "65d1227a5cc269193825bf6f841613b01131f8998a7961b44109c246bf9f445a",
    "system-instantiated/plugins/at/blind.py": "f261eb6a12c5d7858b31f4dc036a83767af32ae81de143783effcbc6e1504885",
    "system-instantiated/plugins/at/plugin.py": "667ea692febe23bd393a9d00a8cfddb669b1660a5cdf4c25cb4065307a57bc00",
    "system-instantiated/plugins/at/at-blind.toml": "8675e15c291bfeb5288a1dd9a316869e9c8358591437eda60249bcb12956263d",
    "system-instantiated/plugins/at/tau-v0.toml": "d6ba2037f76ce275515a6a7e56b066413267c1611c7682fe5291012d04981729",
}


def _free_port():
    s = socket.socket(); s.bind(("127.0.0.1", 0)); p = s.getsockname()[1]; s.close(); return p


def _world_text(**over):
    """a critical world; `h_ticks=n` alone makes it a field world; a value of None drops the key."""
    w = {"kind": "critical", "L": L, "burn": BURN, "seed": SEED, "k": 1, "nlev": NLEV, "knobs_K": list(KNOBS),
         "K_start": K_START, "index_unit": "sweep", "index_kind": "sample_counter"}
    if "h_ticks" in over and "kind" not in over:
        w["kind"] = "field"
    w.update(over)
    return "".join(f"{k} = {json.dumps(v)}\n" for k, v in w.items() if v is not None)


def _write_world(tmp, name="w", tau="value = 1.0\n", **over):
    d = tmp / name; d.mkdir(parents=True, exist_ok=True)
    (d / "ising-blind.toml").write_text(_world_text(**over))
    if tau is not None:
        (d / "tau-v0.toml").write_text(tau)
    return d / "ising-blind.toml"


def _cmd(world, run_dir, port, system="ising"):
    return [sys.executable, "-m", "environment.blind_server2", "--system", system, "--world", str(world),
            "--port", str(port), "--run-dir", str(run_dir)]


def _launch(world, run_dir, port):
    proc = subprocess.Popen(_cmd(world, run_dir, port), cwd=str(ROOT), stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
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
        self.s = socket.create_connection(("127.0.0.1", port), timeout=60)
        self.rf = self.s.makefile("r", encoding="utf-8", newline="\n")
        self.lines = []

    def ask(self, msg):
        self.s.sendall(((msg if isinstance(msg, str) else json.dumps(msg)) + "\n").encode())
        line = self.rf.readline(); assert line, "server closed unexpectedly"
        self.lines.append(line)
        return json.loads(line)

    def close(self):
        for f in (self.rf.close, lambda: self.s.shutdown(socket.SHUT_RDWR), self.s.close):   # the file object holds the fd too
            try:
                f()
            except OSError:
                pass


def _server(tmp, name="w", **over):
    port = _free_port(); world = _write_world(tmp, name, **over); run_dir = tmp / f"run-{name}"
    return _launch(world, run_dir, port), _Conn(port), run_dir, port


def _stop(proc, conn):
    conn.close(); proc.terminate(); proc.wait(timeout=10)


# ---- the declared computation (SCHEMA-1546 §3, §7), written out a second time: the test's own oracle -----------------------
def _find(parent, x):
    while parent[x] != x:
        parent[x] = parent[parent[x]]
        x = parent[x]
    return x


def ref_sweep(s, K, h, rng):
    n = s.shape[0]
    N = n * n
    f = [int(v) for v in s.ravel()]
    u_r, u_d, u_g = rng.random(N), rng.random(N), rng.random(N)
    p, pg = 1.0 - math.exp(-2.0 * K), 1.0 - math.exp(-2.0 * h)
    parent = list(range(N + 1))
    for i in range(n):
        for j in range(n):
            x, r, d = i * n + j, i * n + (j + 1) % n, ((i + 1) % n) * n + j
            if f[x] == f[r] and u_r[x] < p:
                parent[_find(parent, x)] = _find(parent, r)
            if f[x] == f[d] and u_d[x] < p:
                parent[_find(parent, x)] = _find(parent, d)
            if f[x] == 1 and u_g[x] < pg:
                parent[_find(parent, x)] = _find(parent, N)
    label, roots = {}, [_find(parent, x) for x in range(N + 1)]
    for x in range(N + 1):
        label.setdefault(roots[x], len(label))
    u_c = rng.random(len(label))
    ghost = label[roots[N]]
    out = [(-f[x] if (u_c[label[roots[x]]] < 0.5 and label[roots[x]] != ghost) else f[x]) for x in range(N)]
    return np.array(out).reshape(n, n)


def _expected_moments(h=0.0, K_start=K_START):
    N, B = L * L, 20
    rng = np.random.default_rng(SEED)
    s = rng.choice(np.array([-1, 1]), size=(L, L))
    for _ in range(BURN):
        s = ref_sweep(s, K_start, h, rng)
    out = []
    for K in KS:
        for _ in range(N_EQ):
            s = ref_sweep(s, K, h, rng)
        M, A, Q = np.empty(S), np.empty((S, NLEV)), np.empty((S, NLEV))
        for i in range(S):
            for _ in range(SKIP):
                s = ref_sweep(s, K, h, rng)
            M[i] = s.sum() / N
            for l in range(NLEV):
                g = 3 ** (NLEV - 1 - l); b = L // g      # finest first: the last level is the whole lattice
                mb = np.array([s[r * b:(r + 1) * b, c * b:(c + 1) * b].sum() / (b * b) for r in range(g) for c in range(g)])
                A[i, l], Q[i, l] = (mb ** 2).mean(), (mb ** 4).mean()
        blocks = np.array_split(np.arange(S), B)

        def jk(f):
            loo = np.array([f(np.setdiff1d(np.arange(S), b)) for b in blocks])
            return math.sqrt((B - 1) / B * float(((loo - loo.mean()) ** 2).sum()))

        def f_chi(idx):
            return N * ((M[idx] ** 2).mean() - np.abs(M[idx]).mean() ** 2)

        def f_u(idx, l):
            return 1.0 - Q[idx, l].mean() / (3.0 * A[idx, l].mean() ** 2)
        every = np.arange(S)
        out.append((float(f_chi(every)), jk(f_chi), [float(f_u(every, l)) for l in range(NLEV)],
                    [jk(lambda idx, l=l: f_u(idx, l)) for l in range(NLEV)]))
    return out


def _close(a, b):
    return abs(a - b) <= 1e-9 * max(1.0, abs(b))


def _float_list(v, n):
    assert isinstance(v, list) and len(v) == n, f"expected a {n}-list, got {v!r}"
    for x in v:
        assert isinstance(x, float) and not isinstance(x, bool) and math.isfinite(x), f"non-float element {x!r}"


def _check_moments(r, want):
    assert set(r) == MOMENT_KEYS, f"moments keys {sorted(r)} != {sorted(MOMENT_KEYS)}"
    m = len(KS)
    _float_list(r["chi"], m); _float_list(r["chi_err"], m)
    assert isinstance(r["U4"], list) and len(r["U4"]) == m and isinstance(r["U4_err"], list) and len(r["U4_err"]) == m
    for i, (chi, chi_err, U4, U4_err) in enumerate(want):
        _float_list(r["U4"][i], NLEV); _float_list(r["U4_err"][i], NLEV)
        assert _close(r["chi"][i], chi), ("chi", i, r["chi"][i], chi)
        assert _close(r["chi_err"][i], chi_err), ("chi_err", i, r["chi_err"][i], chi_err)
        for l in range(NLEV):
            assert _close(r["U4"][i][l], U4[l]), ("U4", i, l, r["U4"][i][l], U4[l])
            assert _close(r["U4_err"][i][l], U4_err[l]), ("U4_err", i, l, r["U4_err"][i][l], U4_err[l])


GOOD = {"op": "measure", "Ks": KS, "n_eq": N_EQ, "S": S, "skip": SKIP}


def test_b01_the_face_has_the_two_frozen_ops(tmp_path):
    proc, c, _, _ = _server(tmp_path)
    try:
        d = c.ask({"op": "declare"})
        assert d["op"] == "declared", d
        assert set(d) == DECLARED_KEYS, f"declaration keys {sorted(d)} != {sorted(DECLARED_KEYS)}"
        assert d == {"op": "declared", "knobs_K": list(KNOBS), "ordered_side": "+K", "L": L, "tau": 1.0, "k": 1,
                     "index_unit": "sweep", "index_kind": "sample_counter", "observable": "moments", "nlev": NLEV,
                     "roles": ROLES, "update": "swendsen-wang"}, d
        for msg in ({"op": "where"}, {"op": "set", "K": 0.3}, {"op": "step", "n": 1}, {"op": "sense"}, {"op": "truth"},
                    {"op": "probe", "Ks": [0.3], "n": 1}, {"op": "edge"}, {"op": "read"}, {"op": "nudge", "ticks": 1},
                    {"op": "scan"}, {"op": "nope"}, {}, [], "x", 3, None):
            r = c.ask(msg)
            assert r == {"op": "nev", "index": 0}, f"{msg} must be nev at index 0 on the blind face, got {r}"
        assert c.ask("{not json") == {"op": "nev", "index": 0}
        assert c.ask({"op": "declare"}) == d, "declare is constant"
    finally:
        _stop(proc, c)


def test_b02_measure_is_the_declared_computation(tmp_path):
    for name, over, h in (("zero", {}, 0.0), ("field", {"h_ticks": 30000}, 30000 / H_PER_UNIT)):
        proc, c, _, _ = _server(tmp_path, name, **over)
        try:
            r = c.ask(GOOD)
            assert r["op"] == "moments" and r["index"] == len(KS) * (N_EQ + S * SKIP), r
            _check_moments(r, _expected_moments(h))
            r2 = c.ask(GOOD)
            assert r2["op"] == "moments" and r2["index"] == 2 * len(KS) * (N_EQ + S * SKIP), "the index accumulates"
            assert r2["chi"] != r["chi"], "the held state moved on"
        finally:
            _stop(proc, c)


def test_b03_measure_is_total_no_clamp(tmp_path):
    proc, c, _, _ = _server(tmp_path)
    try:
        bad = [dict(GOOD, Ks=[0.30, 0.70]), dict(GOOD, Ks=[0.10]), dict(GOOD, Ks=[]), dict(GOOD, Ks=[1]),
               dict(GOOD, Ks=[True]), dict(GOOD, Ks=0.3), dict(GOOD, n_eq=0), dict(GOOD, n_eq=True),
               dict(GOOD, S=39), dict(GOOD, S=40.0), dict(GOOD, skip=0), dict(GOOD, skip=False),
               {k: v for k, v in GOOD.items() if k != "S"}]
        for msg in bad:
            r = c.ask(msg)
            assert r == {"op": "nev", "index": 0}, f"{msg} must be nev, index unchanged, nothing stepped; got {r}"
        r = c.ask(GOOD)
        assert r["op"] == "moments" and r["index"] == len(KS) * (N_EQ + S * SKIP), r
        _check_moments(r, _expected_moments())  # the rejected calls did not touch the state
    finally:
        _stop(proc, c)


def test_b04_the_truth_lives_only_in_edge_json(tmp_path):
    crit = {"transition": "continuous", "K_c": KC, "held": {"h": 0.0}}
    for name, over, want in (("zero", {}, crit),
                             ("field", {"h_ticks": 1000}, {"transition": "none", "K_c": None, "held": {"h": 0.01}}),
                             ("hard", {"h_ticks": HARD_TICKS}, {"transition": "none", "K_c": None, "held": {"h": HARD_TICKS / H_PER_UNIT}}),
                             ("tiny", {"h_ticks": 1}, {"transition": "none", "K_c": None, "held": {"h": 1e-05}}),
                             ("far", {"knobs_K": [0.5, 0.6], "K_start": 0.5}, crit)):
        proc, c, run_dir, _ = _server(tmp_path, name, **over)
        try:
            edge = json.loads((run_dir / "edge.json").read_text())
            assert edge == want, f"{name}: edge.json = {edge}, want {want}"
            assert sorted(p.name for p in run_dir.iterdir()) == ["edge.json"], sorted(p.name for p in run_dir.iterdir())
            c.ask({"op": "declare"}); c.ask({"op": "where"})
        finally:
            _stop(proc, c)
        perf = json.loads((run_dir / "perf.json").read_text())
        assert isinstance(perf, list) and [p["op"] for p in perf] == ["declare", "where"], perf
        assert all(isinstance(p["seconds"], float) for p in perf)
        out = (proc.stdout.read(), proc.stderr.read())
        assert out[0] == "" and [x.split(":")[0] for x in out[1].splitlines()] == ["malformed"], \
            f"{name}: a started server prints nothing of its own (only the frozen loop's one `malformed:` line): {out!r}"


def _floats(v):
    if isinstance(v, float):
        yield v
    elif isinstance(v, (list, tuple)):
        for x in v:
            yield from _floats(x)
    elif isinstance(v, dict):
        for k, x in v.items():
            yield from _floats(x)


def _needle_tokens():
    names = set()
    for f in sorted((ROOT / "navigator").glob("*.py")):
        for t in tokenize.generate_tokens(io.StringIO(f.read_text()).readline):
            if t.type in (tokenize.NAME, tokenize.STRING):
                names |= set(re.findall(r"[A-Za-z_][A-Za-z0-9_]*", t.string))
    return names


def test_b05_nothing_on_the_wire_tells_the_truth(tmp_path):
    seen = {}
    for name, over in (("zero", {}), ("field", {"h_ticks": 1000}), ("hard", {"h_ticks": HARD_TICKS})):
        proc, c, _, _ = _server(tmp_path, name, **over)
        try:
            d = c.ask({"op": "declare"})
            c.ask(GOOD); c.ask({"op": "where"}); c.ask(dict(GOOD, Ks=[KC])); c.ask("garbage")
            seen[name] = (d, list(c.lines))
        finally:
            _stop(proc, c)
    assert seen["zero"][0] == seen["field"][0] == seen["hard"][0], \
        "the declaration of a field world differs from a critical one: the decoy is told"
    for name, (d, lines) in seen.items():
        for line in lines:
            low = line.lower()
            for word in ("k_c", "kc", "critical", "ising", "transition", "onsager", "field", "decoy", "truth", "edge", '"h"',
                         '"system"', "h_ticks", '"kind"', "held"):
                assert word not in low, f"{name}: the wire says `{word}`: {line[:200]}"
            for x in _floats(json.loads(line)):
                assert abs(x - KC) > 1e-6, f"{name}: the wire carries K_c: {line[:200]}"
    d = seen["zero"][0]
    assert d["roles"] == ROLES, d["roles"]
    assert [r["role"] for r in d["roles"]] == ["crossing", "peak"], "exactly one crossing entry and one peak entry (SCHEMA-1545)"
    assert set(d["roles"][0]) == {"name", "role", "ordered_sign"} and set(d["roles"][1]) == {"name", "role"}
    assert d["roles"][0]["ordered_sign"] == d["ordered_side"][0] == "+", "the crossing's sign on the ordered side is the declared side's"
    names = {r["name"] for r in d["roles"]}
    wire_names = names | {n + "_err" for n in names}
    assert wire_names == MOMENT_KEYS - {"op", "index"}, "every moments key is a declared observable or its _err"
    assert not wire_names & AT_NAMES, f"an AT observable name is reused: {wire_names & AT_NAMES}"
    assert not wire_names & _needle_tokens(), f"the frozen needle already contains {wire_names & _needle_tokens()}"


def _refused(cmd, run_dir, field):
    p = subprocess.run(cmd, cwd=str(ROOT), capture_output=True, text=True, timeout=60)
    assert p.returncode == 2, f"expected exit 2 for field `{field}`, got {p.returncode}\nstderr={p.stderr[-400:]}"
    lines = [x for x in p.stderr.splitlines() if x.strip()]
    assert len(lines) == 1 and lines[0].startswith(f"RefusedToStart field={field} parse=B"), (field, p.stderr[-400:])
    assert p.stdout == "" and not run_dir.exists(), f"a refused start left a run artifact ({field})"


def test_b06_every_start_fault_is_a_refusal(tmp_path):
    good = _write_world(tmp_path, "good")
    n = 0
    for over, field in (({"kind": None}, "kind"), ({"L": None}, "L"), ({"seed": None}, "seed"), ({"k": None}, "k"),
                        ({"zz": 1}, "zz"), ({"K_c": 0.44}, "K_c"), ({"w": 0.1}, "w"), ({"L": 8}, "L"), ({"L": 9.0}, "L"),
                        ({"kind": "decoy"}, "kind"), ({"kind": "field"}, "h_ticks"), ({"h_ticks": 0}, "h_ticks"),
                        ({"h_ticks": -200}, "h_ticks"), ({"h_ticks": 0.002}, "h_ticks"),
                        ({"kind": "critical", "h_ticks": 200}, "h_ticks"), ({"h": 0.0}, "h"), ({"h": -0.0}, "h"),
                        ({"h_ticks": 200, "h": 0.002}, "h"), ({"nlev": 1}, "nlev"), ({"L": 15, "nlev": 3}, "L"),
                        ({"K_start": 0.7}, "K_start"), ({"knobs_K": [0.6, 0.2]}, "knobs_K"), ({"burn": -1}, "burn"),
                        ({"index_unit": ""}, "index_unit")):
        n += 1
        w = _write_world(tmp_path, f"bad{n}", **over)
        _refused(_cmd(w, tmp_path / f"r{n}", _free_port()), tmp_path / f"r{n}", field)
    for tau, field in (("value = 0\n", "value"), ("stamp = \"x\"\n", "value"), ("value = [1]\n", "value"), (None, "tau-v0.toml"),
                       ("value = = 1\n", "tau-v0.toml")):
        n += 1
        w = _write_world(tmp_path, f"bad{n}", tau=tau)
        _refused(_cmd(w, tmp_path / f"r{n}", _free_port()), tmp_path / f"r{n}", field)
    bad_toml = tmp_path / "bt"; bad_toml.mkdir(); (bad_toml / "ising-blind.toml").write_text("L = = 9\n")
    (bad_toml / "tau-v0.toml").write_text("value = 1.0\n")
    _refused(_cmd(bad_toml / "ising-blind.toml", tmp_path / "rbt", _free_port()), tmp_path / "rbt", "ising-blind.toml")
    _refused(_cmd(tmp_path / "missing" / "ising-blind.toml", tmp_path / "rm", _free_port()), tmp_path / "rm", "ising-blind.toml")
    for system in ("at", "nope", "../at", "Ising", "", "ising/../at"):
        _refused(_cmd(good, tmp_path / "rs", _free_port(), system=system), tmp_path / "rs", "system")
    for port in ("0", "65536", "abc", "-1", "8.5"):
        _refused(_cmd(good, tmp_path / "rp", port), tmp_path / "rp", "port")
    busy = socket.socket()
    try:
        busy.bind(("127.0.0.1", 0)); busy.listen(1)
        _refused(_cmd(good, tmp_path / "rb", busy.getsockname()[1]), tmp_path / "rb", "bind")
    finally:
        busy.close()


def test_b07_the_frozen_needle_knows_no_ising_observable(tmp_path):
    sys.path.insert(0, str(ROOT))
    from navigator import estimate, reader, steer  # noqa: E402  (frozen)
    proc, c, _, port = _server(tmp_path)
    try:
        d = c.ask({"op": "declare"})
        decl = reader.parse_declared(d)
        assert isinstance(decl, reader.Declaration), f"the frozen reader refuses the Ising declaration: {decl}"
        assert decl.raw["roles"] == ROLES and decl.ordered_side == "+K" and decl.L == L, "the frozen reader keeps the role list as declared"
        c.close()                      # the server serves one connection at a time: free it for the needle
        # (i) the frozen needle, C and Gs built in: it reads the declaration, then finds no observable it knows
        cfg = tmp_path / "recover2.toml"
        cfg.write_text('needle_structure = "recover-adaptive-v1"\nbracket = [0.30, 0.50]\nm = 5\nN = 2\nn_eq = 3\nS = 40\n'
                       'skip = 1\nz = 2.0\n')
        p = subprocess.run([sys.executable, "-m", "navigator.recover2", "--needle", str(cfg), "--port", str(port)],
                           cwd=str(ROOT), capture_output=True, text=True, timeout=120)
        assert p.returncode == 0, p.stderr[-400:]
        recs = [json.loads(x) for x in p.stdout.splitlines()]
        assert [r["rec"] for r in recs] == ["start", "step", "outcome"], [r["rec"] for r in recs]
        assert recs[0]["belief"]["roles"] == {"declared": ROLES} and recs[0]["belief"]["system"] == "unknown", recs[0]["belief"]
        assert recs[1]["evaluated"] is False and recs[1]["scan"]["C"] is None, "the AT needle evaluated an Ising reply"
        assert recs[2]["kind"] == "REFUSE" and recs[2]["reason"] == "budget", recs[2]
        # (ii) the same frozen narrowing rule, given the two names from the declared ROLES and nothing else
        peak = [r["name"] for r in d["roles"] if r["role"] == "peak"]
        cross = [r["name"] for r in d["roles"] if r["role"] == "crossing"]
        sign = [r["ordered_sign"] for r in d["roles"] if r["role"] == "crossing"]
        assert len(peak) == 1 and len(cross) == 1
        grid = [0.30, 0.35, 0.40, 0.45, 0.50]
        c = _Conn(port)
        r = c.ask({"op": "measure", "Ks": grid, "n_eq": 3, "S": 40, "skip": 1})
        assert r["op"] == "moments"
        nar = estimate.narrow(grid, r[peak[0]], r[peak[0] + "_err"], r[cross[0]], r[cross[0] + "_err"], 2.0)
        assert grid[0] <= nar.lo < nar.hi <= grid[-1] and len(nar.A) >= 1, nar
        # (iii) the frozen step table under the DECLARED ordered side: a grid that brackets the transition is `narrow`.
        # The difference is the frozen one, level 1 minus level 0; it must RISE through 0 as K rises ("+K").
        ends = [KNOBS[0], KNOBS[1]]
        r = c.ask({"op": "measure", "Ks": ends, "n_eq": 20, "S": 400, "skip": 1})
        assert r["op"] == "moments"
        D = [u[1] - u[0] for u in r[cross[0]]]
        classes = steer.end_classes(D, r[cross[0] + "_err"], 2.0)
        kind, why = steer.scan_verdict(*classes, d["ordered_side"])
        assert classes == ("SIG-", "SIG+") and kind == steer.NARROW, \
            f"the levels are in the wrong order for the declared side: D = {D}, classes {classes}, verdict {kind}"
        assert classes[1] == {"+": "SIG+", "-": "SIG-"}[sign[0]], \
            f"the crossing's declared ordered_sign {sign[0]!r} is not the sign of level 1 minus level 0 on the ordered side: D = {D}"
    finally:
        _stop(proc, c)


def test_b08_nothing_frozen_moved_and_the_shipped_worlds():
    for rel, want in FROZEN.items():
        assert hashlib.sha256((ROOT / rel).read_bytes()).hexdigest() == want, f"{rel} was changed"
    w0 = tomllib.loads((ISING / "ising-blind.toml").read_text())
    w1 = tomllib.loads((ISING / "ising-field-blind.toml").read_text())
    tau = tomllib.loads((ISING / "tau-v0.toml").read_text())
    assert w0 == {"kind": "critical", **SHIPPED}, w0
    assert w1 == {"kind": "field", "h_ticks": 1000, **SHIPPED}, "the decoy world is the critical world with a field, and nothing else"
    w2 = tomllib.loads((ISING / "ising-field-hard-blind.toml").read_text())
    assert w2 == {"kind": "field", "h_ticks": HARD_TICKS, **SHIPPED}, \
        "the HARD decoy world is the critical world with the weak declared field, and nothing else"
    assert tau["value"] == 11 and isinstance(tau.get("source"), str) and isinstance(tau.get("stamp"), str), tau
    assert 450 >= w0["k"] * tau["value"], "the stage-3a needle's n_eq = 450 must clear the floor k * tau"
    spec = importlib.util.spec_from_file_location("t1546_blind", ISING / "blind.py")
    blind = importlib.util.module_from_spec(spec); spec.loader.exec_module(blind)
    a, b = blind.load_world(ISING / "ising-blind.toml"), blind.load_world(ISING / "ising-field-blind.toml")
    assert isinstance(a, blind.World) and isinstance(b, blind.World) and a.tau == 11 and b.h == 0.01 and b.h_ticks == 1000
    assert blind.declared(a) == blind.declared(b)
    assert blind.truth(a) == {"transition": "continuous", "K_c": KC, "held": {"h": 0.0}}
    assert blind.truth(b) == {"transition": "none", "K_c": None, "held": {"h": 0.01}}
    hard = blind.load_world(ISING / "ising-field-hard-blind.toml")
    assert isinstance(hard, blind.World) and hard.h_ticks == HARD_TICKS and blind.declared(hard) == blind.declared(a)
    assert blind.truth(hard) == {"transition": "none", "K_c": None, "held": {"h": HARD_TICKS / H_PER_UNIT}}, \
        "the hard decoy is NOT critical, however much it looks it at these sizes"
    src = (ROOT / "environment" / "blind_server2.py").read_text()
    for word in ("ising", "K_c", "critical_K", "lattice", "navigator.estimate", "navigator.recover", "0.0.0.0"):
        assert word not in src, f"the server names `{word}`: it must know no System"
    tree = ast.parse(src)
    consts = {n.value for n in ast.walk(tree) if isinstance(n, ast.Constant) and isinstance(n.value, str)}
    assert "127.0.0.1" in consts, "the server binds the loopback address"
    ops = consts & {"measure", "nev", "declare", "moments"}
    assert not ops, f"the server holds an op name {ops}: the op table is the frozen one"
    imported = {a.name for n in ast.walk(tree) if isinstance(n, ast.ImportFrom) and n.module == "environment" for a in n.names}
    imported |= {a.name.rsplit(".", 1)[-1] for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names
                 if a.name.startswith("environment.")}
    imported |= {n.module.rsplit(".", 1)[-1] for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)
                 and (n.module or "").startswith("environment.")}
    assert "blind_server" in imported, "the server imports the frozen environment.blind_server"
    calls = {n.func.attr if isinstance(n.func, ast.Attribute) else getattr(n.func, "id", "")
             for n in ast.walk(tree) if isinstance(n, ast.Call)}
    defs = {n.name for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)}
    assert "serve_connection" in calls and not defs & {"serve_connection", "handle"}, \
        "the server serves each connection with the FROZEN serve_connection, not a copy of it"


if __name__ == "__main__":
    import tempfile
    _tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    _fail = 0
    for _t in _tests:
        with tempfile.TemporaryDirectory() as _d:
            try:
                (_t(Path(_d)) if _t.__code__.co_argcount else _t()); print(f"PASS {_t.__name__}")
            except Exception as _e:  # noqa: BLE001
                _fail += 1; print(f"FAIL {_t.__name__}: {type(_e).__name__}: {str(_e)[:300]}")
    print(f"{len(_tests) - _fail}/{len(_tests)} passed")
    sys.exit(1 if _fail else 0)
