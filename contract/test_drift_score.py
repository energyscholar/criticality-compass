"""Plan 1561 — the score of a moving crossing, the breakpoint table and the ladder report (contract/SCHEMA-1561.md sections
4 and 5). No server: the run directories are written by the test.
FROZEN: the Generator makes this green; it does not edit this file.

What it pins:
  s01 cycle and the top speed come from the needle's own settings;
  s02 the slew, the jump and the travel of a moving crossing, exactly;
  s03 the trail along the motion is SIGNED by the crossing's own direction: behind is positive going up AND going down;
  s04 the ordered share follows the declared ordered side;
  s05 the OUT runs, the recovery time, and a run that never recovered;
  s06 tokens, never numbers: no steps, and no moving pair;
  s07 rung_class is the total table; anything else raises;
  s08 breakpoint is the total table over the class sequence, and never picks a bracket from a non-monotone ladder;
  s09 the report: every rung of a ladder is listed, a missing rung is MISSING, strays are named, a run whose own config.json
      says it was made otherwise is MISMATCH, a refused worlds file or a missing root exits 2;
  s10 purity: motion and breakpoint change nothing they are handed and give the same answer twice.
Phase 4 (the cross-plan review of 2026-11-17, findings 1 and 6):
  s11 cycle is a TABLE keyed on the needle shape (the start record's "needle"): the hold pair's row gives today's numbers, and a
      shape with no row raises KeyError, never the pair formula;
  s12 the needle SHAPE is part of "made as named": a setpoint-shape run under a ladder root is MISMATCH, a run that names no shape
      is MISMATCH, and a run whose start record names a shape with no cycle row is FAILED;
  s13 the time report: each read rung carries its run's perf.json totals (seconds, calls, per op) or a token; time never decides
      a lock, and a rung that was not read has no time.

RED until environment/drift_score.py and environment/ladder_report.py exist (s11-s13: RED at the Phase-3 tip eca848e).
Run from the repo root:  python contract/test_drift_score.py   (or pytest)
"""
import copy
import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

SETTINGS = {"g": 12, "step": 6, "n_eq": 450, "S": 500, "skip": 1}
TOP = 6 / 1900


PAIR, SETPOINT = "hold-pair-v1", "hold-setpoint-v1"


def _start(side="+", needle=PAIR, **settings):
    return {"rec": "start", "needle": needle, "settings": {**SETTINGS, **settings}, "dials": ["K"],
            "belief": {"ordered_side": {"declared": {"K": side}}}}


def _score(truth, centres, index0=10000, di=1900, lock="HELD", outcome="HORIZON", g=12):
    steps = []
    for k, (t, c) in enumerate(zip(truth, centres)):
        e = c - t
        steps.append({"step": k + 3, "index": index0 + k * di, "centre": c, "truth_tick": t, "e": e,
                      "cell": "IN" if abs(e) <= g else "OUT", "kind": "stay", "true_kind": "stay", "settled": True})
    return {"lock": lock, "outcome": outcome, "g": g, "steps": steps}


def _mods():
    from environment import drift_score
    return drift_score


def test_s01_cycle_and_top_speed():
    DS = _mods()
    assert DS.cycle(PAIR, SETTINGS) == 1900
    assert DS.cycle(PAIR, {**SETTINGS, "n_eq": 0}) == 1000
    assert DS.cycle(PAIR, {**SETTINGS, "S": 40, "skip": 3}) == 2 * (450 + 120)
    m = DS.motion(_score([600.0, 601.0], [600, 600]), _start())
    assert m["top_speed"] == TOP
    m = DS.motion(_score([600.0, 601.0], [600, 600], di=1000), _start(n_eq=0, step=4))
    assert m["top_speed"] == 4 / 1000


def test_s02_slew_jump_travel():
    DS = _mods()
    truth = [600.0, 603.0, 609.0, 609.0, 621.0]
    m = DS.motion(_score(truth, [600, 600, 606, 606, 612]), _start())
    speeds = [3 / 1900 / TOP, 6 / 1900 / TOP, 12 / 1900 / TOP]     # the still pair (609 -> 609) is not a moving pair
    assert abs(m["slew_max"] - max(speeds)) < 1e-12 and abs(m["slew_mean"] - sum(speeds) / 3) < 1e-12, m
    assert m["jump_max_g"] == 12 / 12 and m["travel"] == 21.0 and m["hold_steps"] == 5
    assert m["lock"] == "HELD" and m["outcome"] == "HORIZON"
    uneven = DS.motion({**_score([600.0, 610.0], [600, 600]), "steps": [
        {**_score([600.0], [600])["steps"][0]},
        {**_score([610.0], [600], index0=15000)["steps"][0], "step": 4}]}, _start())
    assert abs(uneven["slew_max"] - 10 / 5000 / TOP) < 1e-12, "the speed is per sweep of the index, not per step"


def test_s03_the_trail_is_signed_by_the_motion():
    DS = _mods()
    up = DS.motion(_score([600.0, 606.0, 612.0, 618.0], [600, 600, 606, 612]), _start())        # 6 behind, going up
    down = DS.motion(_score([600.0, 594.0, 588.0, 582.0], [600, 600, 594, 588]), _start())      # 6 behind, going down
    ahead = DS.motion(_score([600.0, 606.0, 612.0, 618.0], [600, 612, 618, 624]), _start())     # 6 ahead, going up
    assert up["trail_along"] == 6.0 and down["trail_along"] == 6.0, (up["trail_along"], down["trail_along"])
    assert ahead["trail_along"] == -6.0 and abs(up["trail_along_g"] - 0.5) < 1e-12
    mixed = DS.motion(_score([600.0, 606.0, 600.0], [600, 600, 606]), _start())                 # behind going up, behind going down
    assert mixed["trail_along"] == 6.0, mixed["trail_along"]
    pause = DS.motion(_score([600.0, 606.0, 606.0, 612.0], [600, 600, 606, 606]), _start())     # a still pair between two moves
    assert pause["trail_along"] == 6.0, ("the trail is over the MOVING pairs only", pause["trail_along"])


def test_s04_the_ordered_share():
    DS = _mods()
    sc = _score([600.0, 606.0, 612.0, 618.0, 618.0], [600, 610, 610, 620, 619])   # e = 0, +4, -2, +2, +1
    plus, minus = DS.motion(sc, _start("+")), DS.motion(sc, _start("-"))
    assert plus["ordered_share"] == 3 / 5 and minus["ordered_share"] == 1 / 5, (plus["ordered_share"], minus["ordered_share"])


def test_s05_out_runs_and_recovery():
    DS = _mods()
    truth = [600.0] * 9
    centres = [600, 630, 630, 600, 600, 640, 640, 640, 600]
    m = DS.motion(_score(truth, centres, lock="RECOVERED"), _start())
    assert m["out_runs"] == [{"first": 4, "steps": 2, "sweeps": 2 * 1900}, {"first": 8, "steps": 3, "sweeps": 3 * 1900}], m["out_runs"]
    assert m["recovery_max"] == 3 * 1900 and m["unrecovered"] is False
    lost = DS.motion(_score(truth[:7], centres[:7], lock="LOST"), _start())
    assert lost["out_runs"][-1] == {"first": 8, "steps": 2, "sweeps": "never"} and lost["unrecovered"] is True
    assert lost["recovery_max"] == 2 * 1900
    never = DS.motion(_score([600.0, 600.0], [640, 640], lock="LOST"), _start())
    assert never["recovery_max"] == "never" and never["unrecovered"] is True
    clean = DS.motion(_score([600.0, 600.0], [600, 600]), _start())
    assert clean["out_runs"] == [] and clean["recovery_max"] == "no-out-runs" and clean["unrecovered"] is False, "no OUT run is a token, not 0"


def test_s06_tokens_never_numbers():
    DS = _mods()
    keys = ("slew_max", "slew_mean", "jump_max_g", "trail_along", "trail_along_g")
    none = DS.motion({"lock": "LOST", "outcome": "HORIZON", "g": 12, "steps": []}, _start())
    for k in keys + ("ordered_share", "travel"):
        assert none[k] == "no-hold-steps", (k, none[k])
    assert none["hold_steps"] == 0 and none["out_runs"] == []
    assert none["recovery_max"] == none["unrecovered"] == "no-hold-steps", (none["recovery_max"], none["unrecovered"])
    still = DS.motion(_score([600.0, 600.0, 600.0], [600, 606, 600]), _start())
    for k in keys:
        assert still[k] == "no-moving-steps", (k, still[k])
    assert still["travel"] == 0.0 and still["ordered_share"] == 1 / 3
    want = {"lock", "outcome", "hold_steps", "top_speed", "out_runs", "recovery_max", "unrecovered", "ordered_share", "travel",
            "slew_max", "slew_mean", "jump_max_g", "trail_along", "trail_along_g"}
    assert set(none) == set(still) == want, set(still) ^ want


def test_s07_rung_class():
    DS = _mods()
    want = {"HELD": "held", "RECOVERED": "broken", "LOST": "broken", "LEFT-RANGE": "broken",
            "CUT-SHORT": "no-evidence", "REFUSED": "no-evidence", "FAILED": "no-evidence", "MISSING": "no-evidence",
            "MISMATCH": "no-evidence"}
    for lock, cls in want.items():
        assert DS.rung_class(lock) == cls, lock
    for other in ("held", "HORIZON", "", "UNKNOWN"):
        try:
            DS.rung_class(other)
            raise AssertionError(f"rung_class answered {other!r}")
        except KeyError:
            pass


def test_s08_breakpoint():
    DS = _mods()
    L = lambda *c: [(f"r{k}", x) for k, x in enumerate(c)]   # noqa: E731
    cases = [
        (L("held", "held", "held"), ("HOLDS-THROUGH", "r2", "", ())),
        (L("broken", "broken"), ("BROKEN-FROM-FIRST", "", "r0", ())),
        (L("held", "held", "broken", "broken"), ("BREAKS-BETWEEN", "r1", "r2", ())),
        (L("held", "broken"), ("BREAKS-BETWEEN", "r0", "r1", ())),
        (L("held", "broken", "held", "broken", "held"), ("NOT-MONOTONE", "", "", ("r2", "r4"))),
        (L("broken", "held"), ("NOT-MONOTONE", "", "", ("r1",))),
        (L("held", "no-evidence", "broken"), ("INCOMPLETE", "", "", ("r1",))),
        (L("held", "broken", "held", "no-evidence"), ("INCOMPLETE", "", "", ("r3",))),
        (L("no-evidence"), ("INCOMPLETE", "", "", ("r0",))),
        (L("held"), ("HOLDS-THROUGH", "r0", "", ())),
    ]
    for rungs, (kind, below, above, detail) in cases:
        b = DS.breakpoint(rungs)
        assert (b.kind, b.below, b.above, tuple(b.detail)) == (kind, below, above, detail), (rungs, b)


NEEDLES = {"SET": (["declare", "scan", "nudge"], 450), "MID": (["declare", "scan", "nudge"], 0), "OFF": (["declare", "scan"], 450)}


def _run(root, name, lock, truth, centres, refused=False, two=False, made=None, seed=None, drift=None, config=True,
         shape=PAIR, started=PAIR, perf=None):
    """a run directory as run_hold leaves it. `made` = the needle it was REALLY made with (default: the one its name says);
    `shape` = its config's needle_structure (None: the key is absent); `started` = its start record's "needle";
    `perf` = perf.json's text (None: no file)."""
    d = root / name / "runs" / "abc"
    d.mkdir(parents=True)
    if refused:
        (d / "refused.json").write_text("{}")
        return
    mode, run_seed = name.split("--")[2], int(name.split("--")[3][1:])
    ops, n_eq = NEEDLES[made or mode]
    at = {"seed": run_seed if seed is None else seed, "horizon": 1000, "drift": drift or {"target": "L4", "law": "none"},
          "hidden": {"L4": 0.1}, "k": 6}
    if config:
        needle = {"ops": ops, "n_eq": n_eq, "g": 12, **({} if shape is None else {"needle_structure": shape})}
        (d / "config.json").write_text(json.dumps({"at": at, "needle": needle,
                                                   "score": {"out_run": 3, "offset_K": [0.27, -0.6], "plan": 1552}}))
    (d / "score.json").write_text(json.dumps(_score(truth, centres, lock=lock)))
    (d / "report.jsonl").write_text(json.dumps(_start(needle=started)) + "\n" + json.dumps({"rec": "outcome"}) + "\n")
    if perf is not None:
        (d / "perf.json").write_text(perf)
    if two:
        (root / name / "runs" / "def").mkdir()


def test_s09_the_report():
    from environment import ladder_report as LR
    worlds = """base = "at-apparatus.toml"
[[ladder]]
name = "up"
[[ladder.rungs]]
label = "x1"
severity = 1.0
horizon = 1000
drift = {target = "L4", law = "none"}
[[ladder.rungs]]
label = "x2"
severity = 2.0
horizon = 1000
drift = {target = "L4", law = "none"}
[[ladder.rungs]]
label = "x3"
severity = 3.0
horizon = 1000
drift = {target = "L4", law = "none"}
"""
    assert LR.run_name("up", "x1", "SET", 200) == "up--x1--SET--s200"
    assert LR.parse_name("up--x1--SET--s200") == ("up", "x1", "SET", 200)
    for bad in ("up--x1--SETTLED--s200", "up--x1--SET--200", "up--x1--SET", "up--x1--SET--s2x", "a--b--c--d--e"):
        assert LR.parse_name(bad) is None, bad
    with tempfile.TemporaryDirectory() as t:
        t = Path(t)
        (t / "w.toml").write_text(worlds)
        root = t / "runs"
        root.mkdir()
        _run(root, "up--x1--SET--s200", "HELD", [600.0, 601.0], [600, 600])
        _run(root, "up--x2--SET--s200", "HELD", [600.0, 603.0], [600, 600])
        _run(root, "up--x3--SET--s200", "LOST", [600.0, 640.0], [600, 600])
        _run(root, "up--x1--MID--s200", "HELD", [600.0, 601.0], [600, 600])
        _run(root, "up--x3--MID--s200", "RECOVERED", [600.0, 640.0], [600, 640])          # x2 MID never ran
        _run(root, "up--x1--OFF--s200", "LOST", [600.0, 640.0], [600, 600], refused=True)
        _run(root, "up--x2--OFF--s200", "LOST", [600.0, 640.0], [600, 600], two=True)
        _run(root, "up--x1--SET--s201", "HELD", [600.0, 601.0], [600, 600], made="MID")       # named SET, made MID
        _run(root, "up--x2--SET--s201", "HELD", [600.0, 601.0], [600, 600], seed=202)         # named s201, made s202
        _run(root, "up--x3--SET--s201", "HELD", [600.0, 601.0], [600, 600],                   # another rung's world
             drift={"target": "L4", "law": "linear", "rate": 1e-7})
        _run(root, "up--x1--MID--s201", "HELD", [600.0, 601.0], [600, 600], config=False)     # no config.json
        _run(root, "up--x2--MID--s201", "WOBBLY", [600.0, 601.0], [600, 600])                 # a lock outside the table
        _run(root, "up--x3--MID--s201", "HELD", [600.0, 601.0], [600, 600])
        (root / "up--x9--SET--s200").mkdir()
        (root / "notes").mkdir()
        rc = subprocess.run([sys.executable, "-m", "environment.ladder_report", "--worlds", str(t / "w.toml"), "--root", str(root),
                             "--out", str(t / "out.json")], cwd=ROOT, capture_output=True, text=True)
        assert rc.returncode == 0, rc.stderr
        out = json.loads((t / "out.json").read_text())
        assert out["schema"] == "compass-drift-ladders/1" and out["base"] == "at-apparatus.toml"
        assert out["strays"] == ["notes", "up--x9--SET--s200"], out["strays"]
        cells = {(c["ladder"], c["mode"], c["seed"]): c for c in out["cells"]}
        assert list(cells) == [("up", "MID", 200), ("up", "MID", 201), ("up", "OFF", 200), ("up", "SET", 200), ("up", "SET", 201)], \
            list(cells)
        bad = cells[("up", "SET", 201)]
        assert [r["lock"] for r in bad["rungs"]] == ["MISMATCH"] * 3, "a run not made as its name says was read as evidence"
        assert [r["class"] for r in bad["rungs"]] == ["no-evidence"] * 3 and bad["break"]["kind"] == "INCOMPLETE"
        assert [r["lock"] for r in cells[("up", "MID", 201)]["rungs"]] == ["FAILED", "FAILED", "HELD"]
        assert cells[("up", "MID", 201)]["rungs"][2]["scorer"] == {"out_run": 3, "offset_K": [0.27, -0.6]}
        s = cells[("up", "SET", 200)]
        assert [r["label"] for r in s["rungs"]] == ["x1", "x2", "x3"] and [r["severity"] for r in s["rungs"]] == [1.0, 2.0, 3.0]
        assert [r["lock"] for r in s["rungs"]] == ["HELD", "HELD", "LOST"] and s["break"] == {
            "kind": "BREAKS-BETWEEN", "below": "x2", "above": "x3", "detail": []}, s["break"]
        assert s["rungs"][1]["motion"]["slew_max"] == 3 / 1900 / TOP and s["rungs"][2]["class"] == "broken"
        m = cells[("up", "MID", 200)]
        assert [r["lock"] for r in m["rungs"]] == ["HELD", "MISSING", "RECOVERED"] and m["rungs"][1]["motion"] is None
        assert m["break"] == {"kind": "INCOMPLETE", "below": "", "above": "", "detail": ["x2"]}, "a missing rung shortened the ladder"
        o = cells[("up", "OFF", 200)]
        assert [r["lock"] for r in o["rungs"]] == ["REFUSED", "FAILED", "MISSING"], [r["lock"] for r in o["rungs"]]
        (t / "bad.toml").write_text(worlds.replace("severity = 3.0", "severity = 2.0"))
        rc = subprocess.run([sys.executable, "-m", "environment.ladder_report", "--worlds", str(t / "bad.toml"), "--root", str(root),
                             "--out", str(t / "out2.json")], cwd=ROOT, capture_output=True, text=True)
        assert rc.returncode == 2 and rc.stderr.startswith("refused:") and not (t / "out2.json").exists(), (rc.returncode, rc.stderr)
        for args in (["--worlds", str(t / "w.toml"), "--root", str(t / "nowhere")], ["--worlds", str(t / "absent.toml"), "--root", str(root)]):
            rc = subprocess.run([sys.executable, "-m", "environment.ladder_report", *args, "--out", str(t / "out3.json")],
                                cwd=ROOT, capture_output=True, text=True)
            assert rc.returncode == 2 and rc.stderr.startswith("refused:") and not (t / "out3.json").exists(), (args, rc.returncode, rc.stderr)


def test_s10_purity():
    DS = _mods()
    sc, st = _score([600.0, 610.0, 640.0, 640.0], [600, 600, 606, 640], lock="RECOVERED"), _start()
    keep = (copy.deepcopy(sc), copy.deepcopy(st))
    a, b = DS.motion(sc, st), DS.motion(sc, st)
    assert a == b and (sc, st) == keep, "motion changed its input or answered twice differently"
    rungs = [("a", "held"), ("b", "broken")]
    assert DS.breakpoint(rungs) == DS.breakpoint(list(rungs)) and rungs == [("a", "held"), ("b", "broken")]


def test_s11_cycle_is_a_table_by_needle_shape():
    DS = _mods()
    assert DS.cycle(PAIR, SETTINGS) == 1900 and DS.motion(_score([600.0, 601.0], [600, 600]), _start())["top_speed"] == TOP
    # plan 1558 adds the setpoint row at its merge, and replaces this line with that row's numbers (its walk and park reading)
    for shape in (SETPOINT, "hold-other-v9", None):
        try:
            DS.cycle(shape, SETTINGS)
        except KeyError:
            pass
        else:
            raise AssertionError(f"cycle({shape!r}) answered: a shape with no row was given the pair formula")
    sc = _score([600.0, 606.0], [600, 600])
    for start in (_start(needle=SETPOINT), {k: v for k, v in _start().items() if k != "needle"}):
        try:
            DS.motion(sc, start)
        except KeyError:
            pass
        else:
            raise AssertionError(f"motion answered for needle {start.get('needle')!r}: its top speed is not the pair's")


_ONE = """base = "at-apparatus.toml"
[[ladder]]
name = "up"
[[ladder.rungs]]
label = "x1"
severity = 1.0
horizon = 1000
drift = {target = "L4", law = "none"}
[[ladder.rungs]]
label = "x2"
severity = 2.0
horizon = 1000
drift = {target = "L4", law = "none"}
"""


def _report(t, root):
    (t / "w.toml").write_text(_ONE)
    rc = subprocess.run([sys.executable, "-m", "environment.ladder_report", "--worlds", str(t / "w.toml"), "--root", str(root),
                         "--out", str(t / "out.json")], cwd=ROOT, capture_output=True, text=True)
    assert rc.returncode == 0, rc.stderr
    return {(c["ladder"], c["mode"], c["seed"]): c for c in json.loads((t / "out.json").read_text())["cells"]}


def test_s12_the_needle_shape_is_part_of_made_as_named():
    with tempfile.TemporaryDirectory() as t:
        t = Path(t)
        root = t / "runs"
        root.mkdir()
        _run(root, "up--x1--SET--s200", "HELD", [600.0, 601.0], [600, 600])                                 # control
        _run(root, "up--x2--SET--s200", "HELD", [600.0, 601.0], [600, 600], shape=SETPOINT, started=SETPOINT)  # a setpoint run
        _run(root, "up--x1--MID--s200", "HELD", [600.0, 601.0], [600, 600], shape=SETPOINT, started=SETPOINT)
        _run(root, "up--x2--MID--s200", "HELD", [600.0, 601.0], [600, 600], shape=None)                      # names no shape
        _run(root, "up--x1--OFF--s200", "LOST", [600.0, 640.0], [600, 600], shape=SETPOINT, started=SETPOINT)
        _run(root, "up--x1--SET--s201", "HELD", [600.0, 601.0], [600, 600], started=SETPOINT)  # pair config, setpoint start
        _run(root, "up--x2--SET--s201", "HELD", [600.0, 601.0], [600, 600], started="hold-other-v9")
        cells = _report(t, root)
        locks = {k: [r["lock"] for r in c["rungs"]] for k, c in cells.items()}
        assert locks[("up", "SET", 200)] == ["HELD", "MISMATCH"], "a setpoint-shape run under a ladder root was read as SET"
        assert locks[("up", "MID", 200)] == ["MISMATCH", "MISMATCH"], locks[("up", "MID", 200)]
        assert locks[("up", "OFF", 200)] == ["MISMATCH", "MISSING"], locks[("up", "OFF", 200)]
        assert locks[("up", "SET", 201)] == ["FAILED", "FAILED"], "a start record with no cycle row was scored with the pair's"
        assert cells[("up", "SET", 200)]["rungs"][0]["motion"]["top_speed"] == TOP


def test_s13_the_time_report():
    calls = [{"op": "scan", "seconds": 1.0}, {"op": "nudge", "seconds": 0.25}, {"op": "scan", "seconds": 0.5}]
    with tempfile.TemporaryDirectory() as t:
        t = Path(t)
        root = t / "runs"
        root.mkdir()
        _run(root, "up--x1--SET--s200", "HELD", [600.0, 601.0], [600, 600], perf=json.dumps({"time": "t", "calls": calls}))
        _run(root, "up--x2--SET--s200", "LOST", [600.0, 640.0], [600, 600])                                  # no perf.json
        _run(root, "up--x1--MID--s200", "HELD", [600.0, 601.0], [600, 600], perf=json.dumps({"calls": [{"op": "scan"}]}))
        _run(root, "up--x2--MID--s200", "HELD", [600.0, 601.0], [600, 600], perf="not json")
        _run(root, "up--x1--OFF--s200", "LOST", [600.0, 640.0], [600, 600], perf=json.dumps({"calls": calls}), made="SET")
        _run(root, "up--x1--SET--s201", "HELD", [600.0, 601.0], [600, 600], perf=json.dumps({"calls": []}))
        _run(root, "up--x2--SET--s201", "HELD", [600.0, 601.0], [600, 600], perf=json.dumps({"calls": [{"op": "scan", "seconds": "1"}]}))
        cells = _report(t, root)
        keys = {"label", "severity", "lock", "class", "motion", "scorer", "perf"}
        assert all(set(r) == keys for c in cells.values() for r in c["rungs"]), [sorted(r) for c in cells.values() for r in c["rungs"]]
        s = cells[("up", "SET", 200)]["rungs"]
        assert s[0]["perf"] == {"seconds": 1.75, "calls": 3, "by_op": {"nudge": {"calls": 1, "seconds": 0.25},
                                                                        "scan": {"calls": 2, "seconds": 1.5}}}, s[0]["perf"]
        assert (s[1]["lock"], s[1]["perf"]) == ("LOST", "no-perf"), s[1]
        m = cells[("up", "MID", 200)]["rungs"]
        assert [(r["lock"], r["perf"]) for r in m] == [("HELD", "unreadable-perf")] * 2, "time decided a lock, or a bad file was read"
        o = cells[("up", "OFF", 200)]["rungs"]
        assert [(r["lock"], r["perf"]) for r in o] == [("MISMATCH", None), ("MISSING", None)], "a run that was not read has a time"
        e = cells[("up", "SET", 201)]["rungs"][0]["perf"]
        assert e == {"seconds": 0.0, "calls": 0, "by_op": {}} and not isinstance(e["seconds"], bool), e
        assert cells[("up", "SET", 201)]["rungs"][1]["perf"] == "unreadable-perf", "a call whose seconds is not a number was read"


if __name__ == "__main__":
    _tests = [test_s01_cycle_and_top_speed, test_s02_slew_jump_travel, test_s03_the_trail_is_signed_by_the_motion,
              test_s04_the_ordered_share, test_s05_out_runs_and_recovery, test_s06_tokens_never_numbers, test_s07_rung_class,
              test_s08_breakpoint, test_s09_the_report, test_s10_purity,
              test_s11_cycle_is_a_table_by_needle_shape, test_s12_the_needle_shape_is_part_of_made_as_named, test_s13_the_time_report]
    _fail = 0
    for _t in _tests:
        try:
            _t(); print(f"PASS {_t.__name__}")
        except Exception as _e:  # noqa: BLE001
            _fail += 1; print(f"FAIL {_t.__name__}: {type(_e).__name__}: {str(_e)[:300]}")
    print(f"{len(_tests) - _fail}/{len(_tests)} passed")
    sys.exit(1 if _fail else 0)
