"""scale.py - T6: declared BLOCKING maps that define the SCALE relation (maths; no branches).
block3: 3x3 majority. A block of 9 spins of +-1 has an ODD sum, so sign(sum) is never 0: NO TIES BY CONSTRUCTION (a 2x2
majority would need a tie-breaking rule = control). Requires L a power of 3 (checked at the door).
levels: the chain of block lattices s_0 (finest) -> s_1 -> ... (each 3x coarser), a declared relation over scale."""
import numpy as np


def block3(s):
    """s: (..., L, L) of +-1 -> (..., L/3, L/3) of +-1 by 3x3 majority."""
    n, L = s.shape[:-2], s.shape[-1]                             # form: the two lattice axes
    b = s.reshape(*n, L // 3, 3, L // 3, 3).sum(axis=(-3, -1))  # form: 3x3 blocks (odd => no ties)
    return np.sign(b).astype(np.int8)


def levels(s, count):
    out = [s]
    for _ in range(count - 1):
        out.append(block3(out[-1]))
    return out
