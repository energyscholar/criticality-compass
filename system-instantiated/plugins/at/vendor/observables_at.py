"""observables_at.py - plan 0924 phase 1 (Tier E): the per-snapshot observables of studies/NAV-AT/grid.py, BYTE-IDENTICAL, computed for a
whole block of snapshots at once. The frozen path is, per snapshot: bonds(s), bonds(s*t) (np.roll products), and g1 of every block3 level of
s and of s*t. Nothing in it draws a random number, so it can run after the sampler on stored snapshots.
Why the result is the same float, not just close: every quantity is an INTEGER sum of +-1 products (bonds), or such a sum divided by the
frozen mean's own count (g1: np.mean of exact integers = sum / count, one true_divide); the block map is the frozen scale.block3 (integer
sum, sign). Only the representation changes: int8 arrays, no float copy of the lattice, one pass per level for the whole block.
Periodic SIMULATED system; the analysis declares no ring (bonds wrap, g1 is the frozen open-pair form)."""
import numpy as np
from scale import levels

AXES = (-2, -1)  # form: the two lattice axes


def open_sums(x):
    """(n, l, l) +-1 -> the integer sums (h, v) of the open-pair products along the two axes, each (n,): the numerators of the frozen g1's means."""
    h = (x[..., :, :-1] * x[..., :, 1:]).sum(axis=AXES, dtype=int)  # form: open horizontal pairs
    v = (x[..., :-1, :] * x[..., 1:, :]).sum(axis=AXES, dtype=int)  # form: open vertical pairs
    return h, v


def bond_sum(x, h, v):
    """(n, L, L) +-1 and its open sums -> (n,) periodic bond sum = frozen bonds(x): the open pairs plus the wrapped last-to-first pair of each axis (integer, exact)."""
    return h + v + (x[..., :, -1] * x[..., :, 0]).sum(axis=-1, dtype=int) + (x[..., -1, :] * x[..., 0, :]).sum(axis=-1, dtype=int)  # form: wrap pairs


def g1_sums(h, v, l):
    """frozen flow.g1 from the open sums of an (l, l) level: (h + v) / 2 with h, v the frozen means = exact integer sum / count."""
    return (h / (l * (l - 1)) + v / (l * (l - 1))) / 2  # form: mean over the two declared directions, each mean = sum / count


def level_sums(x, nlev):
    """the open sums of each level of the frozen block map of x, finest first: [(h, v, l), ...]."""
    return [open_sums(b) + (b.shape[-1],) for b in levels(x, nlev)]  # form: one entry per declared level


def observables(S, T, nlev):
    """(S, T): (n, L, L) int8 snapshots -> (E2, E4, Gs, Gp) exactly as grid.point builds them (float64)."""
    P = S * T
    ls, lp = level_sums(S, nlev), level_sums(P, nlev)
    hT, vT = open_sums(T)
    E2 = (bond_sum(S, ls[0][0], ls[0][1]) + bond_sum(T, hT, vT)).astype(float)
    E4 = bond_sum(P, lp[0][0], lp[0][1]).astype(float)
    Gs = np.stack([g1_sums(h, v, l) for h, v, l in ls], 1)  # form: one column per declared level
    Gp = np.stack([g1_sums(h, v, l) for h, v, l in lp], 1)  # form: one column per declared level
    return E2, E4, Gs, Gp
