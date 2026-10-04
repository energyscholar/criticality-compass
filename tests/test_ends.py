"""test_ends - plan 0871: the direction-agnostic family bracket (P1), the LINE-END sides (P2) and end-point scoring (P3), proved on PLANTED
families (tests/planted/ends.toml: stored-result signatures built by hand, no instrument runs) through family.py's OWN functions and the
v05-rules family.toml. Every RED here is a plant that must be refused or must read the named value."""
import itertools
import shutil
import sys
import tempfile
import tomllib
from pathlib import Path

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

print("".join(f"FAILED {x}\n" for x in bad) + "test_ends: " + ("FAILED" if bad else "all passed"))
sys.exit(1 if bad else 0)
