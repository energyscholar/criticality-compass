"""test_verdict_equivalence - verdict-x-rules equals verdict_x on its 3 840 non-null cells; every other
difference is a declared one (appendix 9.2). Loads the set BY NAME, never the default."""
import itertools
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path[:0] = [str(ROOT / "cc"), str(ROOT / "cc" / "instruments"), str(ROOT / "tests" / "reference")]
import declare  # noqa: E402
import detect  # noqa: E402
import verdict_x as vx  # noqa: E402

NE, NM, SIDES = "NOT-EVALUATED", "NOT-MEASURED", ("DIS", "MID", "ORD")
NULLS = (NM, NE)
T = detect.load_tables("verdict-x-rules")
cols = T.verdict["columns"]
dom = declare.doms(T.codes, T.codes["null_rank"])
counts, bad, cc = {"equal": 0, "declared": 0, "null": 0, "shared": 0}, [], {}
eff = lambda v: "UNRES" if v == NE else v  # noqa: E731  X2 reads a NOT-EVALUATED growth or stability as UNRES
for vals in itertools.product(*(dom[c] for c in cols)):
    cell = dict(zip(cols, vals))
    cc[vals] = detect.verdict_of(cell, T)[0]
    side, flow, grow, stab, start = (cell[k] for k in ("needle", "flow", "across", "stability", "two_start"))
    hard = side in NULLS or flow in NULLS or start in NULLS or grow == NM or stab == NM
    if hard:   # no vx counterpart: a null may refuse or fall off the window, but never reach a positive class
        counts["null"] += 1
        bad += [f"{cell}: {cc[vals]} is a positive class with a null"] * (cc[vals] in ("POINT", "LINE", "WALKING"))
    elif cell["sink"] not in NULLS:
        theirs = vx.verdict(side, start, flow, eff(grow), eff(stab))
        gap = (side, start, flow) == ("MID", "INDEP", "STOPPED") and (grow == NE or (grow in ("RELEVANT", "MARGINAL") and stab == NE))
        want = ("REFUSE-ACROSS-UNMEASURED" if grow == NE else "REFUSE-STABILITY-UNMEASURED") if gap else theirs
        counts["declared" if gap else "equal"] += 1
        counts["shared"] += NE not in (grow, stab)   # verdict_x's own domain: no NOT-EVALUATED, no null anywhere
        if cc[vals] != want or (gap and theirs != "REFUSE-UNRES"):
            bad.append(f"{cell}: cc {cc[vals]} verdict_x {theirs} wanted {want}")
for vals, v in cc.items():   # sink is ignored by declaration: a null or any other sink never changes a verdict
    swap = tuple("NEITHER" if c == "sink" else x for c, x in zip(cols, vals))
    bad += [f"sink changes {vals}"] * (v != cc[swap])
bad += [f"expected 3 840 shared cells, compared {counts['shared']}"] * (counts["shared"] != 3840)
print(f"cells {len(cc)}: equal {counts['equal']} (of which shared {counts['shared']}), declared differences {counts['declared']}, null cells {counts['null']}")
print("\n".join(bad[:20]) + f"\ntest_verdict_equivalence: {'FAILED ' + str(len(bad)) if bad else 'all passed'}")
sys.exit(1 if bad else 0)
