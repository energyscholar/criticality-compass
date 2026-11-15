"""Plan 1525: the declared narrowing rule, a pure function of the reported moments (contract/SCHEMA-1525.md).
Two estimators of the same critical point are read off one grid:
  A  the fluctuation peak   : the grid points whose specific heat is within z combined errors of the maximum
  B  the block-ratio cross  : the grid points where the level-1 minus level-0 block correlation is within z errors of zero,
                              together with both ends of every sign change between neighbours
The next bracket is the hull of A and B, padded by one grid step, intersected with the bracket that was measured.
U (the union) is never empty because A always holds the argmax, so the new bracket is nested and strictly narrower in
structure, not by a guard."""
import math
from typing import NamedTuple


class Narrowed(NamedTuple):
    A: tuple
    B: tuple
    lo: float
    hi: float


def narrow(grid, C, C_err, Gs, Gs_err, z):
    m = len(grid)
    lo0, hi0 = float(grid[0]), float(grid[-1])
    j = max(range(m), key=lambda i: C[i])  # the first index wins a tie
    A = tuple(i for i in range(m) if C[i] >= C[j] - z * math.sqrt(C_err[i] ** 2 + C_err[j] ** 2))
    D = [Gs[i][1] - Gs[i][0] for i in range(m)]
    sigma = [math.sqrt(Gs_err[i][1] ** 2 + Gs_err[i][0] ** 2) for i in range(m)]
    near_zero = {i for i in range(m) if abs(D[i]) <= z * sigma[i]}
    crossing = {k for i in range(m - 1) if D[i] * D[i + 1] < 0 for k in (i, i + 1)}
    B = tuple(sorted(near_zero | crossing))
    U = set(A) | set(B)
    delta = (hi0 - lo0) / (m - 1)
    lo = max(lo0, float(grid[min(U)]) - delta)
    hi = min(hi0, float(grid[max(U)]) + delta)
    return Narrowed(tuple(int(i) for i in A), tuple(int(i) for i in B), float(lo), float(hi))
