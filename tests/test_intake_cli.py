"""test_intake_cli - plan 1139: the intake from the command line on synthetic data. Each check was seen RED under a stated mutation (the
plan-1139 report lists them).
 1. `bin/cc intake synth`: the same seed writes a byte-identical bank (and truth file); a different seed writes a different bank."""
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CC = str(ROOT / "bin" / "cc")
bad = []


def check(name, ok, why=""):
    print(("ok   " if ok else "FAIL ") + name + ("" if ok else f": {why}"))
    if not ok:
        bad.append(name)


def cc(*args, cwd=ROOT):
    return subprocess.run([CC, *args], capture_output=True, text=True, cwd=cwd)


def tree(d):
    """{relative path: bytes} of every file under d."""
    return {q.relative_to(d).as_posix(): q.read_bytes() for q in sorted(Path(d).rglob("*")) if q.is_file()}


# ---- 1. the synthetic bank is a function of its seed
with tempfile.TemporaryDirectory() as tmp:
    runs = {name: cc("intake", "synth", "b", "--seed", seed, "--out", str(Path(tmp) / name)) for name, seed in (("a", "1"), ("a2", "1"), ("c", "2"))}
    check("1. synth exits 0 three times", all(r.returncode == 0 for r in runs.values()), str([r.stdout + r.stderr for r in runs.values()])[:400])
    a, a2, c = (tree(Path(tmp) / n) for n in ("a", "a2", "c"))
    check("1. the bank holds 9 curves and MANIFEST.json, the truth sits beside it", sorted(a) == sorted([f"b/curve_{i:03d}.csv" for i in range(9)] + ["b/MANIFEST.json", "b-TRUTH/truth.json"]), str(sorted(a)))
    check("1. the same seed writes a byte-identical bank and truth file", a == a2, str([k for k in a if a[k] != a2.get(k)])[:200])
    check("1. a different seed writes a different bank", all(a[k] != c[k] for k in a if k.endswith(".csv")), str([k for k in a if k.endswith(".csv") and a[k] == c[k]]))

print("test_intake_cli: " + ("FAILED " + "; ".join(bad) if bad else "all passed"))
sys.exit(1 if bad else 0)
