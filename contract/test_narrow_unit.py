"""Plan 1525 — the pure narrowing rule `navigator.estimate.narrow` (contract/SCHEMA-1525.md, "The needle").
Synthetic moments with known answers; no server, no sampler. FROZEN: the Generator makes this green; it does not edit it.

`narrow(grid, C, C_err, Gs, Gs_err, z) -> Narrowed(A, B, lo, hi)`:
  A = { i : C[i] >= C[j] - z*sqrt(C_err[i]^2 + C_err[j]^2) },  j = argmax C (first on ties)
  D[i] = Gs[i][1] - Gs[i][0];  s[i] = sqrt(Gs_err[i][1]^2 + Gs_err[i][0]^2)
  B = { i : |D[i]| <= z*s[i] }  ∪  { i, i+1 : D[i]*D[i+1] < 0 }
  U = A ∪ B;  Δ = (hi0 - lo0)/(m-1);  lo = max(lo0, grid[min U] - Δ);  hi = min(hi0, grid[max U] + Δ)

RED until navigator/estimate.py exists.  Run:  python contract/test_narrow_unit.py   (or pytest)
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _grid(lo, hi, m):
    return [lo + i * (hi - lo) / (m - 1) for i in range(m)]


def _gs(D, err=0.001):
    """Gs rows [0.5, 0.5 + D[i]] with equal small errors."""
    return [[0.5, 0.5 + d] for d in D], [[err, err] for _ in D]


def _close(a, b):
    return abs(a - b) <= 1e-12


def _narrow():
    from navigator.estimate import narrow  # noqa: E402 — imported here so a missing module FAILS each test, not the file
    return narrow


C_PEAK = [1.0, 2.0, 3.0, 4.0, 10.0, 4.0, 3.0, 2.0, 1.0]
D_CROSS = [-0.4, -0.3, -0.2, -0.1, -0.05, 0.05, 0.1, 0.2, 0.3]   # sign change between 4 and 5


def test_clear_peak_and_crossing():
    grid = _grid(0.0, 8.0, 9)                    # Δ = 1
    Gs, Gs_err = _gs(D_CROSS)
    r = _narrow()(grid, C_PEAK, [0.1] * 9, Gs, Gs_err, 2.0)
    assert tuple(r.A) == (4,), r
    assert tuple(r.B) == (4, 5), r
    assert _close(r.lo, 3.0) and _close(r.hi, 6.0), r          # U = {4,5}, padded by one Δ each side


def test_noise_keeps_everything_and_never_widens():
    grid = _grid(0.0, 8.0, 9)
    Gs, Gs_err = _gs(D_CROSS)
    r = _narrow()(grid, C_PEAK, [5.0] * 9, Gs, Gs_err, 2.0)    # 10 - 2*sqrt(50) ≈ -4.1 ⇒ every point is in A
    assert tuple(r.A) == tuple(range(9)), r
    assert _close(r.lo, 0.0) and _close(r.hi, 8.0), r          # clipped to the bracket: nested, never wider


def test_B_empty_when_no_crossing():
    grid = _grid(0.30, 0.40, 5)                  # Δ = 0.025
    C = [1.0, 2.0, 5.0, 2.0, 1.0]
    Gs, Gs_err = _gs([-0.4, -0.3, -0.2, -0.15, -0.1])
    r = _narrow()(grid, C, [0.1] * 5, Gs, Gs_err, 2.0)
    assert tuple(r.A) == (2,) and tuple(r.B) == (), r
    assert _close(r.lo, 0.325) and _close(r.hi, 0.375), r


def test_B_by_zero_within_noise_without_a_sign_change():
    grid = _grid(0.0, 8.0, 9)
    D = [-0.4, -0.3, 0.0, -0.1, -0.2, -0.3, -0.35, -0.4, -0.45]   # D[2] = 0: within zσ, and 0*x < 0 is false
    Gs, Gs_err = _gs(D)
    r = _narrow()(grid, C_PEAK, [0.1] * 9, Gs, Gs_err, 2.0)
    assert tuple(r.B) == (2,), r
    assert tuple(r.A) == (4,), r
    assert _close(r.lo, 1.0) and _close(r.hi, 5.0), r          # U = {2, 4}


def test_peak_at_the_edge_clips_to_the_bracket():
    grid = _grid(0.0, 8.0, 9)
    C = [10.0, 4.0, 3.0, 2.0, 1.0, 1.0, 1.0, 1.0, 1.0]
    Gs, Gs_err = _gs([-0.1] * 9)
    r = _narrow()(grid, C, [0.1] * 9, Gs, Gs_err, 2.0)
    assert tuple(r.A) == (0,) and tuple(r.B) == (), r
    assert _close(r.lo, 0.0) and _close(r.hi, 1.0), r


def test_first_index_wins_a_tie():
    grid = _grid(0.0, 8.0, 9)
    C = [1.0, 1.0, 7.0, 1.0, 1.0, 1.0, 7.0, 1.0, 1.0]
    Gs, Gs_err = _gs([-0.1] * 9)
    r = _narrow()(grid, C, [0.0] * 9, Gs, Gs_err, 2.0)       # zero errors: A = exactly the points equal to the max
    assert tuple(r.A) == (2, 6), r


def test_returns_plain_types():
    grid = _grid(0.0, 8.0, 9)
    Gs, Gs_err = _gs(D_CROSS)
    r = _narrow()(grid, C_PEAK, [0.1] * 9, Gs, Gs_err, 2.0)
    assert isinstance(r.A, tuple) and isinstance(r.B, tuple), r
    assert all(type(i) is int for i in r.A + r.B), r
    assert type(r.lo) is float and type(r.hi) is float, r


def test_errors_are_per_point_per_level_and_z_is_honoured():
    """pins: C_err[i] AND C_err[j] both enter A; BOTH Gs_err levels enter sigma; z is the argument, not a constant."""
    grid = _grid(0.0, 8.0, 9)
    C = [1.0, 2.0, 3.0, 7.95, 10.0, 4.0, 3.0, 2.0, 1.0]
    C_err = [0.1, 0.1, 0.1, 2.0, 0.5, 0.1, 0.1, 0.1, 0.1]
    # z = 1: point 3 is in A only with sqrt(C_err[3]^2 + C_err[4]^2) = 2.06 (7.95 >= 7.938); either error alone excludes it
    D = [-0.4, -0.3, -0.2, -0.1, -0.055, -0.3, -0.35, -0.4, -0.45]   # no sign change anywhere
    Gs = [[0.5, 0.5 + d] for d in D]
    Gs_err = [[0.001, 0.001] for _ in D]
    Gs_err[3] = [0.04, 0.04]     # sigma 0.0566: |D|=0.1 is outside 1*sigma but inside 2*sigma (catches a hardcoded z=2)
    Gs_err[4] = [0.05, 0.03]     # sigma 0.0583: |D|=0.055 is inside only when BOTH levels' errors are used
    r = _narrow()(grid, C, C_err, Gs, Gs_err, 1.0)
    assert tuple(r.A) == (3, 4), r
    assert tuple(r.B) == (4,), r
    assert _close(r.lo, 2.0) and _close(r.hi, 5.0), r


if __name__ == "__main__":
    _tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    _fail = 0
    for _t in _tests:
        try:
            _t(); print(f"PASS {_t.__name__}")
        except Exception as _e:  # noqa: BLE001
            _fail += 1; print(f"FAIL {_t.__name__}: {type(_e).__name__}: {_e}")
    print(f"{len(_tests) - _fail}/{len(_tests)} passed")
    sys.exit(1 if _fail else 0)
