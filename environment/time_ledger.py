"""Plan 1565: the time ledger of one hold run (contract/SCHEMA-1565.md section 6). Post hoc and pure apart from its two file ends:
it reads report.jsonl, truth.json and turns.json (and needle-time.jsonl when present) from a run directory and writes ledger.json
there. It changes no reading, decision or random stream: it runs after the run is over.

World time: every sweep of [0, I_end) gets exactly one category from a total table, so the categories sum to the final index:
  idle      a free sweep (the world running on while the needle deliberates; none in a paused world)
  lag-wait  a settle sweep (n_eq) before the point's commanded position is in force
  relax     a settle sweep after it is in force
  scan / approach / read-lo / read-hi   a sampling sweep of an ignite grid, an approach leg, a hold pair's lower or upper probe
  walk / park   a sampling sweep of a setpoint needle's walk leg or park reading (plan 1558's phases)
The sampling category is indexed by the step's phase, and the phases are the needle's own table (navigator/holdtab.py): a phase
with no category has no row and stops the import (KeyError); every served window belongs to a step record (KeyError if not).
`in_transit` is an overlay, not a category: the sampling sweeps taken before the point's position was in force.
Wall and CPU time: the server's per turn (free run, call), the needle's per turn (think, wait) when the stopwatch ran."""
import json
import sys
from pathlib import Path

from navigator import holdtab as HT

CATEGORIES = ("idle", "lag-wait", "relax", "scan", "approach", "read-lo", "read-hi", "walk", "park")
_READING = {"ignite": ("scan",), "approach": ("approach",), "hold": ("read-lo", "read-hi"), "walk": ("walk",), "park": ("park",)}
PAYLOAD = HT.PHASE_PAYLOAD                                    # phase -> its step record's payload key: the needle's one table of phases
SAMPLE = {ph: _READING[ph] for ph in PAYLOAD}           # phase -> category by reading j; KeyError here = a phase with no category
SETTLE = ("lag-wait", "relax")      # indexed by: the position is in force


def _lines(p):
    return [json.loads(x) for x in p.read_text().splitlines() if x.strip()] if p.exists() else []


def arrival(point):
    """the first index at which the point's own position is in force over its sweeps (None: never, within the point)."""
    return next((i for i, pos in point["dial"] if pos == point["pos"]), None)


def owners(report):
    """window (tuple) -> (phase, j within the step's call order, step number)."""
    out = {}
    for r in report:
        if r.get("rec") != "step" or PAYLOAD[r["phase"]] not in r:
            continue
        for j, w in enumerate(r[PAYLOAD[r["phase"]]].get("window", [])):
            out[tuple(w)] = (r["phase"], j if r["phase"] == "hold" else 0, r["step"])
    return out


def intervals(truth, turns, report):
    """-> [(lo, hi, category, step, turn, in_transit)] tiling [0, I_end) exactly."""
    own, rows, out = owners(report), iter(truth["rows"]), []
    for t in turns["turns"]:
        call0 = t["index"] - t["sweeps"]
        points = next(rows)["points"] if t["sweeps"] else []
        first = own[tuple(points[0]["window"])][2] if points else None
        out.append((call0 - t["free"], call0, "idle", first, t["turn"], 0))     # the free run before a call is that call's step's
        start = call0
        for p in points:
            a, b = p["window"]
            phase, j, step = own[(a, b)]
            arr = arrival(p)
            arr = b if arr is None else arr
            s = p["sampling"]
            cut = min(arr, s)   # arr >= a >= start: the dial rows are the point's own sweeps
            out += [(start, cut, "lag-wait", step, t["turn"], 0), (cut, s, "relax", step, t["turn"], 0)]
            # in_transit = |[s, b) & [a, arr)|, the sampling sweeps before arrival: an interval intersection, empty when arr <= s
            out.append((s, b, SAMPLE[phase][j], step, t["turn"], len(range(s, min(arr, b)))))
            start = b
    return [x for x in out if x[1] > x[0]]


def ledger(run_dir):
    run_dir = Path(run_dir)
    report = _lines(run_dir / "report.jsonl")
    truth, turns = json.loads((run_dir / "truth.json").read_text()), json.loads((run_dir / "turns.json").read_text())
    needle = {r["turn"]: r for r in _lines(run_dir / "needle-time.jsonl") if r["turn"] is not None}
    iv = intervals(truth, turns, report)
    end = turns["turns"][-1]["index"] if turns["turns"] else 0
    sweeps = {c: 0 for c in CATEGORIES}
    for lo, hi, c, *_ in iv:
        sweeps[c] += hi - lo
    srv = {"free_s": sum(t["free_s"] for t in turns["turns"]), "call_wall_s": sum(t["wall_s"] for t in turns["turns"]),
           "call_cpu_s": sum(t["cpu_s"] for t in turns["turns"]), "gap_s": sum(t["gap_s"] for t in turns["turns"])}
    ned = {k: sum(r[k] for r in needle.values()) for k in ("think_wall_s", "think_cpu_s", "wait_wall_s", "wait_cpu_s")} if needle else None
    # per hold step: its sweeps by category, its turns' times, its step size, the age of its data at the decision
    steps = {r["step"]: r for r in report if r.get("rec") == "step"}
    per = {}
    for lo, hi, c, st, tn, tr in iv:
        per.setdefault(st, {"sweeps": {k: 0 for k in CATEGORIES}, "turns": set(), "in_transit": 0})
        per[st]["sweeps"][c] += hi - lo
        per[st]["turns"].add(tn)
        per[st]["in_transit"] += tr
    hold = []
    for st in sorted(k for k in per if k is not None and steps.get(k, {}).get("phase") == "hold"):
        r, p = steps[st], per[st]
        idle_turns = {t["turn"]: t for t in turns["turns"]}
        tt = sorted(p["turns"])
        hold.append({"step": st, "index": r["index"], "sweeps": p["sweeps"], "in_transit": p["in_transit"],
                     "ticks": r["verdict"][0]["ticks"], "moved": bool(r["verdict"][0]["ticks"]), "kind": r["verdict"][0]["kind"],
                     "age": [r["index"] - w[0] for w in r["pair"]["window"]],
                     "server_wall_s": sum(idle_turns[t]["wall_s"] + idle_turns[t]["free_s"] for t in tt),
                     "needle_think_s": sum(needle[t]["think_wall_s"] for t in tt if t in needle) if needle else None})
    # the idle sweeps before a hold step's first call belong to the turn of that call: counted above through the turn's step
    n = len(hold) or 1
    summary = {"index": end, "sweeps": sweeps, "share": {c: sweeps[c] / end if end else 0.0 for c in CATEGORIES},
               "in_transit": sum(x[5] for x in iv),
               "per_hold_cycle": {c: sum(h["sweeps"][c] for h in hold) / n for c in CATEGORIES},
               "hold_steps": len(hold), "hold_moves": sum(h["moved"] for h in hold),
               "mean_age": [sum(h["age"][k] for h in hold if len(h["age"]) > k) / max(1, sum(len(h["age"]) > k for h in hold)) for k in (0, 1)],
               "server": srv, "needle": ned,
               "slowest": sorted(({"step": h["step"], "server_wall_s": h["server_wall_s"], "needle_think_s": h["needle_think_s"]}
                                  for h in hold), key=lambda h: -(h["server_wall_s"] + (h["needle_think_s"] or 0.0)))[:5]}
    return {"summary": summary, "hold": hold}


def main(argv=None):
    run_dir = Path((sys.argv[1:] if argv is None else argv)[0])
    doc = ledger(run_dir)
    (run_dir / "ledger.json").write_text(json.dumps(doc))
    return 0


if __name__ == "__main__":
    sys.exit(main())
