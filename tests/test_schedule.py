"""test_schedule - `bin/cc check` runs the tests named in cc.toml [check] exclusive ALONE, after the parallel batch (plan 0881 P1.2).
A scratch copy with 1-second tests (WORKERS ordinary, one exclusive; WORKERS = max(2, cpu_count - 2), the pool bin/cc builds) logs each one's start and end; the exclusive one must start
after every other has ended, and the ordinary ones must still overlap. Planted: an empty exclusive list lets it overlap (RED). The exclusive test is listed FIRST so it is in the pool's first batch whatever the host's core count."""
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
bad = []
WORKERS = max(2, (os.cpu_count() or 3) - 2)   # bin/cc: ThreadPoolExecutor(max(1, cpu_count - 2)); two ordinary tests are the least the parallel check needs
ORD = [f"t_{i}" for i in range(WORKERS)]
NAMES = ["t_x"] + ORD


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
        for n in NAMES:
            (repo / "tests" / f"{n}.py").write_text(SCRIPT)
        (repo / "checks.toml").write_text("[roles]\ntests = [" + ", ".join(f'"tests/{n}.py"' for n in NAMES) + "]\n")
        cfg = (ROOT / "cc.toml").read_text().replace('exclusive = ["test_run_all"]', f"exclusive = {exclusive}")
        (repo / "cc.toml").write_text(cfg)
        r = subprocess.run([sys.executable, str(repo / "bin" / "cc"), "test"], capture_output=True, text=True, cwd=repo)
        out = {}
        for ln in (repo / "tests" / "log.txt").read_text().splitlines():
            kind, name, ts = ln.split()
            out.setdefault(name, {})[kind] = float(ts)
        return out, r.stdout + r.stderr


alone, txt = spans('["t_x"]')
check("the exclusive test starts after every other test has ended", alone["t_x"]["start"] >= max(alone[n]["end"] for n in ORD), str(alone) + txt[:200])
check("the other tests still run in parallel", alone[ORD[1]]["start"] < alone[ORD[0]]["end"], str(alone))
check("results print in checks.toml order", [txt.index(n) for n in NAMES] == sorted(txt.index(n) for n in NAMES), txt)
shared, _ = spans("[]")
check("PLANT: with no exclusive list the exclusive test overlaps the others (the check above can fail)",
      shared["t_x"]["start"] < max(shared[n]["end"] for n in ORD), str(shared))
print("test_schedule: " + ("FAILED" if bad else "all passed"))
sys.exit(1 if bad else 0)
