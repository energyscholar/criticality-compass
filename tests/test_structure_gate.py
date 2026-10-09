"""test_structure_gate - the structure gate of `run` can only say 'clean' when the checker SAID clean (plan 0929 blocker b).
Before: a missing checks.py exited 2 with empty stdout, the gate kept only stdout lines, found nothing, and `run` went on UNGATED.
Now a verdict is the checker's last line `-- N finding(s)` with an exit code that agrees; no checker, a crash, or a disagreeing exit is a REFUSAL.
Each scenario runs bin/cc with CC_STRUCTURE_CHECKS pointing at a scratch directory holding a stub checks.py (no data is read: the gate is first)."""
import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
bad = []


def check(name, ok, why=""):
    print(("ok   " if ok else "FAIL ") + name + ("" if ok else f": {why}"))
    if not ok:
        bad.append(name)


def gate(stub):
    """(rc, output) of `bin/cc run b7-at-line --dry` with a stub checker: None = no checks.py at all."""
    with tempfile.TemporaryDirectory() as t:
        if stub is not None:
            (Path(t) / "checks.py").write_text(stub)
        r = subprocess.run([sys.executable, str(ROOT / "bin" / "cc"), "run", "b7-at-line", "--dry"], capture_output=True, text=True,
                           cwd=ROOT, env={**os.environ, "CC_STRUCTURE_CHECKS": t})
        return r.returncode, r.stdout + r.stderr


def refused(out):
    return "REFUSED: the structure checker" in out and "  Next: " in out


rc, out = gate(None)
check("no checker -> REFUSED with a Next line, the run does not go on", rc == 1 and refused(out) and "is not there" in out, out[:300])
rc, out = gate("import sys\nsys.exit(2)\n")
check("a checker that exits 2 with empty stdout -> REFUSED (no verdict)", rc == 1 and refused(out) and "gave no verdict" in out, out[:300])
rc, out = gate("print('clean: 0 findings')\n")
check("a checker with no trailer line -> REFUSED (no verdict)", rc == 1 and refused(out) and "gave no verdict" in out, out[:300])
rc, out = gate("import sys\nprint('clean: 0 findings')\nprint('-- 0 finding(s)')\nsys.exit(1)\n")
check("a trailer that says 0 but an exit code that says 1 -> REFUSED", rc == 1 and refused(out), out[:300])
rc, out = gate("import sys\nprint('C1 branch  x.py:1 if')\nprint('-- 1 finding(s)')\nsys.exit(1)\n")
check("a finding is reported as before", rc == 1 and "C1 branch" in out and not refused(out), out[:300])
rc, out = gate("print('clean: 0 findings')\nprint('-- 0 finding(s)')\n")
check("a checker that said clean lets the run go on (no structure refusal)", "structure checker" not in out, out[:300])
print("test_structure_gate: " + ("FAILED " + ", ".join(bad) if bad else "ok"))
sys.exit(1 if bad else 0)
