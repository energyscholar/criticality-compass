"""Plan 1552: the needle `hold-pair-v1` (contract/SCHEMA-1552.md). It drops (knowing only what the apparatus declares), finds the
crossing of the observable with a coarse and then a fine tick scan, walks the dial there and holds: it reads a pair of ticks,
one `g` below its centre and one `g` above, and moves the centre by the nine-cell table of navigator.holdtab. It opens its
settings and its map and nothing else, and it imports nothing that could name the apparatus's own state.
Entry: python -m navigator.hold --needle <settings> --port <P> --drop <name> --map <path>
Exit: 0 = a stream with an outcome; 2 = RefusedToStart (one stderr line, empty stdout, no map); 1 = nothing listening."""
import argparse
import json
import socket
import sys
import tomllib

from navigator import holdrep as HR
from navigator import holdtab as HT
from navigator import steer as ST

WIRE = "compass-apparatus/1"
DECLARED = {"op", "wire", "dials", "pos", "fixed", "ordered_side", "roles", "index", "horizon", "lag", "tau", "k", "L",
            "index_unit", "index_kind", "clock"}
M_KEYS = ("observable", "node", "relation", "edge", "direction", "provenance", "transform", "rho_base", "chi_0")
M_FIXED = {"relation": "path", "transform": "none", "rho_base": "not-declared", "chi_0": "not-declared"}
SIGNS = ("+", "-")


# ---------------------------------------------------------------- the settings (parse B): thirteen keys, no default
def _int(lo):
    return lambda v: type(v) is int and v >= lo


def _text(v):
    return type(v) is str and v != ""


def _table(spec):
    return lambda v: type(v) is dict and set(v) == set(spec) and all(spec[k](v[k]) for k in spec)


def _steps(v):
    return (type(v) is list and bool(v) and all(_int(2)(x) and x % 2 == 0 for x in v)
            and all(b < a and a % b == 0 for a, b in zip(v, v[1:])))


CHECKS = (
    ("needle_structure", lambda v: v == HT.NEEDLE),
    ("ops", lambda v: v in ([*HT.OPS["OFF"]], [*HT.OPS["ON"]])),
    ("g", _int(1)), ("step", _int(1)), ("sigma", lambda v: type(v) is int and v == 0), ("n_eq", _int(0)), ("S", _int(40)),
    ("skip", _int(1)), ("z", lambda v: type(v) is float and v > 0),
    ("ignite", _table({"steps": _steps, "S": _int(40), "margin": _int(0), "n_eq": _int(0)})),
    ("approach", _table({"S": _int(40), "n_eq": _int(0)})),
    ("lost", _int(1)),
    ("M", _table({k: (lambda v, k=k: v == M_FIXED[k]) if k in M_FIXED else _text for k in M_KEYS})),
)


def refusal_b(raw):
    """the field of the first refusal, or None. A missing or unknown key first (in sorted order), then the table's order."""
    off = sorted(set(raw) ^ {k for k, _ in CHECKS})
    return off[0] if off else next((k for k, ok in CHECKS if not ok(raw[k])), None)


# ---------------------------------------------------------------- the door (parse A): refuses after `declare`
def _num(v):
    return type(v) in (int, float)


def _dial_ok(dl, pos, d):
    return (type(dl) is dict and set(dl) == {"name", "lo", "hi", "T", "max_nudge"} and type(dl["name"]) is str
            and _num(dl["lo"]) and _num(dl["hi"]) and dl["lo"] < dl["hi"] and _int(1)(dl["T"]) and _int(1)(dl["max_nudge"])
            and _int(0)(pos) and pos <= dl["T"] and all(_int(0)(d[k]) for k in ("index", "lag", "horizon", "k"))
            and _num(d["tau"]) and d["tau"] >= 0)


def _roles_ok(roles):
    names = [r.get("name") for r in roles if type(r) is dict] if type(roles) is list else []
    return (type(roles) is list and len(names) == len(roles) and all(type(n) is str for n in names) and len(set(names)) == len(names)
            and sum(1 for r in roles if r.get("role") == "crossing") == 1)


def refusal_a(d, cfg):
    """the field of the first refusal of a declaration, or None."""
    shaped = type(d) is dict and set(d) == DECLARED and d["op"] == "declared"
    one = shaped and type(d["dials"]) is list and len(d["dials"]) == 1 and type(d["pos"]) is list and len(d["pos"]) == 1
    dl = d["dials"][0] if one else None
    numbers = one and _dial_ok(dl, d["pos"][0], d)
    roles = numbers and _roles_ok(d["roles"])
    cross = [r for r in d["roles"] if r.get("role") == "crossing"][0] if roles else None
    side = roles and type(d["ordered_side"]) is dict and d["ordered_side"].get(dl["name"]) in SIGNS and cross.get("ordered_sign") in SIGNS
    checks = ((shaped, "declared"), (shaped and d["wire"] == WIRE, "wire"), (one, "dials"), (numbers, "numbers"), (roles, "roles"),
              (roles and cross["name"] == cfg["M"]["observable"], "M"), (side, "ordered_side"),
              (side and 2 * cfg["g"] + cfg["step"] <= dl["max_nudge"] and 2 * cfg["g"] <= dl["T"], "g"),
              (side and dl["T"] % cfg["ignite"]["steps"][0] == 0, "ignite"))
    return ([field for ok, field in checks if not ok] + [None])[0]


def refused(field, parse):
    print(f"RefusedToStart field={field} parse={parse}", file=sys.stderr)
    return 2


# ---------------------------------------------------------------- the drop
class Drop:
    def __init__(self, sock, rf, cfg, d, name, mapf):
        dl = d["dials"][0]
        self.sock, self.rf, self.cfg, self.name, self.mapf = sock, rf, cfg, name, mapf
        self.dial = {"name": dl["name"], "lo": dl["lo"], "hi": dl["hi"], "T": dl["T"]}
        self.max_nudge, self.lag, self.horizon, self.skip = dl["max_nudge"], d["lag"], d["horizon"], cfg["skip"]
        self.roles = sorted(r["name"] for r in d["roles"])
        self.obs = cfg["M"]["observable"]
        self.sign = [r for r in d["roles"] if r["name"] == self.obs][0]["ordered_sign"]
        self.side = d["ordered_side"][dl["name"]]
        self.view = HT.ORIENT[(self.side, self.sign)]
        self.mode = ST.mode_of(cfg["ops"])
        self.index, self.pos = d["index"], d["pos"][0]
        self.cmd, self.since = self.pos, self.index - self.lag      # the dial starts settled
        self.kstate, self.seq, self.stepno, self.segment, self.centre = (), 0, 0, 0, None
        self.decl = d

    # -- the wire
    def ask(self, msg):
        try:
            self.sock.sendall((json.dumps(msg) + "\n").encode())
            line = self.rf.readline()
            return json.loads(line) if line else None
        except (OSError, ValueError):
            return None

    def is_reading(self, r, ticks):
        m, roles = len(ticks), set(self.roles)
        table = lambda t: type(t) is dict and set(t) == roles and all(type(c) is list and len(c) == m and all(_num(x) for x in c) for c in t.values())
        win = lambda w: type(w) is list and len(w) == 2 and all(type(x) is int for x in w) and w[0] <= w[1]
        return (type(r) is dict and set(r) == {"op", "pos", "window", "values", "errors", "index"} and r["op"] == "reading"
                and r["pos"] == [[t] for t in ticks] and all(type(p[0]) is int for p in r["pos"])
                and type(r["window"]) is list and len(r["window"]) == m and all(win(w) for w in r["window"])
                and table(r["values"]) and table(r["errors"]) and r["index"] == r["window"][-1][1])

    def take(self, msg, ticks, n_eq, S):
        """one call -> its readings, or None when the reply is not a reading at exactly `ticks` (SCHEMA 4.5)."""
        r = self.ask({**msg, "n_eq": n_eq, "S": S, "skip": self.skip})
        if not self.is_reading(r, ticks):
            return None
        cls = HT.classes(r["values"][self.obs], r["errors"][self.obs], self.cfg["z"])
        out, at = [], self.index
        for j, t in enumerate(ticks):
            self.cmd, self.since = HT.commanded(self.cmd, self.since, t, at)
            a, b = r["window"][j]
            ok = HT.settled(self.since, self.lag, a, self.skip)
            A, B, self.kstate = HT.kernel_next(self.kstate, r["values"][self.obs][j])
            out.append({"tick": t, "window": [a, b], "values": {k: r["values"][k][j] for k in self.roles},
                        "errors": {k: r["errors"][k][j] for k in self.roles}, "cls": cls[j], "settled": ok, "A": A, "B": B})
            at = b
        self.index, self.pos = at, ticks[-1]
        return out

    def scan(self, ticks, n_eq, S):
        return self.take({"op": "scan", "ticks": [[t] for t in ticks]}, ticks, n_eq, S)

    def nudge(self, tick, n_eq, S):
        return self.take({"op": "nudge", "d": [tick - self.pos]}, [tick], n_eq, S)

    # -- the records
    def head(self):
        """the map's head for this drop, as the drop stands before its first message."""
        d, c = self.decl, self.cfg
        clock = {k: d[k] for k in ("index_unit", "index_kind", "clock", "lag", "k", "tau")}
        rule = {"observable": self.obs, "z": c["z"], "ordered_sign": self.sign, "ordered_side": self.side}
        n_eq = {"ignite": c["ignite"]["n_eq"], "approach": c["approach"]["n_eq"], "hold": c["n_eq"]}
        return HR.head(self.name, self.dial, {"tick": self.pos, "index": self.index}, clock, n_eq, self.skip, self.roles, rule, c["M"])

    def record(self, phase, rs, kind, reason, ticks, extra, evaluated):
        """the places and the step record of the step now ending, built and not written."""
        n = self.stepno + 1
        places = [HR.place(self.name, self.seq + j, self.dial, r, {"step": n, "phase": phase, "kind": kind}, self.sign) for j, r in enumerate(rs)]
        payload = {**HR.common(self.segment, rs), **extra} if rs else {}
        return places, HR.step(n, phase, self.index, evaluated, HR.verdict(kind, reason, self.dial["name"], ticks), payload)

    def finish(self, phase, rs, kind, reason, ticks, extra, evaluated=True):
        """places first (flushed), then the step. A step with no reading is `unread`'s kind and carries what it has."""
        places, rec = self.record(phase, rs, kind, reason, ticks, extra, evaluated)
        for p in places:
            self.mapf.write(json.dumps(p) + "\n")
        self.mapf.flush()
        emit(rec)
        self.seq += len(places)
        self.stepno += 1
        return kind

    def unread(self, phase, rs, readings, n_eq, S):
        kind = HT.unread(self.index, HT.cost(readings, n_eq, S, self.skip), self.horizon)
        return self.finish(phase, rs, kind, ST.NOT_EVALUATED, None, {}, False)

    # -- the three phases: each returns the kind of its last step
    def ignite(self):
        c = self.cfg["ignite"]
        self.segment += 1
        lo, hi = 0, self.dial["T"]
        for rnd, width in enumerate(c["steps"], 1):
            ticks = HT.grid(lo, hi, width, c["margin"], self.dial["T"])
            rs = self.scan(ticks, c["n_eq"], c["S"])
            if rs is None:
                return self.unread("ignite", [], len(ticks), c["n_eq"], c["S"])
            cls = [r["cls"] for r in rs]
            br = HT.bracket(ticks, cls, self.view)
            kind = HT.ignite_kind(br, self.cfg["g"], self.dial["T"])
            lo_, hi_ = br or (None, None)
            self.finish("ignite", rs, kind, "|".join(cls), None, {"round": rnd, "lo": lo_, "hi": hi_})
            if kind != "bracketed":
                return kind
            lo, hi = br
        self.centre = (lo + hi) // 2
        return "bracketed"

    def approach(self):
        c = self.cfg["approach"]
        for d in HT.legs(self.centre - self.cfg["g"] - self.pos, self.max_nudge):
            rs = self.nudge(self.pos + d, c["n_eq"], c["S"])
            if rs is None:
                return self.unread("approach", [], 1, c["n_eq"], c["S"])
            self.finish("approach", rs, "moving", "stride", d, {"d": d})
        return "moving"

    def hold(self):
        cfg, g, n, streak = self.cfg, self.cfg["g"], 0, 0
        while True:
            n += 1
            lo_t, hi_t = self.centre - g, self.centre + g
            rs = []
            for probe in HT.PLAN[self.mode](lo_t, hi_t):
                got = self.scan(probe, cfg["n_eq"], cfg["S"]) if self.mode == "OFF" else self.nudge(probe[0], cfg["n_eq"], cfg["S"])
                if got is None:
                    return self.unread("hold", rs, len(probe), cfg["n_eq"], cfg["S"])
                rs += got
            cls = [r["cls"] for r in rs]
            kind, ticks = HT.hold_kind(cls, self.view, self.mode, self.centre, cfg["step"], g, self.dial["T"])
            streak = (streak + 1) * (kind == "no-signal")
            extra = {"n": n, "centre": self.centre, "setpoint": self.centre + cfg["sigma"] * g, "bracket": [lo_t, hi_t], "streak": streak}
            self.finish("hold", rs, kind, "|".join(cls), ticks, extra)
            if kind in HT.LAST_KINDS:
                return kind
            self.centre += ticks
            if HT.APPLIED[self.mode] and streak >= cfg["lost"]:
                return "lost"

    def run(self):
        """segments of ignite, approach (ON only) and hold, until a step with no reading or a range kind ends the stream."""
        phases = {"ON": (self.ignite, self.approach, self.hold), "OFF": (self.ignite, self.hold)}[self.mode]
        while True:
            for phase in phases:
                kind = phase()
                if kind in HT.LAST_KINDS:
                    return kind
                if kind == "no-bracket":
                    break


def emit(rec):
    print(json.dumps(rec), flush=True)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--needle", required=True)
    ap.add_argument("--port", required=True, type=int)
    ap.add_argument("--drop", required=True)
    ap.add_argument("--map", required=True)
    a = ap.parse_args(argv)
    try:
        with open(a.needle, "rb") as f:
            cfg = tomllib.load(f)
    except (OSError, tomllib.TOMLDecodeError):
        return refused("needle", "B")
    bad = refusal_b(cfg)
    if bad:
        return refused(bad, "B")
    try:
        sock = socket.create_connection(("127.0.0.1", a.port))
    except OSError as e:
        print(f"Unreachable 127.0.0.1:{a.port} ({type(e).__name__})", file=sys.stderr)
        return 1
    rf = sock.makefile("r", encoding="utf-8", newline="\n")
    try:
        sock.sendall((json.dumps({"op": "declare"}) + "\n").encode())
        try:
            d = json.loads(rf.readline())
        except (OSError, ValueError):
            d = None
        bad = refusal_a(d, cfg)
        if bad:
            return refused(bad, "A")
        with open(a.map, "a", encoding="utf-8") as mapf:
            drop = Drop(sock, rf, cfg, d, a.drop, mapf)
            mapf.write(json.dumps(drop.head()) + "\n")
            mapf.flush()
            emit(HR.start(cfg, cfg["ops"], drop.dial["name"], {k: v for k, v in d.items() if k != "op"}))
            last = drop.run()
            emit(HR.outcome(HT.outcome(last), last, drop.stepno))
    finally:
        rf.close()
        sock.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
