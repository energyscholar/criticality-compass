"""Plan 1529 — the needle view is blind by construction (contract/SCHEMA-1529.md, "Overlay" and "Blindness").
With the truth switched off, the page cannot depend on any scored value in the file. With it on, the truth is drawn only
from a scored verdict, and a bare report gets nothing. The package cannot name or reach the System's model.
FROZEN: the Generator makes this green; it does not edit it.

RED until the five needleview modules exist.
Run:  python contract/test_needleview_blind.py   (or pytest)
"""
import ast
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
DASH = "—"
TOL = 0.011
OVERLAY_CLASSES = ("truth", "truth-off", "cell", "overlay")
MODULES = ("__init__.py", "__main__.py", "draw.py", "report.py", "scale.py")
ALLOWED_IMPORTS = {"argparse", "json", "math", "sys", "html", "dataclasses", "typing", "needleview"}
BANNED_CALLS = {"__import__", "exec", "eval"}
BANNED_EQUAL = {"where"}
BANNED_PARTS = ("self_dual", "lattice", "system-instantiated", "plugins", "at-blind", "edge.json", "config.json", "perf.json",
                "L4", "Ashkin", "Potts", "Ising")


def _path(name):
    return FIXDIR / f"{name}.verdict.json"


def _fix(name="W1-s22"):
    return json.loads(_path(name).read_text())


def tampered(v, k_c):
    """a copy in which ALL NINE scored values differ from the original, and still form a well-formed verdict tail."""
    t = dict(v)
    t.update(truth_K_c=k_c, a=v["a"] + 0.5, w_max=v["w_max"] + 0.5, contains=not v["contains"], width=v["width"] + 0.25,
             narrow_enough=not v["narrow_enough"], cell="MISS" if v["cell"] == "HIT" else "HIT", run_id="0" * 16, plan="9999")
    assert all(t[k] != v[k] for k in t if k not in REPORT_KEYS) and len(t) == 16
    return t


def _R():
    from needleview import report  # imported here so a missing module FAILS each test, not the file
    return report


def _render(items):
    from needleview import draw
    page = draw.render(items)
    assert isinstance(page, str) and page
    return page


def _run(obj, label, truth):
    got = _R().parse(label, json.dumps(obj), truth)
    assert isinstance(got, _R().Run), got
    return got


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


def _overlay_marks(els):
    return [e for e in els if e["cls"] & set(OVERLAY_CLASSES)]


def _cli(out, items, truth):
    cmd = [sys.executable, "-m", "needleview", "--out", str(out)] + (["--truth"] if truth else []) + items
    r = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
    assert r.returncode == 0, (r.returncode, r.stderr[-300:])
    return out.read_bytes()


def test_b1_truth_off_draws_no_truth():
    els = _els(_render([_run(_fix(n), n, False) for n in NAMES]))
    assert len(_sel(els, "section", "run")) == 3 and len(_sel(els, "svg", "round")) == 15
    assert not _overlay_marks(els)
    table = _sel(els, "table", "runs")[0]
    assert [th["a"]["data-col"] for th in _sel(els, "th", None, table)] == ["label", "kind", "reason", "lo", "hi", "width", "agree"]


def test_b2_truth_off_page_cannot_depend_on_a_scored_value():
    with tempfile.TemporaryDirectory() as d:
        d = Path(d)
        for n in NAMES:
            v = _fix(n)
            a, b, c = d / f"{n}-a.json", d / f"{n}-b.json", d / f"{n}-c.json"
            a.write_text(json.dumps(v))
            b.write_text(json.dumps(tampered(v, 0.123456)))
            c.write_text(json.dumps({k: v[k] for k in REPORT_KEYS}))
            pages = [_cli(d / "o.html", [f"{n}={p}"], False) for p in (a, b, c)]
            assert pages[0] == pages[1] == pages[2], n
            assert str(v["truth_K_c"]).encode() not in pages[0] and b"0.123456" not in pages[1], n
            seen = [_cli(d / "o.html", [f"{n}={p}"], True) for p in (a, b)]
            assert seen[0] != seen[1], "with the truth ON the same change must show (this check can fail)"
            assert seen[0] != pages[0], n


def _x(k, x0, x1):
    return 40.0 + (k - x0) / (x1 - x0) * 240.0


def _check_overlay(els, sec, v):
    k_c, sides = v["truth_K_c"], []
    svgs = _sel(els, "svg", "round", sec)
    assert len(svgs) == len(v["rounds"])
    for r, svg in zip(v["rounds"], svgs):
        x0, x1 = r["grid"][0], r["grid"][-1]
        lines, offs = _sel(els, "line", "truth", svg), _sel(els, "polygon", "truth-off", svg)
        if x0 <= k_c <= x1:
            assert len(lines) == 1 and not offs, (r["round"], len(lines), len(offs))
            assert lines[0]["a"]["data-k"] == repr(k_c)
            for key in ("x1", "x2"):
                assert abs(float(lines[0]["a"][key]) - _x(k_c, x0, x1)) <= TOL, lines[0]["a"]
            sides.append("in")
        else:
            assert len(offs) == 1 and not lines, (r["round"], len(lines), len(offs))
            want = "lo" if k_c < x0 else "hi"
            assert offs[0]["a"]["data-side"] == want, (r["round"], offs[0]["a"])
            sides.append(want)
    cells = _sel(els, "span", "cell", sec)
    assert [c["a"]["data-cell"] for c in cells] == [v["cell"]]
    return sides


def _row(els, i):
    rows = [tr for tr in _sel(els, "tr", None, _sel(els, "table", "runs")[0]) if tr["a"].get("data-run") == str(i)]
    assert len(rows) == 1
    return {c["a"]["data-col"]: c["text"].strip() for c in _sel(els, "td", None, rows[0])}


def test_b3_truth_on_draws_the_truth_where_it_is():
    R = _R()
    vs = [_fix(n) for n in NAMES]
    low, high = tampered(vs[0], 0.123456), tampered(vs[0], 0.9)  # below every grid, above every grid
    bare = {k: vs[0][k] for k in REPORT_KEYS}
    floor = {"kind": "REFUSE", "reason": "floor", "bracket": None, "A_hull": None, "B_hull": None, "agree": None, "rounds": [],
             "truth_K_c": 0.35, "a": 0.003, "w_max": 0.02, "contains": None, "width": None, "narrow_enough": None,
             "cell": "REFUSED", "run_id": "0" * 16, "plan": "1525"}
    reports = vs + [low, high]
    items = [_run(v, f"r{i}", True) for i, v in enumerate(reports)] + [_run(bare, "bare", True), _run(floor, "floor", True)]
    assert items[5].overlay is None and items[6].overlay == R.Overlay(0.35, 0.003, 0.02, None, "REFUSED")
    els = _els(_render(items))
    secs = _sel(els, "section", "run")
    assert len(secs) == 7
    sides = [_check_overlay(els, sec, v) for sec, v in zip(secs, reports)]
    assert sides[0][0] == "in" and sides[1][0] == "in" and sides[2][0] == "in", "round 1 holds the truth in all three runs"
    assert sides[3] == ["lo"] * 5 and sides[4] == ["hi"] * 5, (sides[3], sides[4])
    assert not [e for e in _overlay_marks(els) if any(a is secs[5] for a in e["anc"])], "a bare report gets no overlay mark"
    assert [c["a"]["data-cell"] for c in _sel(els, "span", "cell", secs[6])] == ["REFUSED"]
    assert not _sel(els, "line", "truth", secs[6]) and not _sel(els, "polygon", "truth-off", secs[6])
    ths = _sel(els, "th", None, _sel(els, "table", "runs")[0])
    assert [th["a"]["data-col"] for th in ths] == ["label", "kind", "reason", "lo", "hi", "width", "agree", "truth_K_c", "a",
                                                    "contains", "cell"]
    assert ["overlay" in th["cls"] for th in ths] == [False] * 7 + [True] * 4
    for i, v in enumerate(reports):
        row = _row(els, i)
        assert (row["truth_K_c"], row["a"], row["contains"], row["cell"]) == (
            repr(v["truth_K_c"]), repr(v["a"]), "yes" if v["contains"] else "no", v["cell"]), (i, row)
    row = _row(els, 5)
    assert (row["truth_K_c"], row["a"], row["contains"], row["cell"]) == (DASH, DASH, DASH, DASH), row
    row = _row(els, 6)
    assert (row["truth_K_c"], row["a"], row["contains"], row["cell"]) == (repr(0.35), repr(0.003), DASH, "REFUSED"), row


def test_b4_truth_on_a_bare_report_changes_nothing():
    with tempfile.TemporaryDirectory() as d:
        d = Path(d)
        for n in NAMES:
            p = d / f"{n}.json"
            p.write_text(json.dumps({k: _fix(n)[k] for k in REPORT_KEYS}))
            off, on = _cli(d / "o.html", [f"{n}={p}"], False), _cli(d / "o.html", [f"{n}={p}"], True)
            assert off == on, n
            assert not _overlay_marks(_els(on.decode("utf-8"))), n


def _constants(tree):
    return [n.value for n in ast.walk(tree) if isinstance(n, ast.Constant) and isinstance(n.value, str)]


def test_b5_the_package_cannot_reach_or_name_the_system():
    pkg = ROOT / "needleview"
    found = sorted(p.name for p in pkg.glob("*.py"))
    assert found == sorted(MODULES), found
    for name in found:
        tree = ast.parse((pkg / name).read_text())
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for a in node.names:
                    assert a.name.split(".")[0] in ALLOWED_IMPORTS, (name, a.name)
            elif isinstance(node, ast.ImportFrom):
                assert node.level == 0 and (node.module or "").split(".")[0] in ALLOWED_IMPORTS, (name, node.module)
            elif isinstance(node, ast.Name):
                assert node.id not in BANNED_CALLS, (name, node.id)
                assert node.id != "open" or name == "__main__.py", (name, "open")
            elif isinstance(node, ast.Attribute):
                assert node.attr not in BANNED_CALLS and node.attr != "open", (name, node.attr)
        for s in _constants(tree):
            assert s not in BANNED_EQUAL, (name, s)
            for part in BANNED_PARTS:
                assert part not in s, (name, part, s[:60])


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
