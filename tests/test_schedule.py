"""test_schedule - `bin/cc check` runs the tests named in cc.toml [check] exclusive ALONE, after the parallel batch (plan 0881 P1.2).
A scratch copy with three 1-second tests (two ordinary, one exclusive) logs each one's start and end; the exclusive one must start
after every other has ended, and the ordinary ones must still overlap. Planted: an empty exclusive list lets it overlap (RED)."""
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
bad = []


def check(name, ok, why=""):
    print(("ok   " if ok else "FAIL ") + name + ("" if ok else f": {why}"))
    if not ok:
        bad.append(name)


SCRIPT = 'import time\nfrom pathlib import Path\nL = Path(__file__).parent / "log.txt"\nwith L.open("a") as f: f.write(f"start {Path(__file__).stem} {time.time()}\\n")\ntime.sleep(1)\nwith L.open("a") as f: f.write(f"end {Path(__file__).stem} {time.time()}\\n")\n'


def spans(exclusive):
    with tempfile.TemporaryDirectory() as t:
        repo = Path(t) / "repo"
        repo.mkdir()
        shutil.copytree(ROOT / "bin", repo / "bin")
        shutil.copytree(ROOT / "cc", repo / "cc", ignore=shutil.ignore_patterns("__pycache__"))
        (repo / "tests").mkdir()
        for n in ("t_a", "t_b", "t_x"):
            (repo / "tests" / f"{n}.py").write_text(SCRIPT)
        (repo / "checks.toml").write_text('[roles]\ntests = ["tests/t_a.py", "tests/t_b.py", "tests/t_x.py"]\n')
        cfg = (ROOT / "cc.toml").read_text().replace('exclusive = ["test_run_all"]', f"exclusive = {exclusive}")
        (repo / "cc.toml").write_text(cfg)
        r = subprocess.run([sys.executable, str(repo / "bin" / "cc"), "test"], capture_output=True, text=True, cwd=repo)
        out = {}
        for ln in (repo / "tests" / "log.txt").read_text().splitlines():
            kind, name, ts = ln.split()
            out.setdefault(name, {})[kind] = float(ts)
        return out, r.stdout + r.stderr


alone, txt = spans('["t_x"]')
check("the exclusive test starts after every other test has ended", alone["t_x"]["start"] >= max(alone[n]["end"] for n in ("t_a", "t_b")), str(alone) + txt[:200])
check("the other tests still run in parallel", alone["t_b"]["start"] < alone["t_a"]["end"], str(alone))
check("results print in checks.toml order", txt.index("t_a") < txt.index("t_b") < txt.index("t_x"), txt)
shared, _ = spans("[]")
check("PLANT: with no exclusive list the third test overlaps the others (the check above can fail)",
      shared["t_x"]["start"] < max(shared[n]["end"] for n in ("t_a", "t_b")), str(shared))
print("test_schedule: " + ("FAILED" if bad else "all passed"))
sys.exit(1 if bad else 0)
