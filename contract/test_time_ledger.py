"""Plan 1565 — the time ledger (contract/SCHEMA-1565.md sections 3, 5, 6). Drives the REAL server and the REAL hold needle on the
small world of contract/test_needle_clock.py, then reads the run with environment/time_ledger.py. FROZEN: the Generator makes this
green; it does not edit this file.
  l01  the categories tile world time: their sweeps sum exactly to the final index, paused and charged;
  l02  each category is what it says, recounted here from the truth and the report: idle = the free sweeps; lag-wait = the settle
       sweeps before each point's position was in force, relax = the rest of the settle sweeps; scan, approach, read-lo, read-hi =
       the sampling sweeps of the ignite grid, the approach legs and the hold pairs' first and second readings; in_transit =
       sampling sweeps before arrival;
  l03  the per-step rows: one per hold step, ages from the pair's windows, idle by the step's calls; the summary's moves, mean
       ages and per-cycle idle are those rows';
  l04  run_hold writes ledger.json with the declared keys and its own stage times; it is a function of the run directory and the
       last file written, after the score (the needle's outputs are unchanged by the stopwatch: n04);
  l05  the sampling categories are indexed by the needle's own phase table (navigator/holdtab.py): every phase has a row, and a
       phase with no category stops the import with KeyError (no default row).
RED at base: environment/time_ledger.py does not exist.
Run from the repo root:  python contract/test_time_ledger.py   (or pytest)
"""
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location("_nc1565", ROOT / "contract" / "test_needle_clock.py")
NC = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(NC)
TW = NC.TW
CATEGORIES = ("idle", "lag-wait", "relax", "scan", "approach", "read-lo", "read-hi", "walk", "park")
SUMMARY_KEYS = {"index", "sweeps", "share", "in_transit", "per_hold_cycle", "hold_steps", "hold_moves", "mean_age", "server",
                "needle", "slowest"}
HOLD_KEYS = {"step", "index", "sweeps", "in_transit", "ticks", "moved", "kind", "age", "server_wall_s", "needle_think_s"}
STAGE_KEYS = {"ready_s", "needle_s", "reap_s", "finish_s", "ledger_s"}
WORLDS = {"paused": NC.WORLD, "charged": {**NC.WORLD, "world_clock": {"kind": "charged", "per_turn": 77}}}


def _ledger(tmp, world, n_eq=6):
    sys.path.insert(0, str(ROOT))
    from environment import time_ledger as TL
    report, mapb, truth, nt, turns = NC.drop(tmp, world, n_eq=n_eq, timer=True)
    run = tmp / "run"
    (run / "report.jsonl").write_bytes(report)
    (run / "needle-time.jsonl").write_text("".join(json.dumps(r) + "\n" for r in nt))
    return TL.ledger(run), NC._records(report), truth, turns


def _arrival(p):
    return next((i for i, pos in p["dial"] if pos == p["pos"]), None)


def test_l01_the_categories_tile_world_time(tmp):
    for name, w in WORLDS.items():
        led, _, truth, turns = _ledger(tmp / name, w)
        s = led["summary"]
        assert tuple(s["sweeps"]) == CATEGORIES, list(s["sweeps"])
        assert sum(s["sweeps"].values()) == s["index"] == turns["turns"][-1]["index"], (name, s["sweeps"], s["index"])
        assert abs(sum(s["share"].values()) - 1.0) < 1e-12, (name, s["sweeps"])


def test_l02_each_category_is_what_it_says(tmp):
    for name, w in WORLDS.items():
        led, recs, truth, turns = _ledger(tmp / name, w)
        s = led["summary"]["sweeps"]
        assert s["idle"] == sum(t["free"] for t in turns["turns"]), name
        holds = {tuple(x): j for r in recs if r.get("phase") == "hold" and "pair" in r for j, x in enumerate(r["pair"]["window"])}
        owner = {tuple(x): r["phase"] for r in recs if r.get("rec") == "step"
                 for key in ("grid", "leg") if "window" in r.get(key, {}) for x in r[key]["window"]}   # a refused call has none
        lagw = transit = settle = 0
        read, sample = [0, 0], {"ignite": 0, "approach": 0}
        start = 0
        rows = iter(truth["rows"])
        for t in turns["turns"]:
            if not t["sweeps"]:
                continue
            start = t["index"] - t["sweeps"]
            for p in next(rows)["points"]:
                arr = _arrival(p)
                arr = p["window"][1] if arr is None else arr
                lagw += max(0, min(arr, p["sampling"]) - start)
                settle += p["sampling"] - start
                if tuple(p["window"]) in owner:
                    sample[owner[tuple(p["window"])]] += p["window"][1] - p["sampling"]
                transit += max(0, min(arr, p["window"][1]) - p["sampling"])
                if tuple(p["window"]) in holds:
                    read[holds[tuple(p["window"])]] += p["window"][1] - p["sampling"]
                start = p["window"][1]
        assert s["lag-wait"] == lagw and led["summary"]["in_transit"] == transit, (name, s["lag-wait"], lagw, transit)
        assert [s["read-lo"], s["read-hi"]] == read and read[1] > 0, (name, s, read)
        assert s["lag-wait"] + s["relax"] == settle and [s["scan"], s["approach"]] == [sample["ignite"], sample["approach"]], \
            (name, s, settle, sample)
        assert s["scan"] > 0 and s["approach"] > 0 and s["relax"] > 0, (name, s)


def test_l03_the_per_step_rows(tmp):
    led, recs, _, turns = _ledger(tmp, WORLDS["charged"])
    hold = [r for r in recs if r.get("rec") == "step" and r["phase"] == "hold" and "pair" in r]
    assert [h["step"] for h in led["hold"]] == [r["step"] for r in hold] and len(hold) > 3
    for h, r in zip(led["hold"], hold):
        assert set(h) == HOLD_KEYS and h["age"] == [r["index"] - w[0] for w in r["pair"]["window"]], h
        assert h["moved"] == bool(r["verdict"][0]["ticks"]) and h["sweeps"]["idle"] == 77 * len(r["pair"]["window"]), h
    assert set(led["summary"]) == SUMMARY_KEYS and led["summary"]["hold_steps"] == len(hold)
    s = led["summary"]
    assert s["hold_moves"] == sum(h["moved"] for h in led["hold"]), s
    for k in (0, 1):
        ages = [h["age"][k] for h in led["hold"] if len(h["age"]) > k]
        assert abs(s["mean_age"][k] - sum(ages) / len(ages)) < 1e-9, (k, s["mean_age"])
    assert s["per_hold_cycle"]["idle"] == sum(h["sweeps"]["idle"] for h in led["hold"]) / len(led["hold"]), s["per_hold_cycle"]
    assert led["summary"]["needle"]["think_wall_s"] > 0 and led["summary"]["server"]["call_wall_s"] > 0


def test_l04_run_hold_writes_the_ledger_last(tmp):
    port = TW._free_port()
    env_path, at_path = TW._write_cfgs(tmp, port, WORLDS["charged"])
    score = ROOT / "environment" / "hold-score.toml"
    res = subprocess.run([sys.executable, "-m", "environment.run_hold", "--env", str(env_path), "--at", str(at_path), "--needle",
                          str(NC.needle_cfg(tmp, 6)), "--score", str(score)], cwd=str(ROOT), capture_output=True, text=True, timeout=900)
    assert res.returncode == 0, res.stderr[-600:]
    run = next((tmp / "runs").iterdir())
    doc = json.loads((run / "ledger.json").read_text())
    assert set(doc) == {"summary", "hold", "orchestrator"} and set(doc["orchestrator"]) == STAGE_KEYS, sorted(doc)
    sys.path.insert(0, str(ROOT))
    from environment import time_ledger as TL
    again = TL.ledger(run)
    assert again["summary"]["sweeps"] == doc["summary"]["sweeps"], "the ledger is not a function of the run directory"
    # the ledger is the last thing written: every other output is older than it
    assert all((run / n).stat().st_mtime_ns <= (run / "ledger.json").stat().st_mtime_ns
               for n in ("report.jsonl", "map.jsonl", "truth.json", "score.json", "map-truth.json", "turns.json", "needle-time.jsonl"))


def test_l05_a_phase_with_no_category_has_no_row(tmp):
    import importlib
    sys.path.insert(0, str(ROOT))
    from navigator import holdtab as HT
    from environment import time_ledger as TL
    tables = {n: getattr(HT, n) for n in ("PAYLOAD", "PHASE_PAYLOAD") if hasattr(HT, n)}   # plan 1552's, and plan 1558's once merged
    assert any(TL.PAYLOAD is t for t in tables.values()), "the ledger's phases are not the needle's table"
    assert set(TL.SAMPLE) == set(TL.PAYLOAD) and {c for v in TL.SAMPLE.values() for c in v} <= set(CATEGORIES), TL.SAMPLE
    raised = False
    try:
        for n, t in tables.items():
            setattr(HT, n, {**t, "survey": "grid"})
        try:
            importlib.reload(TL)
        except KeyError:
            raised = True
    finally:
        for n, t in tables.items():
            setattr(HT, n, t)
        importlib.reload(TL)
    assert raised, "a phase with no category was given one"


if __name__ == "__main__":
    import tempfile
    _tests = [v for k, v in sorted(globals().items()) if k.startswith("test_l")]
    _fail = 0
    for _t in _tests:
        with tempfile.TemporaryDirectory() as _d:
            try:
                _t(Path(_d)); print(f"PASS {_t.__name__}", flush=True)
            except Exception as _e:  # noqa: BLE001
                _fail += 1; print(f"FAIL {_t.__name__}: {type(_e).__name__}: {str(_e)[:400]}", flush=True)
    print(f"{len(_tests) - _fail}/{len(_tests)} passed")
    sys.exit(1 if _fail else 0)
