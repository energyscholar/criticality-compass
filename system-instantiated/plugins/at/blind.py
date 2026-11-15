"""Plan 1525: the AT plugin's BLIND start and its moment measurement (contract/SCHEMA-1525.md).
The sibling plugin.py is path-loaded and reused unchanged (State, set, step, the vendored sampler). This module adds only:
  init_blind(cfg)      burn at the declared K_start, never at K_c (the lattice is not told the truth)
  truth(state)         the declared critical coupling, for the server to write to its run artifact — never to the wire
  measure_moments(...) the declared computation: per K, equilibrate, then S samples, moments with a 20-block jackknife."""
import importlib.util
import math
from pathlib import Path

import numpy as np

_spec = importlib.util.spec_from_file_location("plugin_at_base", Path(__file__).with_name("plugin.py"))
plugin = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(plugin)

lattice_at = plugin.lattice_at
observables_at = plugin.observables_at

ORDERED_SIDE = plugin.ORDERED_SIDE
OBSERVABLE = "moments"
BLOCKS = 20  # jackknife blocks (declared)


def init_blind(cfg):
    """cfg: a validated BlindAtConfig. -> plugin.State burned at K_start."""
    rng = np.random.default_rng(cfg.seed)
    S, T = lattice_at.at_sw(cfg.L, cfg.K_start, cfg.L4, 1, 0, cfg.burn, rng)
    return plugin.State(S[0], T[0], rng, cfg.K_start, 0, cfg.L4, cfg.nlev, cfg.L, tuple(cfg.knobs_K), None)


def truth(state):
    return {"K_c": float(lattice_at.self_dual_K(state.L4))}


def _jackknife(S, f):
    """sqrt((B-1)/B * sum_b (loo_b - mean(loo))^2) with loo_b = f(all samples outside block b)."""
    every = np.arange(S)
    loo = np.array([f(np.setdiff1d(every, b)) for b in np.array_split(every, BLOCKS)])
    return math.sqrt((BLOCKS - 1) / BLOCKS * float(((loo - loo.mean()) ** 2).sum()))


def measure_moments(state, Ks, n_eq, S, skip):
    """Ks already validated inside the knob range by the wire. -> {"C","C_err","Gs","Gs_err"} of Python floats."""
    N = state.L * state.L
    C, C_err, Gs, Gs_err = [], [], [], []
    for K in Ks:
        plugin.set(state, K)
        plugin.step(state, n_eq)
        E2 = np.empty(S)
        G = np.empty((S, state.nlev))
        for i in range(S):
            plugin.step(state, skip)
            e2, _, gs, _ = observables_at.observables(state.s[None, :, :], state.t[None, :, :], state.nlev)
            E2[i], G[i] = e2[0], gs[0]
        C.append(float(E2.var() / N))
        C_err.append(_jackknife(S, lambda idx: E2[idx].var() / N))
        Gs.append([float(G[:, l].mean()) for l in range(state.nlev)])
        Gs_err.append([_jackknife(S, lambda idx, l=l: G[idx, l].mean()) for l in range(state.nlev)])
    return {"C": C, "C_err": C_err, "Gs": Gs, "Gs_err": Gs_err}
