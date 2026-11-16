"""Plan 1533: the three record builders of report schema 2 (contract/SCHEMA-1533.md) and the belief map. Pure: it imports only
navigator, opens nothing and prints nothing. Each dict is built in the key order the schema lists."""
from navigator import steer as T

SCHEMA = "compass-report/2"


def detectors():
    return [{"name": "A", "role": "peak", "reads": "C"}, {"name": "B", "role": "crossing", "reads": "Gs"}]


def belief(fields):
    """the declaration as received: one key per slot, `{"declared": value}` for a slot the wire declared, else the bare token."""
    return {s: {"declared": fields[s]} if s in fields else T.UNKNOWN for s in T.SLOTS}


def declared_other(fields):
    """every key of the declaration that is neither a slot nor the reply's own envelope, verbatim."""
    return {k: v for k, v in fields.items() if k not in T.SLOTS and k != "op"}


def start(needle, cfg, ops, dials, fields):
    settings = {"bracket": list(cfg.bracket), "m": cfg.m, "N": cfg.N, "n_eq": cfg.n_eq, "S": cfg.S, "skip": cfg.skip,
                "z": cfg.z, "detectors": detectors()}
    return {"rec": "start", "schema": SCHEMA, "needle": needle, "settings": settings,
            "mode": {"ops": list(ops), "feedback": T.mode_of(ops)},
            "sigma": {"offset": 0, "unit": T.SIGMA_UNIT, "measured": T.SIGMA_MEASURED},
            "dials": list(dials), "belief": belief(fields), "declared_other": declared_other(fields)}


def step(scan, verdict):
    kind, reason = verdict
    return {"rec": "step", "step": scan["round"], "phase": T.PHASES[0], "index": scan["index"], "evaluated": scan["evaluated"],
            "verdict": [{"kind": kind, "reason": reason, "dial": None, "ticks": None}], "scan": scan}


def outcome(kind, reason, located, steps):
    """only a Located outcome carries a bracket: every other kind publishes four nulls."""
    held = located if kind == T.LOCATED else {}
    return {"rec": "outcome", "kind": kind, "reason": reason, "bracket": held.get("bracket"), "A_hull": held.get("A_hull"),
            "B_hull": held.get("B_hull"), "agree": held.get("agree"), "steps": steps}
