"""test_axes - plan 0866: geometry x order. compose(geometry, order) = verdict on every row; the predicted order column
of expected/<set>.toml [order.*]; the axis breakers (tests/breakers-axes/*.toml), each of which must turn this test RED
under its own mutation. CC_AXES_INNER=1 (set by the mutation runs) skips the mutation runs, so they do not recurse."""
import os
import shutil
import subprocess
import sys
import tempfile
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path[:0] = [str(ROOT / "cc"), str(ROOT / "cc" / "instruments")]
import declare  # noqa: E402
import detect  # noqa: E402
import score  # noqa: E402

ROWS = 45360       # the signature domain of v02-rules (needle, sink, flow, across, stability, two_start)
bad = []


def check(name, ok, why=""):
    print(("ok   " if ok else "FAIL ") + name + ("" if ok else f": {why}"))
    if not ok:
        bad.append(name)


found, n = declare.factorisation(ROOT, "v02-rules")
check(f"compose(geometry, order) = verdict on every one of {ROWS} rows of v02-rules", not found and n == ROWS, f"{found} {n}")
check("a set without the three axis files has nothing to prove", declare.factorisation(ROOT, "v01-rules") == ([], 0))
with tempfile.TemporaryDirectory() as t:
    shutil.copy(ROOT / "cc.toml", t)
    shutil.copytree(ROOT / "tables" / "v02-rules", Path(t) / "tables" / "v02-rules")
    f = Path(t) / "tables" / "v02-rules" / "compose.toml"
    f.write_text(f.read_text().replace('verdict = "@geometry"', 'verdict = "NOT"'))
    bent, _ = declare.factorisation(t, "v02-rules")
    check("a compose that differs from verdict.toml on some row is refused with the first row", len(bent) == 1 and "differs from verdict.toml" in bent[0].msg, str(bent))
with tempfile.TemporaryDirectory() as t:
    case = Path(t) / "c.toml"
    case.write_text((ROOT / "cases" / "ising-2d.toml").read_text().replace('order_truth = "CONTINUOUS"', 'order_truth = "SIDEWAYS"'))
    got = declare.check_file(case, ROOT)
    check("a case whose order_truth is outside the alphabet is refused", any("'SIDEWAYS' is not in" in f.msg for f in got), str(got))
results = [__import__("json").loads(f.read_text()) for f in sorted((ROOT / "results").glob("*@v02-rules.json"))]
md = score.tabulate(results)[0]
check("tabulate reports the per-axis agreement for a set that has the axes",
      "Order against order_truth: " in md and "Geometry against class_truth (order_truth not FIRST-ORDER): " in md)
for f in sorted((ROOT / "expected").glob("*.toml")):
    for inp, want in tomllib.loads(f.read_text()).get("order", {}).items():
        got = {s["point"]: s["order"] for s in __import__("json").loads((ROOT / "results" / f"{inp}@{f.stem}.json").read_text())["signature"]}
        miss = {p: (w, got[p]) for p, w in want.items() if got[p] not in ([w] if isinstance(w, str) else w)}
        check(f"{inp} under {f.stem}: the predicted order column", not miss and set(got) == set(want), str(miss))
for f in sorted((ROOT / "tests" / "breakers-axes").glob("*.toml")):
    b = tomllib.loads(f.read_text())
    T = detect.load_tables(b["tables"])
    codes = detect.codes_of(b["cells"], T)
    got = detect.axes_of(codes, T)
    got["verdict"] = detect.composed(got["geometry"], got["order"], T)[0]
    check(f"{b['id']}: {b['expect']}", all(got[k] == v for k, v in b["expect"].items()), str({k: got[k] for k in b["expect"]}))
    if not os.environ.get("CC_AXES_INNER"):
        m = b["mutation"]
        r = subprocess.run([str(ROOT / "bin" / "cc"), "mutate", m["file"], "--py", m["py"], "--", "test_axes"], capture_output=True,
                           text=True, cwd=ROOT, env={**os.environ, "CC_AXES_INNER": "1"})
        check(f"{b['id']}: its mutation turns this test red", "RED   test_axes" in r.stdout and f"FAILED {b['id']}:" in r.stdout, r.stdout[-300:])
print("".join(f"FAILED {x}\n" for x in bad) + "test_axes: " + ("FAILED" if bad else "all passed"))
sys.exit(1 if bad else 0)
