"""Plan 1552: the scorer of a hold run and the truth overlay of its map (contract/SCHEMA-1552.md section 9). Pure: it opens nothing and
prints nothing, and the needle side never imports it. The truth comes in as the rows of truth.json; of a truth point only `window` and
`K_c` are read. A reading with no truth row raises KeyError."""
import math
from dataclasses import dataclass

from navigator import reader as R

NO_STEPS = "no-hold-steps"
LOCKS = ("HELD", "RECOVERED", "LOST", "LEFT-RANGE", "CUT-SHORT")
STATS = ("in_fraction", "mean_e", "rms_e", "max_abs_e", "rms_e_g", "accuracy")
PAYLOAD = {"ignite": "grid", "approach": "leg", "hold": "pair"}
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
