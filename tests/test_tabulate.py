"""test_tabulate - SIGNATURE-TABLE.md and docs/verdict-table.html from the stored results: rows, collisions, the
truth firewall, a seventh signature column, the page's cell counts and the D13 diff (appendix 9.3)."""
import copy
import hashlib
import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path[:0] = [str(ROOT / "cc"), str(ROOT / "cc" / "instruments")]
import detect  # noqa: E402
import score  # noqa: E402

bad = []


def check(name, ok, why=""):
    print(("ok   " if ok else "FAIL ") + name + ("" if ok else f": {why}"))
    if not ok:
        bad.append(name)


def keys(x):
    return {k for k, v in x.items()} | {q for v in x.values() if isinstance(v, dict) for q in keys(v)} | {
        q for v in x.values() if isinstance(v, list) for e in v if isinstance(e, dict) for q in keys(e)}


files = sorted((ROOT / "results").glob("*.json"))
results = [json.loads(f.read_text()) for f in files]
md, found = score.tabulate(results)
rows = [ln for ln in md.splitlines() if ln.startswith("| ") and not ln.startswith(("| run", "|---"))]
want = {"verdict-x-rules": 66, "v01-rules": 79, "v02-rules": 117}   # points per set (v02-rules: the same 76, plan 0866 P-A, + the 27 points of the six fluct inputs, P-B, + the 8 points of w1-potts and w3-potts, 0866 X9, + the 3 of x4-ising-field-3; every set + the 3 of x5n-bilayer, plan 0865 S3): the seven v0 inputs (60), + x5-bilayer (3); v01-rules also the three along inputs (13)
have = {t: sum(len(r["signature"]) for r in results if r["tables"] == t) for t in want}
check("one row per (run, point)", len(rows) == sum(len(r["signature"]) for r in results) == sum(want.values()) and have == want
      and not found, str(found) + str(have))
clash = [ln for ln in md.split("## Collisions")[1].splitlines() if ln.startswith("- ")]
check("x8 1.00 and 1.10 are not a collision", not [c for c in clash if "x8-ising-needle:1.00" in c and "x8-ising-needle:1.10" in c])
check("the collision list holds the C2 pair", any("FIRST-ORDER (" in c and "c2-bc-two-start:d2.0-K1.0" in c and "POINT (" in c
                                                  and "c2-bc-two-start:d1.9-K1.0" in c for c in clash), str(clash[:2]))
check("truth is in SIGNATURE-TABLE.md", "| LINE |" in md and "| FIRST-ORDER |" in md)
live = detect.run("x8-ising-needle", "verdict-x-rules", write=False)
forbidden = {"case", "class_truth", "truth"}
check("no result holds a case or a truth", not any(keys(r) & forbidden for r in results + [live]), str([keys(r) & forbidden for r in results]))
md2, found2 = score.tabulate(results, joins={"w2-potts": {"2": "ising-2d", "3": "potts-q3", "4": "potts-4", "5": "potts-q5"}})
check("an unknown case reads UNJOINED with a finding, not an exception",
      "| `potts-4` | UNJOINED |" in md2 and any("unknown case 'potts-4'" in f and "Next:" in f for f in found2), str(found2))
seven = copy.deepcopy(next(r for r in results if r["input"] == "b7-at-line"))
seven.update(tables="planted7", run_id="b7-at-line@planted7", signature_columns=seven["signature_columns"] + ["extra"])
for s in seven["signature"]:
    s["extra"] = "X"
md7, _ = score.tabulate(results + [seven])
head = next(ln for ln in md7.split("## Rules: planted7")[1].splitlines() if ln.startswith("| run"))
check("a seventh column tabulates in its own section", len(head.strip("|").split("|")) == 5 + 7 + 2 and "extra" in head, head)
page = score.page(results)
cells = [int(n) for n in re.findall(r'data-cells="(\d+)"', page)]
check("the page's cell counts sum to 45 360 per table set and some rows were never hit", sum(cells) == 45360 * len({r["tables"] for r in results}) and 'class=never' in page, str(sum(cells)))
with tempfile.TemporaryDirectory() as t:
    shutil.copytree(ROOT / "tables" / "verdict-x-rules", Path(t) / "d13")
    for q in [Path(t) / "d13", *(Path(t) / "d13").rglob("*")]:   # the copy only; the live set is frozen
        q.chmod(q.stat().st_mode | 0o200)
    f = Path(t) / "d13" / "verdict.toml"
    text = f.read_text()
    flip = text.replace('when.two_start = ["INDEP"]', 'when.two_start = ["INDEP", "UNRES"]').replace('["FLUCT", "UNRES"]', '["FLUCT"]')
    check("the D13 flip edits 15 rows", text.count('when.two_start = ["INDEP"]') == 14 and flip != text)
    f.write_text(flip)
    lines, total, moved = score.diff(detect.load_tables("verdict-x-rules"), detect.load_tables("d13", t), results, [])
    x5 = [("x5-bilayer-2", pt, "REFUSE-SLOW", "NOT") for pt in ("0.0", "0.3")] + [("x5-bilayer", pt, "REFUSE-SLOW", "NOT") for pt in ("0.0", "0.3")] * 2   # x5-bilayer-2@v02-rules, x5@v01-rules and x5@v02-rules reverdicted under a fork of verdict-x-rules
    check("--diff of the D13 flip: 1 512 cells, no fixture point but x5's two v01-rules refusals", total == 1512 and moved == x5,
          "\n".join(lines[:6]) + str(moved))
with tempfile.TemporaryDirectory() as t:       # O2/R14: --diff prints and writes nothing (a copy of the repo, never the live tree)
    repo = Path(t) / "repo"
    shutil.copytree(ROOT, repo, ignore=shutil.ignore_patterns(".git", "__pycache__"))
    pages = [repo / "SIGNATURE-TABLE.md", repo / "docs" / "verdict-table.html"]
    digest = lambda: [hashlib.sha256(q.read_bytes()).hexdigest() if q.is_file() else "absent" for q in pages]  # noqa: E731
    before = digest()
    r = subprocess.run([sys.executable, str(repo / "bin" / "cc"), "tabulate", "--diff", "verdict-x-rules", "v01-rules"],
                       capture_output=True, text=True, cwd=repo)
    check("tabulate --diff writes neither SIGNATURE-TABLE.md nor docs/verdict-table.html",
          r.returncode == 0 and digest() == before and "wrote nothing" in r.stdout, r.stdout + r.stderr)
print("test_tabulate: " + ("FAILED" if bad else "all passed"))
sys.exit(1 if bad else 0)
