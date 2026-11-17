"""Plan 1561: the drift worlds (contract/SCHEMA-1561.md section 3). Pure. A drift world is the shipped world with a few keys
replaced; a ladder is an ordered list of such rungs of rising severity. Nothing here judges a world: `apparatus_config.parse_world`
is the one door, and a rung that leaves the domain is refused there, never clamped here. Parse B: `dict -> Worlds | Malformed`."""
import copy
import json
import re
from dataclasses import dataclass

from environment.drift import float_field
from navigator.reader import Malformed

_NAME = re.compile(r"[A-Za-z0-9_.\-]+")
_WORLD_KEYS = {"base", "ladder"}
_LADDER_KEYS = {"name", "rungs"}
_REQUIRED = ("label", "severity", "horizon", "drift")   # in the order they are checked
_OPTIONAL = ("hidden", "dials")


@dataclass(frozen=True)
class Rung:
    label: str
    severity: float
    table: dict   # the keys this rung replaces in the base world


@dataclass(frozen=True)
class Ladder:
    name: str
    rungs: tuple


@dataclass(frozen=True)
class Worlds:
    base: str
    ladders: tuple


def _name(v):
    """a name: letters, digits, `-`, `_`, `.`; never `--`, the run-name separator."""
    return isinstance(v, str) and _NAME.fullmatch(v) is not None and "--" not in v


def _severity(v):
    return not isinstance(float_field({"severity": v}, "severity", lambda x: x > 0), Malformed)


def _rung(lname, j, r):
    at = f"{lname}[{j}]"
    if not isinstance(r, dict):
        return Malformed(at, "table required")
    missing = [k for k in _REQUIRED if k not in r]
    if missing:
        return Malformed(f"{at}.{missing[0]}", "required")
    extra = sorted(set(r) - set(_REQUIRED) - set(_OPTIONAL))
    if extra:
        return Malformed(f"{at}.{extra[0]}", "unknown key (a rung replaces horizon, drift, hidden or dials only)")
    if not _name(r["label"]):
        return Malformed(f"{at}.label", "a name: letters, digits, - _ . and never --")
    if not _severity(r["severity"]):
        return Malformed(f"{at}.severity", "a finite float > 0")
    keys = ("horizon", "drift") + tuple(k for k in _OPTIONAL if k in r)
    return Rung(r["label"], r["severity"], {k: copy.deepcopy(r[k]) for k in keys})


def _ladder(i, lad):
    at = f"ladder[{i}]"
    if not isinstance(lad, dict) or set(lad) != _LADDER_KEYS:
        return Malformed(at, "table with exactly name and rungs")
    if not _name(lad["name"]):
        return Malformed(f"{at}.name", "a name: letters, digits, - _ . and never --")
    rungs = lad["rungs"]
    if not isinstance(rungs, list) or not rungs:
        return Malformed(f"{at}.rungs", "a non-empty list")
    got = [_rung(lad["name"], j, r) for j, r in enumerate(rungs)]
    bad = next((g for g in got if isinstance(g, Malformed)), None)
    if bad:
        return bad
    name = lad["name"]
    if len({g.label for g in got}) != len(got):
        return Malformed(f"{name}.label", "labels are distinct")
    if any(not a.severity < b.severity for a, b in zip(got, got[1:])):
        return Malformed(f"{name}.severity", "severities rise strictly in the order given")
    return Ladder(name, tuple(got))


def parse_worlds(table):
    if not isinstance(table, dict) or set(table) != _WORLD_KEYS:
        return Malformed("worlds", "table with exactly base and ladder")
    base = table["base"]
    if not (_name(base) and base.endswith(".toml")):
        return Malformed("base", "a sibling .toml file name")
    ladders = table["ladder"]
    if not isinstance(ladders, list) or not ladders:
        return Malformed("ladder", "a non-empty list")
    got = [_ladder(i, lad) for i, lad in enumerate(ladders)]
    bad = next((g for g in got if isinstance(g, Malformed)), None)
    if bad:
        return bad
    if len({g.name for g in got}) != len(got):
        return Malformed("ladder.name", "ladder names are distinct")
    return Worlds(base, tuple(got))


def ladder(worlds, name):
    return {lad.name: lad for lad in worlds.ladders}[name]


def materialise(base, rung, seed):
    """the rung as a world: the base's keys in their order, each replaced by the rung's, the run seed the world's `seed`. The
    drift table is the rung's as declared: a walk's own `seed` is not the run seed, so the run seed moves the noise, never
    the path. Checks nothing; the world door does."""
    return copy.deepcopy({**base, **rung.table, "seed": seed})


# ---- to_toml: every value type has one writer; a type with none has no row -------------------------------------------------
def _key(k):
    return k if re.fullmatch(r"[A-Za-z0-9_\-]+", k) else _str(k)


def _str(s):
    return json.dumps(s).replace("\x7f", "\\u007f")


def _inline(d):
    return "{" + ", ".join(f"{_key(k)} = {_value(v)}" for k, v in d.items()) + "}"


_EMIT = {
    bool: lambda v: "true" if v else "false",
    int: repr,
    float: repr,
    str: _str,
    list: lambda v: "[" + ", ".join(_value(x) for x in v) + "]",
    tuple: lambda v: "[" + ", ".join(_value(x) for x in v) + "]",
    dict: _inline,
}


def _value(v):
    return _EMIT[type(v)](v)


def to_toml(world):
    """one `key = value` line per top-level key, in the table's order; tomllib reads it back equal, every float to its last bit."""
    return "".join(f"{_key(k)} = {_value(v)}\n" for k, v in world.items())
