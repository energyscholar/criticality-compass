"""reduce.py - the declared reduction of a stack of snapshots to its level stack GL (maths; plan 0873 A1).
block3, levels: VERBATIM from the toolset's frozen tools/scale.py. plurality3: VERBATIM from tools/scale3.py (its stochastic
tie-break is part of the declared map; the rng is the caller's declared seed). g1: VERBATIM from tools/flow.py.
block_mean and levels_mean are the one new map (a linear 3x3 block mean for a continuous field; no tie to break). MAPS is the
total table from a declared [block_map] name to its level chain; snapshot reduces ONE snapshot exactly as the toolset's X4
generator did (g1 of each level of one snapshot), so a stack reduces to the frozen G bit for bit."""
import numpy as np


def block3(s):
    """s: (..., L, L) of +-1 -> (..., L/3, L/3) of +-1 by 3x3 majority."""
    n, L = s.shape[:-2], s.shape[-1]                             # form: the two lattice axes
    b = s.reshape(*n, L // 3, 3, L // 3, 3).sum(axis=(-3, -1))  # form: 3x3 blocks (odd => no ties)
    return np.sign(b).astype(np.int8)


def levels(s, count):
    out = [s]
    for _ in range(count - 1):
        out.append(block3(out[-1]))
    return out


def plurality3(s, q, rng):
    """s: (L, L) ints in [0, q) -> (L/3, L/3)."""
    L = s.shape[-1]
    blocks = s.reshape(L // 3, 3, L // 3, 3).transpose(0, 2, 1, 3).reshape(L // 3, L // 3, 9)   # form: 3x3 blocks
    counts = np.stack([(blocks == c).sum(axis=-1) for c in range(q)], axis=-1)     # form: count of each colour (indicator)
    top = counts == counts.max(axis=-1, keepdims=True)                                        # form: the plurality set
    noise = rng.random(top.shape) * top                                                       # uniform among tied colours
    return noise.argmax(axis=-1)


def g1(s):
    """s: (N, L, L) snapshots -> (N,) per-snapshot open-pair nearest-neighbour correlation."""
    s = s.astype(float)
    h = (s[..., :, :-1] * s[..., :, 1:]).mean(axis=(-2, -1))      # form: the two lattice axes
    v = (s[..., :-1, :] * s[..., 1:, :]).mean(axis=(-2, -1))      # form: the two lattice axes
    return (h + v) / 2                                            # form: mean over the two declared directions


def block_mean(f):
    """f: (..., L, L) real -> (..., L/3, L/3): the mean of each 3x3 block (linear; keeps long-wavelength content exactly)."""
    n, L = f.shape[:-2], f.shape[-1]                             # form: the two lattice axes
    return f.reshape(*n, L // 3, 3, L // 3, 3).mean(axis=(-3, -1))   # form: 3x3 blocks


def levels_mean(f, count):
    out = [f.astype(float)]
    for _ in range(count - 1):
        out.append(block_mean(out[-1]))
    return out


MAPS = {"majority3": levels, "mean3": levels_mean}


def snapshot(x, name, count):
    """The level stack of ONE snapshot x (L, L): g1 of each of its `count` levels under the declared map `name`."""
    return np.array([g1(lv[None])[0] for lv in MAPS[name](x, count)])
