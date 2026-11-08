"""test_occupied - plan 0884 P2.2: the declared block map of a decorated lattice and its observable (cc/reduce.py), each verbatim-tested on a planted 3 x 3.
majority_occupied3: four +1 and two -1 occupied sites (three vacant) -> +1; three +1 and three -1 -> 0 (a tie is block state 0); an all-vacant cell -> 0; on an array without
zeros it equals block3 bit for bit. g1_occupied: a plant where multiplying the vacancies as 0 would change the mean returns the occupied-pair value (printed beside the plain g1);
no occupied pair -> NaN (the null). even_cells counts the cells holding an even number of listed sites. MAPS and OBSERVABLES are total over each other."""
import sys
import warnings
from pathlib import Path
import numpy as np

ROOT = Path(__file__).resolve().parent.parent
from lib import bad, bootstrap, check  # noqa: E402
bootstrap(ROOT, "cc", "cc/instruments")
import reduce  # noqa: E402

warnings.simplefilter("ignore", RuntimeWarning)   # 0 / 0 is the declared NaN null; numpy reports it as a warning


A = np.array([[1, 1, 1], [1, -1, -1], [0, 0, 0]], np.int8)       # four +1, two -1, three vacant
B = np.array([[1, 1, 1], [-1, -1, -1], [0, 0, 0]], np.int8)      # three +1, three -1
Z = np.zeros((3, 3), np.int8)
check("four +1 and two -1 occupied -> +1", reduce.majority_occupied3(A)[0, 0] == 1, reduce.majority_occupied3(A))
check("three +1 and three -1 -> tie -> block state 0", reduce.majority_occupied3(B)[0, 0] == 0)
check("all-vacant cell -> 0", reduce.majority_occupied3(Z)[0, 0] == 0)
r = np.random.default_rng(1).choice(np.array([-1, 1], np.int8), (4, 9, 9))
check("no zeros: equals block3 bit for bit", np.array_equal(reduce.majority_occupied3(r), reduce.block3(r)))
two = np.zeros((6, 6), np.int8)
two[:3, :3], two[:3, 3:] = A, B
check("a 6 x 6 maps to 2 x 2 cell by cell", reduce.majority_occupied3(two).tolist() == [[1, 0], [0, 0]], reduce.majority_occupied3(two))
V = np.array([[1, 1, 0], [1, 1, 0], [0, 0, 0]], np.int8)         # a 2 x 2 occupied corner: every occupied pair is +1 * +1
got, plain = float(reduce.g1_occupied(V[None])[0]), float(reduce.g1(V[None])[0])
print(f"     g1_occupied {got}  plain g1 (vacancies multiplied as 0) {plain}")
check("g1_occupied returns the occupied-pair value, not the diluted one", got == 1.0 and abs(plain - 1 / 3) < 1e-12 and got != plain, (got, plain))
full = r[0:1, :, :]
check("no vacancy: g1_occupied equals g1 bit for bit", np.array_equal(reduce.g1_occupied(full), reduce.g1(full)))
check("a snapshot with no occupied pair reads NaN (the declared null)", np.isnan(reduce.g1_occupied(Z[None])[0]))
check("even_cells: A holds 6 listed sites (even), a corner of 4 (even), one site (odd)", reduce.even_cells(A != 0, 3) == (1, 1) and reduce.even_cells(V != 0, 3) == (1, 1)
      and reduce.even_cells(np.pad(np.ones((1, 1), bool), ((0, 2), (0, 2))), 3) == (0, 1))
check("total tables", sorted(reduce.MAPS) == sorted(reduce.OBSERVABLES))
x = np.zeros((9, 9), np.int8)
x[:3, :3] = A
check("snapshot dispatches by the declared map: 2 levels, level 0 = g1_occupied of the table", reduce.snapshot(x, "majority-occupied3", 2).shape == (2,)
      and reduce.snapshot(x, "majority-occupied3", 2)[0] == reduce.g1_occupied(x[None])[0])
sys.exit(1 if bad else 0)
