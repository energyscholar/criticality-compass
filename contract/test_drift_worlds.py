"""Plan 1561 — the drift worlds (contract/SCHEMA-1561.md section 3). Pure unit tests, no server.
FROZEN: the Generator makes this green; it does not edit this file.

What it pins:
  w01 the worlds file is parsed strictly, the field named, in the declared order;
  w02 a parsed file keeps the declared order and the rung's override keys only;
  w03 materialise: the base with the rung's keys, the run seed, the drift as declared (a walk's path does not follow the seed);
      neither argument is changed;
  w04 to_toml reads back equal for every declared rung;
  w05 the shipped drift-worlds.toml is the declared table of SCHEMA-1561 section 3.3, rung for rung;
  w06 every declared rung, with any run seed, is a world the apparatus door accepts; and the door is what judges it.

RED until environment/drift_worlds.py and system-instantiated/plugins/at/drift-worlds.toml exist (and drift.py has the laws).
Run from the repo root:  python contract/test_drift_worlds.py   (or pytest)
"""
import copy
import json
import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "system-instantiated" / "plugins" / "at"))
AT = ROOT / "system-instantiated" / "plugins" / "at"

RUNG = {"label": "a", "severity": 1.0, "horizon": 1000, "drift": {"target": "L4", "law": "none"}}
GOOD = {"base": "at-apparatus.toml", "ladder": [{"name": "one", "rungs": [RUNG, {**RUNG, "label": "b", "severity": 2.0}]}]}


def _mods():
    from environment import apparatus_config, drift_worlds
    from navigator import reader
    return drift_worlds, apparatus_config, reader


def _with(path, value):
    d = copy.deepcopy(GOOD)
    cur = d
    for k in path[:-1]:
        cur = cur[k]
    if value is KeyError:
        del cur[path[-1]]
    else:
        cur[path[-1]] = value
    return d


def test_w01_the_file_is_parsed_strictly():
    DW, _, R = _mods()
    bad = [
        ("worlds", None), ("worlds", []), ("worlds", {"base": "at-apparatus.toml"}), ("worlds", {**GOOD, "extra": 1}),
        ("base", _with(["base"], "at-apparatus.json")), ("base", _with(["base"], "../at-apparatus.toml")),
        ("base", _with(["base"], 3)), ("base", _with(["base"], "")),
        ("ladder", _with(["ladder"], [])), ("ladder", _with(["ladder"], {"name": "one"})),
        ("ladder[0]", _with(["ladder", 0, "extra"], 1)), ("ladder[0]", _with(["ladder", 0], "one")),
        ("ladder[0].name", _with(["ladder", 0, "name"], "a b")), ("ladder[0].name", _with(["ladder", 0, "name"], 7)),
        ("ladder[0].rungs", _with(["ladder", 0, "rungs"], [])), ("ladder[0].rungs", _with(["ladder", 0, "rungs"], RUNG)),
        ("one[0]", _with(["ladder", 0, "rungs", 0], "a")),
        ("one[0].label", _with(["ladder", 0, "rungs", 0, "label"], KeyError)),
        ("one[0].severity", _with(["ladder", 0, "rungs", 0, "severity"], KeyError)),
        ("one[0].horizon", _with(["ladder", 0, "rungs", 0, "horizon"], KeyError)),
        ("one[1].drift", _with(["ladder", 0, "rungs", 1, "drift"], KeyError)),
        ("one[0].seed", _with(["ladder", 0, "rungs", 0, "seed"], 3)),
        ("one[0].burn", _with(["ladder", 0, "rungs", 0, "burn"], 3)),
        ("one[0].label", _with(["ladder", 0, "rungs", 0, "label"], "x/1")),
        ("one[0].label", _with(["ladder", 0, "rungs", 0, "label"], "x--1")),
        ("ladder[0].name", _with(["ladder", 0, "name"], "on--e")), ("base", _with(["base"], "at--apparatus.toml")),
        ("one[0].severity", _with(["ladder", 0, "rungs", 0, "severity"], 1)),
        ("one[0].severity", _with(["ladder", 0, "rungs", 0, "severity"], 0.0)),
        ("one[0].severity", _with(["ladder", 0, "rungs", 0, "severity"], float("nan"))),
        ("one[0].severity", _with(["ladder", 0, "rungs", 0, "severity"], True)),
        ("one.label", _with(["ladder", 0, "rungs", 1, "label"], "a")),
        ("one.severity", _with(["ladder", 0, "rungs", 1, "severity"], 1.0)),
        ("one.severity", _with(["ladder", 0, "rungs", 1, "severity"], 0.5)),
        ("ladder.name", _with(["ladder"], [GOOD["ladder"][0], GOOD["ladder"][0]])),
    ]
    for field, table in bad:
        got = DW.parse_worlds(table)
        assert isinstance(got, R.Malformed), f"accepted a malformed worlds table: want {field}"
        assert got.field == field, f"field {got.field!r}, want {field!r} ({got.detail})"
    # the first failure in the declared order is the one reported
    two = _with(["ladder", 0, "rungs", 0, "label"], KeyError)
    two["ladder"][0]["rungs"][0]["zzz"] = 1
    assert DW.parse_worlds(two).field == "one[0].label"
    first = _with(["ladder", 0, "rungs", 0, "severity"], -1.0)
    first["ladder"][0]["rungs"][1]["label"] = "a"
    assert DW.parse_worlds(first).field == "one[0].severity"


def test_w02_a_parsed_file_keeps_the_declared_order():
    DW, _, R = _mods()
    d = copy.deepcopy(GOOD)
    d["ladder"][0]["rungs"][1]["hidden"] = {"L4": 0.1}
    d["ladder"].append({"name": "zero", "rungs": [{**RUNG, "label": "only", "dials": []}]})
    w = DW.parse_worlds(d)
    assert isinstance(w, DW.Worlds), w
    assert w.base == "at-apparatus.toml" and [x.name for x in w.ladders] == ["one", "zero"]
    assert isinstance(w.ladders, tuple) and isinstance(w.ladders[0].rungs, tuple)
    one = DW.ladder(w, "one")
    assert [(r.label, r.severity) for r in one.rungs] == [("a", 1.0), ("b", 2.0)]
    assert one.rungs[0].table == {"horizon": 1000, "drift": {"target": "L4", "law": "none"}}
    assert one.rungs[1].table == {"horizon": 1000, "drift": {"target": "L4", "law": "none"}, "hidden": {"L4": 0.1}}
    assert DW.ladder(w, "zero").rungs[0].table["dials"] == []
    try:
        DW.ladder(w, "nope")
        raise AssertionError("an unknown ladder name was answered")
    except KeyError:
        pass


def test_w03_materialise():
    DW, _, _ = _mods()
    base = tomllib.loads((AT / "at-apparatus.toml").read_text())
    walk = {"target": "L4", "law": "walk", "at": 20000, "seed": 1561, "every": 2500, "stride": 0.008, "knots": 10}
    w = DW.parse_worlds({"base": "at-apparatus.toml", "ladder": [{"name": "w", "rungs": [
        {"label": "e2500", "severity": 8.0, "horizon": 75000, "hidden": {"L4": 0.1}, "drift": walk}]}]})
    rung = w.ladders[0].rungs[0]
    before_base, before_rung = copy.deepcopy(base), copy.deepcopy(rung.table)
    for seed in (0, 200, 219, 10 ** 9):
        got = DW.materialise(base, rung, seed)
        assert list(got) == list(base), "the base world's key order is the world's"
        assert got["seed"] == seed and got["horizon"] == 75000 and got["hidden"] == {"L4": 0.1}
        assert got["drift"] == walk and got["drift"]["seed"] == 1561, "the walk's path followed the run seed"
        for k in base:
            if k not in ("seed", "horizon", "hidden", "drift"):
                assert got[k] == base[k], k
    assert base == before_base and rung.table == before_rung, "materialise changed an argument"
    got = DW.materialise(base, rung, 200)
    got["drift"]["stride"] = 9.0
    got["dials"][0]["lo"] = -1.0
    assert rung.table["drift"]["stride"] == 0.008 and base == before_base, "a world shares a table with its rung or base"


def _declared():
    DW, _, R = _mods()
    w = DW.parse_worlds(tomllib.loads((AT / "drift-worlds.toml").read_text()))
    assert isinstance(w, DW.Worlds), f"the shipped drift-worlds.toml is refused: {w}"
    return DW, w


def test_w04_to_toml_reads_back_equal():
    DW, w = _declared()
    base = tomllib.loads((AT / w.base).read_text())
    for lad in w.ladders:
        for rung in lad.rungs:
            for seed in (200, 219):
                world = DW.materialise(base, rung, seed)
                text = DW.to_toml(world)
                assert tomllib.loads(text) == world, (lad.name, rung.label)
                assert [ln.split(" = ")[0] for ln in text.splitlines()] == list(world), "one top-level key per line, in order"
    odd = {"seed": 1, "horizon": 1000, "x": 1.0, "rate": 3 * 4.0e-7, "tiny": 1e-300, "name": 'a "quoted" \\ name',
           "drift": {"target": "L4", "law": "linear", "rate": -1.2000000000000002e-06}, "dials": [{"name": "K", "lo": 0.2, "T": 700}]}
    back = tomllib.loads(DW.to_toml(odd))
    assert json.dumps(back, sort_keys=True) == json.dumps(odd, sort_keys=True), "to_toml is not exact: every float and its type, every string"


def _expect():
    """SCHEMA-1561 section 3.3, written out independently of the shipped file."""
    dial = [{"name": "K", "lo": 0.20, "hi": 0.375, "T": 700, "max_nudge": 32, "start": 0}]
    E = {}
    for name, l4, sign in (("ramp", 0.14, -1), ("ramp-reversed", 0.08, 1)):
        E[name] = [(f"x{m}", float(m), 60000 + 150000 // m, {"L4": l4}, None,
                    {"target": "L4", "law": "ramp-then-rest", "at": 20000, "rate": sign * 4.0e-7 * m, "span": 150000 // m})
                   for m in (1, 2, 3, 4, 6, 8, 12)]
    E["ramp-edge"] = [("x1", 1.0, 210000, {"L4": 0.14}, dial,
                       {"target": "L4", "law": "ramp-then-rest", "at": 20000, "rate": -4.0e-7, "span": 150000})]
    E["sine"] = [(f"P{p}", 800000 / p, 150000, {"L4": 0.10}, None, {"target": "L4", "law": "sine", "amp": 0.04, "period": p})
                 for p in (800000, 400000, 200000, 100000, 50000)]
    E["step"] = [(f"J{j}", j / 4, 100000, {"L4": 0.10}, None, {"target": "L4", "law": "step", "at": 40000, "size": -j / 1000})
                 for j in (4, 8, 12, 16, 24, 40)]
    E["step-reversed"] = [(f"J{j}", j / 4, 100000, {"L4": 0.10}, None, {"target": "L4", "law": "step", "at": 40000, "size": j / 1000})
                          for j in (8, 12, 16, 24)]
    E["walk"] = [(f"e{e}", 20000 / e, 50000 + 10 * e, {"L4": 0.10}, None,
                  {"target": "L4", "law": "walk", "at": 20000, "seed": 1561, "every": e, "stride": 0.008, "knots": 10})
                 for e in (20000, 10000, 6000, 4000, 2500, 1500)]
    return E


def test_w05_the_shipped_ladders_are_the_declared_table():
    DW, w = _declared()
    E = _expect()
    assert w.base == "at-apparatus.toml"
    assert [x.name for x in w.ladders] == list(E), [x.name for x in w.ladders]
    for lad in w.ladders:
        assert len(lad.rungs) == len(E[lad.name]), lad.name
        for rung, (label, sev, horizon, hidden, dials, drift) in zip(lad.rungs, E[lad.name]):
            assert rung.label == label and abs(rung.severity - sev) < 1e-12, (lad.name, rung.label, rung.severity, sev)
            assert rung.table["horizon"] == horizon and rung.table["hidden"] == hidden, (lad.name, label)
            assert rung.table.get("dials") == dials, (lad.name, label)
            got = rung.table["drift"]
            assert set(got) == set(drift), (lad.name, label, got)
            for k, v in drift.items():
                assert (abs(got[k] - v) <= 1e-12 * abs(v)) if isinstance(v, float) else got[k] == v, (lad.name, label, k, got[k], v)
                assert type(got[k]) is type(v), (lad.name, label, k)


def test_w06_every_declared_rung_is_an_accepted_world():
    DW, w = _declared()
    _, AC, R = _mods()
    import apparatus as A
    base = tomllib.loads((AT / w.base).read_text())
    for lad in w.ladders:
        for rung in lad.rungs:
            for seed in (200, 210, 219, 0):
                got = AC.parse_world(DW.materialise(base, rung, seed), A.PARAMS, A.HIDDEN)
                assert not isinstance(got, R.Malformed), (lad.name, rung.label, seed, got)
    # the door, not drift_worlds, judges a rung: an out-of-domain rung parses as a rung and is refused as a world
    far = DW.parse_worlds({"base": "at-apparatus.toml", "ladder": [{"name": "far", "rungs": [
        {"label": "x", "severity": 1.0, "horizon": 200000, "hidden": {"L4": 0.14},
         "drift": {"target": "L4", "law": "ramp-then-rest", "at": 0, "rate": -1.0e-6, "span": 200000}}]}]})
    assert isinstance(far, DW.Worlds), far
    got = AC.parse_world(DW.materialise(base, far.ladders[0].rungs[0], 1), A.PARAMS, A.HIDDEN)
    assert isinstance(got, R.Malformed) and got.field == "drift", got


if __name__ == "__main__":
    _tests = [test_w01_the_file_is_parsed_strictly, test_w02_a_parsed_file_keeps_the_declared_order, test_w03_materialise,
              test_w04_to_toml_reads_back_equal, test_w05_the_shipped_ladders_are_the_declared_table,
              test_w06_every_declared_rung_is_an_accepted_world]
    _fail = 0
    for _t in _tests:
        try:
            _t(); print(f"PASS {_t.__name__}")
        except Exception as _e:  # noqa: BLE001
            _fail += 1; print(f"FAIL {_t.__name__}: {type(_e).__name__}: {str(_e)[:300]}")
    print(f"{len(_tests) - _fail}/{len(_tests)} passed")
    sys.exit(1 if _fail else 0)
