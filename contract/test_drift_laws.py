"""Plan 1561 — the two new drift laws (contract/SCHEMA-1561.md section 2). Pure unit tests, no server.
FROZEN: the Generator makes this green; it does not edit this file.

What it pins:
  d01 the law tuple, and the four older laws unchanged at every index and horizon;
  d02 ramp-then-rest is its declared expression: still, then the ramp, then at rest;
  d03 walk_sign is one bit of a sha256; a walk passes through stride * P[n] at every knot, is linear between, rests after;
  d04 both laws are pure functions of the index (order, repetition, a fresh parse: no change);
  d05 the bounds are exact: they contain the law and are attained, at horizons that end mid-segment;
  d06 the two tables are parsed strictly, the field named;
  d07 the world door refuses a drift that leaves the domain (field=drift), never clamps, and accepts one that stays in.

RED until environment/drift.py has the laws `ramp-then-rest` and `walk`.
Run from the repo root:  python contract/test_drift_laws.py   (or pytest)
"""
import hashlib
import math
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "system-instantiated" / "plugins" / "at"))

T = ("L4",)
RAMP = {"target": "L4", "law": "ramp-then-rest", "at": 1000, "rate": -3.0e-7, "span": 5000}
WALK = {"target": "L4", "law": "walk", "at": 300, "seed": 1561, "every": 700, "stride": 0.004, "knots": 9}
OLD = {
    "none": ({"target": "L4", "law": "none"}, lambda i: 0.0),
    "linear": ({"target": "L4", "law": "linear", "rate": -3.5e-7}, lambda i: -3.5e-7 * i),
    "sine": ({"target": "L4", "law": "sine", "amp": 0.02, "period": 977}, lambda i: 0.02 * math.sin(2.0 * math.pi * i / 977)),
    "step": ({"target": "L4", "law": "step", "at": 1234, "size": 0.05}, lambda i: 0.05 if i >= 1234 else 0.0),
}


def _mods():
    from environment import apparatus_config, drift
    from navigator import reader
    return drift, apparatus_config, reader


def _sign(seed, j):
    return 1 - 2 * (hashlib.sha256(f"compass-walk/1 {seed} {j}".encode("utf-8")).digest()[0] & 1)


def _walk_ref(v, i):
    """an independent statement of the walk: sum the finished segments, then the fraction of the current one."""
    if i < v["at"]:
        return 0.0
    J = i - v["at"]
    done = min(J // v["every"], v["knots"])
    pos = sum(_sign(v["seed"], j) for j in range(done))
    if done == v["knots"]:
        return v["stride"] * pos
    return v["stride"] * (pos + _sign(v["seed"], done) * (J - done * v["every"]) / v["every"])


def test_d01_the_law_tuple_and_the_old_laws():
    DR, _, R = _mods()
    assert tuple(DR.LAWS) == ("none", "linear", "sine", "step", "ramp-then-rest", "walk"), DR.LAWS
    idx = [0, 1, 487, 976, 977, 1233, 1234, 1235, 99999, 200000]
    for law, (table, f) in OLD.items():
        d = DR.parse_drift(dict(table), T)
        assert not isinstance(d, R.Malformed), (law, d)
        for i in idx:
            assert DR.offset(d, i) == f(i), (law, i)
    want = {"none": (0.0, 0.0), "linear": (-3.5e-7 * 200000, 0.0), "sine": (-0.02, 0.02), "step": (0.0, 0.05)}
    for law, (table, _) in OLD.items():
        assert DR.bounds(DR.parse_drift(dict(table), T), 200000) == want[law], law
    assert isinstance(DR.parse_drift({"target": "L4", "law": "ramp"}, T), R.Malformed), "'ramp' became a law"


def test_d02_ramp_then_rest_is_its_expression():
    DR, _, R = _mods()
    d = DR.parse_drift(dict(RAMP), T)
    assert not isinstance(d, R.Malformed), d
    for i in [0, 1, 999, 1000, 1001, 3000, 5999, 6000, 6001, 10 ** 6]:
        got = DR.offset(d, i)
        assert isinstance(got, float) and got == -3.0e-7 * min(max(0, i - 1000), 5000), (i, got)
    assert DR.offset(d, 999) == 0.0 and DR.offset(d, 6000) == DR.offset(d, 10 ** 6) == -3.0e-7 * 5000
    up = DR.parse_drift({**RAMP, "rate": 2.0e-7}, T)
    assert DR.offset(up, 3500) == 2.0e-7 * 2500
    big = DR.parse_drift({**RAMP, "rate": -2.4e-6, "span": 50000}, T)      # far beyond 0.06: nothing clips an offset
    assert DR.offset(big, 1000 + 50000) == DR.offset(big, 10 ** 6) == -2.4e-6 * 50000 and DR.bounds(big, 10 ** 6) == (-2.4e-6 * 50000, 0.0)


def test_d03_the_walk_is_its_expression():
    DR, _, R = _mods()
    for s, j in [(0, 0), (1561, 0), (1561, 9), (7, 123), (2 ** 40, 3)]:
        assert DR.walk_sign(s, j) == _sign(s, j) and DR.walk_sign(s, j) in (1, -1), (s, j)
    signs = [_sign(1561, j) for j in range(10)]
    assert signs == [1, -1, 1, 1, 1, 1, 1, 1, 1, -1], signs   # SCHEMA-1561 section 3.3: the declared walk's signs
    assert sum(_sign(9, j) == 1 for j in range(400)) not in (0, 400), "walk_sign is not a coin"
    for table in (WALK, {**WALK, "seed": 9, "knots": 1, "at": 0}, {**WALK, "seed": 42, "every": 1}):
        d = DR.parse_drift(dict(table), T)
        assert not isinstance(d, R.Malformed), (table, d)
        v, e, a = table, table["every"], table["at"]
        P = [0]
        for j in range(table["knots"]):
            P.append(P[-1] + _sign(table["seed"], j))
        for n in range(table["knots"] + 1):
            assert DR.offset(d, a + n * e) == table["stride"] * P[n], ("knot", table, n)
        for n in range(table["knots"]):
            if e % 2 == 0:
                mid = DR.offset(d, a + n * e + e // 2)
                assert abs(mid - table["stride"] * (P[n] + P[n + 1]) / 2) < 1e-15, ("midpoint", table, n)
        for i in sorted({0, a - 1, a, a + 1, a + e - 1, a + e, a + 3 * e + 5, a + table["knots"] * e + 1, 10 ** 6} - {-1}):
            got = DR.offset(d, i)
            assert isinstance(got, float) and abs(got - _walk_ref(v, i)) < 1e-15, (table, i, got, _walk_ref(v, i))
        assert DR.offset(d, a + table["knots"] * e) == DR.offset(d, 10 ** 7), "the walk does not rest after its last knot"


def test_d04_a_law_is_a_pure_function_of_the_index():
    DR, _, _ = _mods()
    rng = random.Random(5)
    idx = [rng.randrange(0, 20000) for _ in range(300)]
    for table in (RAMP, WALK):
        d = DR.parse_drift(dict(table), T)
        forward = [DR.offset(d, i) for i in idx]
        shuffled = list(range(len(idx)))
        rng.shuffle(shuffled)
        out_of_order = {k: DR.offset(d, idx[k]) for k in shuffled}
        fresh = DR.parse_drift(dict(table), T)
        assert forward == [out_of_order[k] for k in range(len(idx))] == [DR.offset(fresh, i) for i in idx], table["law"]


def test_d05_the_bounds_are_exact():
    DR, _, _ = _mods()
    cases = [(RAMP, h) for h in (0, 999, 1000, 3333, 6000, 200000)]
    cases += [({**RAMP, "rate": 4.0e-7}, h) for h in (2500, 200000)]
    cases += [(WALK, h) for h in (0, 299, 300, 1000, 1350, 2400, 6600, 6900, 200000)]
    cases += [({**WALK, "seed": s, "every": 97, "knots": 23}, 1500 + s) for s in range(12)]
    for table, h in cases:
        d = DR.parse_drift(dict(table), T)
        lo, hi = DR.bounds(d, h)
        vals = [DR.offset(d, i) for i in range(0, h + 1)]
        assert lo <= min(vals) and max(vals) <= hi, (table, h, lo, hi, min(vals), max(vals))
        assert abs(min(vals) - lo) < 1e-15 and abs(max(vals) - hi) < 1e-15, ("not attained", table, h, lo, hi, min(vals), max(vals))


def test_d06_the_tables_are_parsed_strictly():
    DR, _, R = _mods()
    bad = [
        ("at", {"target": "L4", "law": "ramp-then-rest", "rate": 1e-7, "span": 5}),
        ("at", {**RAMP, "at": -1}), ("at", {**RAMP, "at": 2.0}), ("at", {**RAMP, "at": True}),
        ("rate", {**RAMP, "rate": 1}), ("rate", {**RAMP, "rate": float("inf")}),
        ("span", {**RAMP, "span": 0}), ("span", {**RAMP, "span": 5.0}),
        ("span", {"target": "L4", "law": "ramp-then-rest", "at": 0, "rate": 1e-7}),
        ("size", {**RAMP, "size": 0.1}),
        ("seed", {**WALK, "seed": -1}), ("seed", {**WALK, "seed": 1.0}), ("seed", {**WALK, "seed": False}),
        ("every", {**WALK, "every": 0}), ("every", {**WALK, "every": 10.0}),
        ("stride", {**WALK, "stride": 0.0}), ("stride", {**WALK, "stride": -0.004}), ("stride", {**WALK, "stride": 1}),
        ("stride", {**WALK, "stride": float("nan")}),
        ("knots", {**WALK, "knots": 0}), ("knots", {**WALK, "knots": True}),
        ("rate", {**WALK, "rate": 1e-7}),
        ("at", {k: v for k, v in WALK.items() if k != "at"}), ("knots", {k: v for k, v in WALK.items() if k != "knots"}),
        ("law", {"target": "L4", "law": "Walk"}),
    ]
    for field, table in bad:
        got = DR.parse_drift(table, T)
        assert isinstance(got, R.Malformed), f"accepted a malformed drift table {table!r}"
        assert got.field == field, f"{table!r}: field {got.field!r}, want {field!r}"
    first = DR.parse_drift({"target": "L4", "law": "walk", "at": -1, "seed": -1, "every": 0, "stride": 0.0, "knots": 0}, T)
    assert first.field == "at", first


def test_d07_the_world_door_refuses_and_never_clamps():
    DR, AC, R = _mods()
    import tomllib
    import apparatus as A
    w = tomllib.loads((ROOT / "system-instantiated" / "plugins" / "at" / "at-apparatus.toml").read_text())
    ok = [{**w, "hidden": {"L4": 0.14}, "horizon": 210000, "drift": {**RAMP, "at": 20000, "rate": -4.0e-7, "span": 150000}},
          {**w, "hidden": {"L4": 0.10}, "horizon": 250000, "drift": {**WALK, "at": 20000, "every": 20000, "stride": 0.008, "knots": 10}}]
    for world in ok:
        got = AC.parse_world(world, A.PARAMS, A.HIDDEN)
        assert not isinstance(got, R.Malformed), (world["drift"], got)
    out = [{**w, "hidden": {"L4": 0.14}, "drift": {**RAMP, "at": 0, "rate": -1.0e-6, "span": 150000}},       # to -0.01
           {**w, "hidden": {"L4": 0.27}, "drift": {**RAMP, "at": 0, "rate": 1.0e-7, "span": 100000}},        # past ln3/4
           {**w, "hidden": {"L4": 0.01}, "horizon": 200000,
            "drift": {**WALK, "seed": 202, "at": 0, "every": 1000, "stride": 0.01, "knots": 10}}]            # walk 202 goes down
    for world in out:
        got = AC.parse_world(world, A.PARAMS, A.HIDDEN)
        assert isinstance(got, R.Malformed) and got.field == "drift", (world["drift"], got)
    # the same out-of-domain ramp, cut to a horizon before it leaves, is accepted: the door judges the declared horizon only
    short = {**w, "hidden": {"L4": 0.14}, "horizon": 100000, "drift": {**RAMP, "at": 0, "rate": -1.0e-6, "span": 150000}}
    assert not isinstance(AC.parse_world(short, A.PARAMS, A.HIDDEN), R.Malformed)


if __name__ == "__main__":
    _tests = [test_d01_the_law_tuple_and_the_old_laws, test_d02_ramp_then_rest_is_its_expression, test_d03_the_walk_is_its_expression,
              test_d04_a_law_is_a_pure_function_of_the_index, test_d05_the_bounds_are_exact, test_d06_the_tables_are_parsed_strictly,
              test_d07_the_world_door_refuses_and_never_clamps]
    _fail = 0
    for _t in _tests:
        try:
            _t(); print(f"PASS {_t.__name__}")
        except Exception as _e:  # noqa: BLE001
            _fail += 1; print(f"FAIL {_t.__name__}: {type(_e).__name__}: {str(_e)[:300]}")
    print(f"{len(_tests) - _fail}/{len(_tests)} passed")
    sys.exit(1 if _fail else 0)
