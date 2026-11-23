"""Plan 1560 — the random Boolean network System on the FROZEN stage-3a blind wire (contract/SCHEMA-1560.md §5-§10).
Launches the REAL, UNCHANGED server `environment.blind_server2 --system rbn` and drives it over a raw socket.
FROZEN: the Generator makes this green; it does not edit this file.

What it pins:
  b01  the face has exactly the two stage-3a ops; the declaration's keys, exactly (the 3a ten, `roles`, `update`, and
       `fixed` naming the held p); no truth, no noise, no system name;
  b02  `measure` is IDENTICAL to a direct computation from the declared network and probe, including the 20-block
       jackknife; the reply's keys are the RBN names;
  b03  `measure` is total and does not clamp (the frozen wire's own validation);
  b04  the truth lives only in <run_dir>/edge.json: a LINE for a critical world, NO transition for a noise world;
  b05  nothing on the wire tells a noise world from a critical one, or carries the K section; `roles` is ONE crossing
       entry (the declared deviation from SCHEMA-1545: no peak); the observable name is one no needle and no System
       has used;
  b06  every start fault is a refusal: exit 2, one stderr line, no run artifact;
  b07  the frozen needle reads the declaration but finds no observable it knows (a REFUSE stream), while the frozen step
       table reads the reply under the declared `-K` side: a critical world brackets (`narrow`), an easy noise world
       leans low (`lean-lo`);
  b08  nothing frozen moved (the server, the navigator's needle and step files, the AT and Ising Systems; NOT the hold
       modules, which plan 1558 edits and the RBN does not use); the three shipped worlds (critical, easy decoy, hard
       decoy) and the declared tau; both decoys fail BY STRUCTURE: on the shipped network the exact expected healing is
       negative on the whole knob range, so no sampling budget finds an in-range crossing.

RED until `system-instantiated/plugins/rbn/` exists.
Run from the repo root:  python contract/test_rbn_blind_conformance.py   (or pytest). About 20 seconds on a quiet host.
"""
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
RBN = ROOT / "system-instantiated" / "plugins" / "rbn"
KNOBS = (1.0, 4.0)
N, P_TICKS, SEED, K_START = 27, 500, 7, 1.0
N_EQ, S, SKIP = 3, 40, 2
KS = [1.5, 3.0]
DECLARED_KEYS = {"op", "knobs_K", "ordered_side", "L", "tau", "k", "index_unit", "index_kind", "observable", "nlev",
                 "roles", "update", "fixed"}
ROLES = [{"name": "heal", "role": "crossing", "ordered_sign": "+"}]
ETA_PER_UNIT = 1000000
MOMENT_KEYS = {"op", "heal", "heal_err", "index"}
HARD_TICKS = 250                     # the shipped HARD decoy's noise, in ticks: no crossing in the knobs, exactly
SHIPPED = {"N": 2187, "p_ticks": 500, "seed": 260, "k": 6, "knobs_K": [1.0, 4.0], "K_start": 1.0,
           "index_unit": "probe", "index_kind": "sample_counter"}   # the three shipped worlds share these eight keys
OTHER_NAMES = {"C", "C_err", "Gs", "Gs_err", "D", "A", "B", "E2", "E4", "Gp", "g1", "U4", "U4_err", "chi", "chi_err"}
LINE = {"form": "2p(1-p)K=1", "approx": "annealed"}
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
    "environment/blind_server2.py": "31a6c9b686941b493670201b764ee0311e0e622df0e4c042a09bcf8848c2748c",
    "system-instantiated/plugins/at/blind.py": "f261eb6a12c5d7858b31f4dc036a83767af32ae81de143783effcbc6e1504885",
    "system-instantiated/plugins/at/plugin.py": "667ea692febe23bd393a9d00a8cfddb669b1660a5cdf4c25cb4065307a57bc00",
    "system-instantiated/plugins/at/at-blind.toml": "8675e15c291bfeb5288a1dd9a316869e9c8358591437eda60249bcb12956263d",
    "system-instantiated/plugins/at/tau-v0.toml": "d6ba2037f76ce275515a6a7e56b066413267c1611c7682fe5291012d04981729",
    "system-instantiated/plugins/ising/blind.py": "a15e651dff2ac1987cba7d6277b741803d7c32ad47129e8218eaa203e95c20eb",
    "system-instantiated/plugins/ising/plugin.py": "ee43557207ab6b62fd84627487952282c28b225f53b645fcefbb8732746fa5e5",
    "system-instantiated/plugins/ising/ising-blind.toml": "970df0b840f3a7447bb9ad113a6be94a06fdd6e010fc605fc6a22d091b595ba8",
    "system-instantiated/plugins/ising/ising-field-blind.toml": "b70e56818b2c384d66ea129ffb2e4be448b57945087e7333298eadc67ec703d0",
    "system-instantiated/plugins/ising/ising-field-hard-blind.toml": "cdced4f6f567bc7e5fbab6630339f8d31269f255b41d64515542d6fbbb155090",
    "system-instantiated/plugins/ising/tau-v0.toml": "d08682254bbd3d763fe5e8c295bca4bdd86135f2728643656ad3352289316068",
}


def _free_port():
    s = socket.socket(); s.bind(("127.0.0.1", 0)); p = s.getsockname()[1]; s.close(); return p


def _world_text(**over):
    """a critical world; `eta_ticks=n` alone makes it a noise world; a value of None drops the key."""
    w = {"kind": "critical", "N": N, "p_ticks": P_TICKS, "seed": SEED, "k": 1, "knobs_K": list(KNOBS), "K_start": K_START,
         "index_unit": "probe", "index_kind": "sample_counter"}
    if "eta_ticks" in over and "kind" not in over:
        w["kind"] = "noise"
    w.update(over)
    return "".join(f"{k} = {json.dumps(v)}\n" for k, v in w.items() if v is not None)


def _write_world(tmp, name="w", tau="value = 1\n", **over):
    d = tmp / name; d.mkdir(parents=True, exist_ok=True)
    (d / "rbn-blind.toml").write_text(_world_text(**over))
    if tau is not None:
        (d / "tau-v0.toml").write_text(tau)
    return d / "rbn-blind.toml"


def _cmd(world, run_dir, port, system="rbn"):
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
        for f in (self.rf.close, lambda: self.s.shutdown(socket.SHUT_RDWR), self.s.close):
            try:
                f()
            except OSError:
                pass


def _server(tmp, name="w", **over):
    port = _free_port(); world = _write_world(tmp, name, **over); run_dir = tmp / f"run-{name}"
    return _launch(world, run_dir, port), _Conn(port), run_dir, port


def _stop(proc, conn):
    conn.close(); proc.terminate()
    t0 = time.monotonic()
    try:
        proc.wait(timeout=10)
    except subprocess.TimeoutExpired:
        # plan 1640 amendment H': name the stall. The kill and the stderr read are cleanup for the diagnosis; the test still fails, and the 10 s is unchanged.
        waited = time.monotonic() - t0
        alive = proc.poll() is None
        proc.kill()
        try:
            err = proc.communicate(timeout=5)[1] or ""
        except subprocess.TimeoutExpired:
            err = "(stderr unreadable: the server did not close it within 5 s of the kill)"
        tail = "\n".join(err.splitlines()[-20:])
        raise AssertionError(f"the blind server did not exit within {waited:.2f} s of SIGTERM (still alive at that point: {alive}); the last 20 lines of its stderr:\n{tail}") from None


# ---- the declared computation (SCHEMA-1560 §2-§3, §7), written out a second time with loops: the test's own oracle ---------
def _ref_outputs(v, inputs, w, x, K, p):
    out = []
    for i in range(len(v)):
        k = int(math.floor(K + float(v[i])))
        r = sum(int(bool(x[inputs[i][m]])) << m for m in range(k))
        out.append(bool(w[i, r] < p))
    return out


def _expected_moments(eta=0.0, p=P_TICKS / 1000, Ks=KS, n_eq=N_EQ, S_=S, skip=SKIP, n=N, seed=SEED):
    B, KMAX = 20, int(math.ceil(KNOBS[1]))
    rng = np.random.default_rng(seed)
    v = rng.random(n)
    inputs = [[int(a) for a in rng.choice(n, KMAX, replace=False)] for _ in range(n)]
    w = rng.random((n, 2 ** KMAX))

    def probe(K):
        x = rng.random(n) < 0.5
        j = int(rng.integers(n))
        ua, ba = rng.random(n), rng.random(n) < 0.5
        ub, bb = rng.random(n), rng.random(n) < 0.5
        y = [bool(b) for b in x]
        y[j] = not y[j]
        fx, fy = _ref_outputs(v, inputs, w, x, K, p), _ref_outputs(v, inputs, w, y, K, p)
        return sum((bool(ba[i]) if ua[i] < eta else fx[i]) != (bool(bb[i]) if ub[i] < eta else fy[i]) for i in range(n))
    out = []
    for K in Ks:
        for _ in range(n_eq):
            probe(K)
        H = np.empty(S_)
        for i in range(S_):
            for _ in range(skip):
                H[i] = probe(K)                     # the last of the `skip` probes is kept
        blocks = np.array_split(np.arange(S_), B)

        def f(idx):
            return 1.0 - H[idx].mean()
        loo = np.array([f(np.setdiff1d(np.arange(S_), b)) for b in blocks])
        out.append((float(f(np.arange(S_))), math.sqrt((B - 1) / B * float(((loo - loo.mean()) ** 2).sum()))))
    return out


def _close(a, b):
    return abs(a - b) <= 1e-9 * max(1.0, abs(b))


def _check_moments(r, want):
    assert set(r) == MOMENT_KEYS, f"moments keys {sorted(r)} != {sorted(MOMENT_KEYS)}"
    m = len(want)
    assert isinstance(r["heal"], list) and len(r["heal"]) == m and isinstance(r["heal_err"], list) and len(r["heal_err"]) == m
    for i, (h, e) in enumerate(want):
        for key in ("heal", "heal_err"):
            row = r[key][i]
            assert isinstance(row, list) and len(row) == 2 and all(type(x) is float and math.isfinite(x) for x in row), (key, row)
            assert row[0] == 0.0, f"{key} level 0 is time 0: the damage there is exactly 1, so it is exactly 0.0"
        assert _close(r["heal"][i][1], h), ("heal", i, r["heal"][i][1], h)
        assert _close(r["heal_err"][i][1], e), ("heal_err", i, r["heal_err"][i][1], e)


GOOD = {"op": "measure", "Ks": KS, "n_eq": N_EQ, "S": S, "skip": SKIP}


def test_b01_the_face_has_the_two_frozen_ops(tmp_path):
    proc, c, _, _ = _server(tmp_path)
    try:
        d = c.ask({"op": "declare"})
        assert d["op"] == "declared", d
        assert set(d) == DECLARED_KEYS, f"declaration keys {sorted(d)} != {sorted(DECLARED_KEYS)}"
        assert d == {"op": "declared", "knobs_K": list(KNOBS), "ordered_side": "-K", "L": N, "tau": 1, "k": 1,
                     "index_unit": "probe", "index_kind": "sample_counter", "observable": "moments", "nlev": 2,
                     "roles": ROLES, "update": "uniform-probe", "fixed": {"p": 0.5}}, d
        for msg in ({"op": "where"}, {"op": "set", "K": 2.0}, {"op": "set", "p": 0.3}, {"op": "step", "n": 1},
                    {"op": "sense"}, {"op": "truth"}, {"op": "probe", "Ks": [2.0], "n": 1}, {"op": "edge"},
                    {"op": "read"}, {"op": "nudge", "ticks": 1}, {"op": "scan"}, {"op": "nope"}, {}, [], "x", 3, None):
            r = c.ask(msg)
            assert r == {"op": "nev", "index": 0}, f"{msg} must be nev at index 0 on the blind face, got {r}"
        assert c.ask("{not json") == {"op": "nev", "index": 0}
        assert c.ask({"op": "declare"}) == d, "declare is constant"
    finally:
        _stop(proc, c)


def test_b02_measure_is_the_declared_computation(tmp_path):
    for name, over, eta in (("zero", {}, 0.0), ("noise", {"eta_ticks": 30000}, 30000 / ETA_PER_UNIT),
                            ("bias", {"p_ticks": 300}, 0.0)):
        proc, c, _, _ = _server(tmp_path, name, **over)
        try:
            r = c.ask(GOOD)
            assert r["op"] == "moments" and r["index"] == len(KS) * (N_EQ + S * SKIP), r
            _check_moments(r, _expected_moments(eta, p=over.get("p_ticks", P_TICKS) / 1000))
            r2 = c.ask(GOOD)
            assert r2["op"] == "moments" and r2["index"] == 2 * len(KS) * (N_EQ + S * SKIP), "the index accumulates"
            assert r2["heal"] != r["heal"], "the probe stream moved on"
        finally:
            _stop(proc, c)


def test_b03_measure_is_total_no_clamp(tmp_path):
    proc, c, _, _ = _server(tmp_path)
    try:
        bad = [dict(GOOD, Ks=[1.5, 4.5]), dict(GOOD, Ks=[0.5]), dict(GOOD, Ks=[]), dict(GOOD, Ks=[2]),
               dict(GOOD, Ks=[True]), dict(GOOD, Ks=2.0), dict(GOOD, n_eq=0), dict(GOOD, n_eq=True),
               dict(GOOD, S=39), dict(GOOD, S=40.0), dict(GOOD, skip=0), dict(GOOD, skip=False),
               {k: v for k, v in GOOD.items() if k != "S"}]
        for msg in bad:
            r = c.ask(msg)
            assert r == {"op": "nev", "index": 0}, f"{msg} must be nev, index unchanged, nothing drawn; got {r}"
        r = c.ask(GOOD)
        assert r["op"] == "moments" and r["index"] == len(KS) * (N_EQ + S * SKIP), r
        _check_moments(r, _expected_moments())  # the rejected calls did not touch the state
    finally:
        _stop(proc, c)


def test_b04_the_truth_lives_only_in_edge_json(tmp_path):
    crit = {"transition": "line", "critical_set": LINE, "held": {"p": 0.5}, "section": {"dial": "K", "K_c": 2.0}}
    for name, over, want in (("zero", {}, crit),
                             ("bias", {"p_ticks": 300}, {"transition": "line", "critical_set": LINE, "held": {"p": 0.3},
                                                         "section": {"dial": "K", "K_c": 1.0 / (2.0 * 0.3 * (1.0 - 0.3))}}),
                             ("noise", {"eta_ticks": 1000}, {"transition": "none", "critical_set": None,
                                                             "held": {"p": 0.5, "eta": 0.001}, "section": None}),
                             ("hard", {"eta_ticks": HARD_TICKS}, {"transition": "none", "critical_set": None,
                                                                  "held": {"p": 0.5, "eta": HARD_TICKS / ETA_PER_UNIT},
                                                                  "section": None}),
                             ("tiny", {"eta_ticks": 1}, {"transition": "none", "critical_set": None,
                                                         "held": {"p": 0.5, "eta": 1e-06}, "section": None}),
                             ("far", {"knobs_K": [3.0, 4.0], "K_start": 3.0}, crit)):
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
        for x in v.values():
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
    for name, over in (("zero", {}), ("noise", {"eta_ticks": 1000}), ("hard", {"eta_ticks": HARD_TICKS})):
        proc, c, _, _ = _server(tmp_path, name, **over)
        try:
            d = c.ask({"op": "declare"})
            c.ask(GOOD); c.ask({"op": "where"}); c.ask(dict(GOOD, Ks=[2.0])); c.ask("garbage")
            seen[name] = (d, list(c.lines))
        finally:
            _stop(proc, c)
    assert seen["zero"][0] == seen["noise"][0] == seen["hard"][0], \
        "the declaration of a noise world differs from a critical one: the decoy is told"
    for name, (d, lines) in seen.items():
        for line in lines:
            low = line.lower()
            for word in ("k_c", "kc", "critical", "rbn", "boolean", "kauffman", "derrida", "transition", "noise", "eta",
                         "decoy", "truth", "edge", '"system"', '"kind"', "held", "section", "annealed", "2p(1-p)"):
                assert word not in low, f"{name}: the wire says `{word}`: {line[:200]}"
            for x in _floats(json.loads(line)):
                assert abs(x - 2.0) > 1e-9, f"{name}: the wire carries the K section 2.0: {line[:200]}"
    d = seen["zero"][0]
    assert d["roles"] == ROLES, d["roles"]
    assert [r["role"] for r in d["roles"]] == ["crossing"], "ONE crossing entry and no peak (the declared deviation)"
    assert set(d["roles"][0]) == {"name", "role", "ordered_sign"}
    assert d["ordered_side"] == "-K" and d["roles"][0]["ordered_sign"] == "+", \
        "the crossing is positive on the ordered side, which is the LOW-K side"
    assert d["fixed"] == {"p": 0.5} and set(d["fixed"]) == {"p"}, "the held dial is declared, by name, with its value"
    names = {r["name"] for r in d["roles"]}
    wire_names = names | {n + "_err" for n in names}
    assert wire_names == MOMENT_KEYS - {"op", "index"}, "every moments key is a declared observable or its _err"
    assert not wire_names & OTHER_NAMES, f"an AT or Ising observable name is reused: {wire_names & OTHER_NAMES}"
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
    for over, field in (({"kind": None}, "kind"), ({"N": None}, "N"), ({"seed": None}, "seed"), ({"k": None}, "k"),
                        ({"zz": 1}, "zz"), ({"K_c": 2.0}, "K_c"), ({"nlev": 2}, "nlev"), ({"p": 0.5}, "p"),
                        ({"N": 28}, "N"), ({"N": 27.0}, "N"), ({"N": 6}, "N"), ({"p_ticks": 0}, "p_ticks"),
                        ({"p_ticks": 1000}, "p_ticks"), ({"p_ticks": None}, "p_ticks"),
                        ({"kind": "decoy"}, "kind"), ({"kind": "noise"}, "eta_ticks"), ({"eta_ticks": 0}, "eta_ticks"),
                        ({"eta_ticks": -220}, "eta_ticks"), ({"eta_ticks": 0.0002}, "eta_ticks"),
                        ({"kind": "critical", "eta_ticks": 220}, "eta_ticks"), ({"eta": 0.0}, "eta"),
                        ({"eta_ticks": 220, "eta": 0.0002}, "eta"), ({"K_start": 4.5}, "K_start"),
                        ({"knobs_K": [4.0, 1.0]}, "knobs_K"), ({"knobs_K": [1.0, 9.0]}, "knobs_K"),
                        ({"index_unit": ""}, "index_unit")):
        n += 1
        w = _write_world(tmp_path, f"bad{n}", **over)
        _refused(_cmd(w, tmp_path / f"r{n}", _free_port()), tmp_path / f"r{n}", field)
    for tau, field in (("value = 0\n", "value"), ("stamp = \"x\"\n", "value"), ("value = [1]\n", "value"), (None, "tau-v0.toml"),
                       ("value = = 1\n", "tau-v0.toml")):
        n += 1
        w = _write_world(tmp_path, f"bad{n}", tau=tau)
        _refused(_cmd(w, tmp_path / f"r{n}", _free_port()), tmp_path / f"r{n}", field)
    bad_toml = tmp_path / "bt"; bad_toml.mkdir(); (bad_toml / "rbn-blind.toml").write_text("N = = 9\n")
    (bad_toml / "tau-v0.toml").write_text("value = 1\n")
    _refused(_cmd(bad_toml / "rbn-blind.toml", tmp_path / "rbt", _free_port()), tmp_path / "rbt", "rbn-blind.toml")
    _refused(_cmd(tmp_path / "missing" / "rbn-blind.toml", tmp_path / "rm", _free_port()), tmp_path / "rm", "rbn-blind.toml")
    for system in ("nope", "../rbn", "RBN", "", "rbn/../at"):
        _refused(_cmd(good, tmp_path / "rs", _free_port(), system=system), tmp_path / "rs", "system")
    for port in ("0", "65536", "abc", "-1", "8.5"):
        _refused(_cmd(good, tmp_path / "rp", port), tmp_path / "rp", "port")
    busy = socket.socket()
    try:
        busy.bind(("127.0.0.1", 0)); busy.listen(1)
        _refused(_cmd(good, tmp_path / "rb", busy.getsockname()[1]), tmp_path / "rb", "bind")
    finally:
        busy.close()


def test_b07_the_frozen_needle_knows_no_rbn_observable(tmp_path):
    sys.path.insert(0, str(ROOT))
    from navigator import reader, steer  # noqa: E402  (frozen)
    proc, c, _, port = _server(tmp_path, "crit", N=243)
    try:
        d = c.ask({"op": "declare"})
        decl = reader.parse_declared(d)
        assert isinstance(decl, reader.Declaration), f"the frozen reader refuses the RBN declaration: {decl}"
        assert decl.raw["roles"] == ROLES and decl.ordered_side == "-K" and decl.L == 243, "the reader keeps the roles as declared"
        c.close()                      # the server serves one connection at a time: free it for the needle
        # (i) the frozen needle, C and Gs built in: it reads the declaration, then finds no observable it knows
        cfg = tmp_path / "recover2.toml"
        cfg.write_text('needle_structure = "recover-adaptive-v1"\nbracket = [1.5, 3.0]\nm = 5\nN = 2\nn_eq = 3\nS = 40\n'
                       'skip = 1\nz = 2.0\n')
        p = subprocess.run([sys.executable, "-m", "navigator.recover2", "--needle", str(cfg), "--port", str(port)],
                           cwd=str(ROOT), capture_output=True, text=True, timeout=120)
        assert p.returncode == 0, p.stderr[-400:]
        recs = [json.loads(x) for x in p.stdout.splitlines()]
        assert [r["rec"] for r in recs] == ["start", "step", "outcome"], [r["rec"] for r in recs]
        assert recs[0]["belief"]["roles"] == {"declared": ROLES} and recs[0]["belief"]["system"] == "unknown", recs[0]["belief"]
        assert recs[1]["evaluated"] is False and recs[1]["scan"]["C"] is None, "the AT needle evaluated an RBN reply"
        assert recs[2]["kind"] == "REFUSE" and recs[2]["reason"] == "budget", recs[2]
        # (ii) the frozen step table under the DECLARED ordered side, the crossing name taken from the declared ROLES.
        # The difference is the frozen one, level 1 minus level 0; it must FALL through 0 as K rises ("-K").
        cross = [r["name"] for r in d["roles"] if r["role"] == "crossing"]
        assert len(cross) == 1
        c = _Conn(port)
        r = c.ask({"op": "measure", "Ks": list(KNOBS), "n_eq": 6, "S": 400, "skip": 1})
        assert r["op"] == "moments"
        D = [u[1] - u[0] for u in r[cross[0]]]
        classes = steer.end_classes(D, r[cross[0] + "_err"], 2.0)
        kind, _ = steer.scan_verdict(*classes, d["ordered_side"])
        assert classes == ("SIG+", "SIG-") and kind == steer.NARROW, \
            f"the levels are in the wrong order for the declared side: D = {D}, classes {classes}, verdict {kind}"
        assert classes[0] == {"+": "SIG+", "-": "SIG-"}[d["roles"][0]["ordered_sign"]], \
            f"the declared ordered_sign is not the sign of level 1 minus level 0 on the ordered (low-K) side: D = {D}"
    finally:
        _stop(proc, c)
    # (iii) an EASY noise world (eta N = 2.4 at N = 243): the damage never heals, the step table leans low, never narrow
    proc, c, _, _ = _server(tmp_path, "easy", N=243, eta_ticks=10000)
    try:
        r = c.ask({"op": "measure", "Ks": list(KNOBS), "n_eq": 6, "S": 400, "skip": 1})
        D = [u[1] - u[0] for u in r["heal"]]
        classes = steer.end_classes(D, r["heal_err"], 2.0)
        assert classes == ("SIG-", "SIG-") and steer.scan_verdict(*classes, "-K")[0] == steer.LEAN_LO, (D, classes)
    finally:
        _stop(proc, c)


def test_b08_nothing_frozen_moved_and_the_shipped_worlds():
    for rel, want in FROZEN.items():
        assert hashlib.sha256((ROOT / rel).read_bytes()).hexdigest() == want, f"{rel} was changed"
    w0 = tomllib.loads((RBN / "rbn-blind.toml").read_text())
    w1 = tomllib.loads((RBN / "rbn-noise-blind.toml").read_text())
    w2 = tomllib.loads((RBN / "rbn-noise-hard-blind.toml").read_text())
    tau = tomllib.loads((RBN / "tau-v0.toml").read_text())
    assert w0 == {"kind": "critical", **SHIPPED}, w0
    assert w1 == {"kind": "noise", "eta_ticks": 1000, **SHIPPED}, "the easy decoy is the critical world with noise, and nothing else"
    assert w2 == {"kind": "noise", "eta_ticks": HARD_TICKS, **SHIPPED}, \
        "the HARD decoy world is the critical world with the weak declared noise, and nothing else"
    assert tau["value"] == 1 and isinstance(tau.get("source"), str) and isinstance(tau.get("stamp"), str), tau
    assert 450 >= w0["k"] * tau["value"], "the stage-3a needle's n_eq = 450 must clear the floor k * tau"
    spec = importlib.util.spec_from_file_location("t1560_blind", RBN / "blind.py")
    blind = importlib.util.module_from_spec(spec); spec.loader.exec_module(blind)
    a, b, h = (blind.load_world(RBN / f) for f in ("rbn-blind.toml", "rbn-noise-blind.toml", "rbn-noise-hard-blind.toml"))
    assert all(isinstance(x, blind.World) for x in (a, b, h)) and a.tau == 1 and b.eta == 0.001 and h.eta_ticks == HARD_TICKS
    assert blind.declared(a) == blind.declared(b) == blind.declared(h)
    assert blind.truth(a) == {"transition": "line", "critical_set": LINE, "held": {"p": 0.5}, "section": {"dial": "K", "K_c": 2.0}}
    assert blind.truth(b)["transition"] == "none" and blind.truth(h) == \
        {"transition": "none", "critical_set": None, "held": {"p": 0.5, "eta": HARD_TICKS / ETA_PER_UNIT}, "section": None}, \
        "the hard decoy is NOT critical, however much it looks it at this size"
    # the decoys fail BY STRUCTURE: on the shipped network the EXPECTED healing is negative on the whole knob range
    # (exact lambda_net on every breakpoint, this file's own reading of SCHEMA section 2), so no sampling finds a crossing
    st = blind.plugin.init(a.N, a.knobs_K[0], a.p, 0.0, a.seed, a.knobs_K)
    v, w = np.asarray(st.net.v), np.asarray(st.net.w)
    km, lo, hi = w.shape[1].bit_length() - 1, a.knobs_K[0], a.knobs_K[1]
    s = np.zeros((a.N, km + 1))
    for k in range(1, km + 1):
        rows = np.arange(2 ** k)
        T = w[:, :2 ** k] < a.p
        s[:, k] = sum((T != T[:, rows ^ (1 << m)]).mean(axis=1) for m in range(k))
    k0 = np.floor(lo + v).astype(int)
    ev = sorted((j - v[i], i, j) for i in range(a.N) for j in range(k0[i] + 1, km + 1) if lo < j - v[i] <= hi)
    lam = [s[np.arange(a.N), k0].mean()]
    for _, i, j in ev:
        lam.append(lam[-1] + (s[i, j] - s[i, j - 1]) / a.N)
    lam_min = min(lam)
    for world, name in ((h, "hard"), (b, "easy")):
        e = world.eta
        top = 1.0 - (1.0 - e) ** 2 * lam_min - a.N * (e - e * e / 2.0)
        assert top < -0.02, f"the {name} decoy's expected healing reaches {top:+.4f} in the knobs: a real in-range crossing"
    assert 1.0 - lam[0] > 0.3 and 1.0 - lam[-1] < -0.5, "the critical world's section lies inside the knobs"


def _fail_report(name, e):
    """The runner's report of one failure: the one-line FAIL (first line of the message, cut to 300), then the rest of the message, each line indented 4 spaces and cut to 200, up to 30 lines (plan 1640 amendment H')."""
    lines = str(e).splitlines() or [""]
    return "\n".join([f"FAIL {name}: {type(e).__name__}: {lines[0][:300]}"] + ["    " + ln[:200] for ln in lines[1:31]])


def test_b09_stop_names_its_stall(tmp_path):
    """RED on 6b67f16: a server that ignores SIGTERM makes _stop raise TimeoutExpired, which names nothing. Now it raises AssertionError carrying the seconds, whether the process was alive, and the stderr tail."""
    code = ("import signal,sys,time\nsignal.signal(signal.SIGTERM, signal.SIG_IGN)\n"
            "print('ready', flush=True)\n" + "".join(f"print('stderr-line-{i}', file=sys.stderr, flush=True)\n" for i in range(25)) + "time.sleep(60)\n")
    proc = subprocess.Popen([sys.executable, "-c", code], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    assert proc.stdout.readline().strip() == "ready"   # (stdout, so that stderr stays unread) the handler is installed before the SIGTERM

    class _NoConn:
        def close(self):
            pass
    try:
        _stop(proc, _NoConn())
    except AssertionError as e:
        m = str(e)
        assert "did not exit within 1" in m and "still alive at that point: True" in m, m[:300]   # 10.0x s
        assert "stderr-line-24" in m and "stderr-line-5" in m and "stderr-line-4\n" not in m + "\n", "the last 20 lines of stderr, no more"
    else:
        raise AssertionError("a server that ignores SIGTERM must make _stop fail")
    finally:
        if proc.poll() is None:
            proc.kill(); proc.communicate()


def test_b10_a_failure_prints_its_whole_message():
    msg = "\n".join(["head"] + [f"leaf{i}" for i in range(11)])
    rep = _fail_report("test_x", AssertionError(msg)).splitlines()
    assert rep[0] == "FAIL test_x: AssertionError: head" and [r.strip() for r in rep[1:]] == [f"leaf{i}" for i in range(11)] and all(r.startswith("    ") for r in rep[1:]), rep
    assert "_fail_report(_t.__name__, _e)" in Path(__file__).read_text().split("if __name__")[-1], "the runner must use _fail_report"


if __name__ == "__main__":
    import tempfile
    _tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    _fail = 0
    for _t in _tests:
        with tempfile.TemporaryDirectory() as _d:
            try:
                (_t(Path(_d)) if _t.__code__.co_argcount else _t()); print(f"PASS {_t.__name__}")
            except Exception as _e:  # noqa: BLE001
                _fail += 1; print(_fail_report(_t.__name__, _e))
    print(f"{len(_tests) - _fail}/{len(_tests)} passed")
    sys.exit(1 if _fail else 0)
