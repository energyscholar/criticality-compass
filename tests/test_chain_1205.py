"""test_chain_1205 - plan 1205 P2: `bin/cc chain` (cc/chain.py), the plan 1201 fix F-a. It reads no real data. In-process checks run
cc/chain.py's evaluation on planted curves; the CLI checks run `bin/cc chain` on a copy of the Compass whose ROOTS.toml names planted LONG_TABLE
banks (tests/intake_plant.py). Each check names its red mutation (applied with `bin/cc mutate`, seen FAIL by this name, reverted):
 H1. every new enum (Lane, Step, FamilyAtom, Robustness, CoLocation) declares ATOMS and an Axiom, and every member NAME parses (the binding
     rule's parser: ATOM(_OR_ATOM)*, NOT_<ATOM> = the complement) to exactly its own atom. Red, per enum: a member with a wrong name added
     (to the class and its ATOMS): Lane ARGMAX_FAST_OR_ARGMIN_FAST, Step NOT_UNMEASURED_BETWEEN, FamilyAtom NOT_NO_SEGMENT, Robustness NOT_FRAGILE,
     CoLocation NOT_CO_LOCATED (the plan's first name for APART_BEYOND_WC: it parses to the complement of CO_LOCATED, two atoms).
 H2. the DIAG arm that stops 10/10 under linenav (plan 1201 DIAG section 4: riser at c0|c1, descending, frac 0.12, uniform slows, tiered;
     the C'' sharp plant of plant1201.py, seeds 1201-1210): under chain, on every seed, the c0|c1 pair is typed STEP_BEYOND_WC at w_c 0.05 and
     0.10 and STEP_WITHIN_WC at w_c 0.15 and 0.25 (its step is 0.1034 of the fast span: the 0.24 riser less the plant's own drift, on the
     sample grid), and lane ARGMAX_FAST at w_c 0.15 is SEGMENT_SPANS_FAMILY (no stop artefact). Red: `abs(b.pos - a.pos) <= wc` -> `<= wc / 2`.
 H3. a NULL bank (noise only, its sigma column the noise's) gives NO_SEGMENT in every cell of every lane, explicitly (the word is printed per
     cell and each lane's NO_SEGMENT atom is ROBUST): an empty output is never a zero. Red: the sample lanes read UNTIERED (chain's
     `F.feature(..., z, kind, ...)` -> `F.feature(..., z, "NONE", ...)`: noise maxima become Located and chance segments appear).
 H4. a planted AtSpanEnd curve (curve 4's peak on its last sample) breaks the planted line: pairs 3|4 and 4|5 are UNMEASURED_BETWEEN (never
     BEYOND) and the family is SEGMENTS_PARTIAL with segments [0, 3] and [5, 8]. Red: `located()` made `p.kind != "Absent"`.
 H5. segment identity across cells is the declared rule IDENTITY (overlap in curve ranks), and Robustness follows its axiom. Red: overlaps()
     made equality of the ranges (`a == b`).
 H6. CO_LOCATION: two observables of one family (the planted line, and a copy with curve 6's peak moved 10 samples): curve 6 is APART_BEYOND_WC
     in every cell, every other curve CO_LOCATED; a curve not Located on either side is NOT_COMPARABLE. Red: CO table (True, False) ->
     CO_LOCATED.
 H7. the CLI golden tests/chain/plant-chain.txt (line2, then line with --with line2 (co-location reads line2's typed result), null, endcurve; stdout and results/chain/<id>.json) is reproduced
     byte for byte (CC_REGOLDEN=1 rewrites it). Red: the sentence's "feature line segment" made "segment".
 H8. the words FOLLOWED and CRITICAL (any case) appear in no chain golden (tests/chain/*.txt) and in no chain output of this run. Red: the
     sentence's "feature line segment" made "critical line segment"; NOT_A_CLASS given the word "followed"; the golden given "CRITICAL".
 H9. every REFUSAL row of chain is reached through the CLI as `REFUSED <code>: ...`, exit 1 (GRID_UNDECLARED, GRID_UNREADABLE (also a wrong
     lane name in the grid), LANE_UNDECLARED, CO_LOCATION_UNRUN, CO_LOCATION_GRID_DIFFERS, CO_LOCATION_SPANS_DIFFER), and the intake's refusals pass through (NO_DECLARATION).
     Red: grid() accepts any lane name (`x in Lane.__members__` -> `True`)."""
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path[:0] = [str(ROOT / "cc"), str(ROOT / "tests")]
import chain  # noqa: E402
import intake_feature as F  # noqa: E402
import intake_synth as S  # noqa: E402
from intake_plant import long_table, write_long  # noqa: E402

GOLD = ROOT / "tests" / "chain" / "plant-chain.txt"
GRID = ROOT / "intake" / "grids" / "ll1-pre-v3.toml"
REGOLDEN = os.environ.get("CC_REGOLDEN") == "1"
WCS = (0.05, 0.10, 0.15, 0.25)
bad, reached = [], set()


def check(name, ok, why=""):
    print(("ok   " if ok else "FAIL ") + name + ("" if ok else f": {why}"))
    if not ok:
        bad.append(name)


# ---- H1 the enum names
def parse(name, atoms):
    """The binding rule's parser (tests/test_intake.py): ATOM(_OR_ATOM)*, NOT_<ATOM> = the complement within the atoms; None when a part is no atom."""
    out = set()
    for part in name.split("_OR_"):
        neg = part.startswith("NOT_") and part[4:] in atoms
        lit = {True: atoms - {part[4:]}, False: {part} & atoms}[neg]
        if not lit:
            return None
        out |= lit
    return frozenset(out)


check("H1. the parser reads NOT_CO_LOCATED over {CO_LOCATED, NOT_CO_LOCATED, NOT_COMPARABLE} as two atoms (a wrong name is seen)",
      parse("NOT_CO_LOCATED", {"CO_LOCATED", "NOT_CO_LOCATED", "NOT_COMPARABLE"}) == {"NOT_CO_LOCATED", "NOT_COMPARABLE"})
for E in (chain.Lane, chain.Step, chain.FamilyAtom, chain.Robustness, chain.CoLocation):
    m = re.search(r"ATOMS: ([A-Z_\s|]+?)\.", E.__doc__ or "")
    atoms = set(re.sub(r"\s", "", m[1]).split("|")) if m else set()
    check(f"H1. {E.__name__} declares ATOMS and an Axiom, and its members are exactly the atoms", bool(atoms) and "Axiom" in E.__doc__ and {x.name for x in E} == atoms,
          f"{sorted(atoms)} vs {sorted(x.name for x in E)}")
    check(f"H1. every {E.__name__} name parses to its own atom alone", all(parse(x.name, atoms) == {x.name} and x.value == x.name for x in E),
          str([x.name for x in E if parse(x.name, atoms) != {x.name}]))


@dataclass(frozen=True)
class Curve:
    slow: tuple
    rows: list


def fam(ident, curves, kind="COLUMN"):
    """A chain.Family of in-memory curves (slow order given), no window: the fast span is the curves' measured one."""
    return chain.Family(ident, tuple(curves), tuple(float(c.slow[0]) for c in curves), F.span(curves, None), F.FAST_ENDS[True](curves, None), 2.0, kind, "h")


ALL = chain.Grid(WCS, tuple(chain.Lane), "planted")


# ---- H2 the DIAG arm (plan 1201 DIAG section 4; the compute host's ~/scratch/1201-diag/plant1201.py oracle(seed, -0.12, "COLUMN", None, 1))
def diag(seed, frac=-0.12, ri=1):
    rng = np.random.default_rng(seed)
    hs = [round(float(h), 10) for h in np.linspace(-0.5, 0.5, 9)]
    cs = []
    for i, h in enumerate(hs):
        c = S.sharp_c(h, 0.0) + frac * 2.0 * (i >= ri)   # the fast span is [1.5, 3.5]: the riser is frac of it, between curve ri - 1 and ri
        v = S.B + S.lor(S.PLANE_GRID, S.A0 + S.A1 * np.exp(-(h - S.H_STAR) ** 2 / (2 * S.S ** 2)), c, S.W) + rng.normal(0, S.SIGMA, S.PLANE_GRID.size)
        cs.append(Curve((h,), [(float(a), float(b), S.SIGMA) for a, b in zip(S.PLANE_GRID, v)]))
    return fam("diag", cs)


arm = []
for seed in range(1201, 1211):
    ev = chain.evaluate(diag(seed), ALL)[chain.Lane.ARGMAX_FAST]
    p = ev[0.15][0]
    arm.append(([ev[w][1][0].name for w in WCS], ev[0.15][3].name, round(abs(p[1].pos - p[0].pos), 4)))
check("H2. DIAG 10/10 arm: c0|c1 is STEP_BEYOND_WC at w_c 0.05 and 0.10, STEP_WITHIN_WC at 0.15 and 0.25, on every seed",
      all(a[0] == ["STEP_BEYOND_WC", "STEP_BEYOND_WC", "STEP_WITHIN_WC", "STEP_WITHIN_WC"] for a in arm), str(arm[:2]))
check("H2. DIAG 10/10 arm: its c0|c1 step is 0.1034 of the fast span on every seed (typed by w_c, never walked)", {a[2] for a in arm} == {0.1034}, str({a[2] for a in arm}))
check("H2. DIAG 10/10 arm: lane ARGMAX_FAST at w_c 0.15 is SEGMENT_SPANS_FAMILY on 10 of 10 seeds (linenav stopped 10 of 10)",
      [a[1] for a in arm] == ["SEGMENT_SPANS_FAMILY"] * 10, str([a[1] for a in arm]))


# ---- H5 identity and robustness (pure)
check("H5. IDENTITY: ranges sharing a curve rank are one segment; disjoint ranges are two (A1 containment)", chain.contained((3, 4), (0, 9)) and chain.contained((2, 5), (2, 5)) and not chain.contained((0, 9), (3, 4)) and not chain.contained((0, 3), (3, 6)) and not chain.contained((0, 3), (4, 6)))
check("H5. Robustness: 4 cells -> m 3, 4 ROBUST; m 2 INTERMEDIATE; m 1 FRAGILE; 1 cell -> m 1 ROBUST (three quarters first)",
      [chain.robustness(m, 4).name for m in (4, 3, 2, 1)] + [chain.robustness(1, 1).name] == ["ROBUST", "ROBUST", "INTERMEDIATE", "FRAGILE", "ROBUST"])
toy = {chain.Lane.ARGMAX_FAST: {0.05: (None, None, [(0, 2)], None), 0.10: (None, None, [(1, 5)], None), 0.15: (None, None, [(4, 8)], None), 0.25: (None, None, [(6, 8)], None)}}
counts = [sum(any(chain.contained(s, o) for o in toy[chain.Lane.ARGMAX_FAST][w][2]) for w in WCS) for s in ((0, 2), (1, 5), (4, 8), (6, 8))]
check("H5. a chain of overlaps is counted per segment, not transitively: (0,2) 1 cell, (1,5) 1, (4,8) 1, (6,8) 2 (A1 containment)", counts == [1, 1, 1, 2], str(counts))


# ---- H6 co-location (in process)
def line_curves(k=9, n=40, moved=None, shift=10, sig=0.03):
    """k curves of n samples (T = 1 .. n), a sharp peak at sample rank 8 + 2j on curve j (`moved`: that curve's peak `shift` ranks later)."""
    return [Curve((0.1 * (j + 1),), [(1.0 + i, 10.0 / (1 + (i - (8 + 2 * j + shift * (j == moved))) ** 2), sig) for i in range(n)]) for j in range(k)]


fa_, fb_ = fam("line", line_curves()), fam("line2", line_curves(moved=6))
ca, cb = ({(c["lane"], c["wc"]): c["curves"] for c in chain.rows(f, ALL, chain.evaluate(f, ALL))[0]} for f in (fa_, fb_))
co = {w: [c.name for c in chain.colocate(ca[("ARGMAX_FAST", w)], cb[("ARGMAX_FAST", w)], w)] for w in WCS}
check("H6. curve 6 APART_BEYOND_WC and every other curve CO_LOCATED, in every cell", all(v == ["CO_LOCATED"] * 6 + ["APART_BEYOND_WC"] + ["CO_LOCATED"] * 2 for v in co.values()), str(co))
mn = [c.name for c in chain.colocate(ca[("ARGMIN_FAST", 0.15)], cb[("ARGMIN_FAST", 0.15)], 0.15)]
check("H6. lane ARGMIN_FAST (each minimum at a span end: AtSpanEnd) is NOT_COMPARABLE on every curve", mn == ["NOT_COMPARABLE"] * 9, str(mn))


# ---- CLI checks
def rows_text(curves):
    return [(c.slow[0], [f"{r[0]:.4f},{r[1]:.4f},{r[2]:.4f}" for r in c.rows]) for c in curves]


def null_curves(seed=1205, k=9, n=40, sig=0.03):
    rng = np.random.default_rng(seed)
    return [Curve((0.1 * (j + 1),), [(1.0 + i, float(1.0 + rng.normal(0, sig)), sig) for i in range(n)]) for j in range(k)]


def end_curves():
    cs = line_curves()
    cs[4] = Curve(cs[4].slow, [(1.0 + i, 10.0 / (1 + (i - 39) ** 2), 0.03) for i in range(40)])   # curve 4's peak on its last sample
    return cs


def cli_checks():
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        w, banks = tmp / "cc", tmp / "banks"
        shutil.copytree(ROOT, w, ignore=shutil.ignore_patterns(".git", "__pycache__", "results", "benchmark", "fixtures", "data", "scratch"))
        with (w / "intake" / "ROOTS.toml").open("a") as f:
            f.write(f'\n"<chain-test>" = "{banks}"   # test_chain_1205: the planted banks\n')
        S.write(banks / "pf", tmp / "pf-TRUTH", "pf", 1, 9)
        m = json.loads((banks / "pf" / "MANIFEST.json").read_text())

        def cc(*args):
            r = subprocess.run([sys.executable, str(w / "bin" / "cc"), *args], capture_output=True, text=True, cwd=w)
            return r.stdout + r.stderr, r.returncode

        def plant(ident, curves, profile=True):
            (banks / ident).mkdir()
            write_long(banks / ident, rows_text(curves))
            d = w / "declarations" / ident
            d.mkdir()
            text = long_table(m, ident).replace("<long-test>/pf", f"<chain-test>/{ident}") + '\n[plane]\naxes = "slow-fast"\n'
            (d / "intake.toml").write_text(text)
            (d / "transducer.toml").write_text(S.declare(m, ident, "pf")[2])
            [cc("intake", "profile", ident, root) for root in re.findall(r'^root = "([^"]*)"', text, re.M)[:1] if profile]

        def refused(out):
            code = re.findall(r"^REFUSED ([A-Z_]+):", out, re.M)
            reached.update(code)
            return code[:1]

        for ident, cs in (("line", line_curves()), ("line2", line_curves(moved=6)), ("null", null_curves()), ("endcurve", end_curves()),
                          ("short", line_curves(n=30))):
            plant(ident, cs)
        text, outs = "", []
        for args in (("line2",), ("line", "--with", "line2"), ("null",), ("endcurve",)):
            out, rc = cc("chain", args[0], "--grid", "intake/grids/ll1-pre-v3.toml", *args[1:])
            res = w / "results" / "chain" / f"{args[0]}.json"
            outs.append((args[0], out, rc, res.read_text() if res.is_file() else "(absent)\n"))
            text += f"$ bin/cc chain {args[0]} --grid intake/grids/ll1-pre-v3.toml {' '.join(args[1:])}\n{out}exit {rc}\n--- results/chain/{args[0]}.json\n{outs[-1][3]}"
        {True: lambda: (GOLD.parent.mkdir(exist_ok=True), GOLD.write_text(text)), False: lambda: None}[REGOLDEN]()
        check("H7. stdout and results/chain/*.json equal the golden tests/chain/plant-chain.txt", GOLD.is_file() and text == GOLD.read_text(),
              "\n".join(ln for ln in text.splitlines() if ln not in (GOLD.read_text().splitlines() if GOLD.is_file() else []))[:600])
        doc = {o[0]: json.loads(o[3]) for o in outs if o[3] != "(absent)\n"}
        line = doc.get("line", {"cells": [], "family_atoms": {}, "co_location": []})
        fa = {(c["lane"], c["wc"]): c["family"] for c in line["cells"]}
        check("H7. the planted line (step 2/39 = 0.051 of the span per curve): ARGMAX_FAST NO_SEGMENT at w_c 0.05, SEGMENT_SPANS_FAMILY at 0.10, 0.15, 0.25",
              [fa.get(("ARGMAX_FAST", x)) for x in WCS] == ["NO_SEGMENT"] + ["SEGMENT_SPANS_FAMILY"] * 3, str(fa))
        seg = [s for c in line["cells"] if c["lane"] == "ARGMAX_FAST" and c["wc"] == 0.15 for s in c["segments"]]
        check("H5. the spanning segment is in 3 of 4 cells, ROBUST, slow 0.1 -> 0.9, 9 curves", [(s["cells"], s["robustness"], s["slow"], s["curves"]) for s in seg] == [(3, "ROBUST", [0.1, 0.9], 9)], str(seg))
        cl = [c for c in line["co_location"] if c["lane"] == "ARGMAX_FAST"]
        check("H6. the CLI co-location rows: curve 6 (slow 0.7) APART_BEYOND_WC in all 4 cells, the rest CO_LOCATED",
              len(cl) == 4 and all([x["co_location"] for x in c["curves"]] == ["CO_LOCATED"] * 6 + ["APART_BEYOND_WC"] + ["CO_LOCATED"] * 2 for c in cl), str(cl)[:400])
        null = doc.get("null", {"cells": [], "family_atoms": {}})
        check("H3. NULL bank: NO_SEGMENT in every one of the 12 cells (3 lanes x 4 w_c)", len(null["cells"]) == 12 and all(c["family"] == "NO_SEGMENT" for c in null["cells"]),
              str([(c["lane"], c["wc"], c["family"]) for c in null["cells"]]))
        check("H3. NULL bank: each lane's family atoms are {NO_SEGMENT: 4 cells, ROBUST}", null["family_atoms"] == {ln: {"NO_SEGMENT": {"cells": 4, "robustness": "ROBUST"}} for ln in ("ARGMAX_FAST", "ARGMIN_FAST", "ARGMAX_ABS_A_FAST")},
              str(null["family_atoms"]))
        nout = [o[1] for o in outs if o[0] == "null"][0]
        check("H3. NULL bank: the word NO_SEGMENT is printed for every cell (an empty output is never a zero)",
              len(re.findall(r"^cell \S+ w_c \S+: NO_SEGMENT;", nout, re.M)) == 12 and nout.count("NO_SEGMENT in 4 of 4 cells (ROBUST)") == 3, nout[:600])
        end = doc.get("endcurve", {"cells": []})
        e15 = [c for c in end["cells"] if c["lane"] == "ARGMAX_FAST" and c["wc"] == 0.15]
        check("H4. the AtSpanEnd curve 4 is typed AtSpanEnd; pairs 3|4 and 4|5 UNMEASURED_BETWEEN; SEGMENTS_PARTIAL with [0, 3] and [5, 8]",
              len(e15) == 1 and e15[0]["curves"][4]["kind"] == "AtSpanEnd" and [s["step"] for s in e15[0]["steps"]][3:5] == ["UNMEASURED_BETWEEN"] * 2
              and e15[0]["family"] == "SEGMENTS_PARTIAL" and [s["ranks"] for s in e15[0]["segments"]] == [[0, 3], [5, 8]], str(e15)[:600])
        for g in sorted({GOLD, *GOLD.parent.glob("*.txt")}):
            check(f"H8. no FOLLOWED and no CRITICAL (any case) in the chain golden {g.name}", g.is_file() and not re.search(r"(?i)followed|critical", g.read_text()), g.name)
        check("H8. no FOLLOWED and no CRITICAL (any case) in this run's chain output", not re.search(r"(?i)followed|critical", text), (re.findall(r"(?i).{40}(?:followed|critical).{20}", text) + [""])[0])
        check("H8. each lane's sentence says \"feature line\" (never a class of line)", all("feature line" in o[1] for o in outs[1:2]), outs[1][1][-400:])

        # ---- H9 the typed refusals
        out, rc = cc("chain", "line")
        check("H9. no --grid: REFUSED GRID_UNDECLARED, exit 1", refused(out) == ["GRID_UNDECLARED"] and rc == 1, out[-300:])
        (tmp / "g-bad.toml").write_text('wc = [0.15]\nlanes = ["ARGMAX"]\n')
        out, rc = cc("chain", "line", "--grid", str(tmp / "g-bad.toml"))
        check("H9. a wrong lane name in the grid: REFUSED GRID_UNREADABLE, exit 1", refused(out) == ["GRID_UNREADABLE"] and rc == 1, out[-300:])
        (tmp / "g-wc.toml").write_text('wc = [0.0]\nlanes = ["ARGMAX_FAST"]\n')
        out, rc = cc("chain", "line", "--grid", str(tmp / "g-wc.toml"))
        check("H9. a w_c outside (0, 1]: REFUSED GRID_UNREADABLE, exit 1", refused(out) == ["GRID_UNREADABLE"] and rc == 1, out[-300:])
        out, rc = cc("chain", "line", "--grid", "intake/grids/ll1-pre-v3.toml", "--with", "short")
        check("H9. --with an id chain has not run: REFUSED CO_LOCATION_UNRUN, exit 1", refused(out) == ["CO_LOCATION_UNRUN"] and rc == 1, out[-300:])
        (tmp / "g-one.toml").write_text('wc = [0.15]\nlanes = ["ARGMAX_FAST"]\n')
        cc("chain", "short", "--grid", str(tmp / "g-one.toml"))
        out, rc = cc("chain", "line", "--grid", "intake/grids/ll1-pre-v3.toml", "--with", "short")
        check("H9. --with an id run under another grid: REFUSED CO_LOCATION_GRID_DIFFERS, exit 1", refused(out) == ["CO_LOCATION_GRID_DIFFERS"] and rc == 1, out[-300:])
        cc("chain", "short", "--grid", "intake/grids/ll1-pre-v3.toml")
        out, rc = cc("chain", "line", "--grid", "intake/grids/ll1-pre-v3.toml", "--with", "short")
        check("H9. --with a family of another fast span: REFUSED CO_LOCATION_SPANS_DIFFER, exit 1", refused(out) == ["CO_LOCATION_SPANS_DIFFER"] and rc == 1, out[-300:])
        out, rc = cc("chain", "nosuch", "--grid", "intake/grids/ll1-pre-v3.toml")
        check("H9. an id with no declarations/<id>/: REFUSED NO_DECLARATION, exit 1", refused(out) == ["NO_DECLARATION"] and rc == 1, out[-300:])
        pol = w / "intake" / "POLICY.toml"
        pol.write_text(re.sub(r"(?s)\n\[feature_projection\.FEATURE_ARGMIN_FAST\].*?(?=\n\[|\Z)", "\n", pol.read_text()))
        out, rc = cc("chain", "line", "--grid", "intake/grids/ll1-pre-v3.toml")
        check("H9. POLICY without a grid lane's row: REFUSED LANE_UNDECLARED naming it, exit 1",
              refused(out) == ["LANE_UNDECLARED"] and "FEATURE_ARGMIN_FAST" in out and rc == 1, out[-300:])


try:
    cli_checks()
except Exception as e:   # a crash is a named FAIL, never a silent pass
    check("H7-H9. the CLI checks run to the end", False, repr(e)[:300])
check("H9. every REFUSAL row of chain was reached through the CLI", set(chain.REFUSAL) <= reached, str(sorted(set(chain.REFUSAL) - reached)))
print(f"{len(bad)} failed" if bad else "test_chain_1205: all passed")
sys.exit(1 if bad else 0)
