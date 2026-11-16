"""Plan 1531 - the needle player is blind by construction (contract/SCHEMA-1531.md, "The two sources" and "Blindness").
With the truth off, no scored value can reach the page, and every SYSTEM slot reads UNKNOWN: a declared value, never an
empty cell. With it on, the truth appears only inside system-sourced elements; the navigator's part does not move.
FROZEN: the Generator makes this green; it does not edit it.

RED until the six needleview/player modules exist.
Run:  python contract/test_needleplayer_blind.py   (or pytest)
"""
import ast
import hashlib
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

SYS_SLOTS = ("truth_K_c", "a", "w_max", "cell", "contains")
MODULES = ("__init__.py", "__main__.py", "assets.py", "frame.py", "page.py", "stream.py")
ALLOWED_IMPORTS = {"argparse", "json", "math", "sys", "html", "dataclasses", "typing", "needleview"}
BANNED_CALLS = {"__import__", "exec", "eval"}
BANNED_EQUAL = {"where"}
BANNED_PARTS = ("self_dual", "lattice", "system-instantiated", "plugins", "at-blind", "edge.json", "config.json", "perf.json",
                "L4", "Ashkin", "Potts", "Ising", "W1", "W2", "W3")
# the five modules of plan 1529, byte for byte: this stage edits none of them
BASE = {"__init__.py": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
        "__main__.py": "8a9fe69eaaff2cd912409a9fb92b4310c1b2cc547920e709f585335f6d40a797",
        "draw.py": "4cb92145cd28dad6879de3ac48fba0bde7c2e4d8f6be9e31a35dda38f9ace923",
        "report.py": "b9ee6aa540ea5c2cbab048580262a9bbd3515d37dcb8a8403d784de0e270b7aa",
        "scale.py": "0616a6a5bcce4156e02e8ac2f7546abdd531eced7e829f9dc7d09725e5af7b22"}


def _cli(out, items, truth):
    cmd = [sys.executable, "-m", "needleview.player", "--out", str(out)] + (["--truth"] if truth else []) + items
    r = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
    assert r.returncode == 0, (r.returncode, r.stderr[-300:])
    return out.read_bytes()


def _system(els):
    return [e for e in els if e["a"].get("data-source") == "system"]


def _navigator_part(els):
    """every element of the stage that is not system-sourced, as (tag, attributes, own text): what the needle's side shows."""
    stage = _by_id(els, "stage")
    return [(e["tag"], sorted(e["a"].items()), e["own"]) for e in els if _in(e, stage) and e["a"].get("data-source") != "system"]


def _specs():
    return _fixture_specs() + [("far", "budget", budget_report()), ("far", "floor", scored_floor()), ("far", "junk", "{not json")]


# ---------- the tests ----------
def test_b1_truth_off_every_system_slot_reads_unknown():
    specs = _specs()
    st = _stream(specs, False)
    els = _els(_render(st))
    for cls in ("truth", "truth-off"):
        assert not _sel(els, None, cls), cls
    n_rounds = sum(1 for e in st if type(e).__name__ == "RoundEv")
    n_runs, n_outcomes = len(specs), sum(1 for e in st if type(e).__name__ == "Outcome")
    marks = _sel(els, "text", "sys-unknown")
    assert len(marks) == n_rounds and all(UNKNOWN in m["text"] for m in marks), "one UNKNOWN mark per frame"
    slots = [e for e in _sel(els, None, "slot") if e["a"]["data-slot"] in SYS_SLOTS]
    assert len(slots) == 3 * n_runs + 2 * n_outcomes, len(slots)
    for s in slots:
        assert s["text"].strip() == UNKNOWN and s["a"]["data-state"] == "unknown" and "data-v" not in s["a"], (s["a"], s["text"])
        assert s["a"]["data-source"] == "system"
    for e in _system(els):
        assert e["text"].strip(), (e["tag"], sorted(e["cls"]), "a system element is never empty")
        assert not [k for k in e["a"] if k.startswith("data-") and k not in ("data-source", "data-slot", "data-state")], e["a"]
    block = _by_id(els, "stream")["text"]
    assert block.count('"UNKNOWN"') == n_runs + n_outcomes


def test_b2_truth_off_page_cannot_depend_on_a_scored_value():
    with tempfile.TemporaryDirectory() as d:
        d = Path(d)
        for n in NAMES:
            v = _fix(n)
            a, b, c = d / f"{n}-a.json", d / f"{n}-b.json", d / f"{n}-c.json"
            a.write_text(json.dumps(v))
            b.write_text(json.dumps(tampered(v, 0.123456)))
            c.write_text(json.dumps(_bare(v)))
            pages = [_cli(d / "o.html", [f"w/{n}={p}"], False) for p in (a, b, c)]
            assert pages[0] == pages[1] == pages[2], n
            assert str(v["truth_K_c"]).encode() not in pages[0] and b"0.123456" not in pages[1], n
            for word in (b"HIT", b"MISS", b"REFUSED"):
                assert word not in pages[0], (n, word)
            seen = [_cli(d / "o.html", [f"w/{n}={p}"], True) for p in (a, b)]
            assert seen[0] != seen[1], "with the truth ON the same change must show (this check can fail)"
            assert seen[0] != pages[0], n


def test_b3_truth_on_moves_only_the_system_part():
    low, high = tampered(_fix(), 0.123456), tampered(_fix(), 0.9)
    specs = _specs() + [("far", "low", low), ("far", "high", high), ("far", "bare", _bare(_fix()))]
    on, off = _els(_render(_stream(specs, True))), _els(_render(_stream(specs, False)))
    assert _navigator_part(on) == _navigator_part(off), "the truth reached an element that is not system-sourced"
    assert [e["tag"] for e in _system(on)] != [e["tag"] for e in _system(off)], "the system part must differ (this check can fail)"
    secs = _sections(on)
    for (world, label, v), sec in zip(specs, secs):
        frames = _sel(on, "svg", "frame", sec)
        slots = {e["a"]["data-slot"]: e for e in _sel(on, None, "slot", sec) if e["a"]["data-slot"] in SYS_SLOTS}
        scored = not isinstance(v, str) and "truth_K_c" in v
        if not scored:
            assert all(s["text"].strip() == UNKNOWN for s in slots.values()), (label, "an unknown system under --truth")
            assert len(_sel(on, "text", "sys-unknown", sec)) == len(frames)
            assert not _sel(on, "line", "truth", sec) and not _sel(on, "polygon", "truth-off", sec)
            continue
        assert slots["truth_K_c"]["text"].strip() == repr(v["truth_K_c"]) and slots["cell"]["text"].strip() == v["cell"]
        assert slots["a"]["text"].strip() == repr(v["a"]) and slots["w_max"]["text"].strip() == repr(v["w_max"])
        assert not _sel(on, "text", "sys-unknown", sec)
        sides = []
        for r, svg in zip(v["rounds"], frames):
            lines, offs = _sel(on, "line", "truth", svg), _sel(on, "polygon", "truth-off", svg)
            assert len(lines) + len(offs) == 1
            inside = r["grid"][0] <= v["truth_K_c"] <= r["grid"][-1]
            assert bool(lines) == inside, (label, r["round"])
            sides.append("in" if lines else offs[0]["a"]["data-side"])
            for e in lines + offs:
                assert e["a"]["data-source"] == "system"
        if label == "low":
            assert sides == ["lo"] * 5, sides
        if label == "high":
            assert sides == ["hi"] * 5, sides
    assert secs[-1]["a"]["data-label"] == "bare"


def test_b4_truth_on_a_bare_report_changes_nothing():
    with tempfile.TemporaryDirectory() as d:
        d = Path(d)
        for n in NAMES:
            p = d / f"{n}.json"
            p.write_text(json.dumps(_bare(_fix(n))))
            off, on = _cli(d / "o.html", [f"w/{n}={p}"], False), _cli(d / "o.html", [f"w/{n}={p}"], True)
            assert off == on, n
            assert b"UNKNOWN" in on


def _constants(tree):
    return [n.value for n in ast.walk(tree) if isinstance(n, ast.Constant) and isinstance(n.value, str)]


def test_b5_the_package_cannot_reach_or_name_the_system():
    base = ROOT / "needleview"
    assert sorted(p.name for p in base.glob("*.py")) == sorted(BASE), "the needle view keeps its five modules"
    for name, want in BASE.items():
        assert hashlib.sha256((base / name).read_bytes()).hexdigest() == want, (name, "a plan-1529 module was edited")
    pkg = base / "player"
    found = sorted(p.name for p in pkg.glob("*.py"))
    assert found == sorted(MODULES), found
    assert not [p for p in pkg.iterdir() if p.is_dir() and p.name != "__pycache__"], "no package below the player"
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
    _main([(n, f) for n, f in sorted(globals().items()) if n.startswith("test_") and callable(f)])
