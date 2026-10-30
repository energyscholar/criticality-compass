"""tau_1282_p1 - plan 1282 P1a: the tau_int pilot (A4.7, A4.8). One adapter call per cell of the 84, three integrated autocorrelation times (Sokal, c = 5,
window_max = N // 10) of level-0 |M|, level-1 block M and level-1 g1, one TSV row per cell. A tool, not a test: python tests/tau_1282_p1.py --toolset <dir> [--cells tiny|all] [--out F] [--time-only].
A window that reaches window_max is a lower bound (never re-run); a series that does not vary has no tau (undefined); a cell is never shortened to fit a budget.
P1a.1 (PRE A4.11): the second input is |level-1 block M|, matching the |.| A4.7 puts on level 0."""
import os

os.environ["OMP_NUM_THREADS"] = os.environ["OPENBLAS_NUM_THREADS"] = "1"   # before numpy loads: one core per worker
import argparse
import dataclasses
import itertools
import math
import multiprocessing
import platform
import sys
import time
from pathlib import Path

sys.path[:0] = [str(Path(__file__).resolve().parent.parent / "cc")]
import numpy as np  # noqa: E402
import gamma  # noqa: E402
import sampler  # noqa: E402
from sampler import Run  # noqa: E402

S = "1282-v10"
PILOT = Run(20000, 1, 2000)
TINY = Run(200, 1, 20)
ROWS = {"all": 84, "tiny": 2}
RANK = {"converged": 0, "lower-bound": 1, "undefined": 2}   # the order of severity of a form
HEAD = "F k L start N tau_M0 W_M0 form_M0 tau_M1 W_M1 form_M1 tau_int form_int tau_G1 W_G1 form_G1 skip burn wall_s host".split()


@dataclasses.dataclass(frozen=True)
class Tau:
    tau: float
    W: int
    form: str


UNDEFINED = Tau(None, 0, "undefined")


def tau_sokal(a, wmax, c=5):
    """Integrated autocorrelation time with Sokal's automatic window: the smallest W <= wmax with W >= c tau(W); none: the lower bound tau(wmax)."""
    if np.ptp(a) == 0:
        return UNDEFINED
    g = gamma.autocov(np.asarray(a, float)[:, None], wmax)[:, 0, 0]
    tau = 0.5 + np.concatenate([[0.0], np.cumsum(g[1:] / g[0])])   # tau[W], W = 0..wmax
    hit = np.flatnonzero(np.arange(1, wmax + 1) >= c * tau[1:]) + 1
    return Tau(float(tau[hit[0]]), int(hit[0]), "converged") if hit.size else Tau(float(tau[wmax]), wmax, "lower-bound")


def combine(a, b):
    """tau_int of two readings: undefined if either is; else lower-bound if either is; the larger tau, with its W."""
    form = max(a.form, b.form, key=RANK.__getitem__)
    top = max((a, b), key=lambda x: -1.0 if x.tau is None else x.tau)
    return UNDEFINED if form == "undefined" else Tau(top.tau, top.W, form)


def num(x):
    return repr(float(x))


COUNT = {"converged": lambda t: (str(math.ceil(2 * t.tau)), str(math.ceil(20 * t.tau))),   # A4.3: skip 2 tau, burn 20 tau, a count only
         "lower-bound": lambda t: (">=" + str(math.ceil(2 * t.tau)), ">=" + str(math.ceil(20 * t.tau))),
         "undefined": lambda t: ("undefined", "undefined")}


def tn(t):
    return "undefined" if t.tau is None else num(t.tau)


def fields(F, k, L, s, run, ch):
    """The TSV columns of one cell up to burn, from its chain."""
    wmax = run.N // 10
    m0, m1, g1 = (tau_sokal(a, wmax) for a in (np.abs(ch.O[:, 1]), np.abs(ch.M1), ch.G[:, 1]))
    ti = combine(m0, m1)
    return [F, k, str(L), s, str(run.N), tn(m0), str(m0.W), m0.form, tn(m1), str(m1.W), m1.form, tn(ti), ti.form, tn(g1), str(g1.W), g1.form, *COUNT[ti.form](ti)]


TOOLS = None


def init(toolset):
    global TOOLS
    TOOLS = sampler.load(toolset)


def cell(task):
    F, k, L, s, run = task
    t0 = time.perf_counter()
    ch, _ = sampler.sample(TOOLS, sampler.LABELS[k], sampler.FAMILY_H[F], L, s, sampler.seed_of(S, F, k, L, s, "pilot"), run)
    return fields(F, k, L, s, run, ch) + [f"{time.perf_counter() - t0:.1f}", platform.node()]


def cells(which):
    if which == "tiny":
        return [("poc", "1.00", 27, s, TINY) for s in ("random", "ordered")]
    return [(F, k, L, s, PILOT) for L in sorted(sampler.SIZES, reverse=True) for F, k, s in itertools.product(sampler.FAMILY_H, sampler.LABELS, sampler.STARTS)]


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument("--toolset", required=True)
    ap.add_argument("--out")
    ap.add_argument("--procs", type=int, default=1)
    ap.add_argument("--timeout", type=float, default=600)
    ap.add_argument("--cells", choices=sorted(ROWS), default="all")
    ap.add_argument("--time-only", action="store_true")
    a = ap.parse_args(argv)
    if a.out is None and not a.time_only:
        ap.error("--out is required unless --time-only")
    tools = sampler.load(a.toolset)
    if isinstance(tools, sampler.Mismatch):
        print(f"pinned tool does not match: {tools.file}")
        return 1
    if a.time_only:
        t0 = time.process_time()
        init(a.toolset)
        cell(("poc", "1.00", 243, "random", PILOT))
        t = time.process_time() - t0
        print(f"TIME cpu_s={t:.1f} projection_core_hours={t * 2548 / 81 / 3600:.2f}")   # sum over the 84 cells of (L/243)^2 = 28 x (1 + 1/9 + 1/81)
        return 0
    todo = cells(a.cells)
    with multiprocessing.Pool(a.procs, init, (a.toolset,)) as pool:
        pending = [pool.apply_async(cell, (t,)) for t in todo]
        try:
            rows = [p.get(timeout=a.timeout) for p in pending]
        except multiprocessing.TimeoutError:
            print(f"blocked: a cell exceeded {a.timeout} s; no retry")
            pool.terminate()
            return 2
    assert len(rows) == ROWS[a.cells], f"{len(rows)} rows, not {ROWS[a.cells]}"
    Path(a.out).write_text("\n".join("\t".join(r) for r in [HEAD, *rows]) + "\n")
    print(f"DONE {len(rows)} rows")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
