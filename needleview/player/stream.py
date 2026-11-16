"""The needle player stream: a report cut into events. Pure: nothing is opened here.

A stream is a tuple of events. Per run it holds a prefix of RunStart, RoundEv*, (Outcome | Refused).
What only the System knows enters through RunStart.system and Outcome.score, each a value or Unknown.
"""
import json
from dataclasses import dataclass
from typing import Union

from needleview.report import Evaluated, Floor, NotEvaluated, ROUND_KEYS, Unreadable, parse

UNKNOWN = "UNKNOWN"
OUTCOME_KEYS = ("kind", "reason", "bracket", "A_hull", "B_hull", "agree")


@dataclass(frozen=True)
class Unknown:
    pass


@dataclass(frozen=True)
class Known:
    truth_K_c: float
    a: float
    w_max: float


@dataclass(frozen=True)
class Scored:
    cell: str
    contains: Union[bool, None]


@dataclass(frozen=True)
class RunStart:
    run: int
    world: str
    label: str
    system: Union[Known, Unknown]


@dataclass(frozen=True)
class RoundEv:
    run: int
    rnd: Union[Evaluated, NotEvaluated]


@dataclass(frozen=True)
class Outcome:
    run: int
    kind: str
    reason: Union[str, None]
    bracket: Union[tuple, None]
    A_hull: Union[tuple, None]
    B_hull: Union[tuple, None]
    agree: Union[bool, None]
    score: Union[Scored, Unknown]


@dataclass(frozen=True)
class Refused:
    run: int
    why: str


def refused(run, world, label, why):
    return (RunStart(run, world, label, Unknown()), Refused(run, why))


def _pair(v):
    return None if v is None else tuple(v)


def events(run, world, label, text, truth):
    item = parse(label, text, truth)
    if isinstance(item, Unreadable):
        return refused(run, world, label, item.why)
    ov = item.overlay
    system = Unknown() if ov is None else Known(ov.truth_K_c, ov.a, ov.w_max)
    score = Unknown() if ov is None else Scored(ov.cell, ov.contains)
    rounds = () if isinstance(item.report, Floor) else item.report.rounds
    obj = json.loads(text)
    nav = {k: obj[k] for k in OUTCOME_KEYS}
    out = Outcome(run, nav["kind"], nav["reason"], _pair(nav["bracket"]), _pair(nav["A_hull"]),
                  _pair(nav["B_hull"]), nav["agree"], score)
    return (RunStart(run, world, label, system),) + tuple(RoundEv(run, r) for r in rounds) + (out,)


def _lst(v):
    return None if v is None else list(v)


def _round_nav(r):
    if isinstance(r, NotEvaluated):
        d = {k: None for k in ROUND_KEYS}
        d.update(round=r.round, grid=list(r.grid), lo=r.lo, hi=r.hi, index=r.index, evaluated=False)
        return d
    return {"round": r.round, "grid": list(r.grid), "C": list(r.C), "C_err": list(r.C_err),
            "Gs": [list(row) for row in r.Gs], "Gs_err": [list(row) for row in r.Gs_err], "D": list(r.D),
            "A": list(r.A), "B": list(r.B), "lo": r.lo, "hi": r.hi, "index": r.index, "evaluated": True}


def _system(s):
    if isinstance(s, Known):
        return {"truth_K_c": s.truth_K_c, "a": s.a, "w_max": s.w_max}
    return UNKNOWN


def _score(s):
    if isinstance(s, Scored):
        return {"cell": s.cell, "contains": s.contains}
    return UNKNOWN


def _one(e):
    if isinstance(e, RunStart):
        return {"ev": "run", "run": e.run, "world": e.world, "label": e.label, "system": _system(e.system)}
    if isinstance(e, RoundEv):
        return {"ev": "round", "run": e.run, "nav": _round_nav(e.rnd)}
    if isinstance(e, Outcome):
        return {"ev": "outcome", "run": e.run,
                "nav": {"kind": e.kind, "reason": e.reason, "bracket": _lst(e.bracket), "A_hull": _lst(e.A_hull),
                        "B_hull": _lst(e.B_hull), "agree": e.agree}, "score": _score(e.score)}
    return {"ev": "unreadable", "run": e.run, "why": e.why}


def encode(stream):
    return [_one(e) for e in stream]
