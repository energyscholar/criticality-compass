"""lib - plan 1427 D18: the one home of what the tests share. Test infrastructure (checks.toml [roles] test_infrastructure); it reads no data.
`check(name, ok, why="")` prints one result line and records a failure in `bad`; every test's exit reads `bad`. `guarded(name, fn)` runs one test and turns an exception into
that test's FAIL. `bootstrap(root, *rel)` puts <root>/<r> on sys.path for each r, in order."""
import sys
from pathlib import Path

bad = []


def check(name, ok, why=""):
    print(("ok   " if ok else "FAIL ") + name + ("" if ok else f": {why}"))
    if not ok:
        bad.append(name)


def guarded(name, fn):
    """Run one test; an exception (the KeyError of a tree without the fix) is that test's FAIL, never a crash of the file."""
    try:
        fn()
    except Exception as e:  # noqa: BLE001
        check(name, False, f"{type(e).__name__}: {e}")


def bootstrap(root, *rel):
    """Put <root>/<r> on sys.path, in front, for each r in `rel`, in the order given. The set is the caller's parameter: this home holds no default."""
    sys.path[:0] = [str(Path(root) / r) for r in rel]
