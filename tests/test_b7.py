"""test_b7 - replay of the frozen B7 ACROSS block on the Ashkin-Teller self-dual line; stability is new."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path[:0] = [str(ROOT / "cc"), str(ROOT / "cc" / "instruments")]
import detect  # noqa: E402

PTS = ["0.0", "0.07", "0.14", "0.21", "0.2747"]
Y = [1.009, 1.073, 1.175, 1.331, 1.321]
EDGES = [(0.976, 1.045), (1.040, 1.106), (1.137, 1.223), (1.265, 1.391), (1.202, 1.423)]   # B7.txt, p lines
bad = []


def check(name, ok, why=""):
    print(("ok   " if ok else "FAIL ") + name + ("" if ok else f": {why}"))
    if not ok:
        bad.append(name)


res = detect.run("b7-at-line", "verdict-x-rules", write=False)
rd = {(r["instrument"], r["unit"]["point"]): r for r in res["readings"] if r["column"] in ("y_last", "d")}
steps = {r["unit"]["point"]: r["estimate"] for r in res["reports"] if r["name"] == "y_steps"}
across = [rd[("across", p)] for p in PTS]
stab = [rd[("stability", p)] for p in PTS]
check("across y_last equals B7's (+-5e-4)", all(abs(r["estimate"] - y) < 5e-4 for r, y in zip(across, Y)),
      str([r["estimate"] for r in across]))
check("across cells SIG+ x5, codes RELEVANT", all(r["cell"] == "SIG+" and r["code"] == "RELEVANT" for r in across))
check("every across reading carries the flags H and T", all(r["flags"] == ["H", "T"] for r in across))
match = all(abs(r["lo"] - lo) < 6e-4 and abs(r["hi"] - hi) < 6e-4 for r, (lo, hi) in zip(across, EDGES))
print("B7's own resample stream: intervals match the printed digits:", match)
check("stability readings are values, not nulls", all(r["estimate"] is not None for r in stab))
check("stability d = y_steps[1] - y_steps[0] of across at row 0 (+-1e-6)",
      all(abs(r["estimate"] - (steps[p][1] - steps[p][0])) < 1e-6 for r, p in zip(stab, PTS)))
print("stability d and cell per point:", [(p, round(r["estimate"], 3), r["cell"]) for r, p in zip(stab, PTS)])
print("".join(f"FAILED {b}\n" for b in bad) + "test_b7: " + ("FAILED" if bad else "all passed"))
sys.exit(1 if bad else 0)
