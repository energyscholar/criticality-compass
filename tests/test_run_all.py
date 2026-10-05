"""test_run_all - one full `run --all` (every input, in-process, nothing written) under the scoreboard's
widest set; every point the expected/<set>.toml lock names must read its locked verdict (plan 0869 P1)."""
import os
import sys
import time
import tomllib
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path[:0] = [str(ROOT / "cc"), str(ROOT / "cc" / "instruments")]
import detect  # noqa: E402
import resources  # noqa: E402

SET = "v03-rules"


def measure(name):
    t0 = time.time()
    got = {s["point"]: s["verdict"] for s in detect.run(name, SET, write=False, reuse=False)["signature"]}
    return name, got, time.time() - t0


if __name__ == "__main__":
    names = sorted(p.name for p in (ROOT / "inputs").iterdir() if p.is_dir() and not p.name.startswith("TEMPLATE"))
    expected = tomllib.loads((ROOT / "expected" / f"{SET}.toml").read_text())["verdicts"]
    memory_gb = tomllib.loads((ROOT / "cc.toml").read_text())["check"]["memory_gb"]
    peaks = resources.recorded_peaks(ROOT, names, SET)
    workers = resources.pool_size(memory_gb, peaks, os.cpu_count() or 3)
    known = [p for p in peaks.values() if p is not None]
    print(f"test_run_all: pool {workers} workers = floor({memory_gb} GB x 1024 / {max(known, default=memory_gb * 1024):.0f} MB largest peak; "
          f"{len(known)} of {len(names)} inputs record one), at most cpu_count-2")
    with ProcessPoolExecutor(workers) as pool:
        done = list(pool.map(measure, names))
    got = {name: g for name, g, _ in done}
    if os.environ.get("CC_VERBOSE") == "1":
        print("".join(f"seconds {sec:7.1f}  {name}\n" for name, _, sec in sorted(done, key=lambda d: -d[2])), end="")
    bad, n = [], 0
    for name in names:
        for pt, want in expected.get(name, {}).items():
            n += 1
            if got[name].get(pt) != want:
                bad.append(f"{name}:{pt}  expected {want}  run {got[name].get(pt)}")
    print(f"run --all under {SET}: {len(names)} inputs, {n} locked points compared")
    print("".join(f"FAILED {b}\n" for b in bad) + "test_run_all: " + ("FAILED" if bad else "all passed"))
    sys.exit(1 if bad else 0)
