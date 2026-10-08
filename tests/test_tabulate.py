"""test_tabulate - SIGNATURE-TABLE.md and docs/verdict-table.html from the stored results: rows, collisions, the
truth firewall, a seventh signature column, the page's cell counts and the D13 diff (appendix 9.3)."""
import copy
import hashlib
import json
import math
import re
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
import frozen  # noqa: E402

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
sets = sorted({r["tables"] for r in results})          # plan 0871 G5: every count below is derived from the result sets on disk, never a hand-listed set name
have = {t: sum(len(r["signature"]) for r in results if r["tables"] == t) for t in sets}
section = {t: [ln for ln in md.split(f"## Rules: {t}")[1].split("\n## ")[0].splitlines() if ln.startswith("| ") and not ln.startswith(("| run", "|---"))] for t in sets}
check("one row per (run, point), in each table set's own section", len(rows) == sum(have.values()) == sum(len(v) for v in section.values())
      and {t: len(v) for t, v in section.items()} == have and not found, str(found) + str(have))
clash = [ln for ln in md.split("## Collisions")[1].splitlines() if ln.startswith("- ")]
check("x8 1.00 and 1.10 are not a collision", not [c for c in clash if "x8-ising-needle:1.00" in c and "x8-ising-needle:1.10" in c])
check("the C2 pair is no longer a collision (plan 0868 step 1: its points re-joined to their own truth) and the x8 / x7a-bc one is",
      not [c for c in clash if "c2-bc-two-start" in c] and any("NOT (x8-ising-needle:1.01)" in c and "POINT (x7a-bc:0.0" in c for c in clash), str(clash[:2]))
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
null_n = len(declare.Ctx(ROOT).alpha["nulls"])
cells_of_set = lambda t: math.prod(len(tomllib.loads((ROOT / "tables" / t / "codes.toml").read_text())["columns"]["signature"][c]["alphabet"]) + null_n   # noqa: E731
                                   for c in tomllib.loads((ROOT / "tables" / t / "verdict.toml").read_text())["columns"])
check("the page's cell counts sum to the product of each table set's declared column alphabets (nulls included), over the sets on disk, and some rows were never hit",
      sum(cells) == sum(cells_of_set(t) for t in sets) and 'class=never' in page, f"{sum(cells)} vs {sum(cells_of_set(t) for t in sets)}")
with tempfile.TemporaryDirectory() as t:
    shutil.copytree(ROOT / "tables" / "verdict-x-rules", Path(t) / "d13")
    frozen.thaw(Path(t) / "d13")   # the copy only; the live set is frozen
    f = Path(t) / "d13" / "verdict.toml"
    text = f.read_text()
    flip = text.replace('when.two_start = ["INDEP"]', 'when.two_start = ["INDEP", "UNRES"]').replace('["FLUCT", "UNRES"]', '["FLUCT"]')
    check("the D13 flip edits 15 rows", text.count('when.two_start = ["INDEP"]') == 14 and flip != text)
    f.write_text(flip)
    lines, total, moved = score.diff(detect.load_tables("verdict-x-rules"), detect.load_tables("d13", t), results, [])
    flipped = [("x2-xy-line-3", "0.5", "REFUSE-UNRES", "REFUSE-SLOW"), ("x2-xy-line-3", "0.6", "WALKING", "REFUSE-SLOW"), ("x2-xy-line-3", "0.7", "REFUSE-UNRES", "REFUSE-SLOW")] \
        + [("x2b-xy", pt, v, "REFUSE-SLOW") for pt, v in (("0.5", "LINE"), ("0.6", "WALKING"), ("0.7", "LINE"), ("0.8", "LINE"), ("0.85", "LINE"))] \
        + [(i, pt, "REFUSE-SLOW", "NOT") for i in ("x5-bilayer-2", "x5-bilayer") for pt in ("0.0", "0.3")] \
        + [(i, pt, "REFUSE-PROBE-INCOMPLETE", "POINT") for i in ("x5n-bilayer-2", "x5n-bilayer-3", "x5n-bilayer") for pt in ("0.0", "0.1", "0.3")] \
        + [(i, pt, "FIRST-ORDER", "NOT") for i in ("x9c-potts-2", "x9c-potts") for pt in ("8", "10")] \
        + [("x2-xy-line-3", "0.6", "REFUSE-UNRES", "REFUSE-SLOW"), ("x2b-xy", "0.6", "LINE", "REFUSE-SLOW")] \
        + [("x2b-xy-2", pt, v, "REFUSE-SLOW") for pt, v in (("0.5", "LINE"), ("0.6", "REFUSE-UNRES"), ("0.7", "REFUSE-WEAK"), ("0.8", "REFUSE-UNRES"), ("0.85", "REFUSE-UNRES"))] \
        + [("x2b-xy-2", "0.89294", "REFUSE-UNRES", "POINT")] \
        + [("x2b-xy-3", pt, "LINE", "REFUSE-SLOW") for pt in ("0.5", "0.6", "0.7", "0.8", "0.85")] + [("x2b-xy-3", "0.89294", "REFUSE-UNRES", "POINT")] \
        + [("x2b-xy-4", pt, "LINE", "REFUSE-SLOW") for pt in ("0.5", "0.6", "0.7", "0.8", "0.85")] \
        + [("x2b-xy-2", pt, "LINE", "REFUSE-SLOW") for pt in ("0.6", "0.7", "0.8", "0.85")]   # plan 0878 P3: the five x2b-xy-4 points under v08-rules (class b); plan 0877 P2: the six x2b-xy-3 points under v08-rules (class b); plan 0872 P4 (v06 results; Auditor listing edit, class b); plan 0874 P2: the four x2b-xy-2 points that move to LINE under v07-rules (class b)
    # plan 0871 G5: the DISTINCT (input, point, stored verdict, flipped verdict) the D13 flip moves is the finding (declared above); how many times each moves is
    # derived from the results on disk - one per stored result of that input whose point holds that stored verdict - so a new table set needs no hand edit
    verdict_at = {(r["input"], s["point"], r["run_id"]): s["verdict"] for r in results for s in r["signature"]}
    x5 = sorted(k for k in flipped for r in results if verdict_at.get((r["input"], k[1], r["run_id"])) == k[2] and r["input"] == k[0])
    moved = sorted(moved)
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
# plan 0894 P3 (E388): a declared null (a family that reads NOT-EVALUATED) is printed and is not a failure; a REAL error still exits non-zero.
with tempfile.TemporaryDirectory() as t:
    mini = Path(t) / "mini"
    shutil.copytree(ROOT, mini, ignore=shutil.ignore_patterns(".git", "__pycache__", "results", "rust"))
    (mini / "results").mkdir()
    frozen.thaw(mini)

    def tab(*names):
        for q in (mini / "results").iterdir():
            q.unlink()
        for n in names:
            for ext in ("json", "npz"):
                if (ROOT / "results" / f"{n}.{ext}").is_file():
                    shutil.copy(ROOT / "results" / f"{n}.{ext}", mini / "results" / f"{n}.{ext}")
        frozen.thaw(mini / "results")
        return subprocess.run([sys.executable, str(mini / "bin" / "cc"), "tabulate"], capture_output=True, text=True, cwd=mini)
    nul = tab("k4-m1@v01-rules")
    check("a family that reads NOT-EVALUATED is printed and tabulate exits 0", "reads NOT-EVALUATED" in nul.stdout and nul.returncode == 0, str(nul.returncode) + nul.stdout[-300:] + nul.stderr[-300:])
    good = tab("b7-at-line@v01-rules")
    check("a clean result set exits 0", good.returncode == 0, good.stdout[-300:] + good.stderr[-300:])
    tab("b7-at-line@v01-rules")
    q = mini / "results" / "b7-at-line@v01-rules.json"
    d = json.loads(q.read_text())
    d["read"][next(k for k in d["read"] if k.startswith("instruments/"))] = "0" * 64   # a result that no longer matches what it read
    q.write_text(json.dumps(d))
    err = subprocess.run([sys.executable, str(mini / "bin" / "cc"), "tabulate"], capture_output=True, text=True, cwd=mini)
    check("a broken (stale) result still exits non-zero, and is printed", err.returncode != 0 and err.stdout.strip() != "tabulate: 1 results", err.stdout[-300:])
    tab("k4-m1@v01-rules", "b7-at-line@v01-rules")
    q = mini / "results" / "b7-at-line@v01-rules.json"
    d = json.loads(q.read_text())
    d["read"][next(k for k in d["read"] if k.startswith("instruments/"))] = "0" * 64
    q.write_text(json.dumps(d))
    both = subprocess.run([sys.executable, str(mini / "bin" / "cc"), "tabulate"], capture_output=True, text=True, cwd=mini)
    check("a null beside a real error: still non-zero", "reads NOT-EVALUATED" in both.stdout and both.returncode != 0, both.stdout[-300:])
print("test_tabulate: " + ("FAILED" if bad else "all passed"))
sys.exit(1 if bad else 0)
