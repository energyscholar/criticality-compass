"""lib - plan 1427 D18: the one home of what the tests share. Test infrastructure (checks.toml [roles] test_infrastructure); it reads no data.
`check(name, ok, why="")` prints one result line and records a failure in `bad`; every test's exit reads `bad`. `guarded(name, fn)` runs one test and turns an exception into
that test's FAIL. `bootstrap(root, *rel)` puts <root>/<r> on sys.path for each r, in order. `cc(repo, *args)` runs `bin/cc` of a tree and returns (returncode, stdout+stderr);
`real_root()` is the data root this host resolves (the caller has put cc/ on sys.path); `parse(name, atoms)` is the binding rule's name parser."""
import subprocess
import sys
import tomllib
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


def cc(repo, *args):
    """Run <repo>/bin/cc with `args` in <repo>; returns (returncode, stdout + stderr)."""
    r = subprocess.run([sys.executable, str(repo / "bin" / "cc"), *args], capture_output=True, text=True, cwd=repo)
    return r.returncode, r.stdout + r.stderr


def real_root():
    """The data root the real tree resolves (cc.toml, CC_DATA_ROOT)."""
    import schema
    return schema.resolve_data_root(tomllib.loads((Path(__file__).resolve().parent.parent / "cc.toml").read_text()))[0]


def parse(name, atoms):
    """The set a constant name denotes: ATOM(_OR_ATOM)*, NOT_<ATOM> = the complement within the atoms; None when a part is no atom."""
    out = set()
    for part in name.split("_OR_"):
        neg = part.startswith("NOT_") and part[4:] in atoms
        lit = {True: atoms - {part[4:]}, False: {part} & atoms}[neg]
        if not lit:
            return None
        out |= lit
    return frozenset(out)
