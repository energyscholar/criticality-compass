#!/usr/bin/env python3
"""gen-verdicts.py - VERDICTS.md from tables/<set>/*.toml (read only). Usage: gen-verdicts.py [CC_ROOT] [SET] [WIDTH]
Every verdict word a table set can emit, with the rows (file:line) that emit it and the first row's `why` (cut to WIDTH).
Line numbers are those of the [[row]] / [[side_row]] headers, the same numbers `bin/cc explain` prints."""
import sys, tomllib
from pathlib import Path
root = Path(sys.argv[1] if len(sys.argv) > 1 else Path(__file__).resolve().parent.parent)
sys.path.insert(0, str(root / "cc"))   # plan 1427 D29: schema.row_lines is the one [[key]] line finder
import schema  # noqa: E402
name = sys.argv[2] if len(sys.argv) > 2 else "v07-rules"
width = int(sys.argv[3]) if len(sys.argv) > 3 else 150
mode = sys.argv[4] if len(sys.argv) > 4 else "full"      # full: every section prints when + why; compact: only the per-point partition prints `when`
tdir = root / "tables" / name


def rows(path, key="row"):
    text = path.read_text()
    lines = schema.row_lines(text, key)
    return list(zip(lines, tomllib.loads(text).get(key, [])))


def when(row):
    return "; ".join(f"{c}={'|'.join(v)}" for c, v in row["when"].items())


def section(title, path, key, verdict_order=None, show_when=True, w=None, why_on=True):
    w = w or width
    rs = rows(path, key)
    by = {}
    for ln, r in rs:
        by.setdefault(r["verdict"], []).append((ln, r))
    order = [v for v in (verdict_order or []) if v in by] + [v for v in by if v not in (verdict_order or [])]
    out = [f"\n### {title} ({path.name}: {len(rs)} rows, {len(by)} verdicts)\n"]
    for v in order:
        ln, r = by[v][0]
        why = " ".join(r["why"].split())
        rest = [str(l) for l, _ in by[v][1:]]
        more = f" (+{len(rest)} rows: {', '.join(rest[:4])}{', ..' if len(rest) > 4 else ''})" if rest else ""
        cut = f"{why[:w]}{'...' if len(why) > w else ''}"
        out.append(f"- **{v}** - line {ln}{more}\n  when: `{when(r)}`\n  why: {cut}" if show_when
                   else f"- **{v}** - line {ln}{more}: {cut}" if why_on else f"{v} {ln}{more}")
    return out


def kv(d):
    return " ".join(f"{k}={x}" for k, x in d.items())


C = mode != "compact"   # compact: no when-lines (open the named line of the file for the full row); full: when + why everywhere


v = tomllib.loads((tdir / "verdict.toml").read_text())
out = [f"# VERDICTS - every word `{name}` can emit, with the row that emits it",
       f"\nGenerated from `tables/{name}/` by `gen-verdicts.py {root} {name} {width} {mode}`; regenerate, never edit. "
       f"Every REFUSE-* word scores as class REFUSE (the set's `refuse` list); `(+N rows: ..)` = further rows that emit the same word.",
       f"\nSignature columns a per-point row may read: {', '.join(v['columns'])}; `ignores` = {', '.join(v['ignores'])}."]
cc = tomllib.loads((root / "cc.toml").read_text())   # plan 0881 P2.3: the label of an instrument whose output is a conventional estimate is one string, in cc.toml [conventional]
codes = tomllib.loads((tdir / "codes.toml").read_text())["columns"]
for inst, label in cc.get("conventional", {}).items():
    fed = sorted(n for grp in codes.values() for n, c in grp.items() if isinstance(c.get("from"), str) and c["from"].startswith(inst + "."))
    read = sorted(set(fed) & (set(v["columns"]) | set(v["ignores"])))
    out.append(f"\nThe `{inst}` instrument is an {label} (cc.toml [conventional]). Columns of this set derived from it: {', '.join(fed) or 'none'}; "
               f"read by a verdict row: {', '.join(read) if read else 'no'}.")
out += section("Per-point verdict (the partition `bin/cc explain` step 8 names)", tdir / "verdict.toml", "row", v["verdicts"], C)
if (tdir / "geometry.toml").is_file():
    g = tomllib.loads((tdir / "geometry.toml").read_text())
    w2 = width if C else 60
    out += section("Geometry axis (step 9): the same words and `why` texts without two_start/probe; `word line`",
                   tdir / "geometry.toml", "row", g["verdicts"], C, w2, C)
    out += section("Probe projection (step 10; @geometry = the geometry stands)", tdir / "probe.toml", "row", None, C, w2)
    o = tomllib.loads((tdir / "order.toml").read_text())
    out += section("Order axis (step 11; values, not verdicts)", tdir / "order.toml", "row", o["values"], C, w2)
    out.append("  score (order value -> class): " + kv(o["score"]))
    out += section("Compose (step 12; (geometry, order) -> verdict)", tdir / "compose.toml", "row", None, C, w2)
if (tdir / "family.toml").is_file():
    f = tomllib.loads((tdir / "family.toml").read_text())
    out += section("Family report (a declared projection C over bracket, f1, f2, points, lower, upper)", tdir / "family.toml", "row", f["verdicts"], C, w2)
    out.append("  class_of: " + kv(f["class_of"]))
    out += section("Side (lower/upper) end kinds; an END-* side names end_point and end_bracket", tdir / "family.toml", "side_row", None, C, w2)
if (tdir / "membership.toml").is_file():
    m = tomllib.loads((tdir / "membership.toml").read_text())
    out.append("\n### Door values of a pair (membership.toml): a refused pair reads this VALUE, never an exception\n")
    for inst, r in m.items():
        if isinstance(r, dict):
            out.append(f"- **[{inst}]** reads `{r['reads']}`: {kv(r['map'])}; the lower-ranked endpoint decides; door {kv(r['door'])}")
print("\n".join(out))
