"""test_fail_lines - a failing test's FAIL lines are never cut off by the 8-line tail of `bin/cc test` (plan 1640 amendment G).
A scratch copy holds one planted test of 20 output lines whose FIRST line is `    FAIL planted_first`; the run must print it. Planted: it is the first line, so a tail-only print drops it (RED on 37904a7)."""
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

from lib import bad, check  # noqa: E402

SCRIPT = 'print("    FAIL planted_first: the sub-test that failed")\nfor i in range(19):\n    print(f"ok   p{i:02d}")\nraise SystemExit(1)\n'

with tempfile.TemporaryDirectory() as t:
    repo = Path(t) / "repo"
    repo.mkdir()
    shutil.copytree(ROOT / "bin", repo / "bin")
    shutil.copytree(ROOT / "cc", repo / "cc", ignore=shutil.ignore_patterns("__pycache__"))
    (repo / "tests").mkdir()
    (repo / "tests" / "t_plant.py").write_text(SCRIPT)
    (repo / "checks.toml").write_text('[roles]\ntests = ["tests/t_plant.py"]\n')
    (repo / "cc.toml").write_text((ROOT / "cc.toml").read_text())
    r = subprocess.run([sys.executable, str(repo / "bin" / "cc"), "test"], capture_output=True, text=True, cwd=repo)
    out = r.stdout + r.stderr
check("the planted test fails the run", r.returncode == 1, out[:300])
check("the first FAIL line of a failing test is printed though 19 lines follow it", "planted_first" in out, out)
print("test_fail_lines: " + ("FAILED" if bad else "all passed"))
sys.exit(1 if bad else 0)
