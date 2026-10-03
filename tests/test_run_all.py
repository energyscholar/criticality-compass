"""test_run_all - one full `run --all` (every input, in-process, nothing written) under the scoreboard's
widest set; every point the expected/<set>.toml lock names must read its locked verdict (plan 0869 P1)."""
import os
import sys
import tomllib
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path[:0] = [str(ROOT / "cc"), str(ROOT / "cc" / "instruments")]
import detect  # noqa: E402

SET = "v03-rules"


def measure(name):
    return name, {s["point"]: s["verdict"] for s in detect.run(name, SET, write=False)["signature"]}


if __name__ == "__main__":
    names = sorted(p.name for p in (ROOT / "inputs").iterdir() if p.is_dir() and not p.name.startswith("TEMPLATE"))
    expected = tomllib.loads((ROOT / "expected" / f"{SET}.toml").read_text())["verdicts"]
    with ProcessPoolExecutor(max(1, (os.cpu_count() or 3) - 2)) as pool:
        got = dict(pool.map(measure, names))
    bad, n = [], 0
    for name in names:
        for pt, want in expected.get(name, {}).items():
            n += 1
            if got[name].get(pt) != want:
                bad.append(f"{name}:{pt}  expected {want}  run {got[name].get(pt)}")
    print(f"run --all under {SET}: {len(names)} inputs, {n} locked points compared")
    print("".join(f"FAILED {b}\n" for b in bad) + "test_run_all: " + ("FAILED" if bad else "all passed"))
    sys.exit(1 if bad else 0)
