"""test_gamma - the Gamma-method (cc/gamma.py, plan 0878 P1.1) on planted AR(1) series of KNOWN integrated autocorrelation time.
x_t = phi x_{t-1} + e_t: tau_int = (1 + phi) / (2 (1 - phi)) and the exact variance of the mean is (1/(1 - phi^2)) (1 + phi)/(1 - phi) / n at large n.
Every check is also run on a PLANTED wrong estimator and must FAIL there (the same predicate, so it can fail): the iid Gamma(0)/n variance (low by 2 tau_int),
a window far too wide (S = 15), and a record whose autocorrelation is not summable inside window_max (the declared null, never a number)."""
import sys
import numpy as np
from lib import bad, bootstrap, check  # noqa: E402
bootstrap(__file__.rsplit("/", 2)[0], "cc")
import gamma

N, PHI, TMAX, S, SEEDS = 24000, 0.8, 400, 1.5, range(12)
TRUE_SE = np.sqrt((1 / (1 - PHI ** 2)) * (1 + PHI) / (1 - PHI) / N)


def ar1(seed, phi=PHI, n=N):
    e, x = np.random.default_rng(seed).normal(size=n), np.zeros(n)
    for t in range(1, n):
        x[t] = phi * x[t - 1] + e[t]
    return x


def gam_of(x):
    return gamma.autocov(x[:, None], TMAX)[:, 0, 0]


def se_ratio(x, s, variance=gamma.variance):
    """SE / the exact SE, or None when no window is found."""
    g = gam_of(x)
    w = gamma.window(g, len(x), s)
    return None if w is None else float(np.sqrt(variance(g, w[0], len(x))) / TRUE_SE), w


def within(ratios, tol=0.05):
    return abs(np.mean(ratios) - 1) <= tol


def iid_variance(g, w, n):
    """the planted wrong one: Gamma(0)/n alone, no window sum"""
    return g[0] / n


def autocov_reference(a, tmax):
    """the toolset's studies/OBS3/coverage.py autocov, verbatim (pads to the power of two above 2n)"""
    n, p = a.shape
    a = a - a.mean(axis=0)
    m = 1 << int(np.ceil(np.log2(2 * n)))
    f = np.fft.rfft(a, m, axis=0)
    g = np.empty((tmax + 1, p, p))
    for i in range(p):
        for j in range(p):
            c = np.fft.irfft(np.conj(f[:, i]) * f[:, j], m)[: tmax + 1]
            g[:, i, j] = c / (n - np.arange(tmax + 1))
    return g


two = np.stack([ar1(2), ar1(3) + 0.3 * ar1(2)], axis=1)
check("autocov (5-smooth padding) equals the reference's (power-of-two padding) for every pair, to rounding", np.allclose(gamma.autocov(two, TMAX), autocov_reference(two, TMAX), rtol=0, atol=1e-9 * float(np.abs(two).max() ** 2)))
check("the padded FFT length is at least n + tmax and 5-smooth", all(int(gamma.SMOOTH[np.searchsorted(gamma.SMOOTH, k)]) >= k for k in (N + TMAX, 600400, 7)))

good = [se_ratio(ar1(k), S) for k in SEEDS]
r_good = [r for r, _ in good]
tau_w = [w[1] for _, w in good]
print(f"S = {S}: SE / exact SE over {len(r_good)} series: mean {np.mean(r_good):.3f}, range [{min(r_good):.3f}, {max(r_good):.3f}]; tau_int mean {np.mean(tau_w):.2f} (exact {0.5 * (1 + PHI) / (1 - PHI):.2f})")
check("AR(1) of known tau_int (n 24 000): the Gamma-method SE is within 5 % of the exact SE", within(r_good))
check("every single series is within 12 % of the exact SE", max(abs(np.array(r_good) - 1)) <= 0.12)

r_iid = [se_ratio(ar1(k), S, iid_variance)[0] for k in SEEDS]
print(f"planted iid Gamma(0)/n: ratio {np.mean(r_iid):.3f} (1/sqrt(2 tau_int) = {1 / np.sqrt(2 * 0.5 * (1 + PHI) / (1 - PHI)):.3f})")
check("the iid plant fails the same 5 % predicate (it is low by the factor sqrt(2 tau_int))", not within(r_iid))
check("the iid plant is low by sqrt(2 tau_int) to within 10 %", abs(np.mean(r_iid) * np.sqrt(2 * 0.5 * (1 + PHI) / (1 - PHI)) - 1) < 0.10)

wide = [se_ratio(ar1(k), 15.0) for k in SEEDS]
w_wide, w_good = np.mean([w[0] for _, w in wide]), np.mean([w[0] for _, w in good])
spread = lambda rs: np.std(rs)   # noqa: E731
print(f"S = 15: mean W {w_wide:.0f} against {w_good:.0f} at S = {S}; SE spread {spread([r for r, _ in wide]):.3f} against {spread(r_good):.3f}; max ratio {max(r for r, _ in wide):.3f}")
check("a window far too wide (S = 15) is read: W is more than 3x the S = 1.5 window", w_wide > 3 * w_good)
check("a window far too wide (S = 15) inflates the SE: its spread is more than 2x and a series reads more than 15 % high",
      spread([r for r, _ in wide]) > 2 * spread(r_good) and max(r for r, _ in wide) > 1.15)

slow = ar1(5, phi=0.9995)   # tau_int ~ 1000 snapshots: not summable inside window_max = 400 at this n
check("window_max reached: window returns the declared null (None), never a number", gamma.window(gam_of(slow), N, S) is None)
check("a non-positive Gamma(0) has no window (None)", gamma.window(np.array([0.0, 0.1, 0.1]), 100, S) is None)
check("variance carries the (1 + (2W + 1)/n) factor", np.isclose(gamma.variance(np.array([2.0, 1.0, 0.5]), 2, 10), (2 + 2 * 1.5) / 10 * (1 + 5 / 10)))
print("test_gamma: " + ("FAILED" if bad else "all passed"))
sys.exit(1 if bad else 0)
