"""Plan 1545 — the drift laws and the tick grid (contract/SCHEMA-1545.md sections 2 and 3). Pure unit tests, no server.
FROZEN: the Generator makes this green; it does not edit this file.

What it pins:
  1. the four laws are the exact declared expressions of the index, and nothing else is a law;
  2. a law is a pure function: calling it out of order or twice changes nothing (no accumulation);
  3. the declared bounds contain the law over the whole horizon;
  4. the drift table is parsed strictly: a missing key, an extra key or a wrong type is a Malformed value, never a default;
  5. a dial value is exactly lo + t * (hi - lo) / T.

RED until `environment/drift.py` and `environment/apparatus_config.py` exist.
Run from the repo root:  python contract/test_apparatus_drift.py   (or pytest)
"""
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

TARGETS = ("L4",)
TABLES = {
    "none": {"target": "L4", "law": "none"},
    "linear": {"target": "L4", "law": "linear", "rate": -3.5e-7},
    "sine": {"target": "L4", "law": "sine", "amp": 0.02, "period": 977},
    "step": {"target": "L4", "law": "step", "at": 1234, "size": 0.05},
}
EXPECT = {
    "none": lambda i: 0.0,
    "linear": lambda i: -3.5e-7 * i,
    "sine": lambda i: 0.02 * math.sin(2.0 * math.pi * i / 977),
    "step": lambda i: 0.05 if i >= 1234 else 0.0,
}
INDICES = [0, 1, 2, 487, 488, 489, 976, 977, 978, 1233, 1234, 1235, 99999, 200000]


def _mods():
    from environment import apparatus_config, drift
    from navigator import reader
    return drift, apparatus_config, reader


def test_the_laws_are_the_declared_expressions():
    DR, _, R = _mods()
    assert tuple(DR.LAWS) == ("none", "linear", "sine", "step"), DR.LAWS
    for law, table in TABLES.items():
        d = DR.parse_drift(dict(table), TARGETS)
        assert not isinstance(d, R.Malformed), (law, d)
        for i in INDICES:
            got = DR.offset(d, i)
            assert isinstance(got, float) and got == EXPECT[law](i), (law, i, got, EXPECT[law](i))


def test_a_law_is_a_pure_function_of_the_index():
    DR, _, _ = _mods()
    for law, table in TABLES.items():
        d = DR.parse_drift(dict(table), TARGETS)
        forward = [DR.offset(d, i) for i in INDICES]
        backward = [DR.offset(d, i) for i in reversed(INDICES)][::-1]
        again = [DR.offset(d, i) for i in INDICES]
        assert forward == backward == again, f"{law}: the offset depends on the order of the calls"


def test_the_bounds_contain_the_law():
    DR, _, _ = _mods()
    horizon = 200000
    want = {"none": (0.0, 0.0), "linear": (-3.5e-7 * horizon, 0.0), "sine": (-0.02, 0.02), "step": (0.0, 0.05)}
    for law, table in TABLES.items():
        d = DR.parse_drift(dict(table), TARGETS)
        lo, hi = DR.bounds(d, horizon)
        assert (lo, hi) == want[law], (law, lo, hi)
        for i in range(0, horizon + 1, 97):
            assert lo <= DR.offset(d, i) <= hi, (law, i)
    up = DR.parse_drift({"target": "L4", "law": "linear", "rate": 2.0e-7}, TARGETS)
    assert DR.bounds(up, horizon) == (0.0, 2.0e-7 * horizon)
    down = DR.parse_drift({"target": "L4", "law": "step", "at": 0, "size": -0.03}, TARGETS)
    assert DR.bounds(down, horizon) == (-0.03, 0.0)


def test_the_drift_table_is_parsed_strictly():
    DR, _, R = _mods()
    bad = [
        ("drift", None), ("drift", [1]),
        ("target", {"law": "none"}), ("target", {"target": "K", "law": "none"}), ("target", {"target": 3, "law": "none"}),
        ("law", {"target": "L4"}), ("law", {"target": "L4", "law": "ramp"}), ("law", {"target": "L4", "law": 1}),
        ("rate", {"target": "L4", "law": "linear"}), ("rate", {"target": "L4", "law": "linear", "rate": 1}),
        ("rate", {"target": "L4", "law": "linear", "rate": float("nan")}),
        ("rate", {"target": "L4", "law": "none", "rate": 1.0e-7}),
        ("size", {"target": "L4", "law": "linear", "rate": 1.0e-7, "size": 0.1}),
        ("amp", {"target": "L4", "law": "sine", "period": 100}), ("amp", {"target": "L4", "law": "sine", "amp": 0.0, "period": 100}),
        ("amp", {"target": "L4", "law": "sine", "amp": -0.01, "period": 100}),
        ("period", {"target": "L4", "law": "sine", "amp": 0.01}), ("period", {"target": "L4", "law": "sine", "amp": 0.01, "period": 1}),
        ("period", {"target": "L4", "law": "sine", "amp": 0.01, "period": 100.0}),
        ("period", {"target": "L4", "law": "sine", "amp": 0.01, "period": True}),
        ("at", {"target": "L4", "law": "step", "size": 0.01}), ("at", {"target": "L4", "law": "step", "at": -1, "size": 0.01}),
        ("at", {"target": "L4", "law": "step", "at": 5.0, "size": 0.01}),
        ("size", {"target": "L4", "law": "step", "at": 5}), ("size", {"target": "L4", "law": "step", "at": 5, "size": 1}),
    ]
    for field, table in bad:
        got = DR.parse_drift(table, TARGETS)
        assert isinstance(got, R.Malformed), f"accepted a malformed drift table {table!r}"
        assert got.field == field, f"{table!r}: field {got.field!r}, want {field!r}"


def test_a_dial_value_is_on_the_tick_grid():
    _, AC, _ = _mods()
    for lo, hi, T in ((0.2, 0.5, 1200), (0.2, 0.5, 7), (-1.0, 3.0, 1), (0.31, 0.39, 320)):
        for t in sorted({0, 1, T // 3, T - 1, T} & set(range(T + 1))):
            got = AC.tick_value(lo, hi, T, t)
            assert isinstance(got, float) and got == lo + t * (hi - lo) / T, (lo, hi, T, t, got)
        assert AC.tick_value(lo, hi, T, 0) == lo


if __name__ == "__main__":
    _tests = [test_the_laws_are_the_declared_expressions, test_a_law_is_a_pure_function_of_the_index, test_the_bounds_contain_the_law,
              test_the_drift_table_is_parsed_strictly, test_a_dial_value_is_on_the_tick_grid]
    _fail = 0
    for _t in _tests:
        try:
            _t(); print(f"PASS {_t.__name__}")
        except Exception as _e:  # noqa: BLE001
            _fail += 1; print(f"FAIL {_t.__name__}: {type(_e).__name__}: {str(_e)[:300]}")
    print(f"{len(_tests) - _fail}/{len(_tests)} passed")
    sys.exit(1 if _fail else 0)
