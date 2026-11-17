"""Plan 1545: the drift laws (contract/SCHEMA-1545.md section 3). Pure. The offset of a hidden parameter is a function of
the apparatus index alone: it has no memory, so no call order, refused call or batching can change it. The laws are a total
table keyed on the law name; an unknown law has no row. Parse B: `dict -> Drift | navigator.reader.Malformed`."""
import hashlib
import math
from dataclasses import dataclass

from navigator import reader as R

# law -> the keys it adds to {target, law}, in the order they are checked
_KEYS = {"none": (), "linear": ("rate",), "sine": ("amp", "period"), "step": ("at", "size"),
         "ramp-then-rest": ("at", "rate", "span"), "walk": ("at", "seed", "every", "stride", "knots")}
LAWS = tuple(_KEYS)


def walk_sign(seed, j):
    """plan 1561: step j of the telegraph walk, +1 or -1: bit 0 of sha256("compass-walk/1 {seed} {j}"). A hash of
    (seed, j), not a stream, so the walk is a total function of the index."""
    return 1 - 2 * (hashlib.sha256(f"compass-walk/1 {seed} {j}".encode("utf-8")).digest()[0] & 1)


def _walk_tables(v):
    """the walk's derived tables, a pure function of its keys: `vel[n]` the sign of segment n (0 at rest, n = knots) and
    `prefix[n]` the running sum of the signs before it."""
    vel = tuple(walk_sign(v["seed"], j) for j in range(v["knots"])) + (0,)
    prefix = [0]
    for s in vel[:-1]:
        prefix.append(prefix[-1] + s)
    return {"vel": vel, "prefix": tuple(prefix)}


def _walk_at(v, j):
    """W(j), j >= 0 sweeps since the walk's onset."""
    n = min(j // v["every"], v["knots"])
    return v["stride"] * (v["prefix"][n] + v["vel"][n] * (j - n * v["every"]) / v["every"])


def _walk_bounds(v, h):
    H = max(0, h - v["at"])
    top = min(H // v["every"], v["knots"])
    seen = [v["stride"] * v["prefix"][n] for n in range(top + 1)] + [_walk_at(v, H)]
    return (min(seen), max(seen))


def _ramp_m(v, i):
    return min(max(0, i - v["at"]), v["span"])

_OFFSET = {
    "none": lambda v, i: 0.0,
    "linear": lambda v, i: v["rate"] * i,
    "sine": lambda v, i: v["amp"] * math.sin(2.0 * math.pi * i / v["period"]),
    "step": lambda v, i: v["size"] if i >= v["at"] else 0.0,
    "ramp-then-rest": lambda v, i: v["rate"] * _ramp_m(v, i),
    "walk": lambda v, i: 0.0 if i < v["at"] else _walk_at(v, i - v["at"]),
}
_BOUNDS = {
    "none": lambda v, h: (0.0, 0.0),
    "linear": lambda v, h: (min(0.0, v["rate"] * h), max(0.0, v["rate"] * h)),
    "sine": lambda v, h: (-v["amp"], v["amp"]),
    "step": lambda v, h: (min(0.0, v["size"]), max(0.0, v["size"])),
    "ramp-then-rest": lambda v, h: (min(0.0, v["rate"] * _ramp_m(v, h)), max(0.0, v["rate"] * _ramp_m(v, h))),
    "walk": _walk_bounds,
}
_DERIVED = {"none": dict, "linear": dict, "sine": dict, "step": dict, "ramp-then-rest": dict, "walk": _walk_tables}
_FIELD = {
    "rate": lambda t: float_field(t, "rate"),
    "amp": lambda t: float_field(t, "amp", lambda x: x > 0, "float>0"),
    "period": lambda t: R._int(t, "period", 2),
    "at": lambda t: R._int(t, "at", 0),
    "size": lambda t: float_field(t, "size"),
    "span": lambda t: R._int(t, "span", 1),
    "seed": lambda t: R._int(t, "seed", 0),
    "every": lambda t: R._int(t, "every", 1),
    "stride": lambda t: float_field(t, "stride", lambda x: x > 0, "float>0"),
    "knots": lambda t: R._int(t, "knots", 1),
}


@dataclass(frozen=True)
class Drift:
    target: str
    law: str
    values: dict   # the law's own keys
    table: dict    # the table as given (for the run directory only)


def float_field(d, f, pred=lambda x: True, what="float"):
    """a finite float; an int is not a float here."""
    v = d.get(f)
    return v if isinstance(v, float) and math.isfinite(v) and pred(v) else R.Malformed(f, what)


def parse_drift(table, targets):
    if not isinstance(table, dict):
        return R.Malformed("drift", "table required")
    target, law = table.get("target"), table.get("law")
    if not isinstance(target, str) or target not in targets:
        return R.Malformed("target", f"one of {tuple(targets)}")
    if not isinstance(law, str) or law not in _KEYS:
        return R.Malformed("law", f"one of {LAWS}")
    extra = sorted(set(table) - {"target", "law", *_KEYS[law]})
    if extra:
        return R.Malformed(extra[0], f"unknown key for law {law}")
    got = [_FIELD[k](table) for k in _KEYS[law]]
    bad = R._first_bad(got)
    if bad:
        return bad
    values = dict(zip(_KEYS[law], got))
    return Drift(target, law, {**values, **_DERIVED[law](values)}, dict(table))


def offset(drift, index):
    return _OFFSET[drift.law](drift.values, index)


def bounds(drift, horizon):
    return _BOUNDS[drift.law](drift.values, horizon)
