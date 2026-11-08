"""test_w2 - replay of the frozen W2 study: Potts q = 2..5 at exact K_c, linear response, stability, two starts."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
from lib import bad, bootstrap, check  # noqa: E402
bootstrap(ROOT, "cc", "cc/instruments")
import detect  # noqa: E402

Q = ["2", "3", "4", "5"]
Y_LAST, Y_FIRST, DD = [0.997, 1.182, 1.442, 1.679], [0.979, 1.188, 1.448, 1.598], [0.018, -0.006, -0.006, 0.081]
D = {"2": [0.0004, 0.0001, -0.0000], "3": [0.0004, 0.0008, 0.0000], "4": [0.0014, 0.0022, 0.0004],
     "5": [-0.0030, -0.0048, 0.0039]}
Z, B3, B2 = "ZERO!", {"ZERO!", "SLOW+", "SLOW-"}, {"ZERO!", "SLOW+"}
CELLS = {"2": [{Z, "SLOW+"}, B3, B3], "3": [Z, {"SLOW+", Z}, B3], "4": [Z, B2, Z], "5": [Z, "UNRES", {"UNRES", Z}]}


res = detect.run("w2-potts", "verdict-x-rules", write=False)
rd = {(r["instrument"], r["unit"]["point"]): r for r in res["readings"] if r["column"] in ("y_last", "d", "D")}
steps = {r["unit"]["point"]: r["estimate"] for r in res["reports"] if r["name"] == "y_steps"}
sig = {s["point"]: s for s in res["signature"]}
across = all(abs(rd[("across", q)]["estimate"] - y) < 5e-4 and rd[("across", q)]["cell"] == "SIG+"
             and sig[q]["across"] == "RELEVANT" for q, y in zip(Q, Y_LAST))
check("across y_last (+-5e-4), SIG+, RELEVANT", across)
check("y_steps first step (+-5e-4)", all(abs(steps[q][0] - y) < 5e-4 for q, y in zip(Q, Y_FIRST)))
check("stability d (+-5e-4)", all(abs(rd[("stability", q)]["estimate"] - d) < 5e-4 for q, d in zip(Q, DD)))
check("stability cells ZERO!, ZERO!, ZERO!, UNRES -> STABLE x3, UNRES",
      [rd[("stability", q)]["cell"] for q in Q] == [Z, Z, Z, "UNRES"]
      and [sig[q]["stability"] for q in Q] == ["STABLE"] * 3 + ["UNRES"])
check("two_start D per (q, L) (+-1e-4)",
      all(abs(p["estimate"] - d) < 1e-4 for q in Q for p, d in zip(rd[("two_start", q)]["per_size"], D[q])))
cells = {q: [p["cell"] for p in rd[("two_start", q)]["per_size"]] for q in Q}
check("two_start cells (exact, boundary cells as sets)",
      all(g == w if isinstance(w, str) else g in w for q in Q for g, w in zip(cells[q], CELLS[q])), str(cells))
print("boundary cells landed:", cells)
check("combined two_start codes INDEP, INDEP, INDEP, UNRES",
      [sig[q]["two_start"] for q in Q] == ["INDEP"] * 3 + ["UNRES"], str([sig[q]["two_start"] for q in Q]))
print("".join(f"FAILED {b}\n" for b in bad) + "test_w2: " + ("FAILED" if bad else "all passed"))
sys.exit(1 if bad else 0)
