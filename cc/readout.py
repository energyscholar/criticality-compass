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
