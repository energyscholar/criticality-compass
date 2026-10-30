"""needle.py - matched flow velocity and sink position (maths; the stages of instruments/needle.toml)."""
import numpy as np
import project


def reduce(arrays, ctx):
    """per-level means of the big and the small lattice: the 7-node vector (big levels, then small levels)."""
    big, small = arrays["GL"]
    return np.hstack([project.level_means(big), project.level_means(small)])


def series(arrays, ctx):
    """the primaries per file (plan 0878): every level of G at the big and the small lattice, [n, levels] each."""
    return list(arrays["GL"])


def from_means(ms, ctx):
    """reduce from the per-file primary means: the same 7-node vector."""
    return np.hstack(ms)


def matched(x, ctx):
    """A over the matched relation; the coarsest edge is the velocity; distances to the two declared sinks."""
    v_all = project.compared(x, ctx.rel["matched"])
    g_final = x.data[:, ctx.big_final]
    return {"velocity": v_all[:, ctx.coarsest], "d_ord": ctx.sink_ordered - g_final,
            "d_dis": g_final - ctx.sink_disordered, "v_all": v_all, "g_final": g_final}
