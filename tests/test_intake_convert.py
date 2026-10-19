"""test_intake_convert - plan 1160 P3: the conversion of a deposit into a canonical bank (cc/intake_convert.py, `bin/cc intake convert |
peek`). Planted inputs only (no real data).
 V1. Each op of intake/CONVERSION.toml [op], on a planted file, writes a bank file equal byte for byte to a hand-written expected file, and
     --verify passes on it (SHEET_TO_CSV only where openpyxl is installed; elsewhere it refuses XLSX_READER_ABSENT and is NOT REACHED here).
 V2. The identity test catches a cell rewritten as repr(float(cell) + 1e-9), a dropped row and a reordered row (each a mutation of
     intake_convert.render, so the bytes about to be written differ from what the ops built): convert refuses and writes no bank.
 V2 (1160 A11). DROP_ROWS_NOT_NUMERIC: the manifest records the dropped rows' source lines (with the step), the [line, column] of each
     cell that is no number and the count, never a cell; the identity test refuses a mutation of the op that drops a numeric row (recording
     that row's own cell, another row's cell, no cell, or a sourceless cell), and a drop declared before DECIMAL_MARK.
 V3. Planted shapes convert and reach an S5 census: a MultiVu-like file through DROP_LINES; a semicolon file with a `##Temp./°C;...` names
     line and decimal commas through DELIMITER + NAMES_LINE + DECIMAL_MARK + RENAME; a WIDE file through WIDE_TO_LONG to a LONG_TABLE; a
     two-sheet xlsx through SHEET_TO_CSV + SELECT_COLUMNS + SPLIT_ROWS to two PER_FILE curves (NOT REACHED without openpyxl: it must run on
     the data host).
 V4. peek on the WIDE file prints "1 text name + N numeric names" and no value, at most depth + 2 lines, and stops before a line of numbers.
 V4 (1160 A10). peek on an xlsx with no --sheet refuses SHEET_REQUIRED, its Detail the sheet names as peek prints names (a TEXT name masked, a
     NUMERIC name counted), or, without openpyxl, that they cannot be listed here; no byte of the archive is printed.
 V5. The chain: --verify refuses CONVERSION_CHAIN_BROKEN after one source byte changes, and IDENTITY_FAILED when a bank cell changes and the
     manifest's sha256 is rewritten to match.
 V7 (1160 A12). Every conversion refusal's Detail names the file (V6: each plant's; of two files under one step, the one that refused);
     a line of quoted empty cells is blank to peek and to the converter (one definition, intake_convert.blank); peek decodes utf-8-sig.
 V6. Structure: OPS is total over the [op] alphabet and the steps VARIANT; each rule table over its kinds; `float` is called only in _same,
     `int` only in peek_cli; every reason the module can emit is a row of intake/CONVERSION.toml; and every row is reached by a plant here
     (with the machine's NOT REACHED xlsx row).
Seen RED (each mutation applied by hand, the test run, the mutation reverted):
 - _same returning True: V2 FAILS on repr(float(cell) + 1e-9) (PASS) and V5 FAILS (no IDENTITY_FAILED after a bank cell changed);
 - verify's `twice` check removed: V6 FAILS (the RANGES plant whose parts overlap passes);
 - verify's `unordered` check removed: V2 FAILS on the reordered row (PASS);
 - verify's `unpartitioned` check removed: V2 FAILS on the dropped row and V6 on the RANGES plant that omits a row (PASS);
 - chained without the raw sha256 comparison: V5 FAILS (no refusal after a source byte changed) and V6's totality (CHAIN_BROKEN unreached);
 - DROP["MARKER"] dropping only the marker line: V1 FAILS on the MARKER case (its header lines are written).
 - (1160 A11) DROP_ROWS_NOT_NUMERIC dropping the rows whose cell IS a number: V1 FAILS; verify justifying every DROP_ROWS_NOT_NUMERIC drop:
   V2 FAILS (each numeric-row drop passes); verify judging the cell without the decimal mark: V2 FAILS (the drop before DECIMAL_MARK passes);
   the manifest's not_numeric_count off by one: V2 FAILS (the manifest record).
 - (1160 A12) _in keeping the file empty: V6 and V7 FAIL; _built naming the first entry for every file, verify's IDENTITY_FAILED without its
   file, peek's old re.split cut, peek decoding utf-8: V7 FAILS.
 - (1160 A10) _xlsx always False: V4 and V6 FAIL; _named printing every name unmasked: V4 FAILS (the sheet-name words).
Not seen red: _same comparing text only. Every op copies a cell's text (DECIMAL_MARK's replacement is applied to the source cell too), so
an output numeral always has its source's text and the bitwise float comparison the plan asks for never decides a case here.
The xlsx shapes run where openpyxl is installed (the data host, docs/INTAKE-ON-A-DATA-HOST.md)."""
import ast
import contextlib
import importlib.util
import io
import json
import re
import sys
import tempfile
import tomllib
import zipfile
from dataclasses import replace
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path[:0] = [str(ROOT / "cc"), str(ROOT / "tests")]
import intake  # noqa: E402
import intake_convert as ic  # noqa: E402
import intake_synth  # noqa: E402
from intake_plant import conversion, long_table, outcome, per_file, rooted, run, workbook  # noqa: E402

bad = []


def check(name, ok, why=""):
    print(("ok   " if ok else "FAIL ") + name + ("" if ok else f": {why}"))
    if not ok:
        bad.append(name)


T = intake.tables(ROOT)
CT = ic.ctables()
ROWS = {r["code"] for r in CT["reason"]}
HAS_XLSX = importlib.util.find_spec("openpyxl") is not None
REACHED = set()


def zipped(members):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        [z.writestr(n, b) for n, b in members.items()]
    return buf.getvalue()


with tempfile.TemporaryDirectory() as tmp:
    tmp = Path(tmp)
    n = iter(range(1000))

    def conv(raws, files, name=None):
        """Plant <tmp>/cc-datasets/<name>/raw and declarations/<name>/CONVERSION.toml; convert: (the result, the bank dir, name)."""
        name = name or f"c{next(n)}"
        raw, d = tmp / "cc-datasets" / name / "raw", tmp / "declarations" / name
        raw.mkdir(parents=True)
        d.mkdir(parents=True)
        [(raw / f).write_bytes(b) for f, b in raws.items()]
        (d / "CONVERSION.toml").write_text({True: lambda: files, False: lambda: conversion(f"<cc-datasets>/{name}/raw", f"<cc-banks>/{name}/bank", files)}[isinstance(files, str)]())
        got = ic.convert(tmp, name, rooted(T, tmp), CT)
        REACHED.add({True: lambda: got.reason, False: lambda: "PASS"}[hasattr(got, "reason")]())
        return got, tmp / "cc-banks" / name / "bank", name

    def verify(name):
        got = ic.verified(tmp, name, rooted(T, tmp), CT)
        REACHED.add({True: lambda: got.reason, False: lambda: "PASS"}[hasattr(got, "reason")]())
        return got

    code = lambda got: {True: lambda: got.reason, False: lambda: "PASS"}[hasattr(got, "reason")]()

    # ---- V1. each op, byte for byte
    CASES = [
        ("UNPACK", {"a.zip": zipped({"run1.csv": "T,C\n1.5,0.25\n"})}, "a.zip", '{op = "UNPACK", member = "run1.csv"}', {"out.csv": "T,C\n1.5,0.25\n"}),
        ("DECODE", {"a.csv": "T,µ\n1.5,0.25\n".encode("latin-1")}, "a.csv", '{op = "DECODE", encoding = "latin-1"}', {"out.csv": "T,µ\n1.5,0.25\n"}),
        ("DROP_LINES MARKER", {"a.dat": b"[Header]\nTITLE,run 1\n[Data]\nTime,Temp (K),Moment\n1.0,300.5,1e-3\n2.0,301.25,2e-3\n"}, "a.dat",
         '{op = "DROP_LINES", rule = {kind = "MARKER", marker = "[Data]"}}', {"out.csv": "Time,Temp (K),Moment\n1.0,300.5,1e-3\n2.0,301.25,2e-3\n"}),
        ("DROP_LINES FIRST", {"a.csv": b"sample A\noperator note\nT,C\n1.5,0.25\n"}, "a.csv", '{op = "DROP_LINES", rule = {kind = "FIRST", count = 2}}', {"out.csv": "T,C\n1.5,0.25\n"}),
        ("DROP_LINES PREFIX", {"a.csv": b"# run 1\nT,C\n# pause\n1.5,0.25\n"}, "a.csv", '{op = "DROP_LINES", rule = {kind = "PREFIX", prefix = "#"}}', {"out.csv": "T,C\n1.5,0.25\n"}),
        ("DELIMITER TAB", {"a.tsv": b"T\tC\n1.5\t0.25\n"}, "a.tsv", '{op = "DELIMITER", from = "TAB"}', {"out.csv": "T,C\n1.5,0.25\n"}),
        ("DELIMITER WHITESPACE", {"a.txt": b"T   C\n  1.5  0.25\n\n1.6 0.5\n"}, "a.txt", '{op = "DELIMITER", from = "WHITESPACE"}', {"out.csv": "T,C\n1.5,0.25\n1.6,0.5\n"}),
        ("DELIMITER SEMICOLON", {"a.csv": b"T;C\n1.5;0.25\n"}, "a.csv", '{op = "DELIMITER", from = "SEMICOLON"}', {"out.csv": "T,C\n1.5,0.25\n"}),
        ("NAMES_LINE WRITE", {"a.csv": b"1.5,0.25\n1.6,0.5\n"}, "a.csv", '{op = "NAMES_LINE", rule = {kind = "WRITE", names = ["T", "C"]}}', {"out.csv": "T,C\n1.5,0.25\n1.6,0.5\n"}),
        ("NAMES_LINE REPLACE_PREFIXED", {"a.csv": b"##T,C\n1.5,0.25\n"}, "a.csv", '{op = "NAMES_LINE", rule = {kind = "REPLACE_PREFIXED", prefix = "##"}}', {"out.csv": "T,C\n1.5,0.25\n"}),
        ("NAMES_LINE FIRST", {"a.csv": b"T,C\n1.5,0.25\n"}, "a.csv", '{op = "NAMES_LINE", rule = {kind = "FIRST"}}', {"out.csv": "T,C\n1.5,0.25\n"}),
        ("DECIMAL_MARK", {"a.csv": b"T;C\n1,5;0,25\n"}, "a.csv", '{op = "DELIMITER", from = "SEMICOLON"}, {op = "DECIMAL_MARK", mark = ","}', {"out.csv": "T,C\n1.5,0.25\n"}),
        ("SELECT_COLUMNS", {"a.csv": b"T,C,s\n1.5,0.25,0.01\n"}, "a.csv", '{op = "SELECT_COLUMNS", columns = ["C", 1]}', {"out.csv": "C,T\n0.25,1.5\n"}),
        ("RENAME", {"a.csv": b"Temp,C\n1.5,0.25\n"}, "a.csv", '{op = "RENAME", pairs = [{from = "Temp", to = "T"}]}', {"out.csv": "T,C\n1.5,0.25\n"}),
        ("SPLIT_ROWS RANGES", {"a.csv": b"T,C\n1.5,0.25\n1.6,0.5\n1.5,0.75\n"}, "a.csv",
         '{op = "SPLIT_ROWS", rule = {kind = "RANGES", parts = [{name = "up.csv", first = 1, last = 2}, {name = "down.csv", first = 3, last = 3}]}}',
         {"up.csv": "T,C\n1.5,0.25\n1.6,0.5\n", "down.csv": "T,C\n1.5,0.75\n"}),
        ("SPLIT_ROWS CHANGE", {"a.csv": b"T,C,h\n1.5,0.25,0.1\n1.6,0.5,0.1\n1.5,0.75,0.2\n"}, "a.csv", '{op = "SPLIT_ROWS", rule = {kind = "CHANGE", column = "h"}}',
         {"out_000.csv": "T,C,h\n1.5,0.25,0.1\n1.6,0.5,0.1\n", "out_001.csv": "T,C,h\n1.5,0.75,0.2\n"}),
        ("WIDE_TO_LONG", {"a.csv": b"h,1.5,1.6\n0.1,0.25,0.5\n0.2,0.75,1.0\n"}, "a.csv", '{op = "WIDE_TO_LONG", key = "h", fast = "T", measured = "C"}',
         {"out.csv": "T,C,h\n1.5,0.25,0.1\n1.6,0.5,0.1\n1.5,0.75,0.2\n1.6,1.0,0.2\n"}),
        ("DROP_ROWS_NOT_NUMERIC", {"a.csv": b"T,C\n1.5,0.25\n1.6,\n1.7,n/a\n1.8,0.5\n"}, "a.csv", '{op = "DROP_ROWS_NOT_NUMERIC", columns = ["C"]}',   # 1160 A11
         {"out.csv": "T,C\n1.5,0.25\n1.8,0.5\n"}),
    ]
    XCASE = ("SHEET_TO_CSV", {"a.xlsx": workbook({"notes": [["planted"]], "data": [["T", "C"], [1.5, 0.25]]})}, "a.xlsx", '{op = "SHEET_TO_CSV", sheet = "data"}',
             {"out.csv": "T,C\n1.5,0.25\n"})
    for op, raws, frm, steps, want in CASES + [XCASE] * HAS_XLSX:
        got, bank, name = conv(raws, [(frm, "out.csv", steps)])
        wrote = {f: (bank / f).read_text() for f in want if (bank / f).is_file()}
        check(f"V1. {op}: the bank equals the expected files byte for byte, and --verify passes", code(got) == "PASS" and wrote == want and code(verify(name)) == "PASS",
              f"{code(got)} {wrote}")
    print({True: "  openpyxl installed: SHEET_TO_CSV ran", False: "  openpyxl NOT installed: SHEET_TO_CSV NOT REACHED HERE (it runs on the data host)"}[HAS_XLSX])
    got, _, _ = conv(XCASE[1], [(XCASE[2], "out.csv", XCASE[3])])
    check("V1. SHEET_TO_CSV refuses XLSX_READER_ABSENT exactly when openpyxl is not installed", (code(got) == "XLSX_READER_ABSENT") is not HAS_XLSX, code(got))

    # ---- V2. the identity test catches three mutations of the bytes about to be written
    rendered = ic.render
    MUTATIONS = {
        "a cell rewritten as repr(float(cell) + 1e-9)": lambda fr: replace(fr, rows=((fr.rows[0][0], (fr.rows[0][1][0], (repr(float(fr.rows[0][1][1][0]) + 1e-9), fr.rows[0][1][1][1]))
                                                                                       + fr.rows[0][1][2:]),) + fr.rows[1:]),
        "a dropped row": lambda fr: replace(fr, rows=fr.rows[:-1]),
        "a reordered row": lambda fr: replace(fr, rows=(fr.rows[1], fr.rows[0]) + fr.rows[2:]),
    }
    MV = CASES[2]
    for what, mut in MUTATIONS.items():
        ic.render = lambda fr, mut=mut: rendered(mut(fr))
        got, bank, _ = conv(MV[1], [(MV[2], "out.csv", MV[3])])
        ic.render = rendered
        check(f"V2. the identity test catches {what}: convert refuses ({code(got)}) and writes no bank",
              code(got) in ("IDENTITY_FAILED", "CELL_MAP_NOT_A_PERMUTATION") and not bank.exists(), code(got))

    # ---- V2. (1160 A11) DROP_ROWS_NOT_NUMERIC: the manifest's lines and count, and the identity test refuses a drop of a numeric row
    NN = ({"a.csv": b"T,C\n1.5,0.25\n1.6,\n1.7,n/a\n1.8,0.5\n"}, "a.csv", '{op = "DROP_ROWS_NOT_NUMERIC", columns = ["C"]}')
    got, bank, _ = conv(NN[0], [(NN[1], "out.csv", NN[2])])
    man = (bank / ic.MANIFEST).read_text()
    unit = json.loads(man)["units"][0]
    check("V2. (1160 A11) the manifest records the dropped rows' source lines with their step, the cells that are no number, and the count; no cell",
          unit["dropped"] == [[3, 0], [4, 0]] and unit["not_numeric"] == [[3, 1], [4, 1]] and unit["not_numeric_count"] == 2 and "n/a" not in man, str(unit))
    dropper = ic.OPS["DROP_ROWS_NOT_NUMERIC"]
    NUMERIC_DROPS = {   # a mutation of the op's result: the frame it returns drops the numeric row of line 5 (1.8,0.5) as well
        "recording that row's own cell (a number)": lambda fr: replace(fr, rows=fr.rows[:-1], dropped=fr.dropped + ((5, 0),), not_numeric=fr.not_numeric + ((5, 1),)),
        "recording another row's cell that is no number": lambda fr: replace(fr, rows=fr.rows[:-1], dropped=fr.dropped + ((5, 0),), not_numeric=fr.not_numeric + ((3, 1),)),
        "recording no cell": lambda fr: replace(fr, rows=fr.rows[:-1], dropped=fr.dropped + ((5, 0),)),
        "recording a sourceless cell": lambda fr: replace(fr, rows=fr.rows[:-1], dropped=fr.dropped + ((5, 0),), not_numeric=fr.not_numeric + (None,)),
    }
    for what, mut in NUMERIC_DROPS.items():
        ic.OPS["DROP_ROWS_NOT_NUMERIC"] = lambda name, fr, step, k, mut=mut: [(nm, mut(f)) for nm, f in dropper(name, fr, step, k)]
        got, bank, _ = conv(NN[0], [(NN[1], "out.csv", NN[2])])
        ic.OPS["DROP_ROWS_NOT_NUMERIC"] = dropper
        check(f"V2. (1160 A11) the identity test refuses a drop of a numeric row {what}: CELL_MAP_NOT_A_PERMUTATION, no bank",
              code(got) == "CELL_MAP_NOT_A_PERMUTATION" and not bank.exists(), code(got))
    got, bank, _ = conv({"a.csv": b"T;C\n1,5;0,25\n1,6;\n"}, [("a.csv", "out.csv", '{op = "DELIMITER", from = "SEMICOLON"}, {op = "DROP_ROWS_NOT_NUMERIC", columns = ["C"]}, {op = "DECIMAL_MARK", mark = ","}')])
    check("V2. (1160 A11) a DROP_ROWS_NOT_NUMERIC declared on a column before its DECIMAL_MARK drops '0,25' too, and the identity test refuses it", code(got) == "CELL_MAP_NOT_A_PERMUTATION", code(got))

    # ---- V3. planted shapes reach a census
    banks = tmp / "banks"
    intake_synth.write(banks / "pf", tmp / "pf-TRUTH", "pf", 1, 9)
    m = json.loads((banks / "pf" / "MANIFEST.json").read_text())
    curves = {f["name"]: (banks / "pf" / f["name"]).read_bytes() for f in m["files"]}

    def census(text, ident):
        got = outcome(run(T, tmp, ident, text), "S5")
        return getattr(got[1], "label", got[0])

    def converted_decl(text, name):
        return re.sub(r'root = "[^"]*"', f'root = "<cc-banks>/{name}/bank"', text.replace('kind = "DEPOSIT"', f'kind = "CONVERTED"\nconverted_from = "<cc-datasets>/{name}/raw"', 1)
                      .replace('file = "MANIFEST.json"', 'file = "CONVERSION-MANIFEST.json"', 1), count=1)

    deposit = census(per_file(m, "dep").replace("<long-test>/pf", "<long-test>/pf"), "dep")
    multivu = {f: b"[Header]\nTITLE,planted MultiVu-like run\nBYAPP,planted\n[Data]\n" + b for f, b in curves.items()}
    got, bank, name = conv(multivu, [(f, f, '{op = "DROP_LINES", rule = {kind = "MARKER", marker = "[Data]"}}') for f in curves])
    label = census(converted_decl(per_file(m, "mv"), name), "mv")
    check("V3. MultiVu-like files through DROP_LINES convert to the deposit's bytes and reach the deposit's census", code(got) == "PASS"
          and all((bank / f).read_bytes() == b for f, b in curves.items()) and label == deposit and not isinstance(label, str), f"{code(got)} {label}")
    semi = {f: ("##Temp./°C;" + b.decode().split("\n", 1)[0].split(",", 1)[1].replace(",", ";") + "\n"
                + "".join(ln.replace(",", ";").replace(".", ",") + "\n" for ln in b.decode().splitlines()[1:])).encode("utf-8") for f, b in curves.items()}
    sc = ('{op = "DELIMITER", from = "SEMICOLON"}, {op = "NAMES_LINE", rule = {kind = "REPLACE_PREFIXED", prefix = "##"}}, {op = "DECIMAL_MARK", mark = ","}, '
          '{op = "RENAME", pairs = [{from = "Temp./°C", to = "T"}]}')
    got, bank, name = conv(semi, [(f, f, sc) for f in curves])
    label = census(converted_decl(per_file(m, "sc"), name), "sc")
    check("V3. semicolon files with a '##Temp./°C;...' names line and decimal commas convert to the deposit's bytes and reach its census",
          code(got) == "PASS" and all((bank / f).read_bytes() == b for f, b in curves.items()) and label == deposit, f"{code(got)} {label}")
    Ts = [f"{1.5 + 0.0125 * j:.4f}" for j in range(40)]
    WIDE = ("h," + ",".join(Ts) + "\n" + "".join(f"{f['h']}," + ",".join(f"{0.1 + 0.01 * k + 0.001 * j:.6f}" for j in range(40)) + "\n" for k, f in enumerate(m["files"]))).encode()
    got, bank, WD = conv({"wide.csv": WIDE}, [("wide.csv", "bank.csv", '{op = "WIDE_TO_LONG", key = "h", fast = "T", measured = "C"}')])
    nosigma = lambda t: re.sub(r'\[measured\.uncertainty\]\nkind = "COLUMN"[^\n]*\nkey = "[^"]*"[^\n]*', '[measured.uncertainty]\nkind = "NONE"', t, count=1).replace(
        'method = "STATED"', 'method = "NONE"', 1)   # plan 1160 P5: the plant's interval is STATED (was iid), which needs the sigma column a WIDE file lacks
    label = census(nosigma(converted_decl(long_table(m, "wd"), WD)), "wd")
    check("V3. a WIDE file through WIDE_TO_LONG reaches a LONG_TABLE census of one curve per row", code(got) == "PASS" and getattr(label, "curves", None) == len(m["files"]), f"{code(got)} {label}")
    rows = [["T", "C", "sigma", "note"]] + [[float(x) for x in ln.split(",")] + ["planted"] for f in list(curves)[:2] for ln in curves[f].decode().splitlines()[1:]]
    first = len(curves[list(curves)[0]].decode().splitlines()) - 1
    xsteps = ('{op = "SHEET_TO_CSV", sheet = "data"}, {op = "SELECT_COLUMNS", columns = ["T", "C", "sigma"]}, '
              f'{{op = "SPLIT_ROWS", rule = {{kind = "RANGES", parts = [{{name = "{list(curves)[0]}", first = 1, last = {first}}}, {{name = "{list(curves)[1]}", first = {first + 1}, last = {len(rows) - 1}}}]}}}}')
    got, bank, XN = conv({"runs.xlsx": workbook({"notes": [["planted two-sheet workbook"]], "data": rows})}, [("runs.xlsx", "x.csv", xsteps)])
    two = lambda t: t.replace(re.search(r"files = \[[^\]]*\]", t)[0], f'files = ["{list(curves)[0]}", "{list(curves)[1]}"]', 1).replace(
        re.search(r"values = \[[^\]]*\]", t)[0], f'values = ["{m["files"][0]["h"]}", "{m["files"][1]["h"]}"]', 1)
    label = {True: lambda: census(two(converted_decl(per_file(m, "xl"), XN)), "xl"), False: lambda: "NOT REACHED"}[HAS_XLSX]()
    check("V3. a two-sheet xlsx through SHEET_TO_CSV + SELECT_COLUMNS + SPLIT_ROWS reaches a census of two PER_FILE curves (openpyxl only)",
          {True: lambda: getattr(label, "curves", None) == 2, False: lambda: code(got) == "XLSX_READER_ABSENT"}[HAS_XLSX](), f"{code(got)} {label}")
    print({True: "", False: "  NOT REACHED HERE: the two-sheet xlsx shape (no openpyxl); it must run on the data host"}[HAS_XLSX])

    # ---- V4. peek
    def peek(ident, *args):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            rc = ic.peek_cli(tmp, ident, list(args), rooted(T, tmp))
        return rc, out.getvalue()
    peekf = lambda ident, f, *args: peek(ident, f"<cc-datasets>/{ident}/raw/{f}", *args)   # (1160 A19) the file by its root-named path
    rc, said = peekf(WD, "wide.csv")
    check("V4. peek on the WIDE file prints '1 text name + 40 numeric names' and stops before the first line of numbers",
          rc == 0 and "line 1: 1 text name + 40 numeric names: 'h'" in said and "stopped: a line of numbers (not printed)" in said and "line 2" not in said, said)
    check("V4. peek prints no value: no names-line number and no data cell", not [x for x in Ts + WIDE.decode().split("\n")[1].split(",") if x in said], said)
    rc, said = peekf(name, list(semi)[0], "--depth", "0")
    check("V4. peek prints at most depth + 2 lines, masking a numeral in a text name", said.count("\n  line ") + said.startswith("  line ") <= 2 and "'##Temp./°C'" in said, said)
    log = [json.loads(x) for x in (tmp / "declarations" / WD / "peek.log").read_text().splitlines()]
    check("V4. peek appends to declarations/<id>/peek.log what was asked and how many lines printed", log[-1]["file"] == f"<cc-datasets>/{WD}/raw/wide.csv" and log[-1]["printed"] == 1, str(log))
    outside = [peek(WD, p) for p in (f"<cc-banks>/{WD}/bank/bank.csv", str(tmp / "cc-datasets" / WD / "raw" / "wide.csv"), f"<cc-datasets>/../cc-datasets/{WD}/raw/wide.csv", "wide.csv")]
    check("V4. (1160 A19: was 'outside <cc-datasets>/<id>/raw') peek refuses a path outside the <cc-datasets> root: another root, an absolute path, "
          "a '..' part, a bare name (SOURCE_FILE_ABSENT)", all(rc == 1 and "SOURCE_FILE_ABSENT" in said for rc, said in outside), str(outside))

    # ---- V4. (1160 A10) peek on an xlsx with no --sheet: SHEET_REQUIRED, its Detail the sheet names (text masked, numeric counted)
    got, bank, XP = conv({"book.xlsx": workbook({"notes 2": [["planted"]], "1.5": [["T"], [1.5]], "data": [["T"], [1.5]]})}, [("book.xlsx", "x.csv", '{op = "SHEET_TO_CSV", sheet = "data"}')])
    rc, said = peekf(XP, "book.xlsx")
    check("V4. (1160 A10) peek on an xlsx with no --sheet refuses SHEET_REQUIRED and prints no byte of the archive",
          rc == 1 and "SHEET_REQUIRED" in said and "PK" not in said and "1.5" not in said and "xl/" not in said, said)
    check("V4. (1160 A10) its Detail lists the sheet names where openpyxl is installed, and says it cannot list them where it is not",
          {True: "the workbook's sheets: #1 'notes #', #2 a numeric name, #3 'data'" in said,   # (1160 A21: was '2 text names + 1 numeric name: ...')
           False: "openpyxl is not installed on this machine, so the sheet names cannot be listed here" in said}[HAS_XLSX], said)
    check("V4. (1160 A10; A21: each by its position, was counted) the sheet-name words: TEXT names masked, a NUMERIC name never printed",
          ic.SHEET_WORDS[(True, True)](["notes 2", "1.5", "data"]) == ["the workbook's sheets: #1 'notes #', #2 a numeric name, #3 'data'; name one with --sheet k (its position) or --sheet NAME"],
          str(ic.SHEET_WORDS[(True, True)](["notes 2", "1.5", "data"])))
    rc, said = peekf(XP, "book.xlsx", "--sheet", "data")
    check("V4. (1160 A10) peek on the xlsx with --sheet reads that sheet (XLSX_READER_ABSENT without openpyxl)",
          {True: "line 1: 1 text name + 0 numeric names: 'T'" in said, False: "XLSX_READER_ABSENT" in said}[HAS_XLSX], said)
    rc, said = peekf(name, list(semi)[0], "--depth", "0")
    check("V4. (1160 A10) a text file with no --sheet is peeked as text, as before", rc == 0 and "line 1:" in said, said)

    # ---- V5. the chain
    got, bank, name = conv({"a.csv": b"T,C\n1.5,0.25\n1.6,0.5\n"}, [("a.csv", "a.csv", "")])
    raw = tmp / "cc-datasets" / name / "raw" / "a.csv"
    raw.write_bytes(raw.read_bytes().replace(b"0.25", b"0.26"))
    check("V5. --verify refuses CONVERSION_CHAIN_BROKEN after one source byte changes", code(verify(name)) == "CONVERSION_CHAIN_BROKEN")
    got, bank, name = conv({"a.csv": b"T,C\n1.5,0.25\n1.6,0.5\n"}, [("a.csv", "a.csv", "")])
    (bank / "a.csv").write_bytes(b"T,C\n1.5,0.26\n1.6,0.5\n")
    man = json.loads((bank / ic.MANIFEST).read_text())
    man["outputs"][0]["sha256"] = ic._sha((bank / "a.csv").read_bytes())
    (bank / ic.MANIFEST).write_text(json.dumps(man))
    check("V5. --verify refuses IDENTITY_FAILED when a bank cell changes and the manifest's sha256 is rewritten to match", code(verify(name)) == "IDENTITY_FAILED")

    # ---- V6. every row of intake/CONVERSION.toml reached
    ok = '{op = "DELIMITER", from = "COMMA"}'
    PLANTS = [
        ("TOML_INVALID", lambda: conv({"a.csv": b"T\n1\n"}, "[[[")),
        ("SCHEMA_UNSUPPORTED", lambda: conv({"a.csv": b"T\n1\n"}, conversion("<cc-datasets>/x/raw", "<cc-banks>/x/bank", [("a.csv", "a.csv", ok)]).replace("schema = 1", "schema = 2"))),
        ("FIELD_MISSING", lambda: conv({"a.csv": b"T\n1\n"}, re.sub(r"out = .*\n", "", conversion("<cc-datasets>/x/raw", "<cc-banks>/x/bank", [("a.csv", "a.csv", ok)])))),
        ("FIELD_TYPE_WRONG", lambda: conv({"a.csv": b"T\n1\n"}, [("a.csv", "a.csv", '{op = "DROP_LINES", rule = {kind = "FIRST", count = "two"}}')])),
        ("FIELD_UNKNOWN", lambda: conv({"a.csv": b"T\n1\n"}, [("a.csv", "a.csv", '{op = "DELIMITER", from = "COMMA", colour = "red"}')])),
        ("VALUE_NOT_LISTED", lambda: conv({"a.csv": b"T\n1\n"}, [("a.csv", "a.csv", '{op = "DELIMITER", from = "PIPE"}')])),
        ("VALUE_STILL_TODO", lambda: conv({"a.csv": b"T\n1\n"}, [("a.csv", "a.csv", '{op = "DELIMITER", from = "TODO"}')])),
        ("ROOT_NOT_UNDER_CC_BANKS", lambda: conv({"a.csv": b"T\n1\n"}, conversion("<cc-datasets>/x/raw", "<cc-datasets>/x/bank", [("a.csv", "a.csv", ok)]))),
        ("OPERATION_NOT_LISTED", lambda: conv({"a.csv": b"T\n1\n"}, [("a.csv", "a.csv", '{op = "INTERPOLATE"}')])),
        ("ROOT_UNRESOLVED", lambda: conv({"a.csv": b"T\n1\n"}, conversion("<no-such-root>/x/raw", "<cc-banks>/x/bank", [("a.csv", "a.csv", ok)]))),
        ("OUTPUT_NAME_REFUSED", lambda: conv({"a.csv": b"T\n1\n"}, [("a.csv", ic.MANIFEST, ok)])),
        ("OUTPUT_NAME_REFUSED", lambda: conv({"a.csv": b"T\n1\n"}, [("a.csv", "x.csv", ok), ("a.csv", "x.csv", ok)])),
        ("BANK_EXISTS", lambda: (lambda nm: (conv({"a.csv": b"T\n1\n"}, [("a.csv", "a.csv", ok)], nm), REACHED.add(code(ic.convert(tmp, nm, rooted(T, tmp), CT)))))(f"c{next(n)}")),
        ("STEP_OUT_OF_ORDER", lambda: conv({"a.csv": b"T\n1\n"}, [("a.csv", "a.csv", ok + ', {op = "DROP_LINES", rule = {kind = "FIRST", count = 1}}')])),
        ("SOURCE_FILE_ABSENT", lambda: conv({"a.csv": b"T\n1\n"}, [("b.csv", "a.csv", ok)])),
        ("SOURCE_FILE_ABSENT", lambda: conv({"a.zip": zipped({"x.csv": "T\n1\n"})}, [("a.zip", "a.csv", '{op = "UNPACK", member = "y.csv"}')])),
        ("CONTAINER_UNREADABLE", lambda: conv({"a.zip": b"T\n1\n"}, [("a.zip", "a.csv", '{op = "UNPACK", member = "y.csv"}')])),
        ("MARKER_LINE_ABSENT", lambda: conv({"a.csv": b"T\n1\n"}, [("a.csv", "a.csv", '{op = "DROP_LINES", rule = {kind = "MARKER", marker = "[Data]"}}')])),
        ("MARKER_LINE_ABSENT", lambda: conv({"a.csv": b"T\n1\n"}, [("a.csv", "a.csv", '{op = "NAMES_LINE", rule = {kind = "REPLACE_PREFIXED", prefix = "##"}}')])),
        ("COLUMN_ABSENT", lambda: conv({"a.csv": b"T,C\n1,2\n"}, [("a.csv", "a.csv", '{op = "SELECT_COLUMNS", columns = ["Z"]}')])),
        ("COLUMN_ABSENT", lambda: conv({"a.csv": b"T,C\n1,2\n3\n"}, [("a.csv", "a.csv", '{op = "SELECT_COLUMNS", columns = [2]}')])),
        ("ENCODING_INVALID", lambda: conv({"a.csv": b"T\n\xff\n"}, [("a.csv", "a.csv", '{op = "DECODE", encoding = "utf-8"}')])),
        ("NAMES_NOT_NUMERIC", lambda: conv({"a.csv": b"h,1.5,note\n0.1,2,x\n"}, [("a.csv", "a.csv", '{op = "WIDE_TO_LONG", key = "h", fast = "T", measured = "C"}')])),
        ("CELL_MAP_NOT_A_PERMUTATION", lambda: conv({"a.csv": b"T\n1\n2\n3\n"}, [("a.csv", "a.csv", '{op = "SPLIT_ROWS", rule = {kind = "RANGES", parts = [{name = "a.csv", first = 1, last = 1}, {name = "b.csv", first = 3, last = 3}]}}')])),
        ("CELL_MAP_NOT_A_PERMUTATION", lambda: conv({"a.csv": b"T\n1\n2\n3\n"}, [("a.csv", "a.csv", '{op = "SPLIT_ROWS", rule = {kind = "RANGES", parts = [{name = "a.csv", first = 1, last = 2}, {name = "b.csv", first = 2, last = 3}]}}')])),
        ("NAMES_COUNT_MISMATCH", lambda: conv({"a.csv": b"1,2,3\n"}, [("a.csv", "a.csv", '{op = "NAMES_LINE", rule = {kind = "WRITE", names = ["T", "C"]}}')])),   # 1160 A29
        ("EMPTY_CELL_UNDER_WHITESPACE", lambda: conv({"a.txt": b"T C\n1\n"}, [("a.txt", "a.csv", '{op = "DELIMITER", from = "WHITESPACE"}')])),   # 1160 A32
        ("XLSX_READER_ABSENT", lambda: conv({"a.xlsx": workbook({"data": [["T"], [1.5]]})}, [("a.xlsx", "a.csv", '{op = "SHEET_TO_CSV", sheet = "data"}')])),
        ("SHEET_REQUIRED", lambda: REACHED.add(code(ic._head(workbook({"data": [["T"], [1.5]]}), "", "utf-8-sig")))),   # (1160 A22: _head takes the encoding)   # (1160 A10) peek's refusal
        ("SHEET_ABSENT", lambda: conv({"a.xlsx": workbook({"data": [["T"], [1.5]]})}, [("a.xlsx", "a.csv", '{op = "SHEET_TO_CSV", sheet = "Sheet9"}')])),
    ]
    NOT_HERE = {False: ["SHEET_ABSENT"], True: ["XLSX_READER_ABSENT"]}[HAS_XLSX]
    UNFILED = []   # (1160 A12) the plants whose refusal's Detail names no file (ROOT_UNRESOLVED and BANK_EXISTS name the root or the out instead)
    for want, plant in PLANTS:
        before = set(REACHED)
        got = plant()
        UNFILED += [want for x in [got] if isinstance(x, tuple) and len(x) == 3 and hasattr(x[0], "reason") and x[0].reason not in ("ROOT_UNRESOLVED", "BANK_EXISTS")
                    and x[0].evidence.file == ""]
        got = {True: lambda: code(got[0]), False: lambda: want if want in REACHED - before else sorted(REACHED - before)}[isinstance(got, tuple) and len(got) == 3]()
        check(f"V6. {want} is reached by its plant{' (NOT REACHED HERE)' * (want in NOT_HERE)}", want in NOT_HERE or got == want, str(got))
    check("V6. the codes reached are exactly the rows of intake/CONVERSION.toml (with the machine's NOT REACHED xlsx row)",
          (REACHED - {"PASS"}) | set(NOT_HERE) == ROWS, f"rows never reached: {sorted(ROWS - REACHED - set(NOT_HERE))}; reached, no row: {sorted(REACHED - ROWS - {'PASS'})}")
    print(f"  openpyxl {'installed' if HAS_XLSX else 'NOT installed'} on this machine; NOT REACHED HERE: {NOT_HERE} ("   # (1160 A23: the reason printed with the row)
          + {True: "openpyxl is installed, so the reader-absent refusal cannot fire here; xlsx IS read", False: "no openpyxl: the xlsx rows run on the data host"}[HAS_XLSX] + ")")
    check("V6. (1160 A12) every plant's conversion refusal names its file in the Detail (the declaration's own: CONVERSION.toml)", not UNFILED, str(UNFILED))

    # ---- V7. (1160 A12) the Detail names the file of a family; peek's blank is the converter's; peek decodes utf-8-sig
    got, _, _ = conv({"a.csv": b"[Data]\nT,C\n1.5,0.25\n", "b.csv": b"[Header]\nT,C\n1.5,0.25\n"},
                     [(f, f, '{op = "DROP_LINES", rule = {kind = "MARKER", marker = "[Data]"}}') for f in ("a.csv", "b.csv")])
    check("V7. (1160 A12) of two files under one step, the refusal names the file that lacks the marker (b.csv), not the other",
          code(got) == "MARKER_LINE_ABSENT" and "b.csv" in str(got.evidence) and "a.csv" not in str(got.evidence), str(got))
    got, bank, QB = conv({"q.csv": b'T,C\n"",""\n1.5,0.25\n'}, [("q.csv", "q.csv", "")])
    rc, said = peekf(QB, "q.csv", "--depth", "3")
    check("V7. (1160 A12) a line of quoted empty cells is blank to peek and to the converter alike (one definition)",
          "line 2: blank" in said and code(got) == "PASS" and [2, -1] in json.loads((bank / ic.MANIFEST).read_text())["units"][0]["dropped"], said + code(got))
    got, bank, BB = conv({"bom.csv": b"\xef\xbb\xbfT,C\n1.5,0.25\n"}, [("bom.csv", "bom.csv", "")])
    rc, said = peekf(BB, "bom.csv")
    check("V7. (1160 A12) peek decodes utf-8-sig, as the converter's default DECODE: a byte-order mark is no part of the first name",
          "line 1: 2 text names + 0 numeric names: 'T', 'C'" in said, said)
    got, bank, name = conv({"a.csv": b"T,C\n1.5,0.25\n"}, [("a.csv", "a.csv", "")])
    (bank / "a.csv").write_bytes(b"T,C\n1.5,0.26\n")
    man = json.loads((bank / ic.MANIFEST).read_text())
    man["outputs"][0]["sha256"] = ic._sha((bank / "a.csv").read_bytes())
    (bank / ic.MANIFEST).write_text(json.dumps(man))
    got = verify(name)
    check("V7. (1160 A12) --verify's IDENTITY_FAILED names the file", code(got) == "IDENTITY_FAILED" and "file 'a.csv' -> 'a.csv'" in str(got.evidence), str(got))

# ---- V6. structure
spec = CT["fields"]["file"]["fields"]["steps"]
check("V6. OPS is total over [op], and [op] names the steps VARIANT's ops", set(ic.OPS) == set(CT["op"]) == set(spec["variants"]), f"{sorted(ic.OPS)} {sorted(CT['op'])}")
rules = {"DROP_LINES": ic.DROP, "NAMES_LINE": ic.NAMES, "SPLIT_ROWS": ic.SPLITS}
check("V6. each rule table is total over its kinds (DROP, NAMES, SPLITS)", all(set(t) == set(spec["variants"][op]["rule"]["variants"]) for op, t in rules.items()))
check("V6. SPLIT (DELIMITER) is total over its from values", set(ic.SPLIT) == set(spec["variants"]["DELIMITER"]["from"]["values"]))
check("V6. every op's stage and gives are stages of LEVEL; DEFAULT holds one step per stage before NAMED",
      all(r["stage"] in ic.LEVEL and r["gives"] in ic.LEVEL for r in CT["op"].values()) and [CT["op"][s["op"]]["stage"] for s in ic.DEFAULT] == ["RAW", "TEXT", "TABLE"])
tree = ast.parse((ROOT / "cc" / "intake_convert.py").read_text())
where = {}
for f in [x for x in tree.body if isinstance(x, ast.FunctionDef)]:   # module-level functions (a nested def counts as its outer function)
    for c in ast.walk(f):
        {True: lambda: where.setdefault(c.func.id, set()).add(f.name), False: lambda: None}[isinstance(c, ast.Call) and isinstance(c.func, ast.Name) and c.func.id in ("float", "int")]()
check("V6. float is called in _same only and int in peek_cli only (a cell is str end to end)", where == {"float": {"_same"}, "int": {"peek_cli"}}, str(where))
emitted = {c.args[0].value for c in ast.walk(tree) if isinstance(c, ast.Call) and isinstance(c.func, ast.Name) and c.func.id == "Refuse" and c.args and isinstance(c.args[0], ast.Constant)}
emitted |= {t.elts[1].value for t in ast.walk(tree) if isinstance(t, ast.Tuple) and len(t.elts) == 3 and isinstance(t.elts[1], ast.Constant) and isinstance(t.elts[1].value, str)}
emitted |= set(ic.XLSX_REASON.values())
emitted |= {c.value for a in ast.walk(tree) if isinstance(a, ast.Assign) and any(getattr(x, "id", "") == "cmap" for x in a.targets) for c in [a.value]}
check("V6. every reason the module emits is a row of intake/CONVERSION.toml", emitted <= ROWS and len(emitted) > 10, str(sorted(emitted - ROWS)))
doc = (ROOT / "docs" / "INTAKE-CONVERSION.md").read_text()
check("V6. docs/INTAKE-CONVERSION.md carries the rule verbatim and a worked example for every op",
      "a conversion is not allowed to change a number; if your deposit needs one changed, the Compass cannot take it" in doc and all(f"### {op}" in doc for op in CT["op"]),
      str([op for op in CT["op"] if f"### {op}" not in doc]))

print("test_intake_convert: " + ("FAILED " + "; ".join(bad) if bad else "all passed"))
sys.exit(1 if bad else 0)
