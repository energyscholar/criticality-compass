"""intake_findings - the profile's findings (plan 1165 section 4; role intake_findings, its own cap tests/test_budget.py FINDINGS_CAP, split from
cc/intake_profile.py by fix S11.P2b F3, which found intake_profile at its cap): the profiled files' values -> every Finding, each where its structure
is and with its one response. Invariants: it reads no byte (a function of FileProfile values); a finding is a row of FindingKind; RAISES (where) and
RESPONSE (what to do) are total over FindingKind (tests/test_intake_profile.py); a text file with no numeric row run is NOT_A_TABLE and raises no
finding of a table's head (HEADER / COMMENT / DELIMITER): those findings range over the tables that have a body (`bodied`)."""
import enum
import re
from dataclasses import field, make_dataclass

FindingKind = enum.Enum("FindingKind", "ENCODING_NOT_UTF8 BOM_PRESENT DELIMITER_NOT_COMMA NO_DELIMITER HEADER_LINES_BEFORE_NAMES NAMES_LINE_ABSENT "
                        "NAMES_LINE_NUMERIC COMMENT_LINES TEXT_RUN_IN_BODY TEXT_RUN_TRAILING TEXT_CELLS_IN_COLUMN EMPTY_CELLS_IN_COLUMN WIDTH_CHANGES "
                        "COLUMNS_DIFFER_ACROSS_FILES NOT_MONOTONE DIRECTION_DESCENDING EQUAL_RUNS_SHORT EQUAL_RUN_LONG REVISITED_VALUES XLSX_SHEETS "
                        "ZIP_MEMBERS UNPROFILED_FORMAT LARGE_FILE ONE_FILE NOT_A_TABLE")
Response = enum.Enum("Response", "CONVERT DECLARE BLOCKS REFUSE_DEPOSIT NONE")
C = Response
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
    "NOT_A_TABLE": (C.DECLARE, "[selection] files without it: no numeric row, so no curve (a README, a script, a manifest)", ""),   # (fix F3)
}
NUMERIC_KINDS = ("NUMERIC", "NUMERIC_WITH_EMPTY")


def frozen(name, fields, doc):
    """A frozen dataclass of typed fields ((name, type) or (name, type, default)): the profile's types (plan 1165 section 3)."""
    return make_dataclass(name, [f[:2] + tuple(field(default=d) for d in f[2:]) for f in fields], frozen=True, namespace={"__doc__": doc})


Finding = frozen("Finding", [("code", str), ("file", str), ("sheet", int), ("lines", tuple), ("column", int), ("response", str), ("does", str), ("otherwise", str)],
                 "A FindingKind atom where it is (file; sheet position or 0; lines [first, last] or none; column or 0) and its RESPONSE row.")


numeric = lambda t: [r for r in t.rows if r.kind in NUMERIC_KINDS]   # a table's numeric row runs: its body (none: it is no table)


def tables_of(f):
    """(sheet position, Table) of a file: its text table (sheet 0) or each sheet of an XLSX."""
    return [(0, t) for t in f.tables] + [(x.position, x.table) for x in {True: f.sheets, False: ()}[isinstance(f.sheets, tuple)]]


def body(t):
    """(the first NUMERIC line, the last NUMERIC run's first and last lines, the names line: the last TEXT line before the body, 0 for none)."""
    nr = [(r.first, r.last) for r in numeric(t)] or [(t.lines + 1, t.lines + 1)]   # no body: past the last line
    return nr[0][0], nr[-1][0], nr[-1][1], max([r.last for r in t.rows if r.kind == "TEXT" and r.last < nr[0][0]], default=0)


def runs(t, where):
    """The lines of t's whole-text runs (no numeric cell) that `where(first line of body, first and last line of the last NUMERIC run)` holds."""
    b = body(t)
    return [((r.first, r.last), 0) for r in t.rows if r.kind == "TEXT" and r.numbers == 0 and where(r, *b[:3])]


span = lambda ls: {True: lambda: (ls[0][0], ls[-1][1]), False: tuple}[len(ls) > 0]()
per_file = lambda holds: lambda fs: [(f.name, 0, (), 0) for f in fs if holds(f)]
per_table = lambda found: lambda fs: [(f.name, k, ls, c) for f in fs for k, t in tables_of(f) for ls, c in found(t)]
per_column = lambda holds, lines=lambda c: (): per_table(lambda t: [(span(lines(c)), c.position) for c in t.columns if holds(c)])
texts = lambda f: [t for t in f.tables if f.kind == "TEXT_TABLE"]
bodied = lambda f: [t for t in texts(f) if numeric(t)]   # (fix F3) a text file's tables that have a body
per_body = lambda found: per_table(lambda t: [x for _ in numeric(t)[:1] for x in found(t)])   # (fix F3) a head finding: only of a table with a body
shape = lambda f: [([c.name for c in t.columns], len(t.columns)) for t in f.tables]   # a text file's masked names line and dominant width
RAISES = {   # FindingKind -> (the profiled files) -> [(file, sheet, lines, column)] where its structure (plan 1165 section 4) is; total (test)
    "ENCODING_NOT_UTF8": per_file(lambda f: f.encoding in ("LATIN1_ONLY", "UTF16")), "BOM_PRESENT": per_file(lambda f: f.encoding == "UTF8_SIG"),
    "DELIMITER_NOT_COMMA": per_file(lambda f: any(t.delimiter in ("SEMICOLON", "TAB", "WHITESPACE") for t in bodied(f))),
    "NO_DELIMITER": per_file(lambda f: any(t.delimiter == "NONE" for t in bodied(f))),
    "HEADER_LINES_BEFORE_NAMES": per_body(lambda t: [((1, body(t)[3] - 1), 0) for _ in range(int(len([r for r in t.rows if r.kind != "BLANK" and r.last < body(t)[3]]) > 0))]),
    "NAMES_LINE_ABSENT": per_table(lambda t: [((), 0) for _ in range(int(body(t)[3] == 0 and body(t)[0] <= t.lines))]),
    "NAMES_LINE_NUMERIC": per_table(lambda t: [((body(t)[3], body(t)[3]), 0) for h in t.header_lines if h.line == body(t)[3]
                                               and len(h.cells) >= 3 and sum(bool(re.fullmatch(r"#\d+", c)) for c in h.cells) >= len(h.cells) - 1]),
    "COMMENT_LINES": per_body(lambda t: [((r.first, r.last), 0) for r in t.rows if r.prefix != ""]),
    "TEXT_RUN_IN_BODY": per_table(lambda t: runs(t, lambda r, first, last0, last1: first < r.first < last0)),
    "TEXT_RUN_TRAILING": per_table(lambda t: runs(t, lambda r, first, last0, last1: r.first > last1)),
    "TEXT_CELLS_IN_COLUMN": per_column(lambda c: c.text > 0, lambda c: c.text_lines),
    "EMPTY_CELLS_IN_COLUMN": per_column(lambda c: c.empty > 0, lambda c: c.empty_lines),
    "WIDTH_CHANGES": per_table(lambda t: [((r.first, r.last), 0) for r in t.rows if r.kind in NUMERIC_KINDS and r.width != len(t.columns)]),
    "COLUMNS_DIFFER_ACROSS_FILES": lambda fs: [(f.name, 0, (), 0) for f in fs if [shape(f)] != [shape(g) for g in fs if texts(g)][:1] and texts(f)],
    "NOT_MONOTONE": per_column(lambda c: c.monotone_runs > 1),
    "DIRECTION_DESCENDING": per_column(lambda c: c.monotone_runs == 1 and c.first_direction == "DESCENDING"),
    "EQUAL_RUNS_SHORT": per_column(lambda c: c.equal_runs[0] + c.equal_runs[1] > 0 and c.revisited == 0),
    "EQUAL_RUN_LONG": per_column(lambda c: c.longest >= 10), "REVISITED_VALUES": per_column(lambda c: c.revisited > 0),
    "XLSX_SHEETS": per_file(lambda f: f.kind == "XLSX"), "ZIP_MEMBERS": per_file(lambda f: f.kind == "ZIP"),
    "UNPROFILED_FORMAT": per_file(lambda f: f.kind == "UNPROFILED_FORMAT"),
    "LARGE_FILE": per_file(lambda f: any(t.lines >= 10000 for _, t in tables_of(f))),
    "ONE_FILE": lambda fs: [(f.name, 0, (), 0) for f in fs if f.kind == "TEXT_TABLE" and sum(g.kind == "TEXT_TABLE" for g in fs) == 1],
    "NOT_A_TABLE": per_file(lambda f: f.kind == "TEXT_TABLE" and not bodied(f)),   # (fix F3) a text file with no numeric row run
}


def findings(files):
    """Every finding of the profiled files, in file order then FindingKind order, each with its response from RESPONSE (computed, never chosen)."""
    order = {f.name: i for i, f in enumerate(files)}
    found = [(order[f], k.value, Finding(k.name, f, s, ls, c, RESPONSE[k.name][0].name, *RESPONSE[k.name][1:])) for k in FindingKind for f, s, ls, c in RAISES[k.name](files)]
    return tuple(x for _, _, x in sorted(found, key=lambda x: x[:2]))
