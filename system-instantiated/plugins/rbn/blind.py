"""Plan 1560: the RBN plugin's stage-3a face (contract/SCHEMA-1560.md section 5-8): the strict world parser, the truth
table, the declaration and the moment measurement. The sibling plugin.py is path-loaded and used unchanged."""
import dataclasses
import importlib.util
import math
import tomllib
from pathlib import Path
from typing import NamedTuple

import numpy as np

_spec = importlib.util.spec_from_file_location("plugin_rbn_base", Path(__file__).with_name("plugin.py"))
plugin = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(plugin)

OBSERVABLE = "moments"
ROLES = ({"name": "heal", "role": "crossing", "ordered_sign": "+"},)
P_PER_UNIT = 1000        # one tick of the bias is 1e-3
ETA_PER_UNIT = 1000000   # one tick of the noise is 1e-6
BLOCKS = 20              # jackknife blocks (declared)
NLEV = 2                 # damage at time 0 and time 1; a constant, not a world key
_COMMON = ("N", "p_ticks", "seed", "k", "knobs_K", "K_start", "index_unit", "index_kind")
WORLD_KEYS = {"critical": ("kind",) + _COMMON, "noise": ("kind", "eta_ticks") + _COMMON}


class Refused(NamedTuple):
    field: str
    detail: str


@dataclasses.dataclass(frozen=True)
class World:
    eta_ticks: int
    N: int
    p_ticks: int
    seed: int
    k: int
    knobs_K: tuple
    K_start: float
    index_unit: str
    index_kind: str
    tau: float

    @property
    def p(self):
        return self.p_ticks / P_PER_UNIT

    @property
    def eta(self):
        return self.eta_ticks / ETA_PER_UNIT


def _int(v, lo, hi=None):
    return type(v) is int and v >= lo and (hi is None or v <= hi)


def _float(v):
    return type(v) is float and math.isfinite(v)


def _knobs(v):
    return isinstance(v, list) and len(v) == 2 and all(_float(x) for x in v)


_CHECK = {
    "eta_ticks": lambda v: _int(v, 1, ETA_PER_UNIT),
    "N": lambda v: _int(v, 9) and v % 3 == 0,
    "p_ticks": lambda v: _int(v, 1, P_PER_UNIT - 1),
    "seed": lambda v: _int(v, 0),
    "k": lambda v: _int(v, 1),
    "knobs_K": _knobs,
    "K_start": _float,
    "index_unit": lambda v: isinstance(v, str) and v != "",
    "index_kind": lambda v: isinstance(v, str) and v != "",
}


def parse_world(d, taud):
    if not isinstance(d, dict):
        return Refused("world", "the world is not a table")
    kind = d.get("kind")
    if not (isinstance(kind, str) and kind in WORLD_KEYS):
        return Refused("kind", f"kind must be one of {sorted(WORLD_KEYS)}, got {kind!r}")
    keys = WORLD_KEYS[kind]
    for key in sorted(d, key=str):
        if key not in keys:
            return Refused(str(key), "unknown key for this kind of world")
    for key in keys[1:]:
        if key not in d:
            return Refused(key, "missing")
        if not _CHECK[key](d[key]):
            return Refused(key, f"ill-typed or out of range: {d[key]!r}")
    lo, hi = d["knobs_K"]
    if not 0 <= lo < hi <= 8:
        return Refused("knobs_K", "knobs must satisfy 0 <= lo < hi <= 8")
    if not lo <= d["K_start"] <= hi:
        return Refused("K_start", "K_start is outside the knobs")
    if not isinstance(taud, dict):
        return Refused("value", "tau is not a table")
    tau = taud.get("value")
    if type(tau) not in (int, float) or not math.isfinite(tau) or tau <= 0:
        return Refused("value", f"tau must be a finite number > 0, got {tau!r}")
    return World(d.get("eta_ticks", 0), d["N"], d["p_ticks"], d["seed"], d["k"], (lo, hi), d["K_start"],
                 d["index_unit"], d["index_kind"], tau)


def _read(path):
    path = Path(path)
    try:
        return tomllib.loads(path.read_bytes().decode("utf-8"))
    except (OSError, UnicodeDecodeError, tomllib.TOMLDecodeError) as e:
        return Refused(path.name, f"{type(e).__name__}: {e}")


def load_world(path):
    d = _read(path)
    if isinstance(d, Refused):
        return d
    taud = _read(Path(path).with_name("tau-v0.toml"))
    if isinstance(taud, Refused):
        return taud
    return parse_world(d, taud)


def init_blind(world):
    return plugin.init(world.N, world.K_start, world.p, world.eta, world.seed, world.knobs_K)


def declared(world):
    return {"op": "declared", "knobs_K": list(world.knobs_K), "ordered_side": plugin.ORDERED_SIDE, "L": world.N,
            "tau": world.tau, "k": world.k, "index_unit": world.index_unit, "index_kind": world.index_kind,
            "observable": OBSERVABLE, "nlev": NLEV, "roles": [dict(r) for r in ROLES], "update": plugin.UPDATE,
            "fixed": {"p": world.p}}


_LINE = {"form": "2p(1-p)K=1", "approx": "annealed"}
_TRUTH = {
    False: lambda w: {"transition": "line", "critical_set": dict(_LINE), "held": {"p": w.p},
                      "section": {"dial": "K", "K_c": plugin.critical_K(w.p)}},
    True: lambda w: {"transition": "none", "critical_set": None, "held": {"p": w.p, "eta": w.eta}, "section": None},
}


def truth(world):
    return _TRUTH[world.eta_ticks >= 1](world)


def _jackknife(S, f):
    every = np.arange(S)
    loo = np.array([f(np.setdiff1d(every, b)) for b in np.array_split(every, BLOCKS)])
    return math.sqrt((BLOCKS - 1) / BLOCKS * float(((loo - loo.mean()) ** 2).sum()))


def measure_moments(state, Ks, n_eq, S, skip):
    lo, hi = state.knobs_K
    if not all(lo <= K <= hi for K in Ks):
        return None
    heal, heal_err = [], []
    for K in Ks:
        plugin.set(state, K, state.p)
        plugin.step(state, n_eq)
        H = np.empty(S)
        for i in range(S):
            plugin.step(state, skip - 1)
            H[i] = plugin.sample(state)

        def f(idx):
            return 1.0 - H[idx].mean()
        heal.append([0.0, float(f(np.arange(S)))])
        heal_err.append([0.0, _jackknife(S, f)])
    return {"heal": heal, "heal_err": heal_err}
