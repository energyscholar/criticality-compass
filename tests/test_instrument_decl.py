"""test_instrument_decl - plan 1282 P2a (R-P2.3): one instrument loader (cc/instrument_decl.py) fills the optional fields from ONE declared defaults
table; no reader restates a default. (a) DEFAULT's keys are optional fields of the instrument schema, read from cc/declare.py by ast (the dict literal
passed as the optional-fields argument of shape(...) in chk_instrument); (b) load of an instrument without per_point gives False, of across_delta True;
(c) `git grep -n 'get("per_point"' -- cc bin` has no hit.
Seen RED on 3e0b80f: (a) and (b) FAIL on ModuleNotFoundError (cc/instrument_decl.py absent), caught by guarded; (c) FAILs with 4 hits."""
import ast
import subprocess
import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path[:0] = [str(ROOT / "cc"), str(ROOT / "cc" / "instruments")]

bad = []


def check(name, ok, why=""):
    print(("ok   " if ok else "FAIL ") + name + ("" if ok else f": {why}"))
    if not ok:
        bad.append(name)


def guarded(name, fn):
    """Run one test; an exception (a ModuleNotFoundError on a tree without cc/instrument_decl.py) is that test's FAIL, never a crash of the file."""
    try:
        fn()
    except Exception as e:  # noqa: BLE001
        check(name, False, f"{type(e).__name__}: {e}")


def optional_fields():
    """The keys of the optional-fields dict literal of the shape(...) call in declare.chk_instrument."""
    fn = next(n for n in ast.walk(ast.parse((ROOT / "cc" / "declare.py").read_text())) if isinstance(n, ast.FunctionDef) and n.name == "chk_instrument")
    call = next(n for n in ast.walk(fn) if isinstance(n, ast.Call) and getattr(n.func, "id", None) == "shape")
    return {k.value for k in call.args[3].keys}


def a():
    import instrument_decl
    opt = optional_fields()
    check("A DEFAULT's keys are optional fields of the instrument schema", set(instrument_decl.DEFAULT) <= opt and "per_point" in opt, f"{sorted(instrument_decl.DEFAULT)} vs {sorted(opt)}")


def b():
    import instrument_decl
    without = sorted(f.stem for f in (ROOT / "instruments").glob("*.toml") if "per_point" not in tomllib.loads(f.read_text()))
    check("B an instrument without per_point loads False", bool(without) and instrument_decl.load(without[0], ROOT)["per_point"] is False, str(without[:1]))
    check("B across_delta loads True", instrument_decl.load("across_delta", ROOT)["per_point"] is True)


def c():
    hits = subprocess.run(["git", "grep", "-n", 'get("per_point"', "--", "cc", "bin"], cwd=ROOT, capture_output=True, text=True).stdout.splitlines()
    check("C no reader restates the per_point default", hits == [], f"{len(hits)} hits: {hits}")


for name, fn in (("A", a), ("B", b), ("C", c)):
    guarded(name, fn)
print("".join(f"FAILED {x}\n" for x in bad) + "test_instrument_decl: " + ("FAILED" if bad else "all passed"))
sys.exit(1 if bad else 0)
