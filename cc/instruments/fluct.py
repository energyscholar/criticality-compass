"""fluct.py - does the variance of the energy density persist with system size: A over ln var(e) (maths)."""
import numpy as np
import project
from kernel import A


def reduce(arrays, ctx):
    """var(e) per size, e = E / the declared unit scale (the second cumulant of the density)."""
    return np.stack([project.density_var(e, s) for e, s in zip(arrays["E"], ctx.unit_scales)])


def growth(x, ctx):
    """x holds ln var(e) per size; A over the size chain divided by the declared ln of the size ratio."""
    y = A(x, ctx.rel["size"]).spatial / ctx.log_ratio
    return {"y_steps": y, "y_last": y[:, ctx.top]}
