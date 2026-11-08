"""test_needle_x8 - replay of the frozen P2/X8 needle on the 2D Ising data (matched velocity + sink position)."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
from lib import bad, bootstrap, check  # noqa: E402
bootstrap(ROOT, "cc", "cc/instruments")
import detect  # noqa: E402

PTS = ["0.90", "0.95", "0.98", "0.99", "1.00", "1.01", "1.02", "1.05", "1.10"]
VEL = [-0.1454, -0.1895, -0.2205, -0.1892, -0.0031, 0.0976, 0.0673, 0.0228, 0.0026]
V_ALL = [[-0.1414, -0.1994, -0.1454], [-0.0962, -0.177, -0.1895], [-0.0519, -0.1316, -0.2205],
         [-0.0268, -0.0937, -0.1892], [0.0153, -0.0013, -0.0031], [0.0558, 0.074, 0.0976],
         [0.072, 0.0849, 0.0673], [0.0993, 0.0809, 0.0228], [0.104, 0.0443, 0.0026]]
CELL = ["SIG-"] * 4 + ["UNRES"] + ["SIG+"] * 3 + ["SLOW+"]
D_ORD = ["SIG+"] * 6 + ["SLOW+"] + [{"SLOW+", "ZERO!", "SLOW-"}, {"ZERO!", "SLOW+", "SLOW-"}]


def codes(column):
    return [sig[p][column] for p in PTS]


res = detect.run("x8-ising-needle", "verdict-x-rules", write=False)
rd = {(r["column"], r["unit"]["point"]): r for r in res["readings"] if r["instrument"] == "needle"}
rep = {r["unit"]["point"]: r["estimate"] for r in res["reports"] if r["name"] == "v_all"}
sig = {s["point"]: s for s in res["signature"]}
vel_cells = [rd[("velocity", p)]["cell"] for p in PTS]
check("velocity estimates equal P2's coarsest (+-5e-4)",
      all(abs(rd[("velocity", p)]["estimate"] - v) < 5e-4 for p, v in zip(PTS, VEL)))
check("v_all equals P2's three matched velocities per point (+-5e-4)",
      all(abs(a - b) < 5e-4 for p, v in zip(PTS, V_ALL) for a, b in zip(rep[p], v)))
check("velocity cells (exact)", vel_cells == CELL, str(vel_cells))
check("d_dis reads SIG+ at all nine", all(rd[("d_dis", p)]["cell"] == "SIG+" for p in PTS))
got = [rd[("d_ord", p)]["cell"] for p in PTS]
check("d_ord cells (exact, with the two boundary cells as sets)",
      all(g == w if isinstance(w, str) else g in w for g, w in zip(got, D_ORD)), str(got))
print("boundary cells landed: d_ord 1.05", got[7], "1.10", got[8])
check("sink codes", codes("sink") == ["NEITHER"] * 6 + ["ORD"] * 3, str(codes("sink")))
check("needle codes (the sink-aware needle reads ORD at 1.10, P2 read MID)",
      codes("needle") == ["DIS"] * 4 + ["MID"] + ["ORD"] * 4, str(codes("needle")))
check("flow codes", codes("flow") == ["FLOWING"] * 4 + ["UNRES"] + ["FLOWING"] * 3 + ["SLOW"], str(codes("flow")))
print("".join(f"FAILED {b}\n" for b in bad) + "test_needle_x8: " + ("FAILED" if bad else "all passed"))
sys.exit(1 if bad else 0)
