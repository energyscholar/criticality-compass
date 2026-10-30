"""kernel_identity_l - kernel.py and the INSTALLED kernel_rs give bit-identical A, B, rho and R on one adapter array per L (plan 1282 P1d).
Usage: kernel_identity_l.py DIR [--nudge]. DIR holds q2-L27.npy, q2-L81.npy, q2-L243.npy (G of the sampler, shape (N, nlev)): x = G, k = N components over n = nlev nodes.
The relation is the level chain, finer to coarser, one Coupling edge per step. Run by hand (it needs an argument, so it is test infrastructure, not a registered test).
--nudge moves the first finite element of kernel_rs's A-spatial one ulp up: the comparison must then report exactly 1 unequal array per L (the RED).
Scope: identity of the kernel arithmetic on one declared one-Coupling relation per L; it does not cover the input's control relation over points.
It never skips: a missing or in-repo kernel_rs prints FAIL with a Next line and exits 1."""
import argparse
import hashlib
import sys
from pathlib import Path
import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path[:0] = [str(ROOT / "cc")]
try:
    import kernel_rs
except ImportError:
    print("FAIL kernel_rs is not installed.\n  Next: pip install the kernel_rs wheel (rust/ builds it with maturin), then rerun with plain python3")
    sys.exit(1)
here = Path(kernel_rs.__file__).resolve()
if ROOT in here.parents:
    print(f"FAIL kernel_rs came from {here}, inside the repo: this tool is for the INSTALLED wheel.\n  Next: remove cc/_ext from sys.path / PYTHONPATH and pip install the wheel")
    sys.exit(1)
assert kernel_rs.KERNEL_REV == "5c7941e0ce644dba844d3732fc25f9063db40f33", kernel_rs.KERNEL_REV
from kernel import A, B, R, rho, Provenance  # noqa: E402
import admit  # noqa: E402

KERNEL_SHA = "1b8b1936ca4658de13ebf153cdae78f68c9bb2b10e4eba05ffaaef8eba90a9d2"
assert hashlib.sha256((ROOT / "cc" / "kernel.py").read_bytes()).hexdigest() == KERNEL_SHA, "cc/kernel.py is not the kernel of record"


def identical(g, w):
    """Bit identity of two arrays (same shape, every element equal; NaNs equal where both are NaN)."""
    return np.shape(g) == np.shape(w) and bool(np.array_equal(g, w, equal_nan=True))


base = np.array([1.0, 2.0, 3.0])
one_ulp = base.copy()
one_ulp[1] = np.nextafter(one_ulp[1], np.inf)
assert identical(base, base.copy()) and not identical(base, one_ulp) and np.allclose(base, one_ulp, rtol=1e-12, atol=1e-12)

ap = argparse.ArgumentParser()
ap.add_argument("dir")
ap.add_argument("--nudge", action="store_true")
args = ap.parse_args()
d = Path(args.dir).expanduser()
bad = 0
for L in (27, 81, 243):
    x = np.load(d / f"q2-L{L}.npy").astype(np.float64)
    k, n = x.shape
    edges = [(i, i + 1) for i in range(n - 1)]
    prov = [Provenance.COUPLING] * len(edges)
    pairs, cc, rb, c0 = [(0, 1)], np.array([0.5]), 1.0, 1.0
    rel, xf, m = admit.declare(n, edges, prov), admit.nodefield(x), admit.m(rb, c0, pairs, cc)
    a = A(xf, rel, m.pairs); b = B(a, rel); r_n = rho(a, rel, m); r = R(b, rel, r_n, m)
    got = [a.spatial, a.comp, b.spatial, b.comp, r_n, r.spatial, r.comp]
    want = kernel_rs.kernel_abr(x.tolist(), n, [(s, t, p.value) for (s, t), p in zip(edges, prov)], pairs, cc.tolist(), rb, c0)
    want = [np.asarray(w, dtype=float).reshape(np.shape(g)) for g, w in zip(got, want)]
    if args.nudge:
        i = int(np.flatnonzero(np.isfinite(want[0].ravel()))[0])
        want[0].flat[i] = np.nextafter(want[0].flat[i], np.inf)
    unequal = sum(not identical(g, w) for g, w in zip(got, want))
    print(f"L={L} n={n} k={k} unequal {unequal} of 7")
    print(f"  shapes {[tuple(np.shape(g)) for g in got]}")
    bad += unequal
sys.exit(1 if bad else 0)
