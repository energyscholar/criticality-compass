"""test_probe - plan 0870: the geometry-axis locks of expected/<set>.toml [geometry.*]; probe completeness (D1): a planted gap in
probe.toml and a planted bad couplings.toml are refused, the two refusals read as declared, and the stored v04-rules results say so."""
import json
import shutil
import sys
import tempfile
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
from lib import bad, bootstrap, check  # noqa: E402
bootstrap(ROOT, "cc", "cc/instruments")
import declare  # noqa: E402
import detect  # noqa: E402
import family  # noqa: E402


def result(inp, tset="v04-rules"):
    return json.loads((ROOT / "results" / f"{inp}@{tset}.json").read_text())


for f in sorted((ROOT / "expected").glob("*.toml")):
    for inp, want in tomllib.loads(f.read_text()).get("geometry", {}).items():
        got = {s["point"]: s["geometry"] for s in result(inp, f.stem)["signature"]}
        miss = {p: (w, got[p]) for p, w in want.items() if got[p] not in ([w] if isinstance(w, str) else w)}
        check(f"{inp} under {f.stem}: the geometry lock (declared before the run)", not miss and set(want) <= set(got), str(miss))
for f in sorted((ROOT / "expected").glob("*.toml")):     # plan 0870 P2: locks on a signature column, declared before the run; a point not named is unlocked
    lock = tomllib.loads(f.read_text())
    for col in ("drift_code", "flow", "probe", "verdict_set"):
        for inp, want in lock.get(col, {}).items():
            got = {s["point"]: s["verdict" if col == "verdict_set" else col] for s in result(inp, f.stem)["signature"]}
            miss = {p: (w, got[p]) for p, w in want.items() if got[p] not in ([w] if isinstance(w, str) else w)}
            check(f"{inp} under {f.stem}: the {col} lock (declared before the run)", not miss and set(want) <= set(got), str(miss))
for f in sorted((ROOT / "expected").glob("*.toml")):     # plan 0870 P3: a family lock that allows more than one outcome (declared before the run)
    for fid, want in tomllib.loads(f.read_text()).get("family_set", {}).items():
        msg, got = family.run(ROOT, fid, f.stem)
        bad_keys = {k: (w, got[1].get(k)) for k, w in want.items() if got is None or got[1].get(k) not in w}
        check(f"family {fid} under {f.stem}: the lock that allows a set (declared before the run)", msg is None and not bad_keys, f"{msg} {bad_keys}")
x5 = result("x5n-bilayer-2")
check("x5n-bilayer-2@v04-rules: verdict REFUSE-PROBE-INCOMPLETE x3 and signature probe INCOMPLETE",
      [(s["verdict"], s["probe"]) for s in x5["signature"]] == [("REFUSE-PROBE-INCOMPLETE", "INCOMPLETE")] * 3, str([(s["verdict"], s["probe"]) for s in x5["signature"]]))
b4 = result("b7-at-line-4")
check("b7-at-line-4@v04-rules: geometry 0.0/0.07 REFUSE-PROBE-INCOMPLETE, verdict unchanged x5",
      [s["geometry"] for s in b4["signature"][:2]] == ["REFUSE-PROBE-INCOMPLETE"] * 2 and {s["verdict"] for s in b4["signature"]} == {"REFUSE-TWO-START-UNMEASURED"})
msg, got = family.run(ROOT, "b7-at-line-2", "v04-rules")
check("family b7-at-line-2 reads LINE under v04-rules", msg is None and got[1]["verdict"] == "LINE", str(msg))
T = detect.load_tables("v04-rules")
cells = {"needle_ordered.velocity": "NOT-MEASURED", "needle.d_ord": "SIG+", "needle.d_dis": "SIG+", "needle.velocity": "ZERO!", "across.y_last": "SIG+",
         "stability.d": "ZERO!", "two_start.D": ["ZERO!", "ZERO!", "ZERO!"]}
for probe, want in (("COMPLETE", "POINT"), ("INCOMPLETE", "REFUSE-PROBE-INCOMPLETE"), ("UNKNOWN", "REFUSE-PROBE-UNKNOWN"), ("NOT-MEASURED", "POINT")):
    codes = detect.codes_of({**cells, "declared.probe": probe, "needle.d_ord": "NEG", "needle.d_dis": "NEG"}, T)
    sig = {n: codes[n] for n in T.codes["columns"]["signature"]}
    check(f"a POINT reading with probe {probe} reads {want}", detect.verdict_of(sig, T)[0] == want and detect.axes_of(codes, T)["geometry"] == want, str(sig))
for why, edit, find in (
        ("a planted missing cell in probe.toml is refused", lambda t: t.replace('when.probe = ["UNKNOWN"]\nwhen.geometry = ["POINT", "LINE", "WALKING"]', 'when.probe = ["UNKNOWN"]\nwhen.geometry = ["POINT", "LINE"]'), "uncovered cells"),
        ("a probe.toml refusal that is not a listed verdict is refused", lambda t: t.replace('verdict = "REFUSE-PROBE-UNKNOWN"', 'verdict = "REFUSE-PROBE-NOWHERE"'), "is not in verdicts")):
    with tempfile.TemporaryDirectory() as t:
        shutil.copy(ROOT / "cc.toml", t)
        shutil.copy(ROOT / "checks.toml", t)
        shutil.copytree(ROOT / "tables" / "v04-rules", Path(t) / "tables" / "v04-rules")
        f = Path(t) / "tables" / "v04-rules" / "probe.toml"
        f.write_text(edit(f.read_text()))
        found = declare.check_file(f, t)
        check(why, any(find in x.msg for x in found), str([x.msg[:80] for x in found]))
for why, edit, find in (
        ("a couplings.toml that omits a stored scalar is refused", lambda t: t.replace('names = ["K", "g"]', 'names = ["K"]'), "must equal the scalars"),
        ("a couplings.toml that probes an undeclared coupling is refused", lambda t: t.replace('probes = ["K"]', 'probes = ["Q"]'), "not a declared coupling"),
        ("a couplings.toml that declares unknown while the data store scalars is refused", lambda t: t.replace('names = ["K", "g"]', 'names = "unknown"'), "the data store the scalars")):
    with tempfile.TemporaryDirectory() as t:
        d = Path(t) / "inputs" / "x5n-bilayer-2"
        d.mkdir(parents=True)
        shutil.copy(ROOT / "cc.toml", t)
        shutil.copy(ROOT / "checks.toml", t)
        shutil.copy(ROOT / "inputs" / "x5n-bilayer-2" / "m.toml", d)
        (d / "couplings.toml").write_text(edit((ROOT / "inputs" / "x5n-bilayer-2" / "couplings.toml").read_text()))
        found = declare.check_file(d / "couplings.toml", t, data_root=declare.Ctx(ROOT).data_root)
        check(why, any(find in x.msg for x in found), str([x.msg[:80] for x in found]))
fam = tomllib.loads((ROOT / "tables" / "v04-rules" / "family.toml").read_text())
lines = declare.row_lines((ROOT / "tables" / "v04-rules" / "family.toml").read_text())
ask = lambda b, f1, f2: detect.verdict_of({"bracket": b, "f1": f1, "f2": f2}, type("S", (), {"verdict": fam, "lines": lines}))   # noqa: E731
check("family (BRACKET, CONSTANT, IRRELEVANT) reads POINT-MANIFOLD, class POINT", ask("BRACKET", "CONSTANT", "IRRELEVANT")[:2] == ("POINT-MANIFOLD", "POINT"))
check("the two siblings of POINT-MANIFOLD are named refusals, each with a Next line",
      all(ask("BRACKET", a, b)[0] == "REFUSE-UNCLASSIFIED" and "Next:" in ask("BRACKET", a, b)[3] for a, b in (("VARIES", "IRRELEVANT"), ("CONSTANT", "MARGINAL"))))
check("a family LINE is still LINE (v03-rules' row)", ask("NOT-MEASURED", "VARIES", "MARGINAL")[:2] == ("LINE", "LINE"))
with tempfile.TemporaryDirectory() as t:
    shutil.copy(ROOT / "cc.toml", t)
    shutil.copy(ROOT / "checks.toml", t)
    shutil.copytree(ROOT / "instruments", Path(t) / "instruments")
    shutil.copytree(ROOT / "tables" / "v04-rules", Path(t) / "tables" / "v04-rules")
    f = Path(t) / "tables" / "v04-rules" / "family.toml"
    text = f.read_text()
    cut = text.index('[[row]]\nwhen = { bracket = ["BRACKET", "NO-MID", "NOT-MEASURED"], f1 = ["CONSTANT"], f2 = ["IRRELEVANT"] }')
    f.write_text(text[:cut] + text[text.index("[[row]]", cut + 5):])
    found = declare.check_file(f, t)
    check("a planted missing POINT-MANIFOLD row in family.toml is refused", any("uncovered cells" in x.msg for x in found), str([x.msg[:80] for x in found]))
new_refusals = [(n, r["why"]) for n in ("verdict", "probe", "family") for r in tomllib.loads((ROOT / "tables" / "v04-rules" / f"{n}.toml").read_text())["row"]
                if r["verdict"] in ("REFUSE-PROBE-INCOMPLETE", "REFUSE-PROBE-UNKNOWN", "REFUSE-UNCLASSIFIED")]
check(f"every new REFUSE row of v04-rules ({len(new_refusals)} rows) names a Next line in its why", len(new_refusals) == 12 and all("Next:" in w for _, w in new_refusals), str(new_refusals)[:300])
print("".join(f"FAILED {x}\n" for x in bad) + "test_probe: " + ("FAILED" if bad else "all passed"))
sys.exit(1 if bad else 0)
