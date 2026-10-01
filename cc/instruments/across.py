"""across.py - growth of the linear response R = cov(G, E) with system size (maths)."""
import numpy as np
import project
from kernel import A


def reduce(arrays, ctx):
    """R per size, from the same snapshots of G and E."""
    return np.stack([project.cov(g, e) for g, e in zip(arrays["G"], arrays["E"])])


def growth(x, ctx):
    """x holds ln(sR) per size; A over the size chain divided by the declared ln of the size ratio."""
    y = A(x, ctx.rel["size"]).spatial / ctx.log_ratio
    return {"y_steps": y, "y_last": y[:, ctx.top]}
