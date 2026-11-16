"""Plan 1552: the shared fixture of the hold contract tests (contract/SCHEMA-1552.md). FROZEN with the tests.

`Fake` is a scripted apparatus: it serves the four ops of contract/SCHEMA-1545.md on a loopback port with the door rules of
that wire as relaxed by plan 1553 (SCHEMA-1553) (whole-call refusal, no clamp, max_nudge, the horizon; `n_eq` below the
declared lag is ACCEPTED: the needle may read mid-move), but its readings come from a function the
test supplies, `f(tick, index, n) -> D`, where `n` counts the measured calls it has accepted. It keeps every request and every
reply, so a test can hold the needle to exactly what it sent. `drop` runs the needle as the orchestrator does: a separate
process handed a settings file, a port, a drop name and a map path, and nothing else."""
import json
import socket
import subprocess
import sys
import threading
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WIRE = "compass-apparatus/1"
CFG = {            # the declared settings of plan 1552: navigator/hold-settled.toml holds exactly these (SETTLED: one of the two hold modes; neither is a default)
    "needle_structure": "hold-pair-v1", "ops": ["declare", "scan", "nudge"], "g": 12, "step": 6, "sigma": 0,
    "n_eq": 450, "S": 500, "skip": 1, "z": 2.0, "ignite": {"steps": [100, 20], "S": 100, "margin": 1, "n_eq": 450}, "approach": {"S": 40, "n_eq": 48},
    "lost": 3,
    "M": {"observable": "D",
          "node": "one reading of the observable: its value at one dial tick, over the window and at the index the wire reports",
          "relation": "path",
          "edge": "from each reading of a drop to the reading the wire served just before it",
          "direction": "the wire's index: the source is the later reading, so the difference is current minus prior",
          "provenance": "steering (declared under the Origin's ruling, pending kernel revision)",
          "transform": "none", "rho_base": "not-declared", "chi_0": "not-declared"},
}
OFF_OPS = ["declare", "scan"]
MID = {**CFG, "n_eq": 0, "S": 500}                # navigator/hold-mid.toml: the hold pair is read mid-move, and still holds
MID_OFF = {**MID, "ops": ["declare", "scan"]}     # navigator/hold-mid-off.toml
MID_NULL = {**CFG, "n_eq": 0, "S": 40}         # navigator/hold-mid-null.toml: the window ends before the dial arrives
ROLES = [{"name": "D", "role": "crossing", "ordered_sign": "+"}, {"name": "C", "role": "peak"}]


def toml(v):
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, (int, float)):
        return repr(v)
    if isinstance(v, str):
        return json.dumps(v)
    if isinstance(v, list):
        return "[" + ", ".join(toml(x) for x in v) + "]"
    return "{" + ", ".join(f"{k} = {toml(x)}" for k, x in v.items()) + "}"


def write_cfg(path, cfg):
    Path(path).write_text("".join(f"{k} = {toml(v)}\n" for k, v in cfg.items()))
    return path


class Fake:
    def __init__(self, f, T=1200, lo=0.2, hi=0.5, max_nudge=32, start=0, lag=48, horizon=200000, tau=67.0, k=6, err=0.01,
                 declared=None, hook=None):
        self.f, self.T, self.max_nudge, self.pos, self.lag, self.horizon, self.err = f, T, max_nudge, start, lag, horizon, err
        self.index, self.n, self.requests, self.replies, self.readings, self.refused, self.hook = 0, 0, [], [], [], 0, hook
        self.declared = {"op": "declared", "wire": WIRE, "dials": [{"name": "K", "lo": lo, "hi": hi, "T": T, "max_nudge": max_nudge}],
                         "pos": [start], "fixed": {}, "ordered_side": {"K": "+"}, "roles": [dict(r) for r in ROLES], "index": 0,
                         "horizon": horizon, "lag": lag, "tau": tau, "k": k, "L": 81, "index_unit": "sweep",
                         "index_kind": "sample_counter", "clock": "algorithmic (Swendsen-Wang)", **(declared or {})}
        self.sock = socket.socket()
        self.sock.bind(("127.0.0.1", 0))
        self.sock.listen(1)
        self.port = self.sock.getsockname()[1]
        self.thread = threading.Thread(target=self._serve, daemon=True)
        self.thread.start()

    def _int(self, v, lo):
        return type(v) is int and v >= lo

    def _positions(self, m):
        op = m.get("op")
        if op == "nudge" and set(m) == {"op", "d", "n_eq", "S", "skip"}:
            d = m["d"]
            ok = type(d) is list and len(d) == 1 and type(d[0]) is int and abs(d[0]) <= self.max_nudge and 0 <= self.pos + d[0] <= self.T
            return [self.pos + d[0]] if ok else None
        if op == "scan" and set(m) == {"op", "ticks", "n_eq", "S", "skip"}:
            t = m["ticks"]
            ok = type(t) is list and len(t) > 0 and all(type(p) is list and len(p) == 1 and type(p[0]) is int and 0 <= p[0] <= self.T for p in t)
            return [p[0] for p in t] if ok else None
        if op == "read" and set(m) == {"op", "n_eq", "S", "skip"}:
            return [self.pos]
        return None

    def _reply(self, m):
        if not isinstance(m, dict):
            return {"op": "nev", "index": self.index}
        if m == {"op": "declare"}:
            return {**self.declared, "pos": [self.pos], "index": self.index}
        pts = self._positions(m)
        ok = (pts is not None and self._int(m.get("n_eq"), 0) and self._int(m.get("S"), 40) and self._int(m.get("skip"), 1)
              and self.index + len(pts) * (m["n_eq"] + m["S"] * m["skip"]) <= self.horizon)
        if not ok:
            self.refused += 1
            return {"op": "nev", "index": self.index}
        out = {"op": "reading", "pos": [], "window": [], "values": {"D": [], "C": []}, "errors": {"D": [], "C": []}}
        for t in pts:
            a = self.index + m["n_eq"] + m["skip"]
            self.index += m["n_eq"] + m["S"] * m["skip"]
            d = float(self.f(t, self.index, self.n))
            out["pos"].append([t]), out["window"].append([a, self.index])
            out["values"]["D"].append(d), out["values"]["C"].append(1.0 + t / 4096.0)
            out["errors"]["D"].append(self.err), out["errors"]["C"].append(0.125)
            self.readings.append({"tick": t, "window": [a, self.index], "D": d, "D_err": self.err, "C": 1.0 + t / 4096.0, "C_err": 0.125,
                                  "op": m["op"], "n_eq": m["n_eq"], "S": m["S"]})
        self.pos, self.n = pts[-1], self.n + 1
        out["index"] = self.index
        return out

    def _serve(self):
        try:
            conn, _ = self.sock.accept()
        except OSError:
            return
        rf = conn.makefile("r", encoding="utf-8", newline="\n")
        try:
            for line in rf:
                try:
                    m = json.loads(line)
                except ValueError:
                    m = None
                self.requests.append(m)
                if self.hook:
                    self.hook(m)
                r = self._reply(m)
                self.replies.append(r)
                conn.sendall((json.dumps(r) + "\n").encode())
        except OSError:
            pass
        finally:
            rf.close()
            conn.close()

    def close(self):
        try:                                    # a serve thread still waiting in accept is let through, so the join below is prompt
            socket.create_connection(("127.0.0.1", self.port), timeout=1).close()
        except OSError:
            pass
        self.sock.close()
        self.thread.join(timeout=5)


def needle_cmd(cfg_path, port, map_path, name="t"):
    return [sys.executable, "-m", "navigator.hold", "--needle", str(cfg_path), "--port", str(port), "--drop", name, "--map", str(map_path)]


def drop(tmp, f, cfg=None, name="t", map_name="map.jsonl", **world):
    """run one needle drop against a Fake -> a result object with rc, out (stdout text), err, records, map (text), places, fake."""
    cfg_path = write_cfg(Path(tmp) / f"hold-{name}.toml", cfg or CFG)
    fake = Fake(f, **world)
    map_path = Path(tmp) / map_name
    try:
        res = subprocess.run(needle_cmd(cfg_path, fake.port, map_path, name), cwd=str(ROOT), capture_output=True, text=True, timeout=300)
    finally:
        fake.close()

    class Got:
        rc, out, err = res.returncode, res.stdout, res.stderr
        records = [json.loads(line) for line in res.stdout.splitlines()]
        map = map_path.read_text() if map_path.exists() else None
        entries = [json.loads(line) for line in (map_path.read_text().splitlines() if map_path.exists() else [])]
    Got.fake = fake
    Got.steps = [r for r in Got.records if r.get("rec") == "step"]
    Got.measured = [m for m in fake.requests if isinstance(m, dict) and m.get("op") != "declare"]
    return Got


def sign_world(x, amp=0.3):
    """D = -amp below the crossing and +amp above it; x is a tick (a real number) or a function of the index."""
    at = x if callable(x) else (lambda index: x)
    return lambda tick, index, n: amp if tick > at(index) else -amp


def kinds(got, phase):
    return [s["verdict"][0]["kind"] for s in got.steps if s["phase"] == phase]
