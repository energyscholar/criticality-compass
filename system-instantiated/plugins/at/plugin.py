"""Plan 1511: the AT plugin — the five-function plugin contract (§11.3) over the frozen vendored sampler.
init(at_cfg) -> State; edge(State) -> {K_c,w}; set(State,K) -> State|None; step(State,n) -> State; sense(State) -> float.
State is single-replica (s,t,rng) held between calls; `set` never re-burns; `step` runs n sweeps in-process.
Sampler wiring: lattice_at._step / at_sw / self_dual_K and observables_at.observables, vendored verbatim (never modified)."""
import os
import sys
from dataclasses import dataclass

import numpy as np

_VENDOR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "vendor")
if _VENDOR not in sys.path:
    sys.path.insert(0, _VENDOR)

import lattice_at  # noqa: E402  (resolved from vendor/)
import observables_at  # noqa: E402

# The AT system's own constants (properties of the system, not tunable config) — emitted in the `declared` message.
ORDERED_SIDE = "+K"
OBSERVABLE = "E2"


@dataclass
class State:
    s: np.ndarray
    t: np.ndarray
    rng: np.random.Generator
    current_K: float
    index: int
    L4: float
    nlev: int
    L: int
    knobs_K: tuple
    w: float


def init(at_cfg):
    """at_cfg: a validated navigator.reader.AtConfig. Burn once at construction; a live world has no re-burn."""
    rng = np.random.default_rng(at_cfg.seed)
    K_c = float(lattice_at.self_dual_K(at_cfg.L4))
    S, T = lattice_at.at_sw(at_cfg.L, K_c, at_cfg.L4, 1, 0, at_cfg.burn, rng)
    return State(S[0], T[0], rng, K_c, 0, at_cfg.L4, at_cfg.nlev, at_cfg.L, tuple(at_cfg.knobs_K), at_cfg.w)


def edge(state):
    return {"K_c": float(lattice_at.self_dual_K(state.L4)), "w": state.w}


def set(state, K):  # noqa: A001 — the contract's name
    lo, hi = state.knobs_K
    if not lo <= K <= hi:
        return None
    state.current_K = K
    return state


def step(state, n):
    s, t = state.s, state.t
    for _ in range(n):
        s, t = lattice_at._step(s, t, state.current_K, state.L4, state.rng)
    state.s, state.t = s, t
    state.index += n
    return state


def sense(state):
    E2, _, _, _ = observables_at.observables(state.s[None, :, :], state.t[None, :, :], state.nlev)
    return float(E2[0])
