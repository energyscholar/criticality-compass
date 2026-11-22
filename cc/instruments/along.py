"""along.py - the B7 statistic: growth with size of the difference of a declared control pair (maths)."""
import numpy as np
import project
from kernel import A   # A is the only step from nodes to edges; why the input is shaped for it: KERNEL-IN-CC.md, "Why CC uses relational math"


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
    """x holds ln(s Delta) per size; y_along = continued(compared(x, size), size) at the top edge (a chain sum inside C, plan 1337) over the declared ln size span."""
    return {"y_along": project.continued(project.compared(x, ctx.rel["size"]), ctx.rel["size"])[:, ctx.top] / ctx.log_span}
