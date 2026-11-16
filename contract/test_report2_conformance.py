"""Plan 1533 — the needle `recover-adaptive-v1` and its orchestrator, end to end (contract/SCHEMA-1533.md).
Part 1 runs the REAL needle `navigator.recover2` as a subprocess against a scripted wire held by this test, so every cell
of the step table is reached on purpose. Part 2 runs the REAL orchestrator `environment.run_blind2` on a tiny lattice.
FROZEN: the Generator makes this green; it does not edit this file.

What it pins:
  1. the numbers are those of `recover-adaptive-v0`: on one scripted world the fold of the schema-2 stream equals the
     schema-1 report of `navigator.recover`, byte for byte as JSON;
  2. the stream is live: the start record is on stdout before the first `measure` is answered, and step r is on stdout
     before `measure` r+1 is answered;
  3. the verdict is the needle's own and is not constant: a range past either end leans, a mirrored declaration
     mirrors the lean, readings with no resolution are `unresolved`, steps that disagree are UNDECIDED;
  4. the stated exceptions to identity, exactly: a step that is not evaluated is terminal (v0 asked N times), and a
     run that is not Located keeps every evaluated step's numbers and carries no bracket;
  5. the belief is the wire's declaration as received; the mode is OFF with `declare` and `measure` held; sigma is 0 g;
  6. refusals are values with the declared exit codes and an empty stdout;
  7. the orchestrator writes report.jsonl, score.json and a schema-1 verdict.json that is the fold plus the score; the
     `plan` stamp is the score file's declared value; the score table is total;
  8. the needle cannot reach the truth, and the frozen files of plans 1511, 1525 and 1529 are unchanged.

RED until navigator/recover2.py, navigator/steer.py, navigator/report2.py, needlestream/read.py,
environment/run_blind2.py, navigator/recover2.toml and environment/score-1533.toml exist.
Run from the repo root:  python contract/test_report2_conformance.py   (or pytest)
"""
import ast
import hashlib
import json
import math
import re
import socket
import subprocess
import sys
import threading
import time
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

M, N_STEPS, N_EQ, S, SKIP, Z = 5, 4, 3, 40, 1, 2.0
PER = M * (N_EQ + S * SKIP)
BRACKET = (0.25, 0.45)
NEEDLE_V1 = {"needle_structure": '"recover-adaptive-v1"', "bracket": f"[{BRACKET[0]}, {BRACKET[1]}]", "m": str(M),
             "N": str(N_STEPS), "n_eq": str(N_EQ), "S": str(S), "skip": str(SKIP), "z": str(Z)}
NEEDLE_V0 = dict(NEEDLE_V1, needle_structure='"recover-adaptive-v0"')
DECLARED = {"op": "declared", "knobs_K": [0.2, 0.5], "ordered_side": "+K", "L": 9, "tau": 1.0, "k": 1,
            "index_unit": "sweep", "index_kind": "sample_counter", "observable": "moments", "nlev": 2}
SLOTS = ("knobs_K", "ordered_side", "L", "tau", "k", "index_unit", "index_kind", "observable", "nlev", "system", "roles")
AT_GOOD = {"L_blocks": "3", "L4": "0.14", "burn": "5", "seed": "11", "k": "1", "nlev": "2", "knobs_K": "[0.20, 0.50]",
           "K_start": "0.20", "index_unit": '"sweep"', "index_kind": '"sample_counter"'}
REPORT_KEYS = ("kind", "reason", "bracket", "A_hull", "B_hull", "agree", "rounds")
NINE = ("truth_K_c", "a", "w_max", "contains", "width", "narrow_enough", "cell", "run_id", "plan")
ALLOWED_IMPORTS = {"argparse", "json", "math", "socket", "sys", "tomllib", "dataclasses", "typing", "collections", "navigator"}
FROZEN = {
    "navigator/estimate.py": "00df2977cf05d2f26fa8de82b7a6fff25ca2d58e9ef04b89cb8fe8d3269a6ea5",
    "navigator/recover.py": "fc96da0b0a0e2f50fd1dceed4164aef0c7db8bfae0ee10b5fd98e355b771a3d0",
    "navigator/reader.py": "0f655fbfcc0cb4be7f9bd7ed89c9e94222830968d148f57d1f59a1194cfd54f8",
    "navigator/needle.py": "02f8d60e00e76684bcf9483529e8bbe42224979e6a60bc13ac7e3b18816f2f3b",
    "navigator/recover.toml": "a5e4aa121d0e2c423c73f9366c4114e641baffd670ac13d4e7da8b57ee4d2c77",
    "environment/run_blind.py": "dcf62dd6ccc2faa85439731528289c54f474faac158d1501dd4aad9d4dcc8d18",
    "environment/blind_config.py": "f5eb9d19e2a0c25ec635247a95f6efecf6dca92faf49dbce7c195267e42927f5",
    "environment/run.py": "6f9385edf14d1fbdc181e8c039f89bb09ade21efa1e2ff0ea69458d86b2e93ad",
    "environment/score-1525.toml": "9b0244ce3c3efc88c95b5f22ad7da2f29db4776b95ab47032cd9ee009b5828d6",
    "needleview/report.py": "b9ee6aa540ea5c2cbab048580262a9bbd3515d37dcb8a8403d784de0e270b7aa",
}


def _free_port():
    s = socket.socket(); s.bind(("127.0.0.1", 0)); p = s.getsockname()[1]; s.close(); return p


def _toml(d):
    return "".join(f"{k} = {v}\n" for k, v in d.items())


# ---- part 1: a scripted wire ---------------------------------------------------------------------------------------------
def crossing_at(K_c, sign=1.0, err=0.001):
    """a world whose block-ratio difference crosses zero at K_c (rising with K when sign = +1) and whose C peaks there."""
    def world(step, Ks):
        return {"C": [1.0 / (1.0 + ((K - K_c) / 0.05) ** 2) for K in Ks], "C_err": [0.001] * len(Ks),
                "Gs": [[0.5, 0.5 + sign * 2.0 * (K - K_c)] for K in Ks], "Gs_err": [[err, err]] * len(Ks)}
    return world


def by_step(*worlds):
    return lambda step, Ks: worlds[min(step, len(worlds)) - 1](step, Ks)


class Wire:
    """one connection, one JSON object per line. `measure` r is answered only once `seen()` reports r stdout lines
    (the start record and r-1 steps), or after `patience` seconds; which of the two happened is recorded in `live`."""

    def __init__(self, world, declared=DECLARED, nev_at=None, seen=None, patience=8.0):
        self.world, self.declared, self.nev_at, self.seen, self.patience = world, declared, nev_at, seen, patience
        self.ops, self.live, self.index, self.step = [], [], 0, 0
        self.sock = socket.socket()
        self.sock.bind(("127.0.0.1", 0))
        self.sock.listen(1)
        self.sock.settimeout(30)
        self.port = self.sock.getsockname()[1]
        self.thread = threading.Thread(target=self._serve, daemon=True)
        self.thread.start()

    def _reply(self, msg):
        op = msg.get("op")
        self.ops.append(op)
        if op == "declare":
            return self.declared
        if op != "measure":
            return {"op": "nev", "index": self.index}
        self.step += 1
        if self.seen is not None:
            t0 = time.time()
            while self.seen() < self.step and time.time() - t0 < self.patience:
                time.sleep(0.01)
            self.live.append(self.seen() >= self.step)
        self.index += len(msg["Ks"]) * (msg["n_eq"] + msg["S"] * msg["skip"])
        if self.nev_at == self.step:
            return {"op": "nev", "index": self.index}
        return {"op": "moments", **self.world(self.step, msg["Ks"]), "index": self.index}

    def _serve(self):
        try:
            conn, _ = self.sock.accept()
        except OSError:
            return
        with conn, conn.makefile("r", encoding="utf-8", newline="\n") as rf:
            for line in rf:
                conn.sendall((json.dumps(self._reply(json.loads(line))) + "\n").encode())

    def close(self):
        try:   # a needle that refused before connecting never arrives: let the accept return
            socket.create_connection(("127.0.0.1", self.port), timeout=1).close()
        except OSError:
            pass
        self.thread.join(timeout=30)
        self.sock.close()


def _needle(tmp, module, cfg, world, **kw):
    """-> (returncode, stdout lines, stderr, wire). The needle is a subprocess handed a port and nothing else."""
    tmp.mkdir(parents=True, exist_ok=True)
    path = tmp / "needle.toml"
    path.write_text(_toml(cfg))
    lines = []
    wire = Wire(world, seen=lambda: len(lines), **kw)
    proc = subprocess.Popen([sys.executable, "-m", module, "--needle", str(path), "--port", str(wire.port)], cwd=str(ROOT),
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    for line in proc.stdout:
        lines.append(line)
    err = proc.stderr.read()
    rc = proc.wait(timeout=120)
    wire.close()
    return rc, lines, err, wire


def _v1(tmp, world, cfg=NEEDLE_V1, **kw):
    from needlestream import read as NS
    rc, lines, err, wire = _needle(tmp / "v1", "navigator.recover2", cfg, world, **kw)
    assert rc == 0, (rc, err)
    stream = NS.read("".join(lines))
    assert isinstance(stream, NS.Stream) and stream.schema == 2, stream
    return stream, [json.loads(x) for x in lines], wire


def _v0(tmp, world, **kw):
    rc, lines, err, wire = _needle(tmp / "v0", "navigator.recover", NEEDLE_V0, world, patience=0.0, **kw)
    assert rc == 0 and len(lines) == 1, (rc, lines, err)
    return json.loads(lines[0]), wire


def _kinds(stream):
    return [(x.verdict[0].kind, x.verdict[0].reason) for x in stream.steps]


def test_c01_the_numbers_are_v0s_and_the_stream_is_live(tmp_path):
    from needlestream import read as NS
    world = crossing_at(0.3312)
    stream, recs, wire = _v1(tmp_path, world)
    v0, wire0 = _v0(tmp_path, world)
    assert v0["kind"] == "Located", v0["kind"]
    assert json.dumps(NS.fold_v1(stream), sort_keys=True) == json.dumps(v0, sort_keys=True), "the fold is not v0's report"
    assert wire.ops == wire0.ops == ["declare"] + ["measure"] * N_STEPS, (wire.ops, wire0.ops)
    assert wire.live == [True] * N_STEPS, f"a record was not on stdout before the next measure was answered: {wire.live}"
    assert _kinds(stream) == [("narrow", "SIG-|SIG+")] * N_STEPS, _kinds(stream)
    assert [r["rec"] for r in recs] == ["start"] + ["step"] * N_STEPS + ["outcome"]
    assert [x.index for x in stream.steps] == [PER * r for r in range(1, N_STEPS + 1)]
    assert stream.outcome.steps == N_STEPS and stream.outcome.kind == "Located" and stream.outcome.reason is None
    lo, hi = stream.outcome.bracket
    assert BRACKET[0] <= lo < 0.3312 < hi <= BRACKET[1], (lo, hi)


def test_c02_the_start_record_says_what_the_needle_was_given(tmp_path):
    stream, recs, _ = _v1(tmp_path, crossing_at(0.3312))
    start = recs[0]
    assert start["needle"] == "recover-adaptive-v1" and start["schema"] == "compass-report/2"
    assert start["settings"] == {"bracket": list(BRACKET), "m": M, "N": N_STEPS, "n_eq": N_EQ, "S": S, "skip": SKIP, "z": Z,
                                 "detectors": [{"name": "A", "role": "peak", "reads": "C"},
                                               {"name": "B", "role": "crossing", "reads": "Gs"}]}, start["settings"]
    assert start["mode"] == {"ops": ["declare", "measure"], "feedback": "OFF"}, start["mode"]
    assert start["dials"] == [], "this needle holds no dial"
    assert start["sigma"] == {"offset": 0, "unit": "g", "measured": "not-defined"}, start["sigma"]
    want = {**{s: "unknown" for s in SLOTS}, **{k: {"declared": v} for k, v in DECLARED.items() if k != "op"}}
    assert start["belief"] == want and start["declared_other"] == {}, start["belief"]
    assert start["belief"]["system"] == "unknown" and start["belief"]["roles"] == "unknown"
    told = dict(DECLARED, system="at", roles={"K": "knob"}, zz_note=["as", "sent", 1])
    stream, recs, _ = _v1(tmp_path / "told", crossing_at(0.3312), declared=told)
    b = recs[0]["belief"]
    assert b["system"] == {"declared": "at"} and b["roles"] == {"declared": {"K": "knob"}}, b
    assert recs[0]["declared_other"] == {"zz_note": ["as", "sent", 1]}, recs[0]["declared_other"]
    assert stream.start.belief == b


def test_c03_a_range_past_an_end_leans_and_the_numbers_stay_v0s(tmp_path):
    cases = {"above": (crossing_at(0.61), "PAST-HI", "lean-hi", "SIG-|SIG-"),
             "below": (crossing_at(0.07), "PAST-LO", "lean-lo", "SIG+|SIG+")}
    for name, (world, kind, lean, cell) in cases.items():
        stream, recs, wire = _v1(tmp_path / name, world)
        v0, _ = _v0(tmp_path / name, world)
        assert v0["kind"] == "Located", "the v0 needle has no other word for this range"
        assert _kinds(stream) == [(lean, cell)] * N_STEPS, (name, _kinds(stream))
        o = recs[-1]
        assert o == {"rec": "outcome", "kind": kind, "reason": lean, "bracket": None, "A_hull": None, "B_hull": None,
                     "agree": None, "steps": N_STEPS}, (name, o)
        assert [x.scan for x in stream.steps] == v0["rounds"], f"{name}: an evaluated step's numbers differ from v0's"
        assert wire.ops == ["declare"] + ["measure"] * N_STEPS and wire.live == [True] * N_STEPS


def test_c04_a_mirrored_declaration_mirrors_the_verdict(tmp_path):
    minus = dict(DECLARED, ordered_side="-K")
    stream, recs, _ = _v1(tmp_path / "in", crossing_at(0.3312, sign=-1.0), declared=minus)
    assert _kinds(stream) == [("narrow", "SIG+|SIG-")] * N_STEPS and stream.outcome.kind == "Located", _kinds(stream)
    assert recs[0]["belief"]["ordered_side"] == {"declared": "-K"}
    stream, _, _ = _v1(tmp_path / "above", crossing_at(0.61, sign=-1.0), declared=minus)
    assert _kinds(stream) == [("lean-hi", "SIG+|SIG+")] * N_STEPS and stream.outcome.kind == "PAST-HI", _kinds(stream)
    stream, _, _ = _v1(tmp_path / "below", crossing_at(0.07, sign=-1.0), declared=minus)
    assert _kinds(stream) == [("lean-lo", "SIG-|SIG-")] * N_STEPS and stream.outcome.kind == "PAST-LO", _kinds(stream)
    stream, _, _ = _v1(tmp_path / "against", crossing_at(0.3312, sign=-1.0))
    assert _kinds(stream) == [("unresolved", "SIG+|SIG-")] * N_STEPS, "ends that contradict the declared order are not a bracket"
    assert (stream.outcome.kind, stream.outcome.reason) == ("UNDECIDED", "unresolved")


def test_c05_no_resolution_and_disagreement_are_undecided(tmp_path):
    stream, recs, _ = _v1(tmp_path / "blur", crossing_at(0.3312, err=5.0))
    assert _kinds(stream) == [("unresolved", "UNRES|UNRES")] * N_STEPS, _kinds(stream)
    assert (stream.outcome.kind, stream.outcome.reason, stream.outcome.bracket) == ("UNDECIDED", "unresolved", None)
    world = by_step(crossing_at(0.3312), crossing_at(0.3312), crossing_at(0.61))
    stream, recs, _ = _v1(tmp_path / "mixed", world)
    v0, _ = _v0(tmp_path / "mixed", world)
    assert [k for k, _ in _kinds(stream)] == ["narrow", "narrow", "lean-hi", "lean-hi"], _kinds(stream)
    assert (stream.outcome.kind, stream.outcome.reason) == ("UNDECIDED", "narrow+lean-hi"), stream.outcome
    assert [x.scan for x in stream.steps] == v0["rounds"] and v0["kind"] == "Located"


def test_c06_a_step_that_is_not_evaluated_is_terminal(tmp_path):
    world = crossing_at(0.3312)
    stream, recs, wire = _v1(tmp_path, world, nev_at=3)
    v0, wire0 = _v0(tmp_path, world, nev_at=3)
    assert wire.ops == ["declare"] + ["measure"] * 3, f"the needle asked again after a reading that never arrived: {wire.ops}"
    assert wire0.ops == ["declare"] + ["measure"] * N_STEPS and v0["kind"] == "REFUSE" and v0["reason"] == "budget"
    assert [k for k, _ in _kinds(stream)] == ["narrow", "narrow", "not-evaluated"] and _kinds(stream)[-1][1] == "n/e"
    assert recs[-1] == {"rec": "outcome", "kind": "REFUSE", "reason": "budget", "bracket": None, "A_hull": None,
                        "B_hull": None, "agree": None, "steps": 3}, recs[-1]
    assert [x.scan for x in stream.steps] == v0["rounds"][:3], "the three steps are v0's first three rounds"
    stream, recs, wire = _v1(tmp_path / "first", world, nev_at=1)
    assert len(stream.steps) == 1 and recs[-1]["kind"] == "REFUSE" and recs[-1]["reason"] == "budget" and len(wire.ops) == 2


def test_c07_the_floor_is_a_refusal_with_no_step(tmp_path):
    stream, recs, wire = _v1(tmp_path, crossing_at(0.3312), declared=dict(DECLARED, k=5))     # n_eq = 3 < k * tau = 5
    assert wire.ops == ["declare"], wire.ops
    assert [r["rec"] for r in recs] == ["start", "outcome"] and recs[0]["belief"]["k"] == {"declared": 5}
    assert recs[1] == {"rec": "outcome", "kind": "REFUSE", "reason": "floor", "bracket": None, "A_hull": None,
                       "B_hull": None, "agree": None, "steps": 0}, recs[1]


def test_c08_refusals_are_values_and_leave_stdout_empty(tmp_path):
    cases = {
        "v0_structure": (NEEDLE_V0, DECLARED, "needle_structure", "B"),
        "unknown_key_sigma": (dict(NEEDLE_V1, sigma="1.0"), DECLARED, "sigma", "B"),
        "unknown_key_mode": (dict(NEEDLE_V1, feedback='"ON"'), DECLARED, "feedback", "B"),
        "m_4": (dict(NEEDLE_V1, m="4"), DECLARED, "m", "B"),
        "bracket_outside_knobs": (dict(NEEDLE_V1, bracket="[0.10, 0.45]"), DECLARED, "bracket", "A"),
        "ordered_side_without_a_cell": (NEEDLE_V1, dict(DECLARED, ordered_side="sideways"), "ordered_side", "A"),
        "nlev_1": (NEEDLE_V1, dict(DECLARED, nlev=1), "nlev", "A"),
        "no_tau": (NEEDLE_V1, {k: v for k, v in DECLARED.items() if k != "tau"}, "tau", "A"),
    }
    for name, (cfg, declared, field, parse) in cases.items():
        rc, lines, err, wire = _needle(tmp_path / name, "navigator.recover2", cfg, crossing_at(0.3312), declared=declared,
                                       patience=0.0)
        assert rc == 2 and lines == [], (name, rc, lines, err)
        assert err.strip() == f"RefusedToStart field={field} parse={parse}", (name, err)
        assert "measure" not in wire.ops, (name, wire.ops)
    path = tmp_path / "alone.toml"
    path.write_text(_toml(NEEDLE_V1))
    res = subprocess.run([sys.executable, "-m", "navigator.recover2", "--needle", str(path), "--port", str(_free_port())],
                         cwd=str(ROOT), stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=60)
    assert res.returncode == 1 and res.stdout == "", (res.returncode, res.stdout, res.stderr)
    assert res.stderr.startswith("Unreachable") and "Traceback" not in res.stderr, res.stderr


# ---- part 2: the real orchestrator on a tiny lattice ----------------------------------------------------------------------
def _write(tmp, needle, score_text, at=None):
    port = _free_port()
    at_dir = tmp / "plugins_at"; at_dir.mkdir(parents=True, exist_ok=True)
    env_path, at_path = tmp / "environment.toml", at_dir / "at-blind.toml"
    env_path.write_text(f'system = "at"\nport = {port}\nrun_dir_root = "{tmp / "runs"}"\n')
    at_path.write_text(_toml(AT_GOOD if at is None else at))
    (at_dir / "tau-v0.toml").write_text("value = 1.0\n")
    needle_path, score = tmp / "needle.toml", tmp / "score.toml"
    needle_path.write_text(_toml(needle))
    score.write_text(score_text)
    return ["--env", str(env_path), "--at", str(at_path), "--needle", str(needle_path), "--score", str(score)]


def _orchestrate(tmp, module, needle, score_text, **kw):
    tmp.mkdir(parents=True, exist_ok=True)
    res = subprocess.run([sys.executable, "-m", module] + _write(tmp, needle, score_text, **kw), cwd=str(ROOT),
                         stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=600)
    dirs = sorted(p for p in (tmp / "runs").glob("*") if p.is_dir()) if (tmp / "runs").exists() else []
    return res, dirs


def _scored(tmp, plan="zz-declared", a="1.0", w_max="1.0", **kw):
    res, dirs = _orchestrate(tmp, "environment.run_blind2", NEEDLE_V1, f'a = {a}\nw_max = {w_max}\nplan = "{plan}"\n', **kw)
    assert res.returncode == 0, (res.returncode, res.stderr)
    assert len(dirs) == 1, dirs
    return dirs[0]


def _oracle_cell(kind, bracket, K_c, searched, a, w_max):
    side = ("below-range", "inside", "above-range")[(K_c >= searched[0]) + (K_c > searched[1])]
    if kind == "Located":
        contains, width = bracket[0] - a <= K_c <= bracket[1] + a, bracket[1] - bracket[0]
        return side, contains, width, width <= w_max, "HIT" if contains and width <= w_max else "MISS"
    cell = {"PAST-LO": "LEAN-TRUE" if side == "below-range" else "LEAN-FALSE", "PAST-HI": "LEAN-TRUE" if side == "above-range" else "LEAN-FALSE",
            "UNDECIDED": "NO-CALL", "REFUSE": "REFUSED"}[kind]
    return side, None, None, None, cell


def test_c09_the_orchestrator_writes_the_stream_the_score_and_the_fold(tmp_path):
    from needlestream import read as NS
    from needleview import report as V1
    run = _scored(tmp_path / "v1")
    names = sorted(p.name for p in run.iterdir())
    assert {"report.jsonl", "score.json", "verdict.json", "edge.json", "perf.json", "config.json"} <= set(names), names
    stream = NS.read((run / "report.jsonl").read_text())
    assert isinstance(stream, NS.Stream) and stream.schema == 2 and stream.outcome is not NS.PENDING, stream
    assert len(stream.steps) == N_STEPS and all(x.evaluated for x in stream.steps)
    assert [e["op"] for e in json.loads((run / "perf.json").read_text())] == ["declare"] + ["measure"] * N_STEPS
    verdict, score = json.loads((run / "verdict.json").read_text()), json.loads((run / "score.json").read_text())
    K_c = json.loads((run / "edge.json").read_text())["K_c"]
    assert tuple(sorted(verdict)) == tuple(sorted(REPORT_KEYS + NINE)), sorted(verdict)
    assert {k: verdict[k] for k in REPORT_KEYS} == NS.fold_v1(stream), "verdict.json is not the fold of report.jsonl"
    assert tuple(sorted(score)) == tuple(sorted(NINE + ("searched", "truth_side"))), sorted(score)
    assert {k: verdict[k] for k in NINE} == {k: score[k] for k in NINE}
    assert score["plan"] == "zz-declared", "the plan stamp is the score file's declared value"
    assert score["truth_K_c"] == K_c and score["searched"] == list(BRACKET) and score["run_id"] == run.name
    o = stream.outcome
    side, contains, width, narrow_enough, cell = _oracle_cell(o.kind, o.bracket, K_c, BRACKET, 1.0, 1.0)
    assert (score["truth_side"], score["contains"], score["width"], score["narrow_enough"], score["cell"]) == \
        (side, contains, width, narrow_enough, cell), (score, o)
    read1 = V1.parse("", (run / "verdict.json").read_text(), True)
    if o.kind in ("Located", "REFUSE"):
        assert isinstance(read1, V1.Run), "a schema-1 viewer must read this verdict.json unchanged"
    else:
        assert isinstance(read1, V1.Unreadable) and o.kind in read1.why, "a schema-1 viewer refuses the kind by name"
    # the same world under the frozen v0 orchestrator: the same lattice, the same seed, the same numbers
    res, dirs = _orchestrate(tmp_path / "v0", "environment.run_blind", NEEDLE_V0, "a = 1.0\nw_max = 1.0\n")
    assert res.returncode == 0 and len(dirs) == 1, (res.returncode, res.stderr)
    v0 = json.loads((dirs[0] / "verdict.json").read_text())
    assert v0["truth_K_c"] == K_c and v0["plan"] == "1525"
    assert json.dumps([x.scan for x in stream.steps], sort_keys=True) == json.dumps(v0["rounds"], sort_keys=True), "a step's numbers differ from v0's round"
    if o.kind == "Located":
        assert json.dumps({k: verdict[k] for k in REPORT_KEYS}, sort_keys=True) == \
            json.dumps({k: v0[k] for k in REPORT_KEYS}, sort_keys=True), "a Located run must be v0's report exactly"


def test_c10_the_score_table_is_total(tmp_path):
    from environment import run_blind2 as RB2
    from environment import blind_config as BC
    assert RB2.SIDES == ("below-range", "inside", "above-range")
    for K_c, want in ((0.1, "below-range"), (0.25, "inside"), (0.3, "inside"), (0.45, "inside"), (0.4500001, "above-range")):
        assert RB2.truth_side(K_c, list(BRACKET)) == want, (K_c, want)
    sc = BC.ScoreConfig(0.003, 0.02)
    for kind in ("Located", "PAST-LO", "PAST-HI", "UNDECIDED", "REFUSE"):
        for K_c in (0.1, 0.3, 0.6):
            for bracket in ([0.29, 0.305], [0.29, 0.4], [0.31, 0.32]):
                side = RB2.truth_side(K_c, list(BRACKET))
                got = RB2.score2(kind, bracket if kind == "Located" else None, side, K_c, sc)
                assert tuple(got) == _oracle_cell(kind, bracket, K_c, BRACKET, 0.003, 0.02)[1:], (kind, K_c, bracket, got)
    cells = {(k, s): RB2.score2(k, None, s, 0.3, sc)[3] for k in ("PAST-LO", "PAST-HI") for s in RB2.SIDES}
    assert cells == {("PAST-LO", "below-range"): "LEAN-TRUE", ("PAST-LO", "inside"): "LEAN-FALSE", ("PAST-LO", "above-range"): "LEAN-FALSE",
                     ("PAST-HI", "below-range"): "LEAN-FALSE", ("PAST-HI", "inside"): "LEAN-FALSE", ("PAST-HI", "above-range"): "LEAN-TRUE"}, cells
    assert {RB2.score2("UNDECIDED", None, s, 0.3, sc)[3] for s in RB2.SIDES} == {"NO-CALL"}, "no call is its own cell"
    assert {RB2.score2("REFUSE", None, s, 0.3, sc)[3] for s in RB2.SIDES} == {"REFUSED"}
    assert {RB2.score2("Located", b, "inside", 0.3, sc)[3] for b in ([0.29, 0.305], [0.29, 0.4], [0.31, 0.32])} == {"HIT", "MISS"}, "HIT and MISS are Located cells only"
    try:
        RB2.score2("Elsewhere", None, "inside", 0.3, sc)
    except KeyError:
        pass
    else:
        raise AssertionError("an outcome kind outside the alphabet has a cell")
    good = RB2.parse_score2({"a": 0.003, "w_max": 0.02, "plan": "x"})
    assert good == (sc, "x"), good
    from navigator import reader as R
    for bad in ({"a": 0.003, "w_max": 0.02}, {"a": 0.003, "w_max": 0.02, "plan": 1533}, {"a": 0.003, "w_max": 0.02, "plan": "x", "z": 1},
                {"a": -1.0, "w_max": 0.02, "plan": "x"}, None):
        assert isinstance(RB2.parse_score2(bad), R.Malformed), bad


def test_c11_refusals_of_the_orchestrator(tmp_path):
    run = _scored(tmp_path / "floor", at=dict(AT_GOOD, k="5"))
    verdict = json.loads((run / "verdict.json").read_text())
    assert verdict["kind"] == "REFUSE" and verdict["reason"] == "floor" and verdict["rounds"] == [] and verdict["cell"] == "REFUSED"
    assert len((run / "report.jsonl").read_text().splitlines()) == 2
    cases = {"score_without_plan": (NEEDLE_V1, "a = 1.0\nw_max = 1.0\n", "plan"),
             "v0_needle_config": (NEEDLE_V0, 'a = 1.0\nw_max = 1.0\nplan = "x"\n', "needle_structure"),
             "bracket_outside_knobs": (dict(NEEDLE_V1, bracket="[0.10, 0.45]"), 'a = 1.0\nw_max = 1.0\nplan = "x"\n', "bracket")}
    for name, (needle, score_text, field) in cases.items():
        res, dirs = _orchestrate(tmp_path / name, "environment.run_blind2", needle, score_text)
        assert res.returncode == 2 and len(dirs) == 1, (name, res.returncode, res.stderr)
        refused = json.loads((dirs[0] / "refused.json").read_text())
        assert refused["kind"] == "RefusedToStart" and refused["field"] == field, (name, refused)
        left = sorted(p.name for p in dirs[0].iterdir())
        assert not {"verdict.json", "score.json", "report.jsonl"} & set(left), (name, left)


def test_c12_the_needle_cannot_reach_the_truth_and_nothing_frozen_moved():
    banned_strings = ("where", "edge", "edge.json", "vendor", "plugins", "system-instantiated", "at-blind", "lattice_at")
    for rel in ("navigator/recover2.py", "navigator/steer.py", "navigator/report2.py"):
        tree = ast.parse((ROOT / rel).read_text())
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for a in node.names:
                    assert a.name.split(".")[0] in ALLOWED_IMPORTS, (rel, a.name)
            if isinstance(node, ast.ImportFrom):
                assert node.level == 0 and (node.module or "").split(".")[0] in ALLOWED_IMPORTS, (rel, node.module)
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                assert not any(b == node.value or (b != "where" and b in node.value) for b in banned_strings), (rel, node.value)
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                assert node.func.id not in ("__import__", "exec", "eval"), (rel, node.func.id)
    tree = ast.parse((ROOT / "environment" / "run_blind2.py").read_text())
    stamps = [n.value for n in ast.walk(tree) if isinstance(n, ast.Constant) and isinstance(n.value, str)
              and re.fullmatch(r"\d{3,}", n.value)]
    assert not stamps, f"a plan number is a literal in the orchestrator: {stamps}"
    for rel, want in FROZEN.items():
        assert hashlib.sha256((ROOT / rel).read_bytes()).hexdigest() == want, f"{rel} was changed"
    v0 = tomllib.loads((ROOT / "navigator" / "recover.toml").read_text())
    v1 = tomllib.loads((ROOT / "navigator" / "recover2.toml").read_text())
    assert v1 == dict(v0, needle_structure="recover-adaptive-v1"), "the v1 needle's settings are v0's, but for its name"
    s0 = tomllib.loads((ROOT / "environment" / "score-1525.toml").read_text())
    s1 = tomllib.loads((ROOT / "environment" / "score-1533.toml").read_text())
    assert s1 == dict(s0, plan="1533"), s1
    assert math.isfinite(s1["a"])


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
