"""test_detect_verdicts - the worked rows: signature codes, verdict, class, verdict.toml line and why."""
import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path[:0] = [str(ROOT / "cc"), str(ROOT / "cc" / "instruments")]
import detect  # noqa: E402

NM = "NOT-MEASURED"
NEEDLE_NM = "honest null (not in verdict_x): the needle was not measured or not evaluated"
TWO_NM = "honest null: the two-start difference was not measured or not evaluated"
X8 = "x8-ising-needle"
ROWS = [  # input, point, codes, verdict, class, why
    (X8, "1.00", {"needle": "MID", "sink": "NEITHER", "flow": "UNRES", "across": NM, "stability": NM, "two_start": NM},
     "REFUSE-TWO-START-UNMEASURED", "REFUSE", TWO_NM),
    (X8, "1.10", {"needle": "ORD", "sink": "ORD", "flow": "SLOW", "across": NM, "stability": NM, "two_start": NM},
     "NOT", "NOT", "verdict_x STAGE1: off the window"),
    ("b7-at-line", "0.07", {"needle": NM, "sink": NM, "flow": NM, "across": "RELEVANT", "two_start": NM},
     "REFUSE-NEEDLE-UNMEASURED", "REFUSE", NEEDLE_NM),
    ("w2-potts", "2", {"needle": NM, "across": "RELEVANT", "stability": "STABLE", "two_start": "INDEP"},
     "REFUSE-NEEDLE-UNMEASURED", "REFUSE", NEEDLE_NM),
    ("w2-potts", "5", {"needle": NM, "across": "RELEVANT", "stability": "UNRES", "two_start": "UNRES"},
     "REFUSE-NEEDLE-UNMEASURED", "REFUSE", NEEDLE_NM),
    *[("c2-bc-two-start", f"d2.0-K{k}", {"needle": NM, "across": NM, "stability": NM, "two_start": "COEXIST"},
       "REFUSE-NEEDLE-UNMEASURED", "REFUSE", NEEDLE_NM) for k in ("2.0", "2.3", "2.6", "3.0")],
]
text = (ROOT / "tables/verdict-x-rules/verdict.toml").read_text()
whys, lines = [r["why"] for r in tomllib.loads(text)["row"]], detect.declare.row_lines(text)
bad, runs = [], {}
for inp, pt, codes, verdict, cls, why in ROWS:
    result = runs.setdefault(inp, detect.run(inp, "verdict-x-rules", write=False))
    sig = {s["point"]: s for s in result["signature"]}[pt]
    got = {k: sig[k] for k in codes}
    ok = (got == codes and (sig["verdict"], sig["verdict_class"], sig["why"]) == (verdict, cls, why)
          and sig["row_line"] == lines[whys.index(why)])
    print(("ok   " if ok else "FAIL ") + f"{inp} {pt}: {verdict}")
    if not ok:
        bad.append(f"{inp} {pt}: wanted {codes} {verdict}, got {got} {sig['verdict']} line {sig['row_line']}")
print("".join(f"FAILED {b}\n" for b in bad) + "test_detect_verdicts: " + ("FAILED" if bad else "all passed"))
sys.exit(1 if bad else 0)
