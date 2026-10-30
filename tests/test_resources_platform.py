"""test_resources_platform - the memory high-water mark is a platform table (plan 1335): Linux resets via clear_refs and reports KiB,
macOS has no in-process reset and reports bytes; an unknown platform is an ImportError, never a silent default."""
import importlib
import resource
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path[:0] = [str(ROOT / "cc"), str(ROOT / "cc" / "instruments")]
import resources  # noqa: E402

bad = []


def check(name, ok, why=""):
    print(("ok   " if ok else "FAIL ") + name + ("" if ok else f": {why}"))
    if not ok:
        bad.append(name)


class _RU:
    def __init__(self, v):
        self.ru_maxrss = v


def t1():
    real = resource.getrusage
    try:
        resource.getrusage = lambda who: _RU(2147483648)
        a = resources.peak_mb(resources.PLATFORMS["darwin"])
        resource.getrusage = lambda who: _RU(2097152)
        b = resources.peak_mb(resources.PLATFORMS["linux"])
    finally:
        resource.getrusage = real
    check("T1 darwin ru_maxrss is bytes", a == 2048.0, str(a))
    check("T1 linux ru_maxrss is KiB", b == 2048.0, str(b))


def t2():
    real = sys.platform
    msg = None
    try:
        sys.platform = "sunos5"
        try:
            importlib.reload(resources)
        except ImportError as e:
            msg = str(e)
    finally:
        sys.platform = real
        importlib.reload(resources)
    check("T2 unknown platform raises ImportError naming it", msg is not None and "'sunos5'" in msg and "PLATFORMS" in msg, str(msg))


def t3():
    calls = []
    real = Path.write_text
    try:
        Path.write_text = lambda self, data, *a, **k: calls.append((str(self), data))
        d = resources.reset_peak(resources.PLATFORMS["darwin"])
        n_d = len(calls)
        l = resources.reset_peak(resources.PLATFORMS["linux"])
    finally:
        Path.write_text = real
    check("T3 darwin reset returns False, no write", d is False and n_d == 0, f"{d} {n_d}")
    check("T3 linux reset returns True, one write of '5'", l is True and len(calls) == 1 and calls[0][1] == "5", f"{l} {calls}")
    check("T3 unrecorded keeps a null peak", resources.unrecorded({"x": None}) == ["x"])


t1()
t2()
t3()
sys.exit(1 if bad else 0)
