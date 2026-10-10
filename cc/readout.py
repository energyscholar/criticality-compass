"""readout.py - estimate + central interval + sign cell of one resampled column (maths)."""
import numpy as np
import sign


def reading(v, level, eps):
    """v[0] is the point estimate; v[1:] the resamples. Returns (estimate, lo, hi, sign cell name)."""
    lo, hi = np.quantile(v[1:], [(1 - level) / 2, (1 + level) / 2])  # form: central interval (two tails)
    return v[0], lo, hi, sign.sign(lo, hi, eps)[0].value


def reading_se(est, se, z, eps):
    """The Gamma-method's reading (plan 0878): est and its SE give the central interval [est - z SE, est + z SE] (z from cc.toml [levels]); the
    sign cell places that interval against the declared margin, exactly as for a resampled interval. Returns (estimate, lo, hi, sign cell name)."""
    lo, hi = est - z * se, est + z * se   # form: the normal interval of the Gamma-method
    return est, lo, hi, sign.sign(lo, hi, eps)[0].value


def rank(m, alpha):
    """r(m, alpha) = the largest r with miss(m, r) <= alpha, miss(m, r) = 2 P(Bin(m, 1/2) <= r - 1) = 2 sum_{i<r} C(m, i) / 2^m (the rank rule of
    navigator v2, studies/NAV-AT/nav2.py rank; plan 0937 [0937].alpha). Exact integer arithmetic: alpha is compared as alpha * 2^m, never as a float tail."""
    c, tail, hit = 1, 0, 0
    for r in range(1, m // 2 + 1):
        tail += c                      # sum_{i < r} C(m, i)
        c = c * (m - r + 1) // r       # C(m, r)
        hit += 2 * tail <= alpha * 2 ** m
    return hit


def chains(v, r, eps):
    """Plan 0937, interval method `chains` (T18-B): v[1:] are the m rows, one per independent chain (v[0] is the reference row the stages read: chain 0's row).
    Returns (estimate, lo, hi, sign cell name): the sample MEDIAN of the m row values (reported; it never enters the sign cell), and the order statistics
    [v_(r), v_(m+1-r)] of the m values per column, which place the cell. Order statistics are values, so ties need no rule."""
    g = np.sort(v[1:], axis=0)
    lo, hi = g[r - 1], g[len(g) - r]
    return np.median(g, axis=0), lo, hi, sign.sign(lo, hi, eps)[0].value
