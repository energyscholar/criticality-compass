"""Plan 1552: the reader of a hold report and of its map (contract/SCHEMA-1552.md section 8).

Pure and total: it opens nothing, prints nothing and never raises; every input is a Stream, a Map or an Unreadable. A report is
read by REPLAY: the needle's own phases (navigator.hold.Drop) are run over a wire that serves exactly the readings the report
holds (window, values, errors), and every record the replay builds from them must be the record the report carries, key for key
and type for type. So every tick, class, settled mark, kind, reason, move, centre, streak, segment, round, bracket and kernel
value is the needle's table's, recomputed. A map is read against its own head: each place's class, settled mark, state and kernel
values are recomputed from its readings, the places before it and the head."""
import json
from dataclasses import dataclass

from navigator import hold as HD
from navigator import holdrep as HR
from navigator import holdtab as HT
from navigator import steer as ST
from needlestream import read as NS

HEAD_KEYS = frozenset(("rec", "map", "drop", "needle", "dial", "start", "clock", "n_eq", "skip", "roles", "sign_rule", "M"))
PLACE_KEYS = frozenset(("rec", "drop", "seq", "dial", "tick", "value", "index", "window", "readings", "class", "settled", "state", "call", "kernel"))
INF = float("inf")


@dataclass(frozen=True)
class Stream:
    start: dict
    steps: tuple
    outcome: object
    mode: str
    dial: dict
    orient: str


@dataclass(frozen=True)
class Drop:
    head: dict
    places: tuple


@dataclass(frozen=True)
class Map:
    drops: tuple


class _Refused(Exception):
    """internal: a text that cannot be read; the readers turn it into an Unreadable value."""


class _Stop(Exception):
    """internal: the report holds no further step: the replay has caught up with it."""


def _no(why):
    raise _Refused(why)


def _same(a, b):
    """equal in value AND in type, key for key (1, 1.0 and True are three different records)."""
    return json.dumps(a, sort_keys=True) == json.dumps(b, sort_keys=True)


def _int(v, lo=0):
    return type(v) is int and v >= lo


def _num(v):
    return type(v) in (int, float) and v == v and v not in (INF, -INF)


def _keys(obj, keys, name):
    if type(obj) is not dict or set(obj) != set(keys):
        _no(f"{name} does not hold exactly its keys")
    return obj


def _lines(text):
    if type(text) is not str:
        _no("the input is not text")
    if text and not text.endswith("\n"):
        _no("the last line has no line end")
    out = []
    for n, line in enumerate(text.split("\n")[:-1], 1):
        obj = json.loads(line)
        if type(obj) is not dict:
            _no(f"line {n} is not a JSON object")
        out.append(obj)
    return out


# ---------------------------------------------------------------- the report: a replay of the needle
class _Replay(HD.Drop):
    """the needle's own drop, over a wire that is the report: it serves the next reported readings and builds, never writes."""

    def __init__(self, cfg, d, name, steps):
        super().__init__(None, None, cfg, d, name, None)
        self.steps, self.i, self.queue = steps, 0, None
        self.entries = [self.head()]

    def _readings(self):
        """the readings the report holds for the step the replay is in; _Stop when it holds no such step."""
        if self.queue is None:
            if self.i >= len(self.steps):
                raise _Stop
            rec = self.steps[self.i]
            p = rec[HT.PHASE_PAYLOAD[rec["phase"]]]
            self.queue = [(p["window"][j], {k: p["values"][k][j] for k in self.roles}, {k: p["errors"][k][j] for k in self.roles})
                          for j in range(len(p.get("window", ())))]
        return self.queue

    def ask(self, msg):
        q = self._readings()
        ticks = [t[0] for t in msg["ticks"]] if msg["op"] == "scan" else [self.pos + msg["d"][0]]
        if len(q) < len(ticks):
            return None                                      # the report holds no such reading: the wire did not answer
        got, self.queue[:] = q[:len(ticks)], q[len(ticks):]
        at = self.index
        for w, _, _ in got:
            if not (type(w) is list and len(w) == 2 and all(type(x) is int for x in w) and at < w[0] <= w[1]):
                _no(f"step {self.stepno + 1}: a window does not move forward from the index before it")
            at = w[1]
        return {"op": "reading", "pos": [[t] for t in ticks], "window": [g[0] for g in got],
                "values": {k: [g[1][k] for g in got] for k in self.roles}, "errors": {k: [g[2][k] for g in got] for k in self.roles},
                "index": got[-1][0][1]}

    def finish(self, phase, rs, kind, reason, ticks, extra, evaluated=True):
        places, rec = self.record(phase, rs, kind, reason, ticks, extra, evaluated)
        if not _same(rec, self.steps[self.i]):
            _no(f"step {rec['step']} is not the step the needle's tables give for the readings it reports")
        self.entries += places
        self.seq += len(places)
        self.stepno += 1
        self.i += 1
        self.queue = None
        return kind


def _declaration(start):
    """the declaration the start record carries, rebuilt: the declared slots, the other declared keys, the envelope."""
    fields = {s: v["declared"] for s, v in start["belief"].items() if v != ST.UNKNOWN}
    return {"op": "declared", **fields, **start["declared_other"]}


def _setup(start):
    """-> (settings, declaration) of a start record that is exactly the one the needle writes for them."""
    cfg = start["settings"]
    bad = HD.refusal_b(cfg)
    if bad:
        _no(f"the settings are refused at {bad} (parse B)")
    d = _declaration(start)
    bad = HD.refusal_a(d, cfg)
    if bad:
        _no(f"the declaration is refused at {bad} (parse A)")
    if not _same(start, HR.start(cfg, cfg["ops"], d["dials"][0]["name"], {k: v for k, v in d.items() if k != "op"})):
        _no("the start record is not the one these settings and this declaration give")
    return cfg, d


def _walk(start, steps, name):
    """-> (the replay, the last kind or None while the report has not ended)."""
    cfg, d = _setup(start)
    w = _Replay(cfg, d, name, steps)
    try:
        last = w.run()
    except _Stop:
        last = None
    if w.i != len(steps):
        _no("steps follow the step that ends the stream")
    return w, last


def _read(text):
    recs = _lines(text)
    if not recs or recs[0].get("rec") != "start":
        _no("the first record is not a start record")
    body = recs[1:]
    n = 0
    while n < len(body) and body[n].get("rec") == "step":
        n += 1
    steps, tail = body[:n], body[n:]
    if len(tail) > 1 or (tail and tail[0].get("rec") != "outcome"):
        _no("records follow the steps that are not one outcome record")
    w, last = _walk(recs[0], steps, "")
    if tail and (last is None or not _same(tail[0], HR.outcome(HT.outcome(last), last, w.stepno))):
        _no("the outcome is not the fold of the last step")
    dl = w.decl["dials"][0]
    return Stream(recs[0], tuple(steps), tail[0] if tail else NS.PENDING, w.mode, dl, "+" if w.side == w.sign else "-")


def read(text):
    """text -> Stream | Unreadable. Never raises, opens nothing."""
    try:
        return _read(text)
    except _Refused as e:
        return NS.Unreadable(str(e))
    except (ValueError, RecursionError, TypeError, KeyError, AttributeError, IndexError, ArithmeticError) as e:
        return NS.Unreadable(f"not readable ({type(e).__name__})")


def places(stream, drop_name):
    """the head and the places a report implies, as the needle wrote them."""
    return _walk(stream.start, list(stream.steps), drop_name)[0].entries


def check(stream, drop):
    """None when the drop is exactly the map its report implies, else a reason."""
    want, have = places(stream, drop.head["drop"]), [drop.head, *drop.places]
    at = next((i for i, (a, b) in enumerate(zip(want, have)) if not _same(a, b)), min(len(want), len(have)))
    return None if _same(want, have) else f"the map is not its report's: the entries differ from entry {at}"


def trail(stream):
    """one point per evaluated hold step: belief (centre), call (kind, ticks) and bracket against the wire's index."""
    return tuple({"step": r["step"], "index": r["index"], "segment": r["pair"]["segment"], "centre": r["pair"]["centre"],
                  "bracket": r["pair"]["bracket"], "kind": r["verdict"][0]["kind"], "ticks": r["verdict"][0]["ticks"]}
                 for r in stream.steps if r["phase"] == "hold" and r["evaluated"])


def sigma(stream):
    """the setpoint offset in units of g and in ticks (g is the half-width) and in the dial's value."""
    cfg, dl = stream.start["settings"], stream.dial
    ticks = HT.offset(cfg["sigma"], cfg["g"])
    return {"g": cfg["sigma"], "ticks": ticks, "value": ticks * (dl["hi"] - dl["lo"]) / dl["T"], "ticks_per_g": cfg["g"]}


def settle(stream):
    """the settle times the needle chose, against the declared lag and the relaxation floor lag + k*tau."""
    cfg, bel = stream.start["settings"], stream.start["belief"]
    lag = stream.start["declared_other"]["lag"]
    floor = lag + bel["k"]["declared"] * bel["tau"]["declared"]
    n_eq = {p: HT.SETTLE[p](cfg)["n_eq"] for p in (*HT.PAYLOAD, *HT.PARKS[cfg["needle_structure"]])}
    return {"lag": lag, "floor": floor, "n_eq": n_eq, "mid_move": {p: n < lag for p, n in n_eq.items()},
            "relaxed": {p: n >= floor for p, n in n_eq.items()}}


def deadband(stream):
    """plan 1558: the needle's MEASURED band, in ticks, from its own evaluated hold pairs: per pair z * rms(errors) / (|D_hi - D_lo| / 2g).
    A flat pair has no finite band: it is counted in n and flat, never dropped. -> {n, flat, median, p95} (None when no pair is finite)."""
    cfg = stream.start["settings"]
    obs = cfg["M"]["observable"]
    pairs = [r["pair"] for r in stream.steps if r["phase"] == "hold" and r["evaluated"]]
    slopes = [abs(p["values"][obs][1] - p["values"][obs][0]) / (2 * cfg["g"]) for p in pairs]
    bands = sorted(cfg["z"] * ((p["errors"][obs][0] ** 2 + p["errors"][obs][1] ** 2) / 2) ** 0.5 / m for p, m in zip(pairs, slopes) if m != 0)
    at = lambda q: bands[min(len(bands) - 1, int(q * len(bands)))] if bands else None
    return {"n": len(pairs), "flat": slopes.count(0), "median": at(0.5), "p95": at(0.95)}


# ---------------------------------------------------------------- the map
def _head(o):
    _keys(o, HEAD_KEYS, "the head")
    roles = o["roles"]
    if o["needle"] not in HT.SHAPES or type(o["drop"]) is not str or not o["drop"]:
        _no("the head is not a drop of this needle")
    dial = _keys(o["dial"], ("name", "lo", "hi", "T"), "head.dial")
    if not (type(dial["name"]) is str and _num(dial["lo"]) and _num(dial["hi"]) and dial["lo"] < dial["hi"] and _int(dial["T"], 1)):
        _no("head.dial is not a name, lo < hi and an int T >= 1")
    start = _keys(o["start"], ("tick", "index"), "head.start")
    if not (_int(start["tick"]) and start["tick"] <= dial["T"] and _int(start["index"])):
        _no("head.start is not a tick on the dial and an index")
    clock = _keys(o["clock"], ("index_unit", "index_kind", "clock", "lag", "k", "tau"), "head.clock")
    if not (all(type(clock[k]) is str for k in ("index_unit", "index_kind", "clock")) and _int(clock["lag"]) and _int(clock["k"])
            and _num(clock["tau"]) and clock["tau"] >= 0):
        _no("head.clock is not units, a lag, k and tau")
    n_eq = _keys(o["n_eq"], HT.PHASES[o["needle"]], "head.n_eq")
    if not all(_int(v) for v in n_eq.values()) or not _int(o["skip"], 1):
        _no("head.n_eq or head.skip is not a settle time or a skip")
    if not (type(roles) is list and roles and roles == sorted(set(roles)) and all(type(r) is str for r in roles)):
        _no("head.roles is not a sorted list of distinct names")
    rule = _keys(o["sign_rule"], ("observable", "z", "ordered_sign", "ordered_side"), "head.sign_rule")
    if not (rule["observable"] in roles and type(rule["z"]) is float and rule["z"] > 0
            and rule["ordered_sign"] in HD.SIGNS and rule["ordered_side"] in HD.SIGNS):
        _no("head.sign_rule is not an observable, a z and two signs")
    if not (dict(HD.CHECKS)["M"](o["M"]) and o["M"]["observable"] == rule["observable"]):
        _no("head.M is not the declaration of the observable")
    return o


def _places(head, recs):
    """the places of one drop, each recomputed from its numbers, the places before it and the head."""
    dial, start, clock, rule = head["dial"], head["start"], head["clock"], head["sign_rule"]
    cmd, since, at, kstate, obs = start["tick"], start["index"] - clock["lag"], start["index"], (), rule["observable"]
    for seq, p in enumerate(recs):
        if p.get("state") not in HT.STATES:                  # the vocabulary of a version: first, before any other content
            _no(f"unknown state {p.get('state')}")
        _keys(p, PLACE_KEYS, f"place {seq}")
        t, w, rd = p["tick"], p["window"], p["readings"]
        if p["drop"] != head["drop"] or not _int(p["seq"]) or p["seq"] != seq or p["dial"] != dial["name"]:
            _no(f"place {seq} is not this drop's place {seq} of this dial")
        if not (_int(t) and t <= dial["T"] and _same(p["value"], dial["lo"] + t * (dial["hi"] - dial["lo"]) / dial["T"])):
            _no(f"place {seq}: the tick is not on the dial or the value is not the tick's")
        if not (type(w) is list and len(w) == 2 and all(_int(x) for x in w) and at < w[0] <= w[1] and _int(p["index"]) and p["index"] == w[1]):
            _no(f"place {seq}: the time index is not the window's end, or the window does not move forward")
        _keys(rd, head["roles"], f"place {seq} readings")
        for v in rd.values():
            if not (_keys(v, ("value", "error"), f"place {seq} reading") and _num(v["value"]) and _num(v["error"])):
                _no(f"place {seq}: a reading is not a number and its error")
        cls = HT.classes([rd[obs]["value"]], [rd[obs]["error"]], rule["z"])[0]
        cmd, since = HT.commanded(cmd, since, t, at)
        ok = HT.settled(since, clock["lag"], w[0], head["skip"])
        a, b, kstate = HT.kernel_next(kstate, rd[obs]["value"])
        call = _keys(p["call"], ("step", "phase", "kind"), f"place {seq} call")
        if not (_int(call["step"], 1) and call["phase"] in HT.PHASES[head["needle"]] and type(call["kind"]) is str):
            _no(f"place {seq}: the call is not a step, a phase and a kind")
        if not (p["class"] == cls and type(p["settled"]) is bool and p["settled"] == ok and p["state"] == HT.state(cls, rule["ordered_sign"], ok)):
            _no(f"place {seq}: the class, the settled mark or the state does not follow from its readings")
        if not _same(p["kernel"], {"A": a, "B": b, "R": HT.R_NOT_EVALUATED}):
            _no(f"place {seq}: the kernel values are not the path's")
        at = w[1]
    return tuple(recs)


def _read_map(text):
    groups, names = [], set()
    for r in _lines(text):
        kind = r.get("rec")
        if kind == "head":
            if r.get("map") != HT.MAP:                       # the version is the vocabulary: first, before any other content
                _no(f"unknown map version {r.get('map')}")
            if r.get("drop") in names:
                _no("two drops of one name")
            names.add(r.get("drop"))
            groups.append((_head(r), []))
        elif kind == "place":
            if not groups:
                _no("a place with no head")
            groups[-1][1].append(r)
        else:
            _no("a record that is neither a head nor a place")
    return Map(tuple(Drop(h, _places(h, ps)) for h, ps in groups))


def read_map(text):
    """text -> Map | Unreadable. Zero or more drops; the empty text is the empty map."""
    try:
        return _read_map(text)
    except _Refused as e:
        return NS.Unreadable(str(e))
    except (ValueError, RecursionError, TypeError, KeyError, AttributeError, IndexError, ArithmeticError) as e:
        return NS.Unreadable(f"not readable ({type(e).__name__})")


def state_at(drop, tick):
    """the state of the latest place at this tick; `unknown` when the needle never read it."""
    return next((p["state"] for p in reversed(drop.places) if p["tick"] == tick), HT.UNVISITED)
