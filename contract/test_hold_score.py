"""Plan 1552 — stage 5a-N acceptance: the score of a hold run against the truth, and the orchestrator
(contract/SCHEMA-1552.md sections 9 and 10). FROZEN: the Generator makes this green; it does not edit it.

What it pins:
  s01  the score file is strict (exactly offset_K, out_run, plan);
  s02  the tracking error, the IN / OUT cells and the verdict table of a hold run, joined to the truth on the reading windows;
  s03  the lock map is total: HELD, RECOVERED, LOST, LEFT-RANGE;
  s04  FEEDBACK OFF on a moving crossing is LOST where FEEDBACK ON is HELD: the null the claim is measured against;
  s05  the truth overlay of a map is a separate table; a state that contradicts the truth is counted, never hidden;
  s06  a reading with no truth row is not scored (KeyError: the orchestrator refuses the run);
  s07  the scorer is pure, and the needle side never imports it;
  s08  end to end on the REAL apparatus (L = 9): `python -m environment.run_hold` leaves report.jsonl, map.jsonl, truth.json,
       score.json and map-truth.json; the map holds no truth; the report and the map are byte-identical on a second run;
  s09  the orchestrator refuses before it starts a server on a malformed needle or score file (exit 2, refused.json).

RED until `environment/hold_score.py` and `environment/run_hold.py` exist.
Run from the repo root:  python contract/test_hold_score.py   (or pytest)
"""
import ast
import json
import math
import socket
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import holdwire as W  # noqa: E402

ROOT = W.ROOT
BASE = 11550 + 3 * 88
DIAL = {"name": "K", "lo": 0.2, "hi": 0.5, "T": 1200, "max_nudge": 32}
K = lambda tick: 0.2 + tick * 0.3 / 1200


def _lib():
    from environment import hold_score as HS
    from needlestream import read_hold as RH
    return HS, RH


def _rows(fake, x, offset_ticks=0.0):
    """truth rows in the shape of contract/SCHEMA-1545.md section 7 for the readings a Fake served; the crossing is x(index)
    and K_c sits `offset_ticks` above it (so the scorer's offset_K must bring it back)."""
    return [{"call": n, "op": r["op"], "index": r["window"][1], "K_c": K(x(r["window"][1]) + offset_ticks), "pos": [r["tick"]], "actual": [K(r["tick"])],
             "points": [{"pos": [r["tick"]], "window": r["window"], "K_c": [K(x(r["window"][0]) + offset_ticks), K(x(r["window"][1]) + offset_ticks)],
                         "sampling": r["window"][0] - 1, "dial": [[r["window"][0] - 1, [r["tick"]]]]}]}      # the keys of SCHEMA-1553 section 5: read by no scorer here
            for n, r in enumerate(fake.readings, 1)]


def _rise(rate):
    return lambda index: 603.5 + max(0, index - BASE) * rate


def _linear(x, slope=0.004):
    """D rises through zero at the crossing, 0.004 per tick (the slope of the production lattice): with an error of 0.01 a
    reading within 5 ticks of the crossing is unresolved."""
    at = x if callable(x) else (lambda index: x)
    return lambda tick, index, n: slope * (tick - at(index))


def test_s01_the_score_file_is_strict():
    HS, RH = _lib()
    from navigator import reader as R
    good = {"offset_K": -0.0018, "out_run": 3, "plan": "1552"}
    assert HS.parse_score(good) == HS.ScoreCfg(-0.0018, 3, "1552")
    for bad in ({**good, "extra": 1}, {k: v for k, v in good.items() if k != "out_run"}, {**good, "offset_K": 0}, {**good, "out_run": -1},
                {**good, "out_run": 3.0}, {**good, "plan": ""}, {**good, "out_run": True}, [], None):
        assert isinstance(HS.parse_score(bad), R.Malformed), bad
    import tomllib
    assert HS.parse_score(tomllib.loads((ROOT / "environment" / "hold-score.toml").read_text())) == HS.ScoreCfg(-0.0018, 3, "1552")


def test_s02_tracking_cells_and_the_verdict_table(tmp):
    HS, RH = _lib()
    x = _rise(1 / 950.0)                                   # one tick per 950 sweeps: two ticks per hold step
    got = W.drop(tmp, _linear(x), horizon=BASE + 30 * 1900)
    st = RH.read(got.out)
    sc = HS.score(st, _rows(got.fake, x, offset_ticks=7.2), HS.ScoreCfg(-7.2 * 0.3 / 1200, 3, "1552"))
    hold = [r for r in got.steps if r["phase"] == "hold" and r["evaluated"]]
    n = len(hold)
    assert sc["hold_steps"] == n == len(sc["steps"]) and n >= 25, sc["hold_steps"]
    for row, r in zip(sc["steps"], hold):
        w = r["pair"]["window"]
        truth = ((x(w[0][0]) + x(w[0][1])) / 2 + (x(w[1][0]) + x(w[1][1])) / 2) / 2
        assert abs(row["truth_tick"] - truth) < 1e-6 and abs(row["e"] - (r["pair"]["centre"] - truth)) < 1e-6, (row, truth)
        assert row["cell"] == ("IN" if abs(row["e"]) <= 12 else "OUT") and row["kind"] == r["verdict"][0]["kind"], row
        assert row["true_kind"] == ("raise" if truth > r["pair"]["centre"] + 12 else "lower" if truth < r["pair"]["centre"] - 12 else "stay"), row
        assert (row["step"], row["index"], row["centre"]) == (r["step"], r["index"], r["pair"]["centre"])
    es = [row["e"] for row in sc["steps"]]
    assert abs(sc["mean_e"] - sum(es) / n) < 1e-9 and abs(sc["rms_e"] - math.sqrt(sum(e * e for e in es) / n)) < 1e-9
    assert abs(sc["max_abs_e"] - max(abs(e) for e in es)) < 1e-9 and abs(sc["rms_e_g"] - sc["rms_e"] / 12) < 1e-12
    assert sc["in_fraction"] == sum(1 for row in sc["steps"] if row["cell"] == "IN") / n == 1.0 and sc["longest_out"] == 0, sc["in_fraction"]
    assert sc["lock"] == "HELD" and sc["outcome"] == "HORIZON" and sc["feedback"] == "ON" and sc["g"] == 12 and sc["segments"] == 1, sc["lock"]
    assert sum(c for row in sc["verdict_table"].values() for c in row.values()) == n and set(sc["verdict_table"]) == {"stay"}, sc["verdict_table"]
    assert sc["accuracy"] == sum(1 for row in sc["steps"] if row["kind"] == row["true_kind"]) / n
    assert (sc["plan"], sc["out_run"]) == ("1552", 3) and abs(sc["offset_K"] + 7.2 * 0.3 / 1200) < 1e-15
    assert sc["mid_move_steps"] == 0 and all(row["settled"] is True for row in sc["steps"])
    mid = W.drop(tmp, _linear(x), {**W.CFG, "n_eq": 0}, name="mid", map_name="mid.jsonl", horizon=BASE + 30 * 1000)       # the same world, read mid-move
    ms = HS.score(RH.read(mid.out), _rows(mid.fake, x, offset_ticks=7.2), HS.ScoreCfg(-7.2 * 0.3 / 1200, 3, "1552"))
    assert ms["mid_move_steps"] == ms["hold_steps"] >= 25 and not any(row["settled"] for row in ms["steps"]), (ms["mid_move_steps"], ms["hold_steps"])
    over = HS.overlay(RH.read_map(mid.map).drops[0], _rows(mid.fake, x, offset_ticks=7.2), -7.2 * 0.3 / 1200)
    assert over["counts"]["not-resolved"] >= 2 * ms["hold_steps"] and {o["agree"] for o in over["places"] if o["state"] == "in-transit"} == {"not-resolved"}
    # a run with no hold step: every per-step statistic is the token, never a number and never null; the run is LOST
    none = W.drop(tmp, _linear(x), name="none", map_name="none.jsonl", horizon=7150 + 4399)
    ns = HS.score(RH.read(none.out), _rows(none.fake, x), HS.ScoreCfg(0.0, 3, "1552"))
    assert HS.NO_STEPS == "no-hold-steps" and (ns["hold_steps"], ns["lock"], ns["longest_out"], ns["mid_move_steps"], ns["segments"]) == (0, "LOST", 0, 0, 1), ns["lock"]
    assert [ns[k] for k in ("in_fraction", "mean_e", "rms_e", "max_abs_e", "rms_e_g", "accuracy")] == ["no-hold-steps"] * 6 and ns["steps"] == [] and ns["verdict_table"] == {}, ns
    # segments = the segments in which the needle read something: a round with no bracket is a segment, whatever follows it
    dark = lambda t, i, n: (0.3 if t > 603.5 else -0.3) if n < 5 or n > 12 else 0.0
    lost = W.drop(tmp, dark, name="dark", map_name="dark.jsonl", horizon=60000)
    ls = HS.score(RH.read(lost.out), _rows(lost.fake, lambda index: 603.5), HS.ScoreCfg(0.0, 3, "1552"))
    assert [s["verdict"][0]["kind"] for s in lost.steps if s["phase"] == "ignite"][2:5] == ["no-bracket", "no-bracket", "bracketed"], W.kinds(lost, "ignite")
    assert ls["segments"] == 4 == max(s[{"ignite": "grid", "approach": "leg", "hold": "pair"}[s["phase"]]]["segment"] for s in lost.steps if s["evaluated"]), ls["segments"]
    wrong = HS.score(st, _rows(got.fake, x, offset_ticks=7.2), HS.ScoreCfg(0.0, 3, "1552"))         # without the offset the same run is 7.2 ticks off
    assert abs((wrong["mean_e"] - sc["mean_e"]) + 7.2) < 1e-6, (wrong["mean_e"], sc["mean_e"])


def test_s03_the_lock_map_is_total():
    HS, RH = _lib()
    I, O = "IN", "OUT"
    assert HS.LOCKS == ("HELD", "RECOVERED", "LOST", "LEFT-RANGE", "CUT-SHORT")
    cases = [("HORIZON", [I] * 9, 3, "HELD"), ("HORIZON", [I, O, O, O, I], 3, "HELD"), ("HORIZON", [I, O, O, O, O, I], 3, "RECOVERED"),
             ("HORIZON", [O, I, O, I, O, I], 0, "RECOVERED"), ("HORIZON", [I, I, O], 3, "LOST"), ("HORIZON", [], 3, "LOST"),
             ("HORIZON", [O] * 5 + [I], 5, "HELD"), ("OFF-DIAL", [I] * 9, 3, "LEFT-RANGE"), ("OFF-DIAL", [], 3, "LEFT-RANGE"),
             ("HORIZON", [I], 0, "HELD"), ("WIRE-LOST", [I] * 9, 3, "CUT-SHORT"), ("WIRE-LOST", [], 3, "CUT-SHORT")]
    for outcome, cells, out_run, want in cases:
        assert HS.lock(outcome, cells, out_run) == want, (outcome, cells, out_run, HS.lock(outcome, cells, out_run))
    for unknown in ("Located", "REFUSE", "", None):          # an outcome kind that is not this needle's has no lock: not a catch-all row
        try:
            HS.lock(unknown, [I], 3)
        except KeyError:
            continue
        raise AssertionError(f"outcome kind {unknown!r} was given a lock")


def test_s04_feedback_off_is_the_null(tmp):
    HS, RH = _lib()
    x = _rise(1 / 950.0)
    cfg = HS.ScoreCfg(0.0, 3, "1552")
    on = W.drop(tmp, _linear(x), name="on", map_name="on.jsonl", horizon=BASE + 40 * 1900)
    off = W.drop(tmp, _linear(x), {**W.CFG, "ops": W.OFF_OPS}, name="off", map_name="off.jsonl", horizon=BASE + 40 * 1900)
    a, b = HS.score(RH.read(on.out), _rows(on.fake, x), cfg), HS.score(RH.read(off.out), _rows(off.fake, x), cfg)
    assert (a["lock"], a["feedback"]) == ("HELD", "ON") and (b["lock"], b["feedback"]) == ("LOST", "OFF"), (a["lock"], b["lock"])
    assert a["in_fraction"] == 1.0 and b["in_fraction"] < 0.25 and b["max_abs_e"] > 60 > 12 > a["max_abs_e"], (a["in_fraction"], b["in_fraction"], a["max_abs_e"], b["max_abs_e"])
    assert b["verdict_table"]["raise"]["raise"] >= 30 and b["accuracy"] > 0.9, b["verdict_table"]      # OFF sees it leave, and says so; it does not follow
    still = W.drop(tmp, W.sign_world(603.5), {**W.CFG, "ops": W.OFF_OPS}, name="still", map_name="still.jsonl", horizon=BASE + 10 * 1900)
    c = HS.score(RH.read(still.out), _rows(still.fake, lambda i: 603.5), cfg)
    assert c["lock"] == "HELD" and c["in_fraction"] == 1.0, c["lock"]                                   # on a crossing that stands still OFF holds too
    # nothing assumes the crossing RISES. A falling one: e is signed the other way, and the truth's call is `lower`
    fall = lambda index: 603.5 - max(0, index - BASE) / 950.0
    down = W.drop(tmp, _linear(fall), {**W.CFG, "ops": W.OFF_OPS}, name="down", map_name="down.jsonl", horizon=BASE + 40 * 1900)
    d = HS.score(RH.read(down.out), _rows(down.fake, fall), cfg)
    assert d["lock"] == "LOST" and d["mean_e"] > 12 and b["mean_e"] < -12, (d["mean_e"], b["mean_e"])
    assert d["verdict_table"]["lower"]["lower"] >= 30 and "raise" not in d["verdict_table"] and all(r["e"] > 0 for r in d["steps"][5:]), d["verdict_table"]
    # ... and one that leaves and COMES BACK: every cell is its own step's, and the lock is the cells', not the direction's
    tri = lambda index: 603.5 + min(max(0, index - BASE), max(0, BASE + 40 * 1900 - index)) / 950.0
    back = W.drop(tmp, _linear(tri), {**W.CFG, "ops": W.OFF_OPS}, name="back", map_name="back.jsonl", horizon=BASE + 40 * 1900)
    t = HS.score(RH.read(back.out), _rows(back.fake, tri), cfg)
    cells = [r["cell"] for r in t["steps"]]
    assert cells[0] == "IN" and cells[-1] == "IN" and "OUT" in cells and t["lock"] == "RECOVERED" and all(r["e"] < 1e-9 for r in t["steps"]), (cells, t["lock"])
    assert all(r["true_kind"] == ("raise" if r["e"] < -12 else "stay") for r in t["steps"]), t["verdict_table"]


def test_s05_the_truth_overlay_is_a_separate_table(tmp):
    HS, RH = _lib()
    x = lambda index: 603.5
    lie = lambda t, i, n: (-0.3 if t > 603.5 else 0.3) if (n == 0 and t == 300) or (n == 0 and t == 900) else (0.0 if t == 600 and n == 0 else (0.3 if t > 603.5 else -0.3))
    got = W.drop(tmp, W.sign_world(603.5), horizon=BASE + 3 * 1900)
    mp = RH.read_map(got.map).drops[0]
    over = HS.overlay(mp, _rows(got.fake, x), 0.0)
    assert set(over) == {"drop", "places", "counts"} and over["drop"] == "t" and len(over["places"]) == len(mp.places), sorted(over)
    for o, p in zip(over["places"], mp.places):
        assert set(o) == {"seq", "tick", "index", "truth_tick", "true_state", "state", "agree"}, sorted(o)
        assert (o["seq"], o["tick"], o["index"], o["state"]) == (p["seq"], p["tick"], p["index"], p["state"])
        assert o["true_state"] == ("ordered-side" if p["tick"] > 603.5 else "disordered-side") and o["agree"] == "resolved-true", o
    assert over["counts"] == {"resolved-true": len(mp.places), "resolved-false": 0, "not-resolved": 0}, over["counts"]
    bad = W.drop(tmp, lie, name="lie", map_name="lie.jsonl", horizon=7150)                    # one grid: two readings on the wrong side, one unresolved
    d = RH.read_map(bad.map).drops[0]
    counts = HS.overlay(d, _rows(bad.fake, x), 0.0)["counts"]
    assert counts == {"resolved-true": 10, "resolved-false": 2, "not-resolved": 1}, counts
    assert (tmp / "lie.jsonl").read_text() == bad.map and "truth" not in bad.map and "K_c" not in bad.map     # the overlay wrote nothing into the map
    flipped = HS.overlay(d, _rows(bad.fake, x, offset_ticks=400.0), 0.0)["counts"]            # the same map against another truth
    assert flipped != counts
    minus = W.drop(tmp, lambda t, i, n: -0.3 if t > 603.5 else 0.3, name="minus", map_name="minus.jsonl", horizon=7150, declared={"ordered_side": {"K": "-"}})
    m = HS.overlay(RH.read_map(minus.map).drops[0], _rows(minus.fake, x), 0.0)
    assert m["counts"]["resolved-true"] == 13 and [o["true_state"] for o in m["places"]] == ["ordered-side"] * 7 + ["disordered-side"] * 6, m["counts"]


def test_s06_a_reading_with_no_truth_row_is_not_scored(tmp):
    HS, RH = _lib()
    got = W.drop(tmp, W.sign_world(603.5), horizon=BASE + 3 * 1900)
    rows = _rows(got.fake, lambda i: 603.5)
    for cut in (rows[:-1], rows[:-2] + rows[-1:]):
        try:
            HS.score(RH.read(got.out), cut, HS.ScoreCfg(0.0, 3, "1552"))
        except KeyError:
            pass
        else:
            raise AssertionError("a hold step with no truth row was scored")
    try:
        HS.overlay(RH.read_map(got.map).drops[0], rows[1:], 0.0)
    except KeyError:
        return
    raise AssertionError("a place with no truth row was overlaid")


def test_s07_the_scorer_is_pure_and_the_needle_never_imports_it():
    tree = ast.parse((ROOT / "environment" / "hold_score.py").read_text())
    mods = {a.name.split(".")[0] for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names} | \
           {(n.module or "").split(".")[0] for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)}
    assert mods <= {"math", "dataclasses", "navigator"}, sorted(mods)
    assert not [n for n in ast.walk(tree) if isinstance(n, ast.Name) and n.id in ("open", "print", "exec", "eval")]
    for rel in ("navigator/hold.py", "navigator/holdtab.py", "navigator/holdrep.py", "needlestream/read_hold.py"):
        t = ast.parse((ROOT / rel).read_text())
        froms = {(n.module or "") for n in ast.walk(t) if isinstance(n, ast.ImportFrom)} | {a.name for n in ast.walk(t) if isinstance(n, ast.Import) for a in n.names}
        assert not [m for m in froms if m.split(".")[0] in ("environment", "cc", "numpy")], (rel, sorted(froms))
        names = {a.name for n in ast.walk(t) if isinstance(n, ast.ImportFrom) for a in n.names}
        assert not names & {"hold_score", "run_hold", "apparatus_server", "apparatus_config"}, (rel, sorted(names))


# ---------------------------------------------------------------- end to end, the real apparatus
WORLD = {"L_blocks": 3, "burn": 5, "seed": 7, "k": 2, "nlev": 2, "index_unit": "sweep", "index_kind": "sample_counter", "lag": 2,
         "horizon": 22000, "dials": [{"name": "K", "lo": 0.2, "hi": 0.5, "T": 1200, "max_nudge": 32, "start": 400}], "fixed": {},
         "hidden": {"L4": 0.14}, "drift": {"target": "L4", "law": "linear", "rate": -4.0e-7}}


def _free_port():
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    p = s.getsockname()[1]
    s.close()
    return p


def _setup(tmp, needle=None, score=None):
    at = tmp / "plugins_at"
    at.mkdir(parents=True, exist_ok=True)
    (tmp / "environment.toml").write_text(f'system = "at"\nport = {_free_port()}\nrun_dir_root = "{tmp / "runs"}"\n')
    (at / "at-apparatus.toml").write_text("".join(f"{k} = {W.toml(v)}\n" for k, v in WORLD.items()))
    (at / "tau-v0.toml").write_text("value = 3.0\n")
    W.write_cfg(tmp / "hold.toml", needle or W.CFG)
    (tmp / "hold-score.toml").write_text("".join(f"{k} = {W.toml(v)}\n" for k, v in (score or {"offset_K": -0.0018, "out_run": 3, "plan": "1552"}).items()))
    return [sys.executable, "-m", "environment.run_hold", "--env", str(tmp / "environment.toml"), "--at", str(at / "at-apparatus.toml"),
            "--needle", str(tmp / "hold.toml"), "--score", str(tmp / "hold-score.toml")]


def _run(tmp, **kw):
    """-> (res, run directory). res.early: the map was seen in the run directory before the truth of the run was written there,
    i.e. while the needle could still be running: the needle was handed a path beside the truth."""
    proc = subprocess.Popen(_setup(tmp, **kw), cwd=str(ROOT), stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    early, t0 = False, time.time()
    while proc.poll() is None and time.time() - t0 < 600:
        for d in ((tmp / "runs").iterdir() if (tmp / "runs").exists() else ()):
            early = early or ((d / "map.jsonl").exists() and not (d / "truth.json").exists())
        time.sleep(0.01)
    out, err = proc.communicate()

    class Res:
        returncode, stdout, stderr = proc.returncode, out, err
    Res.early = early
    dirs = sorted((tmp / "runs").iterdir()) if (tmp / "runs").exists() else []
    return Res, (dirs[0] if dirs else None)


def test_s08_end_to_end_on_the_real_apparatus(tmp):
    HS, RH = _lib()
    res, run = _run(tmp / "a")
    assert res.returncode == 0 and run is not None, (res.returncode, res.stderr[-600:])
    assert not res.early, "the map was in the run directory while the run was live: the needle was handed a path beside the truth"
    have = {p.name for p in run.iterdir()}
    assert {"config.json", "report.jsonl", "map.jsonl", "truth.json", "edge.json", "score.json", "map-truth.json", "server.log"} <= have, sorted(have)
    report, themap = (run / "report.jsonl").read_text(), (run / "map.jsonl").read_text()
    st, mp = RH.read(report), RH.read_map(themap)
    assert isinstance(st, RH.Stream) and isinstance(mp, RH.Map) and len(mp.drops) == 1 and RH.check(st, mp.drops[0]) is None, (st, mp)
    assert mp.drops[0].head["drop"] == run.name and st.outcome["rec"] == "outcome" and len(st.steps) >= 3, (run.name, st.outcome)
    for word in ("K_c", "truth", "actual", "hidden", "drift", "L4", "rate", "law"):
        assert word not in themap and word not in report, f"{word} is in the needle's output"
    truth = json.loads((run / "truth.json").read_text())
    windows = {tuple(p["window"]) for r in truth["rows"] for p in r["points"]}
    assert {tuple(p["window"]) for p in mp.drops[0].places} == windows, "the map's places are not the readings the apparatus served"
    score, over = json.loads((run / "score.json").read_text()), json.loads((run / "map-truth.json").read_text())
    assert score == {**HS.score(st, truth["rows"], HS.ScoreCfg(-0.0018, 3, "1552")), "run_id": run.name}, sorted(score)
    assert over == {**HS.overlay(mp.drops[0], truth["rows"], -0.0018), "run_id": run.name} and len(over["places"]) == len(mp.drops[0].places)
    assert score["lock"] in HS.LOCKS and score["outcome"] == st.outcome["kind"]
    res2, run2 = _run(tmp / "b")
    assert res2.returncode == 0 and run2.name == run.name, (res2.returncode, res2.stderr[-300:])
    assert (run2 / "report.jsonl").read_text() == report and (run2 / "map.jsonl").read_text() == themap, "a second run of the same seed differs"
    res3, run3 = _run(tmp / "a")                                # a re-run into the same run directory: the map is this drop's, not two
    assert res3.returncode == 0 and (run3 / "map.jsonl").read_text() == themap


def test_s09_the_orchestrator_refuses_before_a_server(tmp):
    for n, (field, kw) in enumerate((("sigma", {"needle": {**W.CFG, "sigma": 1}}), ("n_eq", {"needle": {k: v for k, v in W.CFG.items() if k != "n_eq"}}), ("M", {"needle": {k: v for k, v in W.CFG.items() if k != "M"}}),
                                     ("offset_K", {"score": {"offset_K": 0, "out_run": 3, "plan": "1552"}}),
                                     ("score", {"score": {"offset_K": -0.0018, "out_run": 3, "plan": "1552", "extra": 1}}))):
        res, run = _run(tmp / str(n), **kw)
        assert res.returncode == 2 and f"RefusedToStart field={field} parse=B" in res.stderr, (field, res.returncode, res.stderr[-300:])
        assert run is not None and {p.name for p in run.iterdir()} == {"refused.json"}, (field, run)
        assert json.loads((run / "refused.json").read_text()) == {"kind": "RefusedToStart", "field": field, "parse": "B"}


if __name__ == "__main__":
    import tempfile
    _plain = [test_s01_the_score_file_is_strict, test_s03_the_lock_map_is_total, test_s07_the_scorer_is_pure_and_the_needle_never_imports_it]
    _all = [test_s01_the_score_file_is_strict, test_s02_tracking_cells_and_the_verdict_table, test_s03_the_lock_map_is_total,
            test_s04_feedback_off_is_the_null, test_s05_the_truth_overlay_is_a_separate_table, test_s06_a_reading_with_no_truth_row_is_not_scored,
            test_s07_the_scorer_is_pure_and_the_needle_never_imports_it, test_s08_end_to_end_on_the_real_apparatus,
            test_s09_the_orchestrator_refuses_before_a_server]
    _fail = 0
    for _t in _all:
        with tempfile.TemporaryDirectory() as _d:
            try:
                _t() if _t in _plain else _t(Path(_d))
                print(f"PASS {_t.__name__}")
            except Exception as _e:  # noqa: BLE001
                _fail += 1
                print(f"FAIL {_t.__name__}: {type(_e).__name__}: {str(_e)[:500]}")
    print(f"{len(_all) - _fail}/{len(_all)} passed")
    sys.exit(1 if _fail else 0)
