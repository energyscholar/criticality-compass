"""Plan 1546: the Ising plugin's stage-3a face (contract/SCHEMA-1546.md section 5-7): the strict world parser, the truth table,
the declaration and the moment measurement. The sibling plugin.py is path-loaded and used unchanged."""
import dataclasses
import importlib.util
import math
import tomllib
from pathlib import Path
from typing import NamedTuple

import numpy as np

_spec = importlib.util.spec_from_file_location("plugin_ising_base", Path(__file__).with_name("plugin.py"))
plugin = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(plugin)

OBSERVABLE = "moments"
ROLES = ({"name": "U4", "role": "crossing", "ordered_sign": "+"}, {"name": "chi", "role": "peak"})
H_PER_UNIT = 100000   # one tick of the field is 1e-5
BLOCKS = 20           # jackknife blocks (declared)
_COMMON = ("L", "burn", "seed", "k", "nlev", "knobs_K", "K_start", "index_unit", "index_kind")
WORLD_KEYS = {"critical": ("kind",) + _COMMON, "field": ("kind", "h_ticks") + _COMMON}


class Refused(NamedTuple):
    field: str
    detail: str


@dataclasses.dataclass(frozen=True)
class World:
    h_ticks: int
    L: int
    burn: int
    seed: int
    k: int
    nlev: int
    knobs_K: tuple
    K_start: float
    index_unit: str
    index_kind: str
    tau: float

    @property
    def h(self):
        return self.h_ticks / H_PER_UNIT


def _int(v, lo):
    return type(v) is int and v >= lo


def _float(v):
    return type(v) is float and math.isfinite(v)


def _knobs(v):
    return isinstance(v, list) and len(v) == 2 and all(_float(x) for x in v) and v[0] < v[1]


_CHECK = {
    "h_ticks": lambda v: _int(v, 1),
    "L": lambda v: _int(v, 3) and v % 2 == 1,
    "burn": lambda v: _int(v, 0),
    "seed": lambda v: _int(v, 0),
    "k": lambda v: _int(v, 1),
    "nlev": lambda v: _int(v, 2),
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
    if d["L"] % 3 ** (d["nlev"] - 1) != 0:
        return Refused("L", f"L must be a multiple of 3^(nlev-1) = {3 ** (d['nlev'] - 1)}")
    lo, hi = d["knobs_K"]
    if lo < 0:
        return Refused("knobs_K", "the low knob is negative")
    if not lo <= d["K_start"] <= hi:
        return Refused("K_start", "K_start is outside the knobs")
    if not isinstance(taud, dict):
        return Refused("value", "tau is not a table")
    tau = taud.get("value")
    if type(tau) not in (int, float) or not math.isfinite(tau) or tau <= 0:
        return Refused("value", f"tau must be a finite number > 0, got {tau!r}")
    return World(d.get("h_ticks", 0), d["L"], d["burn"], d["seed"], d["k"], d["nlev"], (lo, hi), d["K_start"],
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
    return plugin.init(world.L, world.K_start, world.h, world.burn, world.seed, world.nlev, world.knobs_K)


def declared(world):
    return {"op": "declared", "knobs_K": list(world.knobs_K), "ordered_side": plugin.ORDERED_SIDE, "L": world.L,
            "tau": world.tau, "k": world.k, "index_unit": world.index_unit, "index_kind": world.index_kind,
            "observable": OBSERVABLE, "nlev": world.nlev, "roles": [dict(r) for r in ROLES], "update": plugin.UPDATE}


_TRUTH = {
    False: lambda w: {"transition": "continuous", "K_c": plugin.critical_K(), "held": {"h": w.h}},
    True: lambda w: {"transition": "none", "K_c": None, "held": {"h": w.h}},
}


def truth(world):
    return _TRUTH[world.h_ticks >= 1](world)


def _jackknife(S, f):
    every = np.arange(S)
    loo = np.array([f(np.setdiff1d(every, b)) for b in np.array_split(every, BLOCKS)])
    return math.sqrt((BLOCKS - 1) / BLOCKS * float(((loo - loo.mean()) ** 2).sum()))


def measure_moments(state, Ks, n_eq, S, skip):
    lo, hi = state.knobs_K
    if not all(lo <= K <= hi for K in Ks):
        return None
    N = state.L * state.L
    nlev = state.nlev
    chi, chi_err, U4, U4_err = [], [], [], []
    for K in Ks:
        plugin.set(state, K)
        plugin.step(state, n_eq)
        M = np.empty(S)
        A = np.empty((S, nlev))
        Q = np.empty((S, nlev))
        for i in range(S):
            plugin.step(state, skip)
            _, msum, a, q = plugin.observe(state.s, nlev)
            M[i] = msum / N
            A[i], Q[i] = a, q

        def f_chi(idx):
            return N * ((M[idx] ** 2).mean() - np.abs(M[idx]).mean() ** 2)

        def f_u(idx, l):
            return 1.0 - Q[idx, l].mean() / (3.0 * A[idx, l].mean() ** 2)
        every = np.arange(S)
        chi.append(float(f_chi(every)))
        chi_err.append(_jackknife(S, f_chi))
        U4.append([float(f_u(every, l)) for l in range(nlev)])
        U4_err.append([_jackknife(S, lambda idx, l=l: f_u(idx, l)) for l in range(nlev)])
    return {"chi": chi, "chi_err": chi_err, "U4": U4, "U4_err": U4_err}
