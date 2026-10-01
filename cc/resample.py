"""resample.py - T3b: interval resampling that respects correlation in the sample (maths; no branches).
block_indices: the moving-block bootstrap (Kunsch 1989): contiguous blocks of length b, starts drawn uniformly, joined
and cut to length n. b must exceed the sample's correlation time several times over (declared per study).
iid_indices: the ordinary bootstrap (valid ONLY for independent samples; kept to show the difference)."""
import numpy as np


def block_indices(n, b, rng):
    starts = rng.integers(0, n - b + 1, -(-n // b))
    return (starts[:, None] + np.arange(b)).ravel()[:n]


def iid_indices(n, rng):
    return rng.integers(0, n, n)
