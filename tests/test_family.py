"""test_family - the family layer: the four families against expected/<set>.toml [[family]], the bracket on synthetic codes
through family.py's OWN function, the 240-cell partition, the declarations, and the commands."""
import json
import math
import subprocess
import sys
import tempfile
import tomllib
import numpy as np
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path[:0] = [str(ROOT / "cc"), str(ROOT / "cc" / "instruments")]
import author  # noqa: E402
import detect  # noqa: E402
import declare  # noqa: E402
import family  # noqa: E402

bad = []


def check(name, ok, why=""):
    print(("ok   " if ok else "FAIL ") + name + ("" if ok else f": {why}"))
    if not ok:
        bad.append(name)


def cc(*args):
    r = subprocess.run([sys.executable, str(ROOT / "bin" / "cc"), *args], capture_output=True, text=True, cwd=ROOT)
    return r.returncode, r.stdout + r.stderr


for f in sorted((ROOT / "expected").glob("*.toml")):
    for want in tomllib.loads(f.read_text()).get("family", []):
        msg, got = family.run(ROOT, want["id"], f.stem)
        have = got and {k: got[1].get(k, "<absent>") for k in want if k != "id"}   # plan 0871: every key a lock names, the new columns included
        check(f"{want['id']} under {f.stem}: {want['verdict']}", got is not None and all(have[k] == v for k, v in want.items() if k != "id"),
              f"{msg} {have} vs {want}")
nnn = family.run(ROOT, "x7a-nnn-manifold", "v01-rules")[1]
check("x7a-nnn-manifold is never LINE", nnn is not None and nnn[1]["verdict"] != "LINE")

fam, nulls = tomllib.loads((ROOT / "tables/v01-rules/family.toml").read_text()), ["NOT-MEASURED", "NOT-EVALUATED"]
for codes, want, edges in ((["DIS", "MID", "ORD"], "BRACKET", ["NO-DESCENT"] * 2), (["ORD", "DIS"], "NON-MONOTONE", ["DESCENT"]),
                           (["DIS", "DIS"], "NO-MID", ["NO-DESCENT"]), (["DIS", "NOT-MEASURED", "ORD"], "NOT-MEASURED", ["NOT-MEASURED"] * 2),
                           (["MID", "NOT-EVALUATED"], "NOT-EVALUATED", ["NOT-EVALUATED"])):
    res = {"signature": [{"point": str(i), "needle": c} for i, c in enumerate(codes)]}
    got = family.bracket_of(fam, res, nulls)
    check(f"bracket of {codes} is {want}, edges {edges} (nulls are plumbing)", (got[0], [e[2] for e in got[1]]) == (want, edges), str(got))

text = (ROOT / "tables/v01-rules/family.toml").read_text()
check("the 240-cell family partition validates total", declare.check_file(ROOT / "tables/v01-rules/family.toml", ROOT) == []
      and math.prod(len(v) for v in fam["alphabets"].values()) == 240)
with tempfile.TemporaryDirectory() as tmp:
    (Path(tmp) / "codes.toml").write_text((ROOT / "tables/v01-rules/codes.toml").read_text())
    gap = text.replace('verdict = "LINE"', 'verdict = "REFUSE-BRACKET"', 1).split("[[row]]")
    (Path(tmp) / "family.toml").write_text("[[row]]".join(gap[:-1]))      # the last row removed: cells are uncovered
    found = declare.check_file(Path(tmp) / "family.toml", ROOT)
    check("a family rule with a row removed is refused as not total", any("uncovered cells" in f.msg for f in found), str(found))
    for name, body, frag in (("one point", 'input = "x8-ising-needle"\ninterior = ["1.00"]', "at least two"),
                             ("unknown point", 'input = "x8-ising-needle"\ninterior = ["1.00", "9"]', "is not a point"),
                             ("no control edge", 'input = "x7a-bc"\ninterior = ["0.0", "1.5"]', "not an edge")):
        (Path(tmp) / "d.toml").write_text('schema = 1\nkind = "family-decl"\nid = "d"\n' + body + "\n")
        found = declare.check_file(Path(tmp) / "d.toml", ROOT)
        check(f"a declaration with {name} is refused", any(frag in f.msg for f in found), str(found))
    pre = 'schema = 1\nkind = "family-decl"\nid = "d"\n'
    for name, body, frag in (("an unknown rule name", 'input = "x2b-xy-3"\ninterior = "mid-run"', "mid-run-open"),
                             ("a hand list on an all-observed input", 'input = "c2-bc-two-start"\ninterior = ["d2.0-K1.0", "d2.0-K1.2"]',
                              'interior = "mid-run-open"')):
        (Path(tmp) / "d.toml").write_text(pre + body + "\n")
        found = declare.check_file(Path(tmp) / "d.toml", ROOT)
        check(f"a declaration with {name} is refused naming the rule", any(frag in f.msg + f.nxt for f in found), str(found))
    (Path(tmp) / "d.toml").write_text(pre + 'input = "x2b-xy-3"\ninterior = "mid-run-open"\n')
    check("interior = \"mid-run-open\" on x2b-xy-3 is accepted", declare.check_file(Path(tmp) / "d.toml", ROOT) == [])
    (Path(tmp) / "r" / "families").mkdir(parents=True)
    (Path(tmp) / "r" / "families" / "TEMPLATE.toml.in").write_text((ROOT / "families" / "TEMPLATE.toml.in").read_text())
    author.new_family(Path(tmp) / "r", "fresh")
    check("new family writes a template that validate refuses with a Next line per TODO",
          [f.msg for f in declare.check_file(Path(tmp) / "r" / "families" / "fresh.toml", ROOT)] == ["still TODO"] * 3)

# plan 0879 P1.2: the interior rule "mid-run-open" on synthetic needle codes, through family.py's OWN function
fam8 = tomllib.loads((ROOT / "tables/v08-rules/family.toml").read_text())


def rule(codes, fam_=None):
    pts = [f"p{i}" for i in range(len(codes))]
    m = {"axes": {"point": pts}, "relations": {"control": {"template": "chain", "axis": "point", "provenance": "Continuation"}}}
    res = {"signature": [{"point": q, "needle": c} for q, c in zip(pts, codes)]}
    got, why = family.interior_of({"id": "t", "input": "t", "interior": "mid-run-open"}, res, fam_ or fam8, m)
    return got and [pts.index(q) for q in got], why


for codes, want, name in (
        (["ORD", "ORD", "MID", "MID", "MID", "MID", "MID", "DIS"], [3, 4, 5], "a sink beyond on both sides drops both ends"),
        (["MID", "MID", "MID"], [0, 1, 2], "a run with no sink beyond keeps every point"),
        (["MID"], None, "one point is a null"),
        (["MID", "MID", "DIS", "MID", "MID"], None, "two runs are a null"),
        (["NOT-EVALUATED", "MID", "MID", "MID"], [1, 2, 3], "a null beyond is not a sink"),
        (["ORD", "DIS"], None, "no MID point is a null")):
    got, why = rule(codes)
    check(f"interior rule: {name}", got == want and (why is None) == (want is not None), f"{got} {why}")
got, why = rule(["MID", "MID"], {k: v for k, v in fam8.items() if k != "side"})
check("interior rule: a set with no [side] needle_code is a null with its reason", got is None and "needle_code" in (why or ""), str(why))
got, why = family.interior_of({"id": "t", "input": "x7a-bc", "interior": "mid-run-open"},
                              {"signature": [{"point": q, "needle": "MID"} for q in ("0.0", "1.5")]}, fam8,
                              {"axes": {"point": ["0.0", "1.5"]}, "relations": {"control": {"template": "pair", "pairs": [["0.0", "0.5"]]}}})
check("interior rule: a pair that is not a control edge is a null with its reason", got is None and "relations.control" in (why or ""), str(why))
# prediction (a): the stored x2b-xy-3 under v08, the hand list against the rule
ftx = (ROOT / "tables/v08-rules/family.toml").read_text()
resx = json.loads((ROOT / "results/x2b-xy-3@v08-rules.json").read_text())
mx, nul = detect.load_input("x2b-xy-3"), ["NOT-MEASURED", "NOT-EVALUATED"]
hand = {"id": "x2b-xy-3", "input": "x2b-xy-3", "interior": ["0.5", "0.6", "0.7", "0.8", "0.85"]}
with np.load(ROOT / resx["vectors"]) as zx:
    ah = family.compute(hand, resx, zx, fam8, ftx, mx, nul)
    ar = family.compute({**hand, "interior": "mid-run-open"}, resx, zx, fam8, ftx, mx, nul)
    check("prediction (a): the rule resolves 0.5 0.6 0.7 0.8 0.85 on x2b-xy-3@v08-rules", ar["interior"] == hand["interior"], str(ar["interior"]))
    keys = [k for k in ah if k not in ("interior", "rule")]
    check("prediction (a): every code, end and the verdict equal the hand list (BKT-END)", all(ah[k] == ar[k] for k in keys) and ar["verdict"] == "BKT-END",
          str({k: (ah[k], ar[k]) for k in keys if ah[k] != ar[k]}))
    rl = {**hand, "interior": "mid-run-open"}

    def planted(*dis):
        pl = json.loads(json.dumps(resx))
        pl["signature"] = [{**r, "needle": "DIS"} if r["point"] in dis else r for r in pl["signature"]]
        return family.interior_of(rl, pl, fam8, mx)
    check("plant: 0.89294 DIS makes the rule read 0.5..0.8, not the hand list", planted("0.89294")[0] == ["0.5", "0.6", "0.7", "0.8"], str(planted("0.89294")))
    check("plant: 0.85 DIS splits the run into two, a null", planted("0.85")[0] is None and "2 runs" in planted("0.85")[1], str(planted("0.85")))
    check("plant: 0.85 and 0.89294 DIS read 0.5..0.7 (the run ends at 0.8, which a sink lies beyond)", planted("0.85", "0.89294")[0] == ["0.5", "0.6", "0.7"], str(planted("0.85", "0.89294")))
    check("a hand list shows no rule suffix; a rule shows it", all(("(rule mid-run-open)" in " ".join(family.show(d, c, "v08-rules"))) == r
                                                                 for d, c, r in ((hand, ah, False), ({**hand, "interior": "mid-run-open"}, ar, True))))

with tempfile.TemporaryDirectory() as tmp:   # run() on a rule family whose set has no [side] needle_code refuses with the reason and a Next line
    (Path(tmp) / "families").mkdir()
    for d in ROOT.iterdir():
        if d.name not in ("families", ".git"):
            (Path(tmp) / d.name).symlink_to(d)
    (Path(tmp) / "families" / "rt.toml").write_text('schema = 1\nkind = "family-decl"\nid = "rt"\ninput = "b7-at-line-2"\ninterior = "mid-run-open"\n')
    msg, got = family.run(tmp, "rt", "v01-rules")
    check("run: a rule family under a set with no [side] needle_code refuses with the reason and a Next line",
          got is None and "NOT-EVALUATED" in msg and "needle_code" in msg and "Next: " in msg, str(msg))

rc, out = cc("family", "b7-at-line-2")
check("bin/cc family prints the verdict, each fingerprint and its cells", rc == 0 and "=> family verdict LINE" in out
      and "f2      MARGINAL" in out and "0.0->0.21 y_last" in out, out)
rc, out = cc("family", "b7-at-line-2", "--tables", "verdict-x-rules")
check("a set with no family.toml is refused with the copy to make", rc == 1 and "Next: copy tables/v01-rules/family.toml" in out, out)
rc, out = cc("family", "nope")
check("an unknown family is refused with the list", rc == 1 and "Families: " in out and "Next: bin/cc family" in out, out)
print("".join(f"FAILED {b}\n" for b in bad) + "test_family: " + ("FAILED" if bad else "all passed"))
sys.exit(1 if bad else 0)
