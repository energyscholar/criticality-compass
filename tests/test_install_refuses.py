"""test_install_refuses - plan 0985 phase 3: a wheel carries only the tests the freeze gate names (test_wheel), so `bin/cc check` / `bin/cc test` in such a
workspace REFUSE with a Next line (the clone holds the tests), never a list of 'can't open file' failures. Planted: a workspace copy with no tests/."""
import shutil
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


with tempfile.TemporaryDirectory() as t:
    ws = Path(t) / "ws"
    ws.mkdir()
    for d in ("bin", "cc"):
        shutil.copytree(ROOT / d, ws / d, ignore=shutil.ignore_patterns("__pycache__", "_ext", "*.pyc"))
    for f in ("cc.toml", "checks.toml"):
        shutil.copy2(ROOT / f, ws / f)
    for args in (["check", "--fast"], ["test", "test_kernel"]):
        r = subprocess.run([sys.executable, str(ws / "bin" / "cc"), *args], capture_output=True, text=True, cwd=ws)
        out = r.stdout + r.stderr
        check(f"`bin/cc {' '.join(args)}` without tests/ REFUSES, exit 1, with a Next line", r.returncode == 1 and out.startswith("REFUSED: ") and "Next: " in out, out[:200])
        check(f"`bin/cc {' '.join(args)}` without tests/ prints no 'can't open file' failure", "can't open file" not in out, out[:200])
print("test_install_refuses: " + ("FAILED " + "; ".join(bad) if bad else "ok"))
sys.exit(1 if bad else 0)
