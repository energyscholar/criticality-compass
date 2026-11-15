"""Plan 1529 — the needle-view reader (contract/SCHEMA-1529.md, "The types" and "parse").
A SCHEMA-1525 report is read into a type or refused as a value; nothing else can happen.
FROZEN: the Generator makes this green; it does not edit it.

RED until needleview/report.py and needleview/__main__.py exist.
Run:  python contract/test_needleview_reader.py   (or pytest)
"""
import copy
import dataclasses
import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

FIXDIR = ROOT / "contract" / "fixtures-1529"
NAMES = ("W1-s22", "W2-s24", "W3-s26")
REPORT_KEYS = ("kind", "reason", "bracket", "A_hull", "B_hull", "agree", "rounds")
VERDICT_KEYS = ("truth_K_c", "a", "w_max", "contains", "width", "narrow_enough", "cell", "run_id", "plan")
MOMENTS = ("C", "C_err", "Gs", "Gs_err", "D", "A", "B")


def _path(name):
    return FIXDIR / f"{name}.verdict.json"


def _fix(name="W1-s22"):
    return json.loads(_path(name).read_text())


def _bare(v):
    return {k: v[k] for k in REPORT_KEYS}


def _R():
    from needleview import report  # imported here so a missing module FAILS each test, not the file
    return report


def _load(label, path, truth):
    import needleview.__main__ as m
    return m.load(label, str(path), truth)


def _parse(obj, truth=False, label="x"):
    return _R().parse(label, obj if isinstance(obj, str) else json.dumps(obj), truth)


def budget_report():
    """a fixture with round 3 not evaluated, exactly as the needle writes a budget refusal."""
    v = _bare(_fix())
    r = v["rounds"][2]
    for k in MOMENTS:
        r[k] = None
    r["evaluated"] = False
    r["lo"], r["hi"] = r["grid"][0], r["grid"][-1]
    v.update(kind="REFUSE", reason="budget", bracket=None, A_hull=None, B_hull=None, agree=None)
    return v


def floor_report():
    return {"kind": "REFUSE", "reason": "floor", "bracket": None, "A_hull": None, "B_hull": None, "agree": None, "rounds": []}


def foreign():
    """a Located report from a system nobody has seen: another knob range, grid size, level count and round count."""
    lo, hi, m = -5.0, 12.0, 7
    c = [1.0, 2.0, 5.0, 9.0, 4.0, 2.0, 1.0]
    c_err = [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7]
    gs = [[0.5, 0.5 + d, 0.25 + i / 100.0] for i, d in enumerate([-0.3, -0.2, -0.1, 0.05, 0.1, 0.2, 0.3])]
    gs_err = [[0.01, 0.02 + i / 1000.0, 0.03] for i in range(m)]
    rounds = []
    for r in (1, 2):
        grid = [lo] + [lo + i * (hi - lo) / (m - 1) for i in range(1, m - 1)] + [hi]
        lo, hi = grid[1], grid[5]
        rounds.append({"round": r, "grid": grid, "C": list(c), "C_err": list(c_err), "Gs": copy.deepcopy(gs),
                       "Gs_err": copy.deepcopy(gs_err), "D": [g[1] - g[0] for g in gs], "A": [3], "B": [2, 3],
                       "lo": lo, "hi": hi, "index": 700 * r, "evaluated": True})
    g = rounds[-1]["grid"]
    return {"kind": "Located", "reason": None, "bracket": [lo, hi], "A_hull": [g[3], g[3]], "B_hull": [g[2], g[3]],
            "agree": True, "rounds": rounds}


def test_r1_fixtures_load_as_located():
    R = _R()
    for name in NAMES:
        v = _fix(name)
        run = _load(name, _path(name), False)
        assert isinstance(run, R.Run), (name, run)
        assert run.label == name and run.overlay is None
        rep = run.report
        assert isinstance(rep, R.Located) and len(rep.rounds) == 5 and rep.agree is v["agree"]
        for got, want in zip(rep.rounds, v["rounds"]):
            assert isinstance(got, R.Evaluated) and len(got.grid) == 9
            assert got.grid == tuple(want["grid"]) and got.C == tuple(want["C"]) and got.C_err == tuple(want["C_err"])
            assert got.Gs == tuple(tuple(x) for x in want["Gs"]) and got.Gs_err == tuple(tuple(x) for x in want["Gs_err"])
            assert got.D == tuple(want["D"]) and got.A == tuple(want["A"]) and got.B == tuple(want["B"])
            assert (got.round, got.lo, got.hi, got.index) == (want["round"], want["lo"], want["hi"], want["index"])
        assert [rep.rounds[-1].lo, rep.rounds[-1].hi] == v["bracket"]


def test_r2_overlay_only_on_request_and_only_from_a_verdict():
    R = _R()
    for name in NAMES:
        v = _fix(name)
        blind, seen = _load(name, _path(name), False), _load(name, _path(name), True)
        assert isinstance(seen, R.Run) and isinstance(seen.overlay, R.Overlay)
        o = seen.overlay
        assert (o.truth_K_c, o.a, o.w_max, o.contains, o.cell) == (v["truth_K_c"], v["a"], v["w_max"], v["contains"], v["cell"])
        assert seen.report == blind.report
        bare = _parse(_bare(v), truth=True, label=name)  # a bare report: the truth is absent, not zero
        assert isinstance(bare, R.Run) and bare.overlay is None and bare.report == blind.report
        assert _parse(_bare(v), truth=False, label=name) == blind


def _mutations():
    """(name, text-or-object) — each must be refused."""
    out = [("not json", "not json{"), ("a list", "[1, 2]"), ("a string", '"Located"'), ("empty text", "")]

    def mut(name, f, base=_fix):
        v = base()
        f(v)
        out.append((name, v))

    def r0(v):
        return v["rounds"][0]

    mut("rounds deleted", lambda v: v.pop("rounds"))
    mut("agree deleted", lambda v: v.pop("agree"))
    mut("kind ABSENT", lambda v: v.update(kind="ABSENT"))
    mut("rounds not a list", lambda v: v.update(rounds={}))
    mut("C one short", lambda v: r0(v)["C"].pop())
    mut("lo equals hi", lambda v: r0(v).update(lo=r0(v)["hi"]))
    mut("lo below the grid", lambda v: r0(v).update(lo=r0(v)["grid"][0] - 0.01))
    mut("hi above the grid", lambda v: r0(v).update(hi=r0(v)["grid"][-1] + 0.01))
    mut("A holds m", lambda v: r0(v)["A"].append(9))
    mut("A empty", lambda v: r0(v).update(A=[]))
    mut("B not increasing", lambda v: r0(v).update(B=[4, 3]))
    mut("A holds a bool", lambda v: r0(v).update(A=[True]))
    mut("NaN in C", lambda v: r0(v)["C"].__setitem__(2, float("nan")))
    mut("Infinity in D", lambda v: r0(v)["D"].__setitem__(2, float("inf")))
    mut("negative C_err", lambda v: r0(v)["C_err"].__setitem__(0, -1.0))
    mut("negative Gs_err", lambda v: r0(v)["Gs_err"][0].__setitem__(0, -1.0))
    mut("evaluated with C null", lambda v: r0(v).update(C=None))
    mut("bool in grid", lambda v: r0(v)["grid"].__setitem__(0, True))
    mut("JSON int in grid", lambda v: r0(v)["grid"].__setitem__(0, 0))
    mut("JSON int in C", lambda v: r0(v)["C"].__setitem__(0, 1))
    mut("grid not increasing", lambda v: r0(v)["grid"].__setitem__(1, r0(v)["grid"][0]))
    mut("grid of one point", lambda v: r0(v).update(grid=[0.2]))
    mut("one Gs level", lambda v: r0(v).update(Gs=[[g[0]] for g in r0(v)["Gs"]], Gs_err=[[g[0]] for g in r0(v)["Gs_err"]]))
    mut("ragged Gs", lambda v: r0(v)["Gs"][3].append(0.5))
    mut("round number wrong", lambda v: v["rounds"][1].update(round=5))
    mut("index a float", lambda v: r0(v).update(index=1.0))
    mut("evaluated not a bool", lambda v: r0(v).update(evaluated=1))
    mut("round key missing", lambda v: r0(v).pop("D"))
    mut("round key extra", lambda v: r0(v).update(extra=1.0))
    mut("bracket off the last round", lambda v: v.update(bracket=[v["bracket"][0], v["bracket"][1] + 0.001]))
    mut("Located with a reason", lambda v: v.update(reason="floor"))
    mut("Located with no round", lambda v: v.update(rounds=[]))
    mut("Located with agree null", lambda v: v.update(agree=None))
    mut("A_hull reversed", lambda v: v.update(A_hull=[0.4, 0.3]))
    mut("Located with an unevaluated round", lambda v: v.update(rounds=budget_report()["rounds"]))
    mut("unevaluated with C kept", lambda v: v["rounds"][2].update(C=_fix()["rounds"][2]["C"]), budget_report)
    mut("REFUSE with a hull", lambda v: v.update(A_hull=[0.3, 0.4]), budget_report)
    mut("REFUSE with a bracket", lambda v: v.update(bracket=[0.3, 0.4]), budget_report)
    mut("budget with every round evaluated", lambda v: v.update(rounds=_fix()["rounds"]), budget_report)
    mut("floor with rounds", lambda v: v.update(rounds=_fix()["rounds"]), floor_report)
    mut("budget with no round", lambda v: v.update(reason="budget"), floor_report)
    mut("REFUSE with an unknown reason", lambda v: v.update(reason="tired"), floor_report)
    return out


def test_r3_everything_else_is_unreadable():
    R = _R()
    for name, thing in _mutations():
        for truth in (False, True):
            got = _parse(thing, truth=truth, label="lbl")
            assert isinstance(got, R.Unreadable), (name, truth, type(got).__name__)
            assert got.label == "lbl" and isinstance(got.why, str) and got.why.strip(), name
    v = _fix()
    v["zzz"] = 1.0  # M1: only the seven report keys and the nine verdict keys may appear
    got = _parse(v)
    assert isinstance(got, R.Unreadable) and "unknown key" in got.why and "zzz" in got.why, got
    got = _parse(dict(_fix(), kind="ABSENT"))
    assert isinstance(got, R.Unreadable) and "ABSENT" in got.why, got
    with tempfile.TemporaryDirectory() as d:
        bad = Path(d) / "bytes.json"
        bad.write_bytes(b"\xff\xfe{\x80")
        for name, p in (("missing", Path(d) / "nope.json"), ("a directory", Path(d)), ("not utf-8", bad)):
            got = _load("lbl", p, False)
            assert isinstance(got, R.Unreadable) and got.label == "lbl" and got.why.strip(), (name, got)


def test_r4_budget_keeps_the_unevaluated_round():
    R = _R()
    v = budget_report()
    run = _parse(v)
    assert isinstance(run, R.Run) and isinstance(run.report, R.Budget) and run.overlay is None, run
    rs = run.report.rounds
    assert len(rs) == 5 and [isinstance(r, R.NotEvaluated) for r in rs] == [False, False, True, False, False]
    want = v["rounds"][2]
    assert rs[2] == R.NotEvaluated(3, tuple(want["grid"]), want["lo"], want["hi"], want["index"])


def test_r5_floor_is_its_own_value():
    R = _R()
    run = _parse(floor_report())
    assert isinstance(run, R.Run) and run.report == R.Floor() and run.overlay is None, run
    assert not dataclasses.fields(R.Floor)


def test_r6_a_system_nobody_has_seen():
    R = _R()
    run = _parse(foreign())
    assert isinstance(run, R.Run) and isinstance(run.report, R.Located), run
    rs = run.report.rounds
    assert len(rs) == 2 and all(len(r.grid) == 7 for r in rs) and rs[0].grid[0] == -5.0 and rs[0].grid[-1] == 12.0
    assert all(len(row) == 3 for r in rs for row in r.Gs) and rs[1].A == (3,) and rs[1].B == (2, 3)


def test_r7_types_are_frozen_and_hold_tuples():
    R = _R()
    names = ("Run", "Unreadable", "Located", "Floor", "Budget", "Evaluated", "NotEvaluated", "Overlay")
    for n in names:
        assert dataclasses.is_dataclass(getattr(R, n)), n
    assert [f.name for f in dataclasses.fields(R.Run)] == ["label", "report", "overlay"]
    assert [f.name for f in dataclasses.fields(R.Unreadable)] == ["label", "why"]
    assert [f.name for f in dataclasses.fields(R.Located)] == ["rounds", "agree"]
    assert [f.name for f in dataclasses.fields(R.Budget)] == ["rounds"]
    assert [f.name for f in dataclasses.fields(R.Evaluated)] == ["round", "grid", "C", "C_err", "Gs", "Gs_err", "D", "A", "B",
                                                                 "lo", "hi", "index"]
    assert [f.name for f in dataclasses.fields(R.NotEvaluated)] == ["round", "grid", "lo", "hi", "index"]
    assert [f.name for f in dataclasses.fields(R.Overlay)] == ["truth_K_c", "a", "w_max", "contains", "cell"]
    run = _load("x", _path("W1-s22"), True)
    r0 = run.report.rounds[0]
    for obj, field in ((run, "label"), (run.report, "agree"), (r0, "lo"), (run.overlay, "cell"), (R.Unreadable("a", "b"), "why")):
        try:
            setattr(obj, field, None)
        except dataclasses.FrozenInstanceError:
            continue
        raise AssertionError(f"{type(obj).__name__}.{field} could be assigned")
    assert isinstance(run.report.rounds, tuple) and isinstance(r0.grid, tuple) and isinstance(r0.A, tuple)
    assert isinstance(r0.Gs, tuple) and isinstance(r0.Gs[0], tuple)


def test_r8_a_malformed_truth_is_refused_never_dropped():
    R = _R()
    tails = [("cell MAYBE", lambda v: v.update(cell="MAYBE")), ("truth deleted", lambda v: v.pop("truth_K_c")),
             ("truth a string", lambda v: v.update(truth_K_c="0.35")), ("truth NaN", lambda v: v.update(truth_K_c=float("nan"))),
             ("only run_id", lambda v: [v.pop(k) for k in VERDICT_KEYS if k != "run_id"]),
             ("REFUSED on a Located", lambda v: v.update(cell="REFUSED", contains=None, width=None, narrow_enough=None)),
             ("contains null on a HIT", lambda v: v.update(contains=None)), ("negative a", lambda v: v.update(a=-0.1)),
             ("w_max zero", lambda v: v.update(w_max=0.0))]
    for name, f in tails:
        v = _fix()
        f(v)
        got = _parse(v, truth=True)
        assert isinstance(got, R.Unreadable) and "truth" in got.why, (name, got)
        blind = _parse(v, truth=False)  # with truth off the values are never read
        assert isinstance(blind, R.Run) and blind.overlay is None, (name, blind)
    refused = dict(floor_report(), truth_K_c=0.35, a=0.003, w_max=0.02, contains=None, width=None, narrow_enough=None,
                   cell="REFUSED", run_id="0" * 16, plan="1525")
    got = _parse(refused, truth=True)
    assert isinstance(got, R.Run) and got.report == R.Floor() and got.overlay == R.Overlay(0.35, 0.003, 0.02, None, "REFUSED")
    got = _parse(dict(refused, cell="HIT"), truth=True)
    assert isinstance(got, R.Unreadable) and "truth" in got.why, got


if __name__ == "__main__":
    tests = [(n, f) for n, f in sorted(globals().items()) if n.startswith("test_") and callable(f)]
    ok = 0
    for n, f in tests:
        try:
            f()
            ok += 1
            print(f"ok   {n}")
        except Exception as e:  # noqa: BLE001 — a failed test is reported, the rest still run
            print(f"FAIL {n}: {type(e).__name__}: {str(e)[:300]}")
    print(f"{ok}/{len(tests)} passed")
    sys.exit(0 if ok == len(tests) and tests else 1)
