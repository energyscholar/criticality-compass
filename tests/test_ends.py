"""test_ends - plan 0871: the direction-agnostic family bracket (P1), the LINE-END sides (P2) and end-point scoring (P3), proved on PLANTED
families (tests/planted/ends.toml: stored-result signatures built by hand, no instrument runs) through family.py's OWN functions and the
v05-rules family.toml. Every RED here is a plant that must be refused or must read the named value."""
import itertools
import shutil
import sys
import tempfile
import tomllib
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path[:0] = [str(ROOT / "cc"), str(ROOT / "cc" / "instruments")]
import declare  # noqa: E402
import family  # noqa: E402

bad = []
NULLS = ["NOT-MEASURED", "NOT-EVALUATED"]
SET = ROOT / "tables" / "v05-rules"
FAM = tomllib.loads((SET / "family.toml").read_text())


def check(name, ok, why=""):
    print(("ok   " if ok else "FAIL ") + name + ("" if ok else f": {why}"))
    if not ok:
        bad.append(name)


def bracket(codes):
    res = {"signature": [{"point": str(i), "needle": c} for i, c in enumerate(codes)]}
    got = family.bracket_of(FAM, res, NULLS)
    return got[0]


# ---------------------------------------------------------------- P1: the bracket reads a chain's direction, it does not assume one
for codes, want in ((["DIS", "MID", "ORD"], "BRACKET-UP"), (["ORD", "MID", "DIS"], "BRACKET-DOWN"),
                    (["MID", "MID", "MID", "DIS"], "BRACKET-DOWN"),          # a T-ordered XY chain: the shape X2 and X3 read NON-MONOTONE under v01-v04
                    (["ORD", "MID", "MID", "MID", "DIS"], "BRACKET-DOWN"),   # a T-ordered clock chain
                    (["DIS", "MID", "DIS"], "NON-MONOTONE"),                 # RED: an ascent AND a descent is still refused
                    (["ORD", "MID", "ORD"], "NON-MONOTONE"),
                    (["MID", "MID", "MID"], "BRACKET-FLAT"),                 # no step at all, a MID present: no direction is claimed
                    (["DIS", "DIS"], "NO-MID"), (["ORD", "DIS"], "NO-MID"), (["DIS", "ORD"], "NO-MID"),
                    (["DIS", "NOT-MEASURED", "ORD"], "NOT-MEASURED"), (["MID", "NOT-EVALUATED"], "NOT-EVALUATED"),
                    (["NOT-EVALUATED", "MID", "NOT-MEASURED"], "NOT-MEASURED")):
    check(f"v05 bracket of {codes} is {want}", bracket(codes) == want, bracket(codes))

# the whole (descent, ascent, mid) table is read against the maths of a chain, not against itself: every cell of the 4 x 4 x 4 product
b = FAM["bracket"]
for d, a, m in itertools.product(*[r for _, _, r in declare.bracket_axes(b)], b["mid_rank"]):
    got = b["table"][f"{d},{a},{m}"]
    nul = next((n for n in NULLS if n in (d, a, m)), None)
    want = (nul or "NON-MONOTONE" if nul or (d, a) == ("DESCENT", "ASCENT") else "NO-MID" if m == "NO-MID" else "BRACKET-DOWN" if d == "DESCENT"
            else "BRACKET-UP" if a == "ASCENT" else "BRACKET-FLAT")
    check(f"table cell ({d}, {a}, {m}) is {want}", got == want, got)

check("the v05-rules family partition validates total", declare.check_file(SET / "family.toml", ROOT) == [])
with tempfile.TemporaryDirectory() as tmp:
    shutil.copytree(SET, Path(tmp) / "set")
    text = (SET / "family.toml").read_text()
    cut = "\n".join(ln for ln in text.splitlines() if not ln.startswith('"DESCENT,ASCENT,MID"'))
    (Path(tmp) / "set" / "family.toml").write_text(cut)      # RED: one cell of the bracket table removed
    found = declare.check_file(Path(tmp) / "set" / "family.toml", ROOT)
    check("a bracket table with a missing cell is refused by validate", any("table keys (total)" in f.msg for f in found), str(found))


# ---------------------------------------------------------------- P2: the LINE-END sides, on planted families
PLANT = tomllib.loads((ROOT / "tests" / "planted" / "ends.toml").read_text())
FTEXT = (SET / "family.toml").read_text()
V04 = tomllib.loads((ROOT / "tables" / "v04-rules" / "family.toml").read_text())
M0 = {"instruments": [], "eps": {}}      # no across and no along: f1 and f2 read NOT-MEASURED, so the interior reads LINE only through its points


def planted(plant, fam=FAM, text=FTEXT):
    """family.compute on one planted stored result (signature rows only; compute reads nothing else when no instrument is declared)."""
    sig = []
    for pt in plant["points"]:
        name, kind = pt.split(":")
        sig.append({"point": name, **PLANT["kind"][kind]})
    return family.compute({"interior": plant["interior"]}, {"signature": sig}, None, fam, text, M0, NULLS)


for pl in PLANT["plant"]:
    got = planted(pl)
    want = {k: pl[k] for k in ("bracket", "lower", "upper", "verdict", "class")} | {"points": pl["points_code"]}
    check(f"planted: {pl['name']}", all(got[k] == v for k, v in want.items()), f"{ {k: got[k] for k in want} } vs {want}")
    if "v04_verdict" in pl:
        old = family.compute({"interior": pl["interior"]}, {"signature": [{"point": q.split(":")[0], **PLANT["kind"][q.split(":")[1]]} for q in pl["points"]]},
                             None, V04, (ROOT / "tables" / "v04-rules" / "family.toml").read_text(), M0, NULLS)
        check(f"planted: the verdict v04-rules gave is unchanged ({pl['v04_verdict']})", old["verdict"] == pl["v04_verdict"] == got["verdict"], old["verdict"])

# the end kind reads two_start: the ORDER axis alone cannot tell "the starts agree" from "one start was never run" at a sink
dis_i, dis_s = PLANT["kind"]["DISi"], PLANT["kind"]["DISs"]
check("a sink with the starts agreeing and a sink with one start share the order axis value but not the end", dis_i["order"] == dis_s["order"] == "OFF-WINDOW"
      and planted(PLANT["plant"][0])["upper"] != planted(PLANT["plant"][1])["upper"])

# the whole side table against the spec's sentences, over its full domain (an independent statement of the rule, not a read-back of the file)
sd, al = FAM["side"], FAM["alphabets"]
needles, flows = ["DIS", "MID", "ORD"], ["STOPPED", "SLOW", "FLOWING", "UNRES"]
rows = FAM["side_row"]
bad_cells = []
for bn, bf, yn, yo in itertools.product([*needles, *NULLS], [*flows, *NULLS], sd["needle_rank"], sd["order_rank"]):
    got = next(r["verdict"] for r in rows if all(v in r["when"].get(c, [v]) for c, v in zip(declare.SIDE_KEYS, (bn, bf, yn, yo))))
    null = next((n for n in NULLS if n in (bn, yn)), None)
    kind = {"INDEP": "END-BKT-CANDIDATE", "COEXIST": "END-MULTICRITICAL", "UNMEASURED": "END-ORDER-UNMEASURED"}.get(yo, "UNRES")
    want = ("OPEN" if yn == "NONE" else null or ("UNRES" if bn != "MID" else "NO-END" if yn == "MID" else bf if bf in NULLS
                                                  else "UNRES" if bf == "FLOWING" else kind))
    bad_cells += [((bn, bf, yn, yo), got, want)] * (got != want)
check(f"the side table equals the spec's sentences on all {5 * 6 * 5 * 5} cells", not bad_cells, str(bad_cells[:3]))

# the family partition: outside the cells the spec names, every cell reads what v04-rules read (bracket BRACKET-* standing for BRACKET)
cols = FAM["columns"]
dom = {c: FAM["alphabets"][c] for c in cols}
new = declare.table_values(FAM, dom, cols)
v4 = {c: V04["alphabets"][c] for c in cols[:3]}
old = declare.table_values(V04, v4, cols[:3])                         # v04-rules' verdict over ITS alphabets (one BRACKET code)
old = old[np.array([v4["bracket"].index("BRACKET" if x.startswith("BRACKET-") else x) for x in dom["bracket"]])]   # ... read at v05's three BRACKET-* codes
old = old[:, np.array([v4["f1"].index(x) for x in dom["f1"]])][:, :, np.array([v4["f2"].index(x) for x in dom["f2"]])]
grid = np.meshgrid(*[np.arange(len(dom[c])) for c in cols], indexing="ij")
at = {c: np.array(dom[c])[g] for c, g in zip(cols, grid)}
br3 = np.isin(at["bracket"], ["BRACKET-UP", "BRACKET-DOWN", "BRACKET-FLAT"])
interior_line = (at["points"] == "LINE") | ((at["f1"] == "VARIES") & (at["f2"] == "MARGINAL"))
ep = (at["lower"] == "END-BKT-CANDIDATE") | (at["upper"] == "END-BKT-CANDIDATE")
em = (at["lower"] == "END-MULTICRITICAL") | (at["upper"] == "END-MULTICRITICAL")
special = br3 & interior_line & ep
prior = np.broadcast_to(old[tuple(slice(None) if i < 3 else None for i in range(6))], new.shape)
carved = br3 & (at["points"] == "LINE") & em & ~ep
check("BKT-END exactly when the bracket is directional, the interior reads LINE and a side is END-BKT-CANDIDATE",
      bool((new[special] == "BKT-END").all() and not (new[~special] == "BKT-END").any()), f"{(new[special] != 'BKT-END').sum()} missing")
check("interior LINE with only a multicritical end reads LINE (the end is reported, not read as BKT-END)", bool((new[carved] == "LINE").all()))
check(f"every other of the {int((~special & ~carved).sum())} cells reads what v04-rules read (no existing family verdict can move)",
      bool((new[~special & ~carved] == prior[~special & ~carved]).all()), f"{int((new[~special & ~carved] != prior[~special & ~carved]).sum())} cells differ")

# validate refuses a side table or a side code that is not total
with tempfile.TemporaryDirectory() as tmp:
    shutil.copytree(SET, Path(tmp) / "set")
    f = Path(tmp) / "set" / "family.toml"
    blocks = FTEXT.split("[[side_row]]")
    f.write_text("[[side_row]]".join(blocks[:-1]))
    found = declare.check_file(f, ROOT)
    check("a side partition with its last row removed is refused as not total", any("uncovered cells" in x.msg for x in found), str(found))
    f.write_text(FTEXT.replace('"OFF-WINDOW,INDEP" = "INDEP"\n', ""))
    found = declare.check_file(f, ROOT)
    check("a side.order_code with a missing (order, two_start) key is refused", any("side.order_code" in x.loc for x in found), str(found))
    f.write_text(FTEXT.replace("[[side_row]]", "[[side_row]]\nwhen = { beyond_needles = [\"NONE\"] }\nverdict = \"OPEN\"\nwhy = \"x\"\n\n[[side_row]]", 1))
    found = declare.check_file(f, ROOT)
    check("two side rows that overlap are refused", any("overlap" in x.msg for x in found), str(found))
    f.write_text(FTEXT.replace('lower = ["END-BKT-CANDIDATE"', 'lower = ["END-BKT-CANDIDATEX"', 1))
    check("a lower alphabet that differs from upper is refused", any("alphabets.upper" in x.loc for x in declare.check_file(f, ROOT)))

print("".join(f"FAILED {x}\n" for x in bad) + "test_ends: " + ("FAILED" if bad else "all passed"))
sys.exit(1 if bad else 0)
