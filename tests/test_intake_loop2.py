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
import subprocess
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

# ---- A18-A22: the converter, peek and the seal (planted raw files under <tmp>/cc-datasets; rooted tables)
import contextlib  # noqa: E402
import importlib.util  # noqa: E402
import io  # noqa: E402
import re  # noqa: E402
import time  # noqa: E402
import intake_convert as ic  # noqa: E402
import intake_seal  # noqa: E402
import intake_bytes  # noqa: E402
import intake_blind as blind  # noqa: E402
from intake_plant import conversion, rooted, workbook  # noqa: E402

CT = ic.ctables()
HAS_XLSX = importlib.util.find_spec("openpyxl") is not None
code = lambda got: {True: lambda: got.reason, False: lambda: "PASS"}[hasattr(got, "reason")]()

with tempfile.TemporaryDirectory() as tmp:
    tmp = Path(tmp)
    RT = rooted(T, tmp)
    n = iter(range(1000))

    def conv(raws, files):
        name = f"c{next(n)}"
        raw, d = tmp / "cc-datasets" / name / "raw", tmp / "declarations" / name
        raw.mkdir(parents=True)
        d.mkdir(parents=True)
        [(raw / f).write_bytes(b) for f, b in raws.items()]
        (d / "CONVERSION.toml").write_text(conversion(f"<cc-datasets>/{name}/raw", f"<cc-banks>/{name}/bank", files))
        return ic.convert(tmp, name, RT, CT), tmp / "cc-banks" / name / "bank", name

    def peek(ident, rel, *args):
        (tmp / "declarations" / ident).mkdir(parents=True, exist_ok=True)
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            rc = ic.peek_cli(tmp, ident, [rel, *args], RT)
        return rc, out.getvalue()

    # ---- T18.1 / T18.2: N rows each dropped by DROP_ROWS_NOT_NUMERIC; verify classifies each named cell once
    N = 3000
    body = "".join(f"1.{k:04d},0.5\n1.{k:04d}5,n/a\n" for k in range(N)).encode()
    got, bank, name = conv({"a.csv": b"T,C\n" + body}, [("a.csv", "a.csv", '{op = "DROP_ROWS_NOT_NUMERIC", columns = ["C"]}')])
    cells = sum(len(r) for o in json.loads((bank / ic.MANIFEST).read_text())["outputs"] for r in o["cells"])

    class Counting:
        """ic.NUMBER with its fullmatch calls counted."""
        calls = 0

        def fullmatch(self, text):
            Counting.calls += 1
            return intake.intake_names.NUMBER.fullmatch(text) if hasattr(intake, "intake_names") else re.fullmatch(r"[-+]?(\d+(\.\d*)?|\.\d+)([eE][-+]?\d+)?", text)
    real, ic.NUMBER = ic.NUMBER, Counting()
    t0 = time.monotonic()
    v = ic.verified(tmp, name, RT, CT)
    spent = time.monotonic() - t0
    ic.NUMBER = real
    check("T18.1 (A18) verify of N dropped rows passes and classifies at most 2 cells + N texts (_same: each output cell and its source; each not_numeric cell once, not once per row)",
          code(got) == "PASS" and code(v) == "PASS" and Counting.calls <= 2 * cells + N, f"{code(got)} {code(v)} matches = {Counting.calls}; bound = {2 * cells + N}")
    check("T18.2 (A18) verify of 6000 rows (half dropped) takes under 5 s", spent < 5, f"{spent:.1f} s")

    # ---- T18.4: a manifest unit with no not_numeric list is CONVERSION_CHAIN_BROKEN (no .get default)
    man = json.loads((bank / ic.MANIFEST).read_text())
    del man["units"][0]["not_numeric"]
    (bank / ic.MANIFEST).write_text(json.dumps(man))
    v = ic.verified(tmp, name, RT, CT)
    check("T18.4 (A18) a manifest unit without not_numeric: verify is CONVERSION_CHAIN_BROKEN", code(v) == "CONVERSION_CHAIN_BROKEN", code(v))

    # ---- T19.1 / T19.2: peek names its file by the root-named path; the id names only declarations/<id>/
    got, _, a = conv({"f.csv": b"T,C\n1.5,0.25\n"}, [("f.csv", "f.csv", "")])
    rc, said = peek(f"{a}-r3", f"<cc-datasets>/{a}/raw/f.csv")
    check("T19.1 (A19) a declaration a-r3 peeks <cc-datasets>/a/raw/f.csv: the file is read", rc == 0 and "line 1: 2 text names" in said, said)
    outside = [f"<cc-banks>/{a}/bank/f.csv", str(tmp / "cc-datasets" / a / "raw" / "f.csv"), f"<cc-datasets>/{a}/raw/../raw/f.csv", "f.csv"]
    said = [peek(a, rel)[1] for rel in outside]
    check("T19.2 (A19) another root, an absolute path, a '..' part and a bare name are each SOURCE_FILE_ABSENT",
          all("SOURCE_FILE_ABSENT" in x for x in said), "\n".join(said))

    # ---- T20.1 / T20.2: the seal lists the universe the declared root names, DEPOSIT and CONVERTED
    banks = tmp / "banks"
    intake_synth.write(banks / "pf", tmp / "pf-TRUTH", "pf", 1, 9)
    m = json.loads((banks / "pf" / "MANIFEST.json").read_text())
    curves = {f["name"]: (banks / "pf" / f["name"]).read_bytes() for f in m["files"]}
    got, _, cv = conv(curves, [(f, f, "") for f in curves])
    convert_decl = lambda t: re.sub(r'root = "[^"]*"', f'root = "<cc-banks>/{cv}/bank"', t.replace('kind = "DEPOSIT"', f'kind = "CONVERTED"\nconverted_from = "<cc-datasets>/{cv}/raw"', 1)
                                    .replace('file = "MANIFEST.json"', 'file = "CONVERSION-MANIFEST.json"', 1), count=1)
    sealed = {}
    for mode, edit in (("DEPOSIT", lambda t: t), ("CONVERTED", convert_decl)):
        ident = f"s{next(n)}"
        text = edit(per_file(m, ident))
        d = tmp / "declarations" / ident
        d.mkdir(parents=True)
        (d / "intake.toml").write_text(text)
        (d / "transducer.toml").write_text("# planted\n")
        decl = blind.format_stage(text, [], T).evidence
        minted = intake_seal.mint(decl, d, {"author": "t", "author_kind": intake_seal.AUTHOR_KIND["ai-draft"], "confirmed_by": ""}, ROOT, RT)
        at = intake_bytes.located(decl.data["source"]["root"], RT["roots"])
        rec = {True: lambda: json.loads((d / "SEAL.json").read_text())["universe"]["listing"], False: lambda: None}[(d / "SEAL.json").is_file()]()
        sealed[mode] = (code(minted), rec == intake_seal.listing(at, decl.data["source"]["universe"]) and rec != [])
    check("T20.1 (A20) the seal's listing is the listing of the directory the declared root names (DEPOSIT and CONVERTED)",
          sealed == {"DEPOSIT": ("PASS", True), "CONVERTED": ("PASS", True)}, str(sealed))
    r = subprocess.run([str(ROOT / "bin" / "cc"), "intake", "seal", "dial1118-s1-v4", "--universe", str(tmp), "--author", "x", "--as", "human", "--unconfirmed"],
                       capture_output=True, text=True, cwd=ROOT)
    check("T20.2 (A20) seal --universe X is a usage refusal (exit 1, the usage names no --universe) before the seal is tried (the example is sealed: not ALREADY_SEALED)",
          r.returncode != 0 and "no --universe" in r.stdout + r.stderr and "ALREADY_SEALED" not in r.stdout + r.stderr, r.stdout + r.stderr)

    # ---- T21: a sheet by position (SHEET_TO_CSV sheet = 2) is typed; with openpyxl it is the same sheet as its name
    book = workbook({"notes": [["x"]], "data": [["T", "C"], [1.5, 0.25]]})
    by_pos, _, _ = conv({"b.xlsx": book}, [("b.xlsx", "b.csv", '{op = "SHEET_TO_CSV", sheet = 2}')])
    by_name, bn, _ = conv({"b.xlsx": book}, [("b.xlsx", "b.csv", '{op = "SHEET_TO_CSV", sheet = "data"}')])
    check("T21.1 (A21) SHEET_TO_CSV sheet = 2 is admitted (a position): it converts as sheet = \"data\" (openpyxl) or is XLSX_READER_ABSENT (none)",
          {True: lambda: code(by_pos) == code(by_name) == "PASS", False: lambda: code(by_pos) == code(by_name) == "XLSX_READER_ABSENT"}[HAS_XLSX](), f"{code(by_pos)} {code(by_name)}")
    rc, said = peek("xb", "<cc-datasets>/" + [p.parent.parent.name for p in (tmp / "cc-datasets").glob("*/raw/b.xlsx")][0] + "/raw/b.xlsx", "--sheet", "2")
    check("T21.2 (A21) peek --sheet 2 reads the second sheet (openpyxl), or is XLSX_READER_ABSENT (none)",
          {True: lambda: rc == 0 and "line 1: 2 text names" in said, False: lambda: "XLSX_READER_ABSENT" in said}[HAS_XLSX](), said)
    print({True: "", False: "  NOT REACHED HERE: T21's xlsx reads (no openpyxl); run on the data host"}[HAS_XLSX])

    # ---- T22: peek says which encodings decode the file, and --encoding decodes the head lines
    got, _, lt = conv({"l.csv": "T,µ\n1.5,0.25\n".encode("latin-1")}, [("l.csv", "l.csv", '{op = "DECODE", encoding = "latin-1"}')])
    rc, said = peek(lt, f"<cc-datasets>/{lt}/raw/l.csv")
    line = [x for x in said.splitlines() if "decodes as:" in x] + [""]
    check("T22.1 (A22) peek on a latin-1 file prints 'decodes as: ...latin-1...; not as: utf-8, utf-8-sig...' (words of DECODE's alphabet only)",
          re.search(r"decodes as: [^;]*latin-1", line[0]) is not None and re.search(r"not as: [^;]*\butf-8\b", line[0]) is not None, said)
    rc2, said2 = peek(lt, f"<cc-datasets>/{lt}/raw/l.csv", "--encoding", "latin-1")
    check("T22.1 (A22) --encoding latin-1 decodes the head line (no replacement character)", rc2 == 0 and "\ufffd" not in said2 and "\ufffd" in said, said2)
    rc3, said3 = peek(lt, f"<cc-datasets>/{lt}/raw/l.csv", "--encoding", "koi8-r")
    check("T22.2 (A22) --encoding outside DECODE's alphabet is VALUE_NOT_LISTED", rc3 == 1 and "VALUE_NOT_LISTED" in said3, said3)

    # ---- A29: NAMES_LINE WRITE over rows of another width is NAMES_COUNT_MISMATCH, never a partial header
    two = '{op = "NAMES_LINE", rule = {kind = "WRITE", names = ["T", "C"]}}'
    got, _, _ = conv({"w.csv": b"1.5,0.25,7\n1.6,0.5,8\n"}, [("w.csv", "w.csv", two)])
    check("T29.1 (A29) 2 names written over a 3-column file: NAMES_COUNT_MISMATCH", code(got) == "NAMES_COUNT_MISMATCH", str(got))
    got, _, _ = conv({"w.csv": b"1.5,0.25\n1.6,0.5\n"}, [("w.csv", "w.csv", two)])
    check("T29.2 (A29) 2 names written over a 2-column file: PASS", code(got) == "PASS", str(got))

    check("T29.3 / T32.4 (A29, A32) WIDTH is total over NAMES_LINE's kinds and COLLAPSES over the delimiters (and NONE); WHITESPACE alone collapses",
          set(ic.WIDTH) == set(ic.NAMES) and set(ic.COLLAPSES) == set(ic.SPLIT) | {"NONE"} and {k for k, v in ic.COLLAPSES.items() if v} == {"WHITESPACE"},
          f"{sorted(ic.WIDTH)} {sorted(ic.COLLAPSES)}")

    # ---- A31: the convert summary prints a column name through the masking (a numeral in a name as #)
    hd = f"h{next(n)}"
    (tmp / "cc-datasets" / hd / "raw").mkdir(parents=True)
    (tmp / "cc-datasets" / hd / "raw" / "h.csv").write_bytes(b"T,C at 7357.25 K\n1.5,0.25\n")
    (tmp / "declarations" / hd).mkdir(parents=True)
    (tmp / "declarations" / hd / "CONVERSION.toml").write_text(conversion(f"<cc-datasets>/{hd}/raw", f"<cc-banks>/{hd}/bank", [("h.csv", "h.csv", "")]))
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        rc = ic.convert_cli(tmp, hd, [], RT)
    said = out.getvalue()
    check("T31.1 (A31) bin/cc intake convert's summary does not print the value a names-line cell carries, and names the column masked",
          rc == 0 and "7357" not in said and "'C at # K'" in said, said)

    # ---- A32: DELIMITER WHITESPACE collapses an empty cell, so a row narrower than the names line is EMPTY_CELL_UNDER_WHITESPACE
    ws = '{op = "DELIMITER", from = "WHITESPACE"}'
    got, _, _ = conv({"s.txt": b"T C D\n1.5 0.25 7\n1.6 0.5\n"}, [("s.txt", "s.csv", ws)])
    check("T32.1 (A32) WHITESPACE, a row narrower than the names line: EMPTY_CELL_UNDER_WHITESPACE naming TAB and COMMA",
          code(got) == "EMPTY_CELL_UNDER_WHITESPACE" and "TAB" in str(got.evidence) and "COMMA" in str(got.evidence), str(got))
    got, _, _ = conv({"s.txt": b"T C D\n1.5 0.25 7\n1.6 0.5 8\n"}, [("s.txt", "s.csv", ws)])
    check("T32.2 (A32) WHITESPACE, every row as wide as the names line: PASS", code(got) == "PASS", str(got))
    got, _, _ = conv({"s.csv": b"T,C,D\n1.5,0.25,7\n1.6,0.5,\n"}, [("s.csv", "s.csv", "")])
    check("T32.3 (A32) the same row under COMMA keeps its empty cell (no refusal of this kind)", code(got) != "EMPTY_CELL_UNDER_WHITESPACE", str(got))

print("test_intake_loop2: " + ("FAILED " + "; ".join(bad) if bad else "all passed"))
sys.exit(1 if bad else 0)
