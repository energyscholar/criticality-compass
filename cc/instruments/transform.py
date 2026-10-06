"""transform.py - the declared finite-size transform y_inf = (y2 - r y1)/(1 - r) on one point (maths).
y1, y2 are the growth exponents of ln(s R) over the two size steps (R = cov(G, E), as stability); r = v2/v1 is the needle's own drift ratio (|v| of the top
matched pair over |v| of the previous pair, as needle_chain); equivalently y_inf = y2 + r (y2 - y1)/(1 - r), the limit of a correction that decays by r per step."""
import numpy as np
import project
from kernel import A


def reduce(arrays, ctx):
    """the matched-chain level means laid end to end (largest pair first), then R per size ASCENDING (the blocks come largest first)."""
    m = [project.level_means(g) for g in arrays["GL"]]
    needle = np.hstack([m[j] for k in range(len(m) - 1) for j in (k, k + 1)])
    r = np.stack([project.cov(g, e) for g, e in zip(arrays["G"], arrays["E"])])
    return np.hstack([needle, r[::-1]])


def series(arrays, ctx):
    """the primaries per file (plan 0878): G, E and G*E, then every level of G, at each size, [n, 3 + levels]."""
    return [np.hstack([np.stack([g, e, g * e], axis=1), gl]) for gl, g, e in zip(arrays["GL"], arrays["G"], arrays["E"])]


def from_means(ms, ctx):
    """reduce from the per-file primary means: the matched-chain level means laid end to end, then R per size ASCENDING."""
    split = [(project.cov_of_means(mg, me, mge), np.array(lv)) for mg, me, mge, *lv in ms]
    levels = [lv for _, lv in split]
    needle = np.hstack([levels[j] for k in range(len(levels) - 1) for j in (k, k + 1)])
    return np.hstack([needle, np.stack([r for r, _ in split])[::-1]])


def velocity(x, ctx):
    """A over the matched chain: the previous and top velocities (as needle_chain); R per size is the trailing block. All go to the log door."""
    v = A(x, ctx.rel["chain"]).spatial
    return {"delta": np.hstack([x.data[:, -ctx.n_size:], np.stack([v[:, -1], v[:, ctx.coarsest]], axis=1)])}


def ratio(x, ctx):
    """x holds ln(s R) per size, then ln|v| of (previous, top): y1, y2 by A over the size chain, and ln r = ln|v_top| - ln|v_prev|."""
    y = A(x, ctx.rel["size"]).spatial / ctx.log_ratio
    return {"y1": y[:, 0], "y2": y[:, ctx.top], "lnr": x.data[:, ctx.n_size + 1] - x.data[:, ctx.n_size]}


def transform(x, ctx):
    """y_inf = y2 + r (y2 - y1)/(1 - r); the door has refused every resample whose r is not below 1."""
    r = np.exp(x["lnr"])
    return {"y_inf": x["y2"] + r * (x["y2"] - x["y1"]) / (1 - r)}
