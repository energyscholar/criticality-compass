"""Plan 1552 — stage 5a-N acceptance: the hold needle `hold-pair-v1` (contract/SCHEMA-1552.md), as a black box. Each test runs
the needle as a separate process against the scripted apparatus of contract/holdwire.py and holds it to what it sent on the
wire, what it wrote on stdout and what it appended to its map. FROZEN: the Generator makes this green; it does not edit it.

What it pins:
  h01  a settings file outside its declared domain is refused before the wire is touched (parse B), M and sigma included;
  h02  a declaration the needle cannot serve is refused after `declare` and before anything else (parse A);
  h03  the start record and the map head: the frozen nine keys, the settings verbatim, belief only from the declaration;
  h04  the settle time is the needle's own setting; a reading taken while the dial is in transit (by the needle's lag model,
       from the declared lag) is marked `settled: false` in the stream and is an `in-transit` place in the map;
  h05  ignition: tick grids, the margin, the bracket rule, and a round with no bracket ignites again;
  h06  the approach: whole strides of max_nudge at the cheapest legal reading, then the probe;
  h07  the hold table, FEEDBACK ON: all nine cells, steered by the SIGN of the pair and never by its size, and the centre
       moves by exactly the table's ticks before every pair;
  h08  the dial's end: no clamp and no refused call; the range kind ends the stream with OFF-DIAL;
  h09  FEEDBACK OFF: the client holds no nudge, sends none, and never moves its centre, whatever the readings say;
  h10  lost: `lost` consecutive no-signal steps ignite again (ON); a broken run of them does not;
  h11  the horizon: the wire's refusal is a step with no reading, the last step, outcome HORIZON;
  h12  isolation, static: the needle's three modules import only the allowlist, open exactly the settings and the map, and
       name no truth;
  h13  isolation, dynamic: truth files beside the map change nothing, byte for byte;
  h14  live: the start record and the map head are out before the first reading is answered; each step before the next call;
  h15  the map: exactly one place per reading served, with the wire's own numbers, its index, and a state that follows;
  h16  the kernel values beside the verdicts are A and B of cc/kernel.py over the declared path; R is NOT EVALUATED;
  h17  the opposite orientation steers the same way;
  h18  the tables are total (navigator.holdtab);
  h19  the five shipped settings files hold the declared numbers, and the older needle and reader files are byte-identical.

RED until `navigator/hold.py` exists (the subprocess exits at once: no such module).
Run from the repo root:  python contract/test_hold_needle.py   (or pytest)
"""
import ast
import hashlib
import json
import subprocess
import sys
import threading
import tomllib
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import holdwire as W  # noqa: E402

ROOT = W.ROOT
G, STEP = 12, 6
START_KEYS = {"rec", "schema", "needle", "settings", "mode", "sigma", "dials", "belief", "declared_other"}
SLOTS = ("knobs_K", "ordered_side", "L", "tau", "k", "index_unit", "index_kind", "observable", "nlev", "system", "roles")
COMMON = {"segment", "pos", "window", "values", "errors", "settled", "classes", "kernel"}
PLACE_KEYS = {"rec", "drop", "seq", "dial", "tick", "value", "index", "window", "readings", "class", "settled", "state", "call", "kernel"}
FROZEN = {
    "navigator/steer.py": "229dbad1443291db8f49de5961f5e5fdf7324e64ca6c2720c3648f4b0676ccf5", "navigator/report2.py": "2658a7f9dbae33de982ed066021c5f7f9cf1541635aa6740f4459693401e1a31", "navigator/recover2.py": "d150ad30e686f3eec2e27cd7288cabc246c40de9bdca1dd5bc2cf89d1b79fb0e",
    "navigator/reader.py": "0f655fbfcc0cb4be7f9bd7ed89c9e94222830968d148f57d1f59a1194cfd54f8", "navigator/estimate.py": "00df2977cf05d2f26fa8de82b7a6fff25ca2d58e9ef04b89cb8fe8d3269a6ea5", "needlestream/read.py": "ccfaceb6a7c0a87641869a944f86ed2ec4bfe8d6137a2b0dfaa22ad3ef86e3b9",
    "contract/SCHEMA-1533.md": "9e279395da6f20bb0238b6e34b36cbdad44260d057037498d272e9e883af54d9",      # the apparatus files are plan 1545 A1's to amend
}
ALLOWED_IMPORTS = {"argparse", "json", "socket", "sys", "tomllib", "dataclasses", "navigator"}
BANNED = ("truth", "edge.json", "K_c", "drift", "hidden", "L4", "vendor", "plugins", "system-instantiated", "run_dir", "environ", "perf")
SHORT = {"horizon": 60000}          # a short world: ignition, then about 25 hold steps


def with_cfg(**over):
    return {**W.CFG, **over}


def refusal(got):
    return got.err.strip().splitlines()[-1] if got.err.strip() else ""


def pairs_of(got):
    return [s for s in got.steps if s["phase"] == "hold" and s["evaluated"]]


# ---------------------------------------------------------------- refusals
def test_h01_settings_outside_their_domain_are_refused_before_the_wire(tmp):
    no_m = {k: v for k, v in W.CFG.items() if k != "M"}
    cases = [
        ("M", no_m), ("extra", with_cfg(extra=1)), ("sigma", with_cfg(sigma=1)), ("sigma", with_cfg(sigma=-1)),
        ("ops", with_cfg(ops=["declare", "nudge"])), ("ops", with_cfg(ops=["declare", "scan", "nudge", "read"])),
        ("ops", with_cfg(ops=["scan", "declare"])), ("z", with_cfg(z=2)), ("g", with_cfg(g=0)), ("g", with_cfg(g=12.0)),
        ("step", with_cfg(step=0)), ("S", with_cfg(S=39)), ("lost", with_cfg(lost=0)),
        ("ignite", with_cfg(ignite={"steps": [100, 30], "S": 100, "margin": 1, "n_eq": 450})),
        ("ignite", with_cfg(ignite={"steps": [100, 25], "S": 100, "margin": 1, "n_eq": 450})),
        ("ignite", with_cfg(ignite={"steps": [], "S": 100, "margin": 1, "n_eq": 450})),
        ("ignite", with_cfg(ignite={"steps": [100, 20], "S": 100, "margin": 1})),           # the settle time is a declared choice: no default
        ("ignite", with_cfg(ignite={"steps": [100, 20], "S": 100, "margin": 1, "n_eq": -1})),
        ("approach", with_cfg(approach={"S": 39, "n_eq": 48})), ("approach", with_cfg(approach={"S": 40})),
        ("n_eq", with_cfg(n_eq=-1)), ("n_eq", with_cfg(n_eq=450.0)),
        ("n_eq", {k: v for k, v in W.CFG.items() if k != "n_eq"}),                          # the hold mode is a declared choice: NEITHER mode is a default
        ("needle_structure", with_cfg(needle_structure="recover-adaptive-v1")),
        ("M", with_cfg(M={**W.CFG["M"], "transform": "detrend"})), ("M", with_cfg(M={**W.CFG["M"], "rho_base": "1.0"})),
        ("M", with_cfg(M={**W.CFG["M"], "chi_0": "1.0"})), ("M", with_cfg(M={**W.CFG["M"], "relation": "ring"})),
        ("M", with_cfg(M={k: v for k, v in W.CFG["M"].items() if k != "direction"})),
        ("M", with_cfg(M={**W.CFG["M"], "provenance": ""})),
    ]
    for n, (field, cfg) in enumerate(cases):
        got = W.drop(tmp, W.sign_world(603.5), cfg, name=f"c{n}", map_name=f"m{n}.jsonl", **SHORT)
        assert got.rc == 2 and refusal(got) == f"RefusedToStart field={field} parse=B", (n, field, got.rc, got.err[-300:])
        assert got.out == "" and got.map is None and got.fake.requests == [], (n, field, got.out[:100], got.fake.requests)


def test_h02_a_declaration_it_cannot_serve_is_refused_after_declare(tmp):
    two = [{"name": "K", "lo": 0.2, "hi": 0.5, "T": 1200, "max_nudge": 32}, {"name": "J", "lo": 0.0, "hi": 1.0, "T": 100, "max_nudge": 8}]
    cases = [
        ("wire", {"declared": {"wire": "compass-apparatus/2"}}), ("dials", {"declared": {"dials": two}}), ("dials", {"declared": {"dials": []}}),
        ("roles", {"declared": {"roles": [{"name": "C", "role": "peak"}]}}),
        ("M", {"declared": {"roles": [{"name": "Q", "role": "crossing", "ordered_sign": "+"}, {"name": "C", "role": "peak"}]}}),
        ("ordered_side", {"declared": {"ordered_side": {"K": "?"}}}), ("ordered_side", {"declared": {"ordered_side": {}}}),
        ("ordered_side", {"declared": {"roles": [{"name": "D", "role": "crossing"}, {"name": "C", "role": "peak"}]}}),
        ("g", {"max_nudge": 29}), ("g", {"max_nudge": 23}), ("ignite", {"T": 1250}), ("declared", {"declared": {"extra": 1}}),
        ("numbers", {"declared": {"lag": "48"}}), ("numbers", {"declared": {"lag": True}}), ("numbers", {"declared": {"horizon": 60000.5}}),
        ("numbers", {"declared": {"dials": [{"name": "K", "lo": 0.2, "hi": 0.5, "T": 1200.0, "max_nudge": 32}]}}),
        ("numbers", {"declared": {"dials": [{"name": "K", "lo": 0.5, "hi": 0.2, "T": 1200, "max_nudge": 32}]}}),
        ("numbers", {"declared": {"tau": None}}), ("numbers", {"declared": {"k": 6.0}}),
        ("roles", {"declared": {"roles": [{"name": "D", "role": "crossing", "ordered_sign": "+"}, {"name": "D", "role": "peak"}]}}),
    ]
    for n, (field, world) in enumerate(cases):
        got = W.drop(tmp, W.sign_world(603.5), name=f"d{n}", map_name=f"m{n}.jsonl", **{**SHORT, **world})
        assert got.rc == 2 and refusal(got) == f"RefusedToStart field={field} parse=A", (n, field, got.rc, got.err[-300:])
        assert got.out == "" and got.map is None and got.fake.requests == [{"op": "declare"}], (n, field, got.fake.requests[:3])
    ok = W.drop(tmp, W.sign_world(603.5), name="ok", map_name="ok.jsonl", horizon=20000, max_nudge=30)   # 2g + step = 30 is served
    assert ok.rc == 0 and ok.steps, (ok.rc, ok.err[-200:])


# ---------------------------------------------------------------- the start record, the floor
def test_h03_the_start_record_and_the_map_head(tmp):
    got = W.drop(tmp, W.sign_world(603.5), **SHORT)
    assert got.rc == 0, got.err[-300:]
    s = got.records[0]
    assert set(s) == START_KEYS and s["rec"] == "start" and s["schema"] == "compass-report/2" and s["needle"] == "hold-pair-v1", s
    assert s["settings"] == W.CFG, s["settings"]
    assert s["mode"] == {"ops": ["declare", "scan", "nudge"], "feedback": "ON"}, s["mode"]
    assert s["sigma"] == {"offset": 0, "unit": "g", "measured": "pair-half-width"}, s["sigma"]
    assert s["dials"] == ["K"], s["dials"]
    d = got.fake.declared
    declared = {k: {"declared": d[k]} for k in ("ordered_side", "L", "tau", "k", "index_unit", "index_kind", "roles")}
    assert s["belief"] == {k: declared.get(k, "unknown") for k in SLOTS}, s["belief"]
    assert s["declared_other"] == {k: d[k] for k in ("wire", "dials", "pos", "fixed", "index", "horizon", "lag", "clock")}, s["declared_other"]
    h = got.entries[0]
    assert h == {"rec": "head", "map": "compass-map/1", "drop": "t", "needle": "hold-pair-v1",
                 "dial": {"name": "K", "lo": 0.2, "hi": 0.5, "T": 1200}, "start": {"tick": 0, "index": 0},
                 "clock": {"index_unit": "sweep", "index_kind": "sample_counter", "clock": "algorithmic (Swendsen-Wang)", "lag": 48, "k": 6, "tau": 67.0},
                 "n_eq": {"ignite": 450, "approach": 48, "hold": 450}, "skip": 1, "roles": ["C", "D"],
                 "sign_rule": {"observable": "D", "z": 2.0, "ordered_sign": "+", "ordered_side": "+"}, "M": W.CFG["M"]}, h
    assert [r["rec"] for r in got.records] == ["start"] + ["step"] * len(got.steps) + ["outcome"]
    assert [x["step"] for x in got.steps] == list(range(1, len(got.steps) + 1))


def _marks(got):
    return [(s["phase"], f) for s in got.steps for p in [s[{"ignite": "grid", "approach": "leg", "hold": "pair"}[s["phase"]]]] if p for f in p["settled"]]


def test_h04_the_settle_time_is_the_needles_choice_and_a_mid_move_reading_is_marked(tmp):
    """the wire accepts n_eq below the declared lag (plan 1545 A1). The needle models the lag from the DECLARED lag alone: a
    reading is settled exactly when its first sample comes more than `lag` after the dial was commanded to that tick."""
    hz = {"horizon": 11550 + 3 * 88 + 6 * 1900}
    shipped = W.drop(tmp, W.sign_world(603.5), **hz)
    assert all(f for _, f in _marks(shipped)) and all(e["settled"] is True for e in shipped.entries[1:]), "a settled run marks a reading mid-move"
    assert "in-transit" not in {e["state"] for e in shipped.entries[1:]}
    for n_eq, want in ((0, False), (47, False), (48, True)):                          # the declared lag is 48
        got = W.drop(tmp, W.sign_world(603.5), with_cfg(n_eq=n_eq), name=f"n{n_eq}", map_name=f"n{n_eq}.jsonl", **hz)
        hold = [s for s in got.steps if s["phase"] == "hold" and s["evaluated"]]
        assert got.rc == 0 and len(hold) >= 6 and got.fake.refused == 1, (n_eq, got.rc, len(hold), got.fake.refused)      # only the horizon refuses
        assert all(m["n_eq"] == n_eq for m in got.measured if m["op"] == "nudge" and m["S"] == 500), n_eq
        assert all(s["pair"]["settled"] == [want, want] for s in hold), (n_eq, hold[0]["pair"]["settled"])
        assert all(f for ph, f in _marks(got) if ph != "hold"), n_eq                                    # the other phases keep their own choice
        places = [e for e in got.entries[1:] if e["call"]["phase"] == "hold"]
        assert all(e["settled"] is want and (e["state"] == "in-transit") is (not want) for e in places), (n_eq, places[0])
        assert W.kinds(got, "hold")[:6] == ["stay"] * 6 and [s["pair"]["classes"] for s in hold][:2] == [["SIG-", "SIG+"]] * 2, n_eq   # it still steers on them
    ig = W.drop(tmp, W.sign_world(603.5), with_cfg(ignite={"steps": [100, 20], "S": 100, "margin": 1, "n_eq": 0}, approach={"S": 40, "n_eq": 0}),
                name="ig", map_name="ig.jsonl", **hz)
    marks = _marks(ig)
    assert marks[:13] == [("ignite", True)] + [("ignite", False)] * 12, marks[:13]      # the dial starts at tick 0: the first reading moved nothing
    assert [f for ph, f in marks if ph == "approach"] == [False] * 3 and all(f for ph, f in marks if ph == "hold"), marks[21:26]
    assert [e["state"] for e in ig.entries[1:3]] == ["disordered-side", "in-transit"], [e["state"] for e in ig.entries[1:3]]
    assert ig.measured[0]["n_eq"] == 0 and ig.measured[2] == {"op": "nudge", "d": [-32], "n_eq": 0, "S": 40, "skip": 1}, ig.measured[2]
    nolag = W.drop(tmp, W.sign_world(603.5), with_cfg(n_eq=0), name="nolag", map_name="nolag.jsonl", lag=0, **hz)
    assert all(f for _, f in _marks(nolag)), "with no declared lag nothing is mid-move"
    short = W.drop(tmp, W.sign_world(603.5), with_cfg(n_eq=0, S=40, ops=W.OFF_OPS), name="short", map_name="short.jsonl", horizon=11550 + 400)
    assert [s["pair"]["settled"] for s in short.steps if s["phase"] == "hold" and s["evaluated"]] == [[False, False]] * 5
    assert short.entries[0]["clock"]["lag"] == 48 and short.records[0]["declared_other"]["lag"] == 48


# ---------------------------------------------------------------- ignition, approach
def test_h05_ignition(tmp):
    got = W.drop(tmp, W.sign_world(603.5), **SHORT)
    r1, r2 = got.measured[0], got.measured[1]
    assert r1 == {"op": "scan", "ticks": [[t] for t in range(0, 1201, 100)], "n_eq": 450, "S": 100, "skip": 1}, r1
    assert r2 == {"op": "scan", "ticks": [[t] for t in range(580, 721, 20)], "n_eq": 450, "S": 100, "skip": 1}, r2   # [600, 700] and one margin step
    s1, s2 = got.steps[0], got.steps[1]
    for n, s, lo, hi, cls in ((1, s1, 600, 700, ["SIG-"] * 7 + ["SIG+"] * 6), (2, s2, 600, 620, ["SIG-"] * 2 + ["SIG+"] * 6)):
        assert set(s) == {"rec", "step", "phase", "index", "evaluated", "verdict", "grid"} and s["phase"] == "ignite" and s["evaluated"] is True, s
        g = s["grid"]
        assert set(g) == COMMON | {"round", "lo", "hi"} and (g["segment"], g["round"], g["lo"], g["hi"]) == (1, n, lo, hi), g
        assert g["classes"] == cls and s["verdict"] == [{"kind": "bracketed", "reason": "|".join(cls), "dial": "K", "ticks": None}], s["verdict"]
        assert s["index"] == g["window"][-1][1] == got.fake.replies[n]["index"], (s["index"], g["window"][-1])
        assert g["pos"] == [p[0] for p in got.fake.replies[n]["pos"]] and g["values"] == got.fake.replies[n]["values"] and g["errors"] == got.fake.replies[n]["errors"]
    assert pairs_of(got)[0]["pair"]["centre"] == 610, pairs_of(got)[0]["pair"]
    # unresolved readings are set aside: a zero reading beside the crossing widens the bracket, it does not break it
    wide = W.drop(tmp, lambda t, i, n: 0.0 if t == 600 else (0.3 if t > 603.5 else -0.3), name="wide", map_name="wide.jsonl", **SHORT)
    assert (wide.steps[0]["grid"]["lo"], wide.steps[0]["grid"]["hi"]) == (500, 700) and wide.steps[0]["verdict"][0]["kind"] == "bracketed", wide.steps[0]["grid"]
    assert wide.measured[1]["ticks"] == [[t] for t in range(480, 721, 20)], wide.measured[1]
    # no bracket: the classes are not one run of SIG- then one run of SIG+ -> the needle ignites again, from round 1
    for name, f in (("flat", lambda t, i, n: 0.0 if n < 1 else (0.3 if t > 603.5 else -0.3)),
                    ("all-minus", lambda t, i, n: -0.3 if n < 1 else (0.3 if t > 603.5 else -0.3)),
                    ("all-plus", lambda t, i, n: 0.3 if n < 1 else (0.3 if t > 603.5 else -0.3)),
                    ("contradiction", lambda t, i, n: (0.3 if t in (200, 900) else -0.3) if n < 1 else (0.3 if t > 603.5 else -0.3)),
                    ("round-2", lambda t, i, n: 0.0 if n == 1 else (0.3 if t > 603.5 else -0.3))):
        again = W.drop(tmp, f, name=name, map_name=f"{name}.jsonl", **SHORT)
        k = 2 if name == "round-2" else 1
        s = again.steps[k - 1]
        assert s["verdict"][0]["kind"] == "no-bracket" and s["verdict"][0]["ticks"] is None and (s["grid"]["lo"], s["grid"]["hi"]) == (None, None), (name, s["verdict"])
        nxt = again.steps[k]
        assert nxt["phase"] == "ignite" and (nxt["grid"]["segment"], nxt["grid"]["round"]) == (2, 1), (name, nxt["grid"]["segment"], nxt["grid"]["round"])
        assert again.measured[k]["ticks"] == [[t] for t in range(0, 1201, 100)], (name, again.measured[k])
        assert pairs_of(again) and pairs_of(again)[0]["pair"]["segment"] == 2, name


def test_h06_the_approach(tmp):
    got = W.drop(tmp, W.sign_world(603.5), **SHORT)             # after round 2 the dial is at 720; the low probe is 610 - 12 = 598
    legs = [s for s in got.steps if s["phase"] == "approach"]
    assert [m for m in got.measured[2:5]] == [{"op": "nudge", "d": [-32], "n_eq": 48, "S": 40, "skip": 1}] * 3, got.measured[2:5]
    assert len(legs) == 3 and [s["step"] for s in legs] == [3, 4, 5], [s["step"] for s in legs]
    for j, s in enumerate(legs):
        assert set(s) == {"rec", "step", "phase", "index", "evaluated", "verdict", "leg"} and set(s["leg"]) == COMMON | {"d"}, s
        assert s["verdict"] == [{"kind": "moving", "reason": "stride", "dial": "K", "ticks": -32}] and s["leg"]["d"] == -32, s["verdict"]
        assert s["leg"]["pos"] == [720 - 32 * (j + 1)] and s["leg"]["segment"] == 1, s["leg"]["pos"]
    assert got.measured[5] == {"op": "nudge", "d": [-26], "n_eq": 450, "S": 500, "skip": 1}, got.measured[5]      # 624 -> 598
    assert got.measured[6] == {"op": "nudge", "d": [24], "n_eq": 450, "S": 500, "skip": 1}, got.measured[6]
    near = W.drop(tmp, W.sign_world(783.5), name="near", map_name="near.jsonl", max_nudge=64, **SHORT)             # bracket [780, 800], dial at 820, low probe 778
    assert [s for s in near.steps if s["phase"] == "approach"] == [], "a move of 42 ticks with strides of 64 has no whole stride"
    assert near.measured[2] == {"op": "nudge", "d": [-42], "n_eq": 450, "S": 500, "skip": 1} and near.steps[2]["phase"] == "hold", near.measured[2]
    one = W.drop(tmp, W.sign_world(783.5), name="one", map_name="one.jsonl", **SHORT)                               # the same with strides of 32: one stride, then 10
    assert [m["d"][0] for m in one.measured[2:5]] == [-32, -10, 24] and [s["phase"] for s in one.steps[2:4]] == ["approach", "hold"], one.measured[2:5]


# ---------------------------------------------------------------- the hold
CELLS = [        # (D at the low probe, D at the high probe, kind, ticks ON). The sizes disagree with the signs on purpose.
    (-0.30, 0.30, "stay", 0, "SIG-|SIG+"),
    (-0.10, -0.50, "raise", STEP, "SIG-|SIG-"),          # the smaller |D| is at the LOW probe: a needle steering on |D| goes down
    (-0.30, 0.00, "raise", STEP, "SIG-|UNRES"),
    (0.50, 0.10, "lower", -STEP, "SIG+|SIG+"),           # the smaller |D| is at the HIGH probe: a needle steering on |D| goes up
    (0.00, 0.30, "lower", -STEP, "UNRES|SIG+"),
    (0.00, 0.00, "no-signal", 0, "UNRES|UNRES"),
    (-0.30, 0.30, "stay", 0, "SIG-|SIG+"),               # breaks the run of no-signal
    (0.00, -0.30, "no-signal", 0, "UNRES|SIG-"),
    (0.30, 0.00, "no-signal", 0, "SIG+|UNRES"),
    (-0.30, 0.30, "stay", 0, "SIG-|SIG+"),
    (0.30, -0.30, "no-signal", 0, "SIG+|SIG-"),
    (-0.02, 0.02, "no-signal", 0, "UNRES|UNRES"),        # |D| = 2 * err exactly: the interval holds 0
    (-0.021, 0.021, "stay", 0, "SIG-|SIG+"),
]


def cell_world(first, cells=CELLS):
    """ignition and approach on a sign world; from measured call `first` on, pair j reads cells[j] (low probe, then high)."""
    def f(tick, index, n):
        if n < first:
            return 0.3 if tick > 603.5 else -0.3
        j = (n - first) // 2
        return cells[j % len(cells)][(n - first) % 2]
    return f


def test_h07_the_hold_table_feedback_on(tmp):
    got = W.drop(tmp, cell_world(5), horizon=11550 + 3 * 88 + len(CELLS) * 1900)      # ignition 7150 + 4400, three strides, 13 pairs
    hold = pairs_of(got)
    assert len(hold) == len(CELLS), (len(hold), got.records[-1])
    centre, streak, nudges = 610, 0, [m for m in got.measured[5:]]
    for j, (s, (d_lo, d_hi, kind, ticks, why)) in enumerate(zip(hold, CELLS)):
        p = s["pair"]
        assert set(s) == {"rec", "step", "phase", "index", "evaluated", "verdict", "pair"}, sorted(s)
        assert set(p) == COMMON | {"n", "centre", "setpoint", "bracket", "streak"}, sorted(p)
        streak = streak + 1 if kind == "no-signal" else 0
        assert s["verdict"] == [{"kind": kind, "reason": why, "dial": "K", "ticks": ticks}], (j, s["verdict"], kind, ticks)
        assert (p["n"], p["centre"], p["setpoint"], p["bracket"], p["pos"], p["streak"], p["segment"]) == \
            (j + 1, centre, centre, [centre - G, centre + G], [centre - G, centre + G], streak, 1), (j, p)
        assert p["values"]["D"] == [d_lo, d_hi] and p["classes"] == why.split("|"), (j, p["values"], p["classes"])
        lo_call, hi_call = nudges[2 * j], nudges[2 * j + 1]
        assert hi_call == {"op": "nudge", "d": [2 * G], "n_eq": 450, "S": 500, "skip": 1}, (j, hi_call)
        if j:
            assert lo_call == {"op": "nudge", "d": [-2 * G + CELLS[j - 1][3]], "n_eq": 450, "S": 500, "skip": 1}, (j, lo_call)
        assert s["index"] == p["window"][1][1] and len(p["window"]) == 2, (j, s["index"], p["window"])
        centre += ticks
    assert got.fake.refused == 1 and got.records[-1]["kind"] == "HORIZON", (got.fake.refused, got.records[-1])


def test_h08_the_dials_end_no_clamp(tmp):
    lower = lambda t, i, n: (0.3 if t > 30 else -0.3) if n < 2 else 0.3          # ignition finds the crossing at 30; then always SIG+|SIG+
    got = W.drop(tmp, lower, **SHORT)
    hold = pairs_of(got)
    assert (got.steps[1]["grid"]["lo"], got.steps[1]["grid"]["hi"]) == (20, 40) and got.measured[1]["ticks"] == [[t] for t in range(0, 121, 20)], got.steps[1]["grid"]
    assert [s["pair"]["centre"] for s in hold] == [30, 24, 18, 12], [s["pair"]["centre"] for s in hold]
    assert [s["verdict"][0]["kind"] for s in hold] == ["lower", "lower", "lower", "range-low"], W.kinds(got, "hold")
    assert [s["verdict"][0]["ticks"] for s in hold] == [-6, -6, -6, 0], [s["verdict"][0]["ticks"] for s in hold]
    assert got.steps[-1] is hold[-1] and got.records[-1]["kind"] == "OFF-DIAL" and got.records[-1]["reason"] == "range-low", got.records[-1]
    assert got.fake.refused == 0 and got.measured[-1] == {"op": "nudge", "d": [24], "n_eq": 450, "S": 500, "skip": 1}, (got.fake.refused, got.measured[-1])
    assert min(r["tick"] for r in got.fake.readings if r["op"] == "nudge") == 0 and all(m["d"][0] in (-32, -30, -6, 24) for m in got.measured[2:]), got.measured[2:]
    raise_ = lambda t, i, n: (0.3 if t > 1170 else -0.3) if n < 2 else -0.3     # the same at the high end
    up = W.drop(tmp, raise_, name="up", map_name="up.jsonl", **SHORT)
    hold = pairs_of(up)
    assert [s["pair"]["centre"] for s in hold] == [1170, 1176, 1182, 1188] and W.kinds(up, "hold")[-1] == "range-high", ([s["pair"]["centre"] for s in hold], W.kinds(up, "hold"))
    assert up.records[-1]["kind"] == "OFF-DIAL" and up.records[-1]["reason"] == "range-high" and up.fake.refused == 0, up.records[-1]
    off = W.drop(tmp, lower, with_cfg(ops=W.OFF_OPS), name="off", map_name="off.jsonl", horizon=30000)   # OFF moves nothing, so it never leaves
    assert set(W.kinds(off, "hold")) == {"lower", "no-reading"} and off.records[-1]["kind"] == "HORIZON", (W.kinds(off, "hold"), off.records[-1])


def test_h09_feedback_off_never_moves_the_centre(tmp):
    rising = W.sign_world(lambda index: 603.5 + max(0, index - 11550) / 190.0)       # the crossing climbs 10 ticks per hold step
    got = W.drop(tmp, rising, with_cfg(ops=W.OFF_OPS), horizon=11550 + 12 * 1900)
    assert got.rc == 0 and got.records[0]["mode"] == {"ops": ["declare", "scan"], "feedback": "OFF"}, (got.rc, got.records[0]["mode"])
    assert all(m["op"] == "scan" for m in got.measured), sorted({m["op"] for m in got.measured})
    assert not [s for s in got.steps if s["phase"] == "approach"]
    hold = pairs_of(got)
    assert len(hold) == 12 and all(m == {"op": "scan", "ticks": [[598], [622]], "n_eq": 450, "S": 500, "skip": 1} for m in got.measured[2:14]), got.measured[2:5]
    assert all(s["pair"]["centre"] == 610 and s["pair"]["setpoint"] == 610 and s["verdict"][0]["ticks"] == 0 for s in hold)
    assert W.kinds(got, "hold")[:12] == ["stay"] + ["raise"] * 11, W.kinds(got, "hold")
    on = W.drop(tmp, rising, name="on", map_name="on.jsonl", horizon=11550 + 3 * 88 + 12 * 1900)      # the same world, ON: the centre follows
    assert [s["pair"]["centre"] for s in pairs_of(on)][-1] > 650, [s["pair"]["centre"] for s in pairs_of(on)]
    dark = lambda t, i, n: (0.3 if t > 603.5 else -0.3) if n < 2 else 0.0                              # OFF never ignites again either
    lost = W.drop(tmp, dark, with_cfg(ops=W.OFF_OPS), name="dark", map_name="dark.jsonl", horizon=11550 + 8 * 1900)
    assert W.kinds(lost, "hold")[:8] == ["no-signal"] * 8 and [s["pair"]["streak"] for s in pairs_of(lost)] == list(range(1, 9)), W.kinds(lost, "hold")
    assert len([s for s in lost.steps if s["phase"] == "ignite"]) == 2


def test_h10_lost_ignites_again(tmp):
    cells = [(-0.3, 0.3), (0.0, 0.0), (0.0, 0.0), (-0.3, 0.3), (0.0, 0.0), (0.0, 0.0), (0.0, 0.0)]
    def f(tick, index, n):
        if n < 5 or n >= 5 + 2 * len(cells):
            return 0.3 if tick > 603.5 else -0.3
        return cells[(n - 5) // 2][(n - 5) % 2]
    got = W.drop(tmp, f, **SHORT)
    hold = pairs_of(got)
    assert [s["pair"]["streak"] for s in hold[:7]] == [0, 1, 2, 0, 1, 2, 3], [s["pair"]["streak"] for s in hold[:7]]
    nxt = got.steps[hold[6]["step"]]
    assert nxt["phase"] == "ignite" and (nxt["grid"]["segment"], nxt["grid"]["round"]) == (2, 1), nxt
    assert got.measured[5 + 14]["ticks"] == [[t] for t in range(0, 1201, 100)], got.measured[19]
    assert hold[7]["pair"]["segment"] == 2 and hold[7]["pair"]["n"] == 1 and hold[7]["pair"]["streak"] == 0, hold[7]["pair"]
    two = W.drop(tmp, f, with_cfg(lost=2), name="two", map_name="two.jsonl", **SHORT)
    assert got.steps[4 + 3]["phase"] == "hold" and two.steps[5 + 3]["phase"] == "ignite", (got.steps[7]["phase"], two.steps[8]["phase"])


def test_h11_the_horizon(tmp):
    base = 11550 + 3 * 88
    for name, horizon, phase, steps, part in (("between-pairs", base + 2 * 1900 + 949, "hold", 7, 0), ("in-ignite", 7150 + 4399, "ignite", 1, 0),
                                              ("in-approach", 11550 + 2 * 88 + 87, "approach", 4, 0), ("at-once", 7149, "ignite", 0, 0),
                                              ("mid-pair", base + 2 * 1900 + 950, "hold", 7, 1)):
        got = W.drop(tmp, W.sign_world(603.5), name=name, map_name=f"{name}.jsonl", horizon=horizon)
        last = got.steps[-1]
        payload = last[{"ignite": "grid", "approach": "leg", "hold": "pair"}[phase]]
        assert got.rc == 0 and len(got.steps) == steps + 1, (name, got.rc, len(got.steps))
        assert {k: v for k, v in last.items() if k not in ("index", "grid", "leg", "pair")} == {
            "rec": "step", "step": steps + 1, "phase": phase, "evaluated": False,
            "verdict": [{"kind": "no-reading", "reason": "n/e", "dial": "K", "ticks": None}]}, (name, last)
        assert got.records[-1] == {"rec": "outcome", "kind": "HORIZON", "reason": "no-reading", "bracket": None, "A_hull": None,
                                   "B_hull": None, "agree": None, "steps": steps + 1}, (name, got.records[-1])
        assert got.fake.replies[-1]["op"] == "nev" and got.fake.refused == 1, (name, got.fake.replies[-1])
        assert last["index"] == (got.fake.readings[-1]["window"][1] if got.fake.readings else 0), (name, last["index"])
        assert len(got.entries) - 1 == len(got.fake.readings), (name, len(got.entries), len(got.fake.readings))    # every reading served is a place
        if not part:
            assert payload == {}, (name, payload)
            continue
        # the pair's low probe was served and its high probe was not: the step keeps the reading it has, and so does the map
        assert set(payload) == COMMON and payload["pos"] == [598] and payload["classes"] == ["SIG-"] and payload["segment"] == 1, (name, payload)
        assert payload["values"]["D"] == [got.fake.readings[-1]["D"]] and payload["window"] == [got.fake.readings[-1]["window"]], (name, payload)
        assert got.entries[-1]["call"] == {"step": steps + 1, "phase": "hold", "kind": "no-reading"} and got.entries[-1]["tick"] == 598, got.entries[-1]["call"]
        assert got.entries[-1]["state"] == "disordered-side", got.entries[-1]["state"]
    # a call that fitted before the declared horizon and still was not answered is NOT the horizon: its own kind, its own outcome
    for name, nth, part in (("cut-between", 6, 0), ("cut-mid-pair", 7, 1)):
        count = {"n": 0}
        def cut(m):
            count["n"] += isinstance(m, dict) and m.get("op") == "nudge"
            if count["n"] == nth:
                raise OSError("the wire is cut")
        got = W.drop(tmp, W.sign_world(603.5), name=name, map_name=f"{name}.jsonl", hook=cut, **SHORT)
        last = got.steps[-1]
        assert got.rc == 0 and got.fake.refused == 0 and (last["evaluated"], last["phase"]) == (False, "hold"), (name, got.rc, last)
        assert last["verdict"] == [{"kind": "wire-lost", "reason": "n/e", "dial": "K", "ticks": None}], (name, last["verdict"])
        assert (got.records[-1]["kind"], got.records[-1]["reason"]) == ("WIRE-LOST", "wire-lost"), (name, got.records[-1])
        assert (set(last["pair"]) == COMMON and last["pair"]["pos"] == [598]) if part else last["pair"] == {}, (name, last["pair"])
        assert len(got.entries) - 1 == len(got.fake.readings), (name, len(got.entries), len(got.fake.readings))
    off = W.drop(tmp, W.sign_world(603.5), with_cfg(ops=W.OFF_OPS), name="off", map_name="off.jsonl", horizon=11550 + 2 * 1900 + 1899)
    assert off.steps[-1]["pair"] == {} and len(off.steps) == 5 and off.records[-1]["kind"] == "HORIZON", off.steps[-1]    # a scan is whole or absent


# ---------------------------------------------------------------- isolation
def _strings(tree):
    doc = {id(n.body[0].value) for n in ast.walk(tree) if isinstance(n, (ast.Module, ast.FunctionDef, ast.ClassDef)) and n.body
           and isinstance(n.body[0], ast.Expr) and isinstance(n.body[0].value, ast.Constant) and isinstance(n.body[0].value.value, str)}
    return [n.value for n in ast.walk(tree) if isinstance(n, ast.Constant) and isinstance(n.value, str) and id(n) not in doc]


def test_h12_isolation_static():
    opens = {}
    for name in ("hold", "holdtab", "holdrep"):
        src = (ROOT / "navigator" / f"{name}.py").read_text()
        tree = ast.parse(src)
        mods = {a.name.split(".")[0] for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names} | \
               {(n.module or "").split(".")[0] for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)}
        assert mods <= ALLOWED_IMPORTS, (name, sorted(mods - ALLOWED_IMPORTS))
        local = {a.name for n in ast.walk(tree) if isinstance(n, ast.ImportFrom) and n.module == "navigator" for a in n.names}
        assert local <= {"hold", "holdtab", "holdrep", "reader", "report2", "steer"}, (name, sorted(local))
        bad = [(s, b) for s in _strings(tree) for b in BANNED if b in s]
        assert not bad, (name, bad[:3])
        names = [n for n in ast.walk(tree) if isinstance(n, ast.Name) and n.id in ("open", "exec", "eval", "__import__", "compile", "getattr", "globals")]
        opens[name] = [n.id for n in names]
        assert not [n for n in ast.walk(tree) if isinstance(n, ast.Attribute) and n.attr in ("popen", "system", "environ", "listdir", "read_text", "read_bytes")], name
    assert opens == {"hold": ["open", "open"], "holdtab": [], "holdrep": []}, opens       # the settings file and the map, nothing else
    args = [n.args[0].value for n in ast.walk(ast.parse((ROOT / "navigator" / "hold.py").read_text()))
            if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) and n.func.attr == "add_argument"]
    assert args == ["--needle", "--port", "--drop", "--map"], args


def test_h13_truth_files_beside_the_map_change_nothing(tmp):
    clean = W.drop(tmp, W.sign_world(603.5), **SHORT)
    poisoned = tmp / "run"
    poisoned.mkdir()
    lie = {"time": "lag and drift are in algorithmic (Swendsen-Wang) time", "wire": W.WIRE, "index": 0, "K_c": 0.45, "drift": {"law": "none"},
           "hidden": {"L4": 0.01}, "rows": [{"call": 1, "op": "scan", "index": 7150, "K_c": 0.45, "pos": [1000], "actual": [0.45],
                                              "points": [{"pos": [1000], "window": [451, 550], "K_c": [0.45, 0.45]}]}]}
    for n in ("edge.json", "truth.json", "perf.json", "score.json"):
        (poisoned / n).write_text(json.dumps(lie))
        (tmp / n).write_text(json.dumps(lie))
    dirty = W.drop(tmp, W.sign_world(603.5), map_name="run/map.jsonl", **SHORT)
    assert clean.rc == dirty.rc == 0 and clean.out == dirty.out and clean.map == dirty.map, "a truth file beside the map changed the needle"
    assert clean.fake.requests == dirty.fake.requests


def test_h14_live(tmp):
    seen, gate = {}, threading.Event()
    cfg = W.write_cfg(tmp / "hold.toml", W.CFG)
    second = threading.Event()
    def hook(m):
        if isinstance(m, dict) and m.get("op") == "scan":
            seen["scans"] = seen.get("scans", 0) + 1
            if seen["scans"] == 1:
                gate.wait(timeout=30)                   # the first reading is held back until the test has read the start record
            if seen["scans"] == 2:
                seen["late"] = not second.wait(timeout=20)    # the second is held back until the test has read step 1
    fake = W.Fake(W.sign_world(603.5), hook=hook, **SHORT)
    proc = subprocess.Popen(W.needle_cmd(cfg, fake.port, tmp / "map.jsonl"), cwd=str(ROOT), stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    try:
        first = json.loads(proc.stdout.readline())
        assert first["rec"] == "start", first
        head = (tmp / "map.jsonl").read_text()
        assert head.endswith("\n") and json.loads(head)["rec"] == "head" and len(head.splitlines()) == 1, head[:200]
        gate.set()
        lines = [json.loads(proc.stdout.readline())]            # a needle that holds step 1 back until call 2 is answered waits out the gate
        late = seen.get("late")
        second.set()
        assert lines[0]["rec"] == "step" and lines[0]["step"] == 1 and late is not True, (lines[0]["rec"], late)
        assert len((tmp / "map.jsonl").read_text().splitlines()) >= 1 + 13
    finally:
        gate.set()
        second.set()
        proc.stdout.read()
        proc.wait(timeout=120)
        fake.close()


# ---------------------------------------------------------------- the map, the kernel
STATE = {"SIG-": "disordered-side", "UNRES": "critical-bracketed", "SIG+": "ordered-side"}


def test_h15_the_map_is_one_place_per_reading(tmp):
    got = W.drop(tmp, cell_world(5), horizon=11550 + 3 * 88 + len(CELLS) * 1900)
    places, served = got.entries[1:], got.fake.readings
    assert len(places) == len(served) == 13 + 8 + 3 + 2 * len(CELLS), (len(places), len(served))
    by_step = {s["step"]: s for s in got.steps}
    last = -1
    for n, (p, r) in enumerate(zip(places, served)):
        assert set(p) == PLACE_KEYS and p["rec"] == "place" and p["drop"] == "t" and p["seq"] == n and p["dial"] == "K", (n, sorted(p))
        assert p["tick"] == r["tick"] and p["value"] == 0.2 + r["tick"] * (0.5 - 0.2) / 1200, (n, p["tick"], p["value"])
        assert p["window"] == r["window"] and p["index"] == r["window"][1] and type(p["index"]) is int and p["window"][0] > last, (n, p["index"], p["window"])
        assert p["readings"] == {"C": {"value": r["C"], "error": r["C_err"]}, "D": {"value": r["D"], "error": r["D_err"]}}, (n, p["readings"])
        cls = "SIG+" if r["D"] > 2 * r["D_err"] else "SIG-" if r["D"] < -2 * r["D_err"] else "UNRES"
        assert p["class"] == cls and p["state"] == STATE[cls] and p["settled"] is True, (n, p["class"], p["state"])
        s = by_step[p["call"]["step"]]
        assert p["call"] == {"step": s["step"], "phase": s["phase"], "kind": s["verdict"][0]["kind"]}, (n, p["call"])
        assert p["tick"] in s[{"ignite": "grid", "approach": "leg", "hold": "pair"}[s["phase"]]]["pos"], (n, p["tick"])
        last = p["index"]
    assert "unknown" not in {p["state"] for p in places}                     # a place in the map was read; unknown is for the rest
    assert not any(w in got.map for w in ("K_c", "truth", "actual", "hidden", "drift", "L4"))
    again = W.drop(tmp, cell_world(5), name="u", horizon=11550 + 3 * 88 + 1900)        # append-only: a second drop adds a block
    assert again.map.startswith(got.map) and [e["drop"] for e in again.entries if e["rec"] == "head"] == ["t", "u"]
    assert [e["seq"] for e in again.entries if e["drop"] == "u" and e["rec"] == "place"] == list(range(13 + 8 + 3 + 2))


def _reference_kernel(x):
    """A and B of the kernel reference (cc/kernel.py) over the declared path: edge j runs from reading j + 1 to reading j."""
    import importlib.util
    import numpy as np
    sys.path.insert(0, str(ROOT / "cc"))   # plan 1644 (declared edit): the kernel's types are the door's, so the relation is declared through the door
    import admit
    spec = importlib.util.spec_from_file_location("cc_kernel_reference", ROOT / "cc" / "kernel.py")
    K = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(K)
    n = len(x)
    rel = admit.declare(n, list(zip(range(1, n), range(0, n - 1))), [admit.Provenance.STEERING] * (n - 1))   # declared as STEERING (Origin, pending kernel revision)
    a = K.A(K.NodeField(np.array([x])), rel)
    b = K.B(a, rel)
    return [float(v) for v in a.spatial[0]], [float(v) for v in b.spatial[0]]


def test_h16_the_kernel_values_beside_the_verdicts(tmp):
    noisy = lambda t, i, n: (t - 603.5) * 0.004 + ((i * 2654435761) % 1000 - 500) * 1e-5
    got = W.drop(tmp, noisy, **SHORT)
    x = [r["D"] for r in got.fake.readings]
    A, B = _reference_kernel(x)
    said = [(a, b, s["step"]) for s in got.steps for p in [s[{"ignite": "grid", "approach": "leg", "hold": "pair"}[s["phase"]]]] if p for k in [p["kernel"]]
            for a, b in zip(k["A"], k["B"])]
    assert len(said) == len(x) and said[0][:2] == ("no-predecessor", "no-predecessor"), (len(said), said[0])
    assert [a for a, _, _ in said[1:]] == A and [b for _, b, _ in said[1:]] == B, "the stream's A or B is not the kernel's over the declared path"
    assert A[5] == x[6] - x[5] and B[0] == A[0] and B[5] == A[5] + A[4]            # current minus prior; the first edge is terminal
    assert all(s[{"ignite": "grid", "approach": "leg", "hold": "pair"}[s["phase"]]]["kernel"]["R"] == "NOT EVALUATED" for s in got.steps if s["evaluated"])
    places = got.entries[1:]
    assert [(p["kernel"]["A"], p["kernel"]["B"]) for p in places] == [(a, b) for a, b, _ in said] and all(p["kernel"]["R"] == "NOT EVALUATED" for p in places)
    assert set(places[0]["kernel"]) == {"A", "B", "R"} and got.records[0]["settings"]["M"] == W.CFG["M"]


def test_h17_the_opposite_orientation_steers_the_same_way(tmp):
    plus = W.drop(tmp, cell_world(5), horizon=11550 + 3 * 88 + len(CELLS) * 1900)
    flipped = lambda t, i, n: -cell_world(5)(t, i, n)
    roles = [{"name": "D", "role": "crossing", "ordered_sign": "-"}, {"name": "C", "role": "peak"}]
    for name, world in (("role", {"declared": {"roles": roles}}), ("side", {"declared": {"ordered_side": {"K": "-"}}})):
        minus = W.drop(tmp, flipped, name=name, map_name=f"{name}.jsonl", horizon=11550 + 3 * 88 + len(CELLS) * 1900, **world)
        assert minus.rc == 0 and minus.fake.requests == plus.fake.requests, name
        assert [s["verdict"][0]["kind"] for s in minus.steps] == [s["verdict"][0]["kind"] for s in plus.steps], name
        assert [s["verdict"][0]["ticks"] for s in minus.steps] == [s["verdict"][0]["ticks"] for s in plus.steps], name
        swap = {"SIG-": "SIG+", "SIG+": "SIG-", "UNRES": "UNRES"}
        assert [s["verdict"][0]["reason"] for s in minus.steps[:-1]] == ["|".join(swap[c] for c in s["verdict"][0]["reason"].split("|")) if s["phase"] != "approach" else "stride" for s in plus.steps[:-1]], name
        # the state of a place follows the role's ordered sign alone: the dial's direction orients the steering, not the place
        other = {"ordered-side": "disordered-side", "disordered-side": "ordered-side", "critical-bracketed": "critical-bracketed"}
        want = {"role": [p["state"] for p in plus.entries[1:]], "side": [other[p["state"]] for p in plus.entries[1:]]}[name]
        assert [p["state"] for p in minus.entries[1:]] == want, name
        rule = minus.entries[0]["sign_rule"]
        assert (rule["ordered_sign"], rule["ordered_side"]) == {"role": ("-", "+"), "side": ("+", "-")}[name], (name, rule)
    both = W.drop(tmp, cell_world(5), name="both", map_name="both.jsonl", horizon=11550 + 3 * 88 + len(CELLS) * 1900,
                  declared={"roles": roles, "ordered_side": {"K": "-"}})
    assert both.records[1:] == plus.records[1:] and both.entries[1:] == [{**e, "drop": "both", "state": other[e["state"]]} for e in plus.entries[1:]]
    assert (both.entries[0]["sign_rule"]["ordered_sign"], both.entries[0]["sign_rule"]["ordered_side"]) == ("-", "-")


def test_h18_the_tables_are_total():
    from navigator import holdtab as H
    from navigator import steer as T
    same, flip = H.ORIENT[("+", "+")], H.ORIENT[("+", "-")]
    assert H.ORIENT[("-", "-")] is same and H.ORIENT[("-", "+")] is flip and len(H.ORIENT) == 4
    want = {("SIG-", "SIG+"): "stay", ("SIG-", "SIG-"): "raise", ("SIG-", "UNRES"): "raise", ("SIG+", "SIG+"): "lower", ("UNRES", "SIG+"): "lower",
            ("UNRES", "UNRES"): "no-signal", ("UNRES", "SIG-"): "no-signal", ("SIG+", "UNRES"): "no-signal", ("SIG+", "SIG-"): "no-signal"}
    move = {"stay": 0, "raise": 6, "lower": -6, "no-signal": 0}
    for (lo, hi), kind in want.items():
        assert H.hold_kind([lo, hi], same, "ON", 600, 6, 12, 1200) == (kind, move[kind]), (lo, hi)
        assert H.hold_kind([lo, hi], same, "OFF", 600, 6, 12, 1200) == (kind, 0), (lo, hi)
        assert H.hold_kind([flip[lo], flip[hi]], flip, "ON", 600, 6, 12, 1200) == (kind, move[kind]), (lo, hi)
    assert H.hold_kind(["SIG+", "SIG+"], same, "ON", 17, 6, 12, 1200) == ("range-low", 0) and H.hold_kind(["SIG+", "SIG+"], same, "ON", 18, 6, 12, 1200) == ("lower", -6)
    assert H.hold_kind(["SIG-", "SIG-"], same, "ON", 1183, 6, 12, 1200) == ("range-high", 0) and H.hold_kind(["SIG-", "SIG-"], same, "ON", 1182, 6, 12, 1200) == ("raise", 6)
    assert H.hold_kind(["SIG+", "SIG+"], same, "OFF", 12, 6, 12, 1200) == ("lower", 0)
    assert [H.placed("x", c, 12, 1200) for c in (11, 12, 1188, 1189)] == ["range-low", "x", "x", "range-high"]
    for delta in range(-200, 201):
        legs = H.legs(delta, 32)
        rest = delta - sum(legs)
        assert all(abs(d) == 32 for d in legs) and abs(rest) <= 32 and (not legs or (rest != 0 and (rest > 0) == (delta > 0))), (delta, legs)
        assert len(legs) == max(0, -(-abs(delta) // 32) - 1), (delta, legs)
    assert H.grid(0, 1200, 100, 1, 1200) == list(range(0, 1201, 100)) and H.grid(0, 100, 20, 1, 1200) == list(range(0, 121, 20))
    assert H.grid(1100, 1200, 20, 1, 1200) == list(range(1080, 1201, 20)) and H.grid(600, 700, 20, 0, 1200) == list(range(600, 701, 20))
    t = [0, 10, 20, 30, 40]
    assert H.bracket(t, ["SIG-", "SIG-", "UNRES", "SIG+", "SIG+"], same) == (10, 30) and H.bracket(t, ["SIG+", "SIG+", "UNRES", "SIG-", "SIG-"], flip) == (10, 30)
    for cls in (["UNRES"] * 5, ["SIG-"] * 5, ["SIG+"] * 5, ["SIG-", "SIG+", "SIG-", "SIG+", "SIG+"], ["SIG+", "SIG-", "SIG-", "SIG-", "SIG-"], ["UNRES"] * 4 + ["SIG+"]):
        assert H.bracket(t, cls, same) == (), cls
    assert H.ignite_kind((), 12, 1200) == "no-bracket" and H.ignite_kind((0, 20), 12, 1200) == "range-low" and H.ignite_kind((20, 40), 12, 1200) == "bracketed"
    assert H.ignite_kind((1180, 1200), 12, 1200) == "range-high"
    assert H.OPS == {"OFF": ("declare", "scan"), "ON": ("declare", "scan", "nudge")} and [T.mode_of(H.OPS[m]) for m in ("OFF", "ON")] == ["OFF", "ON"]
    assert [H.outcome(k) for k in ("range-low", "range-high", "no-reading", "wire-lost")] == ["OFF-DIAL", "OFF-DIAL", "HORIZON", "WIRE-LOST"]
    assert set(H.LAST_KINDS) == {"range-low", "range-high", "no-reading", "wire-lost"} and set(H.UNREAD) == {"no-reading", "wire-lost"}
    assert [H.unread(i, c, 1000) for i, c in ((0, 1000), (0, 1001), (999, 1), (999, 2), (1000, 0))] == ["wire-lost", "no-reading", "wire-lost", "no-reading", "wire-lost"]
    assert H.cost(13, 450, 100, 1) == 7150 and H.cost(1, 0, 40, 2) == 80 and H.cost(2, 450, 500, 1) == 1900
    assert H.kernel_next((), 1.5) == ("no-predecessor", "no-predecessor", (1.5,)) and H.kernel_next((1.5,), 2.0) == (0.5, 0.5, (2.0, 0.5))
    assert H.kernel_next((2.0, 0.5), 1.0) == (-1.0, -0.5, (1.0, -1.0))
    assert H.PLACE_STATES == STATE and H.UNVISITED == "unknown" and "unknown" not in H.PLACE_STATES.values()
    assert sorted(H.STATES) == ["critical-bracketed", "disordered-side", "in-transit", "ordered-side"] and H.MAP == "compass-map/1"
    assert [H.state(c, "+", True) for c in ("SIG-", "UNRES", "SIG+")] == ["disordered-side", "critical-bracketed", "ordered-side"]
    assert [H.state(c, "-", True) for c in ("SIG-", "UNRES", "SIG+")] == ["ordered-side", "critical-bracketed", "disordered-side"]
    assert {H.state(c, sg, False) for c in ("SIG-", "UNRES", "SIG+") for sg in "+-"} == {"in-transit"} == {H.IN_TRANSIT}
    assert [H.settled(100, 48, first, 1) for first in (148, 149)] == [False, True] and H.settled(-48, 48, 1, 1) is True
    assert [H.settled(100, 48, first, 2) for first in (149, 150)] == [False, True]        # the first sampling sweep is `skip` before the window opens
    assert H.commanded(5, 10, 9, 70) == (9, 70) and H.commanded(5, 10, 5, 70) == (5, 10)
    assert H.classes([0.021, -0.021, 0.02, -0.02, 0.0], [0.01] * 5, 2.0) == ["SIG+", "SIG-", "UNRES", "UNRES", "UNRES"]


def test_h19_the_shipped_settings_and_the_older_files():
    assert sorted(p.name for p in (ROOT / "navigator").glob("hold*.toml")) == ["hold-mid-null.toml", "hold-mid-off.toml", "hold-mid.toml", "hold-settled-off.toml", "hold-settled.toml"]      # two hold modes, neither named the default: there is no hold.toml
    assert tomllib.loads((ROOT / "navigator" / "hold-settled.toml").read_text()) == W.CFG
    assert tomllib.loads((ROOT / "navigator" / "hold-settled-off.toml").read_text()) == {**W.CFG, "ops": W.OFF_OPS}      # FEEDBACK OFF: the same needle, one setting
    assert tomllib.loads((ROOT / "navigator" / "hold-mid-off.toml").read_text()) == W.MID_OFF == {**W.MID, "ops": W.OFF_OPS}
    assert tomllib.loads((ROOT / "navigator" / "hold-mid.toml").read_text()) == W.MID                              # the mid-move case
    assert tomllib.loads((ROOT / "navigator" / "hold-mid-null.toml").read_text()) == W.MID_NULL                    # the mid-move null
    for rel, sha in FROZEN.items():
        assert hashlib.sha256((ROOT / rel).read_bytes()).hexdigest() == sha, f"{rel} was edited: stage 5a-N adds files, it edits none of these"


if __name__ == "__main__":
    import tempfile
    _tmp = [test_h01_settings_outside_their_domain_are_refused_before_the_wire, test_h02_a_declaration_it_cannot_serve_is_refused_after_declare,
            test_h03_the_start_record_and_the_map_head, test_h04_the_settle_time_is_the_needles_choice_and_a_mid_move_reading_is_marked, test_h05_ignition, test_h06_the_approach,
            test_h07_the_hold_table_feedback_on, test_h08_the_dials_end_no_clamp, test_h09_feedback_off_never_moves_the_centre,
            test_h10_lost_ignites_again, test_h11_the_horizon, test_h13_truth_files_beside_the_map_change_nothing, test_h14_live,
            test_h15_the_map_is_one_place_per_reading, test_h16_the_kernel_values_beside_the_verdicts,
            test_h17_the_opposite_orientation_steers_the_same_way]
    _plain = [test_h12_isolation_static, test_h18_the_tables_are_total, test_h19_the_shipped_settings_and_the_older_files]
    _fail = 0
    for _t in _tmp + _plain:
        with tempfile.TemporaryDirectory() as _d:
            try:
                _t(Path(_d)) if _t in _tmp else _t()
                print(f"PASS {_t.__name__}")
            except Exception as _e:  # noqa: BLE001
                _fail += 1
                print(f"FAIL {_t.__name__}: {type(_e).__name__}: {str(_e)[:400]}")
    print(f"{len(_tmp) + len(_plain) - _fail}/{len(_tmp) + len(_plain)} passed")
    sys.exit(1 if _fail else 0)
