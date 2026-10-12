"""test_kernel.py - the kernel reference against HAND-COMPUTED values, and the door's refusals. Each test was seen to
fail on a deliberately wrong expectation before being trusted."""
import sys
import numpy as np
sys.path.insert(0, __file__.rsplit("/", 2)[0] + "/cc")
from kernel import A, B, R, E, rho, Provenance as P
import admit

C = P.CONTINUATION
# chain 0 -> 1 -> 2 -> 3 (direction declared: node order along the chain)
rel = admit.declare(4, [(0, 1), (1, 2), (2, 3)], [C, C, C])
x = admit.nodefield([1.0, 4.0, 9.0, 16.0])
m = admit.m(rho_base=0.5, chi_0=1.0)

a = A(x, rel).spatial[0]
assert np.allclose(a, [-3, -5, -7]), a                        # x[s] - x[t]
b = B(A(x, rel), rel).spatial[0]
assert np.allclose(b, [-3 - 5, -5 - 7, -7]), b                # IMMEDIATE successor only; terminal adds nothing
r_n = rho(A(x, rel), rel, m)
assert np.allclose(r_n, [0.5 * 3 / 4, 0.5 * 5 / 6, 0.5 * 7 / 8, 0.5 * 7 / 8]), r_n   # chi = max |A| incident
bg = B(A(x, rel), rel)
r = R(bg, rel, r_n, m).spatial[0]
want = [bg.spatial[0][0] + r_n[0] * (bg.spatial[0][1] - 0),
        bg.spatial[0][1] + r_n[1] * (bg.spatial[0][2] - bg.spatial[0][0]),
        bg.spatial[0][2] + r_n[2] * (0 - bg.spatial[0][1])]
assert np.allclose(r, want), (r, want)
assert np.allclose(E(x, rel, m).spatial[0], r)

# B is NOT a path sum: on a 4-node chain, B at the first edge != the net change x[0]-x[3]
assert not np.isclose(b[0], x.data[0, 0] - x.data[0, 3])
# ... except on a 3-node chain (2 edges), where it is exactly the net change (what Case A used)
rel3 = admit.declare(3, [(0, 1), (1, 2)], [C, C])
x3 = admit.nodefield([2.0, 5.0, 11.0])
assert np.isclose(B(A(x3, rel3), rel3).spatial[0][0], 2.0 - 11.0)

# component pairs + cc (two components, pair (0,1))
m2 = admit.m(0.5, 1.0, pairs=[(0, 1)], cc=[0.25])
x2 = admit.nodefield([[1.0, 2.0, 4.0, 8.0], [0.0, 1.0, 1.0, 3.0]])
g2 = A(x2, rel, m2.pairs)
assert np.allclose(g2.comp[0], [1, 1, 3, 5])
assert np.allclose(B(g2, rel).comp[0], [1 + 1, 1 + 3, 3 + 5, 5])  # comp B: c[i] + sum over out[i] of c[tgt]

# the door refuses, with a reason
for bad, why in [(lambda: admit.declare(3, [(0, 1), (1, 2), (2, 0)], [C] * 3), "cycle"),
                 (lambda: admit.declare(2, [(0, 5)], [C]), "outside"),
                 (lambda: admit.declare(2, [(0, 1)], ["Persistence"]), "provenance"),
                 (lambda: admit.nodefield([1.0, np.nan]), "finite"),
                 (lambda: admit.m(np.nan, 1.0), "NOT EVALUATED"),
                 (lambda: admit.m(0.5, 0.0), "NOT EVALUATED"),
                 (lambda: admit.m(0.5, 1.0, pairs=[(0, 1)], cc=[]), "cc")]:
    try:
        bad()
        raise AssertionError(f"door did not refuse: {why}")
    except ValueError as e:
        assert why in str(e), (why, e)
print("test_kernel: all passed")
