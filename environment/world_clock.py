"""Plan 1565: the world clock, world key `world_clock` (contract/SCHEMA-1565.md sections 2 and 3). Pure; imports nothing that opens a file.
A world clock says how many sweeps the world runs on its own while the needle deliberates. Every line the server receives
is a TURN; the world clock is a total table from the needle time spent so far (turns, seconds) to the sweeps the world is owed.
`paused` owes nothing (plans 1545/1553, byte for byte); `charged` owes a declared number of sweeps per turn (deterministic: the
acceptance kind); `wall` owes sweeps for the wall seconds the needle took (for demos; not reproducible). The world ends at its
horizon: the free run never carries the index past it."""
import math
from dataclasses import dataclass

from environment import drift as DR
from navigator import reader as R

ABSENT = {"kind": "paused"}      # a world file with no `world_clock` key (owner ruling 2026-11-16: paused stays the default)

_KEYS = {"paused": (), "charged": ("per_turn",), "wall": ("sweeps_per_second",)}
KINDS = tuple(_KEYS)
_FIELD = {
    "per_turn": lambda t: R._int(t, "per_turn", 0),
    "sweeps_per_second": lambda t: DR.float_field(t, "sweeps_per_second", lambda x: x > 0, "float>0"),
}
_OWED = {
    "paused": lambda v, turns, seconds: 0,
    "charged": lambda v, turns, seconds: v["per_turn"] * turns,
    "wall": lambda v, turns, seconds: math.floor(v["sweeps_per_second"] * seconds),
}


@dataclass(frozen=True)
class WorldClock:
    kind: str
    values: dict
    table: dict      # the table as given (ABSENT when the world has no `world_clock` key)


@dataclass(frozen=True)
class Ledger:
    turns: int       # lines received so far
    seconds: float   # needle wall seconds so far (section 3)
    ran: int         # free sweeps run so far


START = Ledger(0, 0.0, 0)


def parse_world_clock(table):
    """-> WorldClock | Malformed. Order: the table, `kind`, an unknown key (the first in sorted order), the kind's keys."""
    if not isinstance(table, dict):
        return R.Malformed("world_clock", "table required")
    kind = table.get("kind")
    if not (isinstance(kind, str) and kind in _KEYS):
        return R.Malformed("kind", f"one of {KINDS}")
    extra = sorted(set(table) - {"kind", *_KEYS[kind]})
    if extra:
        return R.Malformed(extra[0], "unknown key")
    vals = {k: _FIELD[k](table) for k in _KEYS[kind]}
    bad = R._first_bad(list(vals.values()))
    return bad if bad else WorldClock(kind, vals, dict(table))


def owed(wc, turns, seconds):
    """the free sweeps the world is owed after `turns` turns that took `seconds` of needle time in all."""
    return _OWED[wc.kind](wc.values, turns, seconds)


def turn(wc, ledger, seconds, room):
    """one turn of `seconds` needle time, with `room` sweeps left before the horizon -> (the next ledger, the free sweeps to run now)."""
    t, s = ledger.turns + 1, ledger.seconds + seconds
    free = min(owed(wc, t, s) - ledger.ran, room)
    return Ledger(t, s, ledger.ran + free), free
