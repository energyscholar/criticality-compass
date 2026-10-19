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
     pass; direction UNORDERED makes no claim."""
import re
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path[:0] = [str(ROOT / "cc")]
import intake  # noqa: E402
import intake_synth  # noqa: E402

bad = []


def check(name, ok, why=""):
    print(("ok   " if ok else "FAIL ") + name + ("" if ok else f": {why}"))
    if not ok:
        bad.append(name)


CHOICES = {"intake.mode": '"PROSPECTIVE"', "acquisition.mode": '"INDEPENDENT"', "acquisition.direction": '"UNORDERED"', "acquisition.row_order": '"ASCENDING"',
           "interval.method": '"iid"', "bracket.required": '"CANDIDATE_BRACKET"', "projection.lane": '"PRIMARY"', "projection.from": '"C"', "projection.to": '"C_max"',
           "projection.bias": '"MAX_MEASURED"', "projection.keeps": '"the largest C on each curve"', "projection.discards": '"every other point"',
           "bridge.lane": '"PRIMARY"', "bridge.on": '"C_max"', "bridge.template": '"CHAIN_SLOW"', "bridge.bias": '"CHAIN_SLOW"', "shift.c": "0.0"}
LONG = '''# [reader]: VARIANT on name
[reader]
name = "table-curve-v1"
comment = ["#"]
[reader.format]
kind = "COMMA"
[reader.header]
{header}

[selection]
layout = "LONG_TABLE"
file = "bank.csv"
excluded = []
[selection.slow]
source = "COLUMN"
key = {slow}

'''


def per_file(m, ident):
    """The PER_FILE declaration text of a synth bank: the template filled by --from-synth's values and the choices above."""
    values, dropped, _ = intake_synth.declare(m, ident, "pf")   # the root names bank pf; a test re-points it
    text = intake.fill((ROOT / "intake" / "TEMPLATE.intake.toml.in").read_text().replace("<ID>", ident), {**values, **CHOICES}, dropped)
    return text.replace('method = "iid"', 'method = "iid"\nresamples = 1000\nlevel = 0.95\nseed = 1145\ntau_declared = 1').replace("<intake-synth>/", "<long-test>/")


def long_table(m, ident, header='kind = "NAMES"\nrows = 1\nnames = 1', slow='"h"'):
    """The same declaration as a LONG_TABLE of bank.csv: [reader] table-curve-v1 and [selection] LONG_TABLE replace their PER_FILE blocks."""
    text = per_file(m, ident)
    return re.sub(r"(?s)# \[reader\]:.*?(?=\[knobs\.slow\])", lambda _: LONG.format(header=header, slow=slow), text)


def write_long(bank, blocks, head="T,C,sigma,h\n"):
    """One long file: each (h, rows) block's rows with h appended, in the given order."""
    (bank / "bank.csv").write_text("# the synthetic bank as one long table (plan 1145 test)\n" + head + "".join(f"{r},{h}\n" for h, rows in blocks for r in rows))


def run(tmp, ident, text):
    d = Path(tmp) / "declarations" / ident
    d.mkdir(parents=True)
    (d / "intake.toml").write_text(text)
    t = {**T, "roots": {**T["roots"], "<long-test>": str(Path(tmp) / "banks")}}
    return intake.fold(t["stages"]["stage"], intake.bodies(t, d, text, []))


def outcome(out, sid):
    """("PASS", the evidence) when stage `sid` passed; else (the reason of the first refused stage, its result as text)."""
    first = [e.result for e in out.values() if e.mark is intake.Mark.REFUSED] + [None]
    return {True: lambda: ("PASS", out[sid].result.evidence), False: lambda: (getattr(first[0], "reason", out[sid].mark.name), str(first[0])[:300])}[out[sid].mark is intake.Mark.PASSED]()


T = intake.tables(ROOT)
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

print("test_intake_long: " + ("FAILED " + "; ".join(bad) if bad else "all passed"))
sys.exit(1 if bad else 0)
