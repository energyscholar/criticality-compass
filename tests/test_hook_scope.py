"""test_hook_scope - plan 1257, PTL-229: one t23 module per process, and bypass lines owned by partition. Planted temp files only (no data).
 (a)-(d) against vendor/toolset/t23.py, loaded ONCE by path after sys.addaudithook is wrapped by a counter that calls the real one; access
     logs in their own temp dir, outside every bank and partition (the toolset's studies/TAX-B1b/t23_scope_test.py, same fixtures):
 (a)  ONE shared bank, loaders A and B: A built, A.read(f1); B built, B.read(f2) -> A's log gains 0 lines, B's log gains exactly 1 loader line.
 (b)  TWO disjoint banks, loaders C and D: open(fileC).read() -> 1 in-process-bypass line in C's log, 0 lines in D's (preservation).
 (b2) ONE shared bank, loaders E and F: open(f).read() -> exactly 1 bypass line in EACH of E's and F's logs (preservation).
 (c)  ONE shared bank, six loaders built-then-read in turn -> bypass counts 0 0 0 0 0 0, each log exactly 1 loader line (t23.py: 5 4 3 2 1 0).
 (d)  sys.addaudithook calls made by that module across (a)-(c) == 1; then the real sys.addaudithook is restored.
 (e)  the CC shape through CC's own loader, under its own mkdtemp root: six declaration dirs and ONE shared bank <tmp>/banks/universe; for
      k = 1..6, L_k = intake_bytes._t23().Loader(the SOURCE["DEPOSIT"] partitions, decl_k/access.log) (one _t23() CALL per loader), then
      L_k.read(file) -> six bypass counts all 0 and exactly 1 loader line per log; then, outside any read, open(f).read() of one bank file
      -> exactly 1 new bypass line in EACH of the six logs (the shared hook is live, so the zeros are not vacuous).
 (e2) intake_bytes._t23() is intake_bytes._t23(): one t23 module instance per process.
"""
import importlib.util
import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
_real_addaudithook = sys.addaudithook
_hook_calls = []


def _counting_addaudithook(hook):
    _hook_calls.append(hook)
    _real_addaudithook(hook)


sys.addaudithook = _counting_addaudithook
_spec = importlib.util.spec_from_file_location("t23_under_test", ROOT / "vendor" / "toolset" / "t23.py")
t23 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(t23)

LOGS = Path(tempfile.mkdtemp(prefix="hookscope-logs-"))
results = []


def bank(name, n):
    b = Path(tempfile.mkdtemp(prefix=f"hookscope-{name}-"))
    files = [b / f"f{i}.bin" for i in range(1, n + 1)]
    [f.write_bytes(bytes([i]) * 16) for i, f in enumerate(files, 1)]
    return b, files


def records(log):
    p = Path(log)
    return [json.loads(x) for x in p.read_text().splitlines()] if p.exists() else []


def count(log, route):
    return sum(r["route"] == route for r in records(log))


def report(name, ok, detail, note=""):
    results.append(ok)
    print(f"({name}) {'PASS' if ok else 'FAIL'}  {detail}{note}")


# (a) one shared bank, construct-then-read order
b, (f1, f2) = bank("a", 2)
A = t23.Loader({b: "bank"}, LOGS / "A.log")
A.read(f1)
nA = len(records(A.log))
B = t23.Loader({b: "bank"}, LOGS / "B.log")
B.read(f2)
gainA, recB = len(records(A.log)) - nA, records(B.log)
report("a", gainA == 0 and len(recB) == 1 and recB[0]["route"] == "loader",
       f"A's log gained {gainA} line(s) (want 0); B's log holds {len(recB)} line(s), routes {[r['route'] for r in recB]} (want 1 loader)")

# (b) two disjoint banks
bc, (fc,) = bank("bC", 1)
bd, (_fd,) = bank("bD", 1)
C = t23.Loader({bc: "bankC"}, LOGS / "C.log")
D = t23.Loader({bd: "bankD"}, LOGS / "D.log")
with open(fc, "rb") as fh:
    fh.read()
recC, recD = records(C.log), records(D.log)
report("b", len(recC) == 1 and recC[0]["route"] == "in-process-bypass" and len(recD) == 0,
       f"C's log: {[r['route'] for r in recC]} (want 1 in-process-bypass); D's log: {len(recD)} line(s) (want 0)",
       "  [preservation: expected GREEN on t23.py as well]")

# (b2) one shared bank, a direct open is a bypass in EVERY owner's log
be, (fe,) = bank("b2", 1)
E = t23.Loader({be: "bank"}, LOGS / "E.log")
F = t23.Loader({be: "bank"}, LOGS / "F.log")
with open(fe, "rb") as fh:
    fh.read()
recE, recF = records(E.log), records(F.log)
report("b2", [r["route"] for r in recE] == ["in-process-bypass"] and [r["route"] for r in recF] == ["in-process-bypass"],
       f"E's log: {[r['route'] for r in recE]}; F's log: {[r['route'] for r in recF]} (want exactly 1 in-process-bypass each)",
       "  [preservation: expected GREEN on t23.py as well]")

# (c) one shared bank, six loaders, each constructed then read in turn
bl, fl = bank("c", 6)
Ls = []
for k, f in enumerate(fl, 1):
    Ls.append(t23.Loader({bl: "bank"}, LOGS / f"L{k}.log"))
    Ls[-1].read(f)
byp = [count(L.log, "in-process-bypass") for L in Ls]
ldr = [count(L.log, "loader") for L in Ls]
report("c", byp == [0] * 6 and ldr == [1] * 6,
       f"bypass counts: {' '.join(map(str, byp))}  (want 0 0 0 0 0 0); loader lines: {' '.join(map(str, ldr))} (want 1 1 1 1 1 1)")

# (d) hooks installed by the module across (a)-(c), read before (e); then restore the real sys.addaudithook
n_hooks = len(_hook_calls)
sys.addaudithook = _real_addaudithook
report("d", n_hooks == 1, f"sys.addaudithook calls: {n_hooks} (want 1)")

# (e) the CC shape through CC's own loader, under its own root
sys.path[:0] = [str(ROOT / "cc")]
import intake_bytes  # noqa: E402
import intake_seal  # noqa: E402

tmp = Path(tempfile.mkdtemp(prefix="hookscope-e-"))
universe = tmp / "banks" / "universe"
universe.mkdir(parents=True)
files = [universe / f"c{k}.bin" for k in range(1, 7)]
[f.write_bytes(bytes([k]) * 16) for k, f in enumerate(files, 1)]
decls = [tmp / "declarations" / f"d{k}" for k in range(1, 7)]
[d.mkdir(parents=True) for d in decls]
for d, f in zip(decls, files):
    L = intake_bytes._t23().Loader({str(universe): "universe", str(Path(universe).parent): "outside-universe"}, d / "access.log")
    L.read(f)
lines_of = lambda d: intake_seal.lines(d / "access.log")  # noqa: E731
byp_e = [sum(r["route"] == "in-process-bypass" for r in lines_of(d)) for d in decls]
ldr_e = [sum(r["route"] == "loader" for r in lines_of(d)) for d in decls]
with open(files[0], "rb") as fh:
    fh.read()
live = [sum(r["route"] == "in-process-bypass" for r in lines_of(d)) - n for d, n in zip(decls, byp_e)]
report("e", byp_e == [0] * 6 and ldr_e == [1] * 6 and live == [1] * 6,
       f"bypass counts: {' '.join(map(str, byp_e))}  (want 0 0 0 0 0 0); loader lines: {' '.join(map(str, ldr_e))} (want 1 x6); "
       f"new bypass lines after a direct open(): {' '.join(map(str, live))} (want 1 x6: the hook is live)")

# (e2) one t23 module instance per process
same = intake_bytes._t23() is intake_bytes._t23()
report("e2", same, f"intake_bytes._t23() is intake_bytes._t23(): {same} (want True)")

print(f"test_hook_scope: {'PASS' if all(results) else 'FAIL'} ({sum(results)}/{len(results)})")
sys.exit(0 if all(results) else 1)
