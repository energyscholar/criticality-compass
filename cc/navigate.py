"""navigate.py - the navigator v2 reading at one node and the N0 walk over a stored map (maths). UNTESTED (plan 1114, docs/navigate.md).
READING: the toolset's studies/NAV-AT/nav2.py (lines 81-110), no new number. a = the m chains at L 81, b = the m chains at L 27, each (chains, N) of
  recorded g1 at the final level; d_k = mean(a_k) - mean(b_k); interval [d_(r), d_(m+1-r)]; sign cell at EPS; pinned channel per size; side = ORD
  when L 81 is PINNED, else SIDE[cell]. Fewer than m chains at either size => NOT_ESTABLISHED, a value.
WALK: the N0 bisection of studies/NAV-AT/nav.py acquire (lines 38-52) with ONE change: nav.py moves on the side, and the [P2] side table sends UNRES
  to MID, so an unreadable node STOPPED the walk as if located. Here the walk moves on the cell (MOVE, total over the eight cells and the
  NOT_ESTABLISHED reading); UNRES has its own terminal, UNRESOLVED, which names the node and claims no location."""
from dataclasses import dataclass
import numpy as np
import sign
from sign import Sign

S = Sign
SIDE = {S.SIG_MINUS: "DIS", S.NEG: "DIS", S.SLOW_MINUS: "MID", S.ZERO: "MID", S.UNRES: "MID", S.SLOW_PLUS: "MID", S.POS: "ORD", S.SIG_PLUS: "ORD"}   # declared: toolset m.toml [P2] side_table (frozen; nav2.py line 100 via nav.SIDE)
MOVE = {S.SIG_MINUS: "lo", S.NEG: "lo", S.SLOW_MINUS: "stop", S.ZERO: "stop", S.SLOW_PLUS: "stop", S.UNRES: "unresolved", S.POS: "hi", S.SIG_PLUS: "hi",
        None: "refuse"}   # declared (plan 1114): nav.py MOVE[SIDE[cell]] for every cell but UNRES; UNRES -> unresolved (the T1 defect removed); None = NOT_ESTABLISHED
EPS = 0.01        # declared: nav.py line 19 [NAV-AT-N0] needle eps (nav2.py imports it)
BOUND = 1.0       # declared: nav2.py line 46, [TAX-T6B] reading - the declared sink bound g1 = 1.0
BIG, SMALL = 81, 27   # declared: nav2.py lines 48, 99 - the [NAV-AT-GRID] size pair (a = L 81, b = L 27)
PIN_STATE = ("NONE", "MIXED", "PINNED")   # form: nav2.py line 52, code (k > 0) + (k == m) over k pinned chains of m >= 1
NE = "NOT_ESTABLISHED (INSUFFICIENT_REPLICATES)"
STEP = {"lo": lambda lo, mid, hi: (mid, hi, None), "hi": lambda lo, mid, hi: (lo, mid, None),
        "stop": lambda lo, mid, hi: (lo, hi, "STOP"), "unresolved": lambda lo, mid, hi: (lo, hi, "UNRESOLVED"),
        "refuse": lambda lo, mid, hi: (lo, hi, "NOT_ESTABLISHED")}   # form: nav.py lines 49-51 as a table over MOVE's values (None = keep walking)


@dataclass(frozen=True)
class Reading:
    side: str            # ORD / DIS / MID, or REFUSE when NOT_ESTABLISHED (nav2.Reading)
    cell: object         # sign.Sign (UNRES is a value), None when NOT_ESTABLISHED
    median_diff: object  # median of d_k, None when NOT_ESTABLISHED
    interval: object     # (d_(r), d_(m+1-r)), None when NOT_ESTABLISHED
    m: int
    pinned: object       # {81: channel, 27: channel}, None when NOT_ESTABLISHED
    status: str          # ESTABLISHED | NE
    move: str            # MOVE's value for this reading (plan 1114)


@dataclass(frozen=True)
class Walk:
    outcome: str         # BRACKET | STOP | UNRESOLVED | NOT_ESTABLISHED | REFUSE
    lo: int              # node-index bracket when the walk ended
    hi: int
    trace: tuple         # ((node index, Reading), ...) in read order; the last entry is the node a terminal move ended on


def interval(d, m, r):
    """[d_(r), d_(m+1-r)] of the first m values (nav2.py interval; r = readout.rank(m, alpha))."""
    g = np.sort(np.asarray(d[:m], float))
    return float(g[r - 1]), float(g[m - r])


def pinned(g):
    """PINNED_OBSERVED channel of one size: g (chains, N) recorded samples -> NONE / MIXED / PINNED (nav2.py pinned)."""
    k = int((np.asarray(g) == BOUND).all(axis=1).sum())  # form: a chain is pinned iff every sample equals the declared bound exactly
    return PIN_STATE[int(k > 0) + int(k == len(g))]      # form: PIN_STATE code (MIXED is not PINNED)


def _read(a, b, m, r):
    a, b = np.asarray(a, float)[:m], np.asarray(b, float)[:m]
    d = a.mean(axis=1) - b.mean(axis=1)
    lo, hi = interval(d, m, r)
    s = sign.sign(lo, hi, EPS)[0]
    pin = {BIG: pinned(a), SMALL: pinned(b)}
    sink = pin[BIG] == PIN_STATE[2]   # form: the sink ONLY via PINNED_OBSERVED at L 81 (nav2.py line 100)
    return Reading({True: "ORD", False: SIDE[s]}[sink], s, float(np.median(d)), (lo, hi), m, pin, "ESTABLISHED", {True: "hi", False: MOVE[s]}[sink])


def _refuse(a, b, m, r):
    return Reading("REFUSE", None, None, None, m, None, NE, MOVE[None])


def needle(a, b, m, r):
    """the v2 reading at one node, stage m: a = L 81 chains, b = L 27 chains (lists of recorded series; nav2.py needle)."""
    return {True: _read, False: _refuse}[len(a) >= m and len(b) >= m](a, b, m, r)  # form: [TAX-T18-v15B] eligibility - chain count >= m


def _bisect(read, lo, hi, trace):
    out = None
    while out is None and hi - lo > 1:   # form: nav.py line 45, bisection on node indices until one step wide or a terminal move
        mid = (lo + hi) // 2
        trace.append((mid, read(mid)))
        lo, hi, out = STEP[trace[-1][1].move](lo, mid, hi)
    return Walk(out or "BRACKET", lo, hi, tuple(trace))


def _refuse_ends(read, lo, hi, trace):
    return Walk("REFUSE", lo, hi, tuple(trace))


def walk(read, n):
    """N0 over node indices 0..n-1; read(j) -> Reading. The ends must read lo at 0 and hi at n-1 (nav.py lines 41-44: DIS ... ORD), else REFUSE."""
    trace = [(0, read(0)), (n - 1, read(n - 1))]
    return {("lo", "hi"): _bisect}.get((trace[0][1].move, trace[1][1].move), _refuse_ends)(read, 0, n - 1, trace)
