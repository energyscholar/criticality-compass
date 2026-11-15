"""Plan 1525: the strict parsers of the blind stage (Parse B). Every parse is `dict -> Value | navigator.reader.Malformed`;
a fault is a refusal VALUE, never an exception, and no default is ever filled. Reuses the frozen environment.config loaders."""
import math
from dataclasses import dataclass
from pathlib import Path

from environment import config as C
from navigator import reader as R

AT_KEYS = ("L_blocks", "L4", "burn", "seed", "k", "nlev", "knobs_K", "K_start", "index_unit", "index_kind")
SCORE_KEYS = ("a", "w_max")


@dataclass(frozen=True)
class BlindAtConfig:
    L_blocks: int
    L: int
    L4: float
    burn: int
    seed: int
    k: int
    nlev: int
    knobs_K: tuple
    K_start: float
    index_unit: str
    index_kind: str


@dataclass(frozen=True)
class ScoreConfig:
    a: float
    w_max: float


def _float(d, f, pred=lambda x: True, what="float"):
    v = d.get(f)
    return v if isinstance(v, float) and math.isfinite(v) and pred(v) else R.Malformed(f, what)


def _exact_keys(d, keys, name):
    """-> Malformed | None: a table with no key beyond `keys` (a missing key is refused by its typed extractor)."""
    if not isinstance(d, dict):
        return R.Malformed(name, "table required")
    extra = sorted(set(d) - set(keys))
    return R.Malformed(extra[0], "unknown key") if extra else None


def parse_blind_at_cfg(d):
    bad = _exact_keys(d, AT_KEYS, "at-blind.toml")
    if bad:
        return bad
    Lb, L4 = R._int(d, "L_blocks", 1), _float(d, "L4", lambda x: x > 0, "float>0")
    burn, seed, k, nlev = R._int(d, "burn", 0), R._int(d, "seed"), R._int(d, "k", 1), R._int(d, "nlev", 2)
    knobs, K_start = R._pair(d, "knobs_K"), _float(d, "K_start")
    unit, kind = R._str(d, "index_unit"), R._str(d, "index_kind")
    bad = R._first_bad([Lb, L4, burn, seed, k, nlev, knobs, K_start, unit, kind])
    if bad:
        return bad
    if not knobs[0] <= K_start <= knobs[1]:
        return R.Malformed("K_start", "inside knobs_K")
    return BlindAtConfig(Lb, 3 * Lb, L4, burn, seed, k, nlev, knobs, K_start, unit, kind)


def parse_score_cfg(d):
    bad = _exact_keys(d, SCORE_KEYS, "score-1525.toml")
    if bad:
        return bad
    a, w_max = _float(d, "a", lambda x: x >= 0, "float>=0"), _float(d, "w_max", lambda x: x > 0, "float>0")
    bad = R._first_bad([a, w_max])
    return bad if bad else ScoreConfig(a, w_max)


def load_blind_cfgs(env_path, at_path):
    """-> (EnvConfig, BlindAtConfig, TauConfig) | Malformed. tau-v0.toml is a SIBLING of at-blind.toml."""
    envd = C.load_toml(env_path)
    if isinstance(envd, R.Malformed):
        return envd
    env = C.parse_env_cfg(envd)
    if isinstance(env, R.Malformed):
        return env
    at_path = Path(at_path)
    atd = C.load_toml(at_path)
    if isinstance(atd, R.Malformed):
        return atd
    at = parse_blind_at_cfg(atd)
    if isinstance(at, R.Malformed):
        return at
    taud = C.load_toml(at_path.parent / "tau-v0.toml")
    if isinstance(taud, R.Malformed):
        return taud
    tau = R.parse_tau_cfg(taud)
    return tau if isinstance(tau, R.Malformed) else (env, at, tau)
