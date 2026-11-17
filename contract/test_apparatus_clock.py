"""Plan 1565 — the free-running apparatus: the world's clock and the server's time ledger (contract/SCHEMA-1565.md). Launches the
REAL apparatus server and drives it over a raw socket, with the harness of contract/test_apparatus_wire.py. FROZEN: the Generator
makes this green; it does not edit this file.

What it pins:
  c01  the clock table is strict: every malformed clock is refused before the port binds, on the declared field, and the clock is
       checked after every older key (a world bad in two places is refused on the older key);
  c02  paused is the default and changes nothing: an absent clock, kind "paused" and kind "charged" with per_turn 0 give the same
       bytes on the wire, the same edge.json and the same truth.json, and every turn is charged 0 free sweeps;
  c03  a charged world RUNS: charged c equals, bit for bit, a paused world in which every line is preceded by a read of exactly c
       sweeps (n_eq c-40, S 40, skip 1), the inserted readings dropped. A world that charges but never advances fails here;
  c04  the index is the sum of the clock and the calls: every reply's index, every truth row, and turns.json add up exactly,
       one turn per line received, malformed and refused lines included;
  c05  the idle needle: a client that only declares sees the index climb by c per line, and the world drifts under it
       (truth K_c at the read moves by the declared law); paused, the same client sees index 0;
  c06  the horizon is where the world ends: the free run stops at the horizon exactly and never passes it;
  c07  charged is deterministic: replies are byte-identical whether the client answers at once or sleeps between lines;
  c08  wall steps on real time: the index is floor(sps * the summed gaps); a gap is the time since the previous reply, so the
       gaps sum to no more than the client's own elapsed time and a slow call does not bill its own time;
  c09  turns.json: the exact key set, one row per line, the clock echoed, and perf.json unchanged in shape;
  c10  world_clock.py is a total table: three kinds, `owed` per kind, `turn` bounded by the room left;
  c11  the files this plan must not edit are byte-identical to its base.

RED at base: environment/world_clock.py does not exist and the server writes no turns.json.
Run from the repo root:  python contract/test_apparatus_clock.py   (or pytest)
"""
import hashlib
import importlib.util
import json
import math
import random
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location("_tw1545", ROOT / "contract" / "test_apparatus_wire.py")
TW = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(TW)
WORLD, RQ = TW.WORLD, TW.RQ

TURN_KEYS = {"turn", "op", "gap_s", "free", "free_s", "sweeps", "wall_s", "cpu_s", "index"}
TURNS_KEYS = {"time", "wire", "world_clock", "turns"}
LINES = [{"op": "declare"}, *TW.SEQUENCE, "not json", {"op": "move", "d": [1]}, {"op": "read", "n_eq": 3, "S": 40, "skip": 1, "x": 1},
         {"op": "nudge", "d": [5000], **RQ}, {"op": "read", **RQ}]
C = 50   # the charge of c03 - c07: 10 settle + 40 samples of one sweep is a read of exactly C sweeps
FROZEN = {  # sha256 at plan 1565's base (compass-main 4df8a87); plan 1565 edits none of these
    "environment/apparatus_wire.py": "6a003c3ec34f212d8033d605fd18b6cbb49b993c36ca70c37755e2869760c074",
    "environment/dial.py": "71f5d17ee7d596c1178b50044045822600ed202c71cb3e9d36ddb2db253132b4",
    "system-instantiated/plugins/at/apparatus.py": "7fe53ccb58e5760ac637043063bb1bac0b363dd312b46bb02f2aa4d0676ef6b4",
}


def _send(conn, line):
    return conn.raw(line if isinstance(line, str) else json.dumps(line))


def _run(tmp, world, lines, sleeps=None, insert=None, stamp=None):
    """-> (raw replies, edge, truth, turns, perf). `insert`: a line sent (its reply dropped) before every line. `stamp` (a dict)
    receives "elapsed": the client's seconds from its connection to the last reply."""
    proc, conn, run_dir = TW._server(tmp, world)
    out = []
    t0 = time.monotonic()
    try:
        for j, line in enumerate(lines):
            if sleeps:
                time.sleep(sleeps[j])
            if insert is not None:
                _send(conn, insert)
            out.append(_send(conn, line))
        if stamp is not None:
            stamp["elapsed"] = time.monotonic() - t0
    finally:
        TW._stop(proc, conn)
    rd = lambda n: json.loads((run_dir / n).read_text()) if (run_dir / n).exists() else None
    return out, rd("edge.json"), rd("truth.json"), rd("turns.json"), rd("perf.json")


def _refused(tmp, world, field):
    port = TW._free_port()
    env_path, at_path = TW._write_cfgs(tmp, port, world)
    run_dir = tmp / "run"
    proc = TW._popen("environment.apparatus_server", env_path, at_path, run_dir)
    _, err = proc.communicate(timeout=120)
    assert proc.returncode == 2, (field, proc.returncode, err[-300:])
    assert f"RefusedToStart field={field} parse=B" in err, (field, err[-300:])
    assert not run_dir.exists(), (field, "the run directory was created")


# ---------------------------------------------------------------- tests
def test_c01_the_clock_table_is_strict(tmp):
    cases = [
        ("charged", "world_clock"), ([1], "world_clock"),
        ({}, "kind"), ({"kind": "frozen"}, "kind"), ({"kind": 3}, "kind"), ({"kind": "Charged", "per_turn": 1}, "kind"),
        ({"kind": "paused", "per_turn": 0}, "per_turn"), ({"kind": "charged", "per_turn": 5, "rate": 1}, "rate"),
        ({"kind": "charged", "per_turn": 5, "a": 1, "b": 2}, "a"),
        ({"kind": "charged"}, "per_turn"), ({"kind": "charged", "per_turn": -1}, "per_turn"),
        ({"kind": "charged", "per_turn": 2.0}, "per_turn"), ({"kind": "charged", "per_turn": True}, "per_turn"),
        ({"kind": "wall"}, "sweeps_per_second"), ({"kind": "wall", "sweeps_per_second": 0.0}, "sweeps_per_second"),
        ({"kind": "wall", "sweeps_per_second": 500}, "sweeps_per_second"),
        ({"kind": "wall", "sweeps_per_second": -2.0}, "sweeps_per_second"),
        ({"kind": "wall", "sweeps_per_second": 2.0, "per_turn": 1}, "per_turn"),
        ({"kind": "wall", "sweeps_per_second": float("inf")}, "sweeps_per_second"),
        ({"kind": "wall", "sweeps_per_second": float("nan")}, "sweeps_per_second"),
        ({"kind": "frozen", "rate": 1}, "kind"),                  # the kind before an unknown key
        ({"kind": "charged", "rate": 1}, "rate"),                 # an unknown key before a missing field
    ]
    for j, (clock, field) in enumerate(cases):
        _refused(tmp / f"r{j}", {**WORLD, "world_clock": clock}, field)
    # the clock is checked last: a world bad in an older key and in the clock is refused on the older key
    _refused(tmp / "o1", {**WORLD, "lag": -1, "world_clock": {"kind": "frozen"}}, "lag")
    _refused(tmp / "o2", {**WORLD, "drift": {"target": "L4", "law": "linear", "rate": 1.0}, "world_clock": {"kind": "frozen"}}, "drift")
    _refused(tmp / "o3", {**WORLD, "zzz": 1, "world_clock": {"kind": "frozen"}}, "zzz")
    _refused(tmp / "o4", {**WORLD, "cloak": {"kind": "paused"}}, "cloak")


def test_c02_paused_is_the_default_and_changes_nothing(tmp):
    runs = [_run(tmp / n, w, LINES) for n, w in (("absent", WORLD), ("paused", {**WORLD, "world_clock": {"kind": "paused"}}),
                                                 ("zero", {**WORLD, "world_clock": {"kind": "charged", "per_turn": 0}}))]
    for r in runs[1:]:
        assert r[0] == runs[0][0], "the wire differs from the absent clock"
        assert r[1] == runs[0][1] and r[2] == runs[0][2], "edge.json or truth.json differs from the absent clock"
    for r in runs:
        assert [t["free"] for t in r[3]["turns"]] == [0] * len(LINES), "a paused world ran free sweeps"
    assert runs[0][3]["world_clock"] == {"kind": "paused"} and runs[2][3]["world_clock"] == {"kind": "charged", "per_turn": 0}
    assert json.loads(runs[0][0][0])["index"] == 0


def test_c03_a_charged_world_runs(tmp):
    pad = {"op": "read", "n_eq": C - 40, "S": 40, "skip": 1}
    got = _run(tmp / "charged", {**WORLD, "world_clock": {"kind": "charged", "per_turn": C}}, LINES)
    want = _run(tmp / "padded", WORLD, LINES, insert=pad)
    assert got[0] == want[0], "a charged world is not a paused world that ran C sweeps before every line"
    # the inserted reads are exactly every other truth row of the padded run, starting with the first
    kept, it = [], iter(want[2]["rows"])
    for line, reply in zip(LINES, want[0]):
        pad_row = next(it)
        assert pad_row["op"] == "read" and pad_row["points"][0]["window"][1] - pad_row["points"][0]["sampling"] == 40, "a lost pad"
        if json.loads(reply)["op"] == "reading":
            kept.append(next(it))
    strip = lambda rs: [{k: v for k, v in r.items() if k != "call"} for r in rs]
    assert strip(got[2]["rows"]) == strip(kept), "the truth of a charged world is not the truth of the padded world"
    assert [r["call"] for r in got[2]["rows"]] == list(range(1, len(kept) + 1))


def test_c04_the_index_is_the_sum_of_the_clock_and_the_calls(tmp):
    out, edge, truth, turns, _ = _run(tmp, {**WORLD, "world_clock": {"kind": "charged", "per_turn": C}}, LINES)
    rows = turns["turns"]
    assert len(rows) == len(LINES), "not one turn per line received"
    index = 0
    for j, (reply, t) in enumerate(zip(out, rows)):
        r, m = json.loads(reply), LINES[j]
        cost = len(r["pos"]) * (m["n_eq"] + m["S"] * m["skip"]) if r["op"] == "reading" else 0
        index += C + cost
        assert r["index"] == index == t["index"], (j, r["index"], index, t["index"])
        assert t["turn"] == j + 1 and t["free"] == C and t["sweeps"] == cost, (j, t)
    assert sum(t["free"] + t["sweeps"] for t in rows) == rows[-1]["index"]
    served = [json.loads(x)["index"] for x in out if json.loads(x)["op"] == "reading"]
    assert [r["index"] for r in truth["rows"]] == served, "the truth rows are not at the served indices"


def test_c05_the_idle_needle(tmp):
    n = 40
    lines = [{"op": "declare"}] * n + [{"op": "read", **RQ}]
    out, edge, truth, _, _ = _run(tmp / "charged", {**WORLD, "world_clock": {"kind": "charged", "per_turn": C}}, lines)
    assert [json.loads(x)["index"] for x in out[:n]] == [C * (j + 1) for j in range(n)], "the idle needle's index did not climb by C"
    p = truth["rows"][0]["points"][0]
    assert p["window"][0] == C * (n + 1) + RQ["n_eq"] + 1, p["window"]
    rate = WORLD["drift"]["rate"]
    shift = TW._vendor()[0].self_dual_K(0.14 + rate * p["window"][0])
    assert abs(p["K_c"][0] - shift) < 1e-12 and abs(p["K_c"][0] - edge["K_c"]) > 1e-6, "the world did not drift under the idle needle"
    out0, _, truth0, _, _ = _run(tmp / "paused", WORLD, lines)
    assert [json.loads(x)["index"] for x in out0[:n]] == [0] * n, "a paused world moved under the idle needle"


def test_c06_the_horizon_is_where_the_world_ends(tmp):
    h = 7 * C + 13
    out, _, _, turns, _ = _run(tmp, {**WORLD, "horizon": h, "world_clock": {"kind": "charged", "per_turn": C}},
                               [{"op": "declare"}] * 10 + [{"op": "read", "n_eq": 0, "S": 1, "skip": 1}])
    idx = [json.loads(x)["index"] for x in out]
    assert idx == [min(C * (j + 1), h) for j in range(10)] + [h], idx
    assert json.loads(out[-1])["op"] == "nev", "a call past the horizon was served"
    assert sum(t["free"] for t in turns["turns"]) == h and max(t["index"] for t in turns["turns"]) == h


def test_c07_charged_is_deterministic(tmp):
    w = {**WORLD, "world_clock": {"kind": "charged", "per_turn": C}}
    rng = random.Random(5)
    a = _run(tmp / "fast", w, LINES)
    b = _run(tmp / "slow", w, LINES, sleeps=[rng.uniform(0.0, 0.25) for _ in LINES])
    assert a[0] == b[0] and a[2] == b[2], "a charged world depends on how long the client took"
    assert [t["free"] for t in a[3]["turns"]] == [t["free"] for t in b[3]["turns"]]
    assert sum(t["gap_s"] for t in b[3]["turns"]) > sum(t["gap_s"] for t in a[3]["turns"]) + 0.5, "gap_s does not measure the client"


def test_c08_wall_steps_on_real_time(tmp):
    sps, nap = 400.0, 0.3
    big = {"op": "read", "n_eq": 3000, "S": 40, "skip": 1}   # a call that takes real time on the server
    lines, sleeps, stamp = [{"op": "declare"}] * 6 + [big, {"op": "declare"}], [nap] * 6 + [0, 0], {}
    out, _, _, turns, _ = _run(tmp, {**WORLD, "world_clock": {"kind": "wall", "sweeps_per_second": sps}}, lines, sleeps=sleeps, stamp=stamp)
    idx, gaps = [json.loads(x)["index"] for x in out], [t["gap_s"] for t in turns["turns"]]
    for j, i in enumerate(idx[:6]):
        assert i == math.floor(sps * sum(gaps[:j + 1])), (j, i)            # the wall law, exactly, on the reported gaps
    assert sum(gaps[:6]) >= 5 * nap, gaps                                    # the client's naps are in the gaps
    assert sum(gaps) <= stamp["elapsed"] + 0.05, (sum(gaps), stamp)         # each gap is new time: since the previous reply
    assert gaps[7] < turns["turns"][6]["wall_s"], (gaps[7], turns["turns"][6])   # not since the previous line: no call bills itself


def test_c09_turns_json(tmp):
    out, _, truth, turns, perf = _run(tmp, WORLD, LINES)
    assert set(turns) == TURNS_KEYS and turns["time"] == TW.TIME_LABEL and turns["wire"] == TW.WIRE
    assert len(turns["turns"]) == len(LINES)
    for j, t in enumerate(turns["turns"]):
        assert set(t) == TURN_KEYS, sorted(t)
        assert all(isinstance(t[k], float) and t[k] >= 0 for k in ("gap_s", "free_s", "wall_s", "cpu_s")), t
        want_op = LINES[j].get("op") if isinstance(LINES[j], dict) else None
        assert t["op"] == str(want_op), (j, t["op"])
    assert set(perf) == {"time", "calls"} and [c["op"] for c in perf["calls"]] == [t["op"] for t in turns["turns"]]


def test_c10_the_clock_is_a_total_table(tmp):
    sys.path.insert(0, str(ROOT))
    from environment import world_clock as CK
    assert CK.KINDS == ("paused", "charged", "wall") and CK.ABSENT == {"kind": "paused"}
    ch, wl, pa = CK.parse_world_clock({"kind": "charged", "per_turn": 5}), CK.parse_world_clock({"kind": "wall", "sweeps_per_second": 10.0}), \
        CK.parse_world_clock({"kind": "paused"})
    assert [CK.owed(k, 3, 2.55) for k in (pa, ch, wl)] == [0, 15, 25]
    led, f = CK.turn(ch, CK.START, 9.0, 3)
    assert f == 3 and led == CK.Ledger(1, 9.0, 3)
    led, f = CK.turn(ch, led, 0.0, 0)
    assert f == 0 and led.ran == 3
    led, f = CK.turn(wl, CK.START, 0.25, 100)
    assert f == 2 and led.seconds == 0.25


def test_c11_files_this_plan_does_not_edit(tmp):
    for rel, sha in FROZEN.items():
        assert hashlib.sha256((ROOT / rel).read_bytes()).hexdigest() == sha, f"{rel} changed"


if __name__ == "__main__":
    import tempfile
    _tests = [v for k, v in sorted(globals().items()) if k.startswith("test_c")]
    _fail = 0
    for _t in _tests:
        with tempfile.TemporaryDirectory() as _d:
            try:
                _t(Path(_d)); print(f"PASS {_t.__name__}", flush=True)
            except Exception as _e:  # noqa: BLE001
                _fail += 1; print(f"FAIL {_t.__name__}: {type(_e).__name__}: {str(_e)[:400]}", flush=True)
    print(f"{len(_tests) - _fail}/{len(_tests)} passed")
    sys.exit(1 if _fail else 0)
