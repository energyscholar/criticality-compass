"""test_slots - plan 1559: the host-wide pool of worker slots (contract; the Generator does not edit this file).

Every gate test here builds scratch copies of the tree (bin/ and cc/ only, as test_schedule does) whose tests are tiny scripts that log
their own start and end, and drives `bin/cc test` in them under a PRIVATE pool (CC_SLOTS=<tmp>/pool), so this file never touches the
host's pool and is not throttled by the gate that runs it. Peaks are read from the logs: the most scripts alive at one instant.

c01 two gates at once never exceed the pool: CC_JOBS=3, two gates of 6 tests each -> peak == 3 (base: 2 x min(6, cpus-2))
c02 one gate is capped too: CC_JOBS=2, 6 tests -> peak == 2 (base: min(6, cpus-2))
c03 the gate's failure NAMES and order are the same at CC_JOBS=1 and CC_JOBS=4 (ok/FAIL lines in checks.toml order, rc 1)
c04 a nested `bin/cc test`, its environment scrubbed to PATH and CC_SLOTS, inside every slot of a full pool (CC_JOBS=2): finishes
    (no deadlock), saw the pool full while it ran, and the inner tests of both nested gates together peak at 2 (each runs serially in
    the slot its outer test holds). With CC_JOBS=3 (one slot free) the inner tests peak at exactly 3: a nested fan takes a free slot,
    and no more than the pool has. (base: no pool, inner peak 6)
c05 kill -9 of a whole gate frees its slots: a new gate gets the whole pool at once
c06 kill -9 of the coordinator alone: its live worker KEEPS its slot until the worker exits, then the slot is free
c07 a bad CC_JOBS (0, -1, x, empty) is refused by name, rc 1, and no test starts
c08 one host, one pool: with CC_SLOTS unset the pool is under HOME, never under CC_DATA_ROOT (two gates with two data roots share it),
    and its size is the pool's: a CC_JOBS that disagrees with it is refused by name
c09 structure: no tracked .py file nor bin/cc names a pool constructor (concurrent.futures, a *PoolExecutor, multiprocessing, Pool())
    in code except cc/slots.py (the declared exemptions are frozen measurement drivers); bin/cc, tests/test_golden.py and
    tests/test_run_all.py each call slots.fan( in code. Without .git it walks the tree.
c10 who holds and who waits is visible: with a pool of 1 held by a live test and a second gate waiting, `python cc/slots.py` prints
    `slot-0 held pid <the test's pid> ...` and `wait pid <the waiting gate's pid> ...`; once the holder is killed the waiter runs, and
    the listing shows `slot-0 free` and no `wait` line
c11 slots.fan(fn, items, width, procs=True) runs each fn(item) in its own process inside a held slot: with CC_JOBS=2 and width 4,
    the results come back in order, at most 2 run at once, at most 2 child processes exist at once, and the 6 items ran in 6 different
    processes (a process reused across items would live on, uncounted, while its slot was free between them)

Run as a script (one PASS/FAIL line per test, then n/N passed; rc 0 only when all pass) or under pytest."""
import fcntl
import os
import re
import shutil
import signal
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PY = sys.executable
SLEEPER = '''import os, sys, time
from pathlib import Path
L = Path(os.environ["SLOT_LOG"])
with L.open("a") as f: f.write(f"start {Path(__file__).stem} {os.getpid()} {time.time()}\\n")
time.sleep(float(os.environ.get("SLOT_SLEEP", "1.0")))
with L.open("a") as f: f.write(f"end {Path(__file__).stem} {os.getpid()} {time.time()}\\n")
'''
FAILER = '''import sys
print("planted failure")
sys.exit(1)
'''
PASSER = '''print("ok")
'''


def scratch(base, names, bodies=None):
    """A copy of bin/ and cc/ with tests/<name>.py for each name (a SLEEPER unless `bodies` says otherwise), checks.toml naming them, and
    cc.toml with no exclusive test."""
    repo = Path(base)
    repo.mkdir(parents=True)
    shutil.copytree(ROOT / "bin", repo / "bin")
    shutil.copytree(ROOT / "cc", repo / "cc", ignore=shutil.ignore_patterns("__pycache__"))
    (repo / "tests").mkdir()
    for n in names:
        (repo / "tests" / f"{n}.py").write_text((bodies or {}).get(n, SLEEPER))
    (repo / "checks.toml").write_text("[roles]\ntests = [" + ", ".join(f'"tests/{n}.py"' for n in names) + "]\n")
    (repo / "cc.toml").write_text(re.sub(r"(?m)^exclusive = \[.*?\]", "exclusive = []", (ROOT / "cc.toml").read_text()))
    return repo


def env_for(pool, jobs, log, **extra):
    e = {k: v for k, v in os.environ.items() if k not in ("CC_SLOTS", "CC_JOBS")}
    e.update({"CC_SLOTS": str(pool), "SLOT_LOG": str(log)})
    if jobs is not None:
        e["CC_JOBS"] = str(jobs)
    e.update({k: str(v) for k, v in extra.items()})
    return e


def gate(repo, env):
    return subprocess.Popen([PY, str(repo / "bin" / "cc"), "test"], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, cwd=repo, env=env,
                            start_new_session=True)


def finish(p, timeout):
    try:
        out, _ = p.communicate(timeout=timeout)
        return p.returncode, out
    except subprocess.TimeoutExpired:
        os.killpg(p.pid, signal.SIGKILL)
        out, _ = p.communicate()
        return None, out


def spans(log):
    out = {}
    for ln in Path(log).read_text().splitlines() if Path(log).is_file() else []:
        kind, name, pid, ts = ln.split()
        out.setdefault((name, pid), {})[kind] = float(ts)
    return out


def peak(log):
    ev = sorted([(s["start"], 1) for s in spans(log).values() if "start" in s] + [(s["end"], -1) for s in spans(log).values() if "end" in s],
                key=lambda e: (e[0], e[1]))
    run = best = 0
    for _, d in ev:
        run += d
        best = max(best, run)
    return best


def locked(pool):
    """How many slot files of `pool` are held right now (probed with a non-blocking flock on a fresh descriptor)."""
    n = 0
    for p in sorted(Path(pool).glob("slot-*")):
        fd = os.open(p, os.O_RDWR)
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            fcntl.flock(fd, fcntl.LOCK_UN)
        except BlockingIOError:
            n += 1
        finally:
            os.close(fd)
    return n


def wait_for(pred, timeout):
    t0 = time.time()
    while time.time() - t0 < timeout:
        if pred():
            return True
        time.sleep(0.1)
    return False


def t_c01_two_gates_never_exceed_the_pool(tmp):
    pool, log = tmp / "pool", tmp / "log"
    a, b = scratch(tmp / "a", [f"a{i}" for i in range(6)]), scratch(tmp / "b", [f"b{i}" for i in range(6)])
    t0 = time.time()
    ga, gb = gate(a, env_for(pool, 3, log)), gate(b, env_for(pool, 3, log))
    (ra, oa), (rb, ob) = finish(ga, 120), finish(gb, max(1, 120 - (time.time() - t0)))   # one budget for both
    assert ra == 0 and rb == 0, f"rc {ra} {rb}: {oa[-300:]} {ob[-300:]}"
    assert len(spans(log)) == 12, f"{len(spans(log))} of 12 tests ran"
    assert peak(log) == 3, f"peak {peak(log)} workers at once across two gates, pool 3"


def t_c02_one_gate_is_capped(tmp):
    pool, log = tmp / "pool", tmp / "log"
    a = scratch(tmp / "a", [f"a{i}" for i in range(6)])
    rc, out = finish(gate(a, env_for(pool, 2, log)), 120)
    assert rc == 0, out[-300:]
    assert peak(log) == 2, f"peak {peak(log)} workers at once in one gate, pool 2"


def t_c03_failure_names_unchanged(tmp):
    names = ["p_a", "f_b", "p_c", "f_d", "p_e"]
    bodies = {n: (FAILER if n.startswith("f_") else PASSER) for n in names}
    bodies["p_a"] = "import time\ntime.sleep(0.8)\n" + PASSER   # the first finishes last: results must come back in checks.toml order
    got = {}
    for j in (1, 4):
        repo = scratch(tmp / f"r{j}", names, bodies)
        rc, out = finish(gate(repo, env_for(tmp / f"pool{j}", j, tmp / "log")), 120)
        lines = [ln for ln in out.splitlines() if ln.startswith(("ok  ", "FAIL"))]
        got[j] = (rc, lines)
    want = ["ok   p_a", "FAIL f_b", "ok   p_c", "FAIL f_d", "ok   p_e"]
    assert got[1] == got[4] == (1, want), f"{got}"


INNER = '''import fcntl, os, subprocess, sys, time
from pathlib import Path
here = Path(__file__).resolve().parent.parent
pool = Path(os.environ["CC_SLOTS"])
def locked():
    n = 0
    for p in sorted(pool.glob("slot-*")):
        fd = os.open(p, os.O_RDWR)
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB); fcntl.flock(fd, fcntl.LOCK_UN)
        except BlockingIOError:
            n += 1
        finally:
            os.close(fd)
    return n
want, seen, t0 = int(os.environ["SEEN_WANT"]), 0, time.time()
while seen < want and time.time() - t0 < 20:   # wait for the sibling outer test to hold its slot too (no race on a busy host)
    seen = max(seen, locked())
    time.sleep(0.05)
inner = here / ("inner-" + Path(__file__).stem)
env = {"PATH": os.environ["PATH"], "CC_SLOTS": os.environ["CC_SLOTS"], "SLOT_LOG": os.environ["INNER_LOG"], "SLOT_SLEEP": "1.0"}   # scrubbed: no other variable crosses
r = subprocess.run([sys.executable, str(inner / "bin" / "cc"), "test"], capture_output=True, text=True, cwd=inner, env=env)
with open(os.environ["SEEN_LOG"], "a") as f: f.write(f"{Path(__file__).stem} {seen} {r.returncode}\\n")
sys.exit(r.returncode)
'''


def nested_gates(tmp, jobs):
    pool, log, ilog, seen = tmp / "pool", tmp / "log", tmp / "ilog", tmp / "seen"
    outer = scratch(tmp / "outer", ["o0", "o1"], {"o0": INNER, "o1": INNER})
    for o in ("o0", "o1"):
        scratch(outer / f"inner-{o}", [f"{o}_i{i}" for i in range(3)])
    rc, out = finish(gate(outer, env_for(pool, jobs, log, INNER_LOG=ilog, SEEN_LOG=seen, SEEN_WANT=2)), 90)
    assert rc is not None, f"DEADLOCK: the nested gates (pool {jobs}) did not finish in 90 s: {out[-400:]}"
    assert rc == 0, f"pool {jobs}: rc {rc}: {out[-400:]}"
    assert len(spans(ilog)) == 6, f"pool {jobs}: {len(spans(ilog))} of 6 inner tests ran"
    return [ln.split() for ln in seen.read_text().splitlines()], peak(ilog)


def t_c04_nested_call_never_deadlocks(tmp):
    rows, p = nested_gates(tmp / "j2", 2)
    assert len(rows) == 2 and all(r[1] == "2" for r in rows), f"each outer test must see the pool full (2 held) while it runs: {rows}"
    assert p == 2, f"pool 2, both slots held by the outer tests: the nested gates ran {p} inner tests at once (want 2, one per held slot)"
    rows, p = nested_gates(tmp / "j3", 3)
    assert p == 3, f"pool 3, one slot free: the nested gates ran {p} inner tests at once (want 3: two inherited slots and the free one)"


KEEP = '''import os, time
from pathlib import Path
with open(os.environ["SLOT_LOG"], "a") as f: f.write(f"start {Path(__file__).stem} {os.getpid()} {time.time()}\\n")
time.sleep(float(os.environ.get("SLOT_SLEEP", "60")))
with open(os.environ["SLOT_LOG"], "a") as f: f.write(f"end {Path(__file__).stem} {os.getpid()} {time.time()}\\n")
'''


def t_c05_kill9_of_a_gate_frees_its_slots(tmp):
    pool, log = tmp / "pool", tmp / "log"
    a = scratch(tmp / "a", ["k0", "k1"], {"k0": KEEP, "k1": KEEP})
    ga = gate(a, env_for(pool, 2, log, SLOT_SLEEP=60))
    try:
        assert wait_for(lambda: len(spans(log)) == 2 and locked(pool) == 2, 20), f"gate A never held both slots: locked {locked(pool) if pool.is_dir() else 'no pool'}"
    finally:
        try:
            os.killpg(ga.pid, signal.SIGKILL)
        except (ProcessLookupError, PermissionError):
            pass
        ga.communicate()
    b = scratch(tmp / "b", ["n0", "n1"])
    t0 = time.time()
    rc, out = finish(gate(b, env_for(pool, 2, tmp / "logb", SLOT_SLEEP=1.0)), 30)
    assert rc == 0, f"rc {rc}: {out[-300:]}"
    assert peak(tmp / "logb") == 2, f"after the kill the new gate got {peak(tmp / 'logb')} of 2 slots at once"
    assert time.time() - t0 < 15, f"{time.time() - t0:.1f} s"


def t_c06_orphan_worker_keeps_its_slot(tmp):
    pool, log = tmp / "pool", tmp / "log"
    a = scratch(tmp / "a", ["w0"], {"w0": KEEP})
    ga = gate(a, env_for(pool, 1, log, SLOT_SLEEP=4))
    try:
        assert wait_for(lambda: len(spans(log)) == 1 and locked(pool) == 1, 20), "the worker never held the slot"
        os.kill(ga.pid, signal.SIGKILL)   # the coordinator only; the worker lives on
        ga.communicate()
        time.sleep(0.5)
        assert locked(pool) == 1, "the coordinator died and the live worker's slot was freed: an uncounted worker"
        assert wait_for(lambda: "end" in next(iter(spans(log).values())), 15), "the worker never ended"
        assert wait_for(lambda: locked(pool) == 0, 5), "the worker exited and its slot is still held"
    finally:
        try:
            os.killpg(ga.pid, signal.SIGKILL)
        except (ProcessLookupError, PermissionError):   # the group is gone (macOS answers EPERM for a group of zombies)
            pass
        ga.wait()


def t_c07_bad_jobs_refused_by_name(tmp):
    for i, bad in enumerate(("0", "-1", "x", "")):
        log = tmp / f"log{i}"
        repo = scratch(tmp / f"r{i}", ["s0"], {"s0": SLEEPER})
        rc, out = finish(gate(repo, env_for(tmp / f"pool{i}", bad, log)), 60)
        assert rc == 1, f"CC_JOBS={bad!r}: rc {rc}: {out[-200:]}"
        assert out.startswith("REFUSED: CC_JOBS"), f"CC_JOBS={bad!r}: {out[:200]!r}"
        assert not spans(log), f"CC_JOBS={bad!r}: a test ran"


def t_c08_one_host_one_pool(tmp):
    home, log = tmp / "home", tmp / "log"
    home.mkdir()
    gates = []
    for k in ("a", "b"):
        repo = scratch(tmp / k, [f"{k}{i}" for i in range(4)])
        e = env_for(tmp / "unused", 2, log, HOME=home, CC_DATA_ROOT=tmp / f"data-{k}")
        del e["CC_SLOTS"]
        gates.append(gate(repo, e))
    t0 = time.time()
    res = [finish(g, max(1, 120 - (time.time() - t0))) for g in gates]   # one budget for both
    assert all(rc == 0 for rc, _ in res), f"{[(rc, o[-200:]) for rc, o in res]}"
    want = home / ".cache" / "criticality-compass" / "slots"
    assert sorted(p.name for p in want.glob("slot-*")) == ["slot-0", "slot-1"], f"pool under HOME: {sorted(want.glob('*')) if want.is_dir() else 'absent'}"
    assert not any((tmp / f"data-{k}").exists() for k in "ab"), "a pool was made under CC_DATA_ROOT"
    assert peak(log) == 2, f"two gates with two data roots reached {peak(log)} workers at once, pool 2"
    repo = scratch(tmp / "c", ["c0"])
    e = env_for(tmp / "unused", 3, tmp / "logc", HOME=home)
    del e["CC_SLOTS"]
    rc, out = finish(gate(repo, e), 60)
    assert rc == 1 and out.startswith("REFUSED: CC_JOBS") and "2" in out.splitlines()[0], f"a CC_JOBS of 3 against a pool of 2: rc {rc}: {out[:200]!r}"
    assert not spans(tmp / "logc"), "a test ran under a disagreeing CC_JOBS"
    e2 = {k: v for k, v in e.items() if k != "CC_JOBS"}
    rc, out = finish(gate(repo, e2), 60)
    assert rc == 0, f"no CC_JOBS reads the pool's own size: rc {rc}: {out[-200:]}"


POOLS = re.compile(r"\b(ThreadPoolExecutor|ProcessPoolExecutor|multiprocessing)\b|concurrent\.futures|\bPool\s*\(")
STRINGS = re.compile(r"\"[^\"]*\"|'[^']*'")
EXEMPT = {   # frozen measurement drivers: each is started by its test with --procs <= 2 and runs inside that test's slot (plan 1559 OQ-4)
    "tests/frozen_run_1282.py", "tests/tau_1282_p1.py", "tests/tau_1282_rung0.py",
}


def code(f):
    """The code of a file: comments and string literals removed, line by line."""
    return [STRINGS.sub("", ln).split("#", 1)[0] for ln in (ROOT / f).read_text(errors="replace").splitlines()]


def t_c09_one_way_to_fan_out():
    r = subprocess.run(["git", "-C", str(ROOT), "ls-files", "bin/cc", "*.py"], capture_output=True, text=True)
    files = r.stdout.split() if r.returncode == 0 else ["bin/cc"] + sorted(str(p.relative_to(ROOT)) for p in ROOT.rglob("*.py"))
    hits = []
    for f in files:
        if f in EXEMPT or f == "cc/slots.py" or f.startswith(("contract/test_slots.py", "vendor/")) or not (ROOT / f).is_file():
            continue
        hits += [f"{f}:{i}" for i, ln in enumerate(code(f), 1) if POOLS.search(ln)]
    assert not hits, f"pools built outside cc/slots.py: {hits}"
    assert (ROOT / "cc" / "slots.py").is_file(), "cc/slots.py is absent"
    for f in ("bin/cc", "tests/test_golden.py", "tests/test_run_all.py"):
        assert any("slots.fan(" in ln for ln in code(f)), f"{f} does not fan out through slots.fan (in code)"


def t_c10_holders_and_waiters_are_listed(tmp):
    pool, log = tmp / "pool", tmp / "log"
    a = scratch(tmp / "a", ["h0"], {"h0": KEEP})
    b = scratch(tmp / "b", ["n0"])
    ga = gate(a, env_for(pool, 1, log, SLOT_SLEEP=60))
    gb = None
    try:
        assert wait_for(lambda: len(spans(log)) == 1 and locked(pool) == 1, 20), "the holder never held the slot"
        holder = int(next(iter(spans(log)))[1])
        gb = gate(b, env_for(pool, 1, tmp / "logb", SLOT_SLEEP=0.2))
        listing = lambda: subprocess.run([PY, str(a / "cc" / "slots.py")], capture_output=True, text=True, env=env_for(pool, None, log)).stdout
        assert wait_for(lambda: f"wait pid {gb.pid} " in listing(), 20), f"the waiting gate {gb.pid} is not listed: {listing()!r}"
        out = listing().splitlines()
        assert any(ln.startswith(f"slot-0 held pid {holder} ") for ln in out), f"slot-0 must name its holder {holder}: {out}"
        os.killpg(ga.pid, signal.SIGKILL)
        rc, outb = finish(gb, 30)
        assert rc == 0, f"the waiter did not run after the holder died: rc {rc}: {outb[-200:]}"
        out = listing().splitlines()
        assert out == ["slot-0 free"], f"after both gates: {out}"
    finally:
        for g in (ga, gb):
            if g is not None:
                try:
                    os.killpg(g.pid, signal.SIGKILL)
                except (ProcessLookupError, PermissionError):
                    pass
                g.wait()


PROCS = '''import multiprocessing, os, sys, threading, time
from pathlib import Path
sys.path.insert(0, str(Path(sys.argv[1]) / "cc"))
import slots


def work(i):
    with open(os.environ["SLOT_LOG"], "a") as f: f.write(f"start w{i} {os.getpid()} {time.time()}\\n")
    time.sleep(0.6)
    with open(os.environ["SLOT_LOG"], "a") as f: f.write(f"end w{i} {os.getpid()} {time.time()}\\n")
    return i * i


if __name__ == "__main__":
    most, stop = [0], threading.Event()
    def watch():
        while not stop.is_set():
            most[0] = max(most[0], len(multiprocessing.active_children()))
            time.sleep(0.02)
    threading.Thread(target=watch, daemon=True).start()
    got = slots.fan(work, range(6), 4, procs=True)
    stop.set()
    print(got, most[0])
'''


def t_c11_procs_mode_is_capped(tmp):
    pool, log = tmp / "pool", tmp / "log"
    repo = scratch(tmp / "r", ["unused"])
    (tmp / "procs_driver.py").write_text(PROCS)
    r = subprocess.run([PY, str(tmp / "procs_driver.py"), str(repo)], capture_output=True, text=True, env=env_for(pool, 2, log), timeout=120)
    assert r.returncode == 0, f"rc {r.returncode}: {r.stderr[-400:]}"
    got, most = r.stdout.strip().rsplit(" ", 1)
    assert got == str([i * i for i in range(6)]), f"results out of order or wrong: {got}"
    assert peak(log) == 2, f"procs=True, pool 2: {peak(log)} items computed at once"
    assert int(most) <= 2, f"procs=True, pool 2: {most} child processes alive at once (an idle pool beside the slots)"
    pids = {ln.split()[2] for ln in log.read_text().splitlines() if ln.startswith("start ")}
    assert len(pids) == 6, f"procs=True: 6 items ran in {len(pids)} processes (a worker outlived its item and its slot)"


TESTS = [t_c01_two_gates_never_exceed_the_pool, t_c02_one_gate_is_capped, t_c03_failure_names_unchanged, t_c04_nested_call_never_deadlocks,
         t_c05_kill9_of_a_gate_frees_its_slots, t_c06_orphan_worker_keeps_its_slot, t_c07_bad_jobs_refused_by_name, t_c08_one_host_one_pool,
         t_c09_one_way_to_fan_out, t_c10_holders_and_waiters_are_listed, t_c11_procs_mode_is_capped]


def _run(t):
    if t.__code__.co_argcount == 0:
        return t()
    tmp = Path(tempfile.mkdtemp(prefix="cc-slots-"))
    try:
        return t(tmp)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


for _t in TESTS:   # pytest collects test_* names
    globals()["test_" + _t.__name__[2:]] = (lambda t: lambda: _run(t))(_t)


if __name__ == "__main__":
    n = 0
    for t in TESTS:
        try:
            _run(t)
            print(f"PASS {t.__name__[2:]}")
            n += 1
        except Exception as e:  # noqa: BLE001
            print(f"FAIL {t.__name__[2:]}: {type(e).__name__}: {str(e)[:300]}")
    print(f"{n}/{len(TESTS)} passed")
    sys.exit(0 if n == len(TESTS) else 1)
