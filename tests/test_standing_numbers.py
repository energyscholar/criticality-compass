"""test_standing_numbers - plan 1337 T6 (slow, needs the data root): moving the declared comparisons into C (project.Comparison) changes the
STANDING of a number, never the number. For k4-m1-ch and x4-ising-field-ch under v10-rules a fresh measure equals the result stored at
1066c43 in every key and nested value but the run's provenance fields (run_id, code_commit, code_hash, measure_hash, data_root_source,
peak_rss_mb, peak_rss_why, read), each pin's toolset `commit` (pins is run provenance stamped by bin/cc, never by detect.run) and the new `standing`, which must say "declared report" for every comparison and the declared provenance
for control. Seen RED on 1066c43 (no `standing` key) by the Auditor on the data host (plan 1337 P-2)."""
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path[:0] = [str(ROOT / "cc"), str(ROOT / "cc" / "instruments")]
import detect  # noqa: E402

BASE = "1066c43"
SKIP = {"run_id", "code_commit", "code_hash", "measure_hash", "data_root_source", "peak_rss_mb", "peak_rss_why", "read", "standing"}
WANT = {"x4-ising-field-ch": {"size": "declared report", "matched": "declared report", "start": "declared report"},
        "k4-m1-ch": {"size": "declared report", "matched": "declared report", "start": "declared report", "chain": "declared report",
                     "control": "Coupling"}}
bad = []


def check(name, ok, why=""):
    print(("ok   " if ok else "FAIL ") + name + ("" if ok else f": {why}"))
    if not ok:
        bad.append(name)


def diff(a, b, path=""):
    """(leaf count, the paths where a and b differ): every nested key and list element compared with ==."""
    if isinstance(a, dict) and isinstance(b, dict):
        keys = sorted(set(a) | set(b))
        out = [diff(a.get(k), b.get(k), f"{path}.{k}") if k in a and k in b else (0, [f"{path}.{k}"]) for k in keys]
        return sum(n for n, _ in out), [p for _, ps in out for p in ps]
    if isinstance(a, list) and isinstance(b, list) and len(a) == len(b):
        out = [diff(x, y, f"{path}[{i}]") for i, (x, y) in enumerate(zip(a, b))]
        return sum(n for n, _ in out), [p for _, ps in out for p in ps]
    return 1, [] if a == b else [path]


for iid, want in WANT.items():
    rid = f"{iid}@v10-rules"
    ref = json.loads(subprocess.run(["git", "show", f"{BASE}:results/{rid}.json"], cwd=ROOT, capture_output=True, text=True, check=True).stdout)
    try:
        new = detect.run(iid, "v10-rules", write=False, reuse=False)
    except Exception as e:  # noqa: BLE001
        check(f"T6 {iid}: measured", False, f"{type(e).__name__}: {e}")
        continue
    # pins is run provenance, stamped by bin/cc (stamp_pins) after detect.run and never by it: each pin's commit is the toolset's git state, so it is
    # not compared; each pin's sha256 is, wherever both sides hold a pins block. A fresh detect.run holds none, so pins is skipped there.
    both = "pins" in ref and "pins" in new
    pins = [({f: v["sha256"] for f, v in ref["pins"].items()}, {f: v["sha256"] for f, v in new["pins"].items()})] if both else []
    n, where = diff({k: v for k, v in ref.items() if k not in SKIP | {"pins"}}, {k: v for k, v in new.items() if k not in SKIP | {"pins"}})
    for a, b in pins:
        n2, w2 = diff(a, b, ".pins.*.sha256")
        n, where = n + n2, where + w2
    print(f"T6 {iid}: {n} leaf fields compared")
    check(f"T6 {iid}: every key and value equals {BASE}'s stored result but the run fields", not where, str(where[:20]))
    check(f"T6 {iid}: standing is {want}", new.get("standing") == want, str(new.get("standing")))
print("".join(f"FAILED {b}\n" for b in bad) + "test_standing_numbers: " + ("FAILED" if bad else "all passed"))
sys.exit(1 if bad else 0)
