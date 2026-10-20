"""intake_profile - pre-processing (plan 1165; role intake_profile, its own line cap tests/test_budget.py PROFILE_CAP): `bin/cc intake profile`
reads every byte of every file under a root-named path, before any declaration is written, and reduces them to a PROFILE of their
structure. Invariants:
 - value-free BY TYPE: every field of Profile, FileProfile, Table, RowRun, HeaderLine, ColumnProfile and Finding is an int, a str that is a
   file name, a sha256, an enum atom or a masked name (intake_names.masked: every numeral as #; a NUMERIC cell as its position #k), or a tuple
   of these; no float, and no str that receives a cell's text unmasked. A value is held in memory to count runs, never kept;
 - every file is read once through the vendored t23 logged loader, partition "profiled", into declarations/<id>/profile-access.log;
   nothing is written under the profiled path;
 - a finding is a row of FindingKind and its response is looked up in RESPONSE, total over FindingKind (tests/test_intake_profile.py)."""
import enum
import functools
import importlib.util
import hashlib
import itertools
import json
import re
from collections import Counter
from dataclasses import asdict, dataclass
from pathlib import Path

import intake_bytes
from intake_blind import detail, gate
from intake_convert import SPLIT, _book_names, _decoded, _split, _zipped, sheet_rows
from intake_names import NUMBER, Name, _runs, classify, masked, repeats

FileKind = enum.Enum("FileKind", "TEXT_TABLE XLSX ZIP UNPROFILED_FORMAT")   # by content, never by extension (plan 1165 2.2)
Encoding = enum.Enum("Encoding", "UTF8 UTF8_SIG UTF16 LATIN1_ONLY UNDECODABLE")
Delimiter = enum.Enum("Delimiter", "COMMA SEMICOLON TAB WHITESPACE NONE")   # the election's tie order is this order
RowKind = enum.Enum("RowKind", "BLANK NUMERIC NUMERIC_WITH_EMPTY TEXT")
FindingKind = enum.Enum("FindingKind", "ENCODING_NOT_UTF8 BOM_PRESENT DELIMITER_NOT_COMMA NO_DELIMITER HEADER_LINES_BEFORE_NAMES NAMES_LINE_ABSENT "
                        "NAMES_LINE_NUMERIC COMMENT_LINES TEXT_RUN_IN_BODY TEXT_RUN_TRAILING TEXT_CELLS_IN_COLUMN EMPTY_CELLS_IN_COLUMN WIDTH_CHANGES "
                        "COLUMNS_DIFFER_ACROSS_FILES NOT_MONOTONE DIRECTION_DESCENDING EQUAL_RUNS_SHORT EQUAL_RUN_LONG REVISITED_VALUES XLSX_SHEETS "
                        "ZIP_MEMBERS UNPROFILED_FORMAT LARGE_FILE ONE_FILE")
Response = enum.Enum("Response", "CONVERT DECLARE BLOCKS REFUSE_DEPOSIT NONE")
Contradiction = enum.Enum("Contradiction", "FILE_NOT_PROFILED ENCODING_CONTRADICTS_PROFILE DELIMITER_CONTRADICTS_PROFILE HEADER_CONTRADICTS_PROFILE "
                          "COLUMN_CONTRADICTS_PROFILE CELLS_CONTRADICT_PROFILE WIDTH_CONTRADICTS_PROFILE ORDER_CONTRADICTS_PROFILE "
                          "REPEATS_CONTRADICT_PROFILE SHEET_CONTRADICTS_PROFILE FILES_CONTRADICT_PROFILE")
C, R = Response, Contradiction
RESPONSE = {   # plan 1165 section 4: FindingKind -> (its one response, what it prints, the "or ..." it prints second, "" none); total (test)
    "ENCODING_NOT_UTF8": (C.CONVERT, "DECODE encoding = latin-1 / utf-16", ""),
    "BOM_PRESENT": (C.NONE, "the readers and DECODE's default strip it", ""),
    "DELIMITER_NOT_COMMA": (C.CONVERT, "DELIMITER from = the elected delimiter", "[reader.format] kind TAB / WHITESPACE, when the reader has it"),
    "NO_DELIMITER": (C.REFUSE_DEPOSIT, "NOT_A_TABLE", ""),
    "HEADER_LINES_BEFORE_NAMES": (C.CONVERT, "DROP_LINES MARKER / FIRST count = the lines before the names line", "[reader.header] rows = n"),
    "NAMES_LINE_ABSENT": (C.CONVERT, "NAMES_LINE WRITE names = ...", ""),
    "NAMES_LINE_NUMERIC": (C.CONVERT, "WIDE_TO_LONG key = ...", ""),
    "COMMENT_LINES": (C.DECLARE, "comment = [the prefix]", "DROP_LINES PREFIX"),
    "TEXT_RUN_IN_BODY": (C.BLOCKS, "SPLIT_ROWS RANGES at the run's lines; each NUMERIC run its own output (a curve)",
                         "DROP_LINES PREFIX, when every line of the run shares a comment prefix"),
    "TEXT_RUN_TRAILING": (C.BLOCKS, "SPLIT_ROWS RANGES ending at the last NUMERIC line", ""),
    "TEXT_CELLS_IN_COLUMN": (C.DECLARE, "another column, when another column has no text cell", "DROP_ROWS_NOT_NUMERIC (a lone TEXT cell; never a TEXT run)"),
    "EMPTY_CELLS_IN_COLUMN": (C.CONVERT, "DROP_ROWS_NOT_NUMERIC columns = [k] (a blank is a reading not taken, never a zero)", ""),
    "WIDTH_CHANGES": (C.BLOCKS, "SPLIT_ROWS RANGES where the widths bound blocks", "SELECT_COLUMNS, when the extra columns are trailing empties"),
    "COLUMNS_DIFFER_ACROSS_FILES": (C.DECLARE, "[selection] files per family, with SELECT_COLUMNS / RENAME to one names line", ""),
    "NOT_MONOTONE": (C.DECLARE, "[acquisition] row_order = ACQUISITION, direction = UNORDERED (a dithering knob)", "BLOCKS when the runs are sweeps (FAST_RESTART, or RANGES per run)"),
    "DIRECTION_DESCENDING": (C.DECLARE, "row_order = DESCENDING", ""),
    "EQUAL_RUNS_SHORT": (C.DECLARE, "[replicate] identity = SAME_FAST_VALUE", ""),
    "EQUAL_RUN_LONG": (C.BLOCKS, "the hold is a segment: RANGES around it, or excluded", ""),
    "REVISITED_VALUES": (C.DECLARE, "[knobs.fast] control = MEASURED", ""),
    "XLSX_SHEETS": (C.CONVERT, "SHEET_TO_CSV sheet = one of the sheets", "[reader.format] kind = XLSX, sheet = ..."),
    "ZIP_MEMBERS": (C.CONVERT, "UNPACK member = ... per member", ""),
    "UNPROFILED_FORMAT": (C.REFUSE_DEPOSIT, "NO_READER_FOR_FORMAT (the alphabet has no reader; the card's reader_needed says so)", ""),
    "LARGE_FILE": (C.NONE, "expect the conversion's cost", ""),
    "ONE_FILE": (C.DECLARE, "[selection] layout = LONG_TABLE, slow COLUMN from the column of fewest distinct values and longest equal runs", ""),
}
PREDICTS = {   # plan 1165 section 5: a live S4 / S4 reader / S5 reason a byte-level fact can raise -> the Contradiction that precedes it (test)
    "NOT_UTF8": R.ENCODING_CONTRADICTS_PROFILE, "ROW_WIDTH_DIFFERS": R.WIDTH_CONTRADICTS_PROFILE, "COLUMN_NAME_ABSENT": R.COLUMN_CONTRADICTS_PROFILE,
    "COLUMN_NAME_AMBIGUOUS": R.COLUMN_CONTRADICTS_PROFILE, "COLUMN_POSITION_OUT_OF_RANGE": R.COLUMN_CONTRADICTS_PROFILE,
    "CELL_NOT_A_NUMBER": R.CELLS_CONTRADICT_PROFILE, "HEADER_LINE_ABSENT": R.HEADER_CONTRADICTS_PROFILE, "NO_DATA_ROW": R.HEADER_CONTRADICTS_PROFILE,
    "SHEET_ABSENT": R.SHEET_CONTRADICTS_PROFILE, "COLUMNS_DIFFER": R.FILES_CONTRADICT_PROFILE, "ROW_ORDER_DIFFERS": R.ORDER_CONTRADICTS_PROFILE,
    "FILE_DIFFERS_FROM_FIRST": R.FILES_CONTRADICT_PROFILE, "FAST_VALUE_REPEATED": R.REPEATS_CONTRADICT_PROFILE, "ACQUISITION_ORDER_DIFFERS": R.ORDER_CONTRADICTS_PROFILE,
}
NOT_PREDICTABLE = {   # plan 1165 section 5: the live reasons no profile can precede, each with why (test: PREDICTS + this = every live S4, S5 reason)
    "CURVE_REPEATED": "a slow value's recurrence is a value fact, and the profile holds no value",
    "SLOW_KEY_UNRESOLVED": "a FILE_KEY slow value is a header cell's value, which the profile masks",
    "REPLICATE_KEY_UNRESOLVED": "a replicate key is a value of a file name field or a column, which the profile does not hold",
    "UNIT_DIFFERS": "a unit is compared as declared text; the profile masks every numeral in it",
    "NOT_AN_XLSX": "openpyxl's parse of the cells, not a structure the profile states",
    "XLSX_READER_ABSENT": "a fact of the machine that runs the reader, not of the files",
    "READER_NOT_LIVE": "a fact of the declaration's reader name, not of the files",
    "READER_REFUSED": "the wrapper of a reader reason; each reader reason has its own row",
}
CUT = {d: SPLIT[d] for d in ("COMMA", "SEMICOLON", "TAB", "WHITESPACE")}   # Delimiter -> one line to its cells, in the election's tie order (NONE:
# the line is one cell); the converter's own DELIMITER cuts, so a profile's widths are the widths DELIMITER from = d gives
ENCODINGS = (   # (Encoding, does it hold, DECODE's name): the first that holds decodes the file (plan 1165 2.2); a BOM is structure, read first
    ("UTF8_SIG", lambda r: r.startswith(b"\xef\xbb\xbf"), "utf-8-sig"), ("UTF16", lambda r: r[:2] in (b"\xff\xfe", b"\xfe\xff"), "utf-16"),
    ("UTF8", lambda r: True, "utf-8"), ("LATIN1_ONLY", lambda r: True, "latin-1"))   # latin-1 decodes every byte: LATIN1_ONLY is "not UTF-8"
BINARY = re.compile("[\x00-\x08\x0e-\x1f\x7f]")   # a decoded control character no text table holds: the bytes are a binary format
NUMERIC_KINDS = ("NUMERIC", "NUMERIC_WITH_EMPTY")
BIN = {2: 0, **{n: 1 for n in range(3, 10)}, 10: 2}   # an equal run's length (10 for 10 or more) -> its equal_runs bin (2, 3-9, 10+); a run of 1 none
DIRECTION = {None: "FLAT", True: "ASCENDING", False: "DESCENDING"}   # the first step of a column's numbers (equal values merged) -> first_direction
READER_ABSENT = "NONE_READER_ABSENT"   # an XLSX's `sheets` on a machine without openpyxl (XLSX_READER_ABSENT: the kind stays XLSX)
CLASSES = ("#", "%", ";", "//", "!", "[")   # comment prefix classes: a line's first characters (the reader's own test, startswith)


@dataclass(frozen=True)
class RowRun:
    """A run of lines of one (kind, width, comment prefix): `first` and `last` are 1-based file lines (a block boundary is a change of any)."""
    first: int
    last: int
    kind: str
    width: int
    prefix: str


@dataclass(frozen=True)
class HeaderLine:
    """A line before the first NUMERIC run, as cells: a TEXT cell masked, a NUMERIC one as its position #k, an empty one as ""."""
    line: int
    cells: tuple


@dataclass(frozen=True)
class ColumnProfile:
    """Position k of the dominant width over the body lines of that width: counts of cell classes, the lines of TEXT and empty cells
    (run-length encoded [first, last] pairs), and the order and repeats of its numbers (counts only; equal_runs = runs of 2, 3-9, 10+)."""
    position: int
    name: str
    numeric: int
    empty: int
    text: int
    text_lines: tuple
    empty_lines: tuple
    monotone_runs: int = 0
    first_direction: str = "FLAT"
    equal_runs: tuple = (0, 0, 0)
    longest: int = 0
    revisited: int = 0
    distinct: int = 0


@dataclass(frozen=True)
class Table:
    """One text file's (or one sheet's) cells: the elected delimiter and every delimiter's evidence ((width, lines) pairs), the line count,
    the blank lines (run-length encoded), the comment prefixes counted, the row runs, the header lines (at most 12) and the columns."""
    delimiter: str
    widths: tuple
    lines: int
    blank_lines: tuple
    comment_prefixes: tuple
    rows: tuple
    header_lines: tuple
    columns: tuple


@dataclass(frozen=True)
class FileProfile:
    """One file of the profiled path. `tables` holds its one Table (a TEXT_TABLE) or none; `sheets` (an XLSX) its sheets as
    (position, masked name, Table); `members` (a ZIP) (masked name, size) pairs."""
    name: str
    bytes: int
    sha256: str
    kind: str
    encoding: str
    tables: tuple = ()
    sheets: object = ()
    members: tuple = ()


@dataclass(frozen=True)
class Sheet:
    """One sheet of an XLSX: its 1-based position (the address `sheet = k` takes), its masked name, its row and column counts, its Table."""
    position: int
    name: str
    rows: int
    columns: int
    table: Table


@dataclass(frozen=True)
class Finding:
    """A FindingKind atom where it is (file; sheet position, 0 for none; lines [first, last] or none; column position, 0 for none) and its
    response from RESPONSE: the atom, the text it prints, the "or ..." it prints second."""
    code: str
    file: str
    sheet: int
    lines: tuple
    column: int
    response: str
    does: str
    otherwise: str


def rle(numbers):
    """Sorted line numbers as [first, last] pairs of consecutive runs."""
    groups = itertools.groupby(enumerate(sorted(numbers)), key=lambda p: p[1] - p[0])
    return tuple((g[0][1], g[-1][1]) for g in (list(x) for _, x in groups))


def kind(cs):
    """The RowKind of a line's cells (plan 1165 2.3): BLANK (no cell holds text), TEXT (a cell is no number), NUMERIC_WITH_EMPTY, NUMERIC."""
    filled = [c.strip() for c in cs if c.strip()]
    return {(False, True): "BLANK", (True, False): "TEXT", (True, True): ("NUMERIC", "NUMERIC_WITH_EMPTY")[len(filled) < len(cs)]}[
        (len(filled) > 0, all(NUMBER.fullmatch(c) for c in filled))]


def _prefix(ln):
    return next((p for p in CLASSES if ln.startswith(p)), "")


def _elect(lines):
    """(the elected Delimiter, every delimiter's (width, lines) evidence): the most common width of 2 or more over the most lines; ties in
    Delimiter order; NONE when no delimiter cuts any line into 2 or more cells."""
    hist = {d: sorted(Counter(len(cut(t)) for _, t in lines if t.strip()).items()) for d, cut in CUT.items()}
    score = {d: max([n for w, n in h if w >= 2], default=0) for d, h in hist.items()}
    best = [d for d in CUT if score[d] == max(score.values()) and score[d] > 0] + ["NONE"]
    return best[0], tuple(hist.items())


def segments(ks):
    """The count of maximal monotone segments of a sequence (equal neighbours merged first): a segment takes its direction from its first
    step and ends at the first step against it, the value after which opens the next (a reset between two sweeps opens one, never two)."""
    steps = [b > a for a, b in zip(ks, ks[1:])]
    return functools.reduce(lambda st, up: {None: (st[0], up), up: (st[0], up)}.get(st[1], (st[0] + 1, None)), steps, (int(len(ks) > 0), None))[0]


def order(xs):
    """The order and repeat fields of a column's numbers in file order (counts only; the values are dropped on return): monotone_runs (the
    segments), first_direction, equal_runs (runs of 2, 3-9, 10+), longest, revisited, distinct (intake_names.repeats for the run counts)."""
    runs, rep = _runs(xs), repeats([xs])
    ks = [k for k, _ in runs]
    bins = Counter(BIN.get(min(n, 10)) for _, n in runs)
    return dict(monotone_runs=segments(ks), first_direction=DIRECTION[next((b > a for a, b in zip(ks, ks[1:])), None)],
                equal_runs=tuple(bins[b] for b in range(3)), longest=rep["longest run"], revisited=rep["values revisited"], distinct=len(set(xs)))


def _column(k, name, cells):
    """ColumnProfile of position k (1-based) over (line, cell) pairs."""
    cls = [(n, {True: "empty", False: {True: "numeric", False: "text"}[NUMBER.fullmatch(c.strip()) is not None]}[c.strip() == ""], c) for n, c in cells]
    count = lambda w: [n for n, x, _ in cls if x == w]
    return ColumnProfile(k, name, len(count("numeric")), len(count("empty")), len(count("text")), rle(count("text")), rle(count("empty")),
                         **order([float(c) for _, x, c in cls if x == "numeric"]))


def _name(cs, k):
    """The masked name of position k in a header line's cells: a TEXT cell masked, a NUMERIC one #k, an empty one ""."""
    c = cs[k - 1].strip()
    return {True: lambda: "", False: {Name.TEXT: lambda: masked(c), Name.NUMERIC: lambda: f"#{k}"}[classify(c)]}[c == ""]()


def table(lines, delimiter, widths):
    """The Table of numbered text lines cut by `delimiter` (lines: [(line, text)]; an xlsx sheet's rows come cut, delimiter NONE)."""
    cut = CUT.get(delimiter, lambda t: [t])
    return cells_table([(n, cut(t), _prefix(t)) for n, t in lines], delimiter, widths)


def cells_table(cut, delimiter, widths):
    keyed = [(n, (kind(cs), len(cs), p)) for n, cs, p in cut]
    runs = tuple(RowRun(g[0][0], g[-1][0], *key) for key, g in ((k, list(g)) for k, g in itertools.groupby(keyed, key=lambda x: x[1])))
    body = [r for r in runs if r.kind in NUMERIC_KINDS]
    start = {True: lambda: body[0].first, False: lambda: len(cut) + 1}[len(body) > 0]()
    dominant = max([(r.last - r.first + 1, -i, r.width) for i, r in enumerate(body)], default=(0, 0, 0))[2]   # the longest NUMERIC run's width
    head = [(n, cs) for n, cs, _ in cut if n < start]
    names = [cs for n, cs in head if kind(cs) == "TEXT"][-1:]
    named = lambda k: {True: lambda: _name(names[0], k), False: lambda: "NONE"}[len(names) == 1 and len(names[0]) >= k]()
    within = [(n, cs) for n, cs, _ in cut if n >= start and len(cs) == dominant and kind(cs) != "BLANK"]
    columns = tuple(_column(k, named(k), [(n, cs[k - 1]) for n, cs in within]) for k in range(1, dominant + 1))
    prefixes = Counter(p for _, _, p in cut if p != "")
    return Table(delimiter, widths, len(cut), rle(n for n, cs, _ in cut if kind(cs) == "BLANK"), tuple(sorted(prefixes.items())), runs,
                 tuple(HeaderLine(n, tuple(_name(cs, k) for k in range(1, len(cs) + 1))) for n, cs in head[:12]), columns)


def decoded(raw):
    """(Encoding, text): the first of ENCODINGS that holds and decodes every byte; ("UNDECODABLE", None) for empty bytes or a binary format."""
    enc, text = next((e, t) for e, holds, code in ENCODINGS if holds(raw) for t in [_decoded(raw, code)] if t is not None)
    return {True: (enc, text), False: ("UNDECODABLE", None)}[text != "" and not BINARY.search(text)]


def _text_file(head, enc, text):
    lines = _split(text)
    delimiter, widths = _elect(lines)
    return FileProfile(*head, "TEXT_TABLE", enc, (table(lines, delimiter, widths),))


def _sheet(k, name, raw):
    cut = [(n, [c.strip() for c in cs], "") for n, cs in sheet_rows(raw, k)]
    return Sheet(k, {Name.TEXT: masked, Name.NUMERIC: lambda n: f"#{k}"}[classify(name)](name), len(cut), max([len(cs) for _, cs, _ in cut], default=0),
                 cells_table(cut, "NONE", ()))


def sheets(raw):
    """An XLSX's sheets, each profiled as a table of its cells (intake_convert.sheet_rows, the SHEET_TO_CSV cut), or READER_ABSENT without
    openpyxl; a workbook openpyxl cannot open has none."""
    has = importlib.util.find_spec("openpyxl") is not None
    names = {True: lambda: _book_names(raw) or [], False: lambda: None}[has]()
    return {True: lambda: tuple(_sheet(k, n, raw) for k, n in enumerate(names, 1)), False: lambda: READER_ABSENT}[has]()


KINDS = {   # (is it a zip, does it hold xl/workbook.xml, does it decode as text) -> its FileProfile; total over the 8 keys; by content, never by name
    **{(True, True, t): lambda h, z, e, raw: FileProfile(*h, "XLSX", "UNDECODABLE", sheets=sheets(raw)) for t in (True, False)},
    **{(True, False, t): lambda h, z, e, raw: FileProfile(*h, "ZIP", "UNDECODABLE", members=tuple((masked(i.filename), i.file_size) for i in z.infolist()))
       for t in (True, False)},
    (False, False, True): lambda h, z, e, raw: _text_file(h, *e),
    (False, False, False): lambda h, z, e, raw: FileProfile(*h, "UNPROFILED_FORMAT", "UNDECODABLE"),
}


def profiled(name, raw):
    """The FileProfile of one file's bytes: a zip (an xlsx when it holds xl/workbook.xml, members by masked name and size), a text table (decoded
    by ENCODINGS, cut by the elected delimiter), or UNPROFILED_FORMAT (empty or binary: the alphabet has no reader)."""
    z, e = _zipped(raw), decoded(raw)
    xlsx = z is not None and "xl/workbook.xml" in z.namelist()
    return KINDS[(z is not None, xlsx, e[1] is not None)]((name, len(raw), hashlib.sha256(raw).hexdigest()), z, e, raw)


def as_json(p):
    """PROFILE.json's text: the profile as plain values (asdict: a dataclass to a dict, a tuple to a list), sorted keys."""
    return json.dumps(asdict(p), indent=1, sort_keys=True) + "\n"


@dataclass(frozen=True)
class Profile:
    """The profile of a root-named path: its files in listing order and the findings of section 4."""
    path: str
    files: tuple
    findings: tuple


def listing(base):
    """Every file under base, by its relative path, sorted (the profile reads the whole path: no glob, no sampling)."""
    return sorted(q.relative_to(base).as_posix() for q in Path(base).rglob("*") if q.is_file())


def profile(root, ident, path, t, out="PROFILE.json"):
    """Profile the directory a root-named path names (intake_bytes.located; any other form is ROOT_UNRESOLVED): every file read once through
    the logged loader (partition "profiled", declarations/<id>/profile-access.log); writes declarations/<id>/<out>. Profile | Refuse."""
    d, base = Path(root) / "declarations" / ident, intake_bytes.located(path, t["roots"])
    def go():
        loader = intake_bytes._t23().Loader({base: "profiled"}, d / "profile-access.log")
        p = Profile(path, tuple(profiled(n, loader.read(Path(base) / n)) for n in listing(base)), ())
        (d / out).write_text(as_json(p))
        return p
    return gate([(lambda: base != "" and Path(base).is_dir(), "ROOT_UNRESOLVED", lambda: detail(words=[f"path '{path}' (a root-named path: <name>/<relative path>)"]))], go)

