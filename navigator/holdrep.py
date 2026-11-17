"""Plan 1552: the record builders of the hold report (compass-report/2) and of its map (compass-map/1), contract/SCHEMA-1552.md
sections 5 and 7. Pure: it imports only navigator, opens nothing and prints nothing. Each dict is built in the key order the
schema lists. A reading is a dict: tick, window, values, errors, cls, settled, A, B."""
from navigator import holdtab as HT
from navigator import report2 as P
from navigator import steer as ST


def sigma(settings):
    """the start record's sigma, by shape: plan 1552's zero offset, or the setpoint with its ticks and its dead band."""
    one = {"offset": settings["sigma"], "unit": ST.SIGMA_UNIT, "measured": "pair-half-width"}
    return {HT.NEEDLE: lambda: one, HT.SETPOINT: lambda: {**one, "ticks": HT.offset(settings["sigma"], settings["g"]),
                                                          "dead_band": settings["dead_band"]}}[settings["needle_structure"]]()


def start(settings, ops, dial_name, fields):
    return {"rec": "start", "schema": P.SCHEMA, "needle": settings["needle_structure"], "settings": settings,
            "mode": {"ops": list(ops), "feedback": ST.mode_of(ops)},
            "sigma": sigma(settings),
            "dials": [dial_name], "belief": P.belief(fields), "declared_other": P.declared_other(fields)}


def verdict(kind, reason, dial, ticks):
    return [{"kind": kind, "reason": reason, "dial": dial, "ticks": ticks}]


def common(segment, rs):
    """the eight payload keys every step with a reading carries."""
    roles = sorted(rs[0]["values"])
    return {"segment": segment, "pos": [r["tick"] for r in rs], "window": [r["window"] for r in rs],
            "values": {k: [r["values"][k] for r in rs] for k in roles}, "errors": {k: [r["errors"][k] for r in rs] for k in roles},
            "settled": [r["settled"] for r in rs], "classes": [r["cls"] for r in rs],
            "kernel": {"A": [r["A"] for r in rs], "B": [r["B"] for r in rs], "R": HT.R_NOT_EVALUATED}}


def step(n, phase, index, evaluated, verdict_, payload):
    return {"rec": "step", "step": n, "phase": phase, "index": index, "evaluated": evaluated, "verdict": verdict_,
            HT.PHASE_PAYLOAD[phase]: payload}


def outcome(kind, reason, steps):
    return {"rec": "outcome", "kind": kind, "reason": reason, "bracket": None, "A_hull": None, "B_hull": None, "agree": None,
            "steps": steps}


def head(drop, dial, start_at, clock, n_eq, skip, roles, rule, m, needle=HT.NEEDLE):
    return {"rec": "head", "map": HT.MAP, "drop": drop, "needle": needle, "dial": dial, "start": start_at, "clock": clock,
            "n_eq": n_eq, "skip": skip, "roles": roles, "sign_rule": rule, "M": m}


def place(drop, seq, dial, r, call, sign):
    """one map entry for one reading served."""
    roles = sorted(r["values"])
    return {"rec": "place", "drop": drop, "seq": seq, "dial": dial["name"], "tick": r["tick"],
            "value": dial["lo"] + r["tick"] * (dial["hi"] - dial["lo"]) / dial["T"],
            "index": r["window"][1], "window": r["window"],
            "readings": {k: {"value": r["values"][k], "error": r["errors"][k]} for k in roles},
            "class": r["cls"], "settled": r["settled"], "state": HT.state(r["cls"], sign, r["settled"]), "call": call,
            "kernel": {"A": r["A"], "B": r["B"], "R": HT.R_NOT_EVALUATED}}
