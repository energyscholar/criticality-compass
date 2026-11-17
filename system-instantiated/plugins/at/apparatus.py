"""Plan 1545, amended by plan 1553 (contract/SCHEMA-1553.md: the dial is a delay line, environment/dial.py): the AT plugin's APPARATUS side (contract/SCHEMA-1545.md sections 3, 5 and 7).
The sibling blind.py is path-loaded and reused unchanged (and through it the frozen plugin.py and the vendored sampler).
This module adds only the engine of the emulated apparatus: one lattice, one RNG stream, a dial held as an integer tick,
and a hidden parameter that is a pure function of the sweep index (environment/drift.py). Every sweep is
`state.current_K`, `state.L4`, then the frozen `plugin.step(state, 1)`."""
import importlib.util
import math
from pathlib import Path

import numpy as np

from environment import dial as DL
from environment import drift as DR
from environment.apparatus_config import tick_value

_spec = importlib.util.spec_from_file_location("blind_at_for_apparatus", Path(__file__).with_name("blind.py"))
blind = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(blind)

plugin = blind.plugin
lattice_at = blind.lattice_at
observables_at = blind.observables_at

PARAMS = ("K",)
HIDDEN = {"L4": (0.0, math.log(3) / 4)}   # (lo exclusive, hi inclusive)
ORDERED_SIDE = {"K": "+"}                  # larger K is the ordered side
ROLES = [{"name": "D", "role": "crossing", "ordered_sign": "+"}, {"name": "C", "role": "peak"}]
# the Engine face (plan 1569, contract/SCHEMA-1569.md section 2): what the apparatus host used to hard-code for AT
DYNAMICS = "algorithmic (Swendsen-Wang)"   # the wire's `clock`
S_MIN = 40                                  # the fewest samples a reading may take
EXTRA_KEYS = ()                             # AT has no world keys of its own


def parse_extra(d):
    return dict(d)


def transition(world):
    return "continuous"


class Engine:
    S_MIN = S_MIN

    def __init__(self, world):
        self.w = world
        self.track = DL.start(world.lag, [d.start for d in world.dials])
        K0, L4_0 = self.K(DL.at(self.track, 0)), self.hidden_at(0)["L4"]
        rng = np.random.default_rng(world.seed)
        S, T = lattice_at.at_sw(world.L, K0, L4_0, 1, 0, world.burn, rng)
        self.state = plugin.State(S[0], T[0], rng, K0, 0, L4_0, world.nlev, world.L, (K0, K0), None)

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

    def hidden_at(self, index):
        dr = self.w.drift
        return {k: v + (DR.offset(dr, index) if k == dr.target else 0.0) for k, v in self.w.hidden.items()}

    def K_c(self, index):
        return float(lattice_at.self_dual_K(self.hidden_at(index)["L4"]))

    def sweep(self):
        st = self.state
        st.current_K = self.K(DL.at(self.track, st.index))
        st.L4 = self.hidden_at(st.index)["L4"]
        plugin.step(st, 1)

    def point(self, cur, n_eq, S, skip):
        """one reading: the position `cur` is commanded now and arrives `lag` sweeps later; every sweep runs at the
        position in force at its index. n_eq settle sweeps, then S samples of `skip` sweeps each."""
        st, w = self.state, self.w
        first = st.index
        self.track = DL.command(self.track, first, cur)
        for _ in range(n_eq):
            self.sweep()
        sampling = st.index
        E2, G = np.empty(S), np.empty((S, w.nlev))
        for i in range(S):
            for _ in range(skip):
                self.sweep()
            e2, _, gs, _ = observables_at.observables(st.s[None, :, :], st.t[None, :, :], w.nlev)
            E2[i], G[i] = e2[0], gs[0]
        N = w.L * w.L
        jk1 = blind._jackknife(S, lambda idx: G[idx, 1].mean())
        jk0 = blind._jackknife(S, lambda idx: G[idx, 0].mean())
        return ({"pos": list(cur), "window": [sampling + skip, st.index],
                 "values": {"D": float(G[:, 1].mean()) - float(G[:, 0].mean()), "C": float(E2.var() / N)},
                 "errors": {"D": math.sqrt(jk1 ** 2 + jk0 ** 2), "C": blind._jackknife(S, lambda idx: E2[idx].var() / N)}},
                (first, sampling, st.index))

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
