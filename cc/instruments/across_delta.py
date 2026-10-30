"""across_delta.py - the low-variance across: growth with size of the DIFFERENCE of a declared control pair (maths)."""
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
    """x holds ln(s Delta) per size; A over the size chain divided by the declared ln of the size ratio gives the step exponents yD1, yD2. The reading is
    y_last = yD2 + r (yD2 - yD1)/(1 - r) = (yD2 - r yD1)/(1 - r), r = ctx.ratio (plan 0874: the pair's door value selects r; r = 0 on a RAW pair, so y_last = yD2)."""
    y = project.compared(x, ctx.rel["size"]) / ctx.log_ratio
    r = ctx.ratio
    return {"y_steps": y, "ratio": r, "y_last": y[:, ctx.top] + r * (y[:, ctx.top] - y[:, ctx.top_steps]) / (1 - r)}
