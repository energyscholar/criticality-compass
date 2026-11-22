"""Plan 1561: the score of a moving crossing, and the breakpoint of a ladder (contract/SCHEMA-1561.md section 4). Pure: it opens
nothing and prints nothing, and the needle side never imports it. Every decision is a lookup in a total table; the only numbers
are measurements. Absence is a token, never a number."""
import math
from dataclasses import dataclass

from navigator import holdtab as HT

NO_STEPS, NO_MOVING, NO_RUNS = "no-hold-steps", "no-moving-steps", "no-out-runs"
_PAIR_KEYS = ("slew_max", "slew_mean", "jump_max_g", "trail_along", "trail_along_g")


def _setpoint_cycle(start):
    """plan 1558 (SCHEMA-1558 4.4): 2 r(cfg) + r(park) + the walks' strides (the worst of the centre's move m) at the approach settle."""
    cfg, side = start["settings"], start["belief"]["ordered_side"]["declared"][start["dials"][0]]
    r = lambda x: x["n_eq"] + x["S"] * cfg["skip"]
    off, g, M = HT.offset(cfg["sigma"], cfg["g"]), cfg["g"], start["declared_other"]["dials"][0]["max_nudge"]
    n = lambda d: len(HT.legs(d, M))
    w = max(n(m + HT.SAFE[side] * off - g) + n(HT.SAFE[side] * off + g) for m in (-cfg["step"], 0, cfg["step"]))
    return 2 * r(cfg) + r(cfg["park"]) + w * r(cfg["approach"])


# the needle's sweeps per hold cycle, by the needle's shape, read from the start record. A shape with no row is a KeyError: it is
# never given another row's formula.
CYCLE = {"hold-pair-v1": lambda start: 2 * (start["settings"]["n_eq"] + start["settings"]["S"] * start["settings"]["skip"]),
         "hold-setpoint-v1": _setpoint_cycle}


def cycle(start):
    """the needle's sweeps per hold cycle."""
    return CYCLE[start["needle"]](start)


def _out_runs(steps):
    """the maximal runs of OUT steps, each with the sweeps it took the centre to come back ("never" when it did not)."""
    runs, first = [], None
    for k, s in enumerate(steps):
        if s["cell"] == "OUT" and first is None:
            first = k
        elif s["cell"] != "OUT" and first is not None:
            runs.append((first, k))
            first = None
    ends = runs + ([(first, None)] if first is not None else [])
    return [{"first": steps[a]["step"], "steps": (len(steps) if b is None else b) - a,
             "sweeps": "never" if b is None else steps[b]["index"] - steps[a]["index"]} for a, b in ends]


_SIDE = {"+": lambda e: e > 0, "-": lambda e: e < 0}


def _pairs(steps):
    """the moving pairs: consecutive steps whose truth moved. (d, di, e): the move, the sweeps it took, the later error."""
    return [(b["truth_tick"] - a["truth_tick"], b["index"] - a["index"], b["e"])
            for a, b in zip(steps, steps[1:]) if b["truth_tick"] != a["truth_tick"]]


def _mean(xs):
    return sum(xs) / len(xs)


def _moving(pairs, top, g):
    slew = [abs(d) / di / top for d, di, _ in pairs]
    trail = _mean([-e * math.copysign(1.0, d) for d, _, e in pairs])
    return dict(zip(_PAIR_KEYS, (max(slew), _mean(slew), max(abs(d) for d, _, _ in pairs) / g, trail, trail / g)))


def _no_pairs(token):
    return lambda pairs, top, g: dict.fromkeys(_PAIR_KEYS, token)


def motion(score, start):
    steps, settings = score["steps"], start["settings"]
    top = settings["step"] / cycle(start)
    runs = _out_runs(steps)
    ended = [r["sweeps"] for r in runs if r["sweeps"] != "never"]
    side = _SIDE[start["belief"]["ordered_side"]["declared"][start["dials"][0]]]
    # steps? -> pairs? : the answer for each is one row
    empty = (_no_pairs(NO_STEPS), _no_pairs(NO_MOVING))[bool(steps)]
    pairs = _pairs(steps)
    stats = (_moving if bool(pairs) else empty)(pairs, top, score["g"])
    token = None if bool(steps) else NO_STEPS
    return {
        "lock": score["lock"], "outcome": score["outcome"], "hold_steps": len(steps), "top_speed": top, "out_runs": runs,
        "recovery_max": token or {False: NO_RUNS, True: (max(ended) if ended else "never")}[bool(runs)],
        "unrecovered": token or bool(runs and runs[-1]["sweeps"] == "never"),
        "ordered_share": token or sum(side(s["e"]) for s in steps) / len(steps),
        "travel": token or steps[-1]["truth_tick"] - steps[0]["truth_tick"],
        **stats,
    }


_CLASS = {"HELD": "held", "RECOVERED": "broken", "LOST": "broken", "LEFT-RANGE": "broken",
          "CUT-SHORT": "no-evidence", "REFUSED": "no-evidence", "FAILED": "no-evidence", "MISSING": "no-evidence",
          "MISMATCH": "no-evidence"}


def rung_class(lock):
    """held / broken / no-evidence; any other lock has no row (KeyError)."""
    return _CLASS[lock]


@dataclass(frozen=True)
class Break:
    kind: str
    below: str
    above: str
    detail: tuple


def _labels(rungs, pick):
    return tuple(label for label, cls in rungs if pick(cls))


def _held_after_broken(rungs):
    seen = [cls for _, cls in rungs]
    first = seen.index("broken")
    return tuple(label for k, (label, cls) in enumerate(rungs) if k > first and cls == "held")


# the shape of an all-evidence sequence, runs collapsed -> the break; a shape with no row is not monotone
_SHAPE = {
    ("held",): lambda r: Break("HOLDS-THROUGH", r[-1][0], "", ()),
    ("broken",): lambda r: Break("BROKEN-FROM-FIRST", "", r[0][0], ()),
    ("held", "broken"): lambda r: Break("BREAKS-BETWEEN", next(l for (l, c), (_, n) in zip(r, r[1:]) if c == "held" and n == "broken"),
                                        next(l for (_, c), (l, n) in zip(r, r[1:]) if c == "held" and n == "broken"), ()),
}


def _runs(classes):
    return tuple(c for k, c in enumerate(classes) if k == 0 or classes[k - 1] != c)


def breakpoint(rungs):
    """[(label, class), ...] in the ladder's order -> Break. It chooses nothing: a ladder that holds again after it broke is
    NOT-MONOTONE, and a ladder with a rung that has no evidence is INCOMPLETE."""
    rungs = list(rungs)
    blind = _labels(rungs, lambda c: c == "no-evidence")
    shape = _runs([c for _, c in rungs])
    rows = {True: lambda: Break("INCOMPLETE", "", "", blind),
            False: lambda: _SHAPE.get(shape, lambda r: Break("NOT-MONOTONE", "", "", _held_after_broken(r)))(rungs)}
    return rows[bool(blind)]()
