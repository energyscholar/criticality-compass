"""test_reverdict - a stored result re-verdicted under another table set WITHOUT measuring (plan 0864 P1):
it reproduces every frozen verdict, equals a real run under the new set, runs no instrument, and refuses
when a set changes what a door or membership read."""
from functools import partial
import json
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
from lib import bad, bootstrap, cc as run_cc, check  # noqa: E402
bootstrap(ROOT, "cc", "cc/instruments")
import detect  # noqa: E402
import door  # noqa: E402
import score  # noqa: E402
import frozen  # noqa: E402


calls = []
detect.measure = lambda *a: calls.append("measure") or {}          # any instrument run is recorded
detect.instrument = lambda *a: calls.append("instrument")
door.load_blocks = lambda *a: calls.append("load_blocks")
olds = [json.loads(f.read_text()) for f in sorted((ROOT / "results").glob("*@verdict-x-rules.json"))]
X, V = detect.load_tables("verdict-x-rules"), detect.load_tables("v01-rules")
same = [score.reverdict_result(r, X) for r in olds]
n = sum(len(a["signature"]) * (json.dumps(a["signature"]) == json.dumps(b["signature"])
                               and json.dumps(a["readings"]) == json.dumps(b["readings"])) for a, b in zip(same, olds))
check("reverdict under verdict-x-rules reproduces every frozen verdict, byte for byte (66 of 66)", n == 66, str(n))
check("a derived result names its parent and the parent's vectors",
      all(a["derived_from"] == b["run_id"] and a["vectors"] == b["vectors"] for a, b in zip(same, olds)))
real = {r["input"]: json.loads((ROOT / "results" / f"{r['input']}@v01-rules.json").read_text()) for r in olds}
new = [score.reverdict_result(r, V) for r in olds]
check("reverdict under v01-rules equals the real run under v01-rules (signature and readings)",
      all(a["signature"] == real[a["input"]]["signature"] and a["readings"] == real[a["input"]]["readings"] for a in new))
with tempfile.TemporaryDirectory() as t:           # a set that really moves a code: across SIG+ reads WEAK, not RELEVANT
    shutil.copytree(ROOT / "tables" / "verdict-x-rules", Path(t) / "flip")
    f = Path(t) / "flip" / "codes.toml"
    frozen.thaw(f)
    f.write_text(f.read_text().replace('"SIG+" = "RELEVANT"', '"SIG+" = "WEAK"'))
    b7 = next(r for r in olds if r["input"] == "b7-at-line")
    flip = score.reverdict_result(b7, detect.load_tables("flip", t))
    hit = [r for r in flip["readings"] if r["column"] == "y_last" and r["cell"] == "SIG+"]
    check("a changed code map re-codes the readings and the signature, never the cells",
          hit and all(r["code"] == "WEAK" for r in hit) and {s["across"] for s in flip["signature"]} == {"WEAK"}
          and [r["cell"] for r in flip["readings"]] == [r["cell"] for r in b7["readings"]], str(hit[:1]))
check("reverdict ran no instrument and read no data", not calls, str(calls))
with tempfile.TemporaryDirectory() as t:
    for name, text in (("a", "x = 1\n"), ("b", "x = 2\n"), ("c", "x = 1\n"), ("d", "")):
        (Path(t) / "tables" / name).mkdir(parents=True)
        if text:
            (Path(t) / "tables" / name / "membership.toml").write_text(text)
    res = {"input": "i", "tables": "a", "interval": {"method": "block"}}   # plan 0937: a stored result always names its interval method (the refusal reads it)
    refused = {k: score.reverdict_refusal(res, k, t) for k in "bcd"}
    check("a set whose membership differs is refused with the re-measure command",
          "bin/cc run i --tables b" in (refused["b"] or "") and "bin/cc run i --tables d" in (refused["d"] or ""), str(refused))
    check("a set with the same membership is not refused", refused["c"] is None, str(refused["c"]))
with tempfile.TemporaryDirectory() as t:
    repo = Path(t) / "repo"
    shutil.copytree(ROOT, repo, ignore=shutil.ignore_patterns(".git", "__pycache__"))
    frozen.thaw(repo)   # the copy only; the live tree is frozen
    for q in repo.glob("results/*@v01-rules.*"):
        q.unlink()
    fz = json.loads((repo / "FROZEN.json").read_text())   # the copy is writable: v01-rules results are unfrozen in it
    fz["files"] = {k: v for k, v in fz["files"].items() if "@v01-rules." not in k}
    (repo / "FROZEN.json").write_text(json.dumps(fz))

    cc = partial(run_cc, repo)
    rc, out = cc("reverdict", "x8-ising-needle", "--tables", "v01-rules", "--from", "verdict-x-rules")
    out_json = json.loads((repo / "results" / "x8-ising-needle@v01-rules.json").read_text()) if rc == 0 else {}
    check("the CLI writes a derived result and copies no vectors",
          rc == 0 and out_json["derived_from"] == "x8-ising-needle@verdict-x-rules"
          and not (repo / "results" / "x8-ising-needle@v01-rules.npz").exists(), out)
    cc("tables", "fork", "v01-rules", "mem")
    (repo / "tables" / "mem" / "membership.toml").write_text("x = 1\n")
    rc, out = cc("reverdict", "x8-ising-needle", "--tables", "mem", "--from", "verdict-x-rules")
    check("the CLI refuses a set whose membership differs", rc == 1 and "membership.toml" in out
          and "bin/cc run x8-ising-needle --tables mem" in out, out)
    rc, out = cc("freeze", "x8-ising-needle@v01-rules")
    check("a derived result freezes (its vectors are the parent's)", rc == 0 and "froze" in out, out)
    rc, out = cc("reverdict", "x8-ising-needle", "--tables", "v01-rules", "--from", "verdict-x-rules")
    check("a frozen target is refused", rc == 1 and "is frozen" in out and "Next:" in out, out)
    rc, out = cc("reverdict", "x8-ising-needle", "--tables", "nope")
    check("an unknown set is refused with the sets named", rc == 1 and "no table set 'nope'" in out and "Next:" in out, out)
print("test_reverdict: " + ("FAILED" if bad else "all passed"))
sys.exit(1 if bad else 0)
