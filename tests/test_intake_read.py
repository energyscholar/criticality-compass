"""test_intake_read - plan 1145 phase 1: the reader table-curve-v1 (cc/intake_read.py) on planted files only. Each check was seen RED under a
stated mutation (the plan-1145 report lists them).
 R1. Each format (comma, tab, whitespace, xlsx) reads one planted table to the same Grid: the same columns, units and rows. Comment lines and
     blank lines are dropped; columns by NAME and by 1-based POSITION read the same rows; csv-curve-v1 reads the comma file to the same rows.
     xlsx: with openpyxl installed, the same Grid; without it, Unreadable XLSX_READER_ABSENT (a named reason, never an exception).
 R2. Each Unreadable case refuses with its reason_code and names its row and column: a cell that is not a number (and "nan", and an empty
     cell: no NaN filling, no skipped row), a short row, a missing column name, a position out of range; plus a name that names two columns,
     too few header lines, no data row, bytes that are not UTF-8, and (with openpyxl) a missing sheet and bytes that are no workbook.
 R3. Values exactly as written: no unit conversion, no rounding beyond float parsing, rows in file order (a descending file stays descending).
 R4. Every reason an Unreadable can carry is a reader_reason row of S4 in intake/STAGES.toml, and every reader is a FORMAT [reader] row."""
import ast
import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path[:0] = [str(ROOT / "cc"), str(ROOT / "tests")]
import intake  # noqa: E402
import intake_read as rd  # noqa: E402
from intake_plant import xlsx  # noqa: E402

bad = []


def check(name, ok, why=""):
    print(("ok   " if ok else "FAIL ") + name + ("" if ok else f": {why}"))
    if not ok:
        bad.append(name)


T = intake.tables(ROOT)
HAS_XLSX = importlib.util.find_spec("openpyxl") is not None
ROWS = [(2.5, 0.75, 0.03), (2.25, 1.125, 0.03), (2.0, 0.5, 0.025)]   # descending in T on purpose (R3)
NAMES, UNITS = ["T", "C", "sigma"], ["K", "J/K", "J/K"]


def decl(fmt, header, cols=("T", "C", "sigma"), comment=("#",), layout="PER_FILE"):
    """A declaration's data, only the fields a reader reads (the reader, the role columns): planted, never parsed from TOML here."""
    unc = {True: {"kind": "NONE"}, False: {"kind": "COLUMN", "key": cols[2:3] and cols[2]}}[len(cols) < 3]
    sel = {"PER_FILE": {"layout": "PER_FILE"}, "LONG_TABLE": {"layout": "LONG_TABLE", "slow": {"source": "COLUMN", "key": cols[-1]}}}[layout]
    return {"reader": {"name": "table-curve-v1", "comment": list(comment), "format": fmt, "header": header},
            "knobs": {"fast": {"key": cols[0]}, "slow": {"unit": "T"}}, "measured": {"key": cols[1], "unit": "J/K", "uncertainty": unc}, "selection": sel}


def text(sep, rows=ROWS, head=(NAMES, UNITS), pre="# a planted table (plan 1145)\n", blank="\n"):
    return (pre + "".join(sep.join(h) + "\n" for h in head) + blank + "".join(sep.join(f"{x:g}" for x in r) + "\n" for r in rows)).encode()


def aligned():
    """The planted table as a .dat file: columns padded to width 10, a leading indent, a tab in one line (runs of white space of any length)."""
    lines = [NAMES, UNITS] + [[f"{x:g}" for x in r] for r in ROWS]
    return ("# a planted table (plan 1145)\n" + "".join("  " + "".join(c.ljust(10) for c in ln).rstrip() + "\n" for ln in lines).replace("  2.25", "\t2.25")).encode()


NU = {"kind": "NAMES_UNITS", "rows": 2, "names": 1, "units": 2}
WANT = rd.Grid(("T", "C", "sigma"), (("fast", "K"), ("measured", "J/K"), ("uncertainty", "J/K")), tuple(ROWS))

# ---- R1. each format reads one planted table to the same Grid
got = {
    "COMMA": rd.read_table(text(","), decl({"kind": "COMMA"}, NU)),
    "TAB": rd.read_table(text("\t"), decl({"kind": "TAB"}, NU)),
    "WHITESPACE": rd.read_table(aligned(), decl({"kind": "WHITESPACE"}, NU)),
}
for k, g in got.items():
    check(f"R1. {k} reads the planted table to the expected Grid (columns, stated units, rows)", g == WANT, str(g)[:300])
xl = rd.read_table(xlsx([["# a planted table (plan 1145)"], NAMES, UNITS, [None, None, None]] + [list(r) for r in ROWS]), decl({"kind": "XLSX", "sheet": "data"}, NU))
check({True: "R1. XLSX (openpyxl installed) reads the planted workbook to the same Grid",
       False: "R1. XLSX without openpyxl is Unreadable XLSX_READER_ABSENT (a named reason)"}[HAS_XLSX],
      {True: lambda: xl == WANT, False: lambda: isinstance(xl, rd.Unreadable) and xl.reason == "XLSX_READER_ABSENT"}[HAS_XLSX](), str(xl)[:300])
print(f"  openpyxl installed: {HAS_XLSX}")
pos = rd.read_table(text(" ", head=()), decl({"kind": "WHITESPACE"}, {"kind": "SKIP", "rows": 0}, cols=(1, 2, 3)))
check("R1. columns by 1-based POSITION (no header) read the same rows", isinstance(pos, rd.Grid) and pos.rows == WANT.rows and pos.columns == (1, 2, 3) and pos.units == (), str(pos)[:300])
mixed = rd.read_table(text(","), decl({"kind": "COMMA"}, NU, cols=("T", 2, "sigma")))
check("R1. a name and a position in one declaration read the same rows", isinstance(mixed, rd.Grid) and mixed.rows == WANT.rows, str(mixed)[:300])
picked = rd.read_table(text(",", rows=[r + (9.0,) for r in ROWS], head=(NAMES + ["extra"], UNITS + ["s"])), decl({"kind": "COMMA"}, NU))
check("R1. only the declared columns are read, in role order (an undeclared column is not read)", picked == WANT, str(picked)[:300])
swapped = rd.read_table(text(",", rows=[(r[1], r[0], r[2]) for r in ROWS], head=(["C", "T", "sigma"], ["J/K", "K", "J/K"])), decl({"kind": "COMMA"}, NU))
check("R1. columns found by name in another order read to the same Grid (role order: fast, measured, uncertainty)", swapped == WANT, str(swapped)[:300])
csvc = rd.read_csv(text(",", head=(NAMES,), pre="", blank=""), {})
check("R1. csv-curve-v1 reads the plain comma file (one header line) to the same rows, its columns the header", isinstance(csvc, rd.Grid) and csvc.rows == WANT.rows and csvc.columns == tuple(NAMES), str(csvc)[:300])
none = rd.read_table(text(","), decl({"kind": "COMMA"}, NU, cols=("T", "C")))
check("R1. uncertainty NONE: the Grid holds fast and measured only", isinstance(none, rd.Grid) and none.rows == tuple(r[:2] for r in ROWS), str(none)[:300])

# ---- R2. each Unreadable case refuses with its reason and names its row and column
def refused(name, g, reason, *where):
    check(f"R2. {name}: Unreadable {reason}" + (f", naming {where}" if where else ""),
          isinstance(g, rd.Unreadable) and g.reason == reason and all(w in str(g.detail) for w in where) and g.rows == (), str(g)[:300])


c = lambda **k: decl({"kind": "COMMA"}, NU, **k)
refused("a cell that is not a number", rd.read_table(text(",").replace(b"1.125", b"1.1x5"), c()), "CELL_NOT_A_NUMBER", "row 6", "'C'")
refused("a cell 'nan' (no NaN filling)", rd.read_table(text(",").replace(b"0.025", b"nan"), c()), "CELL_NOT_A_NUMBER", "row 7", "'sigma'")
refused("an empty cell of a declared column (no filling, no skipped row)", rd.read_table(text(",").replace(b"2.25,1.125", b"2.25,"), c()), "CELL_NOT_A_NUMBER", "row 6", "'C'")
refused("a short row", rd.read_table(text(",").replace(b",0.03\n2.25", b"\n2.25"), c()), "ROW_WIDTH_DIFFERS", "row 5")
refused("a missing column name", rd.read_table(text(","), c(cols=("T", "Cp", "sigma"))), "COLUMN_NAME_ABSENT", "'Cp'")
refused("a position out of range", rd.read_table(text(","), c(cols=("T", 4, "sigma"))), "COLUMN_POSITION_OUT_OF_RANGE", "column #4", "columns in the table = 3")
refused("position 0 (positions are 1-based)", rd.read_table(text(","), c(cols=(0, "C", "sigma"))), "COLUMN_POSITION_OUT_OF_RANGE", "column #0")
refused("a name that names two columns", rd.read_table(text(",", head=(["T", "C", "C"], UNITS)), c()), "COLUMN_NAME_AMBIGUOUS", "'C'")
refused("a name with no names line (SKIP)", rd.read_table(text(","), decl({"kind": "COMMA"}, {"kind": "SKIP", "rows": 2})), "COLUMN_NAME_ABSENT", "'T'")
refused("fewer header lines than declared", rd.read_table(text(",", rows=[]), decl({"kind": "COMMA"}, {**NU, "rows": 3})), "HEADER_LINE_ABSENT", "header lines = 2", "header lines declared = 3")
refused("a names line outside the header", rd.read_table(text(","), decl({"kind": "COMMA"}, {**NU, "names": 3})), "HEADER_LINE_ABSENT")
refused("a header and no data row", rd.read_table(text(",", rows=[]), c()), "NO_DATA_ROW")
refused("bytes that are not UTF-8", rd.read_table(b"T,C,sigma\n\xff\xfe2.0,1.0,0.1\n", c()), "NOT_UTF8")
refused("a comment line not declared as one (it becomes header line 1: the names line is one cell wide)", rd.read_table(text(","), c(comment=())), "ROW_WIDTH_DIFFERS", "table width = 1")
xl_ok = {True: lambda: None, False: lambda: print("  (the xlsx SHEET_ABSENT and NOT_AN_XLSX cases need openpyxl: not run on this machine)")}[HAS_XLSX]()
{True: lambda: [refused("an xlsx sheet that is absent", rd.read_table(xlsx([NAMES, UNITS] + [list(r) for r in ROWS], sheet="other"), decl({"kind": "XLSX", "sheet": "data"}, NU)), "SHEET_ABSENT", "'data'"),
                refused("bytes that are no workbook", rd.read_table(b"PK not a zip", decl({"kind": "XLSX", "sheet": "data"}, NU)), "NOT_AN_XLSX"),
                refused("an xlsx number cell whose text does not parse (openpyxl reads rows lazily)", rd.read_table(xlsx([NAMES, UNITS, [2.5, b"x0.75", 0.03]]), decl({"kind": "XLSX", "sheet": "data"}, NU)), "NOT_AN_XLSX", "ValueError"),
                refused("an xlsx text cell in a number column", rd.read_table(xlsx([NAMES, UNITS, [2.5, "n/a", 0.03]]), decl({"kind": "XLSX", "sheet": "data"}, NU)), "CELL_NOT_A_NUMBER", "row 3", "'C'")],
 False: lambda: None}[HAS_XLSX]()

# ---- R3. values exactly as written
odd = rd.read_table(b"T,C,sigma\nK,J/K,J/K\n2.50,1e-3,+.5\n-0.0,1E3,7\n", c(comment=()))
check("R3. a value is its cell as written: 2.50 -> 2.5, 1e-3, +.5, -0.0, 1E3, 7 (no conversion, no unit change)",
      isinstance(odd, rd.Grid) and odd.rows == ((2.5, 0.001, 0.5), (-0.0, 1000.0, 7.0)), str(odd)[:300])
check("R3. rows in file order (the descending planted file stays descending)", got["COMMA"].rows[0][0] > got["COMMA"].rows[-1][0], "")
check("R3. stated units are the header's, not converted", got["COMMA"].units == WANT.units, str(got["COMMA"].units))

# ---- R4. reasons and readers are table rows
s4 = next(s for s in T["stages"]["stage"] if s["id"] == "S4")
tree = ast.parse((ROOT / "cc" / "intake_read.py").read_text())
emitted = ({n.args[0].value for n in ast.walk(tree) if isinstance(n, ast.Call) and getattr(n.func, "id", "") == "Unreadable" and isinstance(n.args[0], ast.Constant)}
           | {n.elts[1].value for n in ast.walk(tree) if isinstance(n, ast.Tuple) and len(n.elts) == 3 and isinstance(n.elts[1], ast.Constant) and isinstance(n.elts[1].value, str)
              and isinstance(n.elts[0], ast.Lambda)})   # an Unreadable(reason, ...) call, or a (holds, reason, detail) row of `first`
rows = {r["code"] for r in s4["reader_reason"]}
check("R4. every reason intake_read emits is a reader_reason row of S4", emitted - {"READER_NOT_LIVE"} <= rows, str(sorted(emitted - rows)))
check("R4. every reader_reason row of S4 is emitted by intake_read", rows <= emitted, str(sorted(rows - emitted)))
check("R4. the reader table is total over FORMAT's [reader] names", set(rd.readers(T)) == set(T["format"]["fields"]["reader"]["variants"]), "")
check("R4. the live readers are csv-curve-v1 and table-curve-v1, and every other reader reads to READER_NOT_LIVE",
      set(rd.LIVE) == {"csv-curve-v1", "table-curve-v1"} and all(rd.readers(T)[r](b"", {}).reason == "READER_NOT_LIVE" for r in rd.readers(T) if r not in rd.LIVE), "")

print("test_intake_read: " + ("FAILED " + "; ".join(bad) if bad else "all passed"))
sys.exit(1 if bad else 0)
