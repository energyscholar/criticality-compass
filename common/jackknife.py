"""Plan 1569: the one jackknife (contract/SCHEMA-1569.md section 5). Equal, exactly, to the frozen `_jackknife` of both plugins'
blind faces: sqrt((B-1)/B * sum_b (loo_b - mean(loo))^2) with loo_b = f(all samples outside block b)."""
import math

import numpy as np

BLOCKS = 20   # jackknife blocks (declared)


def jackknife(S, f, blocks=BLOCKS):
    every = np.arange(S)
    loo = np.array([f(np.setdiff1d(every, b)) for b in np.array_split(every, blocks)])
    return math.sqrt((blocks - 1) / blocks * float(((loo - loo.mean()) ** 2).sum()))
