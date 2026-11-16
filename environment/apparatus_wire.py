"""Plan 1545: the apparatus face's total op -> reply map (contract/SCHEMA-1545.md section 4). Exactly four ops; everything else
is `nev` at the current index. A request is validated WHOLE (keys, types, positions, the horizon) before anything runs: there
is no clamp, no partial move and no partial scan. The reply builders receive only the public declaration and the measured
values; the truth row goes to a list that only the server's exit path writes out."""
from dataclasses import dataclass

WIRE = "compass-apparatus/1"
CLOCK = "algorithmic (Swendsen-Wang)"
TIME_LABEL = "lag and drift are in algorithmic (Swendsen-Wang) time"


@dataclass(frozen=True)
class Public:
    """what the needle may be told: built from the world's public keys only."""
    dials: tuple
    fixed: dict
    ordered_side: dict
    roles: list
    horizon: int
    lag: int
    tau: float
    k: int
    L: int
    index_unit: str
    index_kind: str


def public(world, tau, plug):
    dials = tuple({"name": d.name, "lo": d.lo, "hi": d.hi, "T": d.T, "max_nudge": d.max_nudge} for d in world.dials)
    return Public(dials, dict(world.fixed), dict(plug.ORDERED_SIDE), list(plug.ROLES), world.horizon, world.lag, tau, world.k,
                  world.L, world.index_unit, world.index_kind)


def nev(index):
    return {"op": "nev", "index": index}


def declared(pub, pos, index):
    return {"op": "declared", "wire": WIRE, "dials": [dict(d) for d in pub.dials], "pos": list(pos), "fixed": dict(pub.fixed),
            "ordered_side": dict(pub.ordered_side), "roles": [dict(r) for r in pub.roles], "index": index, "horizon": pub.horizon,
            "lag": pub.lag, "tau": pub.tau, "k": pub.k, "L": pub.L, "index_unit": pub.index_unit, "index_kind": pub.index_kind,
            "clock": CLOCK}


def reading(points, index):
    return {"op": "reading", "pos": [p["pos"] for p in points], "window": [p["window"] for p in points],
            "values": {"D": [p["D"] for p in points], "C": [p["C"] for p in points]},
            "errors": {"D": [p["D_err"] for p in points], "C": [p["C_err"] for p in points]}, "index": index}


def _int(v):
    return isinstance(v, int) and not isinstance(v, bool)


def _legal(pub, pos):
    """a position is a list of one int tick per dial, each inside 0..T."""
    return (isinstance(pos, list) and len(pos) == len(pub.dials)
            and all(_int(t) and 0 <= t <= d["T"] for d, t in zip(pub.dials, pos)))


def _read_positions(pub, pos, msg):
    return [list(pos)]


def _nudge_positions(pub, pos, msg):
    d = msg["d"]
    if not (isinstance(d, list) and len(d) == len(pub.dials) and all(_int(x) for x in d)):
        return None
    if not all(abs(x) <= dl["max_nudge"] for x, dl in zip(d, pub.dials)):
        return None
    new = [p + x for p, x in zip(pos, d)]
    return [new] if _legal(pub, new) else None


def _scan_positions(pub, pos, msg):
    ticks = msg["ticks"]
    return [list(t) for t in ticks] if isinstance(ticks, list) and ticks and all(_legal(pub, t) for t in ticks) else None


def _declare(engine, pub, rows, msg):
    return declared(pub, engine.pos, engine.index)


def _measured(positions_of, lagged):
    """lagged: a commanded move pays the lag, so n_eq must cover it; a read moves nothing."""
    def run(engine, pub, rows, msg):
        n_eq, S, skip = msg["n_eq"], msg["S"], msg["skip"]
        lag = pub.lag if lagged else 0
        if not (_int(n_eq) and n_eq >= lag and _int(S) and S >= 40 and _int(skip) and skip >= 1):
            return nev(engine.index)
        positions = positions_of(pub, engine.pos, msg)
        if positions is None or engine.index + len(positions) * (n_eq + S * skip) > pub.horizon:
            return nev(engine.index)
        points = engine.run(positions, n_eq, S, skip, lag)
        rows.append(engine.truth_row(len(rows) + 1, msg["op"], points))
        return reading(points, engine.index)
    return run


_COMMON = ("n_eq", "S", "skip")
_TABLE = {
    "declare": (frozenset({"op"}), _declare),
    "read": (frozenset({"op", *_COMMON}), _measured(_read_positions, False)),
    "nudge": (frozenset({"op", "d", *_COMMON}), _measured(_nudge_positions, True)),
    "scan": (frozenset({"op", "ticks", *_COMMON}), _measured(_scan_positions, True)),
}
OPS = tuple(_TABLE)


def handle(engine, pub, rows, msg):
    """-> (reply, note_or_None). Appends one truth row to `rows` per accepted read, nudge or scan."""
    if not isinstance(msg, dict):
        return nev(engine.index), "non-object line"
    op = msg.get("op")
    entry = _TABLE.get(op) if isinstance(op, str) else None
    if entry is None or set(msg) != entry[0]:
        return nev(engine.index), f"refused: op={str(op)[:40]!r}"
    reply = entry[1](engine, pub, rows, msg)
    return reply, (f"refused: {op}" if reply["op"] == "nev" else None)
