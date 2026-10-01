"""project.py - the declared projections the instruments read (maths; no branches, no literals)."""
import numpy as np


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
