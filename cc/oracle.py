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
from oracle_measured import MeasuredStart, scan, load_rehearsal, load_sample, file_shas, PARTNER, GRID  # noqa: F401
from oracle_reweight import Reweight, Refusal, DenseStart, REWEIGHT_DECL, report_dense, make_reweight, dense_start  # noqa: F401  plan 1456 WIDTH: the dense reweight field, outside the measure_hash closure
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
    name = "exact"

    def __call__(self, K):
        return sign(K - self.kc, K - self.kc, 0.0)[0]

    def read_digest(self, K):
        return hashlib.sha256(self.decl_str.encode()).hexdigest()   # constant: the declaration is what is read


@dataclass(frozen=True)
class Measured:
    """The finite-L order field: the sign of the matched-pair needle (big L vs its partner, m chains, rank r) read from stored chains. Carries NO K_c; load/shas are injected."""
    big: int
    small: int
    m: int
    r: int
    load: object   # K -> (a, b), lists of final-level g1 series
    shas: object   # K -> sha256 of the bytes load reads
    name = "measured"

    def __call__(self, K):
        return navigate.needle(*self.load(K), self.m, self.r).cell   # None (under-replicated) is the honest REFUSE value

    def read_digest(self, K):
        return self.shas(K)


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
    status = {type(None): lambda: navigate.NE, Refusal: lambda: f"NOT_ESTABLISHED ({cell.reason})"}.get(type(cell), lambda: "ESTABLISHED")()   # a Refusal carries WHY in the status string; cell stays None
    return {True: lambda: Reading("REFUSE", None, None, None, 0, None, status, move_table[None]),
            False: lambda: Reading(navigate.SIDE[cell], cell, None, None, 0, None, status, move_table[cell])}[type(cell) in (type(None), Refusal)]()


@dataclass(frozen=True)
class Declared:
    start: StartDecl
    order: object   # OrderField: K -> Sign | None
    log: OracleLog

    def reading(self, j):
        K = self.start.k(j)
        self.log.record(f"declared:{self.order.name}", self.order.read_digest(K))   # before use
        return reading(self.order, K, MOVE_LIVE)


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


TERMINAL = {Exact: navigate.walk, Measured: scan}   # by order type, total: a point field bisects; a band field (finite L) scans for its flanks
TERMINAL[Reweight] = scan   # plan 1456: the dense reweight field is a band field (the UNRES band + its flanks), so it scans exactly as Measured does


def run(oracle):
    """The terminal of the oracle's order type over its node grid; -> (Walk, bracket (K_lo, K_hi))."""
    w = TERMINAL[type(oracle.order)](read_of(oracle), oracle.start.n())
    return w, (oracle.start.k(w.lo), oracle.start.k(w.hi))


def _declared(root, lo, hi, dk):
    st = StartDecl(lo, hi, dk, KC)
    log = OracleLog(Path(root) / "results" / "navigate" / "declared.access.jsonl", f"declared:{st.start_id()}", schema.git_head(root))
    w, (a, b) = run(Declared(st, EXACT, log))
    trace = [f"  node {j} K={st.k(j):.2f} side={r.side} move={r.move}" for j, r in w.trace]
    return [f"navigate declared ({EXACT.decl_str}; start [{lo}, {hi}], dk {dk})"] + trace + [f"navigate declared: {w.outcome} [{a:.2f}, {b:.2f}]"], 0


def _measured(root, big):
    """`navigate --oracle measured --L BIG` over the 7 labels; the data root is the global --data-root / CC_DATA_ROOT. Absent data or an undeclared L is a NAMED REFUSE (status 2)."""
    data = schema.resolve_data_root(None, schema.DATA_ROOT_FLAG)[0]
    why = [w for w, ok in ((f"no 1282/<run>/ chain files under {data}", bool(list((data / "1282").glob("*/*.npz")))), (f"L {big} has no declared partner {PARTNER}", big in PARTNER)) if not ok]
    st = MeasuredStart(GRID, KC)
    log = OracleLog(Path(root) / "results" / "navigate" / "measured.access.jsonl", f"measured:{st.start_id()}", schema.git_head(root))
    order = lambda: Measured(big, PARTNER[big], 10, 2, lambda K: load_rehearsal(data, K, big), lambda K: file_shas(data, K, big))   # noqa: E731  r = readout.rank(10, 22/1024) = 2
    go = lambda: run(Declared(st, order(), log))   # noqa: E731
    refusal = ([f"REFUSED: {'; '.join(why)}.\n  Next: bin/cc --data-root <dir> navigate --oracle measured --L 243"], 2)
    return {True: lambda: refusal, False: lambda: _report(st, big, *go())}[bool(why)]()


def _report(st, big, w, bracket):
    trace = [f"  node {j} label={st.labels[j]} K={st.k(j):.4f} side={r.side} move={r.move}" for j, r in w.trace]
    return [f"navigate measured (L {big} vs {PARTNER[big]}, m 10; labels {st.labels[0]}..{st.labels[-1]})"] + trace + [f"navigate measured: {w.outcome} [{bracket[0]:.4f}, {bracket[1]:.4f}]"], 0


def _reweight(root, big):
    """`navigate --oracle reweight --L BIG` (plan 1456 WIDTH): the dense FS-reweighted matched-pair bracket over the 7-label chains; absent data is a NAMED REFUSE (status 2), mirroring _measured."""
    data = schema.resolve_data_root(None, schema.DATA_ROOT_FLAG)[0]
    why = [w for w, ok in ((f"no 1282/<run>/ chain files under {data}", bool(list((data / "1282").glob("*/*.npz")))), (f"L {big} has no declared partner {PARTNER}", big in PARTNER)) if not ok]
    st = dense_start(KC)
    log = OracleLog(Path(root) / "results" / "navigate" / "reweight.access.jsonl", f"reweight:{st.start_id()}", schema.git_head(root))
    return {True: lambda: ([f"REFUSED: {'; '.join(why)}.\n  Next: bin/cc --data-root <dir> navigate --oracle reweight --L 243"], 2),
            False: lambda: report_dense(st, big, *run(Declared(st, make_reweight(data, big, 10, 2), log)))}[bool(why)]()   # noqa: E731  r = readout.rank(10, 22/1024) = 2


def cli(root, argv):
    """`navigate --oracle declared --start LO HI --dk DK` | `--oracle measured --L BIG` | `--oracle reweight --L BIG` -> (lines, status); never prints. The usage refusal is status 2."""
    i = argv.index("--start") if "--start" in argv else len(argv)
    pair = argv[i + 1:i + 3]
    dk = argv[argv.index("--dk") + 1] if "--dk" in argv[:-1] else None
    usage = (["REFUSED: need `declared --start LO HI --dk DK` or `measured --L 243`.\n  Next: bin/cc navigate --oracle declared --start 0.35 0.60 --dk 0.01"], 2)
    big = lambda: int(argv[argv.index("--L") + 1])   # noqa: E731
    parse = {"declared": lambda: (_declared, float(pair[0]), float(pair[1]), float(dk)), "measured": lambda: (_measured, big()), "reweight": lambda: (_reweight, big())}
    try:
        fn, *operands = parse[(argv[:1] or [""])[0]]()   # ONLY argv parsing may fail as a usage error
    except (IndexError, KeyError, ValueError, TypeError):
        return usage
    return fn(root, *operands)   # an arm defect propagates (as on the Detector stack), never masked as a usage refusal
