"""Plan 1546: the 2-D Ising core (contract/SCHEMA-1546.md section 2-4). Wire-free: it knows no file, no wire, no truth.
-H/kT = K * sum_<ij> s_i s_j + h * sum_i s_i on an L x L torus. One update: Swendsen-Wang with a ghost spin, one code path
for every h (at h = 0 the ghost bond probability is exactly 0)."""
import math
from dataclasses import dataclass

import numpy as np
from scipy.sparse import coo_matrix
from scipy.sparse.csgraph import connected_components

UPDATE = "swendsen-wang"
ORDERED_SIDE = "+K"
DIALS = ("K",)


@dataclass
class State:
    s: object
    rng: object
    K: float
    h: float
    index: int
    L: int
    nlev: int
    knobs_K: tuple


def critical_K():
    return math.log(1.0 + math.sqrt(2.0)) / 2.0


def sweep(s, K, h, rng):
    """One Swendsen-Wang update; the order of the random draws is the contract. Returns a NEW array."""
    L = s.shape[0]
    N = L * L
    u_r = rng.random(N).reshape(L, L)
    u_d = rng.random(N).reshape(L, L)
    u_g = rng.random(N).reshape(L, L)
    p = 1.0 - math.exp(-2.0 * K)
    pg = 1.0 - math.exp(-2.0 * h)
    site = np.arange(N).reshape(L, L)
    right = np.roll(site, -1, axis=1)
    down = np.roll(site, -1, axis=0)
    br = (s == np.roll(s, -1, axis=1)) & (u_r < p)
    bd = (s == np.roll(s, -1, axis=0)) & (u_d < p)
    bg = (s == 1) & (u_g < pg)
    src = np.concatenate([site[br], site[bd], site[bg]])
    dst = np.concatenate([right[br], down[bd], np.full(int(bg.sum()), N)])
    graph = coo_matrix((np.ones(len(src), dtype=np.int8), (src, dst)), shape=(N + 1, N + 1))
    ncl, lab = connected_components(graph, directed=False)
    u_c = rng.random(ncl)
    flip = (u_c[lab[:N]] < 0.5) & (lab[:N] != lab[N])
    return np.where(flip.reshape(L, L), -s, s)


def init(L, K, h, burn, seed, nlev, knobs_K):
    rng = np.random.default_rng(seed)
    s = rng.choice(np.array([-1, 1]), size=(L, L))
    for _ in range(burn):
        s = sweep(s, K, h, rng)
    return State(s, rng, K, h, 0, L, nlev, tuple(knobs_K))


def set(state, K):
    """The dial, or None outside the knobs (inclusive): no clamp, state untouched. Does not step."""
    lo, hi = state.knobs_K
    if not lo <= K <= hi:
        return None
    state.K = K
    return state


def step(state, n):
    for _ in range(n):
        state.s = sweep(state.s, state.K, state.h, state.rng)
    state.index += n
    return state


def observe(s, nlev):
    """-> (bonds, msum, a, q); levels finest first, the last level is the whole lattice."""
    L = s.shape[0]
    bonds = int((s * np.roll(s, -1, axis=1)).sum() + (s * np.roll(s, -1, axis=0)).sum())
    msum = int(s.sum())
    a, q = [], []
    for l in range(nlev):
        g = 3 ** (nlev - 1 - l)
        b = L // g
        m = s.reshape(g, b, g, b).sum(axis=(1, 3)).astype(float) / (b * b)
        a.append(float((m ** 2).mean()))
        q.append(float((m ** 4).mean()))
    return bonds, msum, a, q
