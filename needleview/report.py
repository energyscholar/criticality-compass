"""The needle-view reader: a report of the needle becomes a typed value, or is refused as a value.

Pure: nothing is opened here. `parse(label, text, truth)` never raises. Every input is a Run or an Unreadable.
"""
import json
import math
from dataclasses import dataclass
from typing import Union

REPORT_KEYS = ("kind", "reason", "bracket", "A_hull", "B_hull", "agree", "rounds")
VERDICT_KEYS = ("truth_K_c", "a", "w_max", "contains", "width", "narrow_enough", "cell", "run_id", "plan")
ROUND_KEYS = ("round", "grid", "C", "C_err", "Gs", "Gs_err", "D", "A", "B", "lo", "hi", "index", "evaluated")
MOMENTS = ("C", "C_err", "Gs", "Gs_err", "D", "A", "B")
CELLS = ("HIT", "MISS", "REFUSED")


@dataclass(frozen=True)
class Evaluated:
    round: int
    grid: tuple
    C: tuple
    C_err: tuple
    Gs: tuple
    Gs_err: tuple
    D: tuple
    A: tuple
    B: tuple
    lo: float
    hi: float
    index: int


@dataclass(frozen=True)
class NotEvaluated:
    round: int
    grid: tuple
    lo: float
    hi: float
    index: int


@dataclass(frozen=True)
class Located:
    rounds: tuple
    agree: bool


@dataclass(frozen=True)
class Floor:
    pass


@dataclass(frozen=True)
class Budget:
    rounds: tuple


@dataclass(frozen=True)
class Overlay:
    truth_K_c: float
    a: float
    w_max: float
    contains: Union[bool, None]
    cell: str


@dataclass(frozen=True)
class Run:
    label: str
    report: Union[Located, Floor, Budget]
    overlay: Union[Overlay, None]


@dataclass(frozen=True)
class Unreadable:
    label: str
    why: str


class _Refused(Exception):
    """internal: a report that cannot be read; parse turns it into an Unreadable value."""


def _no(why):
    raise _Refused(why)


def _is_float(v):
    return type(v) is float and math.isfinite(v)


def _is_int(v):
    return type(v) is int


def _float(v, name):
    if not _is_float(v):
        _no(f"{name} is not a finite float")
    return v


def _floats(v, name, n=None):
    if type(v) is not list or (n is not None and len(v) != n):
        _no(f"{name} is not a list of the right length")
    return tuple(_float(x, name) for x in v)


def _ints(v, name, m):
    if type(v) is not list:
        _no(f"{name} is not a list")
    out = tuple(v)
    if not all(_is_int(i) and 0 <= i < m for i in out):
        _no(f"{name} holds a value that is not an int inside 0..{m - 1}")
    if any(b <= a for a, b in zip(out, out[1:])):
        _no(f"{name} is not strictly increasing")
    return out


def _pair(v, name):
    t = _floats(v, name, 2)
    return t


def _round(r, position):
    if type(r) is not dict or set(r) != set(ROUND_KEYS):
        _no(f"round {position} does not hold exactly the round keys")
    if r["round"] != position or not _is_int(r["round"]):
        _no(f"round {position} is numbered {r['round']!r}")
    if not _is_int(r["index"]) or r["index"] < 0:
        _no(f"round {position}: index is not an int >= 0")
    if type(r["evaluated"]) is not bool:
        _no(f"round {position}: evaluated is not a bool")
    grid = _floats(r["grid"], f"round {position} grid")
    m = len(grid)
    if m < 2 or any(b <= a for a, b in zip(grid, grid[1:])):
        _no(f"round {position}: grid is not strictly increasing with 2 or more points")
    lo, hi = _float(r["lo"], "lo"), _float(r["hi"], "hi")
    if not (grid[0] <= lo < hi <= grid[-1]):
        _no(f"round {position}: lo, hi are not inside the grid")
    if not r["evaluated"]:
        if any(r[k] is not None for k in MOMENTS):
            _no(f"round {position}: not evaluated but holds moments")
        return NotEvaluated(position, grid, lo, hi, r["index"])
    c, c_err, d = (_floats(r[k], f"round {position} {k}", m) for k in ("C", "C_err", "D"))
    if any(e < 0 for e in c_err):
        _no(f"round {position}: C_err is negative")
    levels = {}
    for k in ("Gs", "Gs_err"):
        if type(r[k]) is not list or len(r[k]) != m:
            _no(f"round {position}: {k} is not a list of {m} rows")
        levels[k] = tuple(_floats(row, f"round {position} {k}") for row in r[k])
    nlev = len(levels["Gs"][0])
    if nlev < 2 or any(len(row) != nlev for k in levels for row in levels[k]):
        _no(f"round {position}: Gs rows do not hold the same 2 or more levels")
    if any(e < 0 for row in levels["Gs_err"] for e in row):
        _no(f"round {position}: Gs_err is negative")
    a, b = _ints(r["A"], "A", m), _ints(r["B"], "B", m)
    if not a:
        _no(f"round {position}: A is empty")
    return Evaluated(position, grid, c, c_err, levels["Gs"], levels["Gs_err"], d, a, b, lo, hi, r["index"])


def _hull(v, name):
    t = _pair(v, name)
    if t[0] > t[1]:
        _no(f"{name} is reversed")
    return t


def _read_v1(obj):
    """the reader for the report of contract/SCHEMA-1525.md. Returns (report, is_refusal)."""
    if type(obj["rounds"]) is not list:
        _no("rounds is not a list")
    rounds = tuple(_round(r, i) for i, r in enumerate(obj["rounds"], 1))
    kind = obj["kind"]
    if kind == "Located":
        if obj["reason"] is not None:
            _no("a Located report carries a reason")
        if not rounds or not all(isinstance(r, Evaluated) for r in rounds):
            _no("a Located report needs 1 or more rounds, all evaluated")
        if _pair(obj["bracket"], "bracket") != (rounds[-1].lo, rounds[-1].hi):
            _no("bracket is not the last round's lo, hi")
        _hull(obj["A_hull"], "A_hull")
        if obj["B_hull"] is not None:
            _hull(obj["B_hull"], "B_hull")
        if type(obj["agree"]) is not bool:
            _no("agree is not a bool")
        return Located(rounds, obj["agree"]), False
    if kind == "REFUSE":
        if any(obj[k] is not None for k in ("bracket", "A_hull", "B_hull", "agree")):
            _no("a refusal carries a bracket, hull or agree")
        if obj["reason"] == "floor":
            if rounds:
                _no("a floor refusal carries rounds")
            return Floor(), True
        if obj["reason"] == "budget":
            if not rounds or all(isinstance(r, Evaluated) for r in rounds):
                _no("a budget refusal needs a round that was not evaluated")
            return Budget(rounds), True
        _no(f"a refusal with reason {obj['reason']!r}")
    _no(f"kind {kind!r} is not read by this viewer")


def _overlay(obj, refusal):
    if not any(k in obj for k in VERDICT_KEYS):
        return None
    if not all(k in obj for k in VERDICT_KEYS):
        _no("truth: the scored values are not all present")
    k_c, a, w_max = obj["truth_K_c"], obj["a"], obj["w_max"]
    if not (_is_float(k_c) and _is_float(a) and a >= 0 and _is_float(w_max) and w_max > 0):
        _no("truth: truth_K_c, a or w_max is not a usable float")
    if obj["cell"] not in CELLS or type(obj["run_id"]) is not str or type(obj["plan"]) is not str:
        _no("truth: cell, run_id or plan is malformed")
    if (obj["cell"] == "REFUSED") != refusal:
        _no("truth: cell does not match the report")
    if refusal:
        if any(obj[k] is not None for k in ("contains", "width", "narrow_enough")):
            _no("truth: a refusal carries contains, width or narrow_enough")
        return Overlay(k_c, a, w_max, None, obj["cell"])
    if type(obj["contains"]) is not bool or type(obj["narrow_enough"]) is not bool or not _is_float(obj["width"]):
        _no("truth: contains, width or narrow_enough is malformed")
    return Overlay(k_c, a, w_max, obj["contains"], obj["cell"])


def _frame(obj):
    """rule 1 and 2: an object holding the seven report keys and no key but the nine verdict keys."""
    if type(obj) is not dict:
        _no("not a JSON object")
    for k in REPORT_KEYS:
        if k not in obj:
            _no(f"report key {k} is missing")
    for k in obj:
        if k not in REPORT_KEYS and k not in VERDICT_KEYS:
            _no(f"unknown key {k}")
    return obj


# one entry; a later report schema adds a reader in a new file and a new entry here
READERS = (_read_v1,)


def parse(label, text, truth):
    try:
        obj = _frame(json.loads(text))
        got = None
        for reader in READERS:
            got = reader(obj)
        report, refusal = got
        return Run(label, report, _overlay(obj, refusal) if truth else None)
    except _Refused as e:
        return Unreadable(label, str(e))
    except (ValueError, RecursionError, TypeError) as e:
        return Unreadable(label, f"not readable JSON ({type(e).__name__})")
