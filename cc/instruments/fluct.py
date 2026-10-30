"""fluct.py - does the variance of the energy density persist with system size: A over ln var(e) (maths)."""
import numpy as np
import project


def reduce(arrays, ctx):
    """var(e) per size, e = E / the declared unit scale (the second cumulant of the density)."""
    return np.stack([project.density_var(e, s) for e, s in zip(arrays["E"], ctx.unit_scales)])


def series(arrays, ctx):
    """the primaries per file (plan 0878): e and e*e per size, e = E / the declared unit scale, [n, 2]."""
    d = [e / s for e, s in zip(arrays["E"], ctx.unit_scales)]
    return [np.stack([x, x * x], axis=1) for x in d]


def from_means(ms, ctx):
    """reduce from the per-file primary means: var(e) per size."""
    return np.stack([project.density_var_of_means(*m) for m in ms])


def growth(x, ctx):
    """x holds ln var(e) per size; A over the size chain divided by the declared ln of the size ratio."""
    y = project.compared(x, ctx.rel["size"]) / ctx.log_ratio
    return {"y_steps": y, "y_last": y[:, ctx.top]}
