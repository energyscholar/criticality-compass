"""test_x5 - the X5 bilayer input (plan 0864 P5): under verdict-x-rules CC reproduces the toolset's frozen results/X5c.txt
point for point (verdict, needle side and flow, response, stability, start screen), and the three NOT are the KNOWN FALSE
NEGATIVES; under v01-rules g 0 and g 0.3 refuse as REFUSE-SLOW and g 0.1 stays NOT. The case carries the seal's sha256."""
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path[:0] = [str(ROOT / "cc"), str(ROOT / "cc" / "instruments")]
import detect  # noqa: E402

X5C = Path(os.environ.get("CC_TOOLSET") or Path(os.environ["CC_DATA_ROOT"]).parent) / "results/X5c.txt"   # the study checkout: CC_TOOLSET, else the parent of CC_DATA_ROOT
bad = []


def check(name, ok, why=""):
    print(("ok   " if ok else "FAIL ") + name + ("" if ok else f": {why}"))
    if not ok:
        bad.append(name)


text = X5C.read_text()
want = [re.search(r"VERDICT (\S+)", b).group(1) for b in re.split(r"(?m)^T=", text)[1:4]]
side = re.findall(r"side (\w+), flow (\w+)", text)
resp = re.findall(r"-> (\w+) \| d=.*-> (\w+)\n", text)
start = re.findall(r"-> (INDEP|COEXIST)", text)
x = detect.run("x5-bilayer", "verdict-x-rules", write=False)["signature"]
check("X5c.txt gives three verdicts", want == ["NOT"] * 3 and len(side) == len(resp) == len(start) == 3, str((want, side, resp, start)))
check("CC reproduces X5c's verdicts (3 of 3)", [s["verdict"] for s in x] == want, str([s["verdict"] for s in x]))
check("CC reproduces X5c's needle side and flow, response, stability and start screen",
      [(s["needle"], s["flow"]) for s in x] == [tuple(q) for q in side] and [s["across"] for s in x] == [r[0] for r in resp]
      and [s["stability"] for s in x] == [r[1] for r in resp] and [s["two_start"] for s in x] == start, str(x))
check("the three NOT are the known false negatives: the lock says why", "KNOWN FALSE NEGATIVE (X5-score)"
      in (ROOT / "expected" / "verdict-x-rules.toml").read_text())
v = [s["verdict"] for s in detect.run("x5-bilayer", "v01-rules", write=False)["signature"]]
check("under v01-rules g 0 and g 0.3 are REFUSE-SLOW and g 0.1 is NOT", v == ["REFUSE-SLOW", "NOT", "REFUSE-SLOW"], str(v))
case = (ROOT / "cases" / "coupled-ising-bilinear.toml").read_text()
check("the case is POINT and names the seal's sha256 file, which holds one hash",
      'class_truth = "POINT"' in case and re.fullmatch(r"[0-9a-f]{64}  \S+\.toml\n", (ROOT / "fixtures" / "X5-truth-2026-10-01.sha256").read_text())
      is not None and 'blind_seal = "fixtures/X5-truth-2026-10-01.sha256"' in case)
print("".join(f"FAILED {b}\n" for b in bad) + "test_x5: " + ("FAILED" if bad else "all passed"))
sys.exit(1 if bad else 0)
