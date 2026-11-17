"""Plan 1553 — mid-move readings on the emulated apparatus (contract/SCHEMA-1553.md, an amendment to SCHEMA-1545).
Owner ruling 2026-11-16, "Allow mid-move readings": the wire accepts `nudge` and `scan` with any n_eq >= 0, and the dial is a
DELAY LINE — a move commanded at index c is in force from index c + lag, whatever the call asked for.
FROZEN: the Generator makes this green; it does not edit this file.

The plumbing and the independent model (`_Model`) are those of contract/test_apparatus_wire.py, loaded by path.

What it pins:
  d01  environment.dial: a command arrives exactly `lag` sweeps after it was issued; before that the old tick is in force;
  d02  a track is immutable and append-only: nothing removes, rewrites or hastens an arrival;
  d03  nothing is shadowed: every commanded position is in force for exactly the time until the next command;
  d04  `runs` is the dial over a span as maximal runs; the dial only ever holds a commanded position (never a tick between);
  m01  with n_eq >= lag the replies are the numbers the plan-1545 build gives (recorded from main 61fb241);
  m02  the door: n_eq < lag (and n_eq = 0) is accepted for nudge and scan; every other refusal of plan 1545 stands;
  m03  mid-move sequences (lag 7: the switch falls in the settle, in the sampling, inside a skip group) equal the model;
  m04  a lag longer than whole readings (lag 90) equals the model; `declare` reports the COMMANDED position while a move
       is pending; a refused call in that state changes nothing;
  m05  a reading that ends before its own move arrives is, bit for bit, a `read` at the old position;
  m06  the delay line composes across calls: a pending move carries into the next call (shift identity, lag 50 vs lag 10);
  m07  truth.json: each point records `sampling` and the dial `runs`; `actual` is the dial in force, `pos` the commanded one;
  m08  the wire says nothing new: same reply keys, no forbidden word, no transit marker, byte-identical `declare` under drift;
  m09  a move to the position already commanded is no move: `read` and `nudge [0]` agree bit for bit; a world with no dial;
  m10  what the needle may compute: its own `settled` rule (wire data only) never calls a smeared reading settled;
  m11  everything else of plan 1545 is byte-identical to main 61fb241.

RED until `environment/dial.py` exists and the wire accepts n_eq < lag. m01 and m11 pass at base on purpose.
Run from the repo root:  python contract/test_apparatus_midmove.py   (or pytest)
"""
import hashlib
import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
_spec = importlib.util.spec_from_file_location("apparatus_wire_contract_1545", Path(__file__).with_name("test_apparatus_wire.py"))
W = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(W)

RQ = W.RQ                                       # n_eq 3, S 40, skip 1
Q0 = {"n_eq": 0, "S": 40, "skip": 1}            # the shortest call the wire accepts: 40 sweeps
LAG7 = {**W.WORLD, "lag": 7}
LAG90 = {**W.WORLD, "lag": 90}
MID = [                                         # lag 7
    {"op": "nudge", "d": [30], **Q0},                                   # the switch falls after sample 7
    {"op": "nudge", "d": [-32], "n_eq": 3, "S": 41, "skip": 3},        # inside the second skip group
    {"op": "scan", "ticks": [[100], [900], [410]], **Q0},
    {"op": "read", **Q0},
    {"op": "scan", "ticks": [[1200]], "n_eq": 6, "S": 40, "skip": 1},  # one sweep short: the first sampled sweep is at the old tick
    {"op": "scan", "ticks": [[0]], "n_eq": 7, "S": 40, "skip": 1},     # n_eq = lag: settled, as plan 1545
    {"op": "scan", "ticks": [[1200]], "n_eq": 8, "S": 40, "skip": 1},
    {"op": "scan", "ticks": [[0], [1200], [600]], "n_eq": 2, "S": 40, "skip": 2},
    {"op": "nudge", "d": [0], **Q0},
    {"op": "read", **RQ},
]
BIG = [                                         # lag 90: a move takes longer than two of the shortest calls
    {"op": "nudge", "d": [32], **Q0},                                   # index 0..40: the whole reading at the old tick
    {"op": "read", **Q0},                                               # 40..80: still the old tick
    {"op": "read", **Q0},                                               # 80..120: the move arrives at 90
    {"op": "scan", "ticks": [[1100], [100], [700]], **Q0},              # 120..240: arrivals at 210, (250), (290)
    {"op": "read", "n_eq": 5, "S": 100, "skip": 1},                     # 240..345: TWO arrivals inside one reading
    {"op": "scan", "ticks": [[1200]], **Q0}, {"op": "scan", "ticks": [[0]], **Q0}, {"op": "scan", "ticks": [[1200]], **Q0},
    {"op": "read", "n_eq": 0, "S": 60, "skip": 3},
    {"op": "nudge", "d": [-5], "n_eq": 90, "S": 40, "skip": 1},         # n_eq = lag after a quiet stretch: settled
]
MARKERS = ("settled", "arriv", "switch", "pending", "sampling", "transit", "track", "runs", "commanded", "smear", "moving")
# the replies of main 61fb241 (plan 1545 as merged) to W.SEQUENCE in W.WORLD, recorded on the build host
BASE_61FB241 = [{'op': 'reading',
  'pos': [[400]],
  'window': [[4, 43]],
  'values': {'D': [-0.054166666666666585], 'C': [14.938765432098766]},
  'errors': {'D': [0.06478051863440058], 'C': [2.025180084656623]},
  'index': 43},
 {'op': 'reading',
  'pos': [[407]],
  'window': [[47, 86]],
  'values': {'D': [-0.0986111111111112], 'C': [10.77716049382716]},
  'errors': {'D': [0.0645292721604858], 'C': [3.215228237558521]},
  'index': 86},
 {'op': 'reading',
  'pos': [[375]],
  'window': [[90, 170]],
  'values': {'D': [-0.16598915989159885], 'C': [11.053267822651126]},
  'errors': {'D': [0.057122607032899925], 'C': [3.0239093784391784]},
  'index': 170},
 {'op': 'reading',
  'pos': [[100], [900], [410]],
  'window': [[174, 213], [217, 256], [260, 299]],
  'values': {'D': [-0.17777777777777776, 0.06631944444444449, -0.043055555555555625],
             'C': [5.506666666666666, 11.641358024691359, 22.372222222222224]},
  'errors': {'D': [0.05143973697406524, 0.020274391640293706, 0.09279689327536499],
             'C': [1.375190964240504, 8.501809562656737, 4.19189375242485]},
  'index': 299},
 {'op': 'reading',
  'pos': [[410]],
  'window': [[300, 339]],
  'values': {'D': [-0.09027777777777785], 'C': [14.066049382716049]},
  'errors': {'D': [0.08772799359924208], 'C': [4.377222695959092]},
  'index': 339},
 {'op': 'reading',
  'pos': [[410]],
  'window': [[343, 382]],
  'values': {'D': [-0.006597222222222254], 'C': [16.333333333333332]},
  'errors': {'D': [0.08677627430118896], 'C': [2.7990964034355272]},
  'index': 382}]
PINS = {         # sha256 at main 61fb241
    "contract/SCHEMA-1545.md": "ef7a2a67fd64fb06bf190d6406da268dab51404dda7d9ebcf0471e25770ea320",
    "contract/SCHEMA-1525.md": "40ae7812cefb384bd1a2582751891464ce0928d1e643da87f2df0fa56ce169ec",
    "contract/test_apparatus_drift.py": "3586c1ec9930b059555fe2925af1cb7ce685f7b06e3b64e337cafac900e16261",   # plan 1561: line 45 names six laws
    # "environment/drift.py" is no longer pinned: plan 1561 adds two laws; test_apparatus_drift.py and test_drift_laws.py hold the old four
    "environment/apparatus_config.py": "8d7104d561d5e927d70323c44b2edf0481be2f27df51b2be588a60851f522003",
    "environment/apparatus_server.py": "7a81c7c69ca30c00ba70a476a1fcffcd4711d49322c5f4004aaf1c7f6aa3c155",
    "environment/environment-apparatus.toml": "8d6f1962219fe08ba4cc2a460c5947bf01c160374f7e8925d3d1d9557a4c4b9a",
    "system-instantiated/plugins/at/at-apparatus.toml": "8db2ceab38f5d2f20c2e8b411d8ef96160f0b32d8ca9fd7adc105c4499129eb3",
    "system-instantiated/plugins/at/at-apparatus-static.toml": "788bb649d187f6e85072c942ff7bbbbaf37db5249be2be424713e0e94a33a623",
    "system-instantiated/plugins/at/tau-v0.toml": "e72cf18bd425fb8afc83e9cfa6914084aaf1bc8e0f0149bbd31a917e7f608af8",
    "environment/server.py": "ebb91c4333b0097a4016e5a6175b8f60538a6e592cb74acf624de95256b532b0",
    "environment/wire.py": "5c3628bf3d75720d66639e76fc6021c1e5c6bfbffbd0e9c71beac38a679a4d78",
    "navigator/reader.py": "0f655fbfcc0cb4be7f9bd7ed89c9e94222830968d148f57d1f59a1194cfd54f8",
    "system-instantiated/plugins/at/plugin.py": "667ea692febe23bd393a9d00a8cfddb669b1660a5cdf4c25cb4065307a57bc00",
    "system-instantiated/plugins/at/blind.py": "f261eb6a12c5d7858b31f4dc036a83767af32ae81de143783effcbc6e1504885",
    "environment/blind_wire.py": "d146e7b3566d0f9740822fc912fbd1b66d89bb52c3705574b21f4ac9733a0b16",
    "environment/blind_server.py": "b814ad13891571172bad4bae1198640f89eef6e30589308c9ab5f468837f324b",
    "environment/blind_config.py": "f5eb9d19e2a0c25ec635247a95f6efecf6dca92faf49dbce7c195267e42927f5",
    "environment/config.py": "65d1227a5cc269193825bf6f841613b01131f8998a7961b44109c246bf9f445a",
}
# AMENDED by plan 1565 (owner ruling 2026-11-16, the free-running apparatus): the world file gains an optional `clock` and the
# server a turn loop and turns.json (contract/SCHEMA-1565.md), so these two of the 1545 files are no longer pinned here.
PINS = {k: v for k, v in PINS.items() if k not in ("environment/apparatus_config.py", "environment/apparatus_server.py")}


def _dial():
    from environment import dial
    return dial


def _run(tmp, world, calls):
    """-> (replies, model, truth rows): drive a real server and the model with the same calls."""
    proc, c, run_dir = W._server(tmp, world)
    m = W._Model(world)
    try:
        got = [c.ask(msg) for msg in calls]
    finally:
        W._stop(proc, c)
    want = [m.call(msg) for msg in calls]
    return got, want, m, json.loads((run_dir / "truth.json").read_text())["rows"]


def _vals(r):
    return (r["values"], r["errors"])


# ---------------------------------------------------------------- the delay line, no server
def test_d01_a_command_arrives_after_exactly_lag_sweeps():
    D = _dial()
    t = D.command(D.start(5, [400]), 100, [407])
    assert [D.at(t, i) for i in (0, 99, 100, 104, 105, 106, 10 ** 6)] == [[400]] * 4 + [[407]] * 3, "lag 5, commanded at 100"
    assert D.commanded(t) == [407] and D.commanded(D.start(5, [400])) == [400]
    z = D.command(D.start(0, [400]), 100, [407])
    assert D.at(z, 99) == [400] and D.at(z, 100) == [407], "lag 0: in force for the very next sweep"
    e = D.command(D.start(3, []), 10, [])
    assert D.at(e, 0) == [] and D.at(e, 50) == [] and D.commanded(e) == [], "a world with no dial"
    two = D.command(D.start(4, [1, 9]), 7, [2, 8])
    assert D.at(two, 10) == [1, 9] and D.at(two, 11) == [2, 8], "one entry per dial"
    assert all(type(x) is int for x in D.at(t, 105)) and type(D.at(t, 105)) is list


def test_d02_a_track_is_immutable_and_append_only():
    D = _dial()
    t0 = D.start(5, [400])
    t1 = D.command(t0, 100, [407])
    t2 = D.command(t1, 101, [300])
    assert D.at(t0, 10 ** 6) == [400] and D.at(t1, 10 ** 6) == [407], "command must return a new track and leave the old one alone"
    assert D.at(t2, 104) == [400] and D.at(t2, 105) == [407] and D.at(t2, 106) == [300], \
        "a second command neither drops the first (pending) move nor arrives early"
    for name in ("lag", "arrivals"):
        try:
            setattr(t2, name, getattr(t0, name))
        except Exception:  # noqa: BLE001  (dataclasses.FrozenInstanceError or AttributeError)
            continue
        raise AssertionError(f"a track's `{name}` can be assigned: a pending move could be rewritten")
    assert type(t2.arrivals) is tuple and all(type(a) is tuple and type(a[1]) is tuple for a in t2.arrivals), \
        f"arrivals must be a tuple of (index, tuple of ticks), got {t2.arrivals!r}: a list could be edited in place"
    assert list(D.Track.__dataclass_fields__) == ["lag", "arrivals"] and [n for n in vars(D.Track) if not n.startswith("_")] == [], \
        "Track is two fields and no method: nothing on it may settle, drop or rewrite a move"
    public = sorted(n for n in vars(D) if not n.startswith("_") and callable(getattr(D, n)) and getattr(getattr(D, n), "__module__", "") == D.__name__)
    assert public == ["Track", "at", "command", "commanded", "runs", "start"], \
        f"environment.dial exports {public}: there must be no operation that removes, replaces or hastens an arrival"


def test_d03_nothing_is_shadowed():
    D = _dial()
    for lag in (0, 1, 7, 50, 333):
        t, cmds, c = D.start(lag, [0]), [(-(10 ** 9), [0])], 0
        for n in range(1, 40):
            c += 40 + (n * 37) % 91                       # commands at least 40 sweeps apart, as the wire's shortest call
            pos = [(n * 211) % 1201]
            t = D.command(t, c, pos); cmds.append((c, pos))
        end = cmds[-1][0] + lag + 50
        for (c0, p0), (c1, _) in zip(cmds, cmds[1:] + [(end, None)]):
            for i in {max(0, c0 + lag), max(0, c0 + lag) + 1, c1 + lag - 1}:
                if max(0, c0 + lag) <= i < c1 + lag:
                    assert D.at(t, i) == p0, f"lag {lag}: at index {i} the dial must be at {p0} (commanded at {c0}), got {D.at(t, i)}"
        held = {}
        for i in range(end):
            held[tuple(D.at(t, i))] = held.get(tuple(D.at(t, i)), 0) + 1
        for (c0, p0), (c1, _) in zip(cmds[1:], cmds[2:] + [(end - lag, None)]):
            assert held.get(tuple(p0), 0) >= c1 - c0, f"lag {lag}: {p0} was commanded for {c1 - c0} sweeps and held for fewer"


def test_d04_runs_are_maximal_and_on_the_tick_grid():
    D = _dial()
    t = D.start(5, [400])
    for c, p in ((0, [407]), (40, [407]), (80, [300]), (120, [300]), (160, [407])):
        t = D.command(t, c, p)
    assert D.runs(t, 0, 40) == [[0, [400]], [5, [407]]]
    assert D.runs(t, 40, 80) == [[40, [407]]], "a command to the position already in force starts no run"
    assert D.runs(t, 80, 120) == [[80, [407]], [85, [300]]]
    assert D.runs(t, 80, 85) == [[80, [407]]], "an arrival AT the end of the span is not in it (no sweep of the span ran there)"
    assert D.runs(t, 85, 120) == [[85, [300]]], "an arrival AT the start of the span is the first run"
    assert D.runs(t, 0, 200) == [[0, [400]], [5, [407]], [85, [300]], [165, [407]]]
    seen = {tuple(D.at(t, i)) for i in range(0, 200)}
    assert seen == {(400,), (407,), (300,)}, f"the dial held {sorted(seen)}: only commanded ticks exist, never one between"


# ---------------------------------------------------------------- the wire
def test_m01_settled_calls_give_the_numbers_of_plan_1545(tmp_path):
    proc, c, _ = W._server(tmp_path, W.WORLD)
    try:
        got = [c.ask(msg) for msg in W.SEQUENCE]
    finally:
        W._stop(proc, c)
    assert len(BASE_61FB241) == len(got)
    for n, (g, b) in enumerate(zip(got, BASE_61FB241)):
        W._same_reading(g, b, f"call {n} against main 61fb241")


def test_m02_the_door(tmp_path):
    proc, c, _ = W._server(tmp_path, W.WORLD)             # lag 2
    try:
        m = W._Model(W.WORLD)
        ok = [{"op": "nudge", "d": [1], "n_eq": 1, "S": 40, "skip": 1},          # the two rows plan 1545 a04 refused
              {"op": "scan", "ticks": [[100]], "n_eq": 1, "S": 40, "skip": 1},
              {"op": "nudge", "d": [32], **Q0}, {"op": "scan", "ticks": [[900], [5]], **Q0},
              {"op": "nudge", "d": [-3], "n_eq": 0, "S": 41, "skip": 2}, {"op": "read", **Q0}]
        for msg in ok:
            r = c.ask(msg)
            assert r["op"] == "reading", f"{msg!r} was refused: the wire must accept n_eq < lag (plan 1553)"
            W._same_reading(r, m.call(msg), f"accepted {msg['op']} n_eq={msg['n_eq']}")
        assert m.index == 41 + 41 + 40 + 80 + 82 + 40, m.index
        i0 = m.index
        bad = [{"op": "nudge", "d": [1], "n_eq": -1, "S": 40, "skip": 1}, {"op": "scan", "ticks": [[100]], "n_eq": -1, "S": 40, "skip": 1},
               {"op": "read", "n_eq": -1, "S": 40, "skip": 1}, {"op": "nudge", "d": [1], "n_eq": True, "S": 40, "skip": 1},
               {"op": "nudge", "d": [1], "n_eq": False, "S": 40, "skip": 1}, {"op": "nudge", "d": [1], "n_eq": 0.0, "S": 40, "skip": 1},
               {"op": "nudge", "d": [1], "n_eq": "0", "S": 40, "skip": 1}, {"op": "nudge", "d": [1], "n_eq": None, "S": 40, "skip": 1},
               {"op": "scan", "ticks": [[100]], "n_eq": [0], "S": 40, "skip": 1}, {"op": "nudge", "d": [1], "S": 40, "skip": 1},
               {"op": "nudge", "d": [1], "n_eq": 0, "S": 39, "skip": 1}, {"op": "nudge", "d": [1], "n_eq": 0, "S": 40, "skip": 0},
               {"op": "nudge", "d": [33], **Q0}, {"op": "scan", "ticks": [[1201]], **Q0}, {"op": "nudge", "d": [1], **Q0, "lag": 0},
               {"op": "nudge", "d": [1], **Q0, "settled": False}]
        for msg in bad:
            assert c.ask(msg) == {"op": "nev", "index": i0}, f"{msg!r} was not refused as nev at index {i0}"
        d = c.ask({"op": "declare"})
        assert d["pos"] == [2] and d["index"] == i0, ("a refused call moved the dial or the index", d)
        after = {"op": "read", **RQ}
        W._same_reading(c.ask(after), m.call(after), "after the refusals")
    finally:
        W._stop(proc, c)
    world = {**W.WORLD, "lag": 7, "horizon": 100}         # the horizon counts n_eq + S * skip and nothing for the lag
    proc, c, _ = W._server(tmp_path / "h", world)
    try:
        m = W._Model(world)
        assert c.ask({"op": "scan", "ticks": [[1], [2], [3]], **Q0}) == {"op": "nev", "index": 0}, "3 x 40 = 120 > 100"
        assert c.ask({"op": "nudge", "d": [1], "n_eq": 21, "S": 40, "skip": 2}) == {"op": "nev", "index": 0}, "21 + 80 = 101 > 100"
        for msg in ({"op": "nudge", "d": [9], **Q0}, {"op": "scan", "ticks": [[700]], "n_eq": 0, "S": 60, "skip": 1}):   # 40, then 60: exactly 100
            W._same_reading(c.ask(msg), m.call(msg), "to the horizon with a move still pending")
        assert c.ask({"op": "read", **Q0}) == {"op": "nev", "index": 100}
    finally:
        W._stop(proc, c)


def test_m03_mid_move_readings_match_the_model(tmp_path):
    got, want, m, _ = _run(tmp_path, LAG7, MID)
    for n, (g, w) in enumerate(zip(got, want)):
        W._same_reading(g, w, f"lag 7, call {n} {MID[n]['op']}")
    assert m.index == 40 + 126 + 120 + 40 + 46 + 47 + 48 + 246 + 40 + 43, m.index
    assert [r["pos"] for r in got[2:4]] == [[[100], [900], [410]], [[410]]], "`pos` is the commanded position of each point"


def test_m04_a_lag_longer_than_whole_readings(tmp_path):
    proc, c, _ = W._server(tmp_path, LAG90)
    try:
        m = W._Model(LAG90)
        for n, msg in enumerate(BIG[:1]):
            W._same_reading(c.ask(msg), m.call(msg), f"lag 90, call {n} {msg['op']}")
        d = c.ask({"op": "declare"})
        assert d["pos"] == [432] and d["index"] == 40, ("declare reports the COMMANDED position while the move is pending", d)
        for msg in ({"op": "nudge", "d": [33], **Q0}, {"op": "where"}, {"op": "scan", "ticks": [[1201]], **Q0}, {"op": "nudge", "d": [-31.0], **Q0}):
            assert c.ask(msg) == {"op": "nev", "index": 40}, f"{msg!r} was not refused while a move is pending"
        for n, msg in enumerate(BIG[1:], 1):
            W._same_reading(c.ask(msg), m.call(msg), f"lag 90, call {n} {msg['op']}")
        assert c.ask({"op": "declare"})["pos"] == [1195]
        up = {"op": "scan", "ticks": [[1200]], **Q0}          # commanded 1200; the dial itself is still at 1195 for 90 sweeps
        W._same_reading(c.ask(up), m.call(up), "to the top tick, pending")
        assert c.ask({"op": "nudge", "d": [1], **Q0}) == {"op": "nev", "index": m.index}, \
            "a nudge is measured from the COMMANDED position: 1200 + 1 is off the grid even while the dial is still at 1195"
        down = {"op": "nudge", "d": [-32], **Q0}
        r = c.ask(down)
        W._same_reading(r, m.call(down), "from the commanded position")
        assert r["pos"] == [[1168]], r["pos"]
    finally:
        W._stop(proc, c)


def test_m05_a_reading_that_ends_before_its_move_arrives_is_a_read_at_the_old_tick(tmp_path):
    world = {**W.WORLD, "lag": 40}                        # exactly the cost of Q0: the move arrives as the reading ends
    a, _, _, rows = _run(tmp_path / "moved", world, [{"op": "scan", "ticks": [[1100]], **Q0}, {"op": "read", **Q0}])
    b, _, _, _ = _run(tmp_path / "still", world, [{"op": "read", **Q0}, {"op": "read", **Q0}])
    assert _vals(a[0]) == _vals(b[0]), "lag 40, cost 40: every sweep of the reading ran at the OLD tick, so it must equal a read there"
    assert a[0]["pos"] == [[1100]] and b[0]["pos"] == [[400]] and a[0]["window"] == b[0]["window"], (a[0]["pos"], b[0]["pos"])
    assert _vals(a[1]) != _vals(b[1]), "the move was dropped: the reading after it is still a read at the old tick"
    val = lambda t: W.DIAL["lo"] + t * (W.DIAL["hi"] - W.DIAL["lo"]) / W.DIAL["T"]
    assert rows[0]["points"][0]["dial"] == [[0, [400]]] and rows[0]["index"] == 40, "no sweep of the first reading ran at the new tick"
    assert rows[0]["actual"] == [val(1100)], "an arrival exactly at the call's end IS in force at the row's index (it rules the next sweep)"
    assert rows[1]["points"][0]["dial"] == [[40, [1100]]], "the arrival at the first reading's end opens the next point's dial"
    s, _, _, _ = _run(tmp_path / "short", {**W.WORLD, "lag": 39}, [{"op": "scan", "ticks": [[1100]], **Q0}])
    assert _vals(s[0]) != _vals(b[0]), "lag 39, cost 40: the last sweep runs at the new tick, so the reading must differ"


def test_m06_a_pending_move_carries_into_the_next_call(tmp_path):
    """shift identity. Lag 50, moves commanded at 0, 40, 80, 120 arrive at 50, 90, 130, 170. Lag 10, the same moves commanded
    one call later (at 40, 80, 120, 160) arrive at the same indices. Same seed, same sweeps: the same lattice at every index."""
    moves = [[1100], [100], [700], [1200]]
    late = [{"op": "scan", "ticks": moves, **Q0}, {"op": "read", **Q0}, {"op": "read", **Q0}]
    early = [{"op": "read", **Q0}, {"op": "scan", "ticks": moves, **Q0}, {"op": "read", **Q0}]
    a, wa, _, _ = _run(tmp_path / "lag50", {**W.WORLD, "lag": 50}, late)
    b, wb, _, _ = _run(tmp_path / "lag10", {**W.WORLD, "lag": 10}, early)
    flat = lambda rs: [(r["values"]["D"][j], r["values"]["C"][j], r["errors"]["D"][j], r["errors"]["C"][j], r["window"][j])
                       for r in rs for j in range(len(r["pos"]))]
    fa, fb = flat(a), flat(b)
    assert len(fa) == len(fb) == 6
    for n, (x, y) in enumerate(zip(fa, fb)):
        assert x == y, f"reading {n} (window {x[4]}): lag 50 gives {x[:2]}, the shifted lag-10 run gives {y[:2]} — the pending lag was not carried"
    assert len({x[:4] for x in fa}) == 6, "the six readings must all differ (each sees a different dial history)"
    for n, (g, w) in enumerate(zip(a + b, wa + wb)):
        W._same_reading(g, w, f"shift identity, reply {n}")


def test_m07_the_truth_records_the_dial(tmp_path):
    val = lambda t: W.DIAL["lo"] + t * (W.DIAL["hi"] - W.DIAL["lo"]) / W.DIAL["T"]
    for name, world, calls in (("lag7", LAG7, MID), ("lag90", LAG90, BIG)):
        _, _, m, rows = _run(tmp_path / name, world, calls)
        assert len(rows) == len(calls)
        for got, want in zip(rows, m.rows):
            assert set(got) == {"call", "op", "index", "K_c", "pos", "actual", "points"}, sorted(got)
            for p in got["points"]:
                assert set(p) == {"pos", "window", "K_c", "sampling", "dial"}, sorted(p)
            assert got == want, f"{name} truth row {want['call']}:\n got  {got}\n want {want}"
    # hand-written, lag 90 (see BIG): index spans 0-40, 40-80, 80-120, then the scan 120-160, 160-200, 200-240, then 240-345
    pts = [p for r in rows for p in r["points"]]
    assert [p["dial"] for p in pts[:7]] == [
        [[0, [400]]], [[40, [400]]], [[80, [400]], [90, [432]]],
        [[120, [432]]], [[160, [432]]], [[200, [432]], [210, [1100]]],
        [[240, [1100]], [250, [100]], [290, [700]]]], [p["dial"] for p in pts[:7]]
    assert [p["sampling"] for p in pts[:7]] == [0, 40, 80, 120, 160, 200, 245], [p["sampling"] for p in pts[:7]]
    assert [p["pos"] for p in pts[:7]] == [[432], [432], [432], [1100], [100], [700], [700]]
    assert [(r["pos"], r["actual"]) for r in rows[:5]] == [([432], [val(400)]), ([432], [val(400)]), ([432], [val(432)]),
                                                           ([700], [val(1100)]), ([700], [val(700)])], \
        "`pos` is the commanded position; `actual` is the value of the tick in force at the row's index"
    assert all(type(i) is int and type(t) is int for p in pts for i, pos in p["dial"] for t in pos), "indices and ticks are ints"
    assert all(type(p["sampling"]) is int for p in pts)
    assert rows[-1]["actual"] == [val(rows[-1]["pos"][0])], "n_eq = lag after a quiet stretch: the dial is at the commanded tick"


def test_m08_the_wire_says_nothing_new(tmp_path):
    lines = {}
    for name, world in (("drift", LAG90), ("static", {**W.STATIC, "lag": 90})):
        proc, c, run_dir = W._server(tmp_path / name, world)
        try:
            got = [c.raw('{"op": "declare"}')]
            for msg in BIG[:4] + [{"op": "declare"}, {"op": "nudge", "d": [99], **Q0}] + BIG[4:] + [{"op": "declare"}]:
                got.append(c.raw(json.dumps(msg)))
            lines[name] = got
        finally:
            W._stop(proc, c)
        for line in got:
            for word in W.FORBIDDEN + MARKERS + (str(run_dir), str(tmp_path)):
                assert word not in line, f"the wire carries {word!r}: {line[:200]}"
            r = json.loads(line)
            assert set(r) in (W.DECLARED_KEYS, W.READING_KEYS, {"op", "index"}), sorted(r)
            if r["op"] == "reading":
                assert set(r["values"]) == set(r["errors"]) == {"D", "C"}, r
                assert "dial" not in line, f"a reading names the dial: {line[:200]}"
                m = len(r["pos"])
                assert all(len(r[k]) == m for k in ("pos", "window")) and all(len(r[p][q]) == m for p in ("values", "errors") for q in "DC"), r
    for n in (0, 5, -1):
        assert lines["drift"][n] == lines["static"][n], f"declare line {n} differs between a drifting and a static world"
    d = json.loads(lines["drift"][5])
    assert d["pos"] == [700] and d["lag"] == 90 and d["index"] == 240, ("declare mid-move: the commanded position, the declared lag", d)
    assert lines["drift"][1] != lines["static"][1], "the drift did not act"


def test_m09_a_move_to_the_commanded_position_is_no_move(tmp_path):
    pre = [{"op": "scan", "ticks": [[900]], "n_eq": 20, "S": 40, "skip": 1}]
    a, _, _, ra = _run(tmp_path / "read", LAG7, pre + [{"op": "read", **Q0}, {"op": "read", **RQ}])
    b, wb, _, rb = _run(tmp_path / "nudge0", LAG7, pre + [{"op": "nudge", "d": [0], **Q0}, {"op": "scan", "ticks": [[900]], **RQ}])
    assert [_vals(x) for x in a] == [_vals(x) for x in b], "`read`, `nudge [0]` and a scan to the commanded tick must agree bit for bit"
    assert [p["dial"] for r in ra for p in r["points"]] == [p["dial"] for r in rb for p in r["points"]] == \
        [[[0, [400]], [7, [900]]], [[60, [900]]], [[100, [900]]]]
    for n, (g, w) in enumerate(zip(b, wb)):
        W._same_reading(g, w, f"nudge 0, reply {n}")
    world = {**W.WORLD, "lag": 90, "dials": [], "fixed": {"K": 0.31}}
    calls = [{"op": "nudge", "d": [], **Q0}, {"op": "scan", "ticks": [[], []], **Q0}, {"op": "read", **Q0}]
    g, w, _, rows = _run(tmp_path / "nodial", world, calls)
    for n, (x, y) in enumerate(zip(g, w)):
        W._same_reading(x, y, f"no dial, reply {n}")
    assert [r["actual"] for r in rows] == [[]] * 3 and rows[1]["points"][1]["dial"] == [[80, []]], rows
    zero = {**W.WORLD, "lag": 0}
    g, w, _, rows = _run(tmp_path / "lag0", zero, [{"op": "nudge", "d": [32], **Q0}, {"op": "scan", "ticks": [[5], [1000]], **Q0}])
    for n, (x, y) in enumerate(zip(g, w)):
        W._same_reading(x, y, f"lag 0, reply {n}")
    assert [p["dial"] for r in rows for p in r["points"]] == [[[0, [432]]], [[40, [5]]], [[80, [1000]]]], "lag 0: every move is in force at once"


def test_m10_the_needle_can_tag_settled_from_the_wire_alone(tmp_path):
    """The needle knows `lag` (declared), its own requests and every `index`. Its rule (SCHEMA-1553 section 6): keep `arrive` =
    (index at which it last commanded a position different from the one commanded before) + lag; a reading with window
    [a, b] is `settled` when arrive <= a - skip. The truth must agree that every such reading was sampled wholly at `pos`."""
    for name, world, calls in (("lag7", LAG7, MID), ("lag90", LAG90, BIG)):
        got, _, _, rows = _run(tmp_path / name, world, calls)
        lag, commanded, arrive, index, tags, clean = world["lag"], [W.DIAL["start"]], 0, 0, [], []
        for msg, r in zip(calls, got):
            cost = msg["n_eq"] + msg["S"] * msg["skip"]
            for j, pos in enumerate(r["pos"]):
                c = index + j * cost
                if pos != commanded:
                    arrive, commanded = c + lag, pos
                tags.append(arrive <= r["window"][j][0] - msg["skip"])
            index = r["index"]
        for row in rows:
            for p in row["points"]:
                clean.append(p["dial"][-1][1] == p["pos"] and p["dial"][-1][0] <= p["sampling"])
        assert len(tags) == len(clean)
        for n, (t, cl) in enumerate(zip(tags, clean)):
            assert cl or not t, f"{name} point {n}: the needle's rule says settled, the truth says the dial moved under the samples"
        assert any(tags) and not all(tags), f"{name}: the sequence must hold settled and unsettled readings ({tags})"


def test_m11_the_rest_of_plan_1545_is_byte_identical():
    assert len(PINS) >= 12
    for rel, want in PINS.items():
        got = hashlib.sha256((ROOT / rel).read_bytes()).hexdigest()
        assert got == want, f"{rel} was edited (sha256 {got[:12]}…); plan 1553 edits two source files and adds environment/dial.py"


if __name__ == "__main__":
    import tempfile
    _plain = [test_d01_a_command_arrives_after_exactly_lag_sweeps, test_d02_a_track_is_immutable_and_append_only, test_d03_nothing_is_shadowed,
              test_d04_runs_are_maximal_and_on_the_tick_grid, test_m11_the_rest_of_plan_1545_is_byte_identical]
    _tests = [test_m01_settled_calls_give_the_numbers_of_plan_1545, test_m02_the_door, test_m03_mid_move_readings_match_the_model,
              test_m04_a_lag_longer_than_whole_readings, test_m05_a_reading_that_ends_before_its_move_arrives_is_a_read_at_the_old_tick,
              test_m06_a_pending_move_carries_into_the_next_call, test_m07_the_truth_records_the_dial, test_m08_the_wire_says_nothing_new,
              test_m09_a_move_to_the_commanded_position_is_no_move, test_m10_the_needle_can_tag_settled_from_the_wire_alone]
    _fail = 0
    for _t in _plain[:4]:
        try:
            _t(); print(f"PASS {_t.__name__}")
        except Exception as _e:  # noqa: BLE001
            _fail += 1; print(f"FAIL {_t.__name__}: {type(_e).__name__}: {str(_e)[:400]}")
    for _t in _tests:
        with tempfile.TemporaryDirectory() as _d:
            try:
                _t(Path(_d)); print(f"PASS {_t.__name__}")
            except Exception as _e:  # noqa: BLE001
                _fail += 1; print(f"FAIL {_t.__name__}: {type(_e).__name__}: {str(_e)[:400]}")
    try:
        _plain[4](); print(f"PASS {_plain[4].__name__}")
    except Exception as _e:  # noqa: BLE001
        _fail += 1; print(f"FAIL {_plain[4].__name__}: {type(_e).__name__}: {str(_e)[:400]}")
    print(f"{len(_tests) + 5 - _fail}/{len(_tests) + 5} passed")
    sys.exit(1 if _fail else 0)
