"""frozen_run_1282 - plan 1282 P2d: the frozen-run harness. A manifest names its run; one chain is one unit of work with atomic outputs; completion is derived from the filesystem
by a total table; a chain is a fold with a checkpoint at a yield boundary; STOP is read between compiled calls; the driver runs under a system LaunchDaemon (UserName drops privileges). Counts only: no detect,
no verdict, no seal, no instrument. A tool, not a test.
python tests/frozen_run_1282.py manifest|project|serve|up|down|status|verify|prefix ...   Every mode ends on ONE finish line: DONE <what>, STOPPED, DRAINED, FAILED <reason>, BLOCKED <reason> (exit 2), LOCKED."""
import os

os.environ["OMP_NUM_THREADS"] = os.environ["OPENBLAS_NUM_THREADS"] = "1"   # before numpy loads: one core per worker
import argparse
import concurrent.futures as cf
import csv
import dataclasses
import enum
import fcntl
import hashlib
import importlib.util
import json
import math
import multiprocessing
import platform
import plistlib
import pwd
import re
import signal
import subprocess
import sys
import time
import tomllib
import traceback
import zipfile
from concurrent.futures.process import BrokenProcessPool
from pathlib import Path

HERE = Path(__file__).resolve().parent
CLONE = HERE.parent
sys.path[:0] = [str(CLONE / "cc")]
import numpy as np  # noqa: E402
import sampler  # noqa: E402
from sampler import Run  # noqa: E402


def _load(name):
    spec = importlib.util.spec_from_file_location(name, HERE / f"{name}.py")
    m = importlib.util.module_from_spec(spec)
    sys.modules[name] = m   # a dataclass defined there looks its module up by name
    spec.loader.exec_module(m)
    return m


COST = _load("tau_1282_rung0")   # P2c's cost function: chain_core_h is the one per-chain formula; no second one here

SEAL = "1282-v10"
SCALE = {"rung1": 100, "rung2": 10, "full": 1, "scratch": 1}   # scale -> divisor: a total table
STAGE_CAP = {"rung1": 9, "rung2": 45, "full": 400}   # the approved stage caps (core-h, contended)
UPLIFT = {"": 1, "PILOT-SHORT": 4}   # cost-inputs.tsv flag -> the worst-case factor of the upper cost
CKPT_KEYS = ("seed", "N", "skip", "burn", "stem")


# ---- fsync, one function chosen by the platform table ----
def _fsync(fd):
    {True: lambda: fcntl.fcntl(fd, fcntl.F_FULLFSYNC), False: lambda: os.fsync(fd)}[hasattr(fcntl, "F_FULLFSYNC")]()


def fsync_path(p):
    fd = os.open(str(p), os.O_RDONLY)
    try:
        _fsync(fd)
    finally:
        os.close(fd)


def put(path, data):
    """tmp + fsync + replace + fsync dir: the final name is never partial."""
    path = Path(path)
    tmp = path.with_name(path.name + ".tmp")
    with open(tmp, "wb") as fh:
        fh.write(data if isinstance(data, bytes) else data.encode())
        fh.flush()
        _fsync(fh.fileno())
    os.replace(tmp, path)
    fsync_path(path.parent)


def append(path, line):
    fd = os.open(str(path), os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o644)
    try:
        os.write(fd, line.encode())
        _fsync(fd)
    finally:
        os.close(fd)


def utc():
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def log(D, event):
    fd = os.open(str(Path(D) / "driver.log"), os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o644)
    try:
        os.write(fd, f"{utc()} {event}\n".encode())
    finally:
        os.close(fd)


# ---- H0: the identity measures ----
def _digest(items):
    h = hashlib.sha256()
    for name, a in items:
        a = np.ascontiguousarray(a)
        h.update(f"{name}|{a.dtype.str}|{a.shape}|".encode())
        h.update(a.tobytes())
    return h.hexdigest()


def chain_sha(c):
    """sha256 over the in-memory Chain's arrays O, G, M1, L, K, in that order."""
    return _digest([("O", c.O), ("G", c.G), ("M1", c.M1), ("L", np.asarray(c.L)), ("K", np.asarray(c.couplings["K"], dtype=np.float64))])


@dataclasses.dataclass(frozen=True)
class Sha:
    hex: str


@dataclasses.dataclass(frozen=True)
class Unreadable:
    path: str


def content_sha(path):
    """Sha | Unreadable: the same construction over the npz's arrays in sorted key order. A missing, truncated or non-zip file is a value."""
    try:
        with np.load(path, allow_pickle=False) as z:
            return Sha(_digest([(k, z[k]) for k in sorted(z.files)]))
    except (OSError, ValueError, EOFError, KeyError, zipfile.BadZipFile):
        return Unreadable(str(path))


def file_sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


# ---- the manifest ----
def sha256_of(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def tsv(path):
    return list(csv.DictReader(open(path), delimiter="\t"))


def code_sha(clone=CLONE):
    h = hashlib.sha256()
    for rel in ("cc/sampler.py", "tests/frozen_run_1282.py"):
        h.update((Path(clone) / rel).read_bytes())
    return h.hexdigest()


def git(clone, *a):
    return subprocess.run(["git", "-C", str(clone), *a], capture_output=True, text=True)


def toml_value(v):
    return {str: json.dumps, int: str, float: repr, bool: lambda x: str(x).lower()}[type(v)](v)


def bench_of(path):
    return COST.read_bench(path)[0]


def stop_bound_s(rows, bench, F):
    """CHUNK_SWEEPS x b(L_max) x F / 1000 + 10: independent of tau (H5)."""
    return sampler.CHUNK_SWEEPS * bench.b[max(r["L"] for r in rows)] * F / 1000 + 10


def flags_of(cost_inputs):
    return {(r["F"], r["k"], int(r["L"]), r["s"]): r["flag"] for r in tsv(cost_inputs)}


def row_costs(rows, bench, F, flags):
    """[(contended core-h of one chain, upper)] per row. flags is None for a scratch manifest (no PILOT-SHORT uplift)."""
    out = []
    for r in rows:
        c = COST.chain_core_h(r["L"], r["skip"], r["burn"], r["N"], bench, F)
        out.append((c, c * UPLIFT[""] if flags is None else c * UPLIFT[flags[(r["F"], r["k"], r["L"], r["s"])]]))
    return out


def cap_of(kind, scale, uppers):
    """The total table over the manifest's constructor (no --cap flag exists)."""
    return {"rung": lambda: float(STAGE_CAP[scale]), "full": lambda: float(STAGE_CAP["full"]),
            "only": lambda: 2 * sum(uppers) + 0.2, "scratch": lambda: 2 * sum(uppers) + 0.2}[kind]()


def row_of(F, k, L, s, j, seed, N, skip, burn):
    return dict(F=F, k=k, L=int(L), s=s, j=int(j), seed=int(seed), N=int(N), skip=int(skip), burn=int(burn), stem=f"{F}_{k}_L{L}_{s}_c{j}")


def manifest_text(head, rows):
    lines = [f"{k} = {toml_value(v)}" for k, v in head.items()]
    lines.append("chains = [")
    lines += ["  {" + ", ".join(f"{k} = {toml_value(v)}" for k, v in r.items()) + "}," for r in rows]
    lines.append("]")
    return "\n".join(lines) + "\n"


def build_manifest(a):
    """(kind, rows) from the arguments, or BLOCKED. The two constructors are exclusive."""
    if a.scratch:
        rows, i = [], 0
        for spec in a.scratch:
            L, count, N, skip, burn = (int(x) for x in spec.split(","))
            for _ in range(count):
                k, s = ("0.92", "ordered") if i % 2 == 0 else ("1.08", "random")
                rows.append(row_of("poc", k, L, s, i, 1282400 + i, N, skip, burn))
                i += 1
        return "scratch", rows
    divisor = SCALE[a.scale]
    rows = []
    for c in tsv(a.cells):
        if int(c["N"]) % divisor:
            raise ValueError(f"N = {c['N']} is not divisible by {divisor}")
        for j in sampler.CHAINS:
            rows.append(row_of(c["F"], c["k"], c["L"], c["s"], j, sampler.seed_of(SEAL, c["F"], c["k"], int(c["L"]), c["s"], j), int(c["N"]) // divisor, c["skip"], c["burn"]))
    if a.only:
        keep = set(Path(a.only).read_text().split())
        return "only", [r for r in rows if r["stem"] in keep]
    return {"full": "full"}.get(a.scale, "rung"), rows


def mode_manifest(a):
    for path, sha in ((a.cells, a.cells_sha), (a.cost_inputs, a.cost_inputs_sha), (a.bench, a.bench_sha)):
        if a.scratch is None or path:
            assert sha256_of(path) == sha, f"{path} does not match its declared sha256"
    assert not (a.scratch and (a.cells or a.only)), "--scratch and the grid constructor are exclusive"
    try:
        kind, rows = build_manifest(a)
    except ValueError as e:
        return finish(f"BLOCKED {e}", 2)
    bench = bench_of(a.bench)
    flags = None if kind == "scratch" else flags_of(a.cost_inputs)
    costs = row_costs(rows, bench, a.f, flags)
    scale = "scratch" if kind == "scratch" else a.scale
    head = dict(seal=SEAL, scale=scale, kind=kind, divisor=SCALE[scale], cells_sha=a.cells_sha or "", cc_sha=git(CLONE, "rev-parse", "HEAD").stdout.strip(), code_sha=code_sha(),
                ts_sha=git(sampler.toolset_of(os.environ["CC_DATA_ROOT"]), "rev-parse", "HEAD").stdout.strip(), isf=sampler.PINS[sampler.SRC], numpy=np.__version__,
                python=platform.python_version(), ckpt_seconds=a.ckpt_seconds, stop_bound_s=stop_bound_s(rows, bench, a.f), cost_inputs=str(a.cost_inputs), cost_inputs_sha=a.cost_inputs_sha,
                bench=str(a.bench), bench_sha=a.bench_sha, f=a.f, cap_core_h=cap_of(kind, scale, [u for _, u in costs]))
    text = manifest_text(head, rows)
    D = Path(a.root) / f"{scale}-{hashlib.sha256(text.encode()).hexdigest()[:12]}"
    D.mkdir(parents=True, exist_ok=True)
    put(D / "manifest.toml", text)
    print(D)
    return finish(f"DONE manifest {D}", 0)


def read_manifest(D):
    text = (Path(D) / "manifest.toml").read_bytes()
    m = tomllib.loads(text.decode())
    return m, m.pop("chains"), hashlib.sha256(text).hexdigest()


def mode_project(a):
    m, rows, _ = read_manifest(a.run_dir)
    costs = row_costs(rows, bench_of(m["bench"]), m["f"], None if m["kind"] == "scratch" else flags_of(m["cost_inputs"]))
    x, u, longest = sum(c for c, _ in costs), sum(u for _, u in costs), max(c for c, _ in costs)
    print(f"PROJECTION core_h={x:.4f} core_h_upper={u:.4f} longest_chain_h={longest:.4f} wall_h={max(longest, x / a.procs):.4f} stop_bound_s={m['stop_bound_s']:.1f} cap={m['cap_core_h']:.4f}")
    over = m["kind"] in ("rung", "full") and u > m["cap_core_h"]
    return finish(f"BLOCKED projection {u:.4f} > {m['cap_core_h']:.4f}" if over else "DONE project", 2 if over else 0)


def finish(line, code):
    print(line)
    return code


# ---- H3: completion from the filesystem, a total table ----
class ChainState(enum.Enum):
    DONE = enum.auto()
    RECORD = enum.auto()
    REDO = enum.auto()
    RESUME = enum.auto()
    FRESH = enum.auto()

    @classmethod
    def parse(cls, name):
        return cls[name]   # a wrong name is a KeyError


class RunState(enum.Enum):
    RUNNING = enum.auto()
    DONE = enum.auto()
    STOPPED = enum.auto()
    DRAINED = enum.auto()
    FAILED = enum.auto()
    LOCKED = enum.auto()

    @classmethod
    def parse(cls, name):
        return cls[name]


EXIT = {RunState.RUNNING: None, RunState.DONE: 0, RunState.STOPPED: 0, RunState.DRAINED: 0, RunState.FAILED: 0, RunState.LOCKED: 0}   # RUNNING never exits; every terminal state is 0 (launchd must not respawn)


def read_done(D):
    """{stem: (content_sha, file_sha)}: a line without exactly three fields and its newline (a torn tail) reads as absent; the last line of a stem wins."""
    p = Path(D) / "done.tsv"
    raw = p.read_bytes().decode(errors="replace") if p.exists() else ""
    out = {}
    for ln in raw.split("\n")[:-1]:
        f = ln.split(" ")
        if len(f) == 3:
            out[f[0]] = (f[1], f[2])
    return out


def ckpt_identity(row, build, msha):
    return {**{k: row[k] for k in CKPT_KEYS}, "build": build, "manifest_sha": msha}


def ckpt_load(path):
    """(Fold, meta) or None: a missing or unreadable checkpoint is a value."""
    if not Path(path).exists():
        return None
    try:
        with np.load(path, allow_pickle=False) as z:
            meta = json.loads(str(z["meta"]))
            f = sampler.Fold(z["s"], json.loads(str(z["rng_state"])), int(z["i"]), list(z["O"]), [list(r) for r in z["G"]], list(z["M1"]))
        return f, meta
    except (OSError, ValueError, EOFError, KeyError, zipfile.BadZipFile):
        return None


def ckpt_get(path, row, build, msha):
    """(Fold, meta) iff the checkpoint matches the row (identity fields, build, manifest sha), else None."""
    got = ckpt_load(path)
    return got if got is not None and {k: got[1].get(k) for k in (*CKPT_KEYS, "build", "manifest_sha")} == ckpt_identity(row, build, msha) else None


def classify(D, row, done, build, msha):
    """The H3 table: (ChainState, reason)."""
    D, stem = Path(D), row["stem"]
    sha, rec = content_sha(D / f"{stem}.npz") if (D / f"{stem}.npz").exists() else None, done.get(stem)
    ck = ckpt_get(D / f"{stem}.ckpt.npz", row, build, msha) is not None
    return {
        (Sha, True, True): (ChainState.DONE, ""), (Sha, True, False): (ChainState.REDO, "corrupt"), (Sha, False, False): (ChainState.RECORD, ""),
        (Unreadable, True, False): (ChainState.REDO, "corrupt"), (Unreadable, False, False): (ChainState.REDO, "corrupt"),
        (None, True, False): ((ChainState.RESUME if ck else ChainState.FRESH), ""), (None, False, False): ((ChainState.RESUME if ck else ChainState.FRESH), ""),
    }[(type(sha) if sha is not None else None, rec is not None, bool(sha is not None and rec is not None and isinstance(sha, Sha) and rec[0] == sha.hex))]


# ---- one chain ----
TOOLS = None


def _init():
    global TOOLS
    signal.signal(signal.SIGTERM, signal.SIG_IGN)   # a TERM to the group drains through the driver, never kills a worker mid-write
    TOOLS = sampler.load(sampler.toolset_of(os.environ["CC_DATA_ROOT"]))


def stopper(D, driver_pid):
    D = Path(D)
    return lambda: (D / "STOP").exists() or (D / f"DRAIN.{driver_pid}").exists()


def ckpt_write(D, row, f, build, msha, resumes, cpu_s, wall_s):
    meta = {**ckpt_identity(row, build, msha), "resumes": resumes, "cpu_s": cpu_s, "wall_s": wall_s}
    path = Path(D) / f"{row['stem']}.ckpt.npz"
    tmp = path.with_name(f"{row['stem']}.ckpt.tmp.npz")
    np.savez(tmp, s=f.s, i=np.asarray(f.i), O=np.array(f.O, dtype=np.float64), G=np.array(f.G, dtype=np.float64), M1=np.array(f.M1, dtype=np.float64),
             rng_state=np.asarray(json.dumps(f.rng_state)), meta=np.asarray(json.dumps(meta)))
    fsync_path(tmp)
    os.replace(tmp, path)
    fsync_path(path.parent)


def work(D, row, msha, ckpt_s, driver_pid):
    """One unit of work: STOPPED | DONE. Bytes depend on (seed, N, skip, burn, K, h, L) only; STOP, the checkpoint cadence and kills cannot change them."""
    D, stem, tools = Path(D), row["stem"], TOOLS
    poll, run = stopper(D, driver_pid), Run(row["N"], row["skip"], row["burn"])
    K, h = float(row["k"]) * sampler.KC, sampler.FAMILY_H[row["F"]]
    t0, c0 = time.time(), time.process_time()
    log(D, f"begin {stem} pid={os.getpid()}")
    got = ckpt_get(D / f"{stem}.ckpt.npz", row, tools.build, msha)
    f, resumes, cpu0, wall0 = (None, 0, 0.0, 0.0) if got is None else (got[0], got[1]["resumes"] + 1, got[1]["cpu_s"], got[1]["wall_s"])
    spent = lambda: (cpu0 + time.process_time() - c0, wall0 + time.time() - t0)   # noqa: E731
    if f is not None:
        ckpt_write(D, row, f, tools.build, msha, resumes, *spent())   # the resume count survives a second kill before the next cadence
    if f is None:
        f = sampler.begin(tools, K, h, row["L"], row["s"], row["seed"], run, poll) if not poll() else sampler.NotStarted()
        if isinstance(f, sampler.NotStarted) or poll():
            log(D, f"notstarted {stem}")
            return "STOPPED"
    last = time.time()
    while f.i < run.N:
        r = sampler.advance(tools, f, K, h, run, poll)
        if isinstance(r, sampler.Stopped):
            if f.i >= 1:
                ckpt_write(D, row, f, tools.build, msha, resumes, *spent())
            log(D, f"stopped {stem} i={f.i}" if f.i >= 1 else f"notstarted {stem}")
            return "STOPPED"
        f = r
        if f.i < run.N and ckpt_s > 0 and time.time() - last >= ckpt_s:
            ckpt_write(D, row, f, tools.build, msha, resumes, *spent())
            log(D, f"checkpoint {stem} i={f.i}")
            last = time.time()
        if f.i < run.N and poll():
            ckpt_write(D, row, f, tools.build, msha, resumes, *spent())
            log(D, f"stopped {stem} i={f.i}")
            return "STOPPED"
    chain, call = sampler.finish(f, K, h, row["L"], row["s"], row["seed"], run, tools.build)
    cpu_s, wall_s = spent()
    final, tmp = D / f"{stem}.npz", D / f"{stem}.tmp.npz"
    sampler.write(chain, tmp)
    fsync_path(tmp)
    os.replace(tmp, final)
    fsync_path(D)
    sampler.write_call(call, tmp)   # -> <stem>.tmp.json, then the run's own fields are added
    jt = D / f"{stem}.tmp.json"
    jt.write_text(json.dumps({**json.loads(jt.read_text()), "host": platform.node(), "wall_s": wall_s, "cpu_s": cpu_s, "resumes": resumes}, indent=1) + "\n")
    fsync_path(jt)
    os.replace(jt, D / f"{stem}.json")
    fsync_path(D)
    append(D / "done.tsv", f"{stem} {content_sha(final).hex} {file_sha(final)}\n")
    for ck in (D / f"{stem}.ckpt.npz",):
        ck.unlink(missing_ok=True)
    sweeps = row["burn"] + row["N"] * row["skip"]
    append(D / "progress.tsv", f"{stem}\t{t0:.0f}\t{time.time():.0f}\t{sweeps}\t{wall_s:.1f}\t{cpu_s:.1f}\t{resumes}\t{os.getloadavg()[0]:.2f}\n")
    log(D, f"done {stem}")
    return "DONE"


# ---- the driver ----
def rotate(D):
    p = Path(D) / "driver.log"
    if p.exists() and p.stat().st_size > 10_000_000:
        for i in (2, 1):
            if (Path(D) / f"driver.log.{i}").exists():
                os.replace(Path(D) / f"driver.log.{i}", Path(D) / f"driver.log.{i + 1}")
        os.replace(p, Path(D) / "driver.log.1")


def write_status(D, state, done, total, used, proj, pid, last, reason=""):
    line = f"{state.name} {done}/{total} core_h={used:.3f} proj={proj:.3f} pid={pid}" + (f" reason={reason}" if reason else "")
    tail = "\n".join((Path(D) / "driver.log").read_text().splitlines()[-20:]) if (Path(D) / "driver.log").exists() else ""
    put(Path(D) / "status.line", line + "\n")
    put(Path(D) / "STATUS", f"{line}\nlast_exit={last}\n--- last 20 log lines\n{tail}\n")


def serve(D, procs):
    """The driver. Returns the RunState it ends in (the caller maps it to the exit code through EXIT)."""
    D = Path(D)
    lock = open(D / "driver.lock", "a+")
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        lock.seek(0)
        print(f"LOCKED {lock.read().strip()}")   # nothing is written to the run dir
        return RunState.LOCKED
    lock.seek(0)
    lock.truncate()
    lock.write(str(os.getpid()))
    lock.flush()
    m, rows, msha = read_manifest(D)
    me = os.getpid()
    rotate(D)
    log(D, f"start pid={me} pgid={os.getpgid(0)}")
    total = len(rows)
    bad = ("MANIFEST-CHANGED" if D.name != f"{m['scale']}-{msha[:12]}" else
           "CODE-CHANGED" if code_sha() != m["code_sha"] or git(CLONE, "status", "--porcelain", "--", "cc", "tests").stdout.strip() else "")
    if not bad:
        t = sampler.load(sampler.toolset_of(os.environ["CC_DATA_ROOT"]))
        bad = "TOOLS-MISMATCH" if isinstance(t, sampler.Mismatch) else ""
        build = "" if bad else t.build
    if bad:
        return end(D, RunState.FAILED, 0, total, 0.0, 0.0, me, bad)
    for pat in ("*.tmp.npz", "*.tmp.json", "DRAIN.*"):
        for p in D.glob(pat):
            p.unlink()
    signal.signal(signal.SIGTERM, lambda *_: (D / f"DRAIN.{me}").write_text(""))
    bench = bench_of(m["bench"])
    costs = row_costs(rows, bench, m["f"], None)
    proj = sum(c for c, _ in costs)
    done_tab, todo, used = read_done(D), [], {}
    for r in rows:
        st, why = classify(D, r, done_tab, build, msha)
        if st is ChainState.RECORD:
            append(D / "done.tsv", f"{r['stem']} {content_sha(D / (r['stem'] + '.npz')).hex} {file_sha(D / (r['stem'] + '.npz'))}\n")
            st = ChainState.DONE
        if st is ChainState.REDO:
            log(D, f"corrupt {r['stem']}")
            for ext in (".npz", ".json", ".ckpt.npz"):
                (D / f"{r['stem']}{ext}").unlink(missing_ok=True)
        if st is ChainState.DONE:
            (D / f"{r['stem']}.ckpt.npz").unlink(missing_ok=True)
            used[r["stem"]] = json.loads((D / f"{r['stem']}.json").read_text())["cpu_s"]
        else:
            todo.append(r)
    cost = {r["stem"]: c for r, (c, _) in zip(rows, costs)}
    todo.sort(key=lambda r: (-cost[r["stem"]], r["stem"]))
    stop = stopper(D, me)
    failed, raised, pend, futs = "", {}, list(todo), {}
    ctx = multiprocessing.get_context("spawn")
    state = lambda: write_status(D, RunState.RUNNING, len(used), total, sum(used.values()) / 3600, proj, me, "-")   # noqa: E731
    state()
    with cf.ProcessPoolExecutor(max_workers=procs, mp_context=ctx, initializer=_init) as pool:
        try:
            while pend or futs:
                while pend and len(futs) < procs and not stop() and not failed:
                    r = pend.pop(0)
                    futs[pool.submit(work, str(D), r, msha, m["ckpt_seconds"], me)] = r
                if not futs:
                    break
                fin, _ = cf.wait(futs, timeout=1.0, return_when=cf.FIRST_COMPLETED)
                for fu in fin:
                    r = futs.pop(fu)
                    exc = fu.exception()
                    if isinstance(exc, BrokenProcessPool):
                        raise exc
                    if exc is not None:
                        first = (traceback.format_exception_only(type(exc), exc)[-1]).strip().replace("\t", " ")
                        append(D / "failed.tsv", f"{r['stem']}\t{first}\n")
                        log(D, f"raise {r['stem']} {first}")
                        if r["stem"] in raised:
                            failed = first
                            (D / f"DRAIN.{me}").write_text("")
                        else:
                            raised[r["stem"]] = first
                            pend.insert(0, r)
                    elif fu.result() == "DONE":
                        used[r["stem"]] = json.loads((D / f"{r['stem']}.json").read_text())["cpu_s"]
                        state()
                        if sum(used.values()) / 3600 >= m["cap_core_h"] and not (D / "STOP").exists():
                            (D / "STOP").write_text("BUDGET\n")
                            log(D, "budget STOP")
        except BrokenProcessPool:
            log(D, "crash BrokenProcessPool")
            for w in multiprocessing.active_children():
                w.kill()   # the pool's workers ignore SIGTERM (H5), so the executor's own terminate_broken cannot stop them: without this the exit waits for their chains
            sys.exit(70)   # non-zero: launchd respawns, H3 resumes the work
    n = len(used)
    final = (RunState.FAILED if failed else RunState.DRAINED if (D / f"DRAIN.{me}").exists() else RunState.STOPPED if (D / "STOP").exists() and n < total else RunState.DONE if n == total else RunState.STOPPED)
    return end(D, final, n, total, sum(used.values()) / 3600, proj, me, failed)


def end(D, st, n, total, used, proj, pid, reason=""):
    D = Path(D)
    log(D, f"state {st.name}")
    write_status(D, st, n, total, used, proj, pid, EXIT[st], reason)
    {RunState.DONE: lambda: (D / ".landed").write_text(""), RunState.FAILED: lambda: (D / ".FAILED").write_text(reason + "\n")}.get(st, lambda: None)()
    return st


def mode_serve(a):
    st = serve(a.run_dir, a.procs)
    if st is not RunState.LOCKED:
        print({RunState.DONE: lambda: "DONE serve", RunState.FAILED: lambda: "FAILED " + (Path(a.run_dir) / ".FAILED").read_text().strip()}.get(st, lambda: st.name)())
    return EXIT[st]


# ---- the daemon: a system-domain LaunchDaemon (UserName drops to the invoking user); every privileged act is `sudo -n`, for this label only ----
def run(*cmd, inp=None):
    return subprocess.run(list(cmd), capture_output=True, text=True, input=inp)


def sudo(*cmd):
    return run("sudo", "-n", *cmd)


class Launchd(enum.Enum):
    """The state of a label in the system domain: a total table over (exit code, text), never a bare non-zero."""
    RUNNING = "RUNNING"
    LOADED = "LOADED"
    ABSENT = "ABSENT"
    ERROR = "ERROR"

    @classmethod
    def parse(cls, name):
        return cls[name]


def launchd_state(label):
    r = sudo("launchctl", "print", f"system/{label}")
    text = r.stdout + r.stderr
    pid = bool(re.search(r"^\s*pid = \d+", text, re.M))
    kind = {True: "ok"}.get(r.returncode == 0 and label in text) or {True: "gone"}.get(r.returncode != 0 and "Could not find service" in text) or "err"
    return {("ok", True): Launchd.RUNNING, ("ok", False): Launchd.LOADED, ("gone", True): Launchd.ABSENT, ("gone", False): Launchd.ABSENT,
            ("err", True): Launchd.ERROR, ("err", False): Launchd.ERROR}[(kind, pid)]


def mode_up(a):
    D, label = Path(a.run_dir).resolve(), a.label
    m, _, _ = read_manifest(D)
    t0 = time.time()
    if sudo("true").returncode != 0:
        return finish("BLOCKED sudo -n true failed (passwordless sudo not configured)", 2)
    user = pwd.getpwuid(os.getuid()).pw_name
    plist = {"Label": label, "UserName": user,
             "ProgramArguments": ["/usr/bin/caffeinate", "-i", "/usr/bin/nice", "-n", "10", sys.executable, str(CLONE / "tests" / "frozen_run_1282.py"), "serve", "--run-dir", str(D), "--procs", str(a.procs)],
             "EnvironmentVariables": {"CC_DATA_ROOT": os.environ["CC_DATA_ROOT"], "HOME": str(Path.home()), "OMP_NUM_THREADS": "1", "OPENBLAS_NUM_THREADS": "1"},
             "WorkingDirectory": str(CLONE), "RunAtLoad": True, "KeepAlive": {"SuccessfulExit": False}, "ThrottleInterval": 60,
             "ProcessType": "Standard", "ExitTimeOut": math.ceil(m["stop_bound_s"]) + 30,
             "StandardOutPath": str(D / "agent.log"), "StandardErrorPath": str(D / "agent.log")}
    pl = D / f"{label}.plist"
    pl.write_bytes(plistlib.dumps(plist))
    lint = run("plutil", "-lint", str(pl))
    print(lint.stdout.strip() or lint.stderr.strip())
    if lint.returncode != 0:
        return finish("FAILED up plist-lint", 1)
    (D / "agent.log").write_text("")   # created as the invoking user, so launchd never root-creates it under the UserName drop
    target = f"/Library/LaunchDaemons/{label}.plist"
    inst = sudo("install", "-o", "root", "-g", "wheel", "-m", "0644", str(pl), target)
    if inst.returncode != 0:
        return finish(f"FAILED up install-rc={inst.returncode}", 1)
    print(run("ls", "-l", target).stdout.strip())
    boot = {Launchd.ABSENT: lambda: sudo("launchctl", "bootstrap", "system", target).returncode}.get(launchd_state(label), lambda: 0)()   # loaded -> nothing
    if launchd_state(label) in (Launchd.ABSENT, Launchd.ERROR):
        return finish(f"FAILED up bootstrap-rc={boot}", 1)
    sudo("launchctl", "kickstart", f"system/{label}")   # no -k; EALREADY and a race with RunAtLoad are judged by the print below, not the exit code
    sl = D / "status.line"
    while time.time() - t0 < 120:
        mt = re.search(r"pid=(\d+)", sl.read_text()) if sl.exists() and sl.stat().st_mtime >= t0 else None
        if mt:
            return finish(f"DONE up label={label} pid={mt.group(1)}", 0)
        time.sleep(0.5)
    return finish("FAILED up: no driver pid in status.line within 120 s", 1)


def mode_down(a):
    D, label = Path(a.run_dir).resolve(), a.label
    m, _, _ = read_manifest(D)
    (D / "STOP").write_text("down\n")
    t0 = time.time()
    while time.time() - t0 < m["stop_bound_s"] + 60 and launchd_state(label) in (Launchd.RUNNING, Launchd.ERROR):
        time.sleep(1)
    waited = launchd_state(label) in (Launchd.RUNNING, Launchd.ERROR)
    print("finding: down waited the full bound and the label still read RUNNING/ERROR" if waited else "down: nothing left to drain")
    sudo("launchctl", "bootout", f"system/{label}")
    sudo("rm", "-f", f"/Library/LaunchDaemons/{label}.plist")
    st = launchd_state(label)
    line = {Launchd.ABSENT: (f"DONE down label={label} absent", 0), Launchd.ERROR: ("FAILED label-unknown-state", 1),
            Launchd.LOADED: ("FAILED label-still-loaded", 1), Launchd.RUNNING: ("FAILED label-still-loaded", 1)}[st]
    return finish(*line)


# ---- reading a run ----
def mode_status(a):
    print((Path(a.run_dir) / "STATUS").read_text())
    return finish("DONE status", 0)


def mode_verify(a):
    D = Path(a.run_dir)
    _, rows, _ = read_manifest(D)
    done = read_done(D)
    def intact(stem):
        s = content_sha(D / f"{stem}.npz")
        return stem in done and isinstance(s, Sha) and (s.hex, file_sha(D / f"{stem}.npz")) == done[stem]
    bad = [r["stem"] for r in rows if not intact(r["stem"])]
    print(f"VERIFIED {len(rows) - len(bad)}/{len(rows)}")
    print("differ:", " ".join(bad))
    print(f"leftover tmp={len(list(D.glob('*.tmp.npz')))} ckpt={len(list(D.glob('*.ckpt.npz')))}")
    return finish("DONE verify", 0)


def mode_prefix(a):
    S, Lg = Path(a.short), Path(a.long)
    _, rows, _ = read_manifest(S)
    ok = 0
    for r in rows:
        with np.load(S / f"{r['stem']}.npz") as s, np.load(Lg / f"{r['stem']}.npz") as g:
            ok += all(np.array_equal(s[k], g[k][:len(s[k])]) for k in ("O", "G", "M1")) and all(np.array_equal(s[k], g[k]) for k in ("L", "K"))
    print(f"PREFIX {ok}/{len(rows)}")
    return finish("DONE prefix", 0)


def main(argv):
    p = argparse.ArgumentParser(prog="frozen_run_1282")
    sub = p.add_subparsers(dest="mode", required=True)
    s = sub.add_parser("manifest")
    s.add_argument("--cells")
    s.add_argument("--cells-sha")
    s.add_argument("--cost-inputs", required=True)
    s.add_argument("--cost-inputs-sha", required=True)
    s.add_argument("--bench", required=True)
    s.add_argument("--bench-sha", required=True)
    s.add_argument("--f", type=float, required=True)
    s.add_argument("--scale", choices=["rung1", "rung2", "full"])
    s.add_argument("--ckpt-seconds", type=int, required=True)
    s.add_argument("--root", required=True)
    s.add_argument("--only")
    s.add_argument("--scratch", action="append", help="L,count,N,skip,burn (repeatable): K/K_c 0.92 and 1.08 alternate, seeds 1282400+i")
    for name, extra in (("project", ["--procs"]), ("serve", ["--procs"]), ("up", ["--procs", "--label"]), ("down", ["--label"]), ("status", []), ("verify", [])):
        q = sub.add_parser(name)
        q.add_argument("--run-dir", required=True)
        for e in extra:
            q.add_argument(e, required=e == "--label", type=str if e == "--label" else int, default=None if e == "--label" else 4)
    q = sub.add_parser("prefix")
    q.add_argument("--short", required=True)
    q.add_argument("--long", required=True)
    a = p.parse_args(argv)
    return {"manifest": mode_manifest, "project": mode_project, "serve": mode_serve, "up": mode_up, "down": mode_down, "status": mode_status, "verify": mode_verify, "prefix": mode_prefix}[a.mode](a)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
