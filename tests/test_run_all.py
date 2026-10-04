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
import quick  # noqa: E402

SET = "v03-rules"


def measure(name):
    t0 = time.time()
    if name in quick.heavy("test_run_all", "inputs"):   # `check --quick`: the declared heavy input is read from storage, not re-measured
        res, _, problem = quick.stored(ROOT, name, SET)
        if problem:
            raise SystemExit(f"test_run_all: FAILED quick cannot read the stored {name}:\n{problem}")
        return name, {s["point"]: s["verdict"] for s in res["signature"]}, time.time() - t0
    got = {s["point"]: s["verdict"] for s in detect.run(name, SET, write=False)["signature"]}
    return name, got, time.time() - t0


if __name__ == "__main__":
    names = sorted(p.name for p in (ROOT / "inputs").iterdir() if p.is_dir() and not p.name.startswith("TEMPLATE"))
    expected = tomllib.loads((ROOT / "expected" / f"{SET}.toml").read_text())["verdicts"]
    with ProcessPoolExecutor(max(1, (os.cpu_count() or 3) - 2)) as pool:
        done = list(pool.map(measure, names))
    got = {name: g for name, g, _ in done}
    for name, secs in quick.heavy("test_run_all", "inputs").items():
        quick.note("test_run_all", "inputs", name, secs)
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
