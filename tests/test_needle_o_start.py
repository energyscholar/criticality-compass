"""test_needle_o_start - needle_o really reads the ORDERED start (plan 0867 P3 gap). x9c-potts q = 8 is first order: the random
start's level stack flows to the disordered sink (needle DIS), the ordered start's stays at the ordered sink (needle_o ORD, d_ord
AT), and the pair is PINNED-BETWEEN-PHASES. The breaker: instruments/needle_o.toml `start = "random"` makes needle_o read the
random start, so it reads DIS like needle and the pair collapses; this test must turn RED under that mutation.
CC_NEEDLE_O_INNER=1 (set by the mutation run) skips the mutation run, so it does not recurse."""
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path[:0] = [str(ROOT / "cc"), str(ROOT / "cc" / "instruments")]
import detect  # noqa: E402

bad = []


def check(name, ok, why=""):
    print(("ok   " if ok else "FAIL ") + name + ("" if ok else f": {why}"))
    if not ok:
        bad.append(name)


res = detect.run("x9c-potts", "v03-rules", write=False)
sig = {s["point"]: s for s in res["signature"]}["8"]
o = {r["column"]: r["code"] for r in res["readings"] if r["instrument"] == "needle_o" and r["unit"]["point"] == "8"}
check("q8: the random start's needle reads DIS", sig["needle"] == "DIS", sig["needle"])
check("q8: the ordered start's needle_o reads ORD (velocity ORD, d_ord AT, d_dis NOT-AT)",
      (o["velocity"], o["d_ord"], o["d_dis"]) == ("ORD", "AT", "NOT-AT"), str(o))
check("q8: the pair is PINNED-BETWEEN-PHASES", sig["needle_pair"] == "PINNED-BETWEEN-PHASES", sig["needle_pair"])
if not os.environ.get("CC_NEEDLE_O_INNER"):
    r = subprocess.run([str(ROOT / "bin" / "cc"), "mutate", "instruments/needle_o.toml", "--sed", 's/^start = "ordered"/start = "random"/',
                        "--", "test_needle_o_start"], capture_output=True, text=True, cwd=ROOT, env={**os.environ, "CC_NEEDLE_O_INNER": "1"})
    check("the mutation start = \"random\" turns this test red", "RED   test_needle_o_start" in r.stdout, r.stdout[-300:] + r.stderr[-300:])
print("".join(f"FAILED {x}\n" for x in bad) + "test_needle_o_start: " + ("FAILED" if bad else "all passed"))
sys.exit(1 if bad else 0)
