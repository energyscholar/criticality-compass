"""across_delta.py - the low-variance across: growth with size of the DIFFERENCE of a declared control pair (maths)."""
import numpy as np
import project
from kernel import A


def reduce(arrays, ctx):
    """mean of G per (size ascending, member of the pair: node 0 = a, node 1 = b): one [n_size, 2] array per row."""
    return np.stack([np.mean(g) for g in arrays["G"]]).reshape(ctx.pair_shape)


def delta(x, ctx):
    """Delta(L) = A over the ONE declared control edge (b - a); sizes and resample rows are components."""
    return {"delta": project.p_delta(A(x, ctx.unit_rel).spatial[:, 0], ctx.component_shape)}


def growth(x, ctx):
    """x holds ln(s Delta) per size; A over the size chain divided by the declared ln of the size ratio; the last step is the exponent."""
    y = A(x, ctx.rel["size"]).spatial / ctx.log_ratio
    return {"y_steps": y, "y_last": y[:, ctx.top]}
