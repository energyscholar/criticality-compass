"""Plan 1533 — the reader of a needle report, schema 1 and schema 2 (contract/SCHEMA-1533.md). Pure: no process, no socket.
FROZEN: the Generator makes this green; it does not edit this file.

What it pins:
  1. a schema-1 report (the three fixtures of plan 1529, scored or bare) is read through `needleview.report` and lifted
     into the one in-memory shape; its start and its verdicts are NOT_REPORTED; folding it back gives its seven keys;
  2. a schema-2 stream built here, by hand, from the same fixtures is read; folding it gives the SAME seven keys, so a
     schema-1 viewer reads a schema-2 Located run with not one number changed;
  3. the stream is append-only: every whole-line prefix is readable, its steps are the full stream's first steps, and
     its outcome is PENDING; a line cut in the middle is unreadable;
  4. the reader holds the needle to its own tables: a constant verdict, a verdict that is not the table's, an outcome
     that is not the fold, a changed bracket number, a belief that is not slot -> declared | unknown, a sigma that is
     not an unsigned offset in g, a mode that is not the mode of its ops: each is Unreadable, never drawn;
  5. `read` never raises, whatever it is given;
  6. the reader is pure and the schema-1 reader is untouched.

RED until needlestream/read.py exists.
Run from the repo root:  python contract/test_report2_reader.py   (or pytest)
"""
import ast
import copy
import hashlib
import json
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

FIXTURES = ("W1-s22", "W2-s24", "W3-s26")
REPORT_KEYS = ("kind", "reason", "bracket", "A_hull", "B_hull", "agree", "rounds")
SLOTS = ("knobs_K", "ordered_side", "L", "tau", "k", "index_unit", "index_kind", "observable", "nlev", "system", "roles")
DECLARED = {"knobs_K": [0.2, 0.5], "ordered_side": "+K", "L": 81, "tau": 67.0, "k": 6, "index_unit": "sweep",
            "index_kind": "sample_counter", "observable": "moments", "nlev": 2}
Z = 2.0
NEEDLEVIEW_SHA = {
    "needleview/__init__.py": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
    "needleview/__main__.py": "8a9fe69eaaff2cd912409a9fb92b4310c1b2cc547920e709f585335f6d40a797",
    "needleview/draw.py": "4cb92145cd28dad6879de3ac48fba0bde7c2e4d8f6be9e31a35dda38f9ace923",
    "needleview/report.py": "b9ee6aa540ea5c2cbab048580262a9bbd3515d37dcb8a8403d784de0e270b7aa",
    "needleview/scale.py": "0616a6a5bcce4156e02e8ac2f7546abdd531eced7e829f9dc7d09725e5af7b22",
}
ALLOWED_IMPORTS = {"json", "dataclasses", "typing", "navigator", "needleview", "needlestream"}


def _ns():
    from needlestream import read
    return read


def _fixture(name):
    return json.loads((ROOT / "contract" / "fixtures-1529" / f"{name}.verdict.json").read_text())


def _class(d, e):
    return "UNRES" if abs(d) <= Z * math.sqrt(e[1] ** 2 + e[0] ** 2) else ("SIG+" if d > 0 else "SIG-")


def _kind(lo, hi):
    """the scan table for ordered side +K, written from what each resolved end says."""
    if lo == "SIG+":
        return "unresolved" if hi == "SIG-" else "lean-lo"
    if hi == "SIG-":
        return "lean-hi"
    return "narrow" if (lo, hi) == ("SIG-", "SIG+") else "unresolved"


def _verdict(scan):
    if not scan["evaluated"]:
        return {"kind": "not-evaluated", "reason": "n/e", "dial": None, "ticks": None}
    lo, hi = _class(scan["D"][0], scan["Gs_err"][0]), _class(scan["D"][-1], scan["Gs_err"][-1])
    return {"kind": _kind(lo, hi), "reason": f"{lo}|{hi}", "dial": None, "ticks": None}


def _fold(kinds):
    order = ("narrow", "lean-lo", "lean-hi", "unresolved", "not-evaluated")
    said = [k for k in order if k in kinds]
    if not said:
        return "REFUSE", "floor"
    if "not-evaluated" in said:
        return "REFUSE", "budget"
    one = {"narrow": ("Located", None), "lean-lo": ("PAST-LO", "lean-lo"), "lean-hi": ("PAST-HI", "lean-hi")}
    return one[said[0]] if len(said) == 1 and said[0] in one else ("UNDECIDED", "+".join(said))


def _records(rounds, v1=None, ended=True):
    """a schema-2 stream as a list of records, written by hand from schema-1 rounds."""
    bracket = [rounds[0]["grid"][0], rounds[0]["grid"][-1]] if rounds else [0.2, 0.5]
    start = {"rec": "start", "schema": "compass-report/2", "needle": "recover-adaptive-v1",
             "settings": {"bracket": bracket, "m": 9, "N": 5, "n_eq": 450, "S": 2000, "skip": 1, "z": Z,
                          "detectors": [{"name": "A", "role": "peak", "reads": "C"}, {"name": "B", "role": "crossing", "reads": "Gs"}]},
             "mode": {"ops": ["declare", "measure"], "feedback": "OFF"},
             "sigma": {"offset": 0, "unit": "g", "measured": "not-defined"},
             "dials": [],
             "belief": {**{s: "unknown" for s in SLOTS}, **{k: {"declared": v} for k, v in DECLARED.items()}},
             "declared_other": {}}
    steps = [{"rec": "step", "step": r["round"], "phase": "bracketing", "index": r["index"], "evaluated": r["evaluated"],
              "verdict": [_verdict(r)], "scan": r} for r in rounds]
    if not ended:
        return [start] + steps
    kind, reason = _fold([s["verdict"][0]["kind"] for s in steps])
    six = {k: (v1[k] if kind == "Located" else None) for k in ("bracket", "A_hull", "B_hull", "agree")}
    return [start] + steps + [{"rec": "outcome", "kind": kind, "reason": reason, **six, "steps": len(steps)}]


def _text(records):
    return "".join(json.dumps(r) + "\n" for r in records)


def _leaning(v1, sign):
    """the fixture's rounds with every block-ratio difference pushed to one sign: a range that does not hold the crossing."""
    rounds = copy.deepcopy(v1["rounds"])
    for r in rounds:
        r["Gs"] = [[g[0], g[0] + sign * (0.1 + abs(g[1] - g[0]))] for g in r["Gs"]]
        r["D"] = [g[1] - g[0] for g in r["Gs"]]
    return rounds


def _must_refuse(records, what):
    NS = _ns()
    got = NS.read(_text(records))
    assert isinstance(got, NS.Unreadable), f"{what}: read as a report"
    assert isinstance(got.why, str) and got.why and "Traceback" not in got.why, (what, got.why)
    return got.why


def test_r01_a_schema1_report_is_lifted_into_the_one_shape():
    NS = _ns()
    for name in FIXTURES:
        doc = _fixture(name)
        for text in (json.dumps(doc), json.dumps({k: doc[k] for k in REPORT_KEYS}), json.dumps(doc, indent=1) + "\n"):
            s = NS.read(text)
            assert isinstance(s, NS.Stream), (name, s)
            assert s.schema == 1 and s.start is NS.NOT_REPORTED, (name, s.schema, s.start)
            assert len(s.steps) == len(doc["rounds"]) and all(x.verdict is NS.NOT_REPORTED for x in s.steps), name
            assert [(x.step, x.phase, x.index, x.evaluated) for x in s.steps] == \
                [(r["round"], "bracketing", r["index"], r["evaluated"]) for r in doc["rounds"]], name
            assert [x.scan for x in s.steps] == doc["rounds"], name
            o = s.outcome
            assert (o.kind, o.reason, o.bracket, o.A_hull, o.B_hull, o.agree) == tuple(doc[k] for k in REPORT_KEYS[:6]), name
            assert NS.fold_v1(s) == {k: doc[k] for k in REPORT_KEYS}, name
    assert repr(NS.NOT_REPORTED) == "NOT_REPORTED" and repr(NS.PENDING) == "PENDING"


def test_r02_what_the_schema1_reader_refuses_stays_refused():
    NS = _ns()
    from needleview import report as V1
    doc = _fixture("W1-s22")
    bad = {
        "kind": dict(doc, kind="Elsewhere"),
        "bracket": dict(doc, bracket=[0.1, 0.2]),
        "extra key": dict(doc, schema=1),
        "missing key": {k: v for k, v in doc.items() if k != "agree"},
        "round": dict(doc, rounds=doc["rounds"][:-1] + [dict(doc["rounds"][-1], round=9)]),
    }
    for what, d in bad.items():
        got, want = NS.read(json.dumps(d)), V1.parse("", json.dumps(d), False)
        assert isinstance(want, V1.Unreadable), what
        assert isinstance(got, NS.Unreadable) and got.why == want.why, (what, got, want.why)
    refusal = {"kind": "REFUSE", "reason": "floor", "bracket": None, "A_hull": None, "B_hull": None, "agree": None, "rounds": []}
    s = NS.read(json.dumps(refusal))
    assert isinstance(s, NS.Stream) and s.steps == () and s.outcome.kind == "REFUSE" and NS.fold_v1(s) == refusal


def test_r03_a_schema2_located_stream_folds_to_the_same_seven_keys():
    NS = _ns()
    for name in FIXTURES:
        doc = _fixture(name)
        recs = _records(doc["rounds"], doc)
        assert recs[-1]["kind"] == "Located", (name, recs[-1])
        s = NS.read(_text(recs))
        assert isinstance(s, NS.Stream) and s.schema == 2, (name, s)
        assert json.dumps(NS.fold_v1(s), sort_keys=True) == json.dumps({k: doc[k] for k in REPORT_KEYS}, sort_keys=True), name
        assert isinstance(s.start, NS.Start) and s.start.needle == "recover-adaptive-v1"
        assert s.start.belief == recs[0]["belief"] and s.start.declared_other == {}
        assert s.start.mode == {"ops": ["declare", "measure"], "feedback": "OFF"}
        assert s.start.sigma == {"offset": 0, "unit": "g", "measured": "not-defined"}
        assert s.start.settings == recs[0]["settings"]
        assert s.start.dials == ()
        for x, rec in zip(s.steps, recs[1:-1]):
            assert isinstance(x.verdict, tuple) and len(x.verdict) == 1, x.verdict
            v = x.verdict[0]
            assert (v.kind, v.reason, v.dial, v.ticks) == ("narrow", "SIG-|SIG+", None, None), (name, x.step, v)
            assert (x.step, x.phase, x.index, x.evaluated, x.scan) == (rec["step"], "bracketing", rec["index"], True, rec["scan"])
        from needleview import report as V1
        run = V1.parse(name, json.dumps({**NS.fold_v1(s), **{k: doc[k] for k in V1.VERDICT_KEYS}}), True)
        assert isinstance(run, V1.Run), "the schema-1 viewer must read the fold of a Located stream"


def test_r04_the_stream_is_append_only():
    NS = _ns()
    doc = _fixture("W2-s24")
    recs = _records(doc["rounds"], doc)
    full = NS.read(_text(recs))
    for k in range(1, len(recs)):
        part = NS.read(_text(recs[:k]))
        assert isinstance(part, NS.Stream), (k, part)
        assert part.outcome is NS.PENDING and NS.fold_v1(part) is NS.PENDING, k
        assert part.start == full.start and part.steps == full.steps[:k - 1], k
    whole = _text(recs)
    cut = NS.read(whole[:len(whole) - 7])
    assert isinstance(cut, NS.Unreadable), "a line cut in the middle was read"
    assert isinstance(NS.read(whole.rstrip("\n")), NS.Unreadable), "a last line with no line end is not complete"


def test_r05_the_other_outcomes_are_read():
    NS = _ns()
    doc = _fixture("W1-s22")
    for sign, kind, lean in ((-1, "PAST-HI", "lean-hi"), (1, "PAST-LO", "lean-lo")):
        s = NS.read(_text(_records(_leaning(doc, sign))))
        assert isinstance(s, NS.Stream), s
        o = s.outcome
        assert (o.kind, o.reason, o.bracket, o.A_hull, o.B_hull, o.agree) == (kind, lean, None, None, None, None), o
        assert all(x.verdict[0].kind == lean for x in s.steps)
        assert NS.fold_v1(s)["kind"] == kind and NS.fold_v1(s)["rounds"] == [x.scan for x in s.steps]
        from needleview import report as V1
        refused = V1.parse("", json.dumps(NS.fold_v1(s)), False)
        assert isinstance(refused, V1.Unreadable) and kind in refused.why, "a schema-1 viewer refuses the new kind by name"
    mixed = copy.deepcopy(doc["rounds"])
    mixed[2:] = _leaning({"rounds": mixed[2:]}, -1)
    s = NS.read(_text(_records(mixed)))
    assert isinstance(s, NS.Stream) and (s.outcome.kind, s.outcome.reason) == ("UNDECIDED", "narrow+lean-hi"), s
    short = copy.deepcopy(doc["rounds"][:3])
    short[2].update({k: None for k in ("C", "C_err", "Gs", "Gs_err", "D", "A", "B")}, evaluated=False,
                    lo=short[2]["grid"][0], hi=short[2]["grid"][-1])
    s = NS.read(_text(_records(short)))
    assert isinstance(s, NS.Stream) and (s.outcome.kind, s.outcome.reason) == ("REFUSE", "budget"), s
    assert s.steps[-1].verdict[0].kind == "not-evaluated" and s.steps[-1].verdict[0].reason == "n/e"
    s = NS.read(_text(_records([])))
    assert isinstance(s, NS.Stream) and s.steps == () and (s.outcome.kind, s.outcome.reason) == ("REFUSE", "floor"), s


def test_r06_a_constant_verdict_is_not_a_report():
    doc = _fixture("W1-s22")
    lean = _records(_leaning(doc, -1))
    for rec in lean[1:-1]:
        rec["verdict"][0].update(kind="narrow", reason="SIG-|SIG+")
    lean[-1].update(kind="Located", reason=None, bracket=doc["bracket"], A_hull=doc["A_hull"], B_hull=doc["B_hull"],
                    agree=doc["agree"])
    why = _must_refuse(lean, "always-narrow on a leaning range")
    assert "verdict" in why, why
    located = _records(doc["rounds"], doc)
    for rec in located[1:-1]:
        rec["verdict"][0].update(kind="lean-hi", reason="SIG-|SIG-")
    located[-1].update(kind="PAST-HI", reason="lean-hi", bracket=None, A_hull=None, B_hull=None, agree=None)
    assert "verdict" in _must_refuse(located, "always-lean-hi on a bracketed range")
    one = _records(doc["rounds"], doc)
    one[2]["verdict"][0]["reason"] = "SIG-|UNRES"
    _must_refuse(one, "a reason that is not the cell")
    two = _records(doc["rounds"], doc)
    two[1]["verdict"] = two[1]["verdict"] * 2
    _must_refuse(two, "two verdicts on a one-dial step")
    for field, value in (("dial", "K"), ("ticks", 1)):
        moved = _records(doc["rounds"], doc)
        moved[1]["verdict"][0][field] = value
        _must_refuse(moved, f"a bracketing verdict with a {field}")


def test_r07_the_outcome_is_held_to_the_fold_and_the_numbers_to_the_steps():
    doc = _fixture("W3-s26")

    def changed(edit, what, base=None):
        recs = _records(doc["rounds"], doc) if base is None else base
        edit(recs)
        return _must_refuse(recs, what)

    changed(lambda r: r[-1].update(kind="PAST-HI", reason="lean-hi", bracket=None, A_hull=None, B_hull=None, agree=None),
            "an outcome that is not the fold")
    changed(lambda r: r[-1].update(reason="lean-hi"), "a Located outcome with a reason")
    changed(lambda r: r[0]["settings"].update(z=1e6), "verdicts that are not the table's under the declared z")
    changed(lambda r: r[-1].update(bracket=[r[-1]["bracket"][0], r[-1]["bracket"][1] + 1e-9]), "a changed bracket number")
    changed(lambda r: r[-2]["scan"].update(lo=r[-2]["scan"]["lo"] + 1e-9), "a changed last lo")
    changed(lambda r: r[2]["scan"].update(hi=r[2]["scan"]["hi"] - 1e-9), "a changed hi in the middle: the next grid no longer starts there")
    changed(lambda r: r[0]["settings"].update(bracket=[0.2, 0.49]), "a first grid that is not the declared bracket")
    changed(lambda r: r[-1].update(steps=4), "an outcome that miscounts the steps")
    changed(lambda r: r[3].update(step=7), "a step numbered out of order")
    changed(lambda r: r[3].update(index=r[3]["index"] + 1), "an envelope index that is not its scan's")
    changed(lambda r: r.append(dict(r[-1])), "two outcomes")
    changed(lambda r: r.insert(len(r) - 1, dict(r[0])), "a start record in the middle")
    changed(lambda r: r.insert(1, r.pop()), "an outcome before the steps")
    changed(lambda r: r.pop(0), "no start record")
    changed(lambda r: r[2].update(phase="hold"), "a phase this reader does not read")
    changed(lambda r: r[2].update(extra=1), "an unknown key in a step")
    changed(lambda r: r[2]["scan"].update(extra=1), "an unknown key in a scan")
    changed(lambda r: r[0]["settings"].update(N=3), "more steps than N")
    lean = _records(_leaning(doc, -1))
    changed(lambda r: r[-1].update(bracket=doc["bracket"]), "a PAST-HI outcome that carries a bracket", base=lean)
    short = copy.deepcopy(doc["rounds"][:3])
    short[1].update({k: None for k in ("C", "C_err", "Gs", "Gs_err", "D", "A", "B")}, evaluated=False,
                    lo=short[1]["grid"][0], hi=short[1]["grid"][-1])
    short[2]["grid"] = short[1]["grid"]
    _must_refuse(_records(short), "a step after a step that was not evaluated")


def test_r08_the_start_record_is_held_to_its_types():
    doc = _fixture("W1-s22")

    def changed(edit, what):
        recs = _records(doc["rounds"], doc)
        edit(recs[0])
        return _must_refuse(recs, what)

    changed(lambda s: s.update(schema="compass-report/3"), "another schema")
    changed(lambda s: s.update(extra=1), "an unknown key in the start record")
    changed(lambda s: s.pop("sigma"), "no sigma")
    changed(lambda s: s["belief"].pop("system"), "a belief with a slot missing")
    changed(lambda s: s["belief"].update(system="at"), "a belief slot holding a bare value")
    changed(lambda s: s["belief"].update(nlev=2), "a belief slot holding a bare number")
    changed(lambda s: s["belief"].update(zz={"declared": 1}), "a belief with a slot that is not declared in the schema")
    changed(lambda s: s["belief"].update(tau={"declared": 67.0, "source": "default"}), "a declared value with a second key")
    changed(lambda s: s["belief"].update(ordered_side="unknown"), "a bracketing step with no declared ordered side")
    changed(lambda s: s["belief"].update(ordered_side={"declared": "sideways"}), "an ordered side with no cell")
    changed(lambda s: s["declared_other"].update(nlev=2), "a slot hidden in declared_other")
    for bad in (-1, 1.0, True, None, "0"):
        changed(lambda s, bad=bad: s["sigma"].update(offset=bad), f"sigma.offset {bad!r}")
    changed(lambda s: s["sigma"].update(unit="K"), "a sigma offset in another unit")
    changed(lambda s: s["sigma"].update(measured="C/C_max"), "a sigma with a measured definition this schema does not hold")
    changed(lambda s: s["sigma"].update(setpoint=0.92), "a sigma setpoint")
    changed(lambda s: s.update(dials="K"), "dials that are not a list")
    changed(lambda s: s.update(dials=["K", "K"]), "a dial held twice")
    changed(lambda s: s.pop("dials"), "no dials")
    changed(lambda s: s["mode"].update(feedback="ON"), "ON with no nudge held")
    changed(lambda s: s["mode"].update(ops=["declare", "measure", "nudge"]), "OFF with a nudge held")
    changed(lambda s: s["mode"].update(ops=["declare", "declare"]), "an op held twice")
    changed(lambda s: s["mode"].update(ops="declare"), "ops that are not a list")
    changed(lambda s: s["settings"].update(z=2), "z that is not a float")
    changed(lambda s: s["settings"].pop("detectors"), "no detectors")
    changed(lambda s: s["settings"].update(sigma=1.0), "an unknown setting")
    NS = _ns()
    on = _records(doc["rounds"], doc)
    on[0]["mode"] = {"ops": ["declare", "read", "nudge"], "feedback": "ON"}
    on[0]["sigma"]["offset"] = 3
    on[0]["dials"] = ["K", "p"]
    got = NS.read(_text(on))
    assert isinstance(got, NS.Stream) and got.start.dials == ("K", "p"), "a later needle's mode, offset and dials are readable as declared"
    on[1]["verdict"][0]["dial"] = "q"
    _must_refuse(on, "a verdict on a dial the needle does not hold")


def test_r09_read_never_raises():
    NS = _ns()
    doc = _fixture("W1-s22")
    good = _text(_records(doc["rounds"], doc))
    garbage = ["", "\n", " ", "null", "[]", "{", "{}", "5", '"x"', "[" * 100000, '{"rec": "start"}\n', '{"rec": 1}\n',
               '{"rec": "step"}\n', '{"rec": "outcome"}\n', "not json\n", good + "x\n", good + "{}\n", good + good,
               '{"rec": "start"}\n[]\n', good.replace("\n", "\n\n"), 5, None, b"{}", [], {}]
    for g in garbage:
        got = NS.read(g)
        assert isinstance(got, NS.Unreadable), repr(g)[:60]
        assert isinstance(got.why, str) and got.why, repr(g)[:60]
    lines = good.split("\n")
    for i in range(len(lines) - 1):
        for swap in ('{"rec": "step", "verdict": [{}]}', '{"rec": "step", "scan": 3, "verdict": []}', "null"):
            got = NS.read("\n".join(lines[:i] + [swap] + lines[i + 1:]))
            assert isinstance(got, NS.Unreadable), (i, swap)


def test_r10_the_reader_is_pure_and_the_schema1_reader_is_untouched():
    for rel, want in NEEDLEVIEW_SHA.items():
        assert hashlib.sha256((ROOT / rel).read_bytes()).hexdigest() == want, f"{rel} was changed"
    assert sorted(p.name for p in (ROOT / "needleview").glob("*.py")) == sorted(Path(r).name for r in NEEDLEVIEW_SHA)
    files = sorted((ROOT / "needlestream").glob("*.py"))
    assert {"__init__.py", "read.py"} <= {p.name for p in files}, [p.name for p in files]   # a later phase adds its reader beside these
    for path in files:
        tree = ast.parse(path.read_text())
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                assert all(a.name.split(".")[0] in ALLOWED_IMPORTS for a in node.names), [a.name for a in node.names]
            if isinstance(node, ast.ImportFrom):
                assert node.level == 0 and (node.module or "").split(".")[0] in ALLOWED_IMPORTS, node.module
                assert (node.module or "") not in ("navigator.recover", "navigator.recover2", "navigator.needle"), node.module
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                assert node.func.id not in ("open", "print", "input", "__import__", "exec", "eval"), node.func.id


if __name__ == "__main__":
    _tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    _fail = 0
    for _t in _tests:
        try:
            _t(); print(f"PASS {_t.__name__}")
        except Exception as _e:  # noqa: BLE001
            _fail += 1; print(f"FAIL {_t.__name__}: {type(_e).__name__}: {str(_e)[:300]}")
    print(f"{len(_tests) - _fail}/{len(_tests)} passed")
    sys.exit(1 if _fail else 0)
