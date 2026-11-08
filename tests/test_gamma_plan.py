"""test_gamma_plan - method gamma's plumbing (plan 0878 P2.1): the instruments' series()/from_means() agree with reduce(), the linearisation rows give the
Gamma-method SE of a derived quantity (against the spread over independent replicates), the logcoord door is the declared |v| > door_z SE, and a Gamma statistic
can never be built into a NodeField (it is a projection C output, never an operator input)."""
import sys
from pathlib import Path
import numpy as np

ROOT = Path(__file__).resolve().parent.parent
from lib import bad, bootstrap, check  # noqa: E402
bootstrap(ROOT, "cc", "cc/instruments")
import door  # noqa: E402
import gamma  # noqa: E402


def ar1(rng, phi, n):
    """a stationary AR(1) of unit innovations by FFT filtering (circular: exact enough at n >> tau)."""
    e, w = rng.normal(size=n), 2 * np.pi * np.fft.rfftfreq(n)
    return np.fft.irfft(np.fft.rfft(e) / (1 - phi * np.exp(-1j * w)), n)


rng = np.random.default_rng(11)
IV = {"method": "gamma", "level": 0.95, "window_s": 1.5, "window_max": 400, "door_z": 3.0}

# 1. series/from_means agree with reduce on every instrument module (so the linearisation rows ARE the instrument's own estimate)
ctx = door.Ctx(level=0.95, eps={}, rel={}, pair_shape=(3, 2), unit_scale=7.0, unit_scales=(3.0, 5.0, 7.0))
n = 400
G, E, Q, GL = (lambda k: rng.normal(size=n) + k), (lambda k: rng.normal(size=n) - 3 + k), (lambda k: rng.normal(size=n) + 40 + k), (lambda k: rng.normal(size=(n, 4)) + k)
cases = {
    "needle": {"GL": [GL(1), GL(2)]}, "needle_chain": {"GL": [GL(1), GL(2), GL(3)]},
    "across": {"G": [G(1), G(2), G(3)], "E": [E(1), E(2), E(3)]}, "stability": {"G": [G(1), G(2), G(3)], "E": [E(1), E(2), E(3)]},
    "two_start": {"Q": [Q(0), Q(1)]}, "fluct": {"E": [Q(1), Q(2), Q(3)]},
    "along": {"G": [G(k) for k in range(6)]}, "across_delta": {"G": [G(k) for k in range(6)]}, "stability_delta": {"G": [G(k) for k in range(6)]},
    "transform": {"G": [G(1), G(2), G(3)], "E": [E(1), E(2), E(3)], "GL": [GL(1), GL(2), GL(3)]},
}
for name, arrays in cases.items():
    mod = __import__(name)
    ser = mod.series(arrays, ctx)
    got, want = mod.from_means([s.mean(axis=0) for s in ser], ctx), mod.reduce(arrays, ctx)
    check(f"{name}: from_means(means of series) equals reduce", np.allclose(got, want, rtol=1e-9, atol=1e-9), f"{got} vs {want}")

# 2. the rows: 1 + P of them, row 0 the estimate, each next row one primary displaced by its naive SE
mod, arrays = __import__("across"), cases["across"]
lin = door.linearise(mod.series(arrays, ctx), 0.001)
rows = [mod.from_means(ms, ctx) for ms in door.linearise_plan(lin)]
check("1 + P rows (P = 3 files x 3 primaries)", len(rows) == 10, str(len(rows)))
check("row 0 is the estimate", np.allclose(rows[0], mod.reduce(arrays, ctx)))

# 3. calibration: R = cov(G, E) from two autocorrelated series; the Gamma SE against the spread of R over independent replicates
N, REPS = 24000, 120


def pair(r):
    g = ar1(r, 0.8, N)
    return g, 0.6 * g + ar1(r, 0.6, N)


def cov_reading(g, e):
    arrs = {"G": [g], "E": [e]}
    lin = door.linearise(mod.series(arrs, ctx), 0.001)
    v = np.array([float(mod.from_means(ms, ctx)[0]) for ms in door.linearise_plan(lin)])
    return v[0], door.gamma_stat(lin, v, IV)


reps = [pair(rng) for _ in range(REPS)]
r_est = np.array([float(np.mean(g * e) - np.mean(g) * np.mean(e)) for g, e in reps])
ses = [cov_reading(*reps[k])[1].se for k in range(20)]
print(f"cov(G, E): spread over {REPS} replicates {r_est.std():.5f}; Gamma SE mean over 20 {np.mean(ses):.5f}")
check("the Gamma SE of cov(G, E) is within 12 % of the spread over independent replicates", abs(np.mean(ses) / r_est.std() - 1) < 0.12)
iid_se = np.mean([np.sqrt(np.var(g * e) / N) for g, e in reps[:20]])
check("an iid SE (no autocorrelation) is far too small for it (the plant the Gamma-method corrects)", iid_se < 0.6 * r_est.std(), f"{iid_se} vs {r_est.std()}")

# 4. the logcoord door: |v| > door_z * SE_Gamma for every component, else a refusal; a Gamma statistic is no NodeField
ga, gb = ar1(rng, 0.8, N), ar1(rng, 0.8, N)


def logdoor(shift):
    arrs = {"G": [ga, gb + shift]}
    lin = door.linearise([g[:, None] for g in arrs["G"]], 0.001)
    rows = np.array([[m[1][0] - m[0][0]] for m in door.linearise_plan(lin)])   # Delta = mean(b) - mean(a), [rows, 1]
    c = door.Ctx(level=0.95, eps={}, rel={}, quantity="Delta", interval=IV, lin=lin, method="gamma")
    return door.logcoord(rows, c), door.gamma_stat(lin, rows[:, 0], IV).se


small, se = logdoor(0.5)      # |Delta| ~ 0.5 against SE ~ 0.05: resolved
check("logcoord passes when |Delta| > door_z * SE", not isinstance(small, door.Null), str(small))
lowd, se = logdoor(0.0)
check("logcoord refuses when |Delta| <= door_z * SE (a Null naming door_z)", isinstance(lowd, door.Null) and "door_z" in lowd.reason, str(lowd))
stat = door.GammaStat(0.1, 5, 2.0)
try:
    door.nodefield(stat, ctx)
    refused = False
except ValueError as e:
    refused = "never an operator input" in str(e)
check("a Gamma-method statistic routed into a NodeField is refused", refused)
print("test_gamma_plan: " + ("FAILED" if bad else "all passed"))
sys.exit(1 if bad else 0)
