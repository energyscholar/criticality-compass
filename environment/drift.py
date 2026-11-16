"""Plan 1545: the drift laws (contract/SCHEMA-1545.md section 3). Pure. The offset of a hidden parameter is a function of
the apparatus index alone: it has no memory, so no call order, refused call or batching can change it. The laws are a total
table keyed on the law name; an unknown law has no row. Parse B: `dict -> Drift | navigator.reader.Malformed`."""
import math
from dataclasses import dataclass

from navigator import reader as R

# law -> the keys it adds to {target, law}, in the order they are checked
_KEYS = {"none": (), "linear": ("rate",), "sine": ("amp", "period"), "step": ("at", "size")}
LAWS = tuple(_KEYS)

_OFFSET = {
    "none": lambda v, i: 0.0,
    "linear": lambda v, i: v["rate"] * i,
    "sine": lambda v, i: v["amp"] * math.sin(2.0 * math.pi * i / v["period"]),
    "step": lambda v, i: v["size"] if i >= v["at"] else 0.0,
}
_BOUNDS = {
    "none": lambda v, h: (0.0, 0.0),
    "linear": lambda v, h: (min(0.0, v["rate"] * h), max(0.0, v["rate"] * h)),
    "sine": lambda v, h: (-v["amp"], v["amp"]),
    "step": lambda v, h: (min(0.0, v["size"]), max(0.0, v["size"])),
}
_FIELD = {
    "rate": lambda t: float_field(t, "rate"),
    "amp": lambda t: float_field(t, "amp", lambda x: x > 0, "float>0"),
    "period": lambda t: R._int(t, "period", 2),
    "at": lambda t: R._int(t, "at", 0),
    "size": lambda t: float_field(t, "size"),
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
    return Drift(target, law, dict(zip(_KEYS[law], got)), dict(table))


def offset(drift, index):
    return _OFFSET[drift.law](drift.values, index)


def bounds(drift, horizon):
    return _BOUNDS[drift.law](drift.values, horizon)
