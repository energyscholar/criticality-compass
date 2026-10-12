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


def majority_occupied3(s):
    """s: (..., L, L) of {-1, 0, +1}, 0 = a vacant site OR a tie -> (..., L/3, L/3): per 3x3 cell the sign of the sum over its OCCUPIED sites. A vacant site adds nothing; a tie
    (sum 0, an all-vacant cell included) is block state 0, deterministic (plan 0884; Bruce E318). On an array without zeros it is block3, bit for bit."""
    return block3(s)


def levels_occupied(s, count):
    out = [s]
    for _ in range(count - 1):
        out.append(majority_occupied3(out[-1]))
    return out


def g1_occupied(s):
    """s: (N, L, L) of {-1, 0, +1} -> (N,): g1 over the nearest-neighbour pairs whose BOTH sites are non-zero (a vacancy is not a pair, never a zero in the mean): the mean of the
    products over the occupied horizontal pairs and over the occupied vertical pairs, then their mean. With no occupied pair in a direction the mean is over nothing: the null is NaN (0 / 0, which numpy reports as a RuntimeWarning)."""
    s = s.astype(float)
    h = (s[..., :, :-1] * s[..., :, 1:]).sum(axis=(-2, -1)) / ((s[..., :, :-1] != 0) & (s[..., :, 1:] != 0)).sum(axis=(-2, -1))    # form: the two lattice axes
    v = (s[..., :-1, :] * s[..., 1:, :]).sum(axis=(-2, -1)) / ((s[..., :-1, :] != 0) & (s[..., 1:, :] != 0)).sum(axis=(-2, -1))    # form: the two lattice axes
    return (h + v) / 2                                            # form: mean over the two declared directions


def even_cells(occ, factor):
    """occ: (L, L) bool occupancy -> (cells with an EVEN number of occupied sites, cells): the geometry report L8-d (plan 0884); it reads only which sites are listed, never a moment."""
    L = occ.shape[-1]
    n = occ.reshape(L // factor, factor, L // factor, factor).sum(axis=(1, 3))    # form: factor x factor cells
    return int(((n & 1) == 0).sum()), int(n.size)    # form: parity of a count


MAPS = {"majority3": levels, "mean3": levels_mean, "majority-occupied3": levels_occupied}
OBSERVABLES = {"majority3": g1, "mean3": g1, "majority-occupied3": g1_occupied}   # the observable each declared block map reduces to (a total table over MAPS)


def snapshot(x, name, count):
    """The level stack of ONE snapshot x (L, L): the observable of the declared map `name` on each of its `count` levels."""
    return np.array([OBSERVABLES[name](lv[None])[0] for lv in MAPS[name](x, count)])
