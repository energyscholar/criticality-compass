"""test_v06_locks - plan 0872: the signature-column locks of expected/<set>.toml that tests/test_probe.py does not read: [across.*] and [stability.*] hold a point -> allowed
code (or LIST of allowed codes) of that SIGNATURE column, declared before the run; read against the STORED result of that input under that set. A point not named is unlocked."""
import json
import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
bad, n = [], 0
for f in sorted((ROOT / "expected").glob("*.toml")):
    lock = tomllib.loads(f.read_text())
    for col in ("across", "stability"):
        for inp, want in lock.get(col, {}).items():
            got = {s["point"]: s[col] for s in json.loads((ROOT / "results" / f"{inp}@{f.stem}.json").read_text())["signature"]}
            miss = {p: (w, got.get(p)) for p, w in want.items() if got.get(p) not in ([w] if isinstance(w, str) else w)}
            n += len(want)
            print(("ok   " if not miss else "FAIL ") + f"{inp} under {f.stem}: the {col} lock ({len(want)} points)" + (f": {miss}" if miss else ""))
            bad += [f"{inp} {col}"] * bool(miss)
print(f"{n} locked cells read")
sys.path[:0] = [str(ROOT / "cc"), str(ROOT / "cc" / "instruments")]
import detect  # noqa: E402
import score  # noqa: E402
v06 = json.loads((ROOT / "results" / "x2b-xy-2@v06-rules.json").read_text())
for old in ("v05-rules", "v03-rules"):
    try:
        got = score.reverdict_result(v06, detect.load_tables(old))
        ok = {s["point"]: s["verdict"] for s in got["signature"]} and not any(r["instrument"] in ("across_delta", "transform") for r in got["readings"])
        print(("ok   " if ok else "FAIL ") + f"x2b-xy-2 re-verdicted from v06-rules under {old}: no reading the set does not read is carried")
        bad += [] if ok else [old]
    except KeyError as e:
        print(f"FAIL x2b-xy-2 re-verdicted from v06-rules under {old}: KeyError {e}")
        bad.append(old)
print("".join(f"FAILED {x}\n" for x in bad) + "test_v06_locks: " + ("FAILED" if bad else "all passed"))
sys.exit(1 if bad else 0)
