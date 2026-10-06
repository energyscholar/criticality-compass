"""two_start.py - do two declared starts disagree: A over the start pair (maths)."""
import numpy as np
import project
from kernel import A


def reduce(arrays, ctx):
    """mean of Q per start, over the declared unit scale (the starts come in the pair's order)."""
    return np.stack([project.scaled_mean(q, ctx.unit_scale) for q in arrays["Q"]])


def series(arrays, ctx):
    """the primaries per file (plan 0878): Q per start, [n, 1]."""
    return [q[:, None] for q in arrays["Q"]]


def from_means(ms, ctx):
    """reduce from the per-file primary means: the mean of Q per start over the declared unit scale."""
    return np.stack([m[0] / ctx.unit_scale for m in ms])


def difference(x, ctx):
    """D = Q[b] - Q[a] for the first declared pair."""
    return {"D": A(x, ctx.rel["start"]).spatial[:, 0]}
