"""Plan 1552 — stage 5a-N acceptance: the reader of a hold report and of its map, `needlestream/read_hold.py`
(contract/SCHEMA-1552.md sections 7 and 8). The texts it reads are written by the needle itself against the scripted apparatus
of contract/holdwire.py. FROZEN: the Generator makes this green; it does not edit it.

What it pins:
  r01  every report the needle writes reads as a Stream, and every prefix of it reads as a Stream still PENDING;
  r02  the reader holds a report to the needle's own tables: any one changed number, class, kind, move, centre, kernel value,
       order or key makes it Unreadable (a value, never an exception);
  r03  "resolved here", "cannot tell" and "no reading" are three different cells of a hold step;
  r04  the map the needle writes reads as a Map and is exactly the map its report implies (`check`);
  r05  a map entry for a place that was never read is refused; the state of a never-read place is `unknown`, and only there;
  r06  truth in the map is refused: a place or a head with one more key is Unreadable;
  r07  a place with no time index, or an index that is not its window's end or does not move forward, is Unreadable;
  r08  a place whose state does not follow from its readings and the declared sign rule is Unreadable; so is a mid-move
       reading typed as a clean place;
  r09  the trail (belief, call and bracket against algorithmic time), sigma in both units (ticks and units of g), and the
       needle's settle choice against the declared lag;
  r10  two drops in one file read as two drops, each with what a later merge needs; names are unique;
  r11  the reader is pure and total: it opens nothing, prints nothing, and returns Unreadable on any text.

RED until `needlestream/read_hold.py` exists.
Run from the repo root:  python contract/test_hold_reader.py   (or pytest)
"""
import ast
import copy
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import holdwire as W  # noqa: E402

ROOT = W.ROOT
BASE = 11550 + 3 * 88
CELLS = [(-0.30, 0.30), (-0.10, -0.50), (0.00, 0.00), (0.50, 0.10), (-0.30, 0.00), (0.30, -0.30)]


def _cells(tick, index, n):
    if n < 5:
        return 0.3 if tick > 603.5 else -0.3
    return CELLS[((n - 5) // 2) % len(CELLS)][(n - 5) % 2]


def _lib():
    from needlestream import read as NS
    from needlestream import read_hold as RH
    return NS, RH


def _cutter(nth, op="nudge", scans=0):
    """a Fake hook that cuts the wire at the nth call of `op` (or, for scans, at the scan numbered `scans`)."""
    count = {"n": 0}
    def cut(m):
        count["n"] += isinstance(m, dict) and m.get("op") == op
        if count["n"] == (scans or nth):
            raise OSError("the wire is cut")
    return cut


def _reports(tmp):
    """a set of real reports covering every phase, both modes, every way a stream ends."""
    dark = lambda t, i, n: (0.3 if t > 603.5 else -0.3) if n < 5 or n > 12 else 0.0
    low = lambda t, i, n: (0.3 if t > 30 else -0.3) if n < 2 else 0.3
    worlds = {
        "on": (_cells, None, {"horizon": BASE + 8 * 1900}),
        "mid-pair": (_cells, None, {"horizon": BASE + 2 * 1900 + 950}),
        "off": (_cells, {**W.CFG, "ops": W.OFF_OPS}, {"horizon": 11550 + 6 * 1900}),
        "reignite": (dark, None, {"horizon": 60000}),
        "off-dial": (low, None, {"horizon": 60000}),
        "mid": (_cells, {**W.CFG, "n_eq": 0}, {"horizon": BASE + 6 * 1000}),
        "minus": (lambda t, i, n: -_cells(t, i, n), None, {"horizon": BASE + 6 * 1900, "declared": {"ordered_side": {"K": "-"}}}),
        "cut": (_cells, None, {"horizon": 60000, "hook": _cutter(7)}),            # the wire is lost in the middle of the second pair
        "cut-ignite": (_cells, None, {"horizon": 60000, "hook": _cutter(0, "scan", 2)}),
    }
    return {name: W.drop(tmp, f, cfg, name=name, map_name=f"{name}.jsonl", **world) for name, (f, cfg, world) in worlds.items()}


def _text(records):
    return "".join(json.dumps(r) + "\n" for r in records)


def test_r01_every_report_and_every_prefix_reads(tmp):
    NS, RH = _lib()
    for name, got in _reports(tmp).items():
        assert got.rc == 0, (name, got.err[-200:])
        st = RH.read(got.out)
        assert isinstance(st, RH.Stream), (name, st)
        assert st.outcome == got.records[-1] and list(st.steps) == got.steps and st.start == got.records[0], name
        assert st.mode == got.records[0]["mode"]["feedback"] and st.dial == got.fake.declared["dials"][0], (name, st.mode, st.dial)
        assert st.orient == ("-" if name == "minus" else "+"), (name, st.orient)
        lines = got.out.splitlines(keepends=True)
        for n in range(1, len(lines)):
            part = RH.read("".join(lines[:n]))
            assert isinstance(part, RH.Stream) and part.outcome is NS.PENDING and len(part.steps) == n - 1, (name, n, part)
    assert isinstance(RH.read(""), NS.Unreadable)


def _mutations(recs):
    """(name, mutated records): each is ONE change to a report the needle wrote."""
    hold = [i for i, r in enumerate(recs) if r.get("phase") == "hold" and r["evaluated"]]
    ign = [i for i, r in enumerate(recs) if r.get("phase") == "ignite"]
    leg = [i for i, r in enumerate(recs) if r.get("phase") == "approach"]
    h, h2 = hold[1], hold[3]       # CELLS[1] raise, CELLS[3] lower

    def m(name, f):
        out = copy.deepcopy(recs)
        f(out)
        return name, out
    return [
        m("a kind that is not the table's", lambda o: o[h]["verdict"][0].update(kind="stay")),
        m("a move that is not the table's", lambda o: o[h]["verdict"][0].update(ticks=12)),
        m("a move with the wrong sign", lambda o: o[h2]["verdict"][0].update(ticks=6)),
        m("a class that is not its reading's", lambda o: o[h]["pair"]["classes"].__setitem__(0, "SIG+")),
        m("a reason that is not the classes", lambda o: o[h]["verdict"][0].update(reason="SIG-|SIG+")),
        m("a centre the moves do not give", lambda o: o[hold[2]]["pair"].update(centre=o[hold[2]]["pair"]["centre"] + 1)),
        m("a setpoint off the centre", lambda o: o[h]["pair"].update(setpoint=o[h]["pair"]["setpoint"] + 12)),
        m("a bracket that is not centre +- g", lambda o: o[h]["pair"].update(bracket=[0, 1200])),
        m("a probe that is not at the bracket", lambda o: o[h]["pair"]["pos"].__setitem__(1, o[h]["pair"]["pos"][1] + 1)),
        m("a kernel A that is not the difference", lambda o: o[h]["pair"]["kernel"]["A"].__setitem__(0, 0.0)),
        m("a kernel B that is not the accumulation", lambda o: o[h]["pair"]["kernel"]["B"].__setitem__(1, 0.0)),
        m("R evaluated with nothing declared", lambda o: o[h]["pair"]["kernel"].update(R=0.0)),
        m("a settled mark that is not the lag model's", lambda o: o[h]["pair"]["settled"].__setitem__(0, False)),
        m("no settled marks", lambda o: o[h]["pair"].pop("settled")),
        m("a streak that does not count", lambda o: o[hold[2]]["pair"].update(streak=0)),
        m("a hold step number that skips", lambda o: o[h]["pair"].update(n=7)),
        m("a segment that changes without ignition", lambda o: o[h]["pair"].update(segment=2)),
        m("an index that is not the last window's end", lambda o: o[h].update(index=o[h]["index"] - 1)),
        m("a window that runs backwards", lambda o: o[h]["pair"]["window"].__setitem__(1, o[h]["pair"]["window"][0])),
        m("an error that is missing", lambda o: o[h]["pair"]["errors"].pop("D")),
        m("a value that is not a number", lambda o: o[h]["pair"]["values"]["D"].__setitem__(0, "0.1")),
        m("one more payload key", lambda o: o[h]["pair"].update(K_c=0.35)),
        m("one more step key", lambda o: o[h].update(truth=1)),
        m("a dropped step", lambda o: o.pop(h)),
        m("two steps swapped", lambda o: o.__setitem__(slice(h, h + 2), [o[h + 1], o[h]])),
        m("an evaluated step with no payload", lambda o: o[h].update(pair={})),
        m("a no-reading step that is not the last", lambda o: (o[h].update(evaluated=False, pair={}), o[h]["verdict"][0].update(kind="no-reading", reason="n/e", ticks=None))),
        m("ignition bracket not the readings'", lambda o: o[ign[0]]["grid"].update(lo=500)),
        m("ignition grid not the declared grid", lambda o: o[ign[1]]["grid"]["pos"].__setitem__(0, 590)),
        m("ignition verdict moves the dial", lambda o: o[ign[0]]["verdict"][0].update(ticks=0)),
        m("a round out of order", lambda o: o[ign[1]]["grid"].update(round=1)),
        m("a stride that is not max_nudge", lambda o: (o[leg[0]]["leg"].update(d=-31), o[leg[0]]["verdict"][0].update(ticks=-31))),
        m("an approach skipped", lambda o: o.pop(leg[0])),
        m("feedback that is not the ops", lambda o: o[0]["mode"].update(feedback="OFF")),
        m("settings that are not this needle's", lambda o: o[0]["settings"].update(g=0)),
        m("a start record with no M", lambda o: o[0]["settings"].pop("M")),
        m("sigma not this needle's", lambda o: o[0]["sigma"].update(measured="fluct-window")),
        m("a schema that is not compass-report/2", lambda o: o[0].update(schema="compass-report/3")),
        m("another needle", lambda o: o[0].update(needle="recover-adaptive-v1")),
        m("an outcome that is not the fold", lambda o: o[-1].update(kind="OFF-DIAL", reason="range-low")),
        m("an outcome with a bracket", lambda o: o[-1].update(bracket=[598, 622])),
        m("an outcome step count", lambda o: o[-1].update(steps=o[-1]["steps"] + 1)),
        m("a step after the last", lambda o: o.insert(len(o) - 1, copy.deepcopy(o[h]))),
        m("a verdict on another dial", lambda o: o[h]["verdict"][0].update(dial="J")),
    ]


def test_r02_one_changed_field_is_unreadable(tmp):
    NS, RH = _lib()
    got = W.drop(tmp, _cells, horizon=BASE + 8 * 1900)
    assert isinstance(RH.read(got.out), RH.Stream)
    for name, recs in _mutations(got.records):
        out = RH.read(_text(recs))
        assert isinstance(out, NS.Unreadable), f"read a report with {name}"
    off = W.drop(tmp, _cells, {**W.CFG, "ops": W.OFF_OPS}, name="off", map_name="off.jsonl", horizon=11550 + 6 * 1900)
    moved = copy.deepcopy(off.records)
    i = [k for k, r in enumerate(moved) if r.get("phase") == "hold" and r["verdict"][0]["kind"] == "raise"][0]
    moved[i]["verdict"][0]["ticks"] = 6
    assert isinstance(RH.read(off.out), RH.Stream) and isinstance(RH.read(_text(moved)), NS.Unreadable), "read an OFF report whose verdict moves the dial"
    for junk in ("{", "[]\n", "null\n", '{"rec": "start"}\n', got.out.replace('"rec": "step"', '"rec": "stp"', 1), "\x00\n"):
        assert isinstance(RH.read(junk), NS.Unreadable), junk[:30]


def test_r03_resolved_cannot_tell_and_no_reading_are_three_cells(tmp):
    NS, RH = _lib()
    got = W.drop(tmp, _cells, horizon=BASE + 6 * 1900 + 950)
    st = RH.read(got.out)
    hold = [r for r in st.steps if r["phase"] == "hold"]
    cell = [(r["evaluated"], r["verdict"][0]["kind"], r["verdict"][0]["ticks"]) for r in hold]
    assert cell == [(True, "stay", 0), (True, "raise", 6), (True, "no-signal", 0), (True, "lower", -6), (True, "raise", 6), (True, "no-signal", 0),
                    (False, "no-reading", None)], cell
    assert len({c[1] for c in cell if c[1] in ("stay", "no-signal", "no-reading")}) == 3
    # the horizon and a lost wire are two kinds, and the stream's own declared horizon says which: neither reads as the other
    def renamed(records, kind, outcome):
        out = copy.deepcopy(records)
        out[-2]["verdict"][0]["kind"] = kind
        out[-1].update(kind=outcome, reason=kind)
        return _text(out)
    assert isinstance(RH.read(renamed(got.records, "no-reading", "HORIZON")), RH.Stream)
    assert isinstance(RH.read(renamed(got.records, "wire-lost", "WIRE-LOST")), NS.Unreadable), "a horizon stop read as a lost wire"
    cut = W.drop(tmp, _cells, name="cut", map_name="cut.jsonl", horizon=60000, hook=_cutter(6))
    assert cut.records[-1]["kind"] == "WIRE-LOST" and isinstance(RH.read(cut.out), RH.Stream), cut.records[-1]
    assert isinstance(RH.read(renamed(cut.records, "no-reading", "HORIZON")), NS.Unreadable), "a lost wire read as the horizon"
    assert isinstance(RH.read(renamed(cut.records, "wire-lost", "HORIZON")), NS.Unreadable), "an outcome that is not the fold of the last step"


def test_r04_the_map_reads_and_is_the_map_of_its_report(tmp):
    NS, RH = _lib()
    reports = _reports(tmp)
    for name, got in reports.items():
        st, mp = RH.read(got.out), RH.read_map(got.map)
        assert isinstance(mp, RH.Map) and len(mp.drops) == 1, (name, mp)
        d = mp.drops[0]
        assert [d.head, *d.places] == got.entries and RH.check(st, d) is None, (name, RH.check(st, d))
        assert RH.places(st, name) == got.entries, name
        assert len(d.places) == len(got.fake.readings), (name, len(d.places), len(got.fake.readings))
    a, b = reports["on"], reports["off"]
    assert RH.check(RH.read(a.out), RH.read_map(b.map).drops[0]) is not None, "a map passed the check of another report"


def _map_mut(entries, f):
    out = copy.deepcopy(entries)
    f(out)
    return _text(out)


def test_r05_an_entry_for_a_place_never_read_and_the_unknown_state(tmp):
    NS, RH = _lib()
    got = W.drop(tmp, _cells, horizon=BASE + 4 * 1900)
    st, d = RH.read(got.out), RH.read_map(got.map).drops[0]
    visited = {p["tick"] for p in d.places}
    assert visited == {r["tick"] for r in got.fake.readings} and 5 not in visited
    for t in range(0, 1201):
        assert (RH.state_at(d, t) == "unknown") == (t not in visited), t
    assert RH.state_at(d, 0) == "disordered-side" and RH.state_at(d, 1200) == "ordered-side" and RH.state_at(d, 5) == "unknown"
    states = {t: [p["state"] for p in d.places if p["tick"] == t] for t in visited}
    changed = [t for t, seen in states.items() if seen[0] != seen[-1]]
    assert changed and all(RH.state_at(d, t) == states[t][-1] != states[t][0] for t in changed), changed      # the latest reading of a place, not the first
    # a place the needle never read: appended, inserted, or carried with the default state
    ghost = {**copy.deepcopy(got.entries[-1]), "seq": len(got.entries) - 1, "tick": 5, "value": 0.2 + 5 * 0.3 / 1200}
    ghost["window"] = [ghost["window"][1] + 451, ghost["window"][1] + 950]
    ghost["index"] = ghost["window"][1]
    ghost["kernel"] = {"A": 0.0, "B": ghost["kernel"]["A"], "R": "NOT EVALUATED"}
    forged = RH.read_map(_text(got.entries + [ghost]))
    assert isinstance(forged, RH.Map), forged                      # well-formed on its own: only the report can say it was never read
    assert RH.check(st, forged.drops[0]) is not None, "a map with a place its report never read passed the check"
    unknown = RH.read_map(_map_mut(got.entries, lambda o: o[5].update(state="unknown")))
    assert isinstance(unknown, NS.Unreadable), "a place in the map holds the state of a place never read"
    dropped = RH.read_map(_map_mut(got.entries, lambda o: o.pop(5)))
    assert isinstance(dropped, NS.Unreadable) or RH.check(st, dropped.drops[0]) is not None, "a map missing a reading passed"


def test_r06_truth_in_the_map_is_refused(tmp):
    NS, RH = _lib()
    got = W.drop(tmp, _cells, horizon=BASE + 4 * 1900)
    for key, val in (("K_c", 0.35), ("truth_tick", 603.5), ("true_state", "ordered-side"), ("agree", "resolved-true"), ("actual", [0.35])):
        assert isinstance(RH.read_map(_map_mut(got.entries, lambda o: o[7].update({key: val}))), NS.Unreadable), f"a place with {key} was read"
        assert isinstance(RH.read_map(_map_mut(got.entries, lambda o: o[0].update({key: val}))), NS.Unreadable), f"a head with {key} was read"
        # a reading of something the wire never declared: the head names the declared roles, so the map refuses it standing alone
        assert isinstance(RH.read_map(_map_mut(got.entries, lambda o: o[7]["readings"].update({key: {"value": 0.35, "error": 0.0}}))), NS.Unreadable), f"a reading of {key} was read"
        assert isinstance(RH.read_map(_map_mut(got.entries, lambda o: o[0]["roles"].append(key))), NS.Unreadable), f"a head that declares {key} and places that do not read it"
    assert got.entries[0]["roles"] == ["C", "D"] and all(sorted(e["readings"]) == ["C", "D"] for e in got.entries[1:])
    assert isinstance(RH.read_map(_map_mut(got.entries, lambda o: o[7]["readings"].pop("C"))), NS.Unreadable), "a place missing a declared role was read"
    assert isinstance(RH.read_map(_map_mut(got.entries, lambda o: o[7]["call"].update(K_c=0.35))), NS.Unreadable)
    assert isinstance(RH.read_map(_map_mut(got.entries, lambda o: o[7]["kernel"].update(K_c=0.35))), NS.Unreadable)
    assert isinstance(RH.read_map(_map_mut(got.entries, lambda o: o[7]["readings"]["D"].update(K_c=0.35))), NS.Unreadable)


def test_r07_a_place_with_no_time_index_is_refused(tmp):
    NS, RH = _lib()
    got = W.drop(tmp, _cells, horizon=BASE + 4 * 1900)
    bad = {
        "no index": lambda o: o[7].pop("index"), "a null index": lambda o: o[7].update(index=None),
        "an index that is not the window's end": lambda o: o[7].update(index=o[7]["index"] + 1),
        "no window": lambda o: o[7].pop("window"), "a float index": lambda o: o[7].update(index=float(o[7]["index"])),
        "an index that goes back": lambda o: o[7].update(window=o[6]["window"], index=o[6]["index"]),
        "no clock in the head": lambda o: o[0].pop("clock"), "a clock with no unit": lambda o: o[0]["clock"].pop("index_unit"),
        "no start in the head": lambda o: o[0].pop("start"), "a start with no index": lambda o: o[0]["start"].pop("index"),
        "no lag in the clock": lambda o: o[0]["clock"].pop("lag"), "no settle times in the head": lambda o: o[0].pop("n_eq"), "no skip in the head": lambda o: o[0].pop("skip"),
        "a first place before the drop began": lambda o: o[0]["start"].update(index=o[1]["window"][0]),
        "a seq that skips": lambda o: o[7].update(seq=99), "no tick": lambda o: o[7].pop("tick"),
        "a value that is not the tick's": lambda o: o[7].update(value=o[7]["value"] + 0.001),
        "a tick off the dial": lambda o: o[7].update(tick=1201, value=0.2 + 1201 * 0.3 / 1200),
    }
    for name, f in bad.items():
        assert isinstance(RH.read_map(_map_mut(got.entries, f)), NS.Unreadable), f"read a map with {name}"


def test_r08_a_state_that_does_not_follow_from_its_readings_is_refused(tmp):
    NS, RH = _lib()
    got = W.drop(tmp, _cells, horizon=BASE + 6 * 1900)
    by_class = {c: [i for i, e in enumerate(got.entries) if e.get("class") == c][0] for c in ("SIG-", "SIG+", "UNRES")}
    want = {"SIG-": "disordered-side", "SIG+": "ordered-side", "UNRES": "critical-bracketed"}
    for c, i in by_class.items():
        assert got.entries[i]["state"] == want[c], (c, got.entries[i]["state"])
        for other in set(want.values()) - {want[c]}:
            assert isinstance(RH.read_map(_map_mut(got.entries, lambda o: o[i].update(state=other))), NS.Unreadable), f"{c} read as {other}"
    i = by_class["SIG-"]
    assert isinstance(RH.read_map(_map_mut(got.entries, lambda o: o[i].update({"class": "SIG+", "state": "ordered-side"}))), NS.Unreadable)
    assert isinstance(RH.read_map(_map_mut(got.entries, lambda o: o[i]["readings"]["D"].update(value=0.3))), NS.Unreadable)       # reading changed, state kept
    assert isinstance(RH.read_map(_map_mut(got.entries, lambda o: o[i]["kernel"].update(A=1.0))), NS.Unreadable)
    assert isinstance(RH.read_map(_map_mut(got.entries, lambda o: o[i].update(state="ordered"))), NS.Unreadable)
    # the state list is OPEN across map versions: a state this reader does not know is refused BY NAME, never typed as a known one
    for i_ in by_class.values():
        later = RH.read_map(_map_mut(got.entries, lambda o: o[i_].update(state="discontinuous")))
        assert isinstance(later, NS.Unreadable) and "discontinuous" in later.why and "unknown state" in later.why, later
    newer = RH.read_map(_map_mut(got.entries, lambda o: o[0].update(map="compass-map/2")))
    assert isinstance(newer, NS.Unreadable) and "compass-map/2" in newer.why and "unknown map version" in newer.why, newer
    # ... and BEFORE any other check of that record: a later version may also carry keys this reader has never seen
    newer = RH.read_map(_map_mut(got.entries, lambda o: o[0].update(map="compass-map/2", order_of_line="first")))
    assert isinstance(newer, NS.Unreadable) and "compass-map/2" in newer.why and "unknown map version" in newer.why, newer
    later = RH.read_map(_map_mut(got.entries, lambda o: o[by_class["SIG-"]].update(state="discontinuous", jump=0.4)))
    assert isinstance(later, NS.Unreadable) and "discontinuous" in later.why and "unknown state" in later.why, later
    assert all(RH.state_at(RH.read_map(got.map).drops[0], e["tick"]) in ("ordered-side", "disordered-side", "critical-bracketed", "in-transit") for e in got.entries[1:])
    # a mid-move reading is never typed as a clean place, and a settled one is never typed in transit
    assert isinstance(RH.read_map(_map_mut(got.entries, lambda o: o[i].update(settled=False))), NS.Unreadable), "a mid-move place kept a clean state"
    assert isinstance(RH.read_map(_map_mut(got.entries, lambda o: o[i].update(state="in-transit"))), NS.Unreadable)
    assert isinstance(RH.read_map(_map_mut(got.entries, lambda o: o[i].pop("settled"))), NS.Unreadable)
    hidden = RH.read_map(_map_mut(got.entries, lambda o: o[i].update(settled=False, state="in-transit")))      # the head holds the lag and the start,
    assert isinstance(hidden, NS.Unreadable), "a forged mid-move mark was read"                                   # so the map recomputes the mark alone
    slow = RH.read_map(_map_mut(got.entries, lambda o: o[0]["clock"].update(lag=5000)))                           # the same readings under a longer lag
    assert isinstance(slow, NS.Unreadable), "the settled marks did not change with the declared lag"
    mid = W.drop(tmp, _cells, {**W.CFG, "n_eq": 0}, name="mid", map_name="mid.jsonl", horizon=BASE + 6 * 1000)
    j = [k for k, e in enumerate(mid.entries) if e.get("state") == "in-transit"][0]
    assert isinstance(RH.read_map(mid.map), RH.Map) and len([e for e in mid.entries if e.get("state") == "in-transit"]) >= 10
    for clean in ("ordered-side", "disordered-side", "critical-bracketed"):
        assert isinstance(RH.read_map(_map_mut(mid.entries, lambda o: o[j].update(state=clean))), NS.Unreadable), f"a smeared reading read as {clean}"
    assert isinstance(RH.read_map(_map_mut(mid.entries, lambda o: o[j].update(settled=True))), NS.Unreadable)
    flipped = RH.read_map(_map_mut(got.entries, lambda o: o[0]["sign_rule"].update(ordered_sign="-")))     # the same readings under the other rule
    assert isinstance(flipped, NS.Unreadable), "the states did not change with the declared sign rule"
    turned = RH.read_map(_map_mut(got.entries, lambda o: o[0]["sign_rule"].update(ordered_side="-")))      # the dial's direction is not the state rule
    assert isinstance(turned, RH.Map) and RH.check(RH.read(got.out), turned.drops[0]) is not None
    roles = [{"name": "D", "role": "crossing", "ordered_sign": "-"}, {"name": "C", "role": "peak"}]
    minus = W.drop(tmp, lambda t, i, n: -_cells(t, i, n), name="minus", map_name="minus.jsonl", horizon=BASE + 6 * 1900, declared={"roles": roles})
    assert [e["state"] for e in minus.entries[1:]] == [e["state"] for e in got.entries[1:]] and isinstance(RH.read_map(minus.map), RH.Map)
    assert [e["class"] for e in minus.entries[1:]] != [e["class"] for e in got.entries[1:]]


def test_r09_the_trail_and_sigma_in_both_units(tmp):
    NS, RH = _lib()
    got = W.drop(tmp, _cells, horizon=BASE + 6 * 1900 + 950)
    st = RH.read(got.out)
    trail = RH.trail(st)
    hold = [r for r in got.steps if r["phase"] == "hold" and r["evaluated"]]
    assert list(trail) == [{"step": r["step"], "index": r["index"], "segment": 1, "centre": r["pair"]["centre"], "bracket": r["pair"]["bracket"],
                            "kind": r["verdict"][0]["kind"], "ticks": r["verdict"][0]["ticks"]} for r in hold], trail[:2]
    assert [t["centre"] for t in trail] == [610, 610, 616, 616, 610, 616] and all(a["index"] < b["index"] for a, b in zip(trail, trail[1:]))
    assert RH.sigma(st) == {"g": 0, "ticks": 0, "value": 0.0, "ticks_per_g": 12}, RH.sigma(st)
    phases = ("ignite", "approach", "hold")
    assert RH.settle(st) == {"lag": 48, "floor": 48 + 6 * 67.0, "n_eq": dict(zip(phases, (450, 48, 450))), "mid_move": dict(zip(phases, (False,) * 3)),
                             "relaxed": dict(zip(phases, (True, False, True)))}, RH.settle(st)
    mid = RH.settle(RH.read(W.drop(tmp, _cells, {**W.CFG, "n_eq": 47}, name="m", map_name="m.jsonl", horizon=BASE + 2000).out))
    assert mid["mid_move"] == dict(zip(phases, (False, False, True))) and mid["n_eq"]["hold"] == 47, mid
    pending = RH.read("".join(got.out.splitlines(keepends=True)[:8]))
    assert len(RH.trail(pending)) == 2 and RH.trail(RH.read(got.out.splitlines(keepends=True)[0])) == ()


def test_r10_two_drops_in_one_file(tmp):
    NS, RH = _lib()
    a = W.drop(tmp, _cells, name="a", horizon=BASE + 2 * 1900)
    b = W.drop(tmp, _cells, {**W.CFG, "ops": W.OFF_OPS}, name="b", horizon=11550 + 3 * 1900)       # the same map file: appended
    mp = RH.read_map(b.map)
    assert isinstance(mp, RH.Map) and [d.head["drop"] for d in mp.drops] == ["a", "b"], mp
    assert b.map.startswith(a.map) and RH.check(RH.read(a.out), mp.drops[0]) is None and RH.check(RH.read(b.out), mp.drops[1]) is None
    for d in mp.drops:
        assert set(d.head) == {"rec", "map", "drop", "needle", "dial", "start", "clock", "n_eq", "skip", "roles", "sign_rule", "M"} and d.head["map"] == "compass-map/1"
        assert all(p["drop"] == d.head["drop"] for p in d.places) and [p["seq"] for p in d.places] == list(range(len(d.places)))
    keys = [(p["drop"], p["seq"]) for d in mp.drops for p in d.places]
    assert len(set(keys)) == len(keys)
    assert RH.state_at(mp.drops[0], 598) != "unknown" and RH.state_at(mp.drops[1], 5) == "unknown"
    again = RH.read_map(b.map + a.map)
    assert isinstance(again, NS.Unreadable), "two drops of one name were read as one map"
    assert isinstance(RH.read_map(_text(a.entries[1:])), NS.Unreadable), "a place with no head was read"
    assert isinstance(RH.read_map(""), RH.Map) and RH.read_map("").drops == ()


def test_r11_the_reader_is_pure_and_total():
    NS, RH = _lib()
    tree = ast.parse((ROOT / "needlestream" / "read_hold.py").read_text())
    mods = {a.name.split(".")[0] for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names} | \
           {(n.module or "").split(".")[0] for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)}
    assert mods <= {"json", "dataclasses", "navigator", "needlestream"}, sorted(mods)
    assert not [n for n in ast.walk(tree) if isinstance(n, ast.Name) and n.id in ("open", "print", "exec", "eval", "input")]
    assert not [n for n in ast.walk(tree) if isinstance(n, ast.Attribute) and n.attr in ("read_text", "write_text", "write", "environ", "stdout")]
    for f in (RH.read, RH.read_map):
        for junk in ("", "x", "{}", "[1]\n", '{"rec": 1}\n', '{"rec": "head"}\n', '{"rec": "place"}\n', '{"rec": "start", "schema": []}\n', "\n\n", '{"a": NaN}\n'):
            out = f(junk)
            assert isinstance(out, (NS.Unreadable, RH.Stream, RH.Map)), (f.__name__, junk, out)
            assert not isinstance(out, RH.Stream), (f.__name__, junk)


if __name__ == "__main__":
    import tempfile
    _plain = [test_r11_the_reader_is_pure_and_total]
    _all = [test_r01_every_report_and_every_prefix_reads, test_r02_one_changed_field_is_unreadable,
            test_r03_resolved_cannot_tell_and_no_reading_are_three_cells, test_r04_the_map_reads_and_is_the_map_of_its_report,
            test_r05_an_entry_for_a_place_never_read_and_the_unknown_state, test_r06_truth_in_the_map_is_refused,
            test_r07_a_place_with_no_time_index_is_refused, test_r08_a_state_that_does_not_follow_from_its_readings_is_refused,
            test_r09_the_trail_and_sigma_in_both_units, test_r10_two_drops_in_one_file] + _plain
    _fail = 0
    for _t in _all:
        with tempfile.TemporaryDirectory() as _d:
            try:
                _t() if _t in _plain else _t(Path(_d))
                print(f"PASS {_t.__name__}")
            except Exception as _e:  # noqa: BLE001
                _fail += 1
                print(f"FAIL {_t.__name__}: {type(_e).__name__}: {str(_e)[:400]}")
    print(f"{len(_all) - _fail}/{len(_all)} passed")
    sys.exit(1 if _fail else 0)
