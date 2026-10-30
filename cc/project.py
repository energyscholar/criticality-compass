"""project.py - the declared projections the instruments read (maths; no branches, no literals)."""
from dataclasses import dataclass
import numpy as np


@dataclass(frozen=True)
class Comparison:
    """A declared comparison: ordered differences inside projection C (KERNEL-IN-CC.md). It has no provenance and no src/tgt fields,
    so admit.declare cannot take it as a provenance and kernel.A/B cannot read it (plan 1337)."""
    n: int
    hi: np.ndarray      # int[P]: the minuend index of each declared difference
    lo: np.ndarray      # int[P]: the subtrahend index


def compared(x, c):
    """The declared differences inside C: x[hi] - x[lo] (the same float operation as kernel.A, so bit-identical)."""
    return x.data[:, c.hi] - x.data[:, c.lo]


def continued(g, c):
    """C's chain sum: g[e] plus g over the comparisons leaving lo(e) (kernel.B's expression, read over a comparison)."""
    return np.array([s + np.bincount(c.hi, weights=s, minlength=c.n)[c.lo] for s in g]).reshape(g.shape)


def level_means(gl):
    """per-level mean of a [snapshots, levels] stack."""
    return np.mean(gl, axis=0)


def cov(a, b):
    """the linear response R = cov(G, E) over one resample (the same snapshots for both arrays)."""
    return np.mean(a * b) - np.mean(a) * np.mean(b)


def logcoord(v, s):
    """ln(s R): s is the constant sign the door found; it is declared, never taken here."""
    return np.log(s * v)


def scaled_mean(q, scale):
    """mean of Q over the resample, divided by the declared unit scale."""
    return np.mean(q) / scale


def p_delta(v, shape):
    """Delta per (resample row, size): the signed pair differences re-declared with sizes along the last axis
    (keeps the signed difference per size and row; discards which two runs it came from)."""
    return np.reshape(v, shape)


def density_var(e, scale):
    """var of e / scale over one resample: the second cumulant of the density (keeps it; discards the higher cumulants
    and the time order of the snapshots)."""
    d = e / scale - np.mean(e / scale)
    return np.mean(d * d)


def cov_of_means(mg, me, mge):
    """R = cov(G, E) from the means of G, E and G*E: the same projection as cov, read on the Gamma-method's three primaries (plan 0878)."""
    return mge - mg * me


def density_var_of_means(m, m2):
    """var of e from the means of e and e*e: the same projection as density_var, read on its two primaries (plan 0878)."""
    return m2 - m * m
