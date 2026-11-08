"""tau_1282_rung0 - plan 1282 P2c: rung 0. 41 declared chains on the compiled heat bath (14 cells), the tau_int of each, the stripe count of the ten random chains of the three
below-T_c cells, the sampler's timing, and the core-hour cost tables of the frozen run. Counts only: no detect, no verdict, no seal. A tool, not a test.
python tests/tau_1282_rung0.py [--out DIR] [--procs 4] [--timeout S] (--smoke | --bench | --project BENCH | --run | --collect | --cost RUNG0 PILOT BENCH)
The toolset comes only from CC_DATA_ROOT (sampler.toolset_of). A lower bound or an undefined tau is a VALUE (the Tau forms of tau_1282_p1), never a retry or a longer chain.
Every mode ends on ONE finish line: `DONE <what>`, or `BLOCKED <reason>` (exit 2)."""
import os

os.environ["OMP_NUM_THREADS"] = os.environ["OPENBLAS_NUM_THREADS"] = "1"   # before numpy loads: one core per worker
import argparse
import dataclasses
import hashlib
import importlib.util
import math
import multiprocessing
import platform
import statistics
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(HERE.parent / "cc")]
import numpy as np  # noqa: E402
import sampler  # noqa: E402
from sampler import Run  # noqa: E402


def _p1():
    spec = importlib.util.spec_from_file_location("tau_1282_p1", HERE / "tau_1282_p1.py")
    m = importlib.util.module_from_spec(spec)
    sys.modules["tau_1282_p1"] = m   # a dataclass defined there looks its module up by name
    spec.loader.exec_module(m)
    return m


P1 = _p1()
tau_sokal, combine, Tau, UNDEFINED = P1.tau_sokal, P1.combine, P1.Tau, P1.UNDEFINED

S = "1282-v10"
F = "poc"
KC = sampler.KC
GRID = (1, 10, 100)      # the skip ladder of a rung 0 chain
BGRID = (1, 10, 100, 1000)   # the bench ladder of the cost formula
SWEEPS = {27: 200_000, 81: 40_000, 243: 10_000}   # bench sweeps per measurement, by L
BELOW = ("1.02", "1.05", "1.10")   # the below-T_c labels whose random start takes the ordered tau
HOST_SAFE = platform.node()


# ---- the declared chain table (the brief's 14 cells) ----
@dataclasses.dataclass(frozen=True)
class Cell:
    n: int            # row number in the brief's table
    k: str
    L: int
    start: str
    chains: int
    tau_low: float    # the lower end of the WIDE band; cells 9-11 take their ordered partner's
    burn: int
    N: int


CELLS = (
    Cell(1, "1.00", 27, "ordered", 1, 58, 5_000, 200_000),
    Cell(2, "1.00", 27, "random", 1, 58, 5_000, 200_000),
    Cell(3, "1.00", 81, "ordered", 1, 630, 30_000, 200_000),
    Cell(4, "1.00", 81, "random", 1, 630, 30_000, 200_000),
    Cell(5, "0.98", 81, "ordered", 1, 185, 100_000, 200_000),
    Cell(6, "1.00", 243, "ordered", 1, 6_800, 320_000, 240_000),
    Cell(7, "1.00", 243, "random", 1, 6_800, 320_000, 240_000),
    Cell(8, "0.98", 243, "ordered", 1, 133, 200_000, 200_000),
    Cell(9, "1.02", 243, "random", 10, 60, 60_000, 200_000),
    Cell(10, "1.05", 243, "random", 10, 21, 60_000, 200_000),
    Cell(11, "1.10", 243, "random", 10, 6.8, 60_000, 200_000),
    Cell(12, "1.02", 243, "ordered", 1, 60, 2_000, 200_000),
    Cell(13, "1.05", 243, "ordered", 1, 21, 2_000, 200_000),
    Cell(14, "1.10", 243, "ordered", 1, 6.8, 2_000, 200_000),
)


def skip_of(tau_low):
    """The skip rule: the largest of {1, 10, 100} that is <= tau_low / 10 (1 is the base of the ladder)."""
    return max([GRID[0]] + [g for g in GRID[1:] if g <= tau_low / 10])


def tags_of(c):
    return ("rung0",) if c.chains == 1 else tuple(f"rung0.{j}" for j in range(c.chains))


@dataclasses.dataclass(frozen=True)
class Chain:
    cell: Cell
    tag: str
    run: Run

    @property
    def stem(self):
        return f"rung0_poc_{self.cell.k}_L{self.cell.L}_{self.cell.start}_{self.tag}"

    @property
    def seed(self):
        return sampler.seed_of(S, F, self.cell.k, self.cell.L, self.cell.start, self.tag)

    @property
    def sweeps(self):
        return self.run.burn + self.run.N * self.run.skip


def chain_table():
    """The 41 chains in table order then tag."""
    return [Chain(c, t, Run(c.N, skip_of(c.tau_low), c.burn)) for c in CELLS for t in tags_of(c)]


def bench_seed(L, s):
    return sampler.seed_of(S, F, "1.00", L, "random", f"rung0-bench.{s}")


def contended_seed(i):
    return sampler.seed_of(S, F, "1.00", 243, "random", f"rung0-bench.c{i}")


# ---- the stripe partition: the side of the midpoint of the two attractors ----
def stripe_class(m, m_ord):
    return "ABOVE_MID" if m >= 0.5 * m_ord else "BELOW_MID"


# ---- timing ----
@dataclasses.dataclass(frozen=True)
class Bench:
    y: dict   # (L, s) -> ms per yield, 1 process, median process_time
    b: dict   # L -> ms per sweep of a burn call, 1 process, median process_time


def num(x):
    return repr(float(x))


def tn(t):
    return "undefined" if t.tau is None else num(t.tau)


# ---- the cost formula (the checkable form the owner's R5 needs) ----
def core_hours(cells, taus, bench, N, f=1.0):
    """(total, rows). cells: list of (F, k, L, s). taus: {cell: (tau, source, form)}; an `ordered-of` cell is resolved from its (F, k, L, "ordered") partner in taus (the partner
    need not be in `cells`). skip_c = ceil(2 tau), burn_c = ceil(20 tau) (an `ordered-of` cell: max(that, L^2)), s* = the largest of {1, 10, 100, 1000} <= skip_c, per-yield cost
    y(L, s*) * skip_c / s*. core-h = f * sum over cells of 10 * [burn_c * b(L) + N * per-yield] / 3.6e6 (y, b in ms)."""
    rows, ms = [], 0.0
    for cell in cells:
        Fm, k, L, s = cell
        tau, source, form = taus[cell]
        if source == "ordered-of":
            tau, _, form = taus[(Fm, k, L, "ordered")]
        skip = math.ceil(2 * tau)
        burn = math.ceil(20 * tau)
        burn = max(burn, L * L) if source == "ordered-of" else burn
        sstar = max(g for g in BGRID if g <= skip)
        per_yield = bench.y[(L, sstar)] * skip / sstar
        chain_ms = burn * bench.b[L] + N * per_yield
        ms += 10 * chain_ms
        rows.append(dict(F=Fm, k=k, L=L, s=s, tau=tau, source=source, form=form, skip=skip, burn=burn, sstar=sstar, sweeps=burn + N * skip,
                         chain_core_h=f * chain_ms / 3.6e6, core_h=f * 10 * chain_ms / 3.6e6))
    return f * ms / 3.6e6, rows


def pred_f1(ch, bench):
    """A rung 0 chain's f = 1 prediction in core-h: its declared burn and skip (not tau-derived)."""
    L, r = ch.cell.L, ch.run
    return (r.burn * bench.b[L] + r.N * bench.y[(L, r.skip)]) / 3.6e6


def read_tsv(path):
    """A TSV whose first line is the header (a leading `# ` is not part of the first name); a row is a dict."""
    lines = [ln.split("\t") for ln in Path(path).read_text().splitlines() if ln]
    head = [lines[0][0].removeprefix("# ")] + lines[0][1:]
    return [dict(zip(head, r)) for r in lines[1:]]


def read_bench(path):
    """BENCH -> (Bench, y4, rows): the procs = 1 rows give y and b; the procs = 4 rows give y4 (their median)."""
    rows = read_tsv(path)
    one = [r for r in rows if r["procs"] == "1"]
    four = [float(r["y_med"]) for r in rows if r["procs"] == "4"]
    y = {(int(r["L"]), int(r["s"])): float(r["y_med"]) for r in one}
    b = {int(r["L"]): float(r["b_med"]) for r in one}
    return Bench(y, b), statistics.median(four), rows


# ---- one chain ----
TOOLS = None


def init():
    global TOOLS
    TOOLS = sampler.load(sampler.toolset_of(os.environ["CC_DATA_ROOT"]))
    if isinstance(TOOLS, sampler.Mismatch):
        raise SystemExit(f"BLOCKED pinned tool does not match: {TOOLS.file}")


ROW_HEAD = ("k L start tag burn skip N seed build tau_M0_samples W_M0 form_M0 tau_M1_samples W_M1 form_M1 tau_G1_samples W_G1 form_G1 tau_int_sweeps sigma form_int "
            "mean_absM0_last10 mean_E_last10 mean_g1_last10 cpu_s wall_s host load_at_start").split()


def chain_row(ch, out):
    """Run one chain, write <stem>.tmp.npz -> <stem>.npz and <stem>.json, return its row (also written to rows/<stem>.tsv, tmp + rename)."""
    load0 = os.getloadavg()[0]
    c0, w0 = time.process_time(), time.perf_counter()
    chain, call = sampler.sample(TOOLS, sampler.LABELS[ch.cell.k], sampler.FAMILY_H[F], ch.cell.L, ch.cell.start, ch.seed, ch.run)
    cpu, wall = time.process_time() - c0, time.perf_counter() - w0
    out = Path(out)
    (out / "rows").mkdir(parents=True, exist_ok=True)
    tmp = out / f"{ch.stem}.tmp.npz"
    sampler.write(chain, tmp)
    os.replace(tmp, out / f"{ch.stem}.npz")
    sampler.write_call(call, out / f"{ch.stem}.npz")
    wmax = ch.run.N // 10
    m0, m1, g1 = (tau_sokal(a, wmax) for a in (np.abs(chain.O[:, 1]), np.abs(chain.M1), chain.G[:, 1]))
    ti = combine(m0, m1)
    sk, last, L = ch.run.skip, ch.run.N // 10, ch.cell.L
    tsw = None if ti.tau is None else sk * ti.tau
    sig = "undefined" if ti.tau is None else num(tsw * math.sqrt(2 * (2 * ti.W + 1) / ch.run.N))
    row = [ch.cell.k, str(L), ch.cell.start, ch.tag, str(ch.run.burn), str(sk), str(ch.run.N), str(ch.seed), call.build,
           tn(m0), str(m0.W), m0.form, tn(m1), str(m1.W), m1.form, tn(g1), str(g1.W), g1.form,
           "undefined" if tsw is None else num(tsw), sig, ti.form,
           num(np.mean(np.abs(chain.O[-last:, 1])) / L**2), num(np.mean(chain.O[-last:, 0]) / (2 * L**2)), num(np.mean(chain.G[-last:, 1])),
           f"{cpu:.3f}", f"{wall:.3f}", platform.node(), f"{load0:.2f}"]
    p = out / "rows" / f"{ch.stem}.tsv"
    q = p.with_name(p.name + ".tmp")
    q.write_text("\t".join(ROW_HEAD) + "\n" + "\t".join(row) + "\n")
    os.replace(q, p)
    return row


def worker(ch, out):
    init()
    chain_row(ch, out)


def pool_run(chains, out, procs, timeout):
    """chains longest first, `procs` at a time, one OS process per chain (so each has its own clock). Returns None, or the BLOCKED reason of the first failure (no retry)."""
    todo = [c for c in sorted(chains, key=lambda c: -c.sweeps) if not (Path(out) / "rows" / f"{c.stem}.tsv").is_file()]
    live = []
    ctx = multiprocessing.get_context("spawn")
    while todo or live:
        while todo and len(live) < procs:
            c = todo.pop(0)
            p = ctx.Process(target=worker, args=(c, str(out)))
            p.start()
            live.append((c, p, time.monotonic()))
            print(f"START {c.stem}", flush=True)
        time.sleep(1.0)
        for item in list(live):
            c, p, t0 = item
            if p.exitcode is None and time.monotonic() - t0 > timeout:
                p.kill()
                p.join()
                reason = f"BLOCKED {c.stem} exceeded {timeout} s"
            elif p.exitcode is not None and p.exitcode != 0:
                reason = f"BLOCKED {c.stem} exit code {p.exitcode}"
            else:
                if p.exitcode == 0:
                    live.remove(item)
                    print(f"FINISHED {c.stem} after {time.monotonic() - t0:.0f} s", flush=True)
                continue
            for _, q, _ in live:
                if q.is_alive():
                    q.kill()
            return reason
    return None


# ---- modes ----
def smoke(out, procs):
    tiny = Run(200, 1, 20)
    chains = [Chain(c, "rung0", tiny) for c in CELLS[:2]]
    reason = pool_run(chains, out, procs, 600)
    if reason:
        print(reason)
        return 2
    for c in chains:
        print("\t".join(read_tsv(Path(out) / "rows" / f"{c.stem}.tsv")[0].values()))
    print("DONE smoke")
    return 0


def _med_min(xs):
    return statistics.median(xs), min(xs)


def measure(tools, L, s, repeats=3):
    """(y_med, y_min, wall_med, b-free) for L, s: process_time and perf_counter ms per yield of sample(..., Run(n, s, 0))."""
    n = SWEEPS[L] // s
    cpu, wall = [], []
    for _ in range(repeats):
        c0, w0 = time.process_time(), time.perf_counter()
        sampler.sample(tools, KC, 0.0, L, "random", bench_seed(L, s), Run(n, s, 0))
        cpu.append((time.process_time() - c0) * 1000 / n)
        wall.append((time.perf_counter() - w0) * 1000 / n)
    return n, cpu, wall


def burn_cost(tools, L, repeats=3):
    B = SWEEPS[L]
    cpu, wall = [], []
    for _ in range(repeats):
        c0, w0 = time.process_time(), time.perf_counter()
        sampler.sample(tools, KC, 0.0, L, "random", bench_seed(L, 1), Run(1, 1, B))
        cpu.append((time.process_time() - c0) * 1000 / B)
        wall.append((time.perf_counter() - w0) * 1000 / B)
    return cpu, wall


def contended_worker(i, barrier, q):
    init()
    barrier.wait()
    load0 = os.getloadavg()[0]
    n = SWEEPS[243] // 100
    cpu, wall = [], []
    for _ in range(3):
        c0, w0 = time.process_time(), time.perf_counter()
        sampler.sample(TOOLS, KC, 0.0, 243, "random", contended_seed(i), Run(n, 100, 0))
        cpu.append((time.process_time() - c0) * 1000 / n)
        wall.append((time.perf_counter() - w0) * 1000 / n)
    q.put((i, n, cpu, wall, load0, os.getloadavg()[0], TOOLS.build))


BENCH_HEAD = "host build numpy python L s n y_med y_min b_med wall_med procs load_before load_after cpu_over_wall".split()


def bench(out):
    init()
    rows = []
    for L in (27, 81, 243):
        bcpu, bwall = burn_cost(TOOLS, L)
        for s in BGRID:
            l0 = os.getloadavg()[0]
            n, cpu, wall = measure(TOOLS, L, s)
            l1 = os.getloadavg()[0]
            ym, yn = _med_min(cpu)
            wm = statistics.median(wall)
            rows.append([HOST_SAFE, TOOLS.build, np.__version__, platform.python_version(), str(L), str(s), str(n), num(ym), num(yn), num(statistics.median(bcpu)),
                         num(wm), "1", f"{l0:.2f}", f"{l1:.2f}", num(ym / wm)])
    ctx = multiprocessing.get_context("spawn")
    barrier, q = ctx.Barrier(4), ctx.Queue()
    ps = [ctx.Process(target=contended_worker, args=(i, barrier, q)) for i in range(4)]
    [p.start() for p in ps]
    res = sorted(q.get() for _ in ps)
    [p.join() for p in ps]
    for i, n, cpu, wall, l0, l1, build in res:
        ym, yn = _med_min(cpu)
        wm = statistics.median(wall)
        rows.append([HOST_SAFE, build, np.__version__, platform.python_version(), "243", "100", str(n), num(ym), num(yn), "NA", num(wm), "4", f"{l0:.2f}", f"{l1:.2f}", num(ym / wm)])
    (Path(out)).mkdir(parents=True, exist_ok=True)
    (Path(out) / "bench.tsv").write_text("\t".join(BENCH_HEAD) + "\n" + "\n".join("\t".join(r) for r in rows) + "\n")
    for r in rows:
        print("\t".join(r))
    print("DONE bench")
    return 0


def factor_pre(bench_, y4):
    return max(1.7, y4 / bench_.y[(243, 100)])


def project(bench_path, procs):
    bn, y4, _ = read_bench(bench_path)
    fpre = factor_pre(bn, y4)
    preds = [pred_f1(c, bn) for c in chain_table()]
    quiet, cont = sum(preds), fpre * sum(preds)
    c_h = fpre * max(preds)
    w_h = max(cont / procs, c_h)
    print(f"f_pre={fpre:.4f} y4={y4:.4f} y_243_100={bn.y[(243, 100)]:.4f}")
    if cont > 20:
        print(f"BLOCKED projection {cont:.2f} > 20")
        return 2
    print(f"PROJECTION quiet_core_h={quiet:.3f} contended_core_h={cont:.3f} longest_chain_h={c_h:.3f} wall_h={w_h:.3f} timeout_s={math.ceil(3 * c_h * 3600)} watch_limit_h={3 * w_h:.3f}")
    print("DONE project")
    return 0


def rows_of(out):
    chains = chain_table()
    rows = {}
    for c in chains:
        p = Path(out) / "rows" / f"{c.stem}.tsv"
        if not p.is_file():
            return None, f"BLOCKED collect: no row for {c.stem}"
        rows[c.stem] = read_tsv(p)[0]
    return (chains, rows), None


def collect(out):
    got, why = rows_of(out)
    if why:
        print(why)
        return 2
    chains, rows = got
    lines = ["# " + "\t".join(ROW_HEAD)] + ["\t".join(rows[c.stem][k] for k in ROW_HEAD) for c in chains]
    (Path(out) / "rung0.tsv").write_text("\n".join(lines) + "\n")
    m_ord = {c.cell.k: float(rows[c.stem]["mean_absM0_last10"]) for c in chains if c.cell.n in (12, 13, 14)}   # the ordered partner of cells 9-11: same k, same L
    sh = "k L tag seed m m_ord g1 E tau_M0 form class".split()
    sl, per = ["\t".join(sh)], {k: 0 for k in BELOW}
    for c in chains:
        if c.cell.n in (9, 10, 11):
            r = rows[c.stem]
            m, mo = float(r["mean_absM0_last10"]), m_ord[c.cell.k]
            cls = stripe_class(m, mo)
            per[c.cell.k] += cls == "BELOW_MID"
            tm0 = "undefined" if r["tau_M0_samples"] == "undefined" else num(int(r["skip"]) * float(r["tau_M0_samples"]))
            sl.append("\t".join([c.cell.k, "243", c.tag, r["seed"], r["mean_absM0_last10"], num(mo), r["mean_g1_last10"], r["mean_E_last10"], tm0, r["form_M0"], cls]))
    for k in BELOW:
        sl.append(f"k_of_10\t{k}\t{per[k]}")
    sl.append(f"k_of_30\t{sum(per.values())}")
    (Path(out) / "stripes.tsv").write_text("\n".join(sl) + "\n")
    print(f"k_of_10 {per} k_of_30 {sum(per.values())}")
    print("DONE collect")
    return 0


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def all_cells():
    return [(Fm, k, L, s) for Fm, k, L, s in sampler.cells()]


RUNG0_CELLS = {(F, c.k, c.L, c.start) for c in CELLS if c.chains == 1}


def cell_taus(rung0_rows, pilot_rows):
    """The total table over the 84 cells: {cell: (tau, source, form)}, and each rung 0 cell's own tau. `ordered-of`: poc random at a below-T_c label (its tau is its ordered partner's);
    `rung0`: the other single-chain rung 0 cells; `pilot` (the tau_int column of PILOT): every other cell, and every decoy cell."""
    r0 = {(r["k"], int(r["L"]), r["start"]): r for r in rung0_rows if r["tag"] == "rung0"}
    pil = {(r["F"], r["k"], int(r["L"]), r["start"]): r for r in pilot_rows}
    own = {}
    for c in CELLS:
        key = (F, c.k, c.L, c.start)
        if c.chains == 1:
            r = r0[(c.k, c.L, c.start)]
            if r["tau_int_sweeps"] == "undefined":
                raise SystemExit(f"BLOCKED cost: tau is undefined at {key}")
            own[key] = (float(r["tau_int_sweeps"]), r["form_int"])
        else:
            rs = [r for r in rung0_rows if (r["k"], int(r["L"]), r["start"]) == (c.k, c.L, c.start)]
            ts = [float(r["tau_int_sweeps"]) for r in rs if r["tau_int_sweeps"] != "undefined"]
            own[key] = (statistics.median(ts), f"median of {len(ts)}/{len(rs)} defined, {sum(r['form_int'] == 'converged' for r in rs)} converged")
    taus = {}
    for cell in all_cells():
        Fm, k, L, s = cell
        if Fm == F and s == "random" and k in BELOW:
            taus[cell] = (None, "ordered-of", None)
        elif cell in RUNG0_CELLS:
            taus[cell] = (own[cell][0], "rung0", own[cell][1])
        else:
            r = pil[cell]
            taus[cell] = (float(r["tau_int"]), "pilot", r["form_int"])
    return taus, own, pil


def cost(rung0_path, pilot_path, bench_path, out):
    bn, y4, brows = read_bench(bench_path)
    rung0_rows = read_tsv(rung0_path)
    pilot_rows = read_tsv(pilot_path)
    taus, own, pil = cell_taus(rung0_rows, pilot_rows)
    cells = all_cells()
    chains = chain_table()
    r0 = {(r["k"], int(r["L"]), r["start"], r["tag"]): r for r in rung0_rows}
    rho = [float(r0[(c.cell.k, c.cell.L, c.cell.start, c.tag)]["cpu_s"]) / (pred_f1(c, bn) * 3600) for c in chains]
    f_pre = factor_pre(bn, y4)
    rho_med = statistics.median(rho)
    f_final = max(1.7, y4 / bn.y[(243, 100)], rho_med)
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    _, base = core_hours(cells, taus, bn, 1000)
    inp = ["F k L s tau_c source form tau_own N_pilot_over_tau flag skip burn sstar".split()]
    short = set()
    for r in base:
        cell = (r["F"], r["k"], r["L"], r["s"])
        o = own.get(cell)
        npt = ""
        flag = ""
        if r["source"] == "pilot":
            npt = num(20000 / r["tau"])
            if 20000 / r["tau"] < 200:
                flag = "PILOT-SHORT"
                short.add(cell)
        inp.append([r["F"], r["k"], str(r["L"]), r["s"], num(r["tau"]), r["source"], r["form"], "none" if o is None else num(o[0]) + " (" + o[1] + ")", npt, flag, str(r["skip"]), str(r["burn"]), str(r["sstar"])])
    (out / "cost-inputs.tsv").write_text("\n".join("\t".join(x) for x in inp) + "\n")
    summary = {}
    for N in (1000, 4000):
        quiet, rows = core_hours(cells, taus, bn, N)
        cont = quiet * f_final
        worst = sum(r["core_h"] * (4 if (r["F"], r["k"], r["L"], r["s"]) in short else 1) for r in rows) * f_final
        floor = any(r["form"] == "lower-bound" for r in rows)
        lines = ["F k L s tau_c source form sweeps_per_chain core_h_quiet core_h_contended chain_h_contended".split()]
        for r in rows:
            lines.append([r["F"], r["k"], str(r["L"]), r["s"], num(r["tau"]), r["source"], r["form"], str(r["sweeps"]), num(r["core_h"]), num(r["core_h"] * f_final), num(r["chain_core_h"] * f_final)])
        txt = ["\t".join(x) for x in lines] + [""]
        for L in (27, 81, 243):
            txt.append(f"TOTAL_L{L} quiet={sum(r['core_h'] for r in rows if r['L'] == L):.4f} contended={f_final * sum(r['core_h'] for r in rows if r['L'] == L):.4f}")
        share = sum(r["core_h"] for r in rows if (r["k"], r["L"]) == ("1.00", 243) and r["F"] == F)
        txt.append(f"SHARE_poc_1.00_243 quiet={share:.4f} fraction_of_quiet_total={share / quiet:.4f}")
        txt.append(f"GRAND_QUIET {quiet:.4f}")
        txt.append(f"GRAND_CONTENDED {cont:.4f}   (f_final={f_final:.4f}; the line the R5 gate reads)")
        txt.append(f"GRAND_CONTENDED_PILOTSHORT_WORST {worst:.4f}   ({len(short)} PILOT-SHORT cells x 4)")
        if floor:
            txt.append("FLOOR: a lower-bound tau entered " + "; ".join(sorted(f"{r['F']},{r['k']},{r['L']},{r['s']}" for r in rows if r["form"] == "lower-bound")))
        (out / f"cost-N{N}.tsv").write_text("\n".join(txt) + "\n")
        longest = max(r["chain_core_h"] for r in rows) * f_final
        summary[N] = (quiet, cont, worst, longest, floor)
    # the worked row
    wc = (F, "1.00", 243, "random")
    t = taus[wc]
    _, wr = core_hours([wc], taus, bn, 4000)
    w = wr[0]
    per_y = bn.y[(243, w["sstar"])] * w["skip"] / w["sstar"]
    # the reducer overstatement at L = 243: the model scales y(s*) by skip/s*, the true cost is skip * b + r (r = y(243,1) - b(243))
    r_hat = bn.y[(243, 1)] - bn.b[243]
    over = (w["skip"] / w["sstar"] - 1) * r_hat / (w["skip"] / w["sstar"] * bn.y[(243, w["sstar"])])
    md = ["# cost-DERIVATION", "", "All numbers are produced by tests/tau_1282_rung0.py --cost; hand-check them against these inputs.", "",
          "## Formula (verbatim)",
          "core-h(N) = f * sum_c 10 * [ burn_c * b(L) + N * y(L, s*_c) * skip_c / s*_c ] / 3.6e6   (y, b in ms; 1-process median process_time; 10 chains per cell)",
          "skip_c = ceil(2 tau_c); burn_c = ceil(20 tau_c), except `ordered-of` cells: burn_c = max(ceil(20 tau_c), L^2) (the burn rule Argus will declare in A5: an assumption);",
          "s*_c = the largest of {1,10,100,1000} <= skip_c; f = 1 (QUIET) or f_final (CONTENDED); a lower-bound tau is used as is and flagged FLOOR.", "",
          "## Input shas", f"PILOT {sha(pilot_path)}", f"bench.tsv {sha(bench_path)}", f"rung0.tsv {sha(rung0_path)}", "",
          "## Bench rows used (host build numpy python L s n y_med y_min b_med wall_med procs load_before load_after cpu_over_wall)"]
    md += ["    " + " ".join(r.values()) for r in brows]
    md += ["", f"y4 = median of the four contended y (L=243, s=100) = {y4:.6f} ms; y(243,100) = {bn.y[(243, 100)]:.6f} ms; ratio = {y4 / bn.y[(243, 100)]:.4f}; f_pre = max(1.7, ratio) = {f_pre:.4f}",
           "", "## rho_i = measured cpu_s / (f = 1 prediction), the 41 chains", "chain rho"]
    md += [f"{c.stem} {x:.4f}" for c, x in zip(chains, rho)]
    md += [f"median rho = {rho_med:.4f}", f"f_final = max(1.7, y4/y(243,100), median rho) = max(1.7, {y4 / bn.y[(243, 100)]:.4f}, {rho_med:.4f}) = {f_final:.4f}", "",
           "## Worked row: (poc, 1.00, 243, random) at N = 4000 (source rung0)",
           f"tau = {w['tau']!r} ({w['form']}); skip = ceil(2 tau) = {w['skip']}; burn = ceil(20 tau) = {w['burn']}; s* = {w['sstar']}",
           f"y(243,{w['sstar']}) = {bn.y[(243, w['sstar'])]!r} ms; per-yield = y * skip / s* = {per_y!r} ms; b(243) = {bn.b[243]!r} ms",
           f"one chain = burn*b + N*per-yield = {w['burn'] * bn.b[243]!r} + {4000 * per_y!r} = {w['burn'] * bn.b[243] + 4000 * per_y!r} ms",
           f"cell (10 chains), quiet = {w['core_h']!r} core-h; contended = f_final * quiet = {w['core_h'] * f_final!r} core-h", "",
           "## Longest single chain (contended) and wall"]
    for N, (q, cn, wo, lg, fl) in summary.items():
        md.append(f"N = {N}: quiet {q:.3f}, contended {cn:.3f}, contended + PILOT-SHORT x4 {wo:.3f} core-h; longest chain {lg:.2f} h; wall at 4 procs = {max(cn / 4, lg):.2f} h; at 8 procs = {max(cn / 8, lg):.2f} h; FLOOR={fl}")
    md += ["", f"PILOT-SHORT cells ({len(short)}): " + "; ".join(f"{a},{b},{c},{d}" for a, b, c, d in sorted(short)), "",
           "## Reducer share overstatement at L = 243",
           f"The model scales y(L, s*) by skip/s*, which scales the per-yield reducer cost r by the same factor; the true cost of a yield is skip*b + r. With r_hat = y(243,1) - b(243) = {r_hat:.6f} ms,",
           f"for the worked row (skip/s* = {w['skip'] / w['sstar']:.3f}) the model overstates the per-yield cost by {over:.4%}.", ""]
    (out / "cost-DERIVATION.md").write_text("\n".join(md))
    for N, (q, cn, wo, lg, fl) in summary.items():
        print(f"N={N} quiet={q:.3f} contended={cn:.3f} pilotshort_worst={wo:.3f} longest_chain_h={lg:.2f} floor={fl}")
    print("DONE cost")
    return 0


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument("--out")
    ap.add_argument("--procs", type=int, default=4)
    ap.add_argument("--timeout", type=float)
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--smoke", action="store_true")
    g.add_argument("--bench", action="store_true")
    g.add_argument("--project", metavar="BENCH")
    g.add_argument("--run", action="store_true")
    g.add_argument("--collect", action="store_true")
    g.add_argument("--cost", nargs=3, metavar=("RUNG0", "PILOT", "BENCH"))
    a = ap.parse_args(argv)
    needs_out = a.smoke or a.bench or a.run or a.collect or a.cost
    if a.project and a.out:
        ap.error("--project takes no --out")
    if needs_out and not a.out:
        ap.error("--out is required by --smoke --bench --run --collect --cost")
    if a.run and a.timeout is None:
        ap.error("--run requires --timeout (seconds per chain, no default)")
    if a.project:
        return project(a.project, a.procs)
    if a.smoke:
        return smoke(a.out, a.procs)
    if a.bench:
        return bench(a.out)
    if a.collect:
        return collect(a.out)
    if a.cost:
        return cost(*a.cost, a.out)
    reason = pool_run(chain_table(), a.out, a.procs, a.timeout)
    if reason:
        print(reason)
        return 2
    got, why = rows_of(a.out)
    if why:
        print(why)
        return 2
    print("DONE 41 chains")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
