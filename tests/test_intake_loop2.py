"""test_intake_loop2 - plan 1160 loop 2 and 3 (research/1160/DIAG-loop2.md amendments A17-A23; plan gates P7b A24-A26, S11.8, S11.9
A29-A32): one check per amendment test. Planted inputs only (the synthetic bank of cc/intake_synth.py; no real data).
 T17.1 a PER_FILE curve that revisits one fast value, control MEASURED: S5 passes and S10 is reached; the same under control SET is
       FAST_VALUE_REPEATED.
 T17.4 a SET/NONE curve with one consecutive pair, one revisit and three monotone runs: FAST_VALUE_REPEATED's Detail prints `consecutive
       runs = 1; longest run = 2; values revisited = 1; monotone runs = 3`, the refused curves out of all (S11.8: `curves refused = 1; of
       curves = 9`) and the exit of each kind found (A30); with the file name and the counts taken out it holds no digit.
 T17.5 control MEASURED changes no result on a bank with no repeat: S10's records and the census label of MAX_MEASURED and of ARGMAX_FAST
       (the PRIMARY projection) are the same under MEASURED as under SET.
 (T17.2 is intake_plant.CHOICE_PLANTS' MEASURED_KNOB_HAS_NO_POINTS rows, run by test_intake_reach E2 and test_intake_leak K2 through lint;
 T17.3 is test_intake.py's POINTS totality check.)
Seen RED (each mutation applied by hand, the test run, the mutation reverted):
 - T17.1: the MEASURED plant's control written "SET" (the check's own SET run): FAST_VALUE_REPEATED; POINTS' MEASURED rows keyed by the fast
   value (r[0]) in place of the ordinal: the MEASURED run FAILS (FAST_VALUE_REPEATED).
 - T17.4: census `kinds` taken over every curve in place of the refused ones: the counts differ (FAIL); intake_names.exits returning []:
   the exit check FAILS.
 - T17.2: intake_choices.POINTED's MEASURED row made True: test_intake_reach E2 FAILS (both plants, and MEASURED_KNOB_HAS_NO_POINTS live,
   never reached).
 - T17.5: POINTS' MEASURED rows dropping the first row (rows[1:]): the census labels differ (FAIL). S10's records do NOT differ under that
   mutation: the terminal re-reads each curve's rows (intake_terminal, CURVES), not the census points (plan error, reported).
"""
import json
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path[:0] = [str(ROOT / "cc"), str(ROOT / "tests")]
import intake  # noqa: E402
import intake_synth  # noqa: E402
from intake_plant import MEASURED, outcome, per_file, run  # noqa: E402

bad = []


def check(name, ok, why=""):
    print(("ok   " if ok else "FAIL ") + name + ("" if ok else f": {why}"))
    if not ok:
        bad.append(name)


T = intake.tables(ROOT)
ACQ = lambda t: t.replace('row_order = "ASCENDING"', 'row_order = "ACQUISITION"', 1)   # rows in acquisition order, direction UNORDERED

with tempfile.TemporaryDirectory() as tmp:
    tmp = Path(tmp)
    banks = tmp / "banks"
    intake_synth.write(banks / "pf", tmp / "pf-TRUTH", "pf", 1, 9)
    m = json.loads((banks / "pf" / "MANIFEST.json").read_text())
    first = m["files"][0]["name"]
    n = iter(range(1000))

    def bank(edit):
        """A copy of bank pf whose first curve file's data rows are edit(rows) (each row a line, as written)."""
        name = f"b{next(n)}"
        shutil.copytree(banks / "pf", banks / name)
        head, *rows = (banks / name / first).read_text().splitlines()
        (banks / name / first).write_text("\n".join([head] + edit(rows)) + "\n")
        return name

    def go(name, edit=lambda t: t):
        ident = f"d{next(n)}"
        return run(T, tmp, ident, edit(per_file(m, ident).replace("<long-test>/pf", f"<long-test>/{name}")))

    # ---- T17.1: one revisit (the first row again at the end), rows in acquisition order
    rv = bank(lambda rs: rs + rs[:1])
    meas, setk = go(rv, lambda t: MEASURED(ACQ(t))), go(rv, ACQ)
    check("T17.1 control MEASURED, one revisited fast value: S5 passes and S10 passes", (outcome(meas, "S5")[0], meas["S10"].mark) == ("PASS", intake.Mark.PASSED),
          f"{outcome(meas, 'S5')[0]} {meas['S10'].mark}")
    check("T17.1 the same declaration with control SET is FAST_VALUE_REPEATED at S5", outcome(setk, "S5")[0] == "FAST_VALUE_REPEATED", outcome(setk, "S5")[0])

    # ---- T17.4: x0 x1 x1 x2 .. x(n-3) x(n-1) x(n-4) x(n-2): a consecutive pair (x1), one revisit (x(n-4)), up / down / up
    k4 = bank(lambda rs: rs[:2] + rs[1:-2] + rs[-1:] + [rs[-4], rs[-2]])
    said = str(go(k4, ACQ)["S5"].result.evidence)
    counts = "curves refused = 1; of curves = 9; consecutive runs = 1; longest run = 2; values revisited = 1; monotone runs = 3"
    check("T17.4 FAST_VALUE_REPEATED's Detail counts the refused curves out of all, then the repeat kinds", said.endswith(counts), said)
    check("T17.4 (A30) it names the exit of each kind found: SAME_FAST_VALUE for the consecutive run, MEASURED or SPLIT_ROWS for the revisit",
          "consecutive repeats:" in said and "SAME_FAST_VALUE" in said and "non-consecutive repeats" in said and "SPLIT_ROWS" in said, said)
    check("T17.4 with the file name and the counts taken out, the Detail holds no digit (no value)",
          not any(ch.isdigit() for ch in said.replace(counts, "").replace(first, "")), said)

    # ---- T17.5: MAX_MEASURED and ARGMAX_FAST as the PRIMARY projection, under SET and MEASURED, on the bank with no repeat
    argmax = lambda t: t.replace('bias = "MAX_MEASURED"', 'bias = "ARGMAX_FAST"', 1)
    same = {}
    for what, proj in (("MAX_MEASURED", lambda t: t), ("ARGMAX_FAST", argmax)):
        s, ms = go("pf", proj), go("pf", lambda t: MEASURED(proj(t)))
        rec = lambda out: [h.record() for h in out["S10"].result.evidence.columns]
        same[what] = (s["S10"].mark is intake.Mark.PASSED and rec(s) == rec(ms) and rec(s) != [], outcome(s, "S5")[1].label == outcome(ms, "S5")[1].label)
    check("T17.5 MAX_MEASURED and ARGMAX_FAST: S10's records and the census label are the same under MEASURED as under SET",
          same == {"MAX_MEASURED": (True, True), "ARGMAX_FAST": (True, True)}, str(same))

print("test_intake_loop2: " + ("FAILED " + "; ".join(bad) if bad else "all passed"))
sys.exit(1 if bad else 0)
