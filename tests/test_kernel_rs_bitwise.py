"""test_kernel_rs_bitwise - the INSTALLED kernel_rs wheel is BIT-identical to the Python reference kernel.py on the 300 random declared relations
of test_kernel_rs (same generator, same seed; copied here because that test is frozen). Two things the frozen test cannot do (plan 0929 blocker c):
it asserts allclose(1e-12), which one ulp passes; and it puts cc/_ext (the committed linux .so) first on sys.path, so it never sees an installed wheel.
Here cc/_ext is NOT on the path, the module must come from outside the repo, and the comparison is np.array_equal.
Rust-cell test (cc.toml [check] needs_rust): with no installed wheel it FAILS with a Next line; it is never skipped."""
import sys
from pathlib import Path
import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path[:0] = [str(ROOT / "cc")]
try:
    import kernel_rs
except ImportError:
    print("FAIL kernel_rs is not installed.\n  Next: pip install the kernel_rs wheel (rust/ builds it with maturin; see the [rust] extra), then rerun")
    sys.exit(1)
here = Path(kernel_rs.__file__).resolve()
if ROOT in here.parents:
    print(f"FAIL kernel_rs came from {here}, inside the repo: this test is for the INSTALLED wheel.\n  Next: remove cc/_ext from sys.path / PYTHONPATH and pip install the wheel")
    sys.exit(1)
assert kernel_rs.KERNEL_REV == "5c7941e0ce644dba844d3732fc25f9063db40f33", kernel_rs.KERNEL_REV
from kernel import A, B, R, rho, Provenance as P  # noqa: E402
import admit  # noqa: E402


def identical(g, w):
    """Bit identity of two arrays (same shape, every element equal; NaNs equal where both are NaN)."""
    return np.shape(g) == np.shape(w) and bool(np.array_equal(g, w, equal_nan=True))


# the comparison can fail: one ulp on one element is flagged (the frozen allclose test passes it)
base = np.array([1.0, 2.0, 3.0])
nudged = base.copy()
nudged[1] = np.nextafter(nudged[1], np.inf)
assert identical(base, base.copy()) and not identical(base, nudged) and np.allclose(base, nudged, rtol=1e-12, atol=1e-12)

rng = np.random.default_rng(20260930)
unequal = 0
for trial in range(300):
    n = int(rng.integers(2, 40))
    k = int(rng.integers(1, 4))
    cand = [(i, j) for i in range(n) for j in range(i + 1, n)]          # i < j: acyclic by construction
    ne = int(rng.integers(1, min(len(cand), 3 * n) + 1))
    idx = rng.choice(len(cand), ne, replace=False)
    edges = [cand[i] for i in idx]
    order = rng.permutation(n)                                          # relabel so direction is not index order
    edges = [(int(order[s]), int(order[t])) for s, t in edges]
    prov = [P.CONTINUATION if rng.random() < 0.7 else P.COUPLING for _ in edges]
    pairs = [(a, b) for a in range(k) for b in range(k) if a != b][: int(rng.integers(0, k))]
    cc = rng.normal(size=len(pairs))
    rb, c0 = float(rng.uniform(0.01, 2)), float(rng.uniform(0.01, 3))
    x = rng.normal(size=(k, n)) * rng.uniform(0.1, 10)
    rel, xf, m = admit.declare(n, edges, prov), admit.nodefield(x), admit.m(rb, c0, pairs, cc)
    a = A(xf, rel, m.pairs); b = B(a, rel); r_n = rho(a, rel, m); r = R(b, rel, r_n, m)
    got = [a.spatial, a.comp, b.spatial, b.comp, r_n, r.spatial, r.comp]
    want = kernel_rs.kernel_abr(x.tolist(), n, [(s, t, p.value) for (s, t), p in zip(edges, prov)], pairs, cc.tolist(), rb, c0)
    unequal += sum(not identical(g, np.asarray(w, dtype=float).reshape(np.shape(g))) for g, w in zip(got, want))
print(f"test_kernel_rs_bitwise: {here}: 300 random declared relations x 7 arrays, unequal arrays = {unequal}")
sys.exit(1 if unequal else 0)
