"""intake_read - the readers of the intake: a file's bytes and the declaration to a Grid or an Unreadable (csv-curve-v1;
table-curve-v1). Invariant: a reader never opens a path (S3 SOURCE_INTEGRITY read the bytes once, through the logged loader); a value is a
cell exactly as written (no unit conversion, no NaN, no filling, no skipped row); every way a file cannot be read is an Unreadable whose
`reason` is a `reader_reason` code of S4 in intake/STAGES.toml, with its row and column in a Detail. The one place a decode error or an
xlsx parse error becomes a value is `_text` and `_xlsx_cells`.
Reading, in order (table-curve-v1; csv-curve-v1 is the same reader with a fixed declaration, see CSV_CURVE):
  1. cells: text formats are decoded as UTF-8 (a leading byte-order mark is not a cell) and split into lines; a line that starts with a
     declared comment prefix is dropped; each other line is split into cells (COMMA and TAB as CSV fields, WHITESPACE on runs of white
     space). XLSX: the declared sheet's rows; a row whose first cell is text starting with a comment prefix is dropped.
  2. a row with no cell, or whose every cell is blank, is no row (a blank line holds no value);
  3. the first `rows` rows are the header (HEADER_LINE_ABSENT when there are fewer, or the names or units line is not among them);
  4. the width is the names line's when there is one, else the first data row's; every data row has that width (ROW_WIDTH_DIFFERS);
  5. each declared column (a name, looked up in the names line; or a 1-based position) is resolved (COLUMN_NAME_ABSENT,
     COLUMN_NAME_AMBIGUOUS, COLUMN_POSITION_OUT_OF_RANGE);
  6. every cell of a declared column is a number (CELL_NOT_A_NUMBER): text that is a decimal number, or a numeric xlsx cell."""
import csv
import functools
import importlib.util
import io
from dataclasses import dataclass, field

from intake_blind import NUMBER, Detail, detail, gate
from intake_names import split_unit


@dataclass(frozen=True)
class Grid:
    """A file a reader could read. Invariant: `columns` is the column of each cell of a row (table-curve-v1: the declared column of each
    role, in role order; csv-curve-v1: its header line); every row of `rows` holds one float per column, in file order; `units` holds the
    (role, unit) pairs the file states (a NAMES_UNITS header, or NAMES_UNITS_IN_NAMES: "" for a names cell with no unit), () when it
    states none; `head` holds the header lines as read, each a tuple of
    cell texts (the one place a FILE_KEY slow value is found, see keyed), and takes no part in comparing two Grids."""
    columns: tuple
    units: tuple
    rows: tuple
    head: tuple = field(compare=False)
    readable = True


@dataclass(frozen=True)
class Unreadable:
    """A file a reader cannot read. Invariant: `reason` is a reader_reason code of S4 (intake/STAGES.toml); it holds no row, no column and no
    unit, and `readable` is False, so S4 refuses READER_REFUSED and S5 FILE_DIFFERS_FROM_FIRST before any column is compared."""
    reason: str
    detail: Detail
    columns = ()
    units = ()
    rows = ()
    head = ()
    readable = False


def role_columns(d):
    """The (role, declared column) pairs of a declaration, in role order: fast, measured, the uncertainty column when one is declared, the
    replicate column when [replicate.key] is a COLUMN (plan 1160 A33), the slow column of a LONG_TABLE (always last). Every reader's Grid
    holds its rows in this order (csv-curve-v1: S4 checks its header equals these columns)."""
    unc = {"COLUMN": lambda u: (("uncertainty", u["key"]),), "NONE": lambda u: ()}[d["measured"]["uncertainty"]["kind"]](d["measured"]["uncertainty"])
    rep = {"COLUMN": lambda k: (("replicate", k["column"]),), "FILE_NAME": lambda k: (), "NONE": lambda k: ()}[d["replicate"]["key"]["kind"]](d["replicate"]["key"])
    slow = {"PER_FILE": lambda s: (), "LONG_TABLE": lambda s: (("slow", s["slow"]["key"]),)}[d["selection"]["layout"]](d["selection"])
    return (("fast", d["knobs"]["fast"]["key"]), ("measured", d["measured"]["key"])) + unc + rep + slow


first = functools.partial(gate, refuse=Unreadable)   # gate for readers: the first failing row's Unreadable, else then()


# ---- 1. cells
def _text(data):
    """(decoded, the text or Unreadable NOT_UTF8): the one place a decode error becomes a value (its byte offset, never the byte)."""
    try:
        return True, data.decode("utf-8-sig")
    except UnicodeDecodeError as e:
        return False, Unreadable("NOT_UTF8", detail(counts={"byte offset": e.start}))


SPLIT = {   # a text format -> one line to its cells; total over the text kinds of FORMAT [reader.format]
    "COMMA": lambda ln: next(csv.reader([ln], delimiter=",")),
    "TAB": lambda ln: next(csv.reader([ln], delimiter="\t")),
    "WHITESPACE": lambda ln: ln.split(),
}


def _comment(cell, prefixes):
    return isinstance(cell, str) and any(cell.startswith(p) for p in prefixes)


def _text_cells(kind):
    """A text format's cells: [(line number, cells)] of every line that is not a comment line, or Unreadable NOT_UTF8."""
    def cells(data, spec):
        ok, text = _text(data)
        return {False: lambda: text,
                True: lambda: [(i, SPLIT[kind](ln)) for i, ln in enumerate(text.splitlines(), 1) if not _comment(ln, spec["comment"])]}[ok]()
    return cells


def _xlsx_cells(data, spec):
    """XLSX through openpyxl (installed: the key of the XLSX table below): the declared sheet's rows, or Unreadable NOT_AN_XLSX | SHEET_ABSENT.
    The sheet is a name (str) or a 1-based position (int; plan 1160 A21), looked up in one address table of both: an int never equals a str.
    openpyxl parses a read-only sheet lazily, so the rows are drawn inside the one decoding boundary: a workbook whose cells do not parse is
    NOT_AN_XLSX, never an exception later."""
    import openpyxl
    sheet = spec["format"]["sheet"]
    try:   # the decoding boundary: openpyxl raises zipfile, KeyError, ValueError and its own errors for bytes that are no readable workbook
        book = openpyxl.load_workbook(io.BytesIO(data), read_only=True, data_only=True)
        address = {**dict(enumerate(book.sheetnames, 1)), **{n: n for n in book.sheetnames}}   # position or name -> the sheet's name
        rows = {True: lambda: list(book[address[sheet]].iter_rows(values_only=True)), False: lambda: []}[sheet in address]()
    except Exception as e:
        return Unreadable("NOT_AN_XLSX", detail(words=[type(e).__name__]))   # the error's type only: its message can quote a cell
    return {False: lambda: Unreadable("SHEET_ABSENT", detail(words=[f"sheet '{sheet}'"], counts={"sheets in the workbook": len(book.sheetnames)})),
            True: lambda: [(i, list(r)) for i, r in enumerate(rows, 1) if not (len(r) > 0 and _comment(r[0], spec["comment"]))]}[sheet in address]()


XLSX = {   # is openpyxl installed -> the xlsx cell reader (xlsx is read with openpyxl or not at all)
    True: _xlsx_cells,
    False: lambda data, spec: Unreadable("XLSX_READER_ABSENT", detail(words=["openpyxl is not installed on this machine, so an xlsx file cannot be read here"])),
}
CELLS = {   # [reader.format] kind -> (bytes, the reader's declaration) -> [(row number, cells)] | Unreadable; total over FORMAT's kinds
    "COMMA": _text_cells("COMMA"), "TAB": _text_cells("TAB"), "WHITESPACE": _text_cells("WHITESPACE"),
    "XLSX": lambda data, spec: XLSX[importlib.util.find_spec("openpyxl") is not None](data, spec),
}


# ---- 2 to 6. rows, header, width, columns, numbers
NUMERIC = {   # the exact type of a cell -> (is it a number, its value); total by `look` below: a type with no row is not a number
    str: (lambda c: NUMBER.fullmatch(c.strip()) is not None, lambda c: float(c.strip())),
    int: (lambda c: True, float),
    float: (lambda c: c == c and abs(c) != float("inf"), float),
}
NOT_A_NUMBER = (lambda c: False, float)


def _numeric(c):
    return {True: lambda: NUMERIC[type(c)], False: lambda: NOT_A_NUMBER}[type(c) in NUMERIC]()


def _blank(cell):
    return cell is None or (isinstance(cell, str) and cell.strip() == "")


def _name(cell):
    return {True: lambda: cell.strip(), False: lambda: ""}[isinstance(cell, str)]()


SAID = {str: lambda c: c.strip(), int: repr, float: repr}   # a header cell's type -> its text as written (an xlsx number by repr); others: ""


def _said(cell):
    return {True: lambda: SAID[type(cell)](cell), False: lambda: ""}[type(cell) in SAID]()


def keyed(grid, key):
    """FILE_KEY: the second cell of each header line of a Grid whose first cell is `key`, as text. The census refuses
    SLOW_KEY_UNRESOLVED unless this is exactly one decimal number as written."""
    return [c[1] for c in grid.head if len(c) > 1 and c[0] == key]


HEADER = {   # [reader.header] kind -> (the 1-based header lines it names: names, units); total over FORMAT's header kinds
    "SKIP": lambda h: {},
    "NAMES": lambda h: {"names": h["names"]},
    "NAMES_UNITS": lambda h: {"names": h["names"], "units": h["units"]},
    "NAMES_UNITS_IN_NAMES": lambda h: {"names": h["names"]},   # the units are inside the names line (NAMED)
}
NAMED = {   # [reader.header] kind -> (its row, the cells of each line HEADER names) -> the names and the units the file states; total (test)
    **{k: (lambda h, lined: lined) for k in ("SKIP", "NAMES", "NAMES_UNITS")},
    "NAMES_UNITS_IN_NAMES": lambda h, lined: dict(zip(("names", "units"), map(list, zip(*[split_unit(c, h["unit_syntax"]) for c in lined["names"]])))),
}


def _resolve(ref, names, width):
    """A declared column to its 0-based index: a name looked up in the names line, or a 1-based position. (holds, reason, detail) rows."""
    by = {str: lambda: [(lambda: names.count(ref) > 0, "COLUMN_NAME_ABSENT", lambda: detail(columns=[ref], counts={"names in the names line": len(names)})),
                        (lambda: names.count(ref) < 2, "COLUMN_NAME_AMBIGUOUS", lambda: detail(columns=[ref], counts={"columns it names": names.count(ref)}))],
          int: lambda: [(lambda: 1 <= ref <= width, "COLUMN_POSITION_OUT_OF_RANGE", lambda: detail(columns=[ref], counts={"columns in the table": width}))]}
    return by[type(ref)]()


def _index(ref, names):
    return {str: lambda: names.index(ref), int: lambda: ref - 1}[type(ref)]()


def table(cells, spec, roles):
    """Steps 2 to 6 over [(row number, cells)]: Grid(declared columns, stated units, rows in role order) | Unreadable. `roles` is a function of
    the header rows, called only once the header is there (csv-curve-v1's roles are its header)."""
    rows = [(i, c) for i, c in cells if not all(_blank(x) for x in c)]
    h, lines = spec["header"], HEADER[spec["header"]["kind"]](spec["header"])
    head, body = rows[:h["rows"]], rows[h["rows"]:]
    return first([(lambda: len(head) == h["rows"] and all(1 <= n <= h["rows"] for n in lines.values()), "HEADER_LINE_ABSENT",
                   lambda: detail(rows=lines.values(), counts={"header lines": len(head), "header lines declared": h["rows"]})),
                  (lambda: len(body) > 0, "NO_DATA_ROW", lambda: detail(counts={"header lines": len(head), "data rows": 0}))],
                 lambda: _columns(head, body, lines, roles(head), h))


def _columns(head, body, lines, roles, h):
    named = NAMED[h["kind"]](h, {k: [_name(x) for x in head[n - 1][1]] for k, n in lines.items()})
    names = {True: lambda: named["names"], False: lambda: []}["names" in named]()
    width = {True: lambda: len(head[lines["names"] - 1][1]), False: lambda: len(body[0][1])}["names" in lines]()
    short = [(i, len(c)) for i, c in body if len(c) != width]
    checks = [(lambda: not short, "ROW_WIDTH_DIFFERS", lambda: detail(rows=[short[0][0]], counts={"cells in the row": short[0][1], "table width": width}))]
    checks += [row for _, ref in roles for row in _resolve(ref, names, width)]
    return first(checks, lambda: _numbers(body, named, roles, names, tuple(tuple(_said(x) for x in c) for _, c in head)))


def _numbers(body, named, roles, names, head):
    at = [_index(ref, names) for _, ref in roles]
    bad = [(i, ref) for i, c in body for (_, ref), k in zip(roles, at) if not _numeric(c[k])[0](c[k])]
    units = {True: lambda: tuple((r, named["units"][k]) for (r, _), k in zip(roles, at)), False: lambda: ()}["units" in named]()
    return first([(lambda: not bad, "CELL_NOT_A_NUMBER", lambda: detail(rows=[bad[0][0]], columns=[bad[0][1]], counts={"cells of declared columns that are not numbers": len(bad)}))],
                 lambda: Grid(tuple(ref for _, ref in roles), units, tuple(tuple(_numeric(c[k])[1](c[k]) for k in at) for _, c in body), head))


def read_table(data, d):
    """table-curve-v1: the declared format, comment prefixes, header and columns (role_columns) to a Grid | Unreadable."""
    spec = d["reader"]
    cells = CELLS[spec["format"]["kind"]](data, spec)
    return {True: lambda: cells, False: lambda: table(cells, spec, lambda head: role_columns(d))}[isinstance(cells, Unreadable)]()


CSV_CURVE = {"comment": [], "format": {"kind": "COMMA"}, "header": {"kind": "NAMES", "rows": 1, "names": 1}}


def read_csv(data, d):
    """csv-curve-v1: table-curve-v1 with a fixed declaration (comma, no comment prefix, one header line of names) whose columns are
    the WHOLE header, in its order: its Grid's columns are the header, which S4 compares with the declared columns (COLUMNS_DIFFER)."""
    cells = CELLS["COMMA"](data, CSV_CURVE)
    whole = lambda head: tuple((n, n) for n in (_name(x) for x in head[0][1]))
    return {True: lambda: cells, False: lambda: table(cells, CSV_CURVE, whole)}[isinstance(cells, Unreadable)]()


def readers(t):
    """The reader of each FORMAT [reader] name: csv-curve-v1 and table-curve-v1 are live; every other name reads to Unreadable
    READER_NOT_LIVE (S4 refuses READER_NOT_LIVE first, from LIVE below). Total over FORMAT's reader names."""
    return {**{r: (lambda data, d, r=r: Unreadable("READER_NOT_LIVE", detail(words=[f"reader '{r}' has no body yet"]))) for r in t["format"]["fields"]["reader"]["variants"]},
            "csv-curve-v1": read_csv, "table-curve-v1": read_table}


LIVE = ("csv-curve-v1", "table-curve-v1")
