"""test_check_summary - `bin/cc check` prints EVERY scoreboard line of every test, read from the test's FULL output (plan 0881 P2.2).
The defect: the summary read only each test's last lines, so the earliest sets fell out of view as sets were added (v01 was never
printed) and a gate summary that can drop a line can drop a FAILURE. A scratch copy gets a planted v01 scoreboard failure (one
expected verdict changed); the summary must SHOW it, and the plant must sit where a tail-only summary would have hidden it."""
import re
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


tmp = Path(tempfile.mkdtemp(prefix="cc-summary-"))
try:
    scratch = tmp / "cc"
    shutil.copytree(ROOT, scratch, ignore=shutil.ignore_patterns(".git", "__pycache__", "*.pyc"))
    ct = scratch / "checks.toml"
    ct.write_text(re.sub(r"(?s)\ntests = \[.*?\n\]\n", '\ntests = ["tests/test_scoreboard.py"]\n', ct.read_text(), count=1))
    cc = scratch / "cc.toml"   # validate names every slow/exclusive/needs_data/needs_rust test: the scratch lists only the one test it runs
    cc.write_text(re.sub(r"(?m)^(slow|exclusive|needs_data|needs_rust) = \[.*?\]", r"\1 = []", cc.read_text()))
    ex = scratch / "expected" / "v01-rules.toml"
    text = ex.read_text()
    m = re.search(r'^(\s*"[^"]+" = )"([A-Z!+-]+)"', text, re.M)   # the first expected verdict of the set: change it
    ex.write_text(text.replace(m.group(0), f'{m.group(1)}"PLANTED"', 1))
    direct = subprocess.run([sys.executable, str(scratch / "tests" / "test_scoreboard.py")], capture_output=True, text=True, cwd=scratch)
    lines = (direct.stdout + direct.stderr).strip().splitlines()
    sb = [ln for ln in lines if ln.startswith("scoreboard ")]
    check("the plant is a v01 scoreboard failure", direct.returncode == 1 and sb and sb[0].startswith("scoreboard v01-rules:") and "of" in sb[0], str(lines[:4]))
    check("the plant sits outside the last 8 lines (a tail-only summary hides it)", sb[0] not in lines[-8:], str(lines[-8:]))
    out = subprocess.run([sys.executable, str(scratch / "bin" / "cc"), "check", "--fast"], capture_output=True, text=True, cwd=scratch).stdout
    shown = [ln for ln in out.splitlines() if ln.startswith("check: scoreboard ")]
    check("the check summary SHOWS the planted v01 line", f"check: {sb[0]}" in shown, "\n".join(shown))
    check("the check summary prints every scoreboard line the test printed", [s[len("check: "):] for s in shown] == sb, f"{len(shown)} of {len(sb)}")
    check("the check reports the failure", "check: FAILED: test_scoreboard" in out)
finally:
    shutil.rmtree(tmp, ignore_errors=True)
print("test_check_summary: " + ("FAILED" if bad else "all passed"))
sys.exit(1 if bad else 0)
