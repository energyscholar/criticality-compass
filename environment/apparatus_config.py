"""Plan 1545: the strict parser of an apparatus world (Parse B; contract/SCHEMA-1545.md section 2) and the tick grid.
Every parse is `dict -> Value | navigator.reader.Malformed`; a fault is a refusal VALUE, no default is ever filled.
The plugin supplies PARAMS and the HIDDEN domains, so this module names no parameter."""
import importlib.util
import math
from dataclasses import dataclass
from pathlib import Path

from environment import config as C
from environment import drift as DR
from environment import world_clock as WC
from navigator import reader as R

TOP_KEYS = ("L_blocks", "burn", "seed", "k", "nlev", "index_unit", "index_kind", "lag", "horizon", "dials", "fixed", "hidden", "drift", "world_clock")   # plan 1565: `world_clock` may be absent (absent is WC.ABSENT, paused)
DIAL_KEYS = ("name", "lo", "hi", "T", "max_nudge", "start")


@dataclass(frozen=True)
class Dial:
    name: str
    lo: float
    hi: float
    T: int
    max_nudge: int
    start: int


@dataclass(frozen=True)
class World:
    L_blocks: int
    L: int
    burn: int
    seed: int
    k: int
    nlev: int
    index_unit: str
    index_kind: str
    lag: int
    horizon: int
    dials: tuple
    fixed: dict
    hidden: dict
    drift: DR.Drift
    world_clock: WC.WorldClock


def tick_value(lo, hi, T, t):
    """the dial value of tick t: the only dial values that exist."""
    return lo + t * (hi - lo) / T


def _unknown(d, keys, name):
    if not isinstance(d, dict):
        return R.Malformed(name, "table required")
    extra = sorted(set(d) - set(keys))
    return R.Malformed(extra[0], "unknown key") if extra else None


def parse_dial(d, params):
    bad = _unknown(d, DIAL_KEYS, "dials")
    if bad:
        return bad
    name = R._str(d, "name")
    if not isinstance(name, R.Malformed) and name not in params:
        name = R.Malformed("name", f"one of {tuple(params)}")
    lo, hi = DR.float_field(d, "lo"), DR.float_field(d, "hi")
    T = R._int(d, "T", 1)
    bad = R._first_bad([name, lo, hi, T])
    if bad:
        return bad
    if not lo < hi:
        return R.Malformed("hi", "hi > lo")
    nudge = R._int(d, "max_nudge", 1)
    if not isinstance(nudge, R.Malformed) and nudge > T:
        nudge = R.Malformed("max_nudge", "max_nudge <= T")
    start = R._int(d, "start", 0)
    if not isinstance(start, R.Malformed) and start > T:
        start = R.Malformed("start", "start <= T")
    bad = R._first_bad([nudge, start])
    return bad if bad else Dial(name, lo, hi, T, nudge, start)


def parse_dials(v, params):
    if not isinstance(v, list) or len(v) > 1:
        return R.Malformed("dials", "list of at most one dial (two dials are stage 5b)")
    dials = [parse_dial(x, params) for x in v]
    bad = R._first_bad(dials)
    return bad if bad else tuple(dials)


def _table_of_floats(v, keys, name, domain=None):
    """a table whose keys are exactly `keys`, each a finite float (inside `domain[key] = (lo exclusive, hi inclusive]` when given)."""
    if not isinstance(v, dict) or set(v) != set(keys):
        return R.Malformed(name, f"keys exactly {tuple(keys)}")
    for key, x in v.items():
        if not (isinstance(x, float) and math.isfinite(x)):
            return R.Malformed(name, f"{key}: finite float required")
        if domain is not None and not domain[key][0] < x <= domain[key][1]:
            return R.Malformed(name, f"{key}: inside {domain[key]}")
    return dict(v)


def parse_world(d, params, hidden_domain):
    """params: the plugin's PARAMS; hidden_domain: {name: (lo exclusive, hi inclusive)} -> World | Malformed."""
    bad = _unknown(d, TOP_KEYS, "at-apparatus.toml")
    if bad:
        return bad
    Lb, burn, seed = R._int(d, "L_blocks", 1), R._int(d, "burn", 0), R._int(d, "seed")
    k, nlev = R._int(d, "k", 1), R._int(d, "nlev", 2)
    unit, kind = R._str(d, "index_unit"), R._str(d, "index_kind")
    lag, horizon = R._int(d, "lag", 0), R._int(d, "horizon", 1)
    bad = R._first_bad([Lb, burn, seed, k, nlev, unit, kind, lag, horizon])
    if bad:
        return bad
    dials = parse_dials(d.get("dials"), params)
    if isinstance(dials, R.Malformed):
        return dials
    fixed_keys = [p for p in params if p not in {x.name for x in dials}]
    fixed = _table_of_floats(d.get("fixed"), fixed_keys, "fixed")
    if isinstance(fixed, R.Malformed):
        return fixed
    hidden = _table_of_floats(d.get("hidden"), tuple(hidden_domain), "hidden", hidden_domain)
    if isinstance(hidden, R.Malformed):
        return hidden
    drift = DR.parse_drift(d.get("drift"), tuple(hidden_domain))
    if isinstance(drift, R.Malformed):
        return drift
    b_lo, b_hi = DR.bounds(drift, horizon)
    lo, hi = hidden_domain[drift.target]
    if not (lo < hidden[drift.target] + b_lo and hidden[drift.target] + b_hi <= hi):
        return R.Malformed("drift", f"the drift leaves the domain of {drift.target} within the horizon")
    world_clock = WC.parse_world_clock(d.get("world_clock", WC.ABSENT))
    if isinstance(world_clock, R.Malformed):
        return world_clock
    return World(Lb, 3 * Lb, burn, seed, k, nlev, unit, kind, lag, horizon, dials, fixed, hidden, drift, world_clock)


def load_apparatus(system):
    """the plugin's apparatus side, loaded by path (system-instantiated has a hyphen), as blind_server loads blind.py."""
    f = C.plugin_dir(system) / "apparatus.py"
    spec = importlib.util.spec_from_file_location(f"apparatus_{system}", f)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def load_apparatus_cfgs(env_path, at_path):
    """-> (EnvConfig, World, TauConfig, plugin module) | Malformed. tau-v0.toml is a SIBLING of the world file."""
    envd = C.load_toml(env_path)
    if isinstance(envd, R.Malformed):
        return envd
    env = C.parse_env_cfg(envd)
    if isinstance(env, R.Malformed):
        return env
    plug = load_apparatus(env.system)
    at_path = Path(at_path)
    atd = C.load_toml(at_path)
    if isinstance(atd, R.Malformed):
        return atd
    world = parse_world(atd, plug.PARAMS, plug.HIDDEN)
    if isinstance(world, R.Malformed):
        return world
    taud = C.load_toml(at_path.parent / "tau-v0.toml")
    if isinstance(taud, R.Malformed):
        return taud
    tau = R.parse_tau_cfg(taud)
    return tau if isinstance(tau, R.Malformed) else (env, world, tau, plug)
