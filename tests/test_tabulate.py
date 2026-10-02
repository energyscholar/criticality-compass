"""test_tabulate - SIGNATURE-TABLE.md and docs/verdict-table.html from the stored results: rows, collisions, the
truth firewall, a seventh signature column, the page's cell counts and the D13 diff (appendix 9.3)."""
import copy
import json
import re
import shutil
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
check("one row per (run, point)", len(rows) == sum(len(r["signature"]) for r in results) == 60 and not found, str(found))
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
check("the page's cell counts sum to 45 360 and some rows were never hit", sum(cells) == 45360 and 'class=never' in page, str(sum(cells)))
with tempfile.TemporaryDirectory() as t:
    shutil.copytree(ROOT / "tables" / "verdict-x-rules", Path(t) / "d13")
    f = Path(t) / "d13" / "verdict.toml"
    text = f.read_text()
    flip = text.replace('when.two_start = ["INDEP"]', 'when.two_start = ["INDEP", "UNRES"]').replace('["FLUCT", "UNRES"]', '["FLUCT"]')
    check("the D13 flip edits 15 rows", text.count('when.two_start = ["INDEP"]') == 14 and flip != text)
    f.write_text(flip)
    lines, total, moved = score.diff(detect.load_tables("verdict-x-rules"), detect.load_tables("d13", t), results, [])
    check("--diff of the D13 flip: 1 512 cells, no fixture point", total == 1512 and moved == [], "\n".join(lines[:6]))
print("test_tabulate: " + ("FAILED" if bad else "all passed"))
sys.exit(1 if bad else 0)
