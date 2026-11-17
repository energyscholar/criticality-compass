"""Plan 1560: the random Boolean network core (contract/SCHEMA-1560.md section 2-4). Wire-free: it knows no file, no
wire, no truth. A quenched network, coupled across both dials K (mean in-degree) and p (table bias). One probe is
one Derrida damage measurement on a fresh uniform state; replica noise runs on the same code path at every eta."""
import math
from dataclasses import dataclass

import numpy as np

UPDATE = "uniform-probe"
ORDERED_SIDE = "-K"
DIALS = ("K", "p")


@dataclass(frozen=True)
class Net:
    v: object        # (N,) in-degree offsets
    inputs: object   # (N, KMAX) distinct input indices per node
    w: object        # (N, 2**KMAX) table weights


@dataclass
class State:
    net: Net
    rng: object
    K: float
    p: float
    eta: float
    index: int
    N: int
    knobs_K: tuple


def critical_K(p):
    return 1.0 / (2.0 * p * (1.0 - p))


def kmax(knobs_K):
    return math.ceil(knobs_K[1])


def draw_net(N, KMAX, rng):
    """The draw order is the contract: v, then each node's inputs in node order, then w."""
    v = rng.random(N)
    inputs = np.array([rng.choice(N, KMAX, replace=False) for _ in range(N)])
    w = rng.random((N, 2 ** KMAX))
    return Net(v, inputs, w)


def degrees(net, K):
    return np.floor(K + net.v).astype(int)


def outputs(net, x, K, p):
    """One synchronous update; returns a NEW bool array."""
    k = degrees(net, K)
    kmx = net.inputs.shape[1]
    weight = np.left_shift(1, np.arange(kmx))
    read = x[net.inputs].astype(np.int64) * weight * (np.arange(kmx)[None, :] < k[:, None])
    row = read.sum(axis=1)
    return net.w[np.arange(len(k)), row] < p


def probe(net, K, p, eta, rng):
    """One Derrida probe: the damage h1 after one synchronous step from a single flip on a fresh uniform state."""
    N = len(net.v)
    x = rng.random(N) < 0.5
    j = int(rng.integers(N))
    ua, ba = rng.random(N), rng.random(N) < 0.5
    ub, bb = rng.random(N), rng.random(N) < 0.5
    y = x.copy()
    y[j] = ~y[j]
    fx = np.where(ua < eta, ba, outputs(net, x, K, p))
    fy = np.where(ub < eta, bb, outputs(net, y, K, p))
    return int((fx != fy).sum())


def init(N, K, p, eta, seed, knobs_K):
    rng = np.random.default_rng(seed)
    net = draw_net(N, kmax(knobs_K), rng)
    return State(net, rng, K, p, eta, 0, N, tuple(knobs_K))


def set(state, K, p):
    """Both dials, or None outside the knobs (inclusive) or outside 0 < p < 1: no clamp, state untouched, no draw."""
    lo, hi = state.knobs_K
    if not (lo <= K <= hi and 0.0 < p < 1.0):
        return None
    state.K = K
    state.p = p
    return state


def step(state, n):
    for _ in range(n):
        probe(state.net, state.K, state.p, state.eta, state.rng)
    state.index += n
    return state


def sample(state):
    h = probe(state.net, state.K, state.p, state.eta, state.rng)
    state.index += 1
    return h
