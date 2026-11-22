"""intake_differs - what a selected file differs from the first file in (plan 1160 A34; role `intake_differs` with its own line cap,
tests/test_budget.py DIFFERS_CAP, so the core cap is not raised). S5 FILE_DIFFERS_FROM_FIRST names one member of DIFFERS per refused file.
Invariant (value-free): it reads the pinned bytes S5 already holds, through the reader's own cell layer (intake_read.CELLS); it compares a
names line with the first file's and returns a member of DIFFERS, never a cell, so no name and no value leaves it."""
from intake_read import CELLS, CSV_CURVE, HEADER, SPLIT, Unreadable, _blank, _name

DIFFERS = {   # what a selected file differs from the first file in -> the words its Detail prints (never a name); total, in test order
    "ENCODING": "its bytes do not read as the declared format (text that is not UTF-8; no workbook, or no such sheet)",
    "DELIMITER": "its names line splits into the first file's number of cells under another delimiter, not the declared one",
    "COLUMN_COUNT": "its names line holds another number of cells",
    "NAMES_LINE": "its names line holds as many cells as the first file's, with other names",
    "ROWS": "its names line is the first file's; a row of it does not read (a reader reason of S4)",   # the residue: the four above all fail
}
SPEC = {"csv-curve-v1": lambda d: CSV_CURVE, "table-curve-v1": lambda d: d["reader"]}   # a live reader -> its cell spec (S4 refused the rest)


def _line(data, spec, kind, at):
    """The cells of the `at`-th non-blank line under format `kind`, as names; None when that format's cell layer refuses the bytes."""
    cells = CELLS[kind](data, spec)
    return None if isinstance(cells, Unreadable) else tuple(_name(x) for x in dict(enumerate(c for _, c in cells if not all(_blank(x) for x in c))).get(at, ()))


def lined(data, d):
    """A file's names line (the first non-blank line when the header names none) as cells under the reader's own format, None when that
    format's cell layer refuses the bytes; and the cell counts under each other text format."""
    spec = SPEC[d["reader"]["name"]](d)
    at, kind = HEADER[spec["header"]["kind"]](spec["header"]).get("names", 1) - 1, spec["format"]["kind"]   # SKIP names no line: the first
    return _line(data, spec, kind, at), tuple(len(x) for x in (_line(data, spec, k, at) for k in SPLIT if k != kind) if x is not None)


def differs(first, other, d):
    """The member of DIFFERS the file `other` holds against `first` (each a pinned file's bytes): the first member whose test holds. ROWS
    holds when none of the others does, so the lookup is total over every file S5 refuses."""
    (a, _), (b, alt) = lined(first, d), lined(other, d)
    test = {"ENCODING": lambda: b is None, "DELIMITER": lambda: len(b) != len(a) and len(a) in alt, "COLUMN_COUNT": lambda: len(b) != len(a),
            "NAMES_LINE": lambda: b != a, "ROWS": lambda: True}
    return next(k for k in DIFFERS if test[k]())
