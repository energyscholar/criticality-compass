"""test_intake_leak - plan 1160 P0: no output of the intake carries a data value. Planted inputs only (no real data).
 K1. Two sentinel banks, a PER_FILE bank (five csv-curve-v1 files) and a LONG_TABLE bank (one table-curve-v1 file), whose every numeric cell,
     and every declared slow value, is drawn from a sentinel alphabet: decimal text that begins "-7357.", so each of its printed forms (the raw
     text, repr(float), f"{v:g}", f"{v:.6g}") holds "-7357." or rounds to a string no other output holds. Both pass S5 CENSUS.
 K2. Every live reason row of intake/STAGES.toml (and every live S4 reader reason) is planted on those banks, through the commands a declarer
     runs: `bin/cc intake lint | seal | run` (intake.cli, in process, on a copy of the Compass whose ROOTS.toml names the banks). The plant
     table is total: the codes reached are exactly the live rows (with the machine's NOT REACHED xlsx rows, as test_intake_reach). Plan 1160
     P0 said "reuse test_intake_reach.PLANTS"; that table is built inside a temporary directory over the synthetic bank and is not importable,
     so this test carries its own plant per row over the sentinel banks, with the same totality check.
 K3. No byte of intake-report.md, SEAL.json, seal.log, access.log, stdout or stderr of any plant holds any sentinel cell in any of its forms.
 K4. The report's census section lists the curves by ordinal and file name.
Seen RED (each mutation applied by hand, the test run, the mutation reverted):
 - the fast-span summary reinstated in cc/intake_data.py Census.summary (`{x.fast} span [{lo:g}, {hi:g}]`): K3 FAILS on the two PASS runs;
 - _blocks' where reinstated as f"{f.name} block {i} ({g.columns[-1]} = {h:g})": K3 FAILS (the LONG_TABLE census section and CURVE_REPEATED);
 - _resolve's COLUMN_NAME_ABSENT detail printing the names line (f"... {names}"): K3 FAILS on the numeric-names plant;
 - Census.listing printing the slow value instead of the where: K4 and K3 FAIL;
 - (1160 P2) intake_names.masked returning the stated text unmasked: K3 FAILS on the UNIT_DIFFERS plant whose unit holds a sentinel."""
import contextlib
import hashlib
import io
import re
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path[:0] = [str(ROOT / "cc"), str(ROOT / "tests")]
import importlib.util  # noqa: E402

import intake  # noqa: E402
import intake_blind as blind  # noqa: E402
import intake_synth  # noqa: E402
from intake_plant import long_table, per_file, slow_source, write_long, xlsx  # noqa: E402

bad = []


def check(name, ok, why=""):
    print(("ok   " if ok else "FAIL ") + name + ("" if ok else f": {why}"))
    if not ok:
        bad.append(name)


HAS_XLSX = importlib.util.find_spec("openpyxl") is not None
K = 5   # curves
SENT = re.compile(rb"-7357\.\d+")   # a sentinel cell as written in a bank file or a declaration
cell = lambda k, j, r: f"-7357.{8 - k}{99 - j:02d}{r}"   # curve k, point j, role r (1 fast, 2 measured, 3 sigma): fast ascends in j; no rounding carry
slow = lambda k: f"-7357.{k + 1}5"
CURVES = [(slow(k), [f"{cell(k, j, 1)},{cell(k, j, 2)},{cell(k, j, 3)}" for j in range(6 + k)]) for k in range(K)]
M = {"seed": 7357, "reader": "csv-curve-v1", "pattern": "curve_{index:03d}.csv", "columns": ["T", "C", "sigma"], "replicate": "NONE",
     "slow": {"name": "h", "unit": "dimensionless"}, "fast": {"name": "T", "unit": "dimensionless", "column": "T"},
     "measured": {"name": "C", "unit": "dimensionless", "column": "C"}, "files": [{"name": f"curve_{i:03d}.csv", "h": float(h)} for i, (h, _) in enumerate(CURVES)],
     "generator": {"path": "cc/intake_synth.py", "sha256": hashlib.sha256((ROOT / "cc" / "intake_synth.py").read_bytes()).hexdigest()}}
TRANS = intake_synth.declare(M, "x", "pf")[2]


def forms(text):
    """Every printed form of one sentinel cell: the raw text, repr(float), f"{v:g}", f"{v:.6g}"."""
    v = float(text)
    return {text, repr(v), f"{v:g}", f"{v:.6g}"}


with tempfile.TemporaryDirectory() as tmp:
    tmp = Path(tmp)
    w, banks = tmp / "cc", tmp / "banks"
    shutil.copytree(ROOT, w, ignore=shutil.ignore_patterns(".git", "__pycache__", "results", "benchmark", "fixtures", "data", "scratch"))
    with open(w / "intake" / "ROOTS.toml", "a") as f:
        f.write(f'"<leak>" = "{banks}"   # test_intake_leak: the sentinel banks\n')
    n = iter(range(1000))

    def pf_bank(edit=lambda b: None, curves=CURVES):
        name = f"pf{next(n)}"
        (banks / name).mkdir(parents=True)
        for i, (_, rows) in enumerate(curves):
            (banks / name / f"curve_{i:03d}.csv").write_text("T,C,sigma\n" + "".join(r + "\n" for r in rows))
        (banks / name / "MANIFEST.json").write_text('{"planted": "test_intake_leak"}\n')   # plan 1160 P1: the file the declaration excludes (the seal partitions the universe)
        edit(banks / name)
        return name

    def lt_bank(blocks=CURVES, raw=None, **k):
        name = f"lt{next(n)}"
        (banks / name).mkdir(parents=True)
        write_long(banks / name, blocks, **k)
        {True: lambda: None, False: lambda: (banks / name / "bank.csv").write_bytes(raw)}[raw is None]()
        return name

    def pf(bank, edit=lambda t: t):
        return lambda ident: edit(per_file(M, ident).replace("<long-test>/pf", f"<leak>/{bank}"))

    def lt(bank, edit=lambda t: t, **k):
        return lambda ident: edit(long_table(M, ident, **k).replace("<long-test>/pf", f"<leak>/{bank}"))

    def cli(*args):
        """One `bin/cc intake ...` command in process: (stdout + stderr)."""
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            intake.cli(w, list(args))
        return out.getvalue() + err.getvalue()

    SEAL = lambda u: ("seal", "--universe", str(u), "--author", "plan 1160 leak test", "--as", "ai-draft", "--unconfirmed")

    def plant(text, bank, steps, trans=TRANS):
        """Write the declaration, run `steps` (each a tuple of CLI words after the id, or a function of the bank dir), and return (its code,
        everything it printed and wrote). Its code is the first REFUSE code printed (the reader reason for READER_REFUSED), else PASS."""
        ident = f"d{next(n)}"
        d = w / "declarations" / ident
        d.mkdir(parents=True)
        (d / "intake.toml").write_text(text(ident))
        (d / "transducer.toml").write_text(trans.replace('id = "x"', f'id = "{ident}"'))
        said = "".join({True: lambda s=s: cli(s[0], ident, *s[1:]), False: lambda s=s: (s(banks / bank), "")[1]}[isinstance(s, tuple)]() for s in steps)
        wrote = "".join((d / x).read_text() for x in ("intake-report.md", "SEAL.json", "seal.log", "access.log") if (d / x).is_file())
        m = re.search(r"REFUSE (\w+)\. [^\n]*?Detail: (?:[^;\n]*; )?(\w*)", said)
        code = {True: lambda: "PASS", False: lambda: {True: lambda: m[2], False: lambda: m[1]}[m[1] == "READER_REFUSED"]()}[m is None]()
        return code, said + wrote, ident

    PF, LT = pf_bank(), lt_bank()

    def convert(text, root):
        """(1160 P1) [source] kind CONVERTED, its root `root`, converted_from a deposit name."""
        return re.sub(r'root = "[^"]*"', f'root = "{root}"', text.replace('kind = "DEPOSIT"', 'kind = "CONVERTED"\nconverted_from = "<cc-datasets>/leak/raw"', 1), count=1)

    def keyed(line):
        """(1160 P1) A bank edit: each curve file i gets `line(i)` above its names line (a FILE_KEY header line)."""
        return lambda b: [(b / f"curve_{i:03d}.csv").write_text(line(i) + (b / f"curve_{i:03d}.csv").read_text()) for i in range(K)]
    full = lambda bank: (("lint",), SEAL(banks / bank), ("run",))
    unsealed = (("lint",), ("run",))
    append = lambda name, text: lambda b: (b / name).write_text((b / name).read_text() + text)
    asc = lambda t: t.replace('row_order = "ASCENDING"', 'row_order = "ACQUISITION"')
    nu = 'kind = "NAMES_UNITS"\nrows = 2\nnames = 1\nunits = 2'
    xl = lambda t: t.replace('[reader.format]\nkind = "COMMA"', '[reader.format]\nkind = "XLSX"\nsheet = "data"')
    rows = [[float(x) for x in r.split(",")] + [float(h)] for h, rs in CURVES for r in rs]
    numeric_names = ("T,C,sigma,h\n" + "".join(f"{r},{h}\n" for h, rs in CURVES for r in rs)).replace("T,C,sigma,h", "h," + ",".join(cell(0, j, 1) for j in range(3)), 1).encode()
    S0 = lambda edit, trans=TRANS: (pf(PF, edit), PF, full(PF), trans)
    PLANTS = [
        ("PASS", "the PER_FILE sentinel bank, sealed", (pf(PF), PF, full(PF))),
        ("PASS", "the LONG_TABLE sentinel bank, sealed", (lt(LT), LT, full(LT))),
        # S0 FORMAT
        ("TOML_INVALID", "not TOML", S0(lambda t: t + "\n[[[")),
        ("SCHEMA_UNSUPPORTED", "schema = 4 (1160: was schema = 3, now the format)", S0(lambda t: t.replace("schema = 3", "schema = 4", 1))),
        ("COMMENT_PREFIX_EMPTY", "(1160) comment = [\"\"] on table-curve-v1", (lt(LT, lambda t: t.replace('comment = ["#"]', 'comment = [""]', 1)), LT, full(LT))),
        ("ROOT_NOT_UNDER_CC_BANKS", "(1160) a CONVERTED source whose root is the deposit's", S0(lambda t: convert(t, f"<leak>/{PF}"))),
        # S1 CHOICES
        ("SLOW_VALUES_NOT_ONE_PER_FILE", "(1160) one LISTED value fewer than the files", S0(lambda t: re.sub(r'values = \["[^"]*", ', 'values = [', t, count=1))),
        ("FIELD_MISSING", "[knobs.fast] deleted", S0(lambda t: re.sub(r"(?s)\[knobs\.fast\].*?(?=\[measured\])", "", t))),
        ("FIELD_UNKNOWN", "a field the format does not define", S0(lambda t: t.replace("[intake]\n", '[intake]\ncolour = "red"\n'))),
        ("FIELD_TYPE_WRONG", "a column key that is a boolean", S0(lambda t: t.replace('key = "C"', "key = true", 1))),
        ("VALUE_NOT_LISTED", "layout BY_ROW", S0(lambda t: t.replace('layout = "PER_FILE"', 'layout = "BY_ROW"'))),
        ("VALUE_STILL_TODO", "intake.mode TODO", S0(lambda t: t.replace('mode = "PROSPECTIVE"', 'mode = "TODO"', 1))),
        ("BIAS_KEY_UNDECLARED", "a free-text bias", S0(lambda t: t.replace('bias = "MAX_MEASURED"', 'bias = "the largest C"'))),
        ("FIELD_IS_STAMPED", "a typed timestamp", S0(lambda t: t.replace("[intake]\n", '[intake]\nsealed_at = "2026-10-18T09:00:00Z"\n'))),
        ("FIELD_IS_DERIVED", "a derived field typed", S0(lambda t: t.replace("[acquisition]\n", "[acquisition]\ncorrelated = true\n"))),
        ("STEP_IS_INTERPOLATION", "an interpolation bridge", S0(lambda t: t.replace('template = "CHAIN_SLOW"', 'template = "INTERPOLATE"'))),
        ("BRIDGE_NONE_FITS", "no bridge fits", S0(lambda t: t.replace('template = "CHAIN_SLOW"', 'template = "NONE_FITS"'))),
        ("BASIS_NOT_METADATA", "a figure in the basis", S0(lambda t: re.sub(r'class = "[A-Z_]+"', 'class = "FIGURE"', t, count=1))),
        ("TRANSDUCER_FILE_REFUSED", "a transducer.toml with no [reduction]", S0(lambda t: t, re.sub(r"(?s)\[reduction\].*?(?=\[interval\])", "", TRANS))),
        # S2 SEAL
        ("ALREADY_SEALED", "a second seal", (pf(PF), PF, (SEAL(banks / PF), SEAL(banks / PF)))),
        ("UNIVERSE_ROOT_ABSENT", "a universe that is no directory", (pf(PF), PF, (SEAL(tmp / "nowhere"),))),
        ("SELECTION_OUTSIDE_UNIVERSE", "an empty universe", (pf(PF), PF, (lambda b: (tmp / "empty").mkdir(), SEAL(tmp / "empty")))),
        ("SELECTION_DUPLICATE", "(1160) a file named twice in files", (pf(PF, lambda t: t.replace("files = [", 'files = ["curve_002.csv", ', 1).replace("values = [", f'values = ["{slow(2)}", ', 1)), PF, full(PF))),
        ("UNIVERSE_NOT_PARTITIONED", "(1160) a universe file in no part", (pf(UP := pf_bank(lambda b: (b / "notes.txt").write_text("planted\n"))), UP, full(UP))),
        # S3 SOURCE_INTEGRITY
        ("ROOT_UNRESOLVED", "a root name ROOTS.toml does not hold", (pf(PF, lambda t: t.replace("<leak>/", "<no-such-root>/")), PF, full(PF))),
        ("PATH_OUTSIDE_ROOT", "(1160) a files entry naming a file of another bank (unsealed)", (pf(PO := pf_bank(), lambda t: t.replace('files = ["curve_000.csv"', f'files = ["../{PF}/curve_000.csv"', 1)), PO, unsealed)),
        ("PATH_ON_TRUTH_SIDE", "(1160) truth_side names a selected file (unsealed)", (pf(PF, lambda t: t.replace('truth_side = ["truth.json"]', 'truth_side = ["truth.json", "curve_003.csv"]', 1)), PF, unsealed)),
        ("PATH_NOT_A_FILE", "a selected file deleted (unsealed: the seal would refuse it; 1160: was PATH_NOT_ADMITTED)", (pf(pf_bank(lambda b: (b / "curve_003.csv").unlink())), PF, unsealed)),
        ("PIN_MISMATCH", "a file's bytes changed after its first logged read (unsealed: the seal would see the size)",
         (pf(PIN := pf_bank()), PIN, unsealed + (append("curve_002.csv", f"{cell(2, 50, 1)},{cell(2, 50, 2)},{cell(2, 50, 3)}\n"), ("run",)))),
        ("UNIVERSE_CHANGED", "a file added after the seal", (pf(UC := pf_bank()), UC, full(UC)[:2] + (lambda b: (b / "late.csv").write_text("T,C,sigma\n"), ("run",)))),
        ("CONVERSION_NOT_LIVE", "(1160) a CONVERTED source (no conversion body until P3)", (pf(PF, lambda t: convert(t, f"<cc-banks>/{PF}/bank")), PF, unsealed)),
        # S4 SHAPE
        ("READER_NOT_LIVE", "reader P1", (pf(PF, lambda t: t.replace('name = "csv-curve-v1"', 'name = "P1"')), PF, full(PF))),
        ("COLUMNS_DIFFER", "csv-curve-v1, the first file's names line holds a NUMERIC name",
         (pf(CD := pf_bank(lambda b: (b / "curve_000.csv").write_text((b / "curve_000.csv").read_text().replace("T,C,sigma", f"T,{cell(0, 0, 2)},sigma", 1)))), CD, full(CD))),
        ("UNIT_DIFFERS", "a NAMES_UNITS header stating T in K", (lt(UD := lt_bank(head="T,C,sigma,h\nK,dimensionless,dimensionless,dimensionless\n"), header=nu), UD, full(UD))),
        ("UNIT_DIFFERS", "(1160 P2) a NAMES_UNITS header whose unit of T holds a sentinel number ('K -7357.15'): the stated unit prints masked",
         (lt(US := lt_bank(head=f"T,C,sigma,h\nK {slow(0)},dimensionless,dimensionless,dimensionless\n"), header=nu), US, full(US))),
        ("ROW_ORDER_DIFFERS", "one swapped pair inside block 5",
         (lt(RO := lt_bank([(h, rs[:3] + [rs[4], rs[3]] + rs[5:]) if i == 4 else (h, rs) for i, (h, rs) in enumerate(CURVES)])), RO, full(RO))),
        # S5 CENSUS
        ("FILE_DIFFERS_FROM_FIRST", "a later file's header T,C,err",
         (pf(FD := pf_bank(lambda b: (b / "curve_004.csv").write_text((b / "curve_004.csv").read_text().replace("T,C,sigma", "T,C,err", 1)))), FD, full(FD))),
        ("CURVE_REPEATED", "a slow value in two non-adjacent blocks", (lt(CR := lt_bank(CURVES + CURVES[:1])), CR, full(CR))),
        ("FAST_VALUE_REPEATED", "two adjacent runs of one slow value", (lt(FV := lt_bank(CURVES[:1] + CURVES), asc), FV, full(FV))),
        ("SLOW_KEY_UNRESOLVED", "(1160) FILE_KEY h, each key line's value a sentinel followed by 'x'",
         (pf(SK := pf_bank(keyed(lambda i: f"h,{slow(i)}x\n")), lambda t: slow_source(t, "FILE_KEY")), SK, full(SK))),
        ("PASS", "(1160) FILE_KEY h on the PER_FILE sentinel bank, sealed", (pf(FK := pf_bank(keyed(lambda i: f"h,{slow(i)}\n")), lambda t: slow_source(t, "FILE_KEY")), FK, full(FK))),
        ("PASS", "(1160) slow source NONE on the PER_FILE sentinel bank, sealed", (pf(PF, lambda t: slow_source(t, "NONE")), PF, full(PF))),
        ("REPLICATE_KEY_UNRESOLVED", "a FILE identity on a LONG_TABLE", (lt(RK := lt_bank(CURVES + CURVES[:1]), lambda t: t.replace('identity = "NONE"', 'identity = "FILE"')), RK, full(RK))),
        ("ACQUISITION_ORDER_DIFFERS", "ascending rows in acquisition order, declared DESCENDING",
         (lt(AO := lt_bank(), lambda t: asc(t).replace('direction = "UNORDERED"', 'direction = "DESCENDING"')), AO, full(AO))),
        # S4 reader reasons (table-curve-v1), each the detail of READER_REFUSED
        ("NOT_UTF8", "a byte that is not UTF-8", (lt(B1 := lt_bank(raw=f"T,C,sigma,h\n{cell(0, 0, 1)},{cell(0, 0, 2)}\xff,{cell(0, 0, 3)},{slow(0)}\n".encode("latin-1"))), B1, full(B1))),
        ("HEADER_LINE_ABSENT", "two header lines declared, one present", (lt(B2 := lt_bank(raw=b"T,C,sigma,h\n"), header=nu), B2, full(B2))),
        ("NO_DATA_ROW", "a header and no data row", (lt(B3 := lt_bank(raw=b"# nothing yet\nT,C,sigma,h\n")), B3, full(B3))),
        ("ROW_WIDTH_DIFFERS", "a short row", (lt(B4 := lt_bank(raw=f"T,C,sigma,h\n{cell(0, 0, 1)},{cell(0, 0, 2)},{cell(0, 0, 3)},{slow(0)}\n{cell(0, 1, 1)},{cell(0, 1, 2)},{cell(0, 1, 3)}\n".encode())), B4, full(B4))),
        ("COLUMN_NAME_ABSENT", "a names line whose names are values (a WIDE table: F3)", (lt(B5 := lt_bank(raw=numeric_names)), B5, full(B5))),
        ("COLUMN_NAME_AMBIGUOUS", "two columns named h", (lt(B6 := lt_bank(raw=f"T,C,sigma,h,h\n{cell(0, 0, 1)},{cell(0, 0, 2)},{cell(0, 0, 3)},{slow(0)},{slow(0)}\n".encode())), B6, full(B6))),
        ("COLUMN_POSITION_OUT_OF_RANGE", "the slow column at position 9", (lt(LT, slow="9"), LT, full(LT))),
        ("CELL_NOT_A_NUMBER", "a cell 'n/a'", (lt(B7 := lt_bank(raw=f"T,C,sigma,h\n{cell(0, 0, 1)},n/a,{cell(0, 0, 3)},{slow(0)}\n".encode())), B7, full(B7))),
    ]
    XL = lt_bank(raw=xlsx([["T", "C", "sigma", "h"]] + rows, "data"))
    PLANTS += {False: [("XLSX_READER_ABSENT", "an xlsx sentinel bank without openpyxl", (lt(XL, xl), XL, full(XL)))],
               True: [("NOT_AN_XLSX", "bytes that are no workbook", (lt(B8 := lt_bank(raw=b"T,C,sigma,h\n"), xl), B8, full(B8))),
                      ("SHEET_ABSENT", "sheet 'data' declared, the workbook holds 'Sheet1'", (lt(B9 := lt_bank(raw=xlsx([["T", "C", "sigma", "h"]] + rows, "Sheet1")), xl), B9, full(B9))),
                      ("PASS", "the xlsx sentinel bank", (lt(XL, xl), XL, full(XL)))]}[HAS_XLSX]
    NOT_HERE = {False: ["NOT_AN_XLSX", "SHEET_ABSENT"], True: ["XLSX_READER_ABSENT"]}[HAS_XLSX]

    # ---- K1. the sentinel alphabet: every numeric cell of every bank and every declared slow value
    cells = {m.decode() for q in banks.rglob("*") if q.is_file() for m in SENT.findall(q.read_bytes())} | {slow(k) for k in range(K)}
    numeric = [q for q in banks.rglob("*.csv") for ln in q.read_text(errors="replace").splitlines()[1:] for c in ln.split(",") if re.fullmatch(r"[-+.\d]+", c) and not c.startswith("-7357.")]
    check("K1. every numeric cell of every csv bank is a sentinel", not numeric and len(cells) > 100, f"{len(numeric)} non-sentinel numeric cells, first {numeric[:3]}; {len(cells)} sentinels")
    every = {f for c in cells for f in forms(c)}
    check("K1. every printed form of every sentinel holds -7357 (so no form is a short common string)", all("-7357" in f for f in every), str([f for f in every if "-7357" not in f][:5]))

    # ---- K2, K3. every live row planted, and nothing printed or written holds a sentinel
    hit = lambda text: sorted({f for f in every if f in text})
    check("K3. the scan sees a sentinel when one is printed (a check that cannot see must not convict)", hit(f"T span [{float(cell(0, 0, 1)):g}, 1]") != [])
    live = {r["code"] for s in intake.tables(ROOT)["stages"]["stage"] for k in ("reason", "reader_reason") for r in blind.look(s, k, []) if r["live"]}
    reached, said = set(), {}
    for code, what, (text, bank, steps, *trans) in PLANTS:
        got, out, ident = plant(text, bank, steps, *trans)
        reached |= {got}
        said[code + " " + what] = out
        check(f"K2. {code}: {what}", got == code, got)
        check(f"K3. {code}: no sentinel in its stdout, stderr, intake-report.md, SEAL.json, seal.log or access.log", not hit(out), f"{hit(out)[:5]} in {ident}")
    reached |= {True: {"READER_REFUSED"}, False: set()}[any("REFUSE READER_REFUSED" in o for o in said.values())]   # the reader-reason plants arrived through S4
    print(f"  openpyxl {'installed' if HAS_XLSX else 'NOT installed'} on this machine; NOT REACHED HERE: {NOT_HERE}")
    check("K2. the codes the plants reach are exactly the live rows (with the machine's NOT REACHED rows)", (reached - {"PASS"}) | set(NOT_HERE) == live,
          f"live, never reached: {sorted(live - reached - set(NOT_HERE))}; reached, not live: {sorted(reached - live - {'PASS'})}")

    # ---- K4. the census section: curves by ordinal and file name
    for key, want in (("PASS the PER_FILE sentinel bank, sealed", [f"{i + 1}. curve_{i:03d}.csv: {6 + i} points" for i in range(K)]),
                      ("PASS the LONG_TABLE sentinel bank, sealed", [f"{i + 1}. bank.csv block {i + 1}: {6 + i} points" for i in range(K)])):
        sec = said[key].split("## Census\n", 1)[-1].split("\n## ", 1)[0]
        check(f"K4. {key.split(' ', 1)[1]}: the census section lists each curve by ordinal and file name", "## Census\n" in said[key] and all(x in sec.splitlines() for x in want), sec[:400])

print("test_intake_leak: " + ("FAILED " + "; ".join(bad) if bad else "all passed"))
sys.exit(1 if bad else 0)
