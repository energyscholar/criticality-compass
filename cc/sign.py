"""sign.py - T1: the sign of a measured change as the POSITION of its interval among DECLARED cut points.

Input: an interval [L, U] for the change (from a declared null; see nulls.py) and a declared equivalence margin eps >= 0.
Cut points c = (-eps, 0, +eps). Position codes, by construction (no comparison chain):
    bL = #{c < L}      (searchsorted left)      bU = #{c <= U}     (searchsorted right)
L <= U  =>  bL <= bU, so the reachable pairs are exactly the 10 cells of a triangle; `cell = bU(bU+1)/2 + bL` numbers
them 0..9 bijectively. The verdict table below is TOTAL over those 10 cells and has no unreachable entry.

    bU\\bL   0          1          2          3
    0       SIG-
    1       NEG        SLOW-
    2       UNRES      ZERO!      SLOW+
    3       UNRES      UNRES      POS        SIG+
 SIG+  L > eps                 resolved rise beyond the margin
 POS   0 < L <= eps <= U        resolved rise, margin unresolved
 SLOW+ 0 < L, U < eps           resolved rise, resolved SMALLER than the margin
 ZERO! -eps < L <= 0 <= U < eps  resolved EQUIVALENT to zero within the margin (TOST)
 SLOW-, NEG, SIG-              the mirror images
 UNRES                          the interval straddles 0 and a margin edge: cannot say
eps = 0 collapses the cut points to one: only SIG-, UNRES, SIG+ are reachable -> the three-valued sign exactly.
(The earlier proposed five-valued rule |v|+w<eps / |v|>w OVERLAPPED - a well-resolved small value was both ZERO! and
SLOW. The interval-position form is a partition by construction.)
"""
from enum import Enum
import numpy as np


class Sign(Enum):
    SIG_MINUS = "SIG-"
    NEG = "NEG"
    SLOW_MINUS = "SLOW-"
    UNRES = "UNRES"
    ZERO = "ZERO!"
    SLOW_PLUS = "SLOW+"
    POS = "POS"
    SIG_PLUS = "SIG+"


S = Sign
CELL = (S.SIG_MINUS,                                   # (bL,bU) = (0,0)
        S.NEG, S.SLOW_MINUS,                           # (0,1) (1,1)
        S.UNRES, S.ZERO, S.SLOW_PLUS,                  # (0,2) (1,2) (2,2)
        S.UNRES, S.UNRES, S.POS, S.SIG_PLUS)           # (0,3) (1,3) (2,3) (3,3)


def position(L, U, eps):
    """(bL, bU) for each interval; vectorised."""
    cuts = np.array([-eps, 0.0, eps])
    return np.searchsorted(cuts, L, side="left"), np.searchsorted(cuts, U, side="right")


def cell(L, U, eps):
    bL, bU = position(np.asarray(L, float), np.asarray(U, float), eps)
    return bU * (bU + 1) // 2 + bL                      # form: triangular numbering of the pairs bL <= bU


def sign(L, U, eps):
    """the Sign of each interval [L, U] against the declared margin eps."""
    return [CELL[int(c)] for c in np.atleast_1d(cell(L, U, eps))]


def interval(v, null_lo, null_hi):
    """the interval for the true change, given the measured value v and the null band [null_lo, null_hi] of the same
    statistic under 'no change':  [v - null_hi, v - null_lo]."""
    return np.asarray(v) - null_hi, np.asarray(v) - null_lo
