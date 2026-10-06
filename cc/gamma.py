"""gamma.py - the Gamma-method: the variance of the mean of a derived quantity from its autocovariance, with Wolff's automatic window (maths; plan 0878).
autocov, window: VERBATIM from the toolset's tested reference studies/OBS3/coverage.py (git blob 4a1354635f8a4e02429c8deef203b064d9c2d6b3), functions
autocov and gamma_window; variance is the (1 + (2W+1)/n) line of gamma_window, split out.
Wolff 2004 (Comput. Phys. Commun. 156, 143), the automatic windowing of section 3.3. The result is a statistic of the interval projection C: it places a
reading's sign cell against its declared margin and is never an operator input."""
import numpy as np

SMOOTH = np.array(sorted({2 ** a * 3 ** b * 5 ** c for a in range(30) for b in range(12) for c in range(8)}))   # form: the 5-smooth lengths (fast FFT sizes), up to 7.6e18; tolerance: the ranges only bound the table


def autocov(a, tmax):
    """Gamma_ab(t), t = 0..tmax, for the columns of a [n, p] (means removed): (1/(n-t)) sum_i a(i) b(i+t); FFT, every pair.
    One change from the reference, in the FFT LENGTH only: the reference pads to the power of two above 2n; any length m >= n + tmax gives the same Gamma(t) for
    t <= tmax (no wrap-around), so the smallest 5-smooth m >= n + tmax is used (tests/test_gamma.py asserts equality with the reference's padding)."""
    n, p = a.shape
    a = a - a.mean(axis=0)
    m = int(SMOOTH[np.searchsorted(SMOOTH, n + tmax)])   # form: the FFT length (zero padding past n + tmax: the linear, not the circular, correlation)
    f = np.fft.rfft(a, m, axis=0)
    g = np.empty((tmax + 1, p, p))
    for i in range(p):
        for j in range(p):
            c = np.fft.irfft(np.conj(f[:, i]) * f[:, j], m)[: tmax + 1]
            g[:, i, j] = c / (n - np.arange(tmax + 1))   # form: the unbiased-in-the-mean normalisation 1/(n - t)
    return g


def window(gam, n, s):
    """Wolff's automatic window on Gamma_F(t), t = 0..window_max (window_max = len(gam) - 1): the first W with exp(-W/tau) - tau/sqrt(W n) < 0,
    tau = S / ln((2 tau_int + 1)/(2 tau_int - 1)). Returns (W, tau_int(W)); None when no window is found by window_max (or Gamma_F(0) is not positive):
    the declared null, never a number."""
    if gam[0] <= 0:   # form: a variance that is not positive has no autocorrelation time
        return None
    cf = gam[0]
    for w in range(1, len(gam)):
        cf += 2 * gam[w]   # form: the running sum Gamma(0) + 2 sum Gamma(t)
        tint = cf / (2 * gam[0])   # form: tau_int = (Gamma(0)/2 + sum Gamma(t)) / Gamma(0)
        tau = s / np.log((2 * tint + 1) / (2 * tint - 1)) if tint > 0.5 else 1e-8   # form: Wolff's tau(W) = S / ln((2 tau_int + 1)/(2 tau_int - 1)); tolerance: 1e-8 when tau_int <= 1/2 (the log is undefined)
        if np.exp(-w / tau) - tau / np.sqrt(w * n) < 0:   # form: Wolff's stopping rule g(W) = exp(-W/tau) - tau/sqrt(W n) < 0
            return w, tint
    return None


def variance(gam, w, n):
    """The variance of the mean: (Gamma(0) + 2 sum_{t=1..W} Gamma(t)) / n, times the window's finite-n factor (1 + (2W+1)/n)."""
    return (gam[0] + 2 * gam[1:w + 1].sum()) / n * (1 + (2 * w + 1) / n)   # form: Wolff's variance of the mean with the finite-n window factor
