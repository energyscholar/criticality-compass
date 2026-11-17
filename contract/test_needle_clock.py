"""Plan 1565 — the hold needle under a running clock (contract/SCHEMA-1565.md section 4). Launches the REAL apparatus server and
the REAL hold needle (navigator.hold, as a process, with its four arguments) on a small world. FROZEN: the Generator makes this
green; it does not edit this file.

The needle of plan 1552 was written for a paused world, where the last reply's index is the index of the next command. Under a
running clock the world has moved on by the time the next line arrives, so the needle must read time from the wire:
  n01  paused, the needle's report and map are byte-identical to plan 1552's needle on the same world (the two rules below are
       the old rules wherever the world is paused);
  n02  a command is dated by the reading's own window, never by the last reply: under charged time every `settled` flag the
       needle writes is the truth's (the commanded position was in force at the first sampling sweep);
  n03  a refusal is judged at the index the refusal reports (by the needle and by the reader's replay): a call refused because the clock ran the world to its horizon is
       `no-reading` (outcome HORIZON), never `wire-lost`;
  n04  the stopwatch is transparent: the needle run under environment.needle_timer writes the same report and map bytes, and the
       timer writes one row per turn plus one tail row, with the declared keys.

RED at base: the needle dates commands from the last reply and judges the horizon from a stale index (n02, n03), and
environment/needle_timer.py does not exist (n04).
Run from the repo root:  python contract/test_needle_clock.py   (or pytest)
"""
import hashlib
import importlib.util
import json
import subprocess
import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location("_tw1545", ROOT / "contract" / "test_apparatus_wire.py")
TW = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(TW)

DIAL = {"name": "K", "lo": 0.2, "hi": 0.5, "T": 1200, "max_nudge": 32, "start": 0}
WORLD = {**TW.WORLD, "L_blocks": 3, "lag": 12, "horizon": 40000, "dials": [DIAL], "drift": {"target": "L4", "law": "linear", "rate": -1.0e-6}}
TIMER_KEYS = {"turn", "think_wall_s", "think_cpu_s", "wait_wall_s", "wait_cpu_s"}
GOLDEN = {  # sha256 of plan 1552's needle (compass-main 4df8a87) on WORLD, paused, with needle_cfg(n_eq=0): outcome HORIZON, 152 steps
    "report": "66f53bfc2a53552e89fc1a6b3c7e8d4eff6da90e2977e5efe4dab4c91d10c7e9",
    "map": "7cbbfe7f871d338dbd15b0f76bf01ad6372cff46bd70d9b9d1296cf9c36e47f8"}


def needle_cfg(tmp, n_eq):
    """the shipped mid-move needle, scaled down to the small world: every count is cut, nothing else changes."""
    c = tomllib.loads((ROOT / "navigator" / "hold-mid.toml").read_text())
    c.update(n_eq=n_eq, S=40)
    c["ignite"].update(S=40, n_eq=20)
    c["approach"].update(S=40, n_eq=20)
    p = tmp / "needle.toml"
    p.write_text("".join(f"{k} = {TW._toml(v)}\n" for k, v in c.items() if not isinstance(v, dict))
                 + "".join(f"\n[{k}]\n" + "".join(f"{a} = {TW._toml(b)}\n" for a, b in v.items()) for k, v in c.items() if isinstance(v, dict)))
    return p


def drop(tmp, world, n_eq=0, timer=False):
    """one drop of the hold needle against a fresh server -> (report bytes, map bytes, truth, needle-time rows or None, turns)."""
    tmp.mkdir(parents=True, exist_ok=True)
    port = TW._free_port()
    env_path, at_path = TW._write_cfgs(tmp, port, world)
    run_dir = tmp / "run"
    proc = TW._wait_bound(TW._popen("environment.apparatus_server", env_path, at_path, run_dir), port, "apparatus server")
    head = [sys.executable, "-m", "environment.needle_timer", "--out", str(tmp / "nt.jsonl"), "--"] if timer else \
        [sys.executable, "-m", "navigator.hold"]
    try:
        res = subprocess.run(head + ["--needle", str(needle_cfg(tmp, n_eq)), "--port", str(port), "--drop", "d1", "--map",
                                     str(tmp / "map.jsonl")], cwd=str(ROOT), capture_output=True, timeout=900)
    finally:
        proc.terminate(); proc.wait(timeout=30)
    assert res.returncode == 0, res.stderr.decode()[-600:]
    rd = lambda n: json.loads((run_dir / n).read_text()) if (run_dir / n).exists() else None
    nt = [json.loads(x) for x in (tmp / "nt.jsonl").read_text().splitlines()] if timer else None
    return res.stdout, (tmp / "map.jsonl").read_bytes(), rd("truth.json"), nt, rd("turns.json")


def _records(report):
    return [json.loads(x) for x in report.decode().splitlines() if x.strip()]


def _sha(b):
    return hashlib.sha256(b).hexdigest()


def test_n01_paused_the_needle_is_plan_1552s(tmp):
    report, mapb, *_ = drop(tmp, WORLD)
    assert _records(report)[-1]["rec"] == "outcome"
    assert (_sha(report), _sha(mapb)) == (GOLDEN["report"], GOLDEN["map"]), (_sha(report), _sha(mapb))


def test_n02_settled_is_the_truth_under_charged_time(tmp):
    seen = {}
    for n_eq, c in ((0, 40), (6, 9), (12, 40), (14, 40)):   # n_eq 12 = lag: the boundary, settled exactly at the first sample
        report, _, truth, _, _ = drop(tmp / f"{n_eq}-{c}", {**WORLD, "world_clock": {"kind": "charged", "per_turn": c}}, n_eq=n_eq)
        truth_of = {}
        for row in truth["rows"]:
            for p in row["points"]:
                arr = next((i for i, pos in p["dial"] if pos == p["pos"]), None)
                truth_of[tuple(p["window"])] = arr is not None and arr <= p["sampling"]
        for r in _records(report):
            key = {"ignite": "grid", "approach": "leg", "hold": "pair"}.get(r.get("phase"))
            if r.get("rec") != "step" or key not in r or "settled" not in r[key]:
                continue
            for w, ok in zip(r[key]["window"], r[key]["settled"]):
                assert ok == truth_of[tuple(w)], (n_eq, c, r["step"], w, ok)
                seen[n_eq, c] = seen.get((n_eq, c), 0) + 1
    assert len(seen) == 4 and min(seen.values()) > 5, seen


def test_n03_a_refusal_is_judged_at_the_index_it_reports(tmp):
    for c in (1500, 2900):
        report, mp, _, _, turns = drop(tmp / str(c), {**WORLD, "horizon": 30000, "world_clock": {"kind": "charged", "per_turn": c}})
        out = _records(report)[-1]
        assert out["rec"] == "outcome" and out["kind"] == "HORIZON", (c, out)
        sys.path.insert(0, str(ROOT))
        from needlestream import read_hold as RH       # the reader replays the report: the refused step is answered at its nev index
        st, m = RH.read(report.decode()), RH.read_map(mp.decode())
        assert isinstance(st, RH.Stream) and isinstance(m, RH.Map) and RH.check(st, m.drops[0]) is None, (c, st, m)
        last = turns["turns"][-1]     # the last line was refused (no sweeps) on a turn the clock had run the world on
        assert last["sweeps"] == 0 and last["free"] > 0 and last["index"] <= 30000, (c, last)


def test_n04_the_stopwatch_is_transparent(tmp):
    w = {**WORLD, "world_clock": {"kind": "charged", "per_turn": 40}}
    a = drop(tmp / "plain", w)
    b = drop(tmp / "timed", w, timer=True)
    assert a[0] == b[0] and a[1] == b[1] and a[2] == b[2], "the stopwatch changed what the needle did"
    nt = b[3]
    assert len(nt) == len(b[4]["turns"]) + 1 and nt[-1]["turn"] is None, (len(nt), len(b[4]["turns"]))
    assert all(set(r) == TIMER_KEYS for r in nt) and [r["turn"] for r in nt[:-1]] == list(range(1, len(nt)))
    assert all(r[k] >= 0 for r in nt for k in TIMER_KEYS - {"turn"})


if __name__ == "__main__":
    import tempfile
    _tests = [v for k, v in sorted(globals().items()) if k.startswith("test_n")]
    _fail = 0
    for _t in _tests:
        with tempfile.TemporaryDirectory() as _d:
            try:
                _t(Path(_d)); print(f"PASS {_t.__name__}", flush=True)
            except Exception as _e:  # noqa: BLE001
                _fail += 1; print(f"FAIL {_t.__name__}: {type(_e).__name__}: {str(_e)[:400]}", flush=True)
    print(f"{len(_tests) - _fail}/{len(_tests)} passed")
    sys.exit(1 if _fail else 0)
