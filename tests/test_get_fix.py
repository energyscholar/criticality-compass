"""test_get_fix - plan 1644 T9: the five G-FIX tables are indexed, and an indexed table is the base `.get` over every key that reaches it.
G-FIX-1 intake_against.NAMES, G-FIX-2 intake_profile.CELLS, G-FIX-3 intake_profile.BIN, G-FIX-4 intake_differs (the names row of a header kind),
G-FIX-6 oracle_measured.OUTCOME. For each: over the alphabet the table is indexed with, the head's result equals the base module's result (the base source is read
with `git show`, run as a private module); a key outside the alphabet is a KeyError (at the base it returned the default). A clone without the base commit FAILS with a Next line."""
import subprocess
import sys
from dataclasses import asdict
import types
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Path(__file__).resolve().parent))
from lib import bad, bootstrap, check, guarded  # noqa: E402

bootstrap(ROOT, "cc")
import intake_against  # noqa: E402
import intake_differs  # noqa: E402
import intake_profile  # noqa: E402
import intake_read  # noqa: E402
import oracle_measured  # noqa: E402

BASE = "c9954ba"   # the plan-1639-dist tip this plan branched from (D0)


def base_module(name):
    r = subprocess.run(["git", "-C", str(ROOT), "show", f"{BASE}:cc/{name}.py"], capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(f"the base commit {BASE} is not in this clone: {r.stderr.strip()[:120]}\n  Next: fetch the plan-1639-dist history (git fetch), then rerun")
    m = types.ModuleType(f"base_{name}")
    m.__file__ = str(ROOT / "cc" / f"{name}.py")
    exec(compile(r.stdout, f"{BASE}:cc/{name}.py", "exec"), m.__dict__)
    return m


def keyerror(fn):
    try:
        fn()
    except KeyError:
        return True
    except Exception:   # noqa: BLE001 - any other exception is not the declared refusal
        return False
    return False


def t9():
    ba, bd, bp, bo = (base_module(n) for n in ("intake_against", "intake_differs", "intake_profile", "oracle_measured"))
    kinds = tuple(intake_read.HEADER)
    h = {"kind": "", "rows": 2, "names": 2, "units": 3, "unit_syntax": "PAREN"}
    cells = ["T (K)", "M", ""]
    for k in kinds:
        check(f"T9 G-FIX-1 NAMES[{k}] equals the base .get result", intake_against.NAMES[k](h, cells) == ba.NAMES.get(k, lambda h, cs: list(cs))(h, cells), "")
    check("T9 G-FIX-1 NAMES has a row for every header kind (total over HEADER)", set(intake_against.NAMES) == set(kinds), str(sorted(intake_against.NAMES)))
    check("T9 G-FIX-1 an unknown header kind is a KeyError", keyerror(lambda: intake_against.NAMES["NO_SUCH_KIND"](h, cells)), "")
    lines = [(1, "T,M"), (2, "1,2"), (3, "3,4")]
    for d in ("COMMA", "SEMICOLON", "TAB", "WHITESPACE", "NONE"):
        want, got = bp.CUT.get(d, lambda t: [t])("a,b;c\td e"), intake_profile.CELLS[d]("a,b;c\td e")
        check(f"T9 G-FIX-2 CELLS[{d}] equals the base .get result", want == got, f"{want} / {got}")
        check(f"T9 G-FIX-2 table(..., {d}) equals the base table", asdict(bp.table(lines, d, ())) == asdict(intake_profile.table(lines, d, ())), "")   # two module copies are two classes: compare as plain values
    check("T9 G-FIX-2 an unknown delimiter is a KeyError", keyerror(lambda: intake_profile.CELLS["PIPE"]), "")
    for n in range(1, 31):
        check(f"T9 G-FIX-3 BIN for a run of {n} equals the base .get result", intake_profile.BIN[min(n, 10)] == bp.BIN.get(min(n, 10)), "")
    pairs = [(i + 1, v) for i, v in enumerate([1.0, 1.0, 2.0, 2.0, 2.0, 3.0] + [4.0] * 12 + [5.0, 1.0])]
    check("T9 G-FIX-3 order() of a column with runs of 1, 2, 3 and 12 equals the base", intake_profile.order(pairs) == bp.order(pairs), "")
    check("T9 G-FIX-3 a run of 0 is a KeyError", keyerror(lambda: intake_profile.BIN[0]), "")
    for k in kinds:
        spec = {"comment": [], "format": {"kind": "COMMA"}, "header": {**h, "kind": k}}
        d = {"reader": {"name": "table-curve-v1", **spec}}
        data = b"T,M\n1,2\n3,4\n"
        check(f"T9 G-FIX-4 lined() under header kind {k} equals the base", intake_differs.lined(data, d) == bd.lined(data, d), "")
    for key in ((True, True, False), (True, True, True), (True, False, False), (True, False, True), (False, True, False), (False, True, True), (False, False, False), (False, False, True)):
        check(f"T9 G-FIX-6 OUTCOME{key} equals the base .get result", oracle_measured.OUTCOME[key] == {(True, True, False): "BRACKET"}.get(key, "REFUSE"), "")
    check("T9 G-FIX-6 OUTCOME has all 8 rows, BRACKET in one", len(oracle_measured.OUTCOME) == 8 and list(oracle_measured.OUTCOME.values()).count("BRACKET") == 1, "")
    check("T9 G-FIX-6 a key outside the three bools is a KeyError", keyerror(lambda: oracle_measured.OUTCOME[(1, 2, 3)]), "")


guarded("T9", t9)
print("test_get_fix: " + ("FAILED " + "; ".join(bad) if bad else "all passed"))
sys.exit(1 if bad else 0)
