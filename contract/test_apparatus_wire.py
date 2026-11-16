"""Plan 1545 — stage 5a-S acceptance: the emulated apparatus (contract/SCHEMA-1545.md). Launches the REAL apparatus
server and drives it over a raw socket. FROZEN: the Generator makes this green; it does not edit this file.

What it pins:
  a01  the face has exactly four ops (declare, read, nudge, scan); every older op and every malformed line is `nev`;
  a02  the declaration: exact key set, dials as integer-tick grids, roles, no truth and no drift;
  a03  a sequence of read / nudge / scan with LAG and hidden DRIFT equals, bit for bit, a direct computation from the
       vendored sampler (drift on every sweep, lag as a pure delay, the 20-block jackknife);
  a04  totality: a refused call changes nothing — no clamp, no partial move, no partial scan, no off-grid position;
  a05  the horizon is a door rule;
  a06  drift never reaches the needle: declare is byte-identical with and without drift, and no reply names the truth;
  a07  the truth lives only in the run directory (edge.json before the port binds; truth.json and perf.json on exit),
       one row per accepted call, each file carrying the algorithmic-time label;
  a08  a world with no dial (the OFF mode and the never-nudge null): read still reads;
  a09  the world file is strict: every malformed world is refused before the port binds;
  a10  with no drift and no lag the apparatus is bit-identical to the frozen blind face of plan 1525;
  a11  the step, sine and a steep linear law act on the lattice exactly at the declared index (no accumulation);
  a12  the frozen Stage-2 and blind files are byte-identical to plan 1545's base;
  a13  the two shipped production worlds hold the declared numbers of plan 1545, and differ only in the drift.

RED until `environment/apparatus_server.py` exists (the subprocess exits at once: no such module).
Run from the repo root:  python contract/test_apparatus_wire.py   (or pytest)
"""
import hashlib
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
TIME_LABEL = "lag and drift are in algorithmic (Swendsen-Wang) time"
WIRE = "compass-apparatus/1"
TAU = 3.0
DIAL = {"name": "K", "lo": 0.2, "hi": 0.5, "T": 1200, "max_nudge": 32, "start": 400}
WORLD = {          # L = 9: structural, fast. The drift is large so that one sweep of drift changes the lattice.
    "L_blocks": 3, "burn": 5, "seed": 7, "k": 2, "nlev": 2, "index_unit": "sweep", "index_kind": "sample_counter",
    "lag": 2, "horizon": 20000, "dials": [DIAL], "fixed": {}, "hidden": {"L4": 0.14},
    "drift": {"target": "L4", "law": "linear", "rate": 5.0e-6},
}
STATIC = {**WORLD, "drift": {"target": "L4", "law": "none"}}
DECLARED_KEYS = {"op", "wire", "dials", "pos", "fixed", "ordered_side", "roles", "index", "horizon", "lag", "tau", "k", "L",
                 "index_unit", "index_kind", "clock"}
READING_KEYS = {"op", "pos", "window", "values", "errors", "index"}
ROLES = [{"name": "D", "role": "crossing", "ordered_sign": "+"}, {"name": "C", "role": "peak"}]
FORBIDDEN = ("K_c", "drift", "L4", "actual", "hidden", "truth", "law", "rate", "edge", TIME_LABEL)
RQ = {"n_eq": 3, "S": 40, "skip": 1}
SEQUENCE = [                         # the master sequence of a03 / a07
    {"op": "read", **RQ},
    {"op": "nudge", "d": [7], **RQ},
    {"op": "nudge", "d": [-32], "n_eq": 2, "S": 41, "skip": 2},
    {"op": "scan", "ticks": [[100], [900], [410]], **RQ},
    {"op": "read", "n_eq": 0, "S": 40, "skip": 1},
    {"op": "nudge", "d": [0], **RQ},
]
FROZEN = {         # sha256 at plan 1545's base: 5a-S adds files, it edits none of these
    "system-instantiated/plugins/at/plugin.py": "667ea692febe23bd393a9d00a8cfddb669b1660a5cdf4c25cb4065307a57bc00",
    "system-instantiated/plugins/at/blind.py": "f261eb6a12c5d7858b31f4dc036a83767af32ae81de143783effcbc6e1504885",
    "environment/blind_wire.py": "d146e7b3566d0f9740822fc912fbd1b66d89bb52c3705574b21f4ac9733a0b16",
    "environment/blind_server.py": "b814ad13891571172bad4bae1198640f89eef6e30589308c9ab5f468837f324b",
    "environment/blind_config.py": "f5eb9d19e2a0c25ec635247a95f6efecf6dca92faf49dbce7c195267e42927f5",
    "environment/config.py": "65d1227a5cc269193825bf6f841613b01131f8998a7961b44109c246bf9f445a",
}


# ---------------------------------------------------------------- plumbing
def _free_port():
    s = socket.socket(); s.bind(("127.0.0.1", 0)); p = s.getsockname()[1]; s.close(); return p


def _toml(v):
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, (int, float)):
        return repr(v)
    if isinstance(v, str):
        return json.dumps(v)
    if isinstance(v, list):
        return "[" + ", ".join(_toml(x) for x in v) + "]"
    return "{" + ", ".join(f"{k} = {_toml(x)}" for k, x in v.items()) + "}"


def _write_cfgs(tmp, port, world):
    at_dir = tmp / "plugins_at"; at_dir.mkdir(parents=True, exist_ok=True)
    env_path, at_path = tmp / "environment.toml", at_dir / "at-apparatus.toml"
    env_path.write_text(f'system = "at"\nport = {port}\nrun_dir_root = "{tmp / "runs"}"\n')
    at_path.write_text("".join(f"{k} = {_toml(v)}\n" for k, v in world.items()))
    (at_dir / "tau-v0.toml").write_text(f"value = {TAU}\n")
    return env_path, at_path


def _popen(module, env_path, at_path, run_dir):
    return subprocess.Popen([sys.executable, "-m", module, "--env", str(env_path), "--at", str(at_path), "--run-dir", str(run_dir)],
                            cwd=str(ROOT), stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)


def _wait_bound(proc, port, what):
    for _ in range(600):
        if proc.poll() is not None:
            _, err = proc.communicate()
            raise AssertionError(f"{what} exited early rc={proc.returncode}\nstderr={err[-600:]}")
        try:
            socket.create_connection(("127.0.0.1", port), timeout=0.2).close(); return proc
        except OSError:
            time.sleep(0.05)
    proc.kill(); raise AssertionError(f"{what} never bound the port")


class _Conn:
    def __init__(self, port):
        self.s = socket.create_connection(("127.0.0.1", port), timeout=60)
        self.rf = self.s.makefile("r", encoding="utf-8", newline="\n")

    def raw(self, line):
        self.s.sendall(line.encode() + b"\n")
        out = self.rf.readline(); assert out, "server closed unexpectedly"
        return out

    def ask(self, msg):
        return json.loads(self.raw(json.dumps(msg)))

    def close(self):
        try:
            self.s.close()
        except OSError:
            pass


def _server(tmp, world):
    port = _free_port(); env_path, at_path = _write_cfgs(tmp, port, world)
    run_dir = tmp / "run"
    proc = _wait_bound(_popen("environment.apparatus_server", env_path, at_path, run_dir), port, "apparatus server")
    return proc, _Conn(port), run_dir


def _stop(proc, conn):
    conn.close(); proc.terminate(); proc.wait(timeout=20)


def _close(a, b):
    return abs(a - b) <= 1e-12 * max(1.0, abs(b))


# ---------------------------------------------------------------- the declared computation, straight from the vendor
def _vendor():
    if str(VENDOR) not in sys.path:
        sys.path.insert(0, str(VENDOR))
    import lattice_at, observables_at  # noqa: E401
    return lattice_at, observables_at


def _offset(drift, i):
    law = drift["law"]
    if law == "none":
        return 0.0
    if law == "linear":
        return drift["rate"] * i
    if law == "sine":
        return drift["amp"] * math.sin(2.0 * math.pi * i / drift["period"])
    if law == "step":
        return drift["size"] if i >= drift["at"] else 0.0
    raise AssertionError(law)


class _Model:
    """SCHEMA-1545 sections 3 and 5, written out a second time, independently of the implementation."""

    def __init__(self, world):
        self.lat, self.obs = _vendor()
        self.w = world
        self.L = 3 * world["L_blocks"]
        self.pos = [d["start"] for d in world["dials"]]
        self.rng = np.random.default_rng(world["seed"])
        Ss, Ts = self.lat.at_sw(self.L, self.K(self.pos), self.L4(0), 1, 0, world["burn"], self.rng)
        self.s, self.t, self.index, self.rows = Ss[0], Ts[0], 0, []

    def K(self, pos):
        v = dict(self.w["fixed"])
        for d, t in zip(self.w["dials"], pos):
            v[d["name"]] = d["lo"] + t * (d["hi"] - d["lo"]) / d["T"]
        return v["K"]

    def L4(self, i):
        return self.w["hidden"]["L4"] + _offset(self.w["drift"], i)

    def K_c(self, i):
        return float(self.lat.self_dual_K(self.L4(i)))

    def _sweep(self, pos):
        self.s, self.t = self.lat._step(self.s, self.t, self.K(pos), self.L4(self.index), self.rng)
        self.index += 1

    def call(self, msg):
        """the reply to an ACCEPTED read / nudge / scan."""
        op, n_eq, S, skip = msg["op"], msg["n_eq"], msg["S"], msg["skip"]
        points = {"read": lambda: [list(self.pos)], "nudge": lambda: [[p + d for p, d in zip(self.pos, msg["d"])]],
                  "scan": lambda: [list(p) for p in msg["ticks"]]}[op]()
        lag = 0 if op == "read" else self.w["lag"]
        N, B = self.L * self.L, 20
        out = {"op": "reading", "pos": [], "window": [], "values": {"D": [], "C": []}, "errors": {"D": [], "C": []}}
        truth_points = []
        for cur in points:
            for _ in range(lag):
                self._sweep(self.pos)
            for _ in range(n_eq - lag):
                self._sweep(cur)
            E2, G = np.empty(S), np.empty((S, self.w["nlev"]))
            a = self.index + skip
            for i in range(S):
                for _ in range(skip):
                    self._sweep(cur)
                e2, _, gs, _ = self.obs.observables(self.s[None, :, :], self.t[None, :, :], self.w["nlev"])
                E2[i], G[i] = e2[0], gs[0]
            blocks = np.array_split(np.arange(S), B)

            def jk(f):
                loo = np.array([f(np.setdiff1d(np.arange(S), b)) for b in blocks])
                return math.sqrt((B - 1) / B * float(((loo - loo.mean()) ** 2).sum()))
            g0, g1 = float(G[:, 0].mean()), float(G[:, 1].mean())
            out["values"]["D"].append(g1 - g0)
            out["errors"]["D"].append(math.sqrt(jk(lambda idx: G[idx, 1].mean()) ** 2 + jk(lambda idx: G[idx, 0].mean()) ** 2))
            out["values"]["C"].append(float(E2.var() / N))
            out["errors"]["C"].append(jk(lambda idx: E2[idx].var() / N))
            out["pos"].append(list(cur)); out["window"].append([a, self.index])
            truth_points.append({"pos": list(cur), "window": [a, self.index], "K_c": [self.K_c(a), self.K_c(self.index)]})
            self.pos = list(cur)
        out["index"] = self.index
        d = self.w["dials"]
        self.rows.append({"call": len(self.rows) + 1, "op": op, "index": self.index, "K_c": self.K_c(self.index), "pos": list(self.pos),
                          "actual": [x["lo"] + t * (x["hi"] - x["lo"]) / x["T"] for x, t in zip(d, self.pos)], "points": truth_points})
        return out


def _same_reading(got, want, tag):
    assert set(got) == READING_KEYS, (tag, sorted(got))
    assert got["op"] == "reading" and got["pos"] == want["pos"] and got["window"] == want["window"] and got["index"] == want["index"], \
        (tag, {k: got[k] for k in ("op", "pos", "window", "index")}, {k: want[k] for k in ("pos", "window", "index")})
    for part in ("values", "errors"):
        assert set(got[part]) == {"D", "C"}, (tag, part, sorted(got[part]))
        for name in ("D", "C"):
            g, w = got[part][name], want[part][name]
            assert isinstance(g, list) and len(g) == len(w) and all(isinstance(x, float) for x in g), (tag, part, name, g)
            for j, (x, y) in enumerate(zip(g, w)):
                assert _close(x, y), f"{tag}: {part}.{name}[{j}] = {x!r}, the declared computation gives {y!r}"


# ---------------------------------------------------------------- the tests
def test_a01_the_face_has_exactly_four_ops(tmp_path):
    proc, c, _ = _server(tmp_path, WORLD)
    try:
        assert c.ask({"op": "declare"})["op"] == "declared"
        refused = [{"op": "where"}, {"op": "measure", "Ks": [0.3], "n_eq": 3, "S": 40, "skip": 1}, {"op": "set", "K": 0.3},
                   {"op": "step", "n": 1}, {"op": "sense"}, {"op": "probe", "Ks": [0.3], "n": 1}, {"op": "truth"}, {"op": "drift"},
                   {"op": "edge"}, {"op": "hold"}, {"op": "Declare"}, {"op": 3}, {"op": None}, {"op": []}, {"op": {}}, {"op": ["read"]}, {}, {"n_eq": 3, "S": 40, "skip": 1},
                   {"op": "declare", "verbose": True}, {"op": "read", **RQ, "d": [0]}, {"op": "read", "n_eq": 3, "S": 40},
                   {"op": "nudge", **RQ}, {"op": "nudge", "d": [1], "ticks": [[401]], **RQ}, {"op": "scan", "d": [1], **RQ},
                   {"op": "scan", **RQ}]
        for msg in refused:
            assert c.ask(msg) == {"op": "nev", "index": 0}, f"{msg!r} was not refused as nev at index 0"
        for line in ("not json", "[1, 2]", '"read"', "7", "null", '{"op": "read"'):
            assert json.loads(c.raw(line)) == {"op": "nev", "index": 0}, f"line {line!r} was not nev"
        c.s.sendall(b'\xff\xfe{"op": "declare"}\n')                    # not UTF-8: still one line, still nev, still serving
        assert json.loads(c.rf.readline()) == {"op": "nev", "index": 0}, "a line that is not UTF-8 was not nev"
        d = c.ask({"op": "declare"})
        assert d["pos"] == [DIAL["start"]] and d["index"] == 0, ("a refused line moved something", d)
    finally:
        _stop(proc, c)


def test_a02_the_declaration(tmp_path):
    proc, c, _ = _server(tmp_path, WORLD)
    try:
        d = c.ask({"op": "declare"})
        assert set(d) == DECLARED_KEYS, f"declared keys {sorted(d)} != {sorted(DECLARED_KEYS)}"
        assert d["op"] == "declared" and d["wire"] == WIRE, d
        assert d["dials"] == [{k: DIAL[k] for k in ("name", "lo", "hi", "T", "max_nudge")}], d["dials"]
        assert all(type(d["dials"][0][k]) is int for k in ("T", "max_nudge")), d["dials"]
        assert d["pos"] == [400] and type(d["pos"][0]) is int and d["index"] == 0 and type(d["index"]) is int, d
        assert d["fixed"] == {} and d["ordered_side"] == {"K": "+"} and d["roles"] == ROLES, d
        assert d["horizon"] == 20000 and d["lag"] == 2 and d["tau"] == TAU and d["k"] == 2 and d["L"] == 9, d
        assert d["index_unit"] == "sweep" and d["index_kind"] == "sample_counter", d
        assert d["clock"] == "algorithmic (Swendsen-Wang)", d
        c.ask({"op": "nudge", "d": [5], **RQ})
        d2 = c.ask({"op": "declare"})
        assert d2["pos"] == [405] and d2["index"] == 43, ("declare reports the current position and index", d2)
        assert {k: v for k, v in d2.items() if k not in ("pos", "index")} == {k: v for k, v in d.items() if k not in ("pos", "index")}
    finally:
        _stop(proc, c)


def test_a03_readings_match_the_declared_computation(tmp_path):
    proc, c, _ = _server(tmp_path, WORLD)
    try:
        m = _Model(WORLD)
        for n, msg in enumerate(SEQUENCE):
            _same_reading(c.ask(msg), m.call(msg), f"call {n} {msg['op']}")
        assert m.index == 43 + 43 + 84 + 3 * 43 + 40 + 43, m.index
    finally:
        _stop(proc, c)


def test_a04_a_refused_call_changes_nothing(tmp_path):
    proc, c, _ = _server(tmp_path, WORLD)
    try:
        m = _Model(WORLD)
        first = {"op": "nudge", "d": [7], **RQ}
        _same_reading(c.ask(first), m.call(first), "first")
        i0 = m.index
        bad = [
            {"op": "nudge", "d": [33], **RQ}, {"op": "nudge", "d": [-33], **RQ}, {"op": "nudge", "d": [1200], **RQ},      # beyond max_nudge
            {"op": "nudge", "d": [1.0], **RQ}, {"op": "nudge", "d": [0.5], **RQ}, {"op": "nudge", "d": [True], **RQ},      # not ints
            {"op": "nudge", "d": ["1"], **RQ}, {"op": "nudge", "d": [None], **RQ}, {"op": "nudge", "d": 1, **RQ},
            {"op": "nudge", "d": [], **RQ}, {"op": "nudge", "d": [1, 1], **RQ}, {"op": "nudge", "d": [[1]], **RQ},        # wrong length
            {"op": "nudge", "d": [1], "n_eq": 1, "S": 40, "skip": 1},                                                    # n_eq < lag
            {"op": "nudge", "d": [1], "n_eq": 3, "S": 39, "skip": 1}, {"op": "nudge", "d": [1], "n_eq": 3, "S": 40, "skip": 0},
            {"op": "nudge", "d": [1], "n_eq": 3.0, "S": 40, "skip": 1}, {"op": "nudge", "d": [1], "n_eq": True, "S": 40, "skip": 1},
            {"op": "nudge", "d": [1], "n_eq": 3, "S": 40.0, "skip": 1}, {"op": "nudge", "d": [1], "n_eq": 3, "S": 40, "skip": True},
            {"op": "read", "n_eq": -1, "S": 40, "skip": 1}, {"op": "read", "n_eq": 3, "S": 39, "skip": 1},
            {"op": "read", "n_eq": "3", "S": 40, "skip": 1},
            {"op": "scan", "ticks": [], **RQ}, {"op": "scan", "ticks": [407], **RQ}, {"op": "scan", "ticks": [[]], **RQ},
            {"op": "scan", "ticks": [[1201]], **RQ}, {"op": "scan", "ticks": [[-1]], **RQ}, {"op": "scan", "ticks": [[400.0]], **RQ},
            {"op": "scan", "ticks": [[400, 400]], **RQ}, {"op": "scan", "ticks": [[True]], **RQ},
            {"op": "scan", "ticks": [[100], [200], [1201]], **RQ},        # the LAST point is illegal: nothing of the scan may run
            {"op": "scan", "ticks": [[100], [200.5], [300]], **RQ},
            {"op": "scan", "ticks": [[100]], "n_eq": 1, "S": 40, "skip": 1},
        ]
        for msg in bad:
            assert c.ask(msg) == {"op": "nev", "index": i0}, f"{msg!r} was not refused as nev at index {i0}"
        d = c.ask({"op": "declare"})
        assert d["pos"] == [407] and d["index"] == i0, ("a refused call moved the dial or the index", d)
        # the edges are refused, never clamped: walk to tick 1200, then one more
        up = {"op": "scan", "ticks": [[1190]], **RQ}
        _same_reading(c.ask(up), m.call(up), "to 1190")
        i1 = m.index
        assert c.ask({"op": "nudge", "d": [11], **RQ}) == {"op": "nev", "index": i1}, "a nudge past the top tick was not refused"
        assert c.ask({"op": "declare"})["pos"] == [1190], "a refused nudge was clamped to the edge"
        edge = {"op": "nudge", "d": [10], **RQ}
        _same_reading(c.ask(edge), m.call(edge), "to the top tick")
        assert c.ask({"op": "nudge", "d": [1], **RQ}) == {"op": "nev", "index": m.index}
        down = {"op": "scan", "ticks": [[3]], **RQ}
        _same_reading(c.ask(down), m.call(down), "to 3")
        assert c.ask({"op": "nudge", "d": [-4], **RQ}) == {"op": "nev", "index": m.index}, "a nudge below tick 0 was not refused"
        # the stream is untouched by every refusal above: the next reading is still the declared computation
        after = {"op": "read", **RQ}
        _same_reading(c.ask(after), m.call(after), "after the refusals")
        # a round trip of +2g then -2g returns to the same integer tick
        for step in ({"op": "nudge", "d": [24], **RQ}, {"op": "nudge", "d": [-24], **RQ}):
            _same_reading(c.ask(step), m.call(step), "round trip")
        assert c.ask({"op": "declare"})["pos"] == [3]
    finally:
        _stop(proc, c)


def test_a05_the_horizon_is_a_door_rule(tmp_path):
    world = {**WORLD, "horizon": 100}
    proc, c, _ = _server(tmp_path, world)
    try:
        m = _Model(world)
        for msg in ({"op": "read", **RQ}, {"op": "nudge", "d": [1], **RQ}):           # index 43, then 86
            _same_reading(c.ask(msg), m.call(msg), msg["op"])
        for msg in ({"op": "read", **RQ}, {"op": "nudge", "d": [1], **RQ}, {"op": "scan", "ticks": [[5]], **RQ},
                    {"op": "read", "n_eq": 0, "S": 40, "skip": 1}):
            assert c.ask(msg) == {"op": "nev", "index": 86}, f"{msg!r} runs past the horizon and was not refused"
        assert c.ask({"op": "declare"})["pos"] == [401]
    finally:
        _stop(proc, c)
    world = {**WORLD, "horizon": 129}
    proc, c, _ = _server(tmp_path / "exact", world)
    try:
        m = _Model(world)
        assert c.ask({"op": "scan", "ticks": [[1], [2], [3], [4]], **RQ}) == {"op": "nev", "index": 0}, "4 points cost 172 > 129"
        assert c.ask({"op": "read", "n_eq": 3, "S": 64, "skip": 2}) == {"op": "nev", "index": 0}, "the cost counts skip: 3 + 64 * 2 = 131 > 129"
        msg = {"op": "scan", "ticks": [[1], [2], [3]], **RQ}                          # costs exactly 129: allowed
        _same_reading(c.ask(msg), m.call(msg), "exactly to the horizon")
    finally:
        _stop(proc, c)


def test_a06_drift_never_reaches_the_needle(tmp_path):
    lines = {}
    for name, world in (("drift", WORLD), ("static", STATIC)):
        proc, c, run_dir = _server(tmp_path / name, world)
        try:
            got = [c.raw('{"op": "declare"}')]
            for msg in SEQUENCE + [{"op": "where"}, {"op": "nudge", "d": [99], **RQ}, {"op": "declare"}]:
                got.append(c.raw(json.dumps(msg)))
            lines[name] = got
            for line in got:
                for word in FORBIDDEN + (str(run_dir), str(tmp_path)):
                    assert word not in line, f"the wire carries {word!r}: {line[:200]}"
                r = json.loads(line)
                assert set(r) in (DECLARED_KEYS, READING_KEYS, {"op", "index"}), sorted(r)
        finally:
            _stop(proc, c)
    assert lines["drift"][0] == lines["static"][0], "the declaration differs between a drifting and a static world"
    assert lines["drift"][-1] == lines["static"][-1], "the declaration after the same calls differs with drift"
    assert lines["drift"][1] != lines["static"][1], "the drift did not act on the lattice (the two worlds read the same)"


def test_a07_the_truth_lives_only_in_the_run_directory(tmp_path):
    port = _free_port(); env_path, at_path = _write_cfgs(tmp_path, port, WORLD)
    run_dir = tmp_path / "run"
    proc = _wait_bound(_popen("environment.apparatus_server", env_path, at_path, run_dir), port, "apparatus server")
    c = _Conn(port)
    m = _Model(WORLD)
    try:
        edge = json.loads((run_dir / "edge.json").read_text())           # present while the server is still serving
        assert not (run_dir / "truth.json").exists(), "truth.json is written on exit, not before"
        assert set(edge) == {"time", "wire", "index", "K_c", "drift", "hidden"}, sorted(edge)
        assert edge["time"] == TIME_LABEL and edge["wire"] == WIRE and edge["index"] == 0, edge
        assert edge["K_c"] == m.K_c(0) and edge["drift"] == WORLD["drift"] and edge["hidden"] == WORLD["hidden"], edge
        n_lines = 0
        for msg in SEQUENCE[:2] + [{"op": "where"}, {"op": "nudge", "d": [99], **RQ}, {"op": "declare"}] + SEQUENCE[2:]:
            c.ask(msg); n_lines += 1
        for msg in SEQUENCE:
            m.call(msg)
    finally:
        _stop(proc, c)
    assert proc.returncode == 0, f"the server must exit 0 on SIGTERM, got {proc.returncode}"
    truth = json.loads((run_dir / "truth.json").read_text())
    assert set(truth) == {"time", "wire", "rows"} and truth["time"] == TIME_LABEL and truth["wire"] == WIRE, sorted(truth)
    assert len(truth["rows"]) == len(SEQUENCE), f"{len(truth['rows'])} rows for {len(SEQUENCE)} accepted calls (refusals and declare write none)"
    for got, want in zip(truth["rows"], m.rows):
        assert set(got) == {"call", "op", "index", "K_c", "pos", "actual", "points"}, sorted(got)
        assert got == want, f"truth row {want['call']}:\n got  {got}\n want {want}"
    ks = [r["K_c"] for r in truth["rows"]]
    assert all(b < a for a, b in zip(ks, ks[1:])), ("L4 rises in this world, so the true K_c must fall call by call", ks)
    perf = json.loads((run_dir / "perf.json").read_text())
    assert set(perf) == {"time", "calls"} and perf["time"] == TIME_LABEL, perf
    assert len(perf["calls"]) == n_lines and all(set(x) == {"op", "seconds"} and isinstance(x["seconds"], float) for x in perf["calls"]), perf


def test_a08_a_world_with_no_dial(tmp_path):
    world = {**WORLD, "dials": [], "fixed": {"K": 0.31}}
    proc, c, run_dir = _server(tmp_path, world)
    try:
        m = _Model(world)
        d = c.ask({"op": "declare"})
        assert set(d) == DECLARED_KEYS and d["dials"] == [] and d["pos"] == [] and d["fixed"] == {"K": 0.31}, d
        assert d["ordered_side"] == {"K": "+"} and d["roles"] == ROLES, d
        for msg in ({"op": "read", **RQ}, {"op": "read", "n_eq": 0, "S": 40, "skip": 1}, {"op": "nudge", "d": [], **RQ},
                    {"op": "scan", "ticks": [[], []], **RQ}):
            _same_reading(c.ask(msg), m.call(msg), f"no dial: {msg['op']}")
        for msg in ({"op": "nudge", "d": [1], **RQ}, {"op": "nudge", "d": [0], **RQ}, {"op": "scan", "ticks": [[400]], **RQ}):
            assert c.ask(msg) == {"op": "nev", "index": m.index}, f"{msg!r}: there is no dial to move"
    finally:
        _stop(proc, c)
    truth = json.loads((run_dir / "truth.json").read_text())
    assert [r["actual"] for r in truth["rows"]] == [[]] * 4 and [r["pos"] for r in truth["rows"]] == [[]] * 4, truth["rows"]


def _without(d, key):
    return {k: v for k, v in d.items() if k != key}


def test_a09_the_world_file_is_strict(tmp_path):
    two = [DIAL, {**DIAL, "name": "K"}]
    bad = [
        ("lag", _without(WORLD, "lag")), ("lag", {**WORLD, "lag": -1}), ("lag", {**WORLD, "lag": True}), ("lag", {**WORLD, "lag": 2.0}),
        ("horizon", _without(WORLD, "horizon")), ("horizon", {**WORLD, "horizon": 0}),
        ("L_blocks", _without(WORLD, "L_blocks")), ("seed", _without(WORLD, "seed")), ("k", {**WORLD, "k": 0}),
        ("burn", {**WORLD, "burn": -1}), ("index_unit", _without(WORLD, "index_unit")),
        ("L4", {**WORLD, "L4": 0.14}), ("knobs_K", {**WORLD, "knobs_K": [0.2, 0.5]}), ("K_start", {**WORLD, "K_start": 0.2}),
        ("dials", _without(WORLD, "dials")), ("dials", {**WORLD, "dials": two}), ("dials", {**WORLD, "dials": 1}),
        ("name", {**WORLD, "dials": [{**DIAL, "name": "L4"}]}), ("name", {**WORLD, "dials": [_without(DIAL, "name")]}),
        ("lo", {**WORLD, "dials": [{**DIAL, "lo": 1}]}), ("hi", {**WORLD, "dials": [{**DIAL, "hi": 0.2}]}),
        ("hi", {**WORLD, "dials": [{**DIAL, "hi": 0.1}]}),
        ("T", {**WORLD, "dials": [{**DIAL, "T": 0}]}), ("T", {**WORLD, "dials": [{**DIAL, "T": 1200.0}]}),
        ("max_nudge", {**WORLD, "dials": [{**DIAL, "max_nudge": 0}]}), ("max_nudge", {**WORLD, "dials": [{**DIAL, "max_nudge": 1201}]}),
        ("max_nudge", {**WORLD, "dials": [_without(DIAL, "max_nudge")]}),
        ("start", {**WORLD, "dials": [{**DIAL, "start": 1201}]}), ("start", {**WORLD, "dials": [{**DIAL, "start": -1}]}),
        ("slew", {**WORLD, "dials": [{**DIAL, "slew": 3}]}),
        ("fixed", _without(WORLD, "fixed")), ("fixed", {**WORLD, "fixed": {"K": 0.3}}), ("fixed", {**WORLD, "dials": [], "fixed": {}}),
        ("fixed", {**WORLD, "dials": [], "fixed": {"K": 1}}),
        ("hidden", _without(WORLD, "hidden")), ("hidden", {**WORLD, "hidden": {}}), ("hidden", {**WORLD, "hidden": {"L4": 0.0}}),
        ("hidden", {**WORLD, "hidden": {"L4": 0.28}}), ("hidden", {**WORLD, "hidden": {"L4": 0.14, "w": 1.0}}),
        ("drift", _without(WORLD, "drift")),
        ("law", {**WORLD, "drift": {"target": "L4", "law": "ramp"}}), ("target", {**WORLD, "drift": {"target": "K", "law": "none"}}),
        ("rate", {**WORLD, "drift": {"target": "L4", "law": "linear"}}),
        ("drift", {**WORLD, "drift": {"target": "L4", "law": "linear", "rate": 1.0e-5}}),      # 0.14 + 0.2 leaves the domain
        ("drift", {**WORLD, "drift": {"target": "L4", "law": "linear", "rate": -8.0e-6}}),     # goes below 0.0
        ("drift", {**WORLD, "drift": {"target": "L4", "law": "sine", "amp": 0.14, "period": 100}}),
        ("drift", {**WORLD, "drift": {"target": "L4", "law": "step", "at": 50000, "size": 0.2}}),   # judged by its bounds, not by `at`
    ]
    for n, (field, world) in enumerate(bad):
        tmp = tmp_path / f"w{n}"; tmp.mkdir()
        port = _free_port(); env_path, at_path = _write_cfgs(tmp, port, world)
        proc = _popen("environment.apparatus_server", env_path, at_path, tmp / "run")
        try:
            _, err = proc.communicate(timeout=60)
        except subprocess.TimeoutExpired:
            proc.kill(); proc.communicate()
            raise AssertionError(f"a malformed world (want field={field}) started and served: {world!r}")
        line = err.strip().splitlines()[-1] if err.strip() else ""
        assert proc.returncode == 2 and line.startswith(f"RefusedToStart field={field} parse=B"), \
            f"want exit 2 and 'RefusedToStart field={field} parse=B', got rc={proc.returncode} {line[:200]!r}"
        assert not (tmp / "run").exists(), f"a refused world (field={field}) created its run directory"


def test_a10_static_and_lagless_it_is_the_frozen_blind_face(tmp_path):
    world = {**STATIC, "lag": 0, "dials": [{**DIAL, "start": 0}]}
    ticks = [[400], [600], [333]]
    Ks = [DIAL["lo"] + t[0] * (DIAL["hi"] - DIAL["lo"]) / DIAL["T"] for t in ticks]
    proc, c, _ = _server(tmp_path / "app", world)
    try:
        a = c.ask({"op": "scan", "ticks": ticks, **RQ})
    finally:
        _stop(proc, c)
    tmp = tmp_path / "blind"; at_dir = tmp / "plugins_at"; at_dir.mkdir(parents=True)
    port = _free_port()
    (tmp / "environment.toml").write_text(f'system = "at"\nport = {port}\nrun_dir_root = "{tmp / "runs"}"\n')
    (at_dir / "at-blind.toml").write_text(
        "L_blocks = 3\nL4 = 0.14\nburn = 5\nseed = 7\nk = 2\nnlev = 2\nknobs_K = [0.2, 0.5]\nK_start = 0.2\n"
        'index_unit = "sweep"\nindex_kind = "sample_counter"\n')
    (at_dir / "tau-v0.toml").write_text(f"value = {TAU}\n")
    proc = _wait_bound(_popen("environment.blind_server", tmp / "environment.toml", at_dir / "at-blind.toml", tmp / "run"), port, "blind server")
    c = _Conn(port)
    try:
        b = c.ask({"op": "measure", "Ks": Ks, **RQ})
    finally:
        _stop(proc, c)
    assert a["op"] == "reading" and b["op"] == "moments", (a, b)
    assert a["index"] == b["index"] == 129, (a["index"], b["index"])
    for j in range(3):
        assert a["values"]["D"][j] == b["Gs"][j][1] - b["Gs"][j][0], ("D", j, a["values"]["D"][j], b["Gs"][j])
        assert a["errors"]["D"][j] == math.sqrt(b["Gs_err"][j][1] ** 2 + b["Gs_err"][j][0] ** 2), ("D_err", j)
        assert a["values"]["C"][j] == b["C"][j] and a["errors"]["C"][j] == b["C_err"][j], ("C", j, a["values"]["C"][j], b["C"][j])


def test_a11_step_and_sine_act_at_the_declared_index(tmp_path):
    worlds = {
        "step": {**WORLD, "drift": {"target": "L4", "law": "step", "at": 60, "size": 0.05}},
        "sine": {**WORLD, "drift": {"target": "L4", "law": "sine", "amp": 0.04, "period": 37}},
        # steep and not a dyadic rate: a drift summed sweep by sweep rounds differently from rate * index
        "steep": {**WORLD, "horizon": 700, "drift": {"target": "L4", "law": "linear", "rate": 1.7e-4}},
    }
    calls = [{"op": "read", **RQ}, {"op": "nudge", "d": [-9], **RQ}, {"op": "scan", "ticks": [[500], [380]], **RQ}]
    calls += [{"op": "read", "n_eq": 0, "S": 40, "skip": 1}] * 7
    for name, world in worlds.items():
        proc, c, run_dir = _server(tmp_path / name, world)
        m = _Model(world)
        try:
            for msg in calls:
                _same_reading(c.ask(msg), m.call(msg), f"{name} {msg['op']}")
        finally:
            _stop(proc, c)
        rows = json.loads((run_dir / "truth.json").read_text())["rows"]
        assert rows == m.rows, f"{name}: truth rows differ from the declared law"
    step = _Model(worlds["step"])
    assert step.K_c(59) == step.K_c(0) != step.K_c(60) == step.K_c(19999), "the step law of the model itself"


def test_a12_the_older_faces_are_byte_identical():
    for rel, want in FROZEN.items():
        got = hashlib.sha256((ROOT / rel).read_bytes()).hexdigest()
        assert got == want, f"{rel} was edited (sha256 {got[:12]}…); stage 5a-S adds files and edits none of the older faces"


PRODUCTION = {
    "L_blocks": 27, "burn": 400, "seed": 110, "k": 6, "nlev": 2, "index_unit": "sweep", "index_kind": "sample_counter",
    "lag": 48, "horizon": 200000, "dials": [{"name": "K", "lo": 0.2, "hi": 0.5, "T": 1200, "max_nudge": 32, "start": 0}],
    "fixed": {}, "hidden": {"L4": 0.14},
}


def test_a13_the_shipped_worlds_hold_the_declared_numbers():
    import tomllib
    at = ROOT / "system-instantiated" / "plugins" / "at"
    drifting = tomllib.loads((at / "at-apparatus.toml").read_text())
    static = tomllib.loads((at / "at-apparatus-static.toml").read_text())
    assert drifting == {**PRODUCTION, "drift": {"target": "L4", "law": "linear", "rate": -4.0e-7}}, drifting
    assert static == {**PRODUCTION, "drift": {"target": "L4", "law": "none"}}, static
    env = tomllib.loads((ROOT / "environment" / "environment-apparatus.toml").read_text())
    assert set(env) == {"system", "port", "run_dir_root"} and env["system"] == "at", env
    # the declared arithmetic: the floor lag + k * tau equals stage 3a's n_eq, and the drift stays inside the model
    tau = tomllib.loads((at / "tau-v0.toml").read_text())["value"]
    assert PRODUCTION["lag"] + PRODUCTION["k"] * tau == 450, (PRODUCTION["lag"], tau)
    end = 0.14 - 4.0e-7 * PRODUCTION["horizon"]
    assert 0.0 < end < 0.14 and abs(end - 0.06) < 1e-12, end


if __name__ == "__main__":
    import tempfile
    _tests = [test_a01_the_face_has_exactly_four_ops, test_a02_the_declaration, test_a03_readings_match_the_declared_computation,
              test_a04_a_refused_call_changes_nothing, test_a05_the_horizon_is_a_door_rule, test_a06_drift_never_reaches_the_needle,
              test_a07_the_truth_lives_only_in_the_run_directory, test_a08_a_world_with_no_dial, test_a09_the_world_file_is_strict,
              test_a10_static_and_lagless_it_is_the_frozen_blind_face, test_a11_step_and_sine_act_at_the_declared_index]
    _fail = 0
    for _t in _tests:
        with tempfile.TemporaryDirectory() as _d:
            try:
                _t(Path(_d)); print(f"PASS {_t.__name__}")
            except Exception as _e:  # noqa: BLE001
                _fail += 1; print(f"FAIL {_t.__name__}: {type(_e).__name__}: {str(_e)[:400]}")
    for _t in (test_a12_the_older_faces_are_byte_identical, test_a13_the_shipped_worlds_hold_the_declared_numbers):
        try:
            _t(); print(f"PASS {_t.__name__}")
        except Exception as _e:  # noqa: BLE001
            _fail += 1; print(f"FAIL {_t.__name__}: {type(_e).__name__}: {str(_e)[:400]}")
    print(f"{len(_tests) + 2 - _fail}/{len(_tests) + 2} passed")
    sys.exit(1 if _fail else 0)
