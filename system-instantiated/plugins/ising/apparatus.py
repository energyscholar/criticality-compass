"""Plan 1569 (contract/SCHEMA-1569.md section 4): the Ising plugin's APPARATUS side, behind the Engine face of section 2.
The sibling blind.py is path-loaded and reused unchanged (and through it the frozen plugin.py). This module adds only the engine of
the emulated apparatus: one lattice, one RNG stream, a dial held as an integer tick behind the delay line (environment/dial.py), and
a hidden shift dK of the coupling that is a pure function of the sweep index (environment/drift.py). Every sweep is
`state.K = dial + dK(index)`, then the frozen `plugin.step(state, 1)`."""
import importlib.util
from pathlib import Path

import numpy as np

from common.jackknife import jackknife
from environment import dial as DL
from environment import drift as DR
from environment.apparatus_config import tick_value
from navigator import reader as R

_spec = importlib.util.spec_from_file_location("blind_ising_for_apparatus", Path(__file__).with_name("blind.py"))
blind = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(blind)

plugin = blind.plugin

PARAMS = ("K",)
HIDDEN = {"dK": (-0.1, 0.1)}   # (lo exclusive, hi inclusive)
ORDERED_SIDE = {"K": "+"}      # larger K is the ordered side
ROLES = [{"name": "dU4", "role": "crossing", "ordered_sign": "+"}, {"name": "chi", "role": "peak"}]
DYNAMICS = "algorithmic (Swendsen-Wang)"
S_MIN = 40
EXTRA_KEYS = ("kind", "h_ticks")

_KINDS = {"critical": ("kind",), "field": ("kind", "h_ticks")}      # a kind names its own key set
_TRANSITION = {"critical": "continuous", "field": "none"}
_FIELD = {"critical": lambda extra: 0.0, "field": lambda extra: extra["h_ticks"] / blind.H_PER_UNIT}
_K_C = {"continuous": lambda eng, index: plugin.critical_K() - eng.dK(index), "none": lambda eng, index: None}


def parse_extra(d):
    """d restricted to EXTRA_KEYS -> the plugin's own world keys | Malformed (the door: a kind, and only that kind's keys)."""
    kind = d.get("kind")
    if not (isinstance(kind, str) and kind in _KINDS):
        return R.Malformed("kind", f"one of {tuple(_KINDS)}")
    stray = sorted(set(d) - set(_KINDS[kind]))
    if stray:
        return R.Malformed(stray[0], f"not a key of a {kind} world")
    got = [R._int(d, key, 1) for key in _KINDS[kind][1:]]
    bad = R._first_bad(got)
    return bad if bad else dict(d)


def transition(world):
    return _TRANSITION[world.extra["kind"]]


class Engine:
    S_MIN = S_MIN

    def __init__(self, world):
        self.w = world
        self.transition = transition(world)
        self.h = _FIELD[world.extra["kind"]](world.extra)
        self.track = DL.start(world.lag, [d.start for d in world.dials])
        self.state = plugin.init(world.L, self.lattice_K(0), self.h, world.burn, world.seed, world.nlev, (-np.inf, np.inf))
        # plugin.init draws its own generator from the seed: one lattice, one RNG stream

    @property
    def pos(self):
        return DL.commanded(self.track)

    @property
    def index(self):
        return self.state.index

    def K(self, pos):
        v = dict(self.w.fixed)
        for d, t in zip(self.w.dials, pos):
            v[d.name] = tick_value(d.lo, d.hi, d.T, t)
        return v["K"]

    def dK(self, index):
        dr = self.w.drift
        return self.w.hidden["dK"] + DR.offset(dr, index)

    def lattice_K(self, index):
        return self.K(DL.at(self.track, index)) + self.dK(index)

    def K_c(self, index):
        v = _K_C[self.transition](self, index)
        return None if v is None else float(v)

    def sweep(self):
        st = self.state
        st.K = self.lattice_K(st.index)
        plugin.step(st, 1)

    def point(self, cur, n_eq, S, skip):
        """one reading: the position `cur` is commanded now and arrives `lag` sweeps later; every sweep runs at the position in force
        at its index. n_eq settle sweeps, then S samples of `skip` sweeps each."""
        st, w = self.state, self.w
        first = st.index
        self.track = DL.command(self.track, first, cur)
        for _ in range(n_eq):
            self.sweep()
        sampling = st.index
        N, nlev = w.L * w.L, w.nlev
        M, A, Q = np.empty(S), np.empty((S, nlev)), np.empty((S, nlev))
        for i in range(S):
            for _ in range(skip):
                self.sweep()
            _, msum, a, q = plugin.observe(st.s, nlev)
            M[i] = msum / N
            A[i], Q[i] = a, q

        def u(idx, level):
            return 1.0 - Q[idx, level].mean() / (3.0 * A[idx, level].mean() ** 2)

        def dU4(idx):
            return u(idx, nlev - 1) - u(idx, nlev - 2)

        def chi(idx):
            return N * ((M[idx] ** 2).mean() - np.abs(M[idx]).mean() ** 2)
        every = np.arange(S)
        stats = {"dU4": dU4, "chi": chi}
        return ({"pos": list(cur), "window": [sampling + skip, st.index],
                 "values": {name: float(f(every)) for name, f in stats.items()},
                 "errors": {name: jackknife(S, f) for name, f in stats.items()}}, (first, sampling, st.index))

    def run(self, positions, n_eq, S, skip):
        done = [self.point(cur, n_eq, S, skip) for cur in positions]
        return [p for p, _ in done], [sp for _, sp in done]

    def truth_row(self, call, op, points, spans):
        """the truth of an accepted call: for the run directory only, never for the wire."""
        return {"call": call, "op": op, "index": self.index, "K_c": self.K_c(self.index), "pos": list(self.pos),
                "actual": [tick_value(d.lo, d.hi, d.T, t) for d, t in zip(self.w.dials, DL.at(self.track, self.index))],
                "points": [{"pos": p["pos"], "window": p["window"], "K_c": [self.K_c(p["window"][0]), self.K_c(p["window"][1])],
                            "sampling": sampling, "dial": DL.runs(self.track, first, end)}
                           for p, (first, sampling, end) in zip(points, spans)]}
