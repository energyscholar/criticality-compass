"""Plan 1552: the scorer of a hold run and the truth overlay of its map (contract/SCHEMA-1552.md section 9). Pure: it opens nothing and
prints nothing, and the needle side never imports it. The truth comes in as the rows of truth.json; of a truth point only `window` and
`K_c` are read. A reading with no truth row raises KeyError."""
import math
from dataclasses import dataclass

from navigator import holdtab as HT
from navigator import reader as R

NO_STEPS = "no-hold-steps"
LOCKS = ("HELD", "RECOVERED", "LOST", "LEFT-RANGE", "CUT-SHORT")
STATS = ("in_fraction", "mean_e", "rms_e", "max_abs_e", "rms_e_g", "accuracy")
PAYLOAD = HT.PHASE_PAYLOAD      # plan 1558: the walk and the park carry a payload too
AGREE = {"ordered-side": None, "disordered-side": None, "critical-bracketed": "not-resolved", "in-transit": "not-resolved"}


@dataclass(frozen=True)
class ScoreCfg:
    offset_K: float
    out_run: int
    plan: str


SCORE_KEYS = (("offset_K", lambda v: type(v) is float), ("out_run", lambda v: type(v) is int and v >= 0),
              ("plan", lambda v: type(v) is str and v != ""))


def parse_score(d):
    """dict -> ScoreCfg | Malformed (field `score` for a wrong key set, else the first key outside its domain)."""
    if type(d) is not dict or set(d) != {k for k, _ in SCORE_KEYS}:
        return R.Malformed("score", "exactly offset_K, out_run, plan")
    bad = next((k for k, ok in SCORE_KEYS if not ok(d[k])), None)
    return R.Malformed(bad, "outside its domain") if bad else ScoreCfg(d["offset_K"], d["out_run"], d["plan"])


def truth_ticks(rows, dial, offset_K):
    """(first, last) window -> the true crossing in ticks: the mean of the point's two K_c, plus offset_K, in ticks."""
    return {tuple(p["window"]): (sum(p["K_c"]) / 2 + offset_K - dial["lo"]) * dial["T"] / (dial["hi"] - dial["lo"])
            for row in rows for p in row["points"]}


def _longest_out(cells):
    best = run = 0
    for c in cells:
        run = run + 1 if c == "OUT" else 0
        best = max(best, run)
    return best


def _horizon(cells, out_run):
    live = bool(cells) and cells[-1] == "IN"
    return ("LOST", ("HELD", "RECOVERED")[_longest_out(cells) > out_run])[live]


LOCK = {"OFF-DIAL": lambda cells, out_run: "LEFT-RANGE", "WIRE-LOST": lambda cells, out_run: "CUT-SHORT", "HORIZON": _horizon}


def lock(outcome_kind, cells, out_run):
    """a table over the three outcome kinds; any other kind raises KeyError."""
    return LOCK[outcome_kind](cells, out_run)


def score(stream, rows, cfg):
    dial, g = stream.dial, stream.start["settings"]["g"]
    tt = truth_ticks(rows, dial, cfg.offset_K)
    steps = []
    for r in stream.steps:
        if r["phase"] != "hold" or not r["evaluated"]:
            continue
        p = r["pair"]
        truth = sum(tt[tuple(w)] for w in p["window"]) / len(p["window"])
        c = p["centre"]
        steps.append({"step": r["step"], "index": r["index"], "centre": c, "truth_tick": truth, "e": c - truth,
                      "cell": "IN" if abs(c - truth) <= g else "OUT", "kind": r["verdict"][0]["kind"],
                      "true_kind": "raise" if truth > c + g else "lower" if truth < c - g else "stay", "settled": all(p["settled"])})
    n = len(steps)
    es = [s["e"] for s in steps]
    cells = [s["cell"] for s in steps]
    table = {}
    for s in steps:
        row = table.setdefault(s["true_kind"], {})
        row[s["kind"]] = row.get(s["kind"], 0) + 1
    rms = math.sqrt(sum(e * e for e in es) / n) if n else NO_STEPS
    stats = ({k: NO_STEPS for k in STATS} if not n else
             {"in_fraction": cells.count("IN") / n, "mean_e": sum(es) / n, "rms_e": rms, "max_abs_e": max(abs(e) for e in es),
              "rms_e_g": rms / g, "accuracy": sum(1 for s in steps if s["kind"] == s["true_kind"]) / n})
    segments = {r[PAYLOAD[r["phase"]]]["segment"] for r in stream.steps if r["evaluated"]}
    outcome = stream.outcome["kind"]
    return {"plan": cfg.plan, "offset_K": cfg.offset_K, "out_run": cfg.out_run, "g": g, "feedback": stream.start["mode"]["feedback"],
            "outcome": outcome, "lock": lock(outcome, cells, cfg.out_run), "hold_steps": n, **stats, "longest_out": _longest_out(cells),
            "mid_move_steps": sum(1 for s in steps if not s["settled"]), "segments": len(segments), "verdict_table": table, "steps": steps}


def overlay(drop, rows, offset_K):
    """per place the truth beside the state the needle typed; a table of its own, never written into the map."""
    head = drop.head
    tt = truth_ticks(rows, head["dial"], offset_K)
    ordered_above = head["sign_rule"]["ordered_side"] == "+"
    places, counts = [], {"resolved-true": 0, "resolved-false": 0, "not-resolved": 0}
    for p in drop.places:
        truth = tt[tuple(p["window"])]
        true_state = ("ordered-side", "disordered-side")[(p["tick"] > truth) != ordered_above]
        agree = AGREE[p["state"]] or ("resolved-true" if p["state"] == true_state else "resolved-false")
        counts[agree] += 1
        places.append({"seq": p["seq"], "tick": p["tick"], "index": p["index"], "truth_tick": truth, "true_state": true_state,
                       "state": p["state"], "agree": agree})
    return {"drop": head["drop"], "places": places, "counts": counts}


# ---------------------------------------------------------------- plan 1558: the setpoint score (contract/SCHEMA-1558.md section 9)
SP_STATS = ("safe_fraction", "mean_margin_g", "min_margin_g", "rms_set_e_g", "ordered_share", "ordered_depth_max", "ordered_depth_p95",
            "edge_error_p95", "band_holds")


def _p95(xs):
    xs = sorted(xs)
    return xs[min(len(xs) - 1, int(0.95 * len(xs)))]


def _held(p):
    """the tick the dial held over one point's window: its `dial` runs, each weighted by the samples of the window it covers."""
    a, b = p["window"]
    ends = [r[0] for r in p["dial"][1:]] + [b + 1]
    cover = [(max(0, min(e - 1, b) - max(r[0], a) + 1), r[1][0]) for r, e in zip(p["dial"], ends)]
    return sum(n * t for n, t in cover) / sum(n for n, _ in cover)


def actual_ticks(rows):
    """window -> the tick the dial ACTUALLY held over it (SCHEMA-1553 section 5; one dial), whatever the needle commanded."""
    return {tuple(p["window"]): _held(p) for row in rows for p in row["points"]}


def setpoint_score(stream, rows, cfg):
    st, dial = stream.start, stream.dial
    k, g = st["settings"], st["settings"]["g"]
    side = st["belief"]["ordered_side"]["declared"][dial["name"]]
    off, band = HT.offset(k["sigma"], g), k.get("dead_band", {"ticks": NO_STEPS})["ticks"]
    tt, at = truth_ticks(rows, dial, cfg.offset_K), actual_ticks(rows)
    dev = lambda w: HT.SAFE[side] * (at[tuple(w)] - tt[tuple(w)])        # the dial's displacement from the true crossing, safe side positive
    parks = [{"step": r["step"], "index": r["index"], "centre": r["park"]["centre"], "setpoint": r["park"]["setpoint"],
              "actual": at[tuple(r["park"]["window"][0])], "truth_tick": tt[tuple(r["park"]["window"][0])],
              "margin": dev(r["park"]["window"][0]), "cell": "SAFE" if dev(r["park"]["window"][0]) > 0 else "UNSAFE"}
             for r in stream.steps if r["phase"] == "park" and r["evaluated"]]
    seen = [dev(w) for r in stream.steps if r["phase"] in ("hold", "walk", "park") and r["evaluated"] for w in r[HT.PHASE_PAYLOAD[r["phase"]]]["window"]]
    ms = [q["margin"] for q in parks]
    err = [abs(m - off) for m in ms]
    n = len(parks)
    stats = ({k_: NO_STEPS for k_ in SP_STATS} if not n else
             {"safe_fraction": sum(1 for q in parks if q["cell"] == "SAFE") / n, "mean_margin_g": sum(ms) / n / g, "min_margin_g": min(ms) / g,
              "rms_set_e_g": math.sqrt(sum((m - off) ** 2 for m in ms) / n) / g, "ordered_share": sum(1 for d in seen if d < 0) / len(seen),
              "ordered_depth_max": max(max(0, -d) for d in seen), "ordered_depth_p95": _p95([max(0, -d) for d in seen]),
              "edge_error_p95": _p95(err), "band_holds": _p95(err) <= band})
    return {"plan": cfg.plan, "offset_K": cfg.offset_K, "needle": st["needle"], "sigma": k["sigma"], "sigma_ticks": off, "g": g,
            "dead_band_ticks": band, "ordered_side": side, "feedback": st["mode"]["feedback"], "outcome": stream.outcome["kind"],
            "park_steps": n, **stats, "parks": parks}
