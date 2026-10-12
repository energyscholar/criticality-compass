"""report.py - the relation-free report (maths; the stages of instruments/report.toml): the per-level means of the declared block states and the declared sinks."""
import numpy as np
import project


def reduce(arrays, ctx):
    """per-level means of the level stack of each declared size, side by side (one size for a windowed input)."""
    return np.hstack([project.level_means(gl) for gl in arrays["GL"]])


def series(arrays, ctx):
    """the primaries per file (plan 0878): every level of G at the declared size(s), [n, levels] each."""
    return list(arrays["GL"])


def from_means(ms, ctx):
    """reduce from the per-file primary means: the same vector."""
    return np.hstack(ms)


def describe(x, ctx):
    """the reports: the level means per row, and the declared sinks (ordered, disordered) repeated per row. No column is read."""
    return {"levels": x, "sinks": np.stack([np.zeros(len(x)) + ctx.sink_ordered, np.zeros(len(x)) + ctx.sink_disordered], axis=1)}
