"""slots - plan 1559: a host-wide pool of worker slots, the one way the gate fans work out.
A slot is a lock file held by an exclusive flock: the kernel drops it when the last descriptor closes, so a dead holder holds nothing and
nothing reaps. `run` hands the descriptor to the worker, so a live worker is counted even when its coordinator is gone. The pool size is
the pool's own (<pool>/JOBS, written once); lineage is the process tree: a fan below a holder gets that holder's slot to use in turn.
`python cc/slots.py` lists every holder and every waiter."""
import concurrent.futures as futures
import fcntl
import multiprocessing
import os
import subprocess
import sys
import threading
import time
from pathlib import Path

DEFAULT_JOBS = 8
POLL_S = 0.05
PID_WIDTH = 12   # a record is rewritten in place at this width, so a reader never sees it empty or torn


class Refused(ValueError):
    """A pool setting refused by name (the text starts REFUSED: CC_JOBS)."""


def pool_dir():
    set_ = os.environ.get("CC_SLOTS")
    d = Path(set_) if set_ else Path(os.path.expanduser("~")) / ".cache" / "criticality-compass" / "slots"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _count(text):
    """The positive integer a text spells, else 0."""
    try:
        return max(0, int(text or 0))
    except ValueError:
        return 0


def jobs():
    """The pool's size: <pool>/JOBS, created once and atomically from CC_JOBS or the default; a disagreeing CC_JOBS is refused."""
    d, want = pool_dir(), os.environ.get("CC_JOBS")
    if want is not None and not _count(want):
        raise Refused(f"REFUSED: CC_JOBS={want!r} is not a positive integer\n  Next: unset CC_JOBS, or set it to a number of slots, e.g. CC_JOBS=8")
    tmp = d / f"JOBS.{os.getpid()}.{threading.get_ident()}"
    tmp.write_text(f"{_count(want) or DEFAULT_JOBS}\n")
    try:
        os.link(tmp, d / "JOBS")
    except FileExistsError:
        pass
    tmp.unlink()
    size = _count((d / "JOBS").read_text())
    if want is not None and _count(want) != size:
        raise Refused(f"REFUSED: CC_JOBS={want} disagrees with the pool of {size} slots at {d}\n  Next: unset CC_JOBS, or remove {d / 'JOBS'} while no gate runs")
    return size


class Slot:
    """An open descriptor holding an exclusive flock on a file of the pool; its text is the pid working in it."""

    def __init__(self, path, fd):
        self.path, self.fd = path, fd

    @classmethod
    def take(cls, path):
        """The slot on `path`, or None while another descriptor holds it."""
        fd = os.open(path, os.O_RDWR | os.O_CREAT, 0o644)
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            os.close(fd)
            return None
        return cls(path, fd)

    def mark(self, pid):
        os.pwrite(self.fd, f"{pid:<{PID_WIDTH}d}".encode(), 0)

    def release(self):
        if self.fd is not None:
            os.close(self.fd)
            self.fd = None


class Inherited:
    """The slot an ancestor already holds: one worker at a time works in it, and `release` hands it back to the fan's spares."""
    fd = None

    def __init__(self, spare, lock):
        self.spare, self.lock = spare, lock

    def mark(self, pid):
        pass

    def release(self):
        with self.lock:
            self.spare.append(self)


def acquire(spare, lock):
    """A spare (inherited) slot as soon as one is returned, else a free slot of the pool; waits, never times out, and keeps a wait record."""
    d, size, wait = pool_dir(), jobs(), None
    try:
        while True:
            with lock:
                if spare:
                    return spare.pop()
            for i in range(size):
                if (s := Slot.take(d / f"slot-{i}")) is not None:
                    s.mark(os.getpid())
                    return s
            if wait is None and (wait := Slot.take(d / f"wait-{os.getpid()}-{threading.get_ident()}")) is not None:
                wait.mark(os.getpid())
            time.sleep(POLL_S)
    finally:
        if wait is not None:
            wait.path.unlink(missing_ok=True)
            wait.release()


def _holder(path):
    """None while the file is free (or absent); else (the pid it records, 0 if none yet; when it was last written)."""
    try:
        fd = os.open(path, os.O_RDWR)
    except FileNotFoundError:
        return None
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        return _count(os.pread(fd, PID_WIDTH, 0).decode()), os.fstat(fd).st_mtime
    finally:
        os.close(fd)   # closing a descriptor that took the lock gives it back
    return None


def held(pattern="slot-*"):
    """{pid: count} over the files of the pool matching `pattern` that are held now."""
    out = {}
    for p in sorted(pool_dir().glob(pattern)):
        if (rec := _holder(p)) and rec[0]:
            out[rec[0]] = out.get(rec[0], 0) + 1
    return out


def ancestors(pid=None):
    """This process (or `pid`) and its ancestors, from one `ps`."""
    ps = subprocess.run(["ps", "-Ao", "pid=,ppid="], capture_output=True, text=True).stdout
    parent = {int(a): int(b) for a, b in (ln.split() for ln in ps.splitlines() if ln.strip())}
    chain, pid = [], os.getpid() if pid is None else pid
    while pid > 0 and pid not in chain:
        chain.append(pid)
        pid = parent.get(pid, 0)
    return chain


def nested():
    return bool(set(ancestors()) & set(held()))


def _in_process(fn, item):
    """fn(item) in a fresh process that lives only as long as the call (so it lives only while its slot is held)."""
    with futures.ProcessPoolExecutor(1, mp_context=multiprocessing.get_context("spawn")) as one:
        return one.submit(fn, item).result()


def fan(fn, items, width, procs=False):
    """[fn(item, slot) for item in items], in order, `width` at a time, each inside a slot of the host pool. `procs`: fn(item) runs in its own
    process (fn must be a module-level function)."""
    if procs:
        return fan(lambda item, slot: _in_process(fn, item), items, width)
    jobs()   # a refused setting stops here, before any work
    items, lock = list(items), threading.Lock()
    spare = []
    if nested():
        spare.append(Inherited(spare, lock))

    def one(item):
        slot = acquire(spare, lock)
        try:
            return fn(item, slot)
        finally:
            slot.release()
    with futures.ThreadPoolExecutor(max(1, min(width, len(items)))) as pool:
        return list(pool.map(one, items))


def run(argv, slot, **kw):
    """subprocess.run(argv, **kw) whose child holds the slot too (the descriptor is passed down); the slot then records the child's pid."""
    if kw.pop("capture_output", False):
        kw.update(stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    child = subprocess.Popen(argv, close_fds=True, pass_fds=() if slot.fd is None else (slot.fd,), **kw)
    slot.mark(child.pid)
    out, err = child.communicate()
    return subprocess.CompletedProcess(argv, child.returncode, out, err)


def _line(pid, written):
    age = time.time() - written
    cmd = subprocess.run(["ps", "-o", "command=", "-p", str(pid)], capture_output=True, text=True).stdout.strip()
    return f"{pid} {age:.0f}s {cmd}"


def listing():
    """One line per slot: held (pid, age, command) or free; then one `wait` line per live waiter."""
    d, out = pool_dir(), []
    for i in range(jobs()):
        rec = _holder(d / f"slot-{i}")
        out.append(f"slot-{i} free" if rec is None else f"slot-{i} held pid {_line(*rec)}")
    for p in sorted(d.glob("wait-*")):
        if (rec := _holder(p)):
            out.append(f"wait pid {_line(*rec)}")
    return out


if __name__ == "__main__":
    try:
        print("\n".join(listing()))
    except Refused as e:
        print(e)
        sys.exit(1)
