"""Plan 1531 - the needle's report as an append-only event stream (contract/SCHEMA-1531.md, "The stream").
One event per run start, one per round, one per outcome. The stream alone rebuilds the report. What only the System
knows enters through two fields, and each is a value or Unknown. FROZEN: the Generator makes this green; it does not edit it.

RED until needleview/player/stream.py exists.
Run:  python contract/test_needleplayer_stream.py   (or pytest)
"""
import dataclasses
import copy
import json
import subprocess
import sys
import tempfile
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

FIXDIR = ROOT / "contract" / "fixtures-1529"
NAMES = ("W1-s22", "W2-s24", "W3-s26")
REPORT_KEYS = ("kind", "reason", "bracket", "A_hull", "B_hull", "agree", "rounds")
OUTCOME_KEYS = ("kind", "reason", "bracket", "A_hull", "B_hull", "agree")
MOMENTS = ("C", "C_err", "Gs", "Gs_err", "D", "A", "B")
DASH = "—"
UNKNOWN = "UNKNOWN"
LATER = "not reported (stage 2)"
TOL = 0.011


# ---------- the reports ----------
def _fix(name="W1-s22"):
    return json.loads((FIXDIR / f"{name}.verdict.json").read_text())


def _bare(v):
    return {k: copy.deepcopy(v[k]) for k in REPORT_KEYS}


def tampered(v, k_c):
    """a copy in which ALL NINE scored values differ from the original, and still form a well-formed verdict tail."""
    t = dict(v)
    t.update(truth_K_c=k_c, a=v["a"] + 0.5, w_max=v["w_max"] + 0.5, contains=not v["contains"], width=v["width"] + 0.25,
             narrow_enough=not v["narrow_enough"], cell="MISS" if v["cell"] == "HIT" else "HIT", run_id="0" * 16, plan="9999")
    assert all(t[k] != v[k] for k in t if k not in REPORT_KEYS) and len(t) == 16
    return t


def budget_report():
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


def scored_floor():
    v = floor_report()
    v.update(truth_K_c=0.35, a=0.003, w_max=0.02, contains=None, width=None, narrow_enough=None, cell="REFUSED",
             run_id="0" * 16, plan="1525")
    return v


def foreign():
    """a report from a system nobody has seen: range [-5, 12], m = 7, three levels, two rounds."""
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


def flat_report():
    """every C equal with zero error, every D and its error zero, every Gs equal: all three scales are Flat."""
    v = foreign()
    for r in v["rounds"]:
        m = len(r["grid"])
        r["C"], r["C_err"], r["D"] = [3.0] * m, [0.0] * m, [0.0] * m
        r["Gs"], r["Gs_err"] = [[0.5, 0.5, 0.5] for _ in range(m)], [[0.0, 0.0, 0.0] for _ in range(m)]
    return v


# ---------- the package under test (imported inside the tests, so a missing module FAILS each test, not the file) ----------
def _S():
    from needleview.player import stream
    return stream


def _R():
    from needleview import report
    return report


def _stream(specs, truth=False):
    """specs: [(world, label, report dict or raw text)] -> the events of all of them, run i = position."""
    out = ()
    for i, (world, label, v) in enumerate(specs):
        text = v if isinstance(v, str) else json.dumps(v)
        got = _S().events(i, world, label, text, truth)
        assert isinstance(got, tuple) and got
        out += got
    return out


def _fixture_specs():
    return [(n.split("-")[0], n.split("-")[1], _fix(n)) for n in NAMES]


def _main(tests):
    ok = 0
    for n, f in tests:
        try:
            f()
            ok += 1
            print(f"ok   {n}")
        except Exception as e:  # noqa: BLE001 - a failed test is reported, the rest still run
            print(f"FAIL {n}: {type(e).__name__}: {str(e)[:300]}")
    print(f"{ok}/{len(tests)} passed")
    sys.exit(0 if ok == len(tests) and tests else 1)


# ---------- the tests ----------
FIELDS = {"Unknown": (), "Known": ("truth_K_c", "a", "w_max"), "Scored": ("cell", "contains"),
          "RunStart": ("run", "world", "label", "system"), "RoundEv": ("run", "rnd"),
          "Outcome": ("run", "kind", "reason", "bracket", "A_hull", "B_hull", "agree", "score"), "Refused": ("run", "why")}


def _pair(v):
    return None if v is None else tuple(v)


def test_s1_types_and_the_events_of_a_run():
    S, R = _S(), _R()
    for name, fields in FIELDS.items():
        cls = getattr(S, name)
        assert dataclasses.is_dataclass(cls) and tuple(f.name for f in dataclasses.fields(cls)) == fields, name
        assert cls.__dataclass_params__.frozen, name
    assert S.Unknown() == S.Unknown() and S.UNKNOWN == UNKNOWN
    for i, n in enumerate(NAMES):
        v = _fix(n)
        text = json.dumps(v)
        got = S.events(i, "world-x", n, text, False)
        assert isinstance(got, tuple) and len(got) == 7, len(got)
        assert got[0] == S.RunStart(i, "world-x", n, S.Unknown())
        run = R.parse(n, text, False)
        for j in range(5):
            assert got[1 + j] == S.RoundEv(i, run.report.rounds[j]), (n, j)
        assert got[6] == S.Outcome(i, "Located", None, _pair(v["bracket"]), _pair(v["A_hull"]), _pair(v["B_hull"]), v["agree"],
                                   S.Unknown())
        assert S.events(i, "world-x", n, text, False) == got, "events is a function of its arguments"


def _rebuild(encoded):
    """from the encoded stream ALONE: {run: report dict or ('unreadable', why)} and {run: (world, label)}."""
    reports, names = {}, {}
    for e in encoded:
        i = e["run"]
        if e["ev"] == "run":
            assert set(e) == {"ev", "run", "world", "label", "system"} and i not in names, e
            names[i] = (e["world"], e["label"])
            reports[i] = {"rounds": []}
        elif e["ev"] == "round":
            assert set(e) == {"ev", "run", "nav"} and len(e["nav"]) == 13, sorted(e)
            reports[i]["rounds"].append(e["nav"])
        elif e["ev"] == "outcome":
            assert set(e) == {"ev", "run", "nav", "score"} and tuple(e["nav"]) == OUTCOME_KEYS, sorted(e)
            reports[i].update(e["nav"])
        else:
            assert e["ev"] == "unreadable" and set(e) == {"ev", "run", "why"}, e
            assert reports[i] == {"rounds": []}
            reports[i] = ("unreadable", e["why"])
    return reports, names


def test_s2_the_stream_alone_rebuilds_every_report():
    specs = _fixture_specs() + [("far", "made-up", foreign()), ("far", "budget", budget_report()), ("far", "floor", floor_report()),
                                ("far", "junk", "{not json")]
    enc = _S().encode(_stream(specs))
    assert isinstance(enc, list) and all(type(e) is dict for e in enc)
    again = json.loads(json.dumps(enc))
    assert again == enc, "the encoding survives JSON unchanged"
    reports, names = _rebuild(again)
    assert len(reports) == len(specs)
    for i, (world, label, v) in enumerate(specs):
        assert names[i] == (world, label)
        if isinstance(v, str):
            assert reports[i][0] == "unreadable" and reports[i][1]
        else:
            assert reports[i] == _bare(v), (label, "the seven report keys, exactly")
    runs = [e["run"] for e in enc]
    assert runs == sorted(runs), "one run after another in the static build"
    assert [e["ev"] for e in enc if e["run"] == 5] == ["run", "outcome"], "a floor refusal has no round"
    assert [e["ev"] for e in enc if e["run"] == 4] == ["run"] + ["round"] * 5 + ["outcome"]
    assert enc[[e["run"] for e in enc].index(4) + 3]["nav"]["evaluated"] is False


def test_s3_the_system_is_a_value_or_unknown():
    S = _S()
    v = _fix()
    on = S.events(0, "w", "l", json.dumps(v), True)
    assert on[0].system == S.Known(v["truth_K_c"], v["a"], v["w_max"])
    assert on[-1].score == S.Scored(v["cell"], v["contains"])
    assert on[1:-1] == S.events(0, "w", "l", json.dumps(v), False)[1:-1], "the rounds do not depend on the truth switch"
    bare = S.events(0, "w", "l", json.dumps(_bare(v)), True)
    assert bare[0].system == S.Unknown() and bare[-1].score == S.Unknown(), "a bare report is an unknown system, even on request"
    fl = S.events(0, "w", "l", json.dumps(scored_floor()), True)
    assert fl == (S.RunStart(0, "w", "l", S.Known(0.35, 0.003, 0.02)),
                  S.Outcome(0, "REFUSE", "floor", None, None, None, None, S.Scored("REFUSED", None)))
    enc_on, enc_off = S.encode(on), S.encode(S.events(0, "w", "l", json.dumps(v), False))
    assert enc_on[0]["system"] == {"truth_K_c": v["truth_K_c"], "a": v["a"], "w_max": v["w_max"]}
    assert enc_on[-1]["score"] == {"cell": v["cell"], "contains": v["contains"]}
    assert enc_off[0]["system"] == UNKNOWN and enc_off[-1]["score"] == UNKNOWN, "UNKNOWN is a declared value, not null"


def test_s4_with_the_truth_off_no_scored_value_can_reach_the_stream():
    S = _S()
    for n in NAMES:
        v = _fix(n)
        base = S.events(0, "w", n, json.dumps(v), False)
        assert S.events(0, "w", n, json.dumps(tampered(v, 0.123456)), False) == base, n
        assert S.events(0, "w", n, json.dumps(_bare(v)), False) == base, n
        text = json.dumps(S.encode(base))
        for needle in (repr(v["truth_K_c"]), "0.123456", '"cell"', '"truth_K_c"', '"w_max"'):
            assert needle not in text, (n, needle)
        seen = S.events(0, "w", n, json.dumps(tampered(v, 0.123456)), True)
        assert seen != S.events(0, "w", n, json.dumps(v), True), "with the truth ON the same change must show (this check can fail)"


def test_s5_an_unreadable_input_is_two_events_never_an_exception():
    S = _S()
    v = _fix()
    broken = dict(v, kind="ABSENT")
    bad_truth = dict(v, cell="MAYBE")
    for text in ("{not json", "[1, 2]", json.dumps(broken), json.dumps(dict(v, extra=1))):
        for truth in (False, True):
            got = S.events(3, "w", "l", text, truth)
            assert len(got) == 2 and got[0] == S.RunStart(3, "w", "l", S.Unknown()), got[0]
            assert isinstance(got[1], S.Refused) and got[1].run == 3 and got[1].why, got[1]
    assert "ABSENT" in S.events(0, "w", "l", json.dumps(broken), False)[1].why
    got = S.events(0, "w", "l", json.dumps(bad_truth), True)
    assert len(got) == 2 and isinstance(got[1], S.Refused) and "truth" in got[1].why, "a malformed truth is refused, never dropped"
    assert got[0].system == S.Unknown()
    assert len(S.events(0, "w", "l", json.dumps(bad_truth), False)) == 7, "with the truth off it is never read"
    assert S.refused(2, "w", "l", "because") == (S.RunStart(2, "w", "l", S.Unknown()), S.Refused(2, "because"))
    assert S.encode(S.refused(2, "w", "l", "because"))[1] == {"ev": "unreadable", "run": 2, "why": "because"}


def test_s6_refusals_and_a_system_nobody_has_seen():
    S, R = _S(), _R()
    fl = S.events(0, "w", "l", json.dumps(floor_report()), False)
    assert fl == (S.RunStart(0, "w", "l", S.Unknown()), S.Outcome(0, "REFUSE", "floor", None, None, None, None, S.Unknown()))
    bu = S.events(0, "w", "l", json.dumps(budget_report()), False)
    assert len(bu) == 7 and isinstance(bu[3].rnd, R.NotEvaluated) and isinstance(bu[2].rnd, R.Evaluated)
    assert bu[-1] == S.Outcome(0, "REFUSE", "budget", None, None, None, None, S.Unknown())
    nav = S.encode(bu)[3]["nav"]
    assert all(nav[k] is None for k in MOMENTS) and nav["evaluated"] is False and set(nav) == set(budget_report()["rounds"][2])
    v = foreign()
    fo = S.events(0, "w", "l", json.dumps(v), False)
    assert len(fo) == 4 and len(fo[1].rnd.grid) == 7 and len(fo[1].rnd.Gs[0]) == 3
    assert fo[-1].bracket == tuple(v["bracket"]) and fo[-1].B_hull == tuple(v["B_hull"]) and fo[-1].agree is True


def test_s7_labels_are_carried_never_inferred():
    S = _S()
    world, label = 'Q & <b>"x"', "s/1=é</script>"
    got = S.events(41, world, label, json.dumps(_bare(_fix())), False)
    assert (got[0].run, got[0].world, got[0].label) == (41, world, label)
    assert all(e.run == 41 for e in got)
    enc = S.encode(got)
    assert enc[0]["world"] == world and enc[0]["label"] == label and all(e["run"] == 41 for e in enc)
    two = _stream([("a", "x", _fix("W1-s22")), ("b", "x", _fix("W2-s24"))])
    assert two == S.events(0, "a", "x", json.dumps(_fix("W1-s22")), False) + S.events(1, "b", "x", json.dumps(_fix("W2-s24")), False)


if __name__ == "__main__":
    _main([(n, f) for n, f in sorted(globals().items()) if n.startswith("test_") and callable(f)])
