"""test_probe - plan 0870: the geometry-axis locks of expected/<set>.toml [geometry.*], read against the stored column."""
import json
import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
bad = []


def check(name, ok, why=""):
    print(("ok   " if ok else "FAIL ") + name + ("" if ok else f": {why}"))
    if not ok:
        bad.append(name)


for f in sorted((ROOT / "expected").glob("*.toml")):
    for inp, want in tomllib.loads(f.read_text()).get("geometry", {}).items():
        got = {s["point"]: s["geometry"] for s in json.loads((ROOT / "results" / f"{inp}@{f.stem}.json").read_text())["signature"]}
        miss = {p: (w, got[p]) for p, w in want.items() if got[p] not in ([w] if isinstance(w, str) else w)}
        check(f"{inp} under {f.stem}: the geometry lock (declared before the run)", not miss and set(got) == set(want), str(miss))
print("".join(f"FAILED {x}\n" for x in bad) + "test_probe: " + ("FAILED" if bad else "all passed"))
sys.exit(1 if bad else 0)
