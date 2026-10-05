"""test_pool - a measuring pool is sized from the declared memory budget and the recorded peaks (plan 0881 P1.1): a result records
its input's peak resident memory; the pool is max(1, floor(memory_gb*1024 / largest peak)) at most cpu_count-2; an input with no
recorded peak counts as the largest recorded one. Planted: an input declaring 4 GB must give a pool of one."""
import json
import sys
import tempfile
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path[:0] = [str(ROOT / "cc"), str(ROOT / "cc" / "instruments")]
import detect  # noqa: E402
import resources  # noqa: E402

bad = []


def check(name, ok, why=""):
    print(("ok   " if ok else "FAIL ") + name + ("" if ok else f": {why}"))
    if not ok:
        bad.append(name)


gb = tomllib.loads((ROOT / "cc.toml").read_text())["check"]["memory_gb"]
check("cc.toml declares memory_gb", isinstance(gb, (int, float)) and gb > 0, str(gb))
check("a 1.1 GB peak and 8 cpus: the budget decides, not the cpu count",
      resources.pool_size(5.0, {"a": 1100.0, "b": 600.0}, 64) == 4, str(resources.pool_size(5.0, {"a": 1100.0, "b": 600.0}, 64)))
check("many cpus, small peaks: cpu_count-2 is the cap", resources.pool_size(5.0, {"a": 100.0}, 8) == 6)
check("PLANT: an input declaring 4 GB makes the pool one", resources.pool_size(5.0, {"a": 600.0, "big": 4096.0}, 64) == 1)
check("an input with no recorded peak counts as the largest recorded",
      resources.pool_size(5.0, {"a": 1100.0, "b": None}, 64) == resources.pool_size(5.0, {"a": 1100.0, "b": 1100.0}, 64) == 4)
check("no peak recorded at all: a pool of one", resources.pool_size(5.0, {"a": None}, 64) == 1)
check("a peak above the whole budget still gives one worker", resources.pool_size(5.0, {"a": 9000.0}, 64) == 1)
with tempfile.TemporaryDirectory() as t:
    (Path(t) / "results").mkdir()
    (Path(t) / "results" / "x@s.json").write_text(json.dumps({"peak_rss_mb": 4096.0}))
    (Path(t) / "results" / "y@s.json").write_text(json.dumps({}))
    got = resources.recorded_peaks(t, ["x", "y", "z"], "s")
    check("recorded_peaks reads the result's peak; none recorded or no result is None", got == {"x": 4096.0, "y": None, "z": None}, str(got))
res = detect.run("b7-at-line", "v01-rules", write=False, reuse=False)
check("a measured result records its peak resident memory in MB", isinstance(res.get("peak_rss_mb"), float) and res["peak_rss_mb"] > 10, str(res.get("peak_rss_mb")))
print("test_pool: " + ("FAILED" if bad else "all passed"))
sys.exit(1 if bad else 0)
