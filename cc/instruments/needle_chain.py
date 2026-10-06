"""needle_chain.py - the matched velocity of TWO size pairs and the drift of the needle between them (maths)."""
import numpy as np
import project
from kernel import A


def reduce(arrays, ctx):
    """per-level means of every size (largest first), laid end to end as the matched pairs (big, small), (small, smaller)."""
    m = [project.level_means(g) for g in arrays["GL"]]
    return np.hstack([m[j] for k in range(len(m) - 1) for j in (k, k + 1)])


def series(arrays, ctx):
    """the primaries per file (plan 0878): every level of G at each size, [n, levels]."""
    return list(arrays["GL"])


def from_means(ms, ctx):
    """reduce from the per-file primary means: the matched pairs laid end to end."""
    return np.hstack([ms[j] for k in range(len(ms) - 1) for j in (k, k + 1)])


def chain(x, ctx):
    """A over both matched pairs: the coarsest edge of each is its velocity. [previous, top] go to the log door."""
    v = A(x, ctx.rel["chain"]).spatial
    both = np.stack([v[:, -1], v[:, ctx.coarsest]], axis=1)
    return {"delta": both, "velocity_prev": both[:, 0]}


def drift(x, ctx):
    """omega_eff - 1: x holds ln|v| of (previous, top); A over that step, divided by the declared ln of the size ratio."""
    return {"drift": -A(x, ctx.rel["steps"]).spatial[:, 0] / ctx.log_ratio[ctx.top] - 1}
