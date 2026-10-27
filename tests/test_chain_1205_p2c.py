"""test_chain_1205_p2c - plan 1205 P2c: amendment A1 (research/1205/FABLE-F1-REVIEW.md s1, bound by LL1-PRE-v7.md): the robustness identity is
CONTAINMENT, replacing overlap. A segment s = [lo, hi] of lane L in cell X RECURS in cell Y iff Y holds a segment [lo', hi'] of L with lo' <= lo and
hi <= hi'; m(s) counts the lane's cells in which s recurs (X included); located_fraction is dropped (constant by construction). It reads no real data.
 A1. 10 UNTIERED curves, d(3|4) = 0.03, every other adjacent d = 0.20, w_c in {0.05, 0.10, 0.15, 0.25}: cells 0.05 / 0.10 / 0.15 hold [3, 4] only,
     cell 0.25 holds [0, 9]. In cell 0.25: [0, 9] has cells = 1, FRAGILE; [3, 4] (cells 0.05 .. 0.15) has cells = 4, ROBUST.
     Red (seen at the staged P2b tree, overlap rule): [0, 9] has cells = 4, ROBUST.
 A2. the segment rows carry no located_fraction. Red: the field is still written.
 A3. the declared IDENTITY string names containment, not overlap, and the module docstring agrees. Red: the overlap string.
 A4. the edge lane counts over all its cells (stride cells included): 16 cells in the v6 grid, and a segment recurring in all 16 reads cells = 16.
     Red: keys() ignores the strides."""
import sys
from dataclasses import dataclass
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path[:0] = [str(ROOT / "cc"), str(ROOT / "tests")]
import chain  # noqa: E402
import intake_feature as F  # noqa: E402

bad = []


def check(name, ok, why=""):
    print(("ok   " if ok else "FAIL ") + name + ("" if ok else f": {why}"))
    if not ok:
        bad.append(name)


@dataclass(frozen=True)
class Curve:
    slow: tuple
    rows: list


def fam(curves):
    return chain.Family("p2c", tuple(curves), tuple(float(c.slow[0]) for c in curves), F.span(curves, None), F.FAST_ENDS[True](curves, None), 2.0, "COLUMN", "h")


POS = [0.5, 0.7, 0.5, 0.7, 0.73, 0.53, 0.73, 0.53, 0.73, 0.53]   # adjacent d: 0.20 everywhere but pair 3|4 (0.03)
N = 1001
curves = [Curve((float(j),), [(i / (N - 1), float(np.exp(-((i / (N - 1) - p) / 0.02) ** 2)), 0.0) for i in range(N)]) for j, p in enumerate(POS)]
fm = fam(curves)
LANE = chain.Lane.ARGMAX_FAST
g = chain.Grid((0.05, 0.10, 0.15, 0.25), (LANE,), "p2c")
ev = chain.evaluate(fm, g)
cells, atoms = chain.rows(fm, g, ev)
mine = {c["wc"]: c for c in cells if c["lane"] == LANE.name}
segs = {w: [tuple(s["ranks"]) for s in mine[w]["segments"]] for w in mine}
check("A1. setup: UNTIERED, cells 0.05 / 0.10 / 0.15 hold [3, 4] only and cell 0.25 holds [0, 9]",
      all(segs[w] == [(3, 4)] for w in (0.05, 0.10, 0.15)) and segs[0.25] == [(0, 9)], str(segs))
row = {tuple(s["ranks"]): s for s in mine[0.25]["segments"]}
check("A1. cell 0.25: [0, 9] has cells = 1 and is FRAGILE (containment: no smaller-w_c cell holds a segment containing it)",
      row[(0, 9)]["cells"] == 1 and row[(0, 9)]["robustness"] == "FRAGILE", str(row[(0, 9)]))
r34 = mine[0.05]["segments"][0]
check("A1. [3, 4] (cells 0.05 .. 0.15) has cells = 4 (the 0.25 cell's [0, 9] contains it) and is ROBUST", r34["cells"] == 4 and r34["robustness"] == "ROBUST", str(r34))
check("A2. the segment rows carry no located_fraction", all("located_fraction" not in s for c in cells for s in c["segments"]), "")
check("A3. IDENTITY names containment, not overlap, and the module docstring agrees",
      "contain" in chain.IDENTITY.lower() and "overlap" not in chain.IDENTITY.lower() and "overlap" not in chain.__doc__ and "containment" in chain.__doc__.lower(), chain.IDENTITY)

g6 = chain.grid(str(ROOT / "intake" / "grids" / "ll1-pre-v6.toml"))
E = chain.Lane.ARGMAX_ABS_A_FAST
cl = [Curve((0.1 * (j + 1),), [(1.0 + i, 10.0 / (1 + (i - 20) ** 2), 0.03) for i in range(40)]) for j in range(9)]
f2 = fam(cl)
c6, _ = chain.rows(f2, g6, chain.evaluate(f2, g6))
edge = [c for c in c6 if c["lane"] == E.name]
whole = [s for c in edge for s in c["segments"] if s["ranks"] == [0, 8]]
check("A4. edge lane: 16 cells; a segment [0, 8] present in every cell reads cells = 16 (stride cells counted)",
      len(edge) == 16 and len(whole) == 16 and all(s["cells"] == 16 for s in whole), f"{len(edge)} {len(whole)} {[s['cells'] for s in whole]}")

print(f"\n{len(bad)} FAIL" if bad else "\nall ok")
sys.exit(1 if bad else 0)
