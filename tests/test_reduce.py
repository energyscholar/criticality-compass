"""test_reduce - plan 0873 A1 item 1 (twin K1): cc/reduce.py reproduces the frozen toolset G from the raw snapshots S BIT FOR BIT,
at every L (27, 81, 243) and every level (data/x4s, X4s-1: its G is bit-identical to the frozen data/x4 G); plus the verbatim maps:
plurality3 equals majority on two colours (no ties among 9), block_mean of a known block, the total MAPS table."""
import sys
from pathlib import Path
import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path[:0] = [str(ROOT / "cc")]
import declare  # noqa: E402
import reduce  # noqa: E402

bad = []


def check(name, ok, why=""):
    print(("ok   " if ok else "FAIL ") + name + ("" if ok else f": {why}"))
    if not ok:
        bad.append(name)


root = declare.Ctx(ROOT).data_root
for L in (27, 81, 243):
    z = np.load(root / "x4s" / f"K0.4600-h0.0000-L{L}-plus.npz")
    G = z["G"]
    got = np.array([reduce.snapshot(x, "majority3", G.shape[1]) for x in z["S"]])
    check(f"L={L}: reduce(S) == the frozen G, every snapshot and level ({G.shape[1]} levels), bit for bit",
          got.shape == G.shape and got.dtype == G.dtype and got.tobytes() == G.tobytes(), f"{int((got != G).sum())} cells differ")
    for k in range(G.shape[1]):
        check(f"L={L} level {k}: the column is identical", got[:, k].tobytes() == G[:, k].tobytes())
z = np.load(root / "x4s" / "K0.4600-h0.0000-L27-plus.npz")
s = z["S"][:50].copy()
s[0, 0, 0] *= -1   # a planted one-spin change: the comparison must be able to see it
check("a planted one-spin flip changes the reduced G (the comparison can fail)",
      np.array([reduce.snapshot(x, "majority3", 2) for x in s]).tobytes() != z["G"][:50].tobytes())
rng = np.random.default_rng(0)
two = rng.integers(0, 2, size=(27, 27))
check("plurality3 on two colours equals the 3x3 majority (nine cells cannot tie)",
      (reduce.plurality3(two, 2, rng) == (reduce.block3(2 * two - 1) > 0)).all())
f = np.arange(36.0).reshape(6, 6)
check("block_mean of a 6x6 ramp is its 2x2 block means", reduce.block_mean(f).tolist() == [[7.0, 10.0], [25.0, 28.0]], str(reduce.block_mean(f)))
check("MAPS is the total table of the declared block maps", sorted(reduce.MAPS) == ["majority-occupied3", "majority3", "mean3"])
print("".join(f"FAILED {x}\n" for x in bad) + "test_reduce: " + ("FAILED" if bad else "all passed"))
sys.exit(1 if bad else 0)
