"""test_resample.py - on a synthetic AR(1) (tau ~ 50), the block interval for the mean must match the TRUE spread of the
mean over independent replicates, and the iid interval must be far too narrow (the failure B5 exposed)."""
import sys
import numpy as np
sys.path.insert(0, __file__.rsplit("/", 2)[0] + "/cc")
from resample import block_indices, iid_indices

rng = np.random.default_rng(3)
phi, n = np.exp(-1 / 50), 8000


def ar1():
    x = np.zeros(n)
    e = rng.normal(size=n)
    for t in range(1, n):
        x[t] = phi * x[t - 1] + e[t]
    return x


true_sd = np.std([ar1().mean() for _ in range(200)])
x = ar1()
blk = np.std([x[block_indices(n, 400, rng)].mean() for _ in range(400)])
iid = np.std([x[iid_indices(n, rng)].mean() for _ in range(400)])
idx = block_indices(n, 400, rng)
assert len(idx) == n and idx.min() >= 0 and idx.max() < n
print(f"true sd of mean {true_sd:.4f} | block bootstrap {blk:.4f} | iid bootstrap {iid:.4f}")
assert 0.6 < blk / true_sd < 1.5, "block interval does not match the true spread"
assert iid / true_sd < 0.3, "iid interval should be far too narrow here"
print("test_resample: all passed")
