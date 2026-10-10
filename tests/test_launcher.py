"""test_launcher - the `compass` launcher runs bin/cc from the clone it sits in, and REFUSES (with a Next line) when it was copied out of a clone
(a non-editable install). Plan 0929 P2. No pip: the launcher module is run directly, from the clone and from a copy in a scratch directory."""
import shutil
import subprocess
import sys
import tempfile
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
bad = []


def check(name, ok, why=""):
    print(("ok   " if ok else "FAIL ") + name + ("" if ok else f": {why}"))
    if not ok:
        bad.append(name)


def launch(pkg_parent, *args):
    r = subprocess.run([sys.executable, "-c", "import criticality_compass, sys; sys.exit(criticality_compass.main(sys.argv[1:]))", *args],
                       capture_output=True, text=True, cwd=pkg_parent, env={"PYTHONPATH": str(pkg_parent), "PATH": "/usr/bin:/bin"})
    return r.returncode, r.stdout + r.stderr


rc, out = launch(ROOT, "help")
check("from the clone: `help` is bin/cc's help", rc == 0 and out.startswith("cc - Criticality Compass"), out[:200])
with tempfile.TemporaryDirectory() as t:
    shutil.copytree(ROOT / "criticality_compass", Path(t) / "criticality_compass", ignore=shutil.ignore_patterns("__pycache__"))
    rc, out = launch(Path(t), "help")
    check("copied out of a clone: REFUSED with `Next: pip install -e`", rc == 1 and out.startswith("REFUSED: ") and "Next: pip install -e" in out, out[:200])
rc, out = launch(ROOT, "--help")
check("`--help` is the help text, exit 0", rc == 0 and out.startswith("cc - Criticality Compass"), out[:200])
rc, out = launch(ROOT, "no-such-command")
check("an unknown command exits non-zero", rc != 0 and "unknown command" in out, f"{rc} {out[:200]}")
with tempfile.TemporaryDirectory() as t:   # a non-editable install: the launcher sits beside a packaged workspace/ (setup.py), no clone above it
    pkg = Path(t) / "criticality_compass"
    shutil.copytree(ROOT / "criticality_compass", pkg, ignore=shutil.ignore_patterns("__pycache__"))
    for d in ("bin", "cc"):
        shutil.copytree(ROOT / d, pkg / "workspace" / d, ignore=shutil.ignore_patterns("__pycache__", "_ext"))
    shutil.copy2(ROOT / "cc.toml", pkg / "workspace" / "cc.toml")
    rc, out = launch(Path(t), "help")
    check("packaged workspace: `help` runs from site-packages shape", rc == 0 and out.startswith("cc - Criticality Compass"), out[:200])
setup = (ROOT / "setup.py").read_text()
check("setup.py packages the runtime trees", all(f'"{d}"' in setup for d in ("bin", "cc", "tables", "inputs", "results")))
pp = tomllib.loads((ROOT / "pyproject.toml").read_text())["project"]
check("the console script is `compass`, never `cc`", list(pp["scripts"]) == ["compass"], str(pp["scripts"]))
check("the kernel is a declared optional extra", "kernel" in tomllib.loads((ROOT / "pyproject.toml").read_text())["project"]["optional-dependencies"])
check("requires-python is >=3.11", pp["requires-python"] == ">=3.11")
print("test_launcher: " + ("FAILED " + ", ".join(bad) if bad else "ok"))
sys.exit(1 if bad else 0)
