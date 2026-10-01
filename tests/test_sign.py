"""test_sign.py - the interval-position sign: totality, the eps = 0 collapse, and hand cases."""
import sys
import itertools
import numpy as np
sys.path.insert(0, __file__.rsplit("/", 2)[0] + "/cc")
from sign import sign, cell, CELL, Sign as S

eps = 0.5
cases = {(-2.0, -1.0): S.SIG_MINUS, (-1.0, -0.2): S.NEG, (-0.4, -0.1): S.SLOW_MINUS, (-1.0, 0.2): S.UNRES,
         (-0.3, 0.3): S.ZERO, (0.1, 0.4): S.SLOW_PLUS, (0.2, 1.0): S.POS, (0.6, 2.0): S.SIG_PLUS,
         (-1.0, 1.0): S.UNRES, (-0.2, 1.0): S.UNRES}
for (L, U), want in cases.items():
    assert sign(L, U, eps) == [want], ((L, U), sign(L, U, eps), want)

# totality and bijectivity: every ordered interval over a dense grid lands in a cell 0..9, and all 10 cells occur
grid = np.linspace(-2, 2, 81)
cells = {int(cell(L, U, eps)) for L, U in itertools.product(grid, grid) if L <= U}
assert cells == set(range(10)), cells
assert len(CELL) == 10

# eps = 0 collapse: only SIG-, UNRES, SIG+ reachable, and they equal the three-valued rule
three = {S.SIG_MINUS, S.UNRES, S.SIG_PLUS}
for L, U in itertools.product(grid, grid):
    if L <= U:
        got = sign(L, U, 0.0)[0]
        assert got in three, (L, U, got)
        want = S.SIG_PLUS if L > 0 else S.SIG_MINUS if U < 0 else S.UNRES
        assert got == want, (L, U, got, want)
print("test_sign: all passed")
