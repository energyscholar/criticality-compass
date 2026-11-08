"""intake_profile - pre-processing (plan 1165; role intake_profile, its own cap tests/test_budget.py PROFILE_CAP; the cross-check against a declaration
is cc/intake_against.py): `bin/cc intake profile` reads every byte of every file under a root-named path, before any declaration is written, and reduces
them to a PROFILE of their structure. Invariants: - value-free BY TYPE: every field of Profile, FileProfile, Table, RowRun, HeaderLine, ColumnProfile and
Finding is an int, a str that is a file name, a sha256, an enum atom or a masked name (intake_names.masked: every numeral as #; a NUMERIC cell as its position
#k), or a tuple of these; no float, and no str that receives a cell's text unmasked. A value is held in memory to count runs, never kept; - every file is read
once through the vendored t23 logged loader, partition "profiled", into declarations/<id>/profile-access.log; nothing is written under the profiled path;
- a finding is a row of FindingKind and its response is looked up in RESPONSE, total over FindingKind (tests/test_intake_profile.py)."""
import datetime
import enum
import functools
import importlib.util
import hashlib
import itertools
import json
import re
from collections import Counter
from dataclasses import asdict, field, make_dataclass
from pathlib import Path

import intake_bytes
import intake_seal
from intake_blind import Refuse, detail, format_stage, gate
from intake_convert import MANIFEST, SPLIT, _book_names, _decoded, _manifest, _split, _zipped, sheet_rows
from intake_findings import NUMERIC_KINDS, RAISES, RESPONSE, Finding, FindingKind, Response, body, findings, frozen, tables_of   # (fix F3) the findings' own role
from intake_names import NUMBER, Name, _runs, classify, masked, repeats

FileKind = enum.Enum("FileKind", "TEXT_TABLE XLSX ZIP UNPROFILED_FORMAT")   # by content, never by extension (plan 1165 2.2)
Encoding = enum.Enum("Encoding", "UTF8 UTF8_SIG UTF16 LATIN1_ONLY UNDECODABLE NOT_APPLICABLE")   # by FileKind (KINDS): a text decoding; UNDECODABLE (empty or binary); NOT_APPLICABLE (a zip, an xlsx)
Delimiter = enum.Enum("Delimiter", "COMMA SEMICOLON TAB WHITESPACE NONE")   # the election's tie order is this order
RowKind = enum.Enum("RowKind", "BLANK NUMERIC NUMERIC_WITH_EMPTY TEXT")
CUT = {d: SPLIT[d] for d in ("COMMA", "SEMICOLON", "TAB", "WHITESPACE")}   # Delimiter -> one line to its cells, in the election's tie order (NONE:
# the line is one cell); the converter's own DELIMITER cuts, so a profile's widths are the widths DELIMITER from = d gives
ENCODINGS = (   # (Encoding, does it hold, DECODE's name): the first that holds decodes the file (plan 1165 2.2); a BOM is structure, read first
    ("UTF8_SIG", lambda r: r.startswith(b"\xef\xbb\xbf"), "utf-8-sig"), ("UTF16", lambda r: r[:2] in (b"\xff\xfe", b"\xfe\xff"), "utf-16"),
    ("UTF8", lambda r: True, "utf-8"), ("LATIN1_ONLY", lambda r: True, "latin-1"))   # latin-1 decodes every byte: LATIN1_ONLY is "not UTF-8"
BINARY = re.compile("[\x00-\x08\x0e-\x1f\x7f]")   # a decoded control character no text table holds: the bytes are a binary format
BIN = {2: 0, **{n: 1 for n in range(3, 10)}, 10: 2}   # an equal run's length (10 for 10 or more) -> its equal_runs bin (2, 3-9, 10+); a run of 1 none
DIRECTION = {None: "FLAT", True: "ASCENDING", False: "DESCENDING"}   # the first step of a column's numbers (equal values merged) -> first_direction
READER_ABSENT = "NONE_READER_ABSENT"   # an XLSX's `sheets` on a machine without openpyxl (XLSX_READER_ABSENT: the kind stays XLSX)
CELLS_UNREADABLE = "NONE_CELLS_UNREADABLE"   # (plan 1281 B8) an XLSX's `sheets` when its names load and a sheet's cells do not parse: the reader names it (S4 NOT_AN_XLSX)
CLASSES = ("#", "%", ";", "//", "!", "[")   # comment prefix classes: a line's first characters (the reader's own test, startswith)




RowRun = frozen("RowRun", [("first", int), ("last", int), ("kind", str), ("width", int), ("prefix", str), ("numbers", int)],
                "A run of lines of one (kind, width, comment prefix, numbers: 1 when each line holds a numeric cell, so a `n/a` row of a body is told "
                "from a whole text row); first and last are 1-based file lines (a block boundary is a change of any).")
HeaderLine = frozen("HeaderLine", [("line", int), ("cells", tuple)], "A line before the body as cells: a TEXT cell masked, a NUMERIC one #k, an empty one \"\".")
ColumnProfile = frozen("ColumnProfile", [("position", int), ("name", str), ("numeric", int), ("empty", int), ("text", int), ("text_lines", tuple),
                                         ("empty_lines", tuple), ("monotone_runs", int, 0), ("first_direction", str, "FLAT"), ("equal_runs", tuple, (0, 0, 0)),
                                         ("longest", int, 0), ("revisited", int, 0), ("distinct", int, 0), ("segment_lines", tuple, ()),
                                         ("short_lines", tuple, ()), ("long_lines", tuple, ()), ("revisited_lines", tuple, ())],
                       "Position k of the dominant width over the body lines of that width holding a number: counts of cell classes, the lines of TEXT "
                       "and empty cells ([first, last] runs), the order and repeats of its numbers (counts only; equal_runs: runs of 2, 3-9, 10+), and "
                       "(fix S11.P2b F4) where they are, as [first, last] line ranges: each monotone segment, each equal run of 2-9 and of 10+, each "
                       "run of a value seen in an earlier run.")
Table = frozen("Table", [("delimiter", str), ("widths", tuple), ("lines", int), ("blank_lines", tuple), ("comment_prefixes", tuple), ("rows", tuple),
                         ("header_lines", tuple), ("columns", tuple)],
               "A text file's or a sheet's cells: the elected delimiter and every delimiter's (width, lines) evidence, the line count, the blank lines, "
               "the comment prefixes counted, the row runs, the header lines (at most 12) and the columns.")
FileProfile = frozen("FileProfile", [("name", str), ("bytes", int), ("sha256", str), ("kind", str), ("encoding", str), ("tables", tuple, ()),
                                     ("sheets", object, ()), ("members", tuple, ()), ("encoding_lines", tuple, ())],
                     "One file: `tables` its one Table (a TEXT_TABLE); `sheets` an XLSX's Sheets (or READER_ABSENT); `members` a ZIP's (masked name, size).")
Sheet = frozen("Sheet", [("position", int), ("name", str), ("rows", int), ("columns", int), ("table", object)],
               "One sheet of an XLSX: its 1-based position (the address `sheet = k` takes), its masked name, its row and column counts, its Table.")
Profile = frozen("Profile", [("path", str), ("files", tuple), ("findings", tuple)], "The profile of a root-named path: its files in listing order, its findings.")


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


def starts(ks):
    """(fix F4) The index of each monotone segment's first key: segments' own fold, keeping where each segment opens (len = segments(ks))."""
    up = lambda st, iu: {None: (st[0], iu[1]), iu[1]: (st[0], iu[1])}.get(st[1], (st[0] + (iu[0] + 1,), None))
    return functools.reduce(up, enumerate(b > a for a, b in zip(ks, ks[1:])), ((0,)[:len(ks)], None))[0]


def order(pairs):
    """The order and repeat fields of a column's numbers in file order, from (line, number) pairs (counts and line ranges only; the values are dropped on return): monotone_runs (the segments), first_direction, equal_runs (runs of 2, 3-9, 10+), longest, revisited, distinct (intake_names.repeats for the run counts), and each count's [first, last] lines."""
    xs = [x for _, x in pairs]
    runs, rep = _runs(xs), repeats([xs])
    ks = [k for k, _ in runs]
    bins = Counter(BIN.get(min(n, 10)) for _, n in runs)
    g = [(k, [n for n, _ in grp]) for k, grp in itertools.groupby(pairs, key=lambda p: p[1])]   # the equal runs with their lines
    at = lambda sel: tuple((ls[0], ls[-1]) for i, (k, ls) in enumerate(g) if sel(i, k, len(ls)))
    first = {k: i for i, (k, _) in reversed(list(enumerate(g)))}   # each value's first run
    seg = starts(ks) + (len(g),)
    return dict(monotone_runs=segments(ks), first_direction=DIRECTION[next((b > a for a, b in zip(ks, ks[1:])), None)],
                equal_runs=tuple(bins[b] for b in range(3)), longest=rep["longest run"], revisited=rep["values revisited"], distinct=len(set(xs)),
                segment_lines=tuple((g[a][1][0], g[b - 1][1][-1]) for a, b in zip(seg, seg[1:])), short_lines=at(lambda i, k, n: 2 <= n < 10),
                long_lines=at(lambda i, k, n: n >= 10), revisited_lines=at(lambda i, k, n: first[k] < i))


def _column(k, name, cells):
    """ColumnProfile of position k (1-based) over (line, cell) pairs."""
    cls = [(n, {True: "empty", False: {True: "numeric", False: "text"}[NUMBER.fullmatch(c.strip()) is not None]}[c.strip() == ""], c) for n, c in cells]
    count = lambda w: [n for n, x, _ in cls if x == w]
    return ColumnProfile(k, name, len(count("numeric")), len(count("empty")), len(count("text")), rle(count("text")), rle(count("empty")),
                         **order([(n, float(c)) for n, x, c in cls if x == "numeric"]))


def _name(cs, k):
    """The masked name of position k in a header line's cells: a TEXT cell masked, a NUMERIC one #k, an empty one ""."""
    c = cs[k - 1].strip()
    return {True: lambda: "", False: {Name.TEXT: lambda: masked(c), Name.NUMERIC: lambda: f"#{k}"}[classify(c)]}[c == ""]()


def table(lines, delimiter, widths):
    """The Table of numbered text lines cut by `delimiter` (lines: [(line, text)]; an xlsx sheet's rows come cut, delimiter NONE)."""
    cut = CUT.get(delimiter, lambda t: [t])
    return cells_table([(n, cut(t), _prefix(t)) for n, t in lines], delimiter, widths)


def cells_table(cut, delimiter, widths):
    keyed = [(n, (kind(cs), len(cs), p, int(any(NUMBER.fullmatch(c.strip()) for c in cs)))) for n, cs, p in cut]
    runs = tuple(RowRun(g[0][0], g[-1][0], *key) for key, g in ((k, list(g)) for k, g in itertools.groupby(keyed, key=lambda x: x[1])))
    body = [r for r in runs if r.kind in NUMERIC_KINDS]
    start = {True: lambda: body[0].first, False: lambda: len(cut) + 1}[len(body) > 0]()
    dominant = max([(r.last - r.first + 1, -i, r.width) for i, r in enumerate(body)], default=(0, 0, 0))[2]   # the longest NUMERIC run's width
    head = [(n, cs) for n, cs, _ in cut if n < start]
    names = [cs for n, cs in head if kind(cs) == "TEXT"][-1:]
    named = lambda k: {True: lambda: _name(names[0], k), False: lambda: "NONE"}[len(names) == 1 and len(names[0]) >= k]()
    within = [(n, cs) for n, cs, _ in cut if n >= start and len(cs) == dominant and any(NUMBER.fullmatch(c.strip()) for c in cs)]
    columns = tuple(_column(k, named(k), [(n, cs[k - 1]) for n, cs in within]) for k in range(1, dominant + 1))
    prefixes = Counter(p for _, _, p in cut if p != "")
    return Table(delimiter, widths, len(cut), rle(n for n, cs, _ in cut if kind(cs) == "BLANK"), tuple(sorted(prefixes.items())), runs,
                 tuple(HeaderLine(n, tuple(_name(cs, k) for k in range(1, len(cs) + 1))) for n, cs in head[:12]), columns)


def decoded(raw):
    """(Encoding, text): the first of ENCODINGS that holds and decodes every byte; ("UNDECODABLE", None) for empty bytes or a binary format."""
    enc, text = next((e, t) for e, holds, code in ENCODINGS if holds(raw) for t in [_decoded(raw, code)] if t is not None)
    return {True: (enc, text), False: ("UNDECODABLE", None)}[text != "" and not BINARY.search(text)]


ENCODING_LINES = {   # (fix F4) Encoding -> (the decoded lines) -> where ENCODING_NOT_UTF8 is: the lines no utf-8 decode reads; total over the text decodings
    "UTF8": lambda ls: (), "UTF8_SIG": lambda ls: (), "UTF16": lambda ls: ((1, len(ls)),)[:len(ls)],
    "LATIN1_ONLY": lambda ls: rle(n for n, t in ls if _decoded(t.encode("latin-1"), "utf-8") is None)}   # latin-1 is one byte per character


def _text_file(head, enc, text):
    lines = _split(text)
    delimiter, widths = _elect(lines)
    return FileProfile(*head, "TEXT_TABLE", enc, (table(lines, delimiter, widths),), encoding_lines=ENCODING_LINES[enc](lines))


def _sheet(k, name, rows):
    cut = [(n, [c.strip() for c in cs], "") for n, cs in rows]
    return Sheet(k, {Name.TEXT: masked, Name.NUMERIC: lambda n: f"#{k}"}[classify(name)](name), len(cut), max([len(cs) for _, cs, _ in cut], default=0),
                 cells_table(cut, "NONE", ()))


def sheets(raw):
    """An XLSX's sheets, each profiled as a table of its cells (intake_convert.sheet_rows, the SHEET_TO_CSV cut), or READER_ABSENT without openpyxl; a workbook openpyxl cannot open has none; (plan 1281 B8) a Refuse from sheet_rows, by type, makes it CELLS_UNREADABLE."""
    has = importlib.util.find_spec("openpyxl") is not None
    got = [(k, n, sheet_rows(raw, k)) for k, n in enumerate({True: lambda: _book_names(raw) or [], False: lambda: []}[has](), 1)]
    return {(True, False): lambda: tuple(_sheet(k, n, g) for k, n, g in got), (True, True): lambda: CELLS_UNREADABLE, (False, False): lambda: READER_ABSENT}[(has, Refuse in {type(g) for _, _, g in got})]()


KINDS = {   # (is it a zip, does it hold xl/workbook.xml, does it decode as text) -> its FileProfile; total over the 8 keys; by content, never by name
    **{(True, True, t): lambda h, z, e, raw: FileProfile(*h, "XLSX", "NOT_APPLICABLE", sheets=sheets(raw)) for t in (True, False)},
    **{(True, False, t): lambda h, z, e, raw: FileProfile(*h, "ZIP", "NOT_APPLICABLE", members=tuple((masked(i.filename), i.file_size) for i in z.infolist()))
       for t in (True, False)},
    (False, False, True): lambda h, z, e, raw: _text_file(h, *e),
    (False, False, False): lambda h, z, e, raw: FileProfile(*h, "UNPROFILED_FORMAT", "UNDECODABLE"),
}


def profiled(name, raw):
    """The FileProfile of one file's bytes: a zip (an xlsx when it holds xl/workbook.xml, members by masked name and size), a text table (decoded by ENCODINGS, cut by the elected delimiter), or UNPROFILED_FORMAT (empty or binary: the alphabet has no reader)."""
    z, e = _zipped(raw), decoded(raw)
    xlsx = z is not None and "xl/workbook.xml" in z.namelist()
    return KINDS[(z is not None, xlsx, e[1] is not None)]((name, len(raw), hashlib.sha256(raw).hexdigest()), z, e, raw)


def as_json(p):
    """PROFILE.json's text: the profile as plain values (asdict: a dataclass to a dict, a tuple to a list), sorted keys."""
    return json.dumps(asdict(p), indent=1, sort_keys=True) + "\n"


def listing(base):
    """Every file under base, by its relative path, sorted (the profile reads the whole path: no glob, no sampling)."""
    return sorted(q.relative_to(base).as_posix() for q in Path(base).rglob("*") if q.is_file())




def profile(root, ident, path, t, out="PROFILE.json"):
    """Profile the directory a root-named path names (intake_bytes.located; any other form is ROOT_UNRESOLVED): every file read once through the logged loader (partition "profiled", declarations/<id>/profile-access.log); writes declarations/<id>/<out> and its .md, appends to profile.log, replaces the ## Profile section of <path>/../MANIFEST.md when it exists. Writes nothing under the path. Profile | Refuse."""
    d, base = Path(root) / "declarations" / ident, intake_bytes.located(path, t["roots"])
    def go():
        loader = intake_bytes._t23().Loader({base: "profiled"}, d / "profile-access.log")
        files = tuple(profiled(n, loader.read(Path(base) / n)) for n in listing(base))
        p, now = Profile(path, files, findings(files)), datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        (d / out).write_text(as_json(p))
        sha = hashlib.sha256((d / out).read_bytes()).hexdigest()
        (d / out).with_suffix(".md").write_text(md(p, sha))
        with (d / "profile.log").open("a") as log:
            log.write(json.dumps({"time": now, "path": path, "out": out, "files": len(files), "bytes": sum(f.bytes for f in files), "sha256": sha}) + "\n")
        manifest = Path(base).parent / "MANIFEST.md"
        {True: lambda: manifest.write_text(section(manifest.read_text(), p, sha, now)), False: lambda: None}[manifest.is_file()]()
        return p
    return gate([(lambda: base != "" and Path(base).is_dir(), "ROOT_UNRESOLVED", lambda: detail(words=[f"path '{path}' (a root-named path: <name>/<relative path>)"]))], go)


def _cells(h):
    """A header line as peek prints it (intake_convert._said's form): its text names masked, its numeric names counted, or blank."""
    text = [c for c in h.cells if c != "" and not re.fullmatch(r"#\d+", c)]
    num = sum(bool(re.fullmatch(r"#\d+", c)) for c in h.cells)
    return {True: f"line {h.line}: blank", False: f"line {h.line}: {len(text)} text name{'s' * (len(text) != 1)} + {num} numeric name{'s' * (num != 1)}" + "".join(f"{', ' * (i > 0) or ': '}'{c}'" for i, c in enumerate(text))}[
        len(text) + num == 0]


def _table_md(t, title):
    names, blanks = body(t)[3], [n for a, b in t.blank_lines for n in range(a, b + 1)]
    row = lambda n: n - names - sum(names < b <= n for b in blanks)   # RANGES' data-row number: rows after the names line, blank lines not rows
    rows = lambda r: {True: lambda: f"{row(r.first)}-{row(r.last)}", False: lambda: "-"}[r.first > names and r.kind != "BLANK"]()
    out = [f"### {title}", f"- delimiter {t.delimiter}; evidence " + "; ".join(f"{d} " + " ".join(f"{w}x{n}" for w, n in h) for d, h in t.widths),
           f"- {t.lines} lines; blank lines " + (", ".join(f"{a}-{b}" for a, b in t.blank_lines) or "none") + "; comment prefixes "
           + (", ".join(f"'{c}' x{n}" for c, n in t.comment_prefixes) or "none"), "", "| lines | data rows | kind | width |", "|---|---|---|---|"]
    out += [f"| {r.first}-{r.last} | {rows(r)} | {r.kind}{' (' + r.prefix + ')' if r.prefix else ''}{' with numbers' * (r.kind == 'TEXT' and r.numbers)} | {r.width} |" for r in t.rows]
    out += ["", "Header lines:"] + [f"- {_cells(h)}" for h in t.header_lines] + ["", "| k | name | numeric | empty | text | text lines | empty lines | monotone runs |"
            " first direction | equal runs 2 / 3-9 / 10+ | longest | revisited | distinct |", "|" + "---|" * 13]
    lines = lambda ls: ", ".join(f"{a}-{b}" for a, b in ls) or "-"
    out += [f"| {c.position} | {c.name or '(empty)'} | {c.numeric} | {c.empty} | {c.text} | {lines(c.text_lines)} | {lines(c.empty_lines)} | {c.monotone_runs} |"
            f" {c.first_direction} | {' / '.join(map(str, c.equal_runs))} | {c.longest} | {c.revisited} | {c.distinct} |" for c in t.columns[:12]]
    return out + [f"+{len(t.columns) - 12} more columns in PROFILE.json" for _ in range(int(len(t.columns) > 12))] + [""]


def md(p, sha):
    """PROFILE.md: the human form of PROFILE.json (no fact in one that is not in the other), per file, then the findings with their responses."""
    out = [f"# Profile of {p.path}", "", f"PROFILE.json sha256 {sha}; {len(p.files)} files; {len(p.findings)} findings.", ""]
    for f in p.files:
        out += [f"## {f.name}", f"- {f.kind}; encoding {f.encoding}; {f.bytes} bytes; sha256 {f.sha256}"] + [f"- member {m} ({n} bytes)" for m, n in f.members]
        out += {True: lambda: [f"- sheets: {({READER_ABSENT: 'openpyxl is not installed here', CELLS_UNREADABLE: 'a sheet whose cells do not parse (the reader refuses NOT_AN_XLSX)'}[f.sheets])} ({f.sheets})"],
                False: lambda: [f"- sheet #{x.position} '{x.name}': {x.rows} rows, {x.columns} columns" for x in f.sheets]}[isinstance(f.sheets, str)]() + [""]
        out += [x for k, t in tables_of(f) for x in _table_md(t, {True: "the table", False: f"sheet #{k}"}[k == 0])]
    where = lambda x: "".join(" lines " + ", ".join(f"{a}-{b}" for a, b in x.ranges[:12]) for _ in x.ranges[:1]) + f" (+{len(x.ranges) - 12} more in PROFILE.json)" * (len(x.ranges) > 12)
    out += ["## Findings", ""] + [f"- {x.code}: {x.file}" + f" sheet #{x.sheet}" * (x.sheet > 0) + where(x) + f" column {x.column}" * (x.column > 0)   # (fix F4) every range
            + f" against {x.compared}" * (x.compared != "") + f" -> {x.response}: {x.does}" + f" (or {x.otherwise})" * (x.otherwise != "") for x in p.findings]
    return "\n".join(out + ["", "Unprofiled: " + (", ".join(f"{f.name} ({f.bytes} bytes)" for f in p.files if f.kind == "UNPROFILED_FORMAT") or "none"), ""])


def section(text, p, sha, now):
    """MANIFEST.md with its `## Profile` section (counts only) replaced whole: from that heading to the next `## ` or the end; appended when absent."""
    rows = [f"| {f.name} | {f.kind} | {f.encoding} | {' '.join(t.delimiter for t in f.tables) or '-'} | {sum(t.lines for _, t in tables_of(f))} |"
            f" {sum(r.last - r.first + 1 for _, t in tables_of(f) for r in t.rows if r.kind in NUMERIC_KINDS)} | {len(RAISES['TEXT_RUN_IN_BODY']([f]))} |"
            f" {'/'.join(sorted({str(r.width) for _, t in tables_of(f) for r in t.rows if r.kind in NUMERIC_KINDS})) or '-'} | {sum(x.file == f.name for x in p.findings)} |" for f in p.files]
    new = "\n".join([f"## Profile", "", f"Profiled {now} (bin/cc intake profile); PROFILE.json sha256 {sha}.", "",
                     "| file | kind | encoding | delimiter | lines | numeric rows | text runs in body | widths | findings |", "|" + "---|" * 9] + rows) + "\n"
    m = re.search(r"^## Profile[ \t]*$.*?(?=^## |\Z)", text, re.M | re.S)
    return {True: lambda: text[:m.start()] + new + "\n" * (m.end() < len(text)) + text[m.end():], False: lambda: text.rstrip("\n") + "\n\n" + new}[m is not None]()



USAGE = ("usage: bin/cc intake profile <id> <root-named path> (PROFILE.json of the files the run reads) | profile <id> --raw <root-named path>"
         " (PROFILE-raw.json of a deposit a conversion reads) | profile <id> --check (the declaration against PROFILE.json)")


def _said(ident, p, out):
    sha = hashlib.sha256((Path(out)).read_bytes()).hexdigest()
    return (f"profile {ident}: {p.path}: {len(p.files)} files ({sum(f.kind == 'UNPROFILED_FORMAT' for f in p.files)} unprofiled), {len(p.findings)} findings;"
            f" {Path(out).name} sha256 {sha}\n" + "".join(f"  {x}\n" for x in md(p, sha).split("## Findings\n\n")[1].split("\n\nUnprofiled")[0].splitlines())
            + f"  Next: read declarations/{ident}/{Path(out).with_suffix('.md').name}; each finding names its one response (docs/INTAKE-PREPROCESSING.md)")


def profile_cli(root, ident, args, t):
    """bin/cc intake profile <id> [--raw] <root-named path>: the profile and its findings printed, exit 0; a refusal or usage, exit 1 (--check: check_cli)."""
    import intake_convert
    path, out = [a for a in args if a != "--raw"], {True: "PROFILE-raw.json", False: "PROFILE.json"}["--raw" in args]
    ok = len(path) == 1 and not path[0].startswith("--")
    got = {True: lambda: profile(root, ident, path[0], t, out), False: lambda: None}[ok]()
    print({(True, True): lambda: f"profile {ident}: " + got.text(intake_convert.ctables()["sentences"]),
           (True, False): lambda: _said(ident, got, Path(root) / "declarations" / ident / out), (False, False): lambda: f"bin/cc intake: {USAGE}"}[(ok, isinstance(got, Refuse))]())
    return {True: 0, False: 1}[ok and not isinstance(got, Refuse)]



EMPTY = {"path": "", "files": [], "findings": []}   # (fix F6) the profile value of no PROFILE.json: absence is its sha "", never a missing key


def read(d, bank, get):
    """[PROFILE.json of declarations/<id>, its sha256, the bank's CONVERSION-MANIFEST.json (intake_convert._manifest, {} when not of its shape), its sha256]; EMPTY / {} and "" for a file not there (absent: the sha is ""); `get` reads the manifest (S3: the run's loader)."""
    got = [{True: lambda: g(f), False: lambda: None}[f.is_file()]() for f, g in ((Path(d) / "PROFILE.json", Path.read_bytes), (Path(bank) / MANIFEST, get))]
    return [x for b, v, e in zip(got, (json.loads, lambda b: _manifest(b.decode("utf-8", "replace")) or {}), (EMPTY, {})) for x in {True: lambda: (v(b), hashlib.sha256(b).hexdigest()), False: lambda: (e, "")}[b is not None]()]


def check_cli(root, ident, args, t):
    """bin/cc intake profile <id> --check, the declarer's gate before lint: the declaration (S0) against PROFILE.json and its bank's manifest (intake_against.against); every contradiction printed (code, file, where), exit 1 on any or on no profile."""
    d = Path(root) / "declarations" / ident
    s0 = format_stage(intake_seal.declared(d), (), t)
    p, sha, m, _ = {True: lambda: [EMPTY, "", {}, ""], False: lambda: read(d, intake_bytes.located(s0.evidence.data["source"]["root"], t["roots"]), Path.read_bytes)}[isinstance(s0, Refuse)]()
    found = {True: lambda: (), False: lambda: intake_bytes.intake_against.against(p, m, s0.evidence.data)}[sha == ""]()
    print(f"profile {ident} --check: " + {True: lambda: f"REFUSE {s0.reason}: the declaration does not pass FORMAT (bin/cc intake lint {ident})", False: lambda: {True: f"PROFILE_ABSENT: run bin/cc intake profile {ident} <root-named path> first",
          False: f"{len(found)} contradictions" + "".join(f"\n  {c.name} {f}: {w}" for c, f, w in found)}[sha == ""]}[isinstance(s0, Refuse)]())
    return int(isinstance(s0, Refuse) or sha == "" or len(found) > 0)
