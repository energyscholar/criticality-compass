"""windows.py - the declared one-side window cutter (plumbing; plan 0884 amendment 1; flag W). An input's [windows] side = S, origin = <name> cuts every stack to s[N, S, S]
before it is reduced: one window side, a projection the input declares, never a size relation. ORIGINS is the total table from the origin names of cc.toml alphabets.window_origin
to the (row, col) offset into a reader's array, which already starts at the file's own minimum row and column. This module imports nothing of the declare side."""
import numpy as np

ORIGINS = {"extent-min": (0, 0)}


def window_shape(shape, w):
    """The (N, side, side) shape a stack of `shape` has after the window w = {side, origin}, or None when the window does not fit inside its extent."""
    r0, c0 = ORIGINS[w["origin"]]
    return (shape[0], w["side"], w["side"]) if r0 + w["side"] <= shape[1] and c0 + w["side"] <= shape[2] else None


def crop(s, w):
    """The window of the stack s[N, H, W]; a window that does not fit is a ValueError (bin/cc validate refuses it first, with a Next line)."""
    r0, c0 = ORIGINS[w["origin"]]
    out = s[:, r0:r0 + w["side"], c0:c0 + w["side"]]
    if out.shape[1:] != (w["side"], w["side"]):
        raise ValueError(f"window side {w['side']} at origin {w['origin']} does not fit a stack of extent {s.shape[1]} x {s.shape[2]}")
    return np.ascontiguousarray(out)
