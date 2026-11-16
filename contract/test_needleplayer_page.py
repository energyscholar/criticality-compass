"""Plan 1531 - the needle player page (contract/SCHEMA-1531.md, "The fragments", "The page", "The script", "The CLI").
One page, one round on show. Every fragment is a function of the events before it. Every drawn element names its source.
The geometry is the needle view's, mark for mark. FROZEN: the Generator makes this green; it does not edit it.

RED until the six needleview/player modules exist.
Run:  python contract/test_needleplayer_page.py   (or pytest)
"""
import re
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


# ---------- reading the page back ----------
class _Page(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.els, self.stack = [], []

    def _el(self, tag, attrs):
        a = dict(attrs)
        el = {"tag": tag, "a": a, "cls": set((a.get("class") or "").split()), "text": "", "own": "", "anc": list(self.stack)}
        self.els.append(el)
        return el

    def handle_starttag(self, tag, attrs):
        el = self._el(tag, attrs)
        if tag not in VOID:   # a void element holds nothing, with or without a closing slash
            self.stack.append(el)

    def handle_startendtag(self, tag, attrs):
        self._el(tag, attrs)

    def handle_endtag(self, tag):
        for i in range(len(self.stack) - 1, -1, -1):
            if self.stack[i]["tag"] == tag:
                del self.stack[i:]
                return

    def handle_data(self, data):
        for el in self.stack:
            el["text"] += data
        if self.stack:
            self.stack[-1]["own"] += data


VOID = {"meta", "input", "br", "hr"}


def _els(page):
    p = _Page()
    p.feed(page)
    p.close()
    return p.els


def _in(e, anc):
    return any(a is anc for a in e["anc"])


def _sel(els, tag=None, cls=None, within=None):
    return [e for e in els if (tag is None or e["tag"] == tag) and (cls is None or cls in e["cls"])
            and (within is None or _in(e, within))]


def _one(els, tag=None, cls=None, within=None):
    got = _sel(els, tag, cls, within)
    assert len(got) == 1, (tag, cls, len(got))
    return got[0]


def _by_id(els, ident):
    got = [e for e in els if e["a"].get("id") == ident]
    assert len(got) == 1, (ident, len(got))
    return got[0]


def _sections(els):
    return _sel(els, "section", "run")


def _frags(els, kind=None, within=None):
    return [e for e in els if "data-ev" in e["a"] and (kind is None or e["a"]["data-ev"] == kind) and (within is None or _in(e, within))]


def _slots(els, within):
    out = {}
    for e in _sel(els, None, "slot", within):
        assert e["a"]["data-slot"] not in out, ("slot twice", e["a"]["data-slot"])
        out[e["a"]["data-slot"]] = e
    return out


def _slot_is(slot, state, text, v="same"):
    assert slot["a"]["data-state"] == state and slot["text"].strip() == text, (slot["a"], slot["text"])
    if state == "value":
        assert slot["a"].get("data-v") == (text if v == "same" else v), slot["a"]
    else:
        assert "data-v" not in slot["a"], slot["a"]


def _render(stream):
    from needleview.player import page
    got = page.render(stream)
    assert isinstance(got, str) and got
    return got


def _F(stream):
    from needleview.player import frame
    got = frame.fragments(stream)
    assert isinstance(got, tuple) and all(isinstance(f, str) for f in got)
    return got


def _cli(args, cwd=ROOT):
    return subprocess.run([sys.executable, "-m", "needleview.player"] + [str(a) for a in args], cwd=cwd, capture_output=True, text=True)


def _mixed_specs():
    return _fixture_specs() + [("far", "made-up", foreign()), ("far", "budget", budget_report()), ("far", "floor", floor_report()),
                               ("far", "junk", "{not json"), ("far", "flat", flat_report())]


def _frames(els, sec):
    return _sel(els, "svg", "frame", sec)


FORBIDDEN = ("http:", "https:", "<link", "<img", "<iframe", "<object", "<embed", "@import", "url(", "<path", "src=", "srcdoc", "xlink")
NAV_SLOTS = ("belief", "verdict", "kind", "reason", "lo", "hi", "width", "agree", "A_hull", "B_hull")
SYS_SLOTS = ("truth_K_c", "a", "w_max", "cell", "contains")
NAV_MARKS = ("tick", "c", "c-err", "d", "d-err", "zero", "g", "next", "trail", "not-evaluated", "rnd", "body", "frame", "why")
SYS_MARKS = ("truth", "truth-off", "sys-unknown")


# ---------- the tests ----------
def test_p01_one_file_no_network():
    page = _render(_stream(_mixed_specs()))
    assert page.startswith("<!doctype html>") and "<title>Needle player</title>" in page
    low = page.lower()
    for bad in FORBIDDEN:
        assert bad not in low, bad
    els = _els(page)
    scripts = _sel(els, "script")
    assert len(scripts) == 2, len(scripts)
    assert scripts[0]["a"] == {"type": "application/json", "id": "stream"}, scripts[0]["a"]
    assert scripts[1]["a"] == {}, "the player script has no attribute: no src, no type"
    assert len(_sel(els, "noscript")) == 1 and len(_sel(els, "style")) == 1
    assert _render(_stream(_mixed_specs())) == page, "render is a function of the stream"


def test_p02_the_page_carries_its_stream():
    S = _S()
    specs = _mixed_specs() + [("far", "s</script><b>x", _bare(_fix()))]
    for truth in (False, True):
        st = _stream(specs, truth)
        page = _render(st)
        els = _els(page)
        block = _by_id(els, "stream")
        assert "<" not in block["text"], "no '<' inside the data block, so it cannot end early"
        assert json.loads(block["text"]) == S.encode(st), "the block is the encoded stream"
        assert len(_sel(els, "script")) == 2 and len(_sections(els)) == len(specs)


def test_p03_fragments_are_append_only():
    S = _S()
    for truth in (False, True):
        st = _stream(_mixed_specs(), truth)
        full = _F(st)
        assert len(full) == len(st)
        for k in range(len(st) + 1):
            assert _F(st[:k]) == full[:k], ("an event changed an earlier fragment", k)
        kinds = {S.RunStart: "run", S.RoundEv: "round", S.Outcome: "outcome", S.Refused: "unreadable"}
        for e, f in zip(st, full):
            els = _els(f)
            root = els[0]
            assert root["a"]["data-ev"] == kinds[type(e)] and root["a"]["data-run"] == str(e.run), root["a"]
            assert all(_in(x, root) for x in els[1:]), "a fragment is ONE element"
            assert len(_frags(els)) == 1
        a, b = [e for e in st if e.run == 0], [e for e in st if e.run == 3]
        mixed = [x for pair in zip(a, b) for x in pair] + a[len(b):] + b[len(a):]
        got = dict(zip(map(id, mixed), _F(tuple(mixed))))
        want = dict(zip(map(id, st), full))
        assert all(got[id(e)] == want[id(e)] for e in mixed), "a fragment depends only on the earlier events of ITS run"
        page = _render(st)
        for run in sorted({e.run for e in st}):
            joined = "".join(f for e, f in zip(st, full) if e.run == run)
            assert page.count(joined + "</section>") == 1, ("a section holds exactly its run's fragments, in order", run)


def _marks(els, svg, tag, cls):
    return _sel(els, tag, cls, svg)


COMPARE = (("line", "tick", ("data-k",), ("x1", "x2")),
           ("circle", "c", ("class", "data-i", "data-k", "data-v", "data-err"), ("cx", "cy")),
           ("line", "c-err", ("data-i",), ("x1", "x2", "y1", "y2")),
           ("circle", "d", ("class", "data-i", "data-k", "data-v", "data-sig"), ("cx", "cy")),
           ("line", "d-err", ("data-i",), ("x1", "x2", "y1", "y2")),
           ("line", "zero", (), ("x1", "x2", "y1", "y2")),
           ("circle", "g", ("data-level", "data-i", "data-k", "data-v", "data-err"), ("cx", "cy")),
           ("rect", "next", ("data-lo", "data-hi"), ("x", "width")),
           ("line", "truth", ("data-k",), ("x1", "x2")),
           ("polygon", "truth-off", ("data-side",), ()),
           ("text", "not-evaluated", (), ()))


def _same_marks(els_a, svg_a, els_b, svg_b, where):
    for tag, cls, exact, near in COMPARE:
        a, b = _marks(els_a, svg_a, tag, cls), _marks(els_b, svg_b, tag, cls)
        assert len(a) == len(b), (where, cls, len(a), len(b))
        for x, y in zip(a, b):
            for k in exact:
                va, vb = x["a"].get(k), y["a"].get(k)
                if k == "class":
                    va, vb = x["cls"] & {"in-A", "in-B"}, y["cls"] & {"in-A", "in-B"}
                assert va == vb, (where, cls, k, va, vb)
            for k in near:
                assert abs(float(x["a"][k]) - float(y["a"][k])) <= TOL, (where, cls, k, x["a"][k], y["a"][k])
    assert len(_sel(els_a, "circle", None, svg_a)) == len(_sel(els_b, "circle", None, svg_b)), (where, "an extra circle")


def test_p04_the_geometry_is_the_needle_views_mark_for_mark():
    from needleview import draw
    R = _R()
    cases = [(n, _fix(n)) for n in NAMES] + [("made-up", foreign()), ("budget", budget_report()), ("flat", flat_report()),
                                              ("low", tampered(_fix(), 0.123456)), ("high", tampered(_fix(), 0.9))]
    for truth in (False, True):
        st = _stream([("w", n, v) for n, v in cases], truth)
        els = _els(_render(st))
        old = _els(draw.render([R.parse(n, json.dumps(v), truth) for n, v in cases]))
        secs, old_secs = _sections(els), _sel(old, "section", "run")
        assert len(secs) == len(old_secs) == len(cases)
        for (n, v), sec, osec in zip(cases, secs, old_secs):
            new, was = _frames(els, sec), _sel(old, "svg", "round", osec)
            assert len(new) == len(was) == len(v["rounds"]), (n, len(new))
            for r, a, b in zip(v["rounds"], new, was):
                for k in ("data-round", "data-evaluated", "data-x0", "data-x1", "data-lo", "data-hi"):
                    assert a["a"][k] == b["a"][k], (n, k)
                assert a["a"]["viewbox"] == "0 0 300 320", a["a"]
                _same_marks(els, a, old, b, (n, r["round"], truth))
                sys_marks = _marks(els, a, "line", "truth") + _marks(els, a, "polygon", "truth-off") + _marks(els, a, "text", "sys-unknown")
                assert len(sys_marks) == 1, (n, r["round"], "exactly one mark for the system's K_c: where it is, or UNKNOWN")
                scored = truth and "truth_K_c" in v
                assert ("sys-unknown" in sys_marks[0]["cls"]) == (not scored), (n, truth)
                if not scored:
                    assert UNKNOWN in sys_marks[0]["text"], sys_marks[0]["text"]


def _xg(k, g0, g1):
    return 40.0 + (k - g0) / (g1 - g0) * 240.0


def test_p05_the_trail_and_the_keys():
    cases = [(n, _fix(n)) for n in NAMES] + [("made-up", foreign()), ("budget", budget_report())]
    els = _els(_render(_stream([("w", n, v) for n, v in cases], True)))
    for (n, v), sec in zip(cases, _sections(els)):
        g0, g1 = v["rounds"][0]["grid"][0], v["rounds"][0]["grid"][-1]
        spans = [(g0, g1)]
        for r, svg in zip(v["rounds"], _frames(els, sec)):
            spans.append((r["lo"], r["hi"]))
            trail = _marks(els, svg, "rect", "trail")
            assert len(trail) == len(spans) == r["round"] + 1, (n, r["round"], len(trail))
            for j, (t, (lo, hi)) in enumerate(zip(trail, spans)):
                a = t["a"]
                assert (a["data-j"], a["data-lo"], a["data-hi"], a["data-key"]) == (str(j), repr(lo), repr(hi), f"trail-{j}"), a
                assert abs(float(a["x"]) - _xg(lo, g0, g1)) <= TOL and abs(float(a["width"]) - (_xg(hi, g0, g1) - _xg(lo, g0, g1))) <= TOL, a
                assert abs(float(a["y"]) - 298.0) <= TOL and abs(float(a["height"]) - 14.0) <= TOL, a
                assert ("now" in t["cls"]) == (j == r["round"]), (n, j)
            keys = [e["a"]["data-key"] for e in els if _in(e, svg) and "data-key" in e["a"]]
            assert len(set(keys)) == len(keys), (n, r["round"], "a key is repeated inside one frame")
            want = [f"trail-{j}" for j in range(len(spans))] + [f"tick-{i}" for i in range(len(r["grid"]))]
            if r["evaluated"]:
                m, nlev = len(r["grid"]), len(r["Gs"][0])
                want += ["zero", "next"] + [f"{p}-{i}" for p in ("c", "cerr", "d", "derr") for i in range(m)]
                want += [f"g-{lev}-{i}" for lev in range(nlev) for i in range(m)]
            if _marks(els, svg, "line", "truth"):
                want.append("truth")
            assert sorted(keys) == sorted(want), (n, r["round"], sorted(set(keys) ^ set(want))[:6])
            grid = [repr(k) for k in r["grid"]]
            for e in _marks(els, svg, "line", "tick"):
                assert e["a"]["data-key"] == f'tick-{grid.index(e["a"]["data-k"])}', e["a"]
            for tag, cls, pre in (("circle", "c", "c-"), ("line", "c-err", "cerr-"), ("circle", "d", "d-"), ("line", "d-err", "derr-")):
                for e in _marks(els, svg, tag, cls):
                    assert e["a"]["data-key"] == pre + e["a"]["data-i"], e["a"]
            for e in _marks(els, svg, "circle", "g"):
                assert e["a"]["data-key"] == f'g-{e["a"]["data-level"]}-{e["a"]["data-i"]}', e["a"]


def test_p06_every_element_names_its_source():
    for truth in (False, True):
        els = _els(_render(_stream(_mixed_specs(), truth)))
        stage = _by_id(els, "stage")
        roots = _frags(els)
        assert roots and all(_in(r, stage) for r in roots)
        marked = {id(r) for r in roots}
        marked |= {id(e) for e in els if any(id(a) in marked for a in e["anc"])}
        for e in els:
            if id(e) not in marked:
                assert "data-source" not in e["a"], (e["tag"], "a source outside the fragments")
                continue
            src = e["a"].get("data-source")
            assert src in ("navigator", "system"), (e["tag"], sorted(e["cls"]), "no data-source")
            if src == "navigator":
                assert not any(a["a"].get("data-source") == "system" for a in e["anc"]), (e["tag"], "navigator inside system")
            if e["cls"] & set(SYS_MARKS) or e["a"].get("data-slot") in SYS_SLOTS:
                assert src == "system", (sorted(e["cls"]), e["a"].get("data-slot"))
            if e["cls"] & set(NAV_MARKS) or e["a"].get("data-slot") in NAV_SLOTS:
                assert src == "navigator", (sorted(e["cls"]), e["a"].get("data-slot"))
            if "slot" in e["cls"]:
                assert e["a"]["data-slot"] in NAV_SLOTS + SYS_SLOTS, e["a"]
        for r in _frags(els, "run") + _frags(els, "outcome"):
            zones = _sel(els, None, "zone", r)
            assert sorted(z["a"]["data-source"] for z in zones) == ["navigator", "system"], "two zones, one per source"
            for z in zones:
                name = _one(els, None, "zone-name", z)
                assert name["text"].strip() == z["a"]["data-source"].upper(), name["text"]
            for s in _sel(els, None, "slot", r):
                assert any(_in(s, z) and z["a"]["data-source"] == s["a"]["data-source"] for z in zones), ("a slot outside its zone", s["a"])
        for svg in _sel(els, "svg", "frame"):
            layers = _sel(els, "g", "layer", svg)
            assert sorted(g["a"]["data-source"] for g in layers) == ["navigator", "system"], "two layers, one per source"
            for e in els:
                if _in(e, svg) and not any(e is g for g in layers):
                    mine = [g for g in layers if _in(e, g)]
                    assert len(mine) == 1 and mine[0]["a"]["data-source"] == e["a"]["data-source"], (e["tag"], sorted(e["cls"]))
        assert len(_sel(els, "svg")) == len(_sel(els, "svg", "frame")), "no svg but the frames"


def test_p07_selectors_come_from_the_labels():
    specs = [("bench-A", "first", foreign()), ('Q & <b>"x"', "s/1", _bare(_fix())), ("bench-A", "second", floor_report()),
             ("zeta", "first", "{junk")]
    page = _render(_stream(specs))
    for bad in ("W1", "W2", "W3"):
        assert bad not in page, (bad, "a world that no input named")
    els = _els(page)
    worlds = ["bench-A", 'Q & <b>"x"', "zeta"]
    pick = _by_id(els, "pick-world")
    assert pick["tag"] == "select" and pick["a"].get("aria-label") == "world"
    opts = _sel(els, "option", None, pick)
    assert [o["a"]["value"] for o in opts] == worlds and [o["text"] for o in opts] == worlds, "first appearance, escaped, nothing else"
    runs = _sel(els, "select", "pick-run")
    assert [s["a"]["data-world"] for s in runs] == worlds, "one run selector per world"
    want = {"bench-A": [("0", "first"), ("2", "second")], 'Q & <b>"x"': [("1", "s/1")], "zeta": [("3", "first")]}
    for s in runs:
        assert "hidden" in s["a"] and s["a"].get("aria-label") == "run", s["a"]
        assert [(o["a"]["value"], o["text"]) for o in _sel(els, "option", None, s)] == want[s["a"]["data-world"]]
    assert len(_sel(els, "option")) == len(worlds) + len(specs) and len(_sel(els, "select")) == 1 + len(worlds)
    assert [(s["a"]["data-run"], s["a"]["data-world"], s["a"]["data-label"]) for s in _sections(els)] == [
        (str(i), w, l) for i, (w, l, _) in enumerate(specs)]
    fx = _els(_render(_stream(_fixture_specs())))
    assert [o["text"] for o in _sel(fx, "option", None, _by_id(fx, "pick-world"))] == ["W1", "W2", "W3"]


def _chrome(els):
    stage = _by_id(els, "stage")
    return [e for e in els if e is not stage and not _in(e, stage) and e["tag"] != "option"]


def test_p08_one_stage_one_round_on_show():
    specs = _mixed_specs()
    st = _stream(specs)
    els = _els(_render(st))
    player, stage = _by_id(els, "player"), _by_id(els, "stage")
    assert _in(stage, player) and player["a"].get("data-view") == "navigator"
    for k in ("data-step-ms", "data-play-ms"):
        assert re.fullmatch(r"[1-9][0-9]*", player["a"].get(k, "")), (k, player["a"])
    want = {"prev": ("button", "previous round"), "play": ("button", "play"), "next": ("button", "next round"),
            "scrub": ("input", "round"), "pos": ("output", None)}
    for ident, (tag, label) in want.items():
        e = _by_id(els, ident)
        assert e["tag"] == tag and _in(e, player) and not _in(e, stage), ident
        assert label is None or e["a"].get("aria-label") == label, (ident, e["a"])
    scrub = _by_id(els, "scrub")["a"]
    assert (scrub.get("type"), scrub.get("min"), scrub.get("step")) == ("range", "1", "1"), scrub
    secs = _sections(els)
    assert len(secs) == len(specs) and all(_in(s, stage) and "hidden" in s["a"] for s in secs), "every run is hidden until chosen"
    n_rounds = sum(1 for e in st if type(e).__name__ == "RoundEv")
    bodies = _sel(els, "div", "body")
    frames = _sel(els, "svg", "frame")
    assert len(bodies) == len(frames) == n_rounds and all("hidden" in b["a"] for b in bodies), "every round is hidden until chosen"
    for f in frames:
        assert sum(1 for b in bodies if _in(f, b)) == 1, "a frame lives in one round body"
    for r in _frags(els, "round"):
        btn = _one(els, "button", "rnd", r)
        assert btn["a"]["data-round"] == r["a"]["data-round"] == btn["text"].strip(), btn["a"]
        assert not any(_in(btn, b) for b in bodies), "the round button stays visible when its body is hidden"
        assert len([b for b in bodies if _in(b, r)]) == 1
    style = re.sub(r"\s+", "", _one(els, "style")["text"])
    assert "[hidden]{display:none!important}" in style
    one = [("w", "a", foreign()), ("w", "b", foreign())]
    six = one + [("w", c, _bare(_fix())) for c in "cdef"]
    assert len(_chrome(_els(_render(_stream(one))))) == len(_chrome(_els(_render(_stream(six))))), \
        "nothing outside the stage is repeated per run but one option"


def _hull(p):
    return f"{p[0]!r}, {p[1]!r}"


def test_p09_slots_say_what_is_known_and_what_is_not():
    specs = _fixture_specs() + [("far", "budget", budget_report()), ("far", "floor", scored_floor()), ("far", "junk", "{not <json>"),
                                ("far", "bare", _bare(_fix()))]
    for truth in (False, True):
        els = _els(_render(_stream(specs, truth)))
        secs = _sections(els)
        for (world, label, v), sec in zip(specs, secs):
            head = _frags(els, "run", sec)
            assert len(head) == 1
            hs = _slots(els, head[0])
            assert sorted(hs) == ["a", "belief", "truth_K_c", "w_max"], sorted(hs)
            _slot_is(hs["belief"], "not-reported", LATER)
            scored = truth and not isinstance(v, str) and "truth_K_c" in v
            for k in ("truth_K_c", "a", "w_max"):
                if scored:
                    _slot_is(hs[k], "value", repr(v[k]))
                else:
                    _slot_is(hs[k], "unknown", UNKNOWN)
            outs, bad = _frags(els, "outcome", sec), _frags(els, "unreadable", sec)
            if isinstance(v, str):
                assert not outs and len(bad) == 1 and not _frags(els, "round", sec)
                why = _one(els, "p", "why", bad[0])
                assert why["text"].strip() and len(_slots(els, bad[0])) == 0
                continue
            assert len(outs) == 1 and not bad
            out = outs[0]
            assert out["a"]["data-kind"] == v["kind"] and out["a"]["data-reason"] == (v["reason"] or ""), out["a"]
            os_ = _slots(els, out)
            assert sorted(os_) == sorted(("kind", "reason", "lo", "hi", "width", "agree", "A_hull", "B_hull", "cell", "contains"))
            _slot_is(os_["kind"], "value", v["kind"])
            if v["kind"] == "Located":
                lo, hi = v["bracket"]
                _slot_is(os_["reason"], "absent", DASH)
                _slot_is(os_["lo"], "value", repr(lo))
                _slot_is(os_["hi"], "value", repr(hi))
                _slot_is(os_["width"], "value", repr(hi - lo))
                _slot_is(os_["agree"], "value", "yes" if v["agree"] else "no")
                _slot_is(os_["A_hull"], "value", _hull(v["A_hull"]))
                _slot_is(os_["B_hull"], "value", _hull(v["B_hull"]))
            else:
                _slot_is(os_["reason"], "value", v["reason"])
                for k in ("lo", "hi", "width", "agree", "A_hull", "B_hull"):
                    _slot_is(os_[k], "absent", DASH)
            if scored:
                _slot_is(os_["cell"], "value", v["cell"])
                if v["contains"] is None:
                    _slot_is(os_["contains"], "absent", DASH)
                else:
                    _slot_is(os_["contains"], "value", "yes" if v["contains"] else "no")
            else:
                _slot_is(os_["cell"], "unknown", UNKNOWN)
                _slot_is(os_["contains"], "unknown", UNKNOWN)
            rounds = _frags(els, "round", sec)
            assert len(rounds) == len(v["rounds"])
            for r, frag in zip(v["rounds"], rounds):
                assert frag["a"]["data-round"] == str(r["round"]) and frag["a"]["data-evaluated"] == ("true" if r["evaluated"] else "false")
                rs = _slots(els, frag)
                assert sorted(rs) == ["verdict"], sorted(rs)
                _slot_is(rs["verdict"], "not-reported", LATER)
                assert len(_sel(els, "text", "not-evaluated", frag)) == (0 if r["evaluated"] else 1)
                assert len(_sel(els, "circle", None, frag)) == (len(r["grid"]) * (2 + len(r["Gs"][0])) if r["evaluated"] else 0)
    b_none = foreign()
    b_none["B_hull"], b_none["agree"] = None, False
    for r in b_none["rounds"]:
        r["B"] = []
    els = _els(_render(_stream([("w", "l", b_none)])))
    os_ = _slots(els, _frags(els, "outcome")[0])
    _slot_is(os_["B_hull"], "absent", DASH)
    _slot_is(os_["agree"], "value", "no")
    els = _els(_render(_stream([("w", "l", '{"why": "<b>&'), ("w", "m", json.dumps(dict(_bare(_fix()), kind="ABSENT")))])))
    assert not _sel(els, "b") and "ABSENT" in _one(els, "p", "why", _sections(els)[1])["text"], "why is escaped, and names the kind"


def test_p10_the_script_moves_marks_and_measures_nothing():
    els = _els(_render(_stream(_fixture_specs(), True)))
    js = _sel(els, "script")[1]["text"]
    assert js.strip()
    numbers = re.findall(r"(?<![\w$.])(?:\d+\.?\d*(?:[eE][+-]?\d+)?|\.\d+)", js)
    assert set(numbers) <= {"0", "1", "2", "3"}, ("a number in the script that is not 0, 1, 2 or 3", sorted(set(numbers))[:8])
    assert not re.search(r"0[xXbBoO][0-9a-fA-F]", js), "no other spelling of a number"
    for bad in ("Math.", "getBBox", "getBoundingClientRect", "getCTM", "getScreenCTM", "createElement", "innerHTML", "outerHTML",
                "insertAdjacentHTML", "document.write", "eval(", "Function(", "fetch(", "XMLHttpRequest", "WebSocket", "EventSource",
                "import(", "localStorage", "sessionStorage", "viewBox", "offsetWidth", "clientWidth", "Date", "random",
                "data-k'", 'data-k"', "data-v", "data-lo", "data-hi", "data-x0", "data-x1", "JSON.parse", "dataset"):
        assert bad not in js, (bad, "the script shows, hides and interpolates; it creates and measures nothing")
    for need in ("data-key", "prefers-reduced-motion", "data-step-ms", "data-play-ms", "requestAnimationFrame", "cloneNode", "addEventListener", "hidden"):
        assert need in js, need
    style = _one(els, "style")["text"]
    for need in ("prefers-reduced-motion", "prefers-color-scheme: dark", ':root:not([data-theme="light"])', ':root[data-theme="dark"]'):
        assert need in style, need


def test_p11_the_cli():
    import needleview.player.__main__ as M
    with tempfile.TemporaryDirectory() as d:
        d = Path(d)
        a, b, eq = d / "a.json", d / "b.json", d / "k=v.json"
        a.write_text(json.dumps(_fix()))
        b.write_text(json.dumps(foreign()))
        eq.write_text(json.dumps(floor_report()))
        (d / "bin.json").write_bytes(b"\xff\xfe\x00")
        out = d / "o.html"
        triples = [("alpha", "s1", a), ("beta", "s1/x", b), ("alpha", "s2", eq), ("beta", "gone", d / "missing.json"),
                   ("beta", "dir", d), ("beta", "bin", d / "bin.json")]
        items = [f"{w}/{l}={p}" for w, l, p in triples]
        for truth in (False, True):
            flag = ["--truth"] if truth else []
            r = _cli(["--out", out] + flag + items)
            assert r.returncode == 0, r.stderr[-300:]
            st = ()
            for i, (w, l, p) in enumerate(triples):
                got = M.load(i, w, l, str(p), truth)
                assert isinstance(got, tuple)
                st += got
            assert [type(e).__name__ for e in st if e.run >= 3] == ["RunStart", "Refused"] * 3, "an unreadable path is drawn, not an error"
            first = out.read_bytes()
            assert first == _render(st).encode("utf-8"), "the CLI writes exactly render(the loaded stream)"
            assert _cli(["--out", out] + flag + items).returncode == 0 and out.read_bytes() == first
            assert M.main(["--out", str(out)] + flag + items) == 0 and out.read_bytes() == first
        els = _els(out.read_text(encoding="utf-8"))
        assert [(s["a"]["data-world"], s["a"]["data-label"]) for s in _sections(els)] == [(w, l) for w, l, _ in triples]
        out.unlink()
        for bad in ([], ["--out", out], [f"alpha/s1={a}"], ["--out", out, str(a)], ["--out", out, f"alpha={a}"],
                    ["--out", out, f"/s1={a}"], ["--out", out, f"alpha/={a}"], ["--out", out, "alpha/s1="],
                    ["--out", out, f"alpha/s1={a}", f"alpha/s1={b}"], ["--out", d / "no" / "such" / "o.html", f"alpha/s1={a}"]):
            r = _cli(bad)
            assert r.returncode == 2 and r.stderr.strip(), (bad, r.returncode)
            assert not out.exists(), (bad, "nothing is written on a usage error")


if __name__ == "__main__":
    _main([(n, f) for n, f in sorted(globals().items()) if n.startswith("test_") and callable(f)])
