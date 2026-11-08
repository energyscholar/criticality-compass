"""test_along - the along instrument (unit "pair", membership door) against the frozen [B7] p-lines and X7a.
b7-at-line-2 reproduces B7's ALONG p block; x7a-bc reproduces X7a's membership screen (every pair off the manifold);
x7a-nnn's pair is a SET (its stream is not X7a's); the all-pairs relation and the missing-rule refusal are checked."""
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
from lib import bad, bootstrap, check  # noqa: E402
bootstrap(ROOT, "cc", "cc/instruments")
import admit  # noqa: E402
import declare  # noqa: E402
import detect  # noqa: E402
import door  # noqa: E402
import view  # noqa: E402
from kernel import A  # noqa: E402

Y = [-0.007, -0.019, -0.111, 0.131]                                   # results/B7.txt, p lines
EDGES = [(-0.080, 0.069), (-0.106, 0.056), (-0.248, 0.005), (0.037, 0.216)]
DELTA = [[0.0353, 0.036, 0.0348], [0.0443, 0.0379, 0.0425], [0.054, 0.0543, 0.0423], [0.0682, 0.0728, 0.0909]]
BC_PAIRS = [["0.0", "1.0"], ["1.0", "1.5"], ["1.5", "1.8"], ["1.8", "1.9"], ["1.9", "1.95"]]   # results/X7a.txt
BC_OFF = [["0.0", "1.0"], ["1.0", "1.5"], ["1.5"], ["1.9"], ["1.9"]]
V = [0.0724, -0.0741, -0.0773, -0.0070, 0.0326, -0.0276]
NNN_ALLOWED = {"NOT-EVALUATED", "UNRES"}   # declared before the run: the nnn stream is not X7a's, only the set is asserted


def pairs(res):
    return {tuple(r["unit"]["pair"]): r for r in res["pair_readings"]}


b7, bc, nnn = (detect.run(i, "v01-rules", write=False) for i in ("b7-at-line-2", "x7a-bc", "x7a-nnn"))
rows = [r for r in b7["pair_readings"]]
check("b7-2: four consecutive pairs of the declared chain", [r["unit"]["pair"] for r in rows] ==
      [["0.0", "0.07"], ["0.07", "0.14"], ["0.14", "0.21"], ["0.21", "0.2747"]])
check("b7-2: y_along equals B7's p lines (+-5e-4)", all(abs(r["estimate"] - y) < 5e-4 for r, y in zip(rows, Y)),
      str([r["estimate"] for r in rows]))
match = all(abs(r["lo"] - lo) < 6e-4 and abs(r["hi"] - hi) < 6e-4 for r, (lo, hi) in zip(rows, EDGES))
print("B7's own resample stream: along intervals match the printed digits:", match)
check("b7-2: cells ZERO!, ZERO!, SLOW+ exactly (the boundary pair is reported, not asserted)",
      [rows[i]["cell"] for i in (0, 1, 3)] == ["ZERO!", "ZERO!", "SLOW+"], str([r["cell"] for r in rows]))
print("boundary pair 0.14->0.21 (frozen [-0.248, +0.005]):", rows[2]["cell"], round(rows[2]["lo"], 4), round(rows[2]["hi"], 4))
dl = {tuple(r["unit"]["pair"]): r["estimate"] for r in b7["reports"] if r["name"] == "delta"}
check("b7-2: Delta per size equals B7's (+-5e-5)", all(np.abs(np.array(dl[tuple(r["unit"]["pair"])]) - d).max() < 5e-5
                                                    for r, d in zip(rows, DELTA)), str(dl))
check("b7-2: every pair carries the flags T and U (no needle declared: membership unchecked)",
      all(r["flags"] == ["T", "U"] for r in rows) and all(p["flags"] == ["T", "U"] for p in b7["pairs"]))
check("b7-2: a pair has no point row (readings hold no along)", all(r["instrument"] != "along" for r in b7["readings"]))
check("b7-2: the vectors are keyed by pair", all(r["vector_key"] == "along/y_along/pair=" + "->".join(r["unit"]["pair"]) for r in rows))

vel = [r["estimate"] for r in bc["readings"] if r["column"] == "velocity"]
check("x7a-bc: needle velocities equal X7a's (+-2e-4)", all(abs(a - b) < 2e-4 for a, b in zip(vel, V)), str(vel))
check("x7a-bc: needle codes ORD DIS DIS MID ORD MID", [s["needle"] for s in bc["signature"]] == ["ORD", "DIS", "DIS", "MID", "ORD", "MID"])
check("x7a-bc: the five pairs", [r["unit"]["pair"] for r in bc["pair_readings"]] == BC_PAIRS)
check("x7a-bc: every pair reads REFUSE-OFF-MANIFOLD with no numbers",
      all(r["cell"] == "REFUSE-OFF-MANIFOLD" and r["estimate"] is None for r in bc["pair_readings"]))
check("x7a-bc: each reason names exactly the points X7a names",
      all(f"off-manifold: [{', '.join(o)}] read" in r["reason"] for o, r in zip(BC_OFF, bc["pair_readings"])),
      str([r["reason"] for r in bc["pair_readings"]]))
check("x7a-bc: the pairs carry the point flag N, never U (the needle was measured)", all(p["flags"] == ["N"] for p in bc["pairs"]))

p = nnn["pair_readings"][0]
check("x7a-nnn: the pair reads one of the declared set", p["cell"] in NNN_ALLOWED, p["cell"])
print("x7a-nnn pair reads", p["cell"], "-", p["reason"])
dn = next(r["estimate"] for r in nnn["reports"] if r["name"] == "delta")
check("x7a-nnn: a refused unit keeps the Delta it computed (-0.0091, -0.0103, -0.0053)",
      np.abs(np.array(dn) - [-0.0091, -0.0103, -0.0053]).max() < 5e-5, str(dn))
check("x7a-nnn: the refusal names the logged quantity, Delta", "sign of Delta not constant" in (p["reason"] or ""), str(p["reason"]))
check("x7a-nnn: flags N and T (a pair takes both points' flags)", nnn["pairs"][0]["flags"] == ["N", "T"], str(nnn["pairs"]))

basic, adv = view.show(bc, None, "basic"), view.show(b7, None, "advanced")
want = "  pair 0.0->1.0 y_along REFUSE-OFF-MANIFOLD (off-manifold: [0.0, 1.0] read [ORD, DIS] (membership.toml [along] reads needle))"
check("show lists the pairs after the points; BASIC keeps the cell and the reason, drops eps and flags",
      basic[-5] == want and not any("eps" in x or "flags" in x for x in basic[-6:]), str(basic[-6:]))
check("show ADVANCED adds eps, flags and the vector key to a pair line",
      "eps y=0.25 flags: truth point, membership unchecked (the upstream needle was not measured) vector along/y_along/pair=0.0->0.07"
      in adv[-4], str(adv[-4:]))
m = {"axes": {"point": ["a", "b", "c", "d"]}, "relations": {"r": {"template": "all-pairs", "axis": "point", "provenance": "Coupling"}}}
rel = door.relations_for(m, "r")
check("all-pairs: an edge (j -> i) for every i < j, in a fixed order",
      list(zip(rel.src, rel.tgt)) == [(1, 0), (2, 0), (2, 1), (3, 0), (3, 1), (3, 2)]
      and door.control_pairs(m, "r") == [("a", "b"), ("a", "c"), ("b", "c"), ("a", "d"), ("b", "d"), ("c", "d")],
      str(list(zip(rel.src, rel.tgt))))
check("all-pairs: A reads x[j] - x[i] on those edges",
      (A(admit.nodefield([1.0, 3.0, 7.0, 15.0]), rel).spatial[0] == [2.0, 6.0, 4.0, 14.0, 12.0, 8.0]).all())
found = declare.validate(ROOT, "x7a-bc", "verdict-x-rules")[0]
check("a set with no membership rule is refused at validate, naming the file and the copy to make",
      any("tables/verdict-x-rules/membership.toml" in f.loc and "has no rule for it" in f.msg and "copy tables/v01-rules" in f.nxt
          for f in found), str(found))
print("".join(f"FAILED {b}\n" for b in bad) + "test_along: " + ("FAILED" if bad else "all passed"))
sys.exit(1 if bad else 0)
