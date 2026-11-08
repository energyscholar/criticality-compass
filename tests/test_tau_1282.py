"""test_tau_1282 - plan 1282 P1a: the tau_int tool (tests/tau_1282_p1.py). T1-T3 the Sokal estimator on known series (AR(1) tau 1.5, white noise tau 0.5, a random walk that never
converges is a lower bound); T4 the tool's tiny run writes the header and exactly 2 rows; T4b the random row equals an outside recomputation; T5 combine is a total table on forms;
T6 a constant series has no tau. Reads the author's data root (cc.toml [check] needs_data).
Seen RED on 1f4ab4b (tests/tau_1282_p1.py absent); T4b also seen RED by mutation (tau_M0 fed O[:,0] instead of |O[:,1]|).
P1a.1: T7 seen RED on c1175fa."""
import importlib.util
import math
import os
import shutil
import subprocess
import sys
import tempfile
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
from lib import bad, bootstrap, check, guarded  # noqa: E402
bootstrap(ROOT, "cc", "cc/instruments")
import numpy as np  # noqa: E402
import schema  # noqa: E402

REAL = schema.resolve_data_root(tomllib.loads((ROOT / "cc.toml").read_text()))[0]
TOOL = ROOT / "tests" / "tau_1282_p1.py"


def tool():
    spec = importlib.util.spec_from_file_location("tau_1282_p1", TOOL)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def t1_t3():
    m, rng = tool(), np.random.default_rng(12345)
    e = rng.standard_normal(200_000)
    ar = np.empty_like(e)
    ar[0] = e[0]
    for i in range(1, len(e)):
        ar[i] = 0.5 * ar[i - 1] + e[i]
    r = m.tau_sokal(ar, len(ar) // 10)
    check("T1 AR(1) phi 0.5: tau within 5 % of 1.5, converged", r.form == "converged" and abs(r.tau - 1.5) <= 0.075, str(r))
    r = m.tau_sokal(e, len(e) // 10)
    check("T2 white noise: tau within 0.05 of 0.5, converged", r.form == "converged" and abs(r.tau - 0.5) <= 0.05, str(r))
    w = np.cumsum(np.random.default_rng(12345).standard_normal(20_000))
    r = m.tau_sokal(w, len(w) // 10)
    check("T3 a random walk: lower-bound at W == 2000", r.form == "lower-bound" and r.W == 2000, str(r))


def t5_t6():
    m = tool()
    T, U = m.Tau, m.Tau(None, 0, "undefined")
    cases = [((U, T(4.0, 20, "converged")), U), ((T(3.0, 15, "lower-bound"), T(4.0, 20, "converged")), T(4.0, 20, "lower-bound")),
             ((T(2.0, 10, "converged"), T(1.0, 5, "converged")), T(2.0, 10, "converged"))]
    for (a, b), want in cases:
        check(f"T5 combine({a.form}, {b.form}) both orders", m.combine(a, b) == want and m.combine(b, a) == want, f"{m.combine(a, b)} / {m.combine(b, a)}")
    for v in (0.1, 0.0):
        check(f"T6 np.full(1000, {v}) is undefined", m.tau_sokal(np.full(1000, v), 100) == U, str(m.tau_sokal(np.full(1000, v), 100)))


def t4():
    import sampler
    m, tmp = tool(), Path(tempfile.mkdtemp(prefix="t4-"))
    try:
        out = tmp / "tiny.tsv"
        r = subprocess.run([sys.executable, str(TOOL), "--toolset", str(sampler.toolset_of(Path(os.environ["CC_DATA_ROOT"]))), "--out", str(out), "--procs", "2", "--cells", "tiny"],
                           capture_output=True, text=True, cwd=ROOT)
        rows = [ln.split("\t") for ln in out.read_text().splitlines()] if out.is_file() else []
        check("T4 the tiny run exits 0 and ends DONE 2 rows", r.returncode == 0 and r.stdout.strip().splitlines()[-1] == "DONE 2 rows", (r.stdout + r.stderr)[-400:])
        check("T4 the TSV is the header and exactly 2 rows", len(rows) == 3 and rows[0] == m.HEAD and all(len(x) == len(m.HEAD) for x in rows), str(rows)[:300])
        row = next(x for x in rows[1:] if x[3] == "random")
        t = sampler.load(sampler.toolset_of(REAL))
        run = sampler.Run(200, 1, 20)
        ch, _ = sampler.sample(t, sampler.LABELS["1.00"], sampler.FAMILY_H["poc"], 27, "random", sampler.seed_of("1282-v10", "poc", "1.00", 27, "random", "pilot"), run)
        wm = run.N // 10
        m0, m1, g1 = (m.tau_sokal(a, wm) for a in (np.abs(ch.O[:, 1]), np.abs(ch.M1), ch.G[:, 1]))
        ti = m.combine(m0, m1)
        tn = lambda x: "undefined" if x.tau is None else repr(float(x.tau))  # noqa: E731
        cnt = {"converged": ("", ""), "lower-bound": (">=", ">="), "undefined": None}[ti.form]   # A4.3: skip 2 tau, burn 20 tau, a count only; a lower bound is prefixed
        sb = ("undefined", "undefined") if cnt is None else (cnt[0] + str(math.ceil(2 * ti.tau)), cnt[1] + str(math.ceil(20 * ti.tau)))
        want = ["poc", "1.00", "27", "random", "200", tn(m0), str(m0.W), m0.form, tn(m1), str(m1.W), m1.form, tn(ti), ti.form, tn(g1), str(g1.W), g1.form, *sb]
        check("T4b the random row equals the outside recomputation (all but wall_s, host)", row[:len(want)] == want, f"{row[:len(want)]} vs {want}")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def t7():
    import sampler
    import types
    m = tool()
    N = 20000
    rng = np.random.default_rng(7)
    e = rng.standard_normal(N)
    a = np.zeros(N)
    for t in range(1, N):
        a[t] = 0.5 * a[t - 1] + e[t]
    sgn = np.array([1 if (t // 1000) % 2 == 0 else -1 for t in range(N)])
    M1 = sgn * (5.0 + a)
    ch = types.SimpleNamespace(O=np.stack([np.zeros(N), np.abs(M1)], 1), G=np.stack([np.zeros(N), a], 1), M1=M1)
    r = m.fields("poc", "1.00", 27, "random", sampler.Run(20000, 1, 2000), ch)
    want = m.tau_sokal(np.abs(M1), 2000)
    check("T7 tau_M1 is tau of |M1|", r[8] == m.tn(want) and r[10] == want.form, f"{r[8]} {r[10]} vs {m.tn(want)} {want.form}")
    check("T7 the sign flips do not set tau_M1", r[8] != m.tn(m.tau_sokal(M1, 2000)), f"{r[8]}")


for n, f in (("T1-T3", t1_t3), ("T4", t4), ("T5-T6", t5_t6), ("T7", t7)):
    guarded(n, f)
print("test_tau_1282: " + ("FAILED" if bad else "all passed"))
sys.exit(1 if bad else 0)
