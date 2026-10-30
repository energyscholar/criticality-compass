"""stability.py - does the growth exponent change between size steps: A over the steps chain (maths)."""
import numpy as np
import project


def reduce(arrays, ctx):
    """R per size, from the same snapshots of G and E."""
    return np.stack([project.cov(g, e) for g, e in zip(arrays["G"], arrays["E"])])


def series(arrays, ctx):
    """the primaries per file (plan 0878): G, E and G*E per size, [n, 3]."""
    return [np.stack([g, e, g * e], axis=1) for g, e in zip(arrays["G"], arrays["E"])]


def from_means(ms, ctx):
    """reduce from the per-file primary means: R per size."""
    return np.stack([project.cov_of_means(*m) for m in ms])


def growth(x, ctx):
    """per-step growth y of ln(sR), one row per resample."""
    return {"y_steps": project.compared(x, ctx.rel["size"]) / ctx.log_ratio}


def curvature(x, ctx):
    """d = y_last - y_prev for EVERY resample: A over the steps chain at its last edge."""
    return {"d": project.compared(x, ctx.rel["steps"])[:, ctx.top_steps]}
