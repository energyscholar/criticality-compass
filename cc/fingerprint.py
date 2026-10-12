"""fingerprint.py - the family fingerprints as maths inside the declared projection C (plan 0892, an external verifier (ruling Q19)): consecutive and all-pairs
differences of stored per-point readings over index pairs. Not a relational pass: no kernel operator, no declared relation, no door (maths)."""
import numpy as np
import sign


def chain_pairs(n):
    """(i, i + 1) for i = 0..n-2, in axis order: the difference read is x[i + 1] - x[i] (the door's chain edge order)."""
    return [(i, i + 1) for i in range(n - 1)]


def all_pairs(n):
    """(i, j) for j = 1..n-1 and i < j, nested in that order: the difference read is x[j] - x[i] (the door's all-pairs edge order)."""
    return [(i, j) for j in range(1, n) for i in range(j)]


def _ij(pairs):
    return np.array([i for i, _ in pairs], int), np.array([j for _, j in pairs], int)


def code_steps(ranks, pairs):
    """The sign cell of each difference ranks[j] - ranks[i] over the index pairs, eps = 0: three cells."""
    i, j = _ij(pairs)
    r = np.asarray(ranks, dtype=float)
    d = r[j] - r[i]
    return [s.value for s in sign.sign(d, d, 0)]


def pair_differences(y, pairs):
    """y[:, j] - y[:, i] per row for every index pair (i, j): [rows, pairs]."""
    i, j = _ij(pairs)
    y = np.asarray(y, dtype=float)
    return y[:, j] - y[:, i]
