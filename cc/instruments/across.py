"""across.py - growth of the linear response R = cov(G, E) with system size (maths)."""
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
    """x holds ln(sR) per size; A over the size chain divided by the declared ln of the size ratio."""
    y = project.compared(x, ctx.rel["size"]) / ctx.log_ratio
    return {"y_steps": y, "y_last": y[:, ctx.top]}
