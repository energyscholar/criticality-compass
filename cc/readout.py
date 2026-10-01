"""readout.py - estimate + central interval + sign cell of one resampled column (maths)."""
import numpy as np
import sign


def reading(v, level, eps):
    """v[0] is the point estimate; v[1:] the resamples. Returns (estimate, lo, hi, sign cell name)."""
    lo, hi = np.quantile(v[1:], [(1 - level) / 2, (1 + level) / 2])  # form: central interval (two tails)
    return v[0], lo, hi, sign.sign(lo, hi, eps)[0].value
