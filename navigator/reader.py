"""Plan 1511: the needle's reader — total maps (S1). Every parse is `input -> Value | Malformed`; no default is ever filled,
no exception is the control path. Parse A = wire messages; Parse B = config files (§11.6).
Pure: no clock, no I/O. (The server may import the Parse-B functions; this module imports nothing from environment.)"""
from dataclasses import dataclass


@dataclass(frozen=True)
class Malformed:
    field: str
    detail: str = ""


@dataclass(frozen=True)
class Declaration:
    knobs_K: tuple
    ordered_side: str
    L: int
    tau: float
    k: int
    index_unit: str
    index_kind: str
    observable: str
    raw: dict


@dataclass(frozen=True)
class Edge:
    K_c: float
    w: float
    index: int


@dataclass(frozen=True)
class NeedleConfig:
    host: str
    port: int
    needle_structure: str
    u: float
    du: float
    N: int
    n: int


@dataclass(frozen=True)
class AtConfig:
    L_blocks: int
    L: int
    L4: float
    burn: int
    seed: int
    k: int
    nlev: int
    knobs_K: tuple
    w: float
    index_unit: str
    index_kind: str


@dataclass(frozen=True)
class TauConfig:
    value: float


# ---- typed field extractors: each returns the value or a Malformed naming the field --------------------------------------
def _int(d, f, lo=None):
    v = d.get(f)
    if isinstance(v, bool) or not isinstance(v, int) or (lo is not None and v < lo):
        return Malformed(f, f"int>={lo} required")
    return v


def _real(d, f, pred=None, what="real"):
    v = d.get(f)
    if isinstance(v, bool) or not isinstance(v, (int, float)) or (pred is not None and not pred(v)):
        return Malformed(f, what)
    return float(v) if isinstance(v, float) else v


def _str(d, f):
    v = d.get(f)
    return v if isinstance(v, str) else Malformed(f, "str required")


def _pair(d, f):
    v = d.get(f)
    if (not isinstance(v, (list, tuple)) or len(v) != 2 or any(isinstance(x, bool) or not isinstance(x, (int, float)) for x in v)
            or not v[0] < v[1]):
        return Malformed(f, "[lo,hi] with lo<hi required")
    return (float(v[0]), float(v[1]))


def _first_bad(vals):
    """the first Malformed among extracted values, else None."""
    return next((v for v in vals if isinstance(v, Malformed)), None)


# ---- Parse A: wire messages ------------------------------------------------------------------------------------------------
def parse_declared(m):
    if not isinstance(m, dict):
        return Malformed("declared", "object required")
    if m.get("op") != "declared":
        return Malformed("op", "declared expected")
    knobs, side = _pair(m, "knobs_K"), _str(m, "ordered_side")
    L = _int(m, "L", 3)
    if isinstance(L, int) and L % 3:
        L = Malformed("L", "multiple of 3 required")
    tau, k = _real(m, "tau", lambda x: x > 0, "tau>0"), _int(m, "k", 1)
    unit, kind, obs = _str(m, "index_unit"), _str(m, "index_kind"), _str(m, "observable")
    vals = [knobs, side, L, tau, k, unit, kind, obs]
    bad = _first_bad(vals)
    if bad:
        return bad
    return Declaration(knobs, side, L, tau, k, unit, kind, obs, dict(m))


def parse_edge(m):
    if not isinstance(m, dict):
        return Malformed("edge", "object required")
    if m.get("op") != "edge":
        return Malformed("op", "edge expected")
    K_c = _real(m, "K_c")
    w = _real(m, "w", lambda x: x > 0, "w>0")
    i = _int(m, "index")
    bad = _first_bad([K_c, w, i])
    return bad if bad else Edge(float(K_c), float(w), i)


# ---- Parse B: config files -------------------------------------------------------------------------------------------------
def parse_needle_cfg(d):
    if not isinstance(d, dict):
        return Malformed("needle.toml", "table required")
    host = _str(d, "host")
    port = _int(d, "port", 1)
    if isinstance(port, int) and port > 65535:
        port = Malformed("port", "<=65535")
    struct = _str(d, "needle_structure")
    if isinstance(struct, str) and struct != "margin-constant-v0":
        struct = Malformed("needle_structure", "unknown structure")
    u = _real(d, "u", lambda x: x >= 0, "u>=0")
    du = _real(d, "du", lambda x: x > 0, "du>0")
    N, n = _int(d, "N", 1), _int(d, "n", 1)
    bad = _first_bad([host, port, struct, u, du, N, n])
    return bad if bad else NeedleConfig(host, port, struct, float(u), float(du), N, n)


def parse_at_cfg(d):
    if not isinstance(d, dict):
        return Malformed("at.toml", "table required")
    Lb, L4 = _int(d, "L_blocks", 1), _real(d, "L4", lambda x: x > 0, "L4>0")
    burn, seed, k, nlev = _int(d, "burn", 1), _int(d, "seed"), _int(d, "k", 1), _int(d, "nlev", 1)
    knobs, w = _pair(d, "knobs_K"), _real(d, "w", lambda x: x > 0, "w>0")
    unit, kind = _str(d, "index_unit"), _str(d, "index_kind")
    bad = _first_bad([Lb, L4, burn, seed, k, nlev, knobs, w, unit, kind])
    return bad if bad else AtConfig(Lb, 3 * Lb, float(L4), burn, seed, k, nlev, knobs, float(w), unit, kind)


def parse_tau_cfg(d):
    if not isinstance(d, dict):
        return Malformed("tau-v0.toml", "table required")
    v = _real(d, "value", lambda x: x > 0, "value>0")
    return v if isinstance(v, Malformed) else TauConfig(v)
