"""stability.py - does the growth exponent change between size steps: A over the steps chain (maths)."""
import numpy as np
import project
from kernel import A


def reduce(arrays, ctx):
    """R per size, from the same snapshots of G and E."""
    return np.stack([project.cov(g, e) for g, e in zip(arrays["G"], arrays["E"])])


def growth(x, ctx):
    """per-step growth y of ln(sR), one row per resample."""
    return {"y_steps": A(x, ctx.rel["size"]).spatial / ctx.log_ratio}


def curvature(x, ctx):
    """d = y_last - y_prev for EVERY resample: A over the steps chain at its last edge."""
    return {"d": A(x, ctx.rel["steps"]).spatial[:, ctx.top_steps]}
