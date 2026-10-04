"""test_probe - plan 0870: the geometry-axis locks of expected/<set>.toml [geometry.*]; probe completeness (D1): a planted gap in
probe.toml and a planted bad couplings.toml are refused, the two refusals read as declared, and the stored v04-rules results say so."""
import json
import shutil
import sys
import tempfile
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path[:0] = [str(ROOT / "cc"), str(ROOT / "cc" / "instruments")]
import declare  # noqa: E402
import detect  # noqa: E402
import family  # noqa: E402

bad = []


def check(name, ok, why=""):
    print(("ok   " if ok else "FAIL ") + name + ("" if ok else f": {why}"))
    if not ok:
        bad.append(name)


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
print("".join(f"FAILED {x}\n" for x in bad) + "test_probe: " + ("FAILED" if bad else "all passed"))
sys.exit(1 if bad else 0)
