"""oracle.py - plan 1282 P3: the ONE total Oracle sum type the frozen navigate walk reads through. Declared (primary: start declared from physics, a
Detector-free order field, navigator triggered by hand) | LiveDetector (convenience: a total stub until P2f lands). The walk (cc/navigate.py) is untouched and
identical for both constructors. STRUCTURE, NOT CONTROL: MOVE_LIVE sends a MID cell to "unresolved" (never "stop"), so a false location from an interior node
is unreachable; location is only the adjacent-ends BRACKET, DK wide by construction of the node grid."""
import hashlib
import json
import math
import os
import sys
import time
from dataclasses import dataclass
from pathlib import Path

import navigate
import schema
from navigate import Reading
from sign import Sign, sign

S = Sign
MOVE_LIVE = {S.SIG_MINUS: "lo", S.NEG: "lo", S.POS: "hi", S.SIG_PLUS: "hi",   # DIS -> raise the cold end; ORD -> lower the hot end
             S.SLOW_MINUS: "unresolved", S.ZERO: "unresolved", S.SLOW_PLUS: "unresolved", S.UNRES: "unresolved",   # MID -> UNRESOLVED, never stop
             None: "refuse"}   # not established; total over Sign + {None}
KC = 0.5 * math.log(1 + math.sqrt(2))   # declared: exact 2-D Ising K_c = 1/2 ln(1 + sqrt 2) = 0.4406868


@dataclass(frozen=True)
class Exact:
    """The exact 2-D Ising order field: closes over its own K_c; branch-free (the only comparison is inside frozen sign.sign)."""
    kc: float
    decl_str: str

    def __call__(self, K):
        return sign(K - self.kc, K - self.kc, 0.0)[0]


EXACT = Exact(KC, "exact 2-D Ising K_c = 1/2*ln(1+sqrt(2))")


@dataclass(frozen=True)
class StartDecl:
    lo: float
    hi: float
    dk: float
    target: float   # read by the SCORER alone, never by reading()

    def n(self):
        return round((self.hi - self.lo) / self.dk) + 1

    def k(self, j):
        return self.lo + j * self.dk

    def start_id(self):
        return f"{self.lo}-{self.hi}-{self.dk}"


class OracleLog:
    """Append-before-use (T23): one jsonl record per probe, written O_APPEND before the Reading is built."""

    def __init__(self, path, partition, head):
        self.path, self.partition, self.head = Path(path), partition, head

    def record(self, name, digest):
        rec = dict(t_ns=time.time_ns(), partition=self.partition, path=name, sha256=digest, size=0, argv=sys.argv[1:], pid=os.getpid(),
                   git_head=self.head, route="declared")
        self.path.parent.mkdir(parents=True, exist_ok=True)
        fd = os.open(self.path, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o644)
        os.write(fd, (json.dumps(rec, sort_keys=True) + "\n").encode())
        os.close(fd)


def reading(order, K, move_table):
    """The navigate.Reading at K: order(K) is a Sign or None; move_table is total over Sign + {None}. median_diff/interval None (no sampled interval), m 0."""
    cell = order(K)
    return {True: lambda: Reading("REFUSE", None, None, None, 0, None, navigate.NE, move_table[None]),
            False: lambda: Reading(navigate.SIDE[cell], cell, None, None, 0, None, "ESTABLISHED", move_table[cell])}[cell is None]()


@dataclass(frozen=True)
class Declared:
    start: StartDecl
    order: object   # OrderField: K -> Sign | None
    log: OracleLog

    def reading(self, j):
        self.log.record("declared:exact", hashlib.sha256(self.order.decl_str.encode()).hexdigest())   # before use
        return reading(self.order, self.start.k(j), MOVE_LIVE)


@dataclass(frozen=True)
class LiveDetector:
    """Convenience arm: concrete reading owed on the P2f Detector thread. A total stub: REFUSE at every node, never None, never an exception."""
    det: object
    pins: object
    run: object
    log: OracleLog

    def reading(self, j):
        return Reading("REFUSE", None, None, None, 0, None, navigate.NE, "refuse")


READERS = {Declared: Declared.reading, LiveDetector: LiveDetector.reading}   # total over the sum, by type; no third case, no default


def read_of(oracle):
    return lambda j: READERS[type(oracle)](oracle, j)


def run(oracle):
    """The walk over the oracle's node grid; -> (Walk, bracket (K_lo, K_hi))."""
    w = navigate.walk(read_of(oracle), oracle.start.n())
    return w, (oracle.start.k(w.lo), oracle.start.k(w.hi))


def _declared(root, lo, hi, dk):
    st = StartDecl(lo, hi, dk, KC)
    log = OracleLog(Path(root) / "results" / "navigate" / "declared.access.jsonl", f"declared:{st.start_id()}", schema.git_head(root))
    w, (a, b) = run(Declared(st, EXACT, log))
    trace = [f"  node {j} K={st.k(j):.2f} side={r.side} move={r.move}" for j, r in w.trace]
    return [f"navigate declared ({EXACT.decl_str}; start [{lo}, {hi}], dk {dk})"] + trace + [f"navigate declared: {w.outcome} [{a:.2f}, {b:.2f}]"], 0


def cli(root, argv):
    """`navigate --oracle declared --start LO HI --dk DK` -> (lines, status); never prints. The usage refusal is status 2."""
    i = argv.index("--start") if "--start" in argv else len(argv)
    pair = argv[i + 1:i + 3]
    dk = argv[argv.index("--dk") + 1] if "--dk" in argv[:-1] else None
    usage = (["REFUSED: need `declared --start LO HI --dk DK`.\n  Next: bin/cc navigate --oracle declared --start 0.35 0.60 --dk 0.01"], 2)
    try:
        return _declared(root, float(pair[0]), float(pair[1]), float(dk)) if argv[:1] == ["declared"] else usage
    except (IndexError, TypeError, ValueError):
        return usage
