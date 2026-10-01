"""test_kernel_rs.py - the Python reference (kernel.py) must EQUAL the pinned Rust kernel on random declared relations."""
import sys
import numpy as np
sys.path[:0] = [__file__.rsplit("/", 2)[0] + "/cc", __file__.rsplit("/", 2)[0] + "/cc/_ext"]
import kernel_rs
assert kernel_rs.KERNEL_REV == "5c7941e0ce644dba844d3732fc25f9063db40f33"
from kernel import A, B, R, rho, Provenance as P
import admit

rng = np.random.default_rng(20260930)
worst = 0.0
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
    want = kernel_rs.kernel_abr(x.tolist(), n, [(s, t, p.value) for (s, t), p in zip(edges, prov)],
                                pairs, cc.tolist(), rb, c0)
    for g, w in zip(got, want):
        w = np.asarray(w, dtype=float).reshape(np.shape(g))
        worst = max(worst, float(np.max(np.abs(g - w), initial=0.0)))
        assert np.allclose(g, w, rtol=1e-12, atol=1e-12), (trial, g, w)
print(f"test_kernel_rs: 300 random declared relations, Python == Rust, worst |diff| = {worst:.2e}")

# the Rust crate refuses an undeclared rho as a NotEvaluated VALUE (not a crash)
try:
    kernel_rs.kernel_abr([[1.0, 2.0]], 2, [(0, 1, "Continuation")], [], [], 0.5, 0.0)
    raise AssertionError("Rust accepted chi_0 = 0")
except kernel_rs.NotEvaluatedError:
    pass
# DIVERGENCE (recorded, not repaired): the Rust constructor ACCEPTS a cycle; V8 section 4 declares rings inadmissible.
out = kernel_rs.kernel_abr([[1.0, 2.0, 3.0]], 3, [(0, 1, "Continuation"), (1, 2, "Continuation"), (2, 0, "Continuation")], [], [], 0.5, 1.0)
print("Rust accepts a 3-cycle (V8 text forbids it; our door refuses it):", out[0])
