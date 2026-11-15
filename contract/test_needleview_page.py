"""Plan 1529 — the needle-view page (contract/SCHEMA-1529.md, "The page" and "The CLI").
Every drawn number and every drawn position is checked against the report it came from, on three real runs and on a
report from a system nobody has seen. FROZEN: the Generator makes this green; it does not edit it.

RED until needleview/report.py, needleview/draw.py and needleview/__main__.py exist.
Run:  python contract/test_needleview_page.py   (or pytest)
"""
import copy
import json
import math
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
MOMENTS = ("C", "C_err", "Gs", "Gs_err", "D", "A", "B")
FORBIDDEN = ("<script", "http:", "https:", "<link", "<img", "<iframe", "@import", "url(", "<path")
DASH = "—"
TOL = 0.011
PLOT = {"c": (10.0, 90.0), "d": (115.0, 70.0), "g": (200.0, 70.0)}  # top, height


# ---------- the reports ----------
def _path(name):
    return FIXDIR / f"{name}.verdict.json"


def _fix(name="W1-s22"):
    return json.loads(_path(name).read_text())


def _bare(v):
    return {k: v[k] for k in REPORT_KEYS}


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


def foreign():
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


def one_sided():
    """D never changes sign and B is empty: the D plot's scale must still reach 0, so the zero line is inside the plot."""
    v = foreign()
    for r in v["rounds"]:
        r["Gs"] = [[0.5, 0.6 + i / 10.0, 0.25] for i in range(len(r["grid"]))]
        r["D"] = [g[1] - g[0] for g in r["Gs"]]
        r["B"] = []
    v["B_hull"], v["agree"] = None, False
    return v


def flat_report():
    """every C equal with zero error, every D and its error zero, every Gs equal: all three scales are Flat."""
    v = foreign()
    for r in v["rounds"]:
        m = len(r["grid"])
        r["C"], r["C_err"], r["D"] = [3.0] * m, [0.0] * m, [0.0] * m
        r["Gs"], r["Gs_err"] = [[0.5, 0.5, 0.5] for _ in range(m)], [[0.0, 0.0, 0.0] for _ in range(m)]
    return v


# ---------- the package under test ----------
def _R():
    from needleview import report  # imported here so a missing module FAILS each test, not the file
    return report


def _render(items):
    from needleview import draw
    page = draw.render(items)
    assert isinstance(page, str) and page
    return page


def _run(obj, label, truth=False):
    got = _R().parse(label, json.dumps(obj), truth)
    assert isinstance(got, _R().Run), got
    return got


def _fixture_runs(truth=False):
    return [_run(_fix(n), n, truth) for n in NAMES]


# ---------- reading the page back ----------
class _Page(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.els, self.stack = [], []

    def _el(self, tag, attrs):
        a = dict(attrs)
        el = {"tag": tag, "a": a, "cls": set((a.get("class") or "").split()), "text": "", "anc": list(self.stack)}
        self.els.append(el)
        return el

    def handle_starttag(self, tag, attrs):
        self.stack.append(self._el(tag, attrs))

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


def _els(page):
    p = _Page()
    p.feed(page)
    p.close()
    return p.els


def _sel(els, tag, cls=None, within=None):
    return [e for e in els if e["tag"] == tag and (cls is None or cls in e["cls"])
            and (within is None or any(a is within for a in e["anc"]))]


def _sections(els):
    return _sel(els, "section", "run")


def _f(el, key):
    return float(el["a"][key])


def _near(el, key, want):
    assert abs(_f(el, key) - want) <= TOL, (el["tag"], sorted(el["cls"]), key, el["a"].get(key), want)


def _x(k, x0, x1):
    return 40.0 + (k - x0) / (x1 - x0) * 240.0


def _y(v, lo, hi, plot):
    top, h = PLOT[plot]
    return top + h / 2.0 if hi == lo else top + h - (v - lo) / (hi - lo) * h


def _sig(r, i):
    return math.sqrt(r["Gs_err"][i][1] ** 2 + r["Gs_err"][i][0] ** 2)


def _domains(r):
    m = len(r["grid"])
    c = (min(r["C"][i] - r["C_err"][i] for i in range(m)), max(r["C"][i] + r["C_err"][i] for i in range(m)))
    d = (min([0.0] + [r["D"][i] - _sig(r, i) for i in range(m)]), max([0.0] + [r["D"][i] + _sig(r, i) for i in range(m)]))
    flat = [x for row in r["Gs"] for x in row]
    return c, d, (min(flat), max(flat))


def _by_i(marks):
    out = {int(e["a"]["data-i"]): e for e in marks}
    assert len(out) == len(marks), "a data-i is repeated"
    return out


CASES = [(n, lambda n=n: _fix(n)) for n in NAMES] + [("foreign", foreign), ("one-sided", one_sided)]


def _drawn():
    """[(name, report dict, [svg.round ...], all elements)] for the three fixtures and the two made-up reports, on ONE page."""
    reports = [(n, f()) for n, f in CASES]
    els = _els(_render([_run(v, n) for n, v in reports]))
    secs = _sections(els)
    assert len(secs) == len(reports)
    out = []
    for (n, v), sec in zip(reports, secs):
        svgs = _sel(els, "svg", "round", sec)
        assert len(svgs) == len(v["rounds"]), (n, len(svgs))
        out.append((n, v, svgs, els))
    return out


# ---------- the tests ----------
def test_p01_self_contained():
    page = _render(_fixture_runs())
    assert page.startswith("<!doctype html>"), page[:40]
    low = page.lower()
    for bad in FORBIDDEN:
        assert bad not in low, bad
    titles = _sel(_els(page), "title")
    assert titles and titles[0]["text"].strip() == "Needle view", [t["text"] for t in titles]


def test_p02_counts():
    for n, v, svgs, els in _drawn():
        for r, svg in zip(v["rounds"], svgs):
            m, nlev = len(r["grid"]), len(r["Gs"][0])
            want = {("circle", "c"): m, ("line", "c-err"): m, ("circle", "d"): m, ("line", "d-err"): m, ("circle", "g"): m * nlev,
                    ("line", "tick"): m, ("line", "zero"): 1, ("rect", "next"): 1, ("text", "not-evaluated"): 0}
            got = {k: len(_sel(els, k[0], k[1], svg)) for k in want}
            assert got == want, (n, r["round"], got)
            assert len(_sel(els, "circle", None, svg)) == m * (2 + nlev), (n, r["round"])


def test_p03_every_number_round_trips():
    for n, v, svgs, els in _drawn():
        for r, svg in zip(v["rounds"], svgs):
            a = svg["a"]
            assert a["data-round"] == str(r["round"]) and a["data-evaluated"] == "true", (n, a)
            assert (a["data-x0"], a["data-x1"]) == (repr(r["grid"][0]), repr(r["grid"][-1])), (n, a)
            assert (a["data-lo"], a["data-hi"]) == (repr(r["lo"]), repr(r["hi"])), (n, a)
            for i, e in _by_i(_sel(els, "circle", "c", svg)).items():
                assert (e["a"]["data-k"], e["a"]["data-v"], e["a"]["data-err"]) == (repr(r["grid"][i]), repr(r["C"][i]),
                                                                                  repr(r["C_err"][i])), (n, i)
            for i, e in _by_i(_sel(els, "circle", "d", svg)).items():
                assert (e["a"]["data-k"], e["a"]["data-v"], e["a"]["data-sig"]) == (repr(r["grid"][i]), repr(r["D"][i]),
                                                                                  repr(_sig(r, i))), (n, i)
            seen = set()
            for e in _sel(els, "circle", "g", svg):
                i, lev = int(e["a"]["data-i"]), int(e["a"]["data-level"])
                seen.add((i, lev))
                assert (e["a"]["data-k"], e["a"]["data-v"], e["a"]["data-err"]) == (repr(r["grid"][i]), repr(r["Gs"][i][lev]),
                                                                                  repr(r["Gs_err"][i][lev])), (n, i, lev)
            assert seen == {(i, lev) for i in range(len(r["grid"])) for lev in range(len(r["Gs"][0]))}, n
            assert sorted(e["a"]["data-k"] for e in _sel(els, "line", "tick", svg)) == sorted(repr(k) for k in r["grid"]), n
            nxt = _sel(els, "rect", "next", svg)[0]["a"]
            assert (nxt["data-lo"], nxt["data-hi"]) == (repr(r["lo"]), repr(r["hi"])), (n, nxt)


def test_p04_the_two_sets_are_marked():
    for n, v, svgs, els in _drawn():
        for r, svg in zip(v["rounds"], svgs):
            in_a = sorted(int(e["a"]["data-i"]) for e in _sel(els, "circle", "c", svg) if "in-A" in e["cls"])
            in_b = sorted(int(e["a"]["data-i"]) for e in _sel(els, "circle", "d", svg) if "in-B" in e["cls"])
            assert in_a == r["A"] and in_b == r["B"], (n, r["round"], in_a, in_b)
            stray = [e for e in els if ("in-A" in e["cls"] and "c" not in e["cls"]) or ("in-B" in e["cls"] and "d" not in e["cls"])]
            assert not stray, (n, stray[:1])


def test_p05_x_positions():
    for n, v, svgs, els in _drawn():
        for r, svg in zip(v["rounds"], svgs):
            x0, x1 = r["grid"][0], r["grid"][-1]
            for cls in ("c", "d", "g"):
                for e in _sel(els, "circle", cls, svg):
                    _near(e, "cx", _x(r["grid"][int(e["a"]["data-i"])], x0, x1))
            for cls in ("c-err", "d-err"):
                for i, e in _by_i(_sel(els, "line", cls, svg)).items():
                    _near(e, "x1", _x(r["grid"][i], x0, x1))
                    _near(e, "x2", _x(r["grid"][i], x0, x1))
            for e in _sel(els, "line", "tick", svg):
                _near(e, "x1", _x(float(e["a"]["data-k"]), x0, x1))
                _near(e, "x2", _x(float(e["a"]["data-k"]), x0, x1))
            nxt = _sel(els, "rect", "next", svg)[0]
            _near(nxt, "x", _x(r["lo"], x0, x1))
            _near(nxt, "width", _x(r["hi"], x0, x1) - _x(r["lo"], x0, x1))
            zero = _sel(els, "line", "zero", svg)[0]
            _near(zero, "x1", 40.0)
            _near(zero, "x2", 280.0)


def test_p06_y_positions():
    for n, v, svgs, els in _drawn():
        for r, svg in zip(v["rounds"], svgs):
            dc, dd, dg = _domains(r)
            cs = _by_i(_sel(els, "circle", "c", svg))
            for i, e in cs.items():
                _near(e, "cy", _y(r["C"][i], *dc, "c"))
            for i, e in _by_i(_sel(els, "line", "c-err", svg)).items():
                _near(e, "y1", _y(r["C"][i] + r["C_err"][i], *dc, "c"))
                _near(e, "y2", _y(r["C"][i] - r["C_err"][i], *dc, "c"))
            for i, e in _by_i(_sel(els, "circle", "d", svg)).items():
                _near(e, "cy", _y(r["D"][i], *dd, "d"))
            for i, e in _by_i(_sel(els, "line", "d-err", svg)).items():
                _near(e, "y1", _y(r["D"][i] + _sig(r, i), *dd, "d"))
                _near(e, "y2", _y(r["D"][i] - _sig(r, i), *dd, "d"))
            zero = _sel(els, "line", "zero", svg)[0]
            _near(zero, "y1", _y(0.0, *dd, "d"))
            _near(zero, "y2", _y(0.0, *dd, "d"))
            for e in _sel(els, "circle", "g", svg):
                _near(e, "cy", _y(r["Gs"][int(e["a"]["data-i"])][int(e["a"]["data-level"])], *dg, "g"))
            top = max(range(len(r["C"])), key=lambda i: r["C"][i])  # the largest C is drawn highest
            assert all(_f(cs[top], "cy") <= _f(e, "cy") for e in cs.values()), (n, r["round"])


def test_p07_refusals_and_unreadables_are_drawn_never_skipped():
    R = _R()
    label, why = "a<zq>&\"c'=d", "why <zw>text</zw> & more"
    items = [_run(_fix(), "first"), R.Unreadable(label, why), _run(budget_report(), "bud"), _run(floor_report(), "flo"),
             _run(_fix("W2-s24"), "last")]
    page = _render(items)
    assert "<zq>" not in page and "<zw>" not in page,"a label or a why reached the page unescaped"
    els = _els(page)
    secs = _sections(els)
    assert [(s["a"]["data-run"], s["a"]["data-label"], s["a"]["data-kind"], s["a"]["data-reason"]) for s in secs] == [
        ("0", "first", "Located", ""), ("1", label, "Unreadable", ""), ("2", "bud", "REFUSE", "budget"),
        ("3", "flo", "REFUSE", "floor"), ("4", "last", "Located", "")]
    unread, bud, flo = secs[1], secs[2], secs[3]
    assert [p["text"].strip() for p in _sel(els, "p", "why", unread)] == [why]
    assert not _sel(els, "svg", "round", unread) and not _sel(els, "svg", "round", flo)
    assert [p["a"]["data-reason"] for p in _sel(els, "p", "refuse", flo)] == ["floor"]
    assert [p["a"]["data-reason"] for p in _sel(els, "p", "refuse", bud)] == ["budget"]
    assert not _sel(els, "p", "refuse", secs[0]) and not _sel(els, "p", "why", secs[0])
    svgs = _sel(els, "svg", "round", bud)
    assert [s["a"]["data-evaluated"] for s in svgs] == ["true", "true", "false", "true", "true"]
    dead, r = svgs[2], budget_report()["rounds"][2]
    assert len(_sel(els, "line", "tick", dead)) == 9 and len(_sel(els, "text", "not-evaluated", dead)) == 1
    assert not _sel(els, "circle", None, dead) and not _sel(els, "rect", "next", dead) and not _sel(els, "line", "zero", dead)
    assert (dead["a"]["data-x0"], dead["a"]["data-x1"], dead["a"]["data-lo"], dead["a"]["data-hi"]) == (
        repr(r["grid"][0]), repr(r["grid"][-1]), repr(r["lo"]), repr(r["hi"]))
    for e in _sel(els, "line", "tick", dead):
        _near(e, "x1", _x(float(e["a"]["data-k"]), r["grid"][0], r["grid"][-1]))
    assert len(_sel(els, "text", "not-evaluated")) == 1


def test_p08_flat_scales_draw_at_mid_height():
    v = flat_report()
    els = _els(_render([_run(v, "flat")]))
    svgs = _sel(els, "svg", "round")
    assert len(svgs) == 2
    for svg in svgs:
        for cls, mid in (("c", 55.0), ("d", 150.0), ("g", 235.0)):
            marks = _sel(els, "circle", cls, svg)
            assert marks
            for e in marks:
                _near(e, "cy", mid)
        for cls, mid in (("c-err", 55.0), ("d-err", 150.0), ("zero", 150.0)):
            for e in _sel(els, "line", cls, svg):
                _near(e, "y1", mid)
                _near(e, "y2", mid)
        for e in _sel(els, "circle", "c", svg):
            _near(e, "cx", _x(float(e["a"]["data-k"]), float(svg["a"]["data-x0"]), float(svg["a"]["data-x1"])))
    assert float(svgs[0]["a"]["data-x0"]) == -5.0 and float(svgs[0]["a"]["data-x1"]) == 12.0


def _row(els, i):
    rows = [tr for tr in _sel(els, "tr", None, _sel(els, "table", "runs")[0]) if tr["a"].get("data-run") == str(i)]
    assert len(rows) == 1, (i, len(rows))
    cells = _sel(els, "td", None, rows[0])
    return [c["a"]["data-col"] for c in cells], {c["a"]["data-col"]: c["text"].strip() for c in cells}


def test_p09_overview_table_and_width_paths():
    R = _R()
    vs = [_fix(n) for n in NAMES]
    items = [_run(v, n) for v, n in zip(vs, NAMES)] + [_run(budget_report(), "bud"), _run(floor_report(), "flo"),
                                                       R.Unreadable("bad", "why")]
    els = _els(_render(items))
    tables, widths = _sel(els, "table", "runs"), _sel(els, "svg", "widths")
    assert len(tables) == 1 and len(widths) == 1
    first_section = els.index(_sections(els)[0])
    assert els.index(widths[0]) < els.index(tables[0]) < first_section, "the overview comes first"
    cols = ["label", "kind", "reason", "lo", "hi", "width", "agree"]
    assert [th["a"]["data-col"] for th in _sel(els, "th", None, tables[0])] == cols
    for i, (v, n) in enumerate(zip(vs, NAMES)):
        order, cell = _row(els, i)
        last = v["rounds"][-1]
        assert order == cols and cell == {"label": n, "kind": "Located", "reason": DASH, "lo": repr(last["lo"]),
                                           "hi": repr(last["hi"]), "width": repr(last["hi"] - last["lo"]),
                                           "agree": "yes" if v["agree"] else "no"}, (n, cell)
    for i, n, kind, reason in ((3, "bud", "REFUSE", "budget"), (4, "flo", "REFUSE", "floor"), (5, "bad", "Unreadable", DASH)):
        order, cell = _row(els, i)
        assert order == cols and cell == {"label": n, "kind": kind, "reason": reason, "lo": DASH, "hi": DASH, "width": DASH,
                                           "agree": DASH}, (n, cell)
    no = dict(_fix(), agree=False)
    assert _row(_els(_render([_run(no, "n")])), 0)[1]["agree"] == "no"
    paths = _sel(els, "polyline", "width-path", widths[0])
    assert [p["a"]["data-run"] for p in paths] == ["0", "1", "2", "3"], "one path per item that has a round"
    for p, v in zip(paths, vs + [budget_report()]):
        rs = v["rounds"]
        want = [rs[0]["grid"][-1] - rs[0]["grid"][0]] + [r["hi"] - r["lo"] for r in rs]
        assert p["a"]["data-widths"] == ",".join(repr(w) for w in want), p["a"]


def test_p10_deterministic_and_the_cli_writes_exactly_render():
    import needleview.__main__ as M
    items = _fixture_runs()
    assert _render(items) == _render(items)
    with tempfile.TemporaryDirectory() as d:
        d = Path(d)
        eq = d / "k=v.json"  # a path holding "=" must be given with a label
        eq.write_text(_path("W3-s26").read_text())
        out = d / "page.html"
        p1, p2 = str(_path("W1-s22")), str(_path("W2-s24"))
        cmd = [sys.executable, "-m", "needleview", "--out", str(out)]
        r = subprocess.run(cmd + [f"A={p1}", p2, f"C={eq}"], cwd=ROOT, capture_output=True, text=True)
        assert r.returncode == 0, (r.returncode, r.stderr[-300:])
        want = _render([M.load("A", p1, False), M.load(p2, p2, False), M.load("C", str(eq), False)])
        assert out.read_bytes() == want.encode("utf-8")
        assert [s["a"]["data-label"] for s in _sections(_els(want))] == ["A", p2, "C"]
        missing = str(d / "nope.json")
        r = subprocess.run(cmd + [missing], cwd=ROOT, capture_output=True, text=True)
        assert r.returncode == 0 and out.read_bytes() == _render([M.load(missing, missing, False)]).encode("utf-8")
        out.unlink()
        for name, args in (("no item", ["--out", str(out)]), ("no --out", [p1]), ("empty label", ["--out", str(out), f"={p1}"]),
                           ("empty path", ["--out", str(out), "A="]),
                           ("out in a missing directory", ["--out", str(d / "no-such-dir" / "page.html"), p1])):
            r = subprocess.run([sys.executable, "-m", "needleview"] + args, cwd=ROOT, capture_output=True, text=True)
            assert r.returncode == 2 and r.stderr.strip(), (name, r.returncode, r.stderr[-200:])
            assert not out.exists(), name


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
