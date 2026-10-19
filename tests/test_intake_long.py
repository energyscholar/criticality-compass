"""test_intake_long - plan 1145 phase 1: the layout LONG_TABLE, and the S4/S5 reasons plan 1139 left without a body (E8), on planted banks
only. Each check was seen RED under a stated mutation (the plan-1145 report lists them). The stages run in-process (intake.fold over the
stage table) on declarations written from the template, with a temporary ROOTS name for the planted bank; S0's transducer check is not run
here (tests/test_intake_cli.py runs it on the command line).
 L1. The synthetic bank (seed 1, 9 curves) written as ONE file, the slow knob h a column, read with table-curve-v1 as a LONG_TABLE, gives the
     SAME census label as the PER_FILE bank read with csv-curve-v1; the slow column by 1-based position gives it too.
 L2. A LONG_TABLE in which one slow value occurs in two non-adjacent blocks refuses S5 CURVE_REPEATED (no replicate identity declared); a
     declared FILE identity cannot tell blocks of one file apart: REPLICATE_KEY_UNRESOLVED. Two ADJACENT runs of one value are one block,
     so a repeated row there is FAST_VALUE_REPEATED (that bank declares row_order ACQUISITION, so S4 makes no order claim).
 L3. Row order is checked within each curve: the long file (each block ascending in T, the whole file not) passes S4 with row_order
     ASCENDING; one swapped pair inside a block refuses S4 ROW_ORDER_DIFFERS.
 L4. UNIT_DIFFERS (S4) is live: a NAMES_UNITS header that states the declared units passes; one that states another unit refuses.
 L5. ACQUISITION_ORDER_DIFFERS (S5) is live: rows stored in acquisition order that do not run in the declared direction refuse; rows that do
     pass; direction UNORDERED makes no claim.
 L6. (plan 1160 P2) [replicate] identity SAME_FAST_VALUE: a curve with consecutive rows of one T (three readings of a point) passes S5,
     its points counted once and its readings per point min 1, max 3; the same bank under NONE refuses FAST_VALUE_REPEATED; a
     NON-consecutive repeat refuses S4 ROW_ORDER_DIFFERS under both (row_order ASCENDING). Seen RED: POINTS["SAME_FAST_VALUE"] made one
     point per row (as NONE) fails the PASS check (FAST_VALUE_REPEATED)."""
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path[:0] = [str(ROOT / "cc"), str(ROOT / "tests")]
import intake  # noqa: E402
import intake_synth  # noqa: E402
from intake_plant import long_table, outcome, per_file, write_long  # noqa: E402
import intake_plant  # noqa: E402

bad = []


def check(name, ok, why=""):
    print(("ok   " if ok else "FAIL ") + name + ("" if ok else f": {why}"))
    if not ok:
        bad.append(name)


T = intake.tables(ROOT)
run = lambda tmp, ident, text: intake_plant.run(T, tmp, ident, text)
with tempfile.TemporaryDirectory() as tmp:
    banks = Path(tmp) / "banks"
    intake_synth.write(banks / "pf", Path(tmp) / "pf-TRUTH", "pf", 1, 9)
    m = __import__("json").loads((banks / "pf" / "MANIFEST.json").read_text())
    curves = [(f["h"], (banks / "pf" / f["name"]).read_text().splitlines()[1:]) for f in m["files"]]

    def bank(name, blocks, **k):
        (banks / name).mkdir()
        write_long(banks / name, blocks, **k)
        return name

    # ---- L1. the same census label
    pf = outcome(run(tmp, "pf", per_file(m, "pf")), "S5")
    check("L1. the PER_FILE bank passes S5 CENSUS (9 curves, MISALIGNED)", pf[0] == "PASS" and pf[1].label.curves == 9 and pf[1].label.alignment.name == "MISALIGNED", str(pf)[:300])
    lt = outcome(run(tmp, "lt", long_table(m, "lt").replace("<long-test>/pf", "<long-test>/" + bank("lt", curves))), "S5")
    check("L1. the same bank as ONE long file (LONG_TABLE) passes S5 with the SAME census label", lt[0] == "PASS" and pf[0] == "PASS" and lt[1].label == pf[1].label, f"{str(lt)[:200]} against {str(pf)[:200]}")
    print(f"  census label: {getattr(pf[1], 'label', pf)}")
    lp = outcome(run(tmp, "lp", long_table(m, "lp", slow="4").replace("<long-test>/pf", "<long-test>/lt")), "S5")
    check("L1. the slow column by 1-based position (4) gives the same label", lp[0] == "PASS" and lp[1].label == pf[1].label, str(lp)[:300])

    # ---- L2. CURVE_REPEATED on a non-adjacent block; a FILE identity; adjacent runs are one block
    rep = outcome(run(tmp, "rep", long_table(m, "rep").replace("<long-test>/pf", "<long-test>/" + bank("rep", curves + curves[:1]))), "S5")
    check("L2. a slow value in two non-adjacent blocks refuses S5 CURVE_REPEATED", rep[0] == "CURVE_REPEATED", str(rep)[:300])
    fid = outcome(run(tmp, "fid", long_table(m, "fid").replace("<long-test>/pf", "<long-test>/rep").replace('identity = "NONE"', 'identity = "FILE"')), "S5")
    check("L2. a FILE replicate identity on a LONG_TABLE refuses S5 REPLICATE_KEY_UNRESOLVED (one file holds every curve)", fid[0] == "REPLICATE_KEY_UNRESOLVED", str(fid)[:300])
    adj = outcome(run(tmp, "adj", long_table(m, "adj").replace("<long-test>/pf", "<long-test>/" + bank("adj", curves[:1] + curves)).replace('row_order = "ASCENDING"', 'row_order = "ACQUISITION"')), "S5")
    check("L2. two ADJACENT runs of one slow value are one block: its repeated T refuses FAST_VALUE_REPEATED, not CURVE_REPEATED", adj[0] == "FAST_VALUE_REPEATED", str(adj)[:300])

    # ---- L3. row order within each curve
    s4 = outcome(run(tmp, "ord", long_table(m, "ord").replace("<long-test>/pf", "<long-test>/lt")), "S4")
    check("L3. each block ascending in T (the whole file not) passes S4 with row_order ASCENDING", s4[0] == "PASS", str(s4)[:300])
    swapped = [(h, rs[:3] + [rs[4], rs[3]] + rs[5:]) if i == 4 else (h, rs) for i, (h, rs) in enumerate(curves)]
    sw = outcome(run(tmp, "sw", long_table(m, "sw").replace("<long-test>/pf", "<long-test>/" + bank("sw", swapped))), "S4")
    check("L3. one swapped pair inside block 5 refuses S4 ROW_ORDER_DIFFERS, naming the block", sw[0] == "ROW_ORDER_DIFFERS", str(sw)[:300])

    # ---- L4. UNIT_DIFFERS through a header that states units
    nu = 'kind = "NAMES_UNITS"\nrows = 2\nnames = 1\nunits = 2'
    good = outcome(run(tmp, "u1", long_table(m, "u1", header=nu).replace("<long-test>/pf", "<long-test>/" + bank("u1", curves, head="T,C,sigma,h\n" + "dimensionless," * 3 + "dimensionless\n"))), "S4")
    check("L4. a header stating the declared units passes S4", good[0] == "PASS", str(good)[:300])
    wrong = outcome(run(tmp, "u2", long_table(m, "u2", header=nu).replace("<long-test>/pf", "<long-test>/" + bank("u2", curves, head="T,C,sigma,h\nK,dimensionless,dimensionless,dimensionless\n"))), "S4")
    check("L4. a header stating T in K (declared dimensionless) refuses S4 UNIT_DIFFERS", wrong[0] == "UNIT_DIFFERS", str(wrong)[:300])
    unc = outcome(run(tmp, "u3", long_table(m, "u3", header=nu).replace("<long-test>/pf", "<long-test>/" + bank("u3", curves, head="T,C,sigma,h\ndimensionless,dimensionless,J,dimensionless\n"))), "S4")
    check("L4. an uncertainty stated in another unit than the measured quantity refuses S4 UNIT_DIFFERS", unc[0] == "UNIT_DIFFERS", str(unc)[:300])

    # ---- L5. ACQUISITION_ORDER_DIFFERS
    acq = lambda ident, direction: long_table(m, ident).replace("<long-test>/pf", "<long-test>/lt").replace('row_order = "ASCENDING"', 'row_order = "ACQUISITION"').replace('direction = "UNORDERED"', f'direction = "{direction}"')
    down = outcome(run(tmp, "a1", acq("a1", "DESCENDING")), "S5")
    check("L5. rows stored in acquisition order, ascending in T, declared DESCENDING: S5 refuses ACQUISITION_ORDER_DIFFERS", down[0] == "ACQUISITION_ORDER_DIFFERS", str(down)[:300])
    up = outcome(run(tmp, "a2", acq("a2", "ASCENDING")), "S5")
    check("L5. the same rows declared ASCENDING pass S5", up[0] == "PASS", str(up)[:300])
    un = outcome(run(tmp, "a3", acq("a3", "UNORDERED")), "S5")
    check("L5. direction UNORDERED makes no claim: S5 passes", un[0] == "PASS", str(un)[:300])
    pfd = outcome(run(tmp, "a4", per_file(m, "a4").replace('row_order = "ASCENDING"', 'row_order = "ACQUISITION"').replace('direction = "UNORDERED"', 'direction = "DESCENDING"')), "S5")
    check("L5. the same holds for PER_FILE: ascending files in acquisition order, declared DESCENDING, refuse", pfd[0] == "ACQUISITION_ORDER_DIFFERS", str(pfd)[:300])

    # ---- L6. (1160 P2) SAME_FAST_VALUE: consecutive readings of one point
    tripled = [(h, [x for j, r in enumerate(rs) for x in [r] * (1 + 2 * (i == 2 and j % 2 == 0))]) for i, (h, rs) in enumerate(curves)]
    apart = [(h, rs[:5] + [rs[2]] + rs[5:]) if i == 2 else (h, rs) for i, (h, rs) in enumerate(curves)]
    ident = lambda name, b, who: long_table(m, name).replace("<long-test>/pf", "<long-test>/" + b).replace('identity = "NONE"', f'identity = "{who}"')
    sf = outcome(run(tmp, "sf", ident("sf", bank("sf", tripled), "SAME_FAST_VALUE")), "S5")
    check("L6. consecutive equal T under SAME_FAST_VALUE pass S5: the points are those of the plain bank, readings per point min 1, max 3",
          sf[0] == "PASS" and sf[1].label.readings == (1, 3) and sf[1].curves == lt[1].curves and sf[1].label.n_max == lt[1].label.n_max, str(sf)[:300])
    sn = outcome(run(tmp, "sn", ident("sn", "sf", "NONE")), "S5")
    check("L6. the same bank under identity NONE refuses S5 FAST_VALUE_REPEATED", sn[0] == "FAST_VALUE_REPEATED", str(sn)[:300])
    for who in ("SAME_FAST_VALUE", "NONE"):
        na = outcome(run(tmp, "na" + who, ident("na" + who, {True: lambda: bank("na", apart), False: lambda: "na"}[who == "SAME_FAST_VALUE"](), who)), "S5")
        check(f"L6. a NON-consecutive repeat of T refuses S4 ROW_ORDER_DIFFERS under {who}", na[0] == "ROW_ORDER_DIFFERS", str(na)[:300])

print("test_intake_long: " + ("FAILED " + "; ".join(bad) if bad else "all passed"))
sys.exit(1 if bad else 0)
