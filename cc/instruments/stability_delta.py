"""stability_delta.py - does the growth exponent of the DIFFERENCE of a declared control pair change between size steps: d_D = yD2 - yD1 (maths).
reduce and delta are across_delta's; growth reports the step exponents; curvature is stability's, on the Delta basis."""
import numpy as np
import project
from kernel import A


def reduce(arrays, ctx):
    """mean of G per (size ascending, member of the pair: node 0 = a, node 1 = b): one [n_size, 2] array per row."""
    return np.stack([np.mean(g) for g in arrays["G"]]).reshape(ctx.pair_shape)


def series(arrays, ctx):
    """the primaries per file (plan 0878): G per (size, member of the pair), [n, 1]."""
    return [g[:, None] for g in arrays["G"]]


def from_means(ms, ctx):
    """reduce from the per-file primary means: the mean of G per (size ascending, member of the pair), one [n_size, 2] array."""
    return np.stack([m[0] for m in ms]).reshape(ctx.pair_shape)


def delta(x, ctx):
    """Delta(L) = A over the ONE declared control edge (b - a); sizes and resample rows are components."""
    return {"delta": project.p_delta(A(x, ctx.unit_rel).spatial[:, 0], ctx.component_shape)}


def growth(x, ctx):
    """x holds ln(s Delta) per size; A over the size chain divided by the declared ln of the size ratio gives the step exponents yD1, yD2 (raw: no transform)."""
    return {"y_steps": project.compared(x, ctx.rel["size"]) / ctx.log_ratio}


def curvature(x, ctx):
    """d = yD2 - yD1 for EVERY resample: A over the steps chain at its last edge."""
    return {"d": project.compared(x, ctx.rel["steps"])[:, ctx.top_steps]}
