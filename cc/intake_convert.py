"""intake_convert - the conversion of a deposit into a canonical bank, and `peek` (plan 1160 P3; role intake_handoff, its own line cap
tests/test_budget.py HANDOFF_CAP). A conversion is declared in declarations/<id>/CONVERSION.toml, walked against intake/CONVERSION.toml by
the S0 walker (intake_blind.section), and run as a fold of the declared steps over each output file. Invariants:
 - a cell is str end to end: every op is a function from text cells to text cells; `float` is called in `_same` only (the identity test)
   and `int` in peek's depth parser only (tests/test_intake_convert.py checks both over the AST), so no arithmetic on a value is reachable;
 - every cell carries its source (line, column) in its file's source frame, so the manifest's cell map is built, never inferred;
 - nothing is written unless `verify` passes on the bytes about to be written: the cell map is a permutation (every output cell has one
   source cell; no source cell feeds two output cells but a broadcast column's; every source line is written, dropped by a declared step,
   blank, or a names line) and the identity holds (a number bitwise equal as a float, a text equal; rows in source order);
 - CONVERSION-MANIFEST.json holds paths, sha256s, sizes, counts, the cell map (line and column numbers), the steps as declared, the code
   hash and the time: never a cell value; the converter prints counts and names (a NUMERIC name never), and peek prints counts and masked
   text names, never a value;
 - every refusal is a value: a Refuse of a reason row of intake/CONVERSION.toml, the first failing check's."""
import csv
import functools
import hashlib
import importlib.util
import io
import itertools
import json
import re
import struct
import time
import tomllib
import zipfile
from dataclasses import dataclass, replace
from pathlib import Path

import intake_bytes
import intake_census
import intake_read
import schema
from intake_blind import NUMBER, Name, Pass, Refuse, classify, detail, flag, gate, look, parse
from intake_names import masked

MANIFEST = "CONVERSION-MANIFEST.json"
LINES = re.compile(r"\r\n|\r|\n")
OUT_NAME = re.compile(r"\w[\w.-]*")


def ctables():
    """intake/CONVERSION.toml of this code's own tree (as S3 reads it, and the manifest hashes it) and its sentences."""
    ct = tomllib.loads((intake_bytes.ROOT / "intake" / "CONVERSION.toml").read_text())
    return {**ct, "sentences": {r["code"]: r["sentence"] for r in ct["reason"]}}


def _in(where, got):
    """got, a Refuse placed in the file `where` names (plan 1160 A12: a conversion refusal's Detail names the file), else got unchanged."""
    return {True: lambda: Refuse(got.reason, replace(got.evidence, file=where)), False: lambda: got}[isinstance(got, Refuse)]()


def _entry(f):
    """The name of one [[file]] entry, for a Detail (file names are metadata)."""
    return f"file '{f['from']}' -> '{f['to']}'"


def _bind(x, f):
    """f(x), or x when x is a Refuse: the chain of a conversion, in which the first refusal is the result."""
    return {True: lambda: x, False: lambda: f(x)}[isinstance(x, Refuse)]()


@dataclass(frozen=True)
class Frame:
    """One output file between two steps. Invariant: the plan (below) puts each step after the stage it needs, so the step finds its field
    filled: `raw` (bytes), `lines` ((line, text) in source order), `rows` ((line, cells), a cell (text, (line, column)) naming its source
    cell), `names` (the names line's cells; a written name's source is None). `dropped` holds (line, step) of each source line a declared
    step dropped (step -1: a line with no text in any cell); `named` the names line's source line (none when written); `broadcast` the
    output columns whose source cell repeats down the rows (WIDE_TO_LONG fast and key); `not_numeric` the source cell that is no number in each
    row DROP_ROWS_NOT_NUMERIC dropped (its [line, column]: a coordinate, never the cell's text; plan 1160 A11), and `not_numeric_kind` that
    row's kind, EMPTY or TEXT (plan 1160 A16), one per row, in the same order."""
    raw: bytes = b""
    lines: tuple = ()
    rows: tuple = ()
    names: tuple = ()
    dropped: tuple = ()
    named: tuple = ()
    broadcast: frozenset = frozenset()
    not_numeric: tuple = ()
    not_numeric_kind: tuple = ()
    cut: str = "NONE"   # (plan 1160 A32) the DELIMITER that cut the lines into cells (NONE: an xlsx sheet's cells, never cut from text)


def _decoded(raw, encoding):
    """The text, or None: the one place a decode error becomes a value."""
    try:
        return raw.decode(encoding)
    except UnicodeDecodeError:
        return None


def _zipped(raw):
    """The archive, or None: the one place a zip error becomes a value."""
    try:
        return zipfile.ZipFile(io.BytesIO(raw))
    except zipfile.BadZipFile:
        return None


def _split(text):
    """The lines of a text (\\r\\n, \\r or \\n), numbered from 1; a final line break ends the last line, it opens no empty one."""
    parts = LINES.split(text)
    return tuple(enumerate(parts[:len(parts) - (parts[-1] == "")], 1))


def _member(z, fr, step):
    return {True: lambda: replace(fr, raw=z.read(step["member"])),
            False: lambda: Refuse("SOURCE_FILE_ABSENT", detail(words=[f"member '{step['member']}'"], counts={"members in the archive": len(z.namelist())}))}[step["member"] in z.namelist()]()


def _unpack(fr, step, k):
    z = _zipped(fr.raw)
    return {True: lambda: Refuse("CONTAINER_UNREADABLE", detail(words=["UNPACK: the bytes are no zip archive"])), False: lambda: _member(z, fr, step)}[z is None]()


def _decode(fr, step, k):
    text = _decoded(fr.raw, step["encoding"])
    return {True: lambda: Refuse("ENCODING_INVALID", detail(words=[f"encoding {step['encoding']}"])), False: lambda: replace(fr, raw=b"", lines=_split(text))}[text is None]()


def _marker(rule, lines):
    at = [i for i, (_, t) in enumerate(lines) if t.strip() == rule["marker"]] + [None]
    return {True: lambda: None, False: lambda: set(range(at[0] + 1))}[at[0] is None]()


DROP = {   # DROP_LINES rule kind -> (rule, lines) -> the indices of the lines it drops, or None (MARKER_LINE_ABSENT); total over its kinds
    "MARKER": _marker,
    "FIRST": lambda rule, lines: set(range(min(rule["count"], len(lines)))),
    "PREFIX": lambda rule, lines: {i for i, (_, t) in enumerate(lines) if t.startswith(rule["prefix"])},
}


def _drop(fr, step, k):
    gone = DROP[step["rule"]["kind"]](step["rule"], fr.lines)
    return {True: lambda: Refuse("MARKER_LINE_ABSENT", detail(words=[f"DROP_LINES MARKER '{step['rule']['marker']}'"], counts={"lines": len(fr.lines)})),
            False: lambda: replace(fr, lines=tuple(x for i, x in enumerate(fr.lines) if i not in gone),
                                   dropped=fr.dropped + tuple((fr.lines[i][0], k) for i in sorted(gone)))}[gone is None]()


SPLIT = {**intake_read.SPLIT, "SEMICOLON": lambda ln: next(csv.reader([ln], delimiter=";"))}   # DELIMITER from -> one line to its cells; total


def blank(cs):
    """A row with no text in any cell: the converter records it as blank (step -1), never a row, and peek prints it as `blank` (plan 1160
    A12: one definition, so peek's blank lines are the converter's)."""
    return not any(c.strip() for c in cs)


def _tabled(fr, cut):
    """Rows of cells, each cell naming its (line, column); a row with no text in any cell (blank) is recorded as blank (step -1), never a row."""
    return replace(fr, raw=b"", lines=(), rows=tuple((n, tuple((c, (n, j)) for j, c in enumerate(cs))) for n, cs in cut if not blank(cs)),
                   dropped=fr.dropped + tuple((n, -1) for n, cs in cut if blank(cs)))


def _delimit(fr, step, k):
    return replace(_tabled(fr, [(n, SPLIT[step["from"]](t)) for n, t in fr.lines]), cut=step["from"])


CELL_TEXT = {type(None): lambda v: "", str: lambda v: v, int: repr, float: repr}   # an xlsx cell as openpyxl returns it -> its text (repr: a number)
XLSX_REASON = {"NOT_AN_XLSX": "CONTAINER_UNREADABLE", "SHEET_ABSENT": "SHEET_ABSENT", "XLSX_READER_ABSENT": "XLSX_READER_ABSENT"}   # intake_read's -> ours


def sheet_rows(raw, sheet):
    """[(row number, cell texts)] of one xlsx sheet through intake_read's xlsx table (openpyxl or XLSX_READER_ABSENT), or a Refuse."""
    got = intake_read.CELLS["XLSX"](raw, {"format": {"sheet": sheet}, "comment": []})
    return {True: lambda: Refuse(XLSX_REASON[got.reason], got.detail), False: lambda: [(n, [look(CELL_TEXT, type(v), str)(v) for v in r]) for n, r in got]}[
        isinstance(got, intake_read.Unreadable)]()


def _sheet(fr, step, k):
    return _bind(sheet_rows(fr.raw, step["sheet"]), lambda cut: _tabled(fr, cut))


def _first(rule, fr):
    head = fr.rows[:1]
    return replace(fr, names=tuple(c for _, cs in head for c in cs), rows=fr.rows[1:], named=tuple(n for n, _ in head))


def _prefixed(rule, fr):
    p, head = rule["prefix"], fr.rows[:1]
    ok = len(head) == 1 and len(head[0][1]) > 0 and head[0][1][0][0].startswith(p)
    return {False: lambda: Refuse("MARKER_LINE_ABSENT", detail(words=["NAMES_LINE REPLACE_PREFIXED: the first row does not begin with the prefix"])),
            True: lambda: replace(_first(rule, fr), names=((head[0][1][0][0][len(p):], head[0][1][0][1]),) + head[0][1][1:])}[ok]()


NAMES = {   # NAMES_LINE rule kind -> (rule, frame) -> the frame with its names line, or a Refuse; total over its kinds
    "FIRST": _first,
    "WRITE": lambda rule, fr: replace(fr, names=tuple((n, None) for n in rule["names"])),
    "REPLACE_PREFIXED": _prefixed,
}


COLLAPSES = {"WHITESPACE": True, "COMMA": False, "SEMICOLON": False, "TAB": False, "NONE": False}   # (A32) Frame.cut -> does a run of white space
# swallow an empty cell (so a row narrower than the names line has lost one); total over SPLIT's delimiters and NONE (test)
WIDTH = {   # (A29) NAMES_LINE rule kind -> does the names line state the column count of every row; total over NAMES' kinds (test)
    "WRITE": lambda f: all(len(cs) == len(f.names) for _, cs in f.rows),   # written names are the declared header of every row
    "FIRST": lambda f: True, "REPLACE_PREFIXED": lambda f: True,   # the file's own names line: a short row is COLUMN_ABSENT where a column is used
}


def _named(fr, step, k):
    """The names line (NAMES), then (A32) no row narrower than it under WHITESPACE, then (A29) a written names line as wide as every row."""
    narrow = lambda f: [n for n, cs in f.rows if len(cs) < len(f.names)]
    wide = lambda f: [n for n, cs in f.rows if len(cs) != len(f.names)]
    return _bind(NAMES[step["rule"]["kind"]](step["rule"], fr), lambda f: gate([
        (lambda: not (COLLAPSES[f.cut] and narrow(f)), "EMPTY_CELL_UNDER_WHITESPACE", lambda: detail(rows=narrow(f)[:3], counts={"rows narrower than the names line": len(narrow(f)),
            "names": len(f.names)}, words=["DELIMITER WHITESPACE has no empty cell: if the file is delimited by tabs or commas, declare DELIMITER TAB or COMMA"])),
        (lambda: WIDTH[step["rule"]["kind"]](f), "NAMES_COUNT_MISMATCH", lambda: detail(rows=wide(f)[:3], counts={"names written": len(f.names),
            "rows with another number of cells": len(wide(f))}))], lambda: f))


def _mark(fr, step, k):
    swap = lambda cs: tuple((t.replace(step["mark"], "."), at) for t, at in cs)
    return replace(fr, names=swap(fr.names), rows=tuple((n, swap(cs)) for n, cs in fr.rows))


POSITION = {   # a column ref's type -> (names texts, ref) -> its 0-based index, or None (absent, ambiguous or out of range)
    int: lambda texts, ref: {True: ref - 1, False: None}[1 <= ref <= len(texts)],
    str: lambda texts, ref: look({t: i for i, t in enumerate(texts) if texts.count(t) == 1}, ref, None),   # a name held once
}


def position(fr, ref):
    return POSITION[type(ref)]([t for t, _ in fr.names], ref)


def _columns(fr, refs, then):
    """then(indices) when every ref is one column of the names line and every row holds it; else COLUMN_ABSENT."""
    at = [position(fr, r) for r in refs]
    absent = [r for r, a in zip(refs, at) if a is None]
    short = lambda: [n for n, cs in fr.rows if len(cs) <= max(at)]
    return gate([(lambda: not absent, "COLUMN_ABSENT", lambda: detail(columns=absent[:3], counts={"columns absent": len(absent), "names in the names line": len(fr.names)})),
                 (lambda: not short(), "COLUMN_ABSENT", lambda: detail(rows=short()[:3], counts={"rows too short for a declared column": len(short())}))], lambda: then(at))


def _select(fr, step, k):
    return _columns(fr, step["columns"], lambda at: replace(fr, names=tuple(fr.names[a] for a in at), rows=tuple((n, tuple(cs[a] for a in at)) for n, cs in fr.rows),
                                                            broadcast=frozenset(i for i, a in enumerate(at) if a in fr.broadcast)))


def _rename(fr, step, k):
    def renamed(at):
        new = {a: p["to"] for a, p in zip(at, step["pairs"])}
        return replace(fr, names=tuple((look(new, i, t), src) for i, (t, src) in enumerate(fr.names)))
    return _columns(replace(fr, rows=()), [p["from"] for p in step["pairs"]], renamed)


def _ranges(rule, fr, name):
    return [(p["name"], replace(fr, rows=fr.rows[p["first"] - 1:p["last"]])) for p in rule["parts"]]


def _change(rule, fr, name):
    def parts(at):
        runs = [list(rs) for _, rs in itertools.groupby(fr.rows, key=lambda r: r[1][at[0]][0])]
        return [(f"{Path(name).stem}_{i:03d}{Path(name).suffix}", replace(fr, rows=tuple(rs))) for i, rs in enumerate(runs)]
    return _columns(fr, [rule["column"]], parts)


SPLITS = {"RANGES": _ranges, "CHANGE": _change}   # SPLIT_ROWS rule kind -> (rule, frame, output name) -> [(name, frame)] | Refuse; total


def _wide(fr, step, k):
    texts = [t for t, _ in fr.names]
    def long(at):
        key, others = at[0], [j for j in range(len(texts)) if j != at[0]]
        text = [j for j in others if classify(texts[j]) is Name.TEXT]
        short = [n for n, cs in fr.rows if len(cs) < len(texts)]
        return gate([(lambda: not text, "NAMES_NOT_NUMERIC", lambda: detail(columns=[texts[j] for j in text][:3], counts={"text names besides the key": len(text)})),
                     (lambda: not short, "COLUMN_ABSENT", lambda: detail(rows=short[:3], counts={"rows shorter than the names line": len(short)}))],
                    lambda: replace(fr, names=((step["fast"], None), (step["measured"], None), (texts[key], None)), broadcast=frozenset({0, 2}),
                                    rows=tuple((n, (fr.names[j], cs[j], cs[key])) for n, cs in fr.rows for j in others)))
    return _columns(replace(fr, rows=()), [step["key"]], long)


EMPTINESS = {True: "EMPTY", False: "TEXT"}   # (A16) a dropped row -> its one kind: is every cell of it that is no number empty; total over bool


def _not_numeric(fr, step, k):
    """DROP_ROWS_NOT_NUMERIC (plan 1160 A11): each data row in which a named column's cell is no number (NUMBER: empty, or text) is dropped,
    recorded with its step, the source cell that is no number and (A16) the row's kind, classed once: EMPTY when every cell of the row that
    is no number is empty, else TEXT. Every kept row is unchanged, so the identity test still holds on it."""
    def drop(at):
        bad = lambda cs: [cs[a][1] for a in at if NUMBER.fullmatch(cs[a][0].strip()) is None]
        gone = [(n, bad(cs)[0], EMPTINESS[all(t.strip() == "" for t, _ in cs if NUMBER.fullmatch(t.strip()) is None)]) for n, cs in fr.rows if bad(cs)]
        return replace(fr, rows=tuple((n, cs) for n, cs in fr.rows if not bad(cs)), dropped=fr.dropped + tuple((n, k) for n, _, _ in gone),
                       not_numeric=fr.not_numeric + tuple(c for _, c, _ in gone), not_numeric_kind=fr.not_numeric_kind + tuple(e for _, _, e in gone))
    return _columns(fr, step["columns"], drop)


def _one(op):
    """An op on one frame as an op on one output: [(its name, the new frame)] or the Refuse."""
    return lambda name, fr, step, k: _bind(op(fr, step, k), lambda f: [(name, f)])


OPS = {   # the closed alphabet: op -> (output name, frame, step, its index among the declared steps) -> [(name, frame)] | Refuse; total over
    "UNPACK": _one(_unpack), "DECODE": _one(_decode), "DROP_LINES": _one(_drop), "DELIMITER": _one(_delimit),   # intake/CONVERSION.toml [op]
    "SHEET_TO_CSV": _one(_sheet), "NAMES_LINE": _one(_named), "DECIMAL_MARK": _one(_mark), "SELECT_COLUMNS": _one(_select),
    "RENAME": _one(_rename), "WIDE_TO_LONG": _one(_wide), "DROP_ROWS_NOT_NUMERIC": _one(_not_numeric),
    "SPLIT_ROWS": lambda name, fr, step, k: SPLITS[step["rule"]["kind"]](step["rule"], fr, name),
}
LEVEL = {"RAW": 0, "TEXT": 1, "TABLE": 2, "NAMED": 3}
DEFAULT = [{"op": "DECODE", "encoding": "utf-8-sig"}, {"op": "DELIMITER", "from": "COMMA"}, {"op": "NAMES_LINE", "rule": {"kind": "FIRST"}}]   # RAW, TEXT, TABLE
FRAMING = {"UNPACK", "DECODE", "DELIMITER", "SHEET_TO_CSV"}   # the steps that only frame a source: its cells, as the identity test reads them


def plan(steps, ct):
    """The steps as run: each declared step (with its index) after the default step of every stage it skips, then the defaults up to NAMED;
    or STEP_OUT_OF_ORDER when a step needs an earlier stage than the one before it leaves."""
    op = ct["op"]
    before = ["RAW"] + [op[s["op"]]["gives"] for s in steps]
    late = [i for i, s in enumerate(steps) if LEVEL[before[i]] > LEVEL[op[s["op"]]["stage"]]]
    run = [x for i, s in enumerate(steps) for x in [(d, -1) for d in DEFAULT[LEVEL[before[i]]:LEVEL[op[s["op"]]["stage"]]]] + [(s, i)]]
    return gate([(lambda: not late, "STEP_OUT_OF_ORDER", lambda: detail(words=[f"step {i + 1} {steps[i]['op']} needs {op[steps[i]['op']]['stage']}, after {before[i]}" for i in late][:3]))],
                lambda: run + [(d, -1) for d in DEFAULT[LEVEL[before[-1]]:]])


def _step(parts, x):
    got = [OPS[x[0]["op"]](name, fr, x[0], x[1]) for name, fr in parts]
    bad = [g for g in got if isinstance(g, Refuse)]
    return {True: lambda: bad[0], False: lambda: [p for g in got for p in g]}[len(bad) > 0]()


def run(raw, name, steps):
    """The fold of steps (as planned) over one source file's bytes: [(output name, NAMED frame)] or the first Refuse."""
    return functools.reduce(lambda acc, x: _bind(acc, lambda parts: _step(parts, x)), steps, [(name, Frame(raw=raw))])


def render(fr):
    """(the output bytes, the cell map): the names line and each row as CSV; per row, each cell's source [line, column] (None: no source)."""
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator="\n")
    w.writerow([t for t, _ in fr.names])
    w.writerows([[t for t, _ in cs] for _, cs in fr.rows])
    return buf.getvalue().encode(), [[{True: lambda a=a: list(a), False: lambda a=a: None}[a is not None]() for _, a in cs] for _, cs in fr.rows]


def _same(out, src):
    """The identity of one cell: two numbers (NUMBER) are bitwise equal as floats; anything else is equal as text."""
    num = NUMBER.fullmatch(out.strip()) is not None and NUMBER.fullmatch(src.strip()) is not None
    return {True: lambda: struct.pack("<d", float(out)) == struct.pack("<d", float(src)), False: lambda: out == src}[num]()


def frame(raw, steps, ct):
    """A source file's frame as the identity test reads it: only the framing steps (FRAMING) of its plan, so every line is cut into cells."""
    return _bind(plan(steps, ct), lambda p: _bind(run(raw, "", [x for x in p if x[0]["op"] in FRAMING]), lambda parts: parts[0][1]))


def _cell_ok(c):
    return isinstance(c, list) and len(c) == 2 and all(type(v) is int for v in c)


@dataclass(frozen=True)
class Mapped:
    """(plan 1160 A18) One unit's cell map as the identity test reads it, computed once and carried as a value: the source cells written
    outside a broadcast column (as written, a repeat kept), the lines they hold, and the lines of its not_numeric cells that are cells of
    its source frame and no number (after its DECIMAL_MARK steps). Invariant: line and column numbers only, never a cell."""
    used: tuple
    mapped: frozenset
    nonnumber: frozenset


def verify(files, units, outputs, frames):
    """The identity test. files: the [[file]] entries as declared; units: per entry {dropped, names, not_numeric}; outputs: [(record {unit,
    broadcast, cells}, its bytes)]; frames: per entry its source frame (or a Refuse). Pass(counts) | Refuse CELL_MAP_NOT_A_PERMUTATION |
    IDENTITY_FAILED. Every set is computed once (plan 1160 A18: the Mapped of each unit), so it is linear in the cells and the dropped rows."""
    grid = [{at: t for _, cs in f.rows for t, at in cs} for f in frames]
    lines = [{n for n, _ in f.rows} | {n for n, _ in f.dropped} for f in frames]
    blank = [{n for n, s in f.dropped if s == -1} for f in frames]
    data = [list(csv.reader(io.StringIO(b.decode("utf-8"))))[1:] for _, b in outputs]
    shape = [r["path"] for (r, _), rows in zip(outputs, data) if [len(x) for x in r["cells"]] != [len(x) for x in rows] or not all(c is None or _cell_ok(c) for x in r["cells"] for c in x)]
    return gate([(lambda: not shape, "CELL_MAP_NOT_A_PERMUTATION", lambda: detail(file=", ".join(_entry(files[u]) for u in sorted({r["unit"] for r, _ in outputs if r["path"] in shape})[:3]), words=shape[:3] + ["the cell map's shape is not the output's rows and columns"]))],
                lambda: _mapped(files, units, outputs, frames, data, grid, lines, blank))


def _mapped(files, units, outputs, frames, data, grid, lines, blank):
    """verify after the cell map's shape holds (so every cell is None or a [line, column]): each set once, then the gate rows in order."""
    cells = [(r["unit"], j in r["broadcast"], tuple(c), out) for (r, _), rows in zip(outputs, data) for row, outs in zip(r["cells"], rows) for j, (c, out) in enumerate(zip(row, outs))]
    sourceless = [(u, c) for u, _, c, _ in cells if c not in grid[u]]
    mark = lambda u: [s["mark"] for s in files[u]["steps"] if s["op"] == "DECIMAL_MARK"]
    src = lambda u, c: functools.reduce(lambda t, m: t.replace(m, "."), mark(u), grid[u][c])
    used = [[c for v, b, c, _ in cells if not b and v == u] for u in range(len(frames))]
    per = [Mapped(tuple(used[u]), frozenset(c[0] for c in used[u]), frozenset(
        c[0] for c in units[u]["not_numeric"] if _cell_ok(c) and tuple(c) in grid[u] and NUMBER.fullmatch(src(u, tuple(c)).strip()) is None)) for u in range(len(frames))]
    twiced = [u for u, mp in enumerate(per) if len(mp.used) != len(set(mp.used))]
    twice = sum(len(mp.used) - len(set(mp.used)) for mp in per)
    entries = lambda us: ", ".join(_entry(files[u]) for u in sorted(set(us))[:3])   # plan 1160 A12: the Detail names the file
    held = lambda u: sorted(per[u].mapped) + sorted(n for n, _ in units[u]["dropped"]) + sorted(units[u]["names"])
    why = {"DROP_LINES": lambda u, n: True, "DROP_ROWS_NOT_NUMERIC": lambda u, n: n in per[u].nonnumber}   # plan 1160 A11: a row's drop needs its cell no number
    unjustified = lambda u: [n for n, s in units[u]["dropped"] if not ({True: lambda: n in blank[u], False: lambda: look(why, files[u]["steps"][s]["op"], lambda u, n: False)(u, n)}[s == -1]())]
    unpartitioned = [u for u in range(len(frames)) if sorted(held(u)) != sorted(lines[u]) or len(set(held(u))) != len(held(u)) or unjustified(u)]
    differ = lambda: [(u, c) for u, _, c, out in cells if not _same(out, src(u, c))]
    hollow = lambda: [r for r, _ in outputs if any(all(j in r["broadcast"] for j in range(len(row))) for row in r["cells"])]
    keys = lambda r: [min(tuple(c) for j, c in enumerate(row) if j not in r["broadcast"]) for row in r["cells"]]   # after `hollow`: never empty
    unordered = lambda: [r for r, _ in outputs if any(a >= b for a, b in zip(keys(r), keys(r)[1:]))]
    cmap = "CELL_MAP_NOT_A_PERMUTATION"
    return gate([(lambda: not sourceless, cmap, lambda: detail(file=entries([u for u, _ in sourceless]), counts={"output cells with no source cell": len(sourceless)})),
                 (lambda: twice == 0, cmap, lambda: detail(file=entries(twiced), counts={"source cells written twice outside a broadcast column": twice})),
                 (lambda: not unpartitioned, cmap, lambda: detail(file=entries(unpartitioned), words=[
                     "a source line is not exactly one of: written, dropped by a declared DROP_LINES step, dropped by DROP_ROWS_NOT_NUMERIC for a cell that is no number, blank, a names line"])),
                 (lambda: not hollow(), cmap, lambda: detail(file=entries([r["unit"] for r in hollow()]), words=[r["path"] for r in hollow()][:3] + [
                     "an output row holds no source cell outside a broadcast column"])),
                 (lambda: not differ(), "IDENTITY_FAILED", lambda: detail(file=entries([u for u, _ in differ()]), rows=sorted({c[0] for _, c in differ()})[:3],
                                                                        counts={"output cells not identical to their source cell": len(differ())})),
                 (lambda: not unordered(), "IDENTITY_FAILED", lambda: detail(file=entries([r["unit"] for r in unordered()]), words=[r["path"] for r in unordered()][:3] + ["rows not in source order"]))],
                lambda: Pass(Verified(len(outputs), sum(len(x) for x in data), len(cells))))


@dataclass(frozen=True)
class Verified:
    """The identity test passed. Invariant: counts only."""
    outputs: int
    rows: int
    cells: int

    def summary(self):
        return f"the identity holds on {self.cells} cells of {self.rows} rows in {self.outputs} output files, and the cell map is a permutation"


@dataclass(frozen=True)
class Converted:
    """A bank written. Invariant: holds the out root as declared (never a machine path), and per output its name, counts and column names."""
    out: str
    verified: Verified
    listing: tuple
    split: tuple   # (A16) per file that declares DROP_ROWS_NOT_NUMERIC: (its name, {EMPTY: n, TEXT: n}), counts only

    def summary(self):
        return (f"wrote {len(self.listing)} output files and {MANIFEST} to {self.out}; {self.verified.summary()}.\n"
                + "\n".join(f"  {n}: {r} rows, {len(cs)} columns ({', '.join(NAME_SHOWN[classify(c)](c) for c in cs)})" for n, r, cs in self.listing)   # (A31) masked
                + "".join(f"\n  {f}: rows dropped as not numeric (DROP_ROWS_NOT_NUMERIC): EMPTY {k['EMPTY']}, TEXT {k['TEXT']}" for f, k in self.split))


def declared(text, ct):
    """S0 of a conversion: the declaration as plain values, or the first finding's Refuse (every finding listed)."""
    p = parse(text)
    found = p.findings((), {"format": ct, "admit": {}})
    return {True: lambda: p.data, False: lambda: Refuse(found[0].reason, detail(file="CONVERSION.toml", words=[f"{f.reason} at {f.loc or 'the file'}: {f.detail}" for f in found]))}[not found]()


def _text(p):
    return {True: lambda: Path(p).read_text(), False: lambda: ""}[Path(p).is_file()]()


def _sha(b):
    return hashlib.sha256(b).hexdigest()


def _inside(base, rel):
    """base/rel when it is a file under base, else None (a name that leaves base is no file of it)."""
    q = Path(base) / rel
    return {True: q, False: None}[q.resolve().is_relative_to(Path(base).resolve()) and q.is_file()]


def _where(conv, t):
    src, out = intake_bytes.located(conv["source"], t["roots"]), intake_bytes.located(conv["out"], t["roots"])
    return gate([(lambda: src != "" and Path(src).is_dir() and out != "", "ROOT_UNRESOLVED", lambda: detail(words=[f"source '{conv['source']}'", f"out '{conv['out']}'"]))],
                lambda: (Path(src), Path(out)))


def _sources(conv, src, loader):
    """{relative path: bytes} of every declared `from`, read once through the logged loader, or SOURCE_FILE_ABSENT."""
    rels = list(dict.fromkeys(f["from"] for f in conv["file"]))
    absent = [r for r in rels if _inside(src, r) is None]
    return gate([(lambda: not absent, "SOURCE_FILE_ABSENT", lambda: detail(file=", ".join(f"file '{r}'" for r in absent[:3]), counts={"files absent": len(absent)}))],
                lambda: {r: loader.read(src / r) for r in rels})


def _built(conv, ct, raws):
    """Every file entry planned and run: [(entry index, [(name, frame)])], or the first Refuse."""
    got = [_in(_entry(f), _bind(plan(f["steps"], ct), lambda p, f=f: run(raws[f["from"]], f["to"], p))) for f in conv["file"]]
    bad = [g for g in got if isinstance(g, Refuse)]
    return {True: lambda: bad[0], False: lambda: [(u, parts) for u, parts in enumerate(got)]}[len(bad) > 0]()


def _records(conv, ct, raws, built):
    """(units, outputs, frames): the manifest's records and the bytes they describe."""
    srcs = list(dict.fromkeys(f["from"] for f in conv["file"]))
    kinded = lambda parts: dict((c, e) for _, fr in parts for c, e in zip(fr.not_numeric, fr.not_numeric_kind))   # each dropped row once, with its one kind
    units = [{"file": u, "source": srcs.index(conv["file"][u]["from"]), "dropped": sorted({tuple(x) for _, fr in parts for x in fr.dropped}),
              "names": sorted({n for _, fr in parts for n in fr.named}), "not_numeric": [{True: lambda c=c: list(c), False: lambda: None}[c is not None]() for c in kinded(parts)],
              "not_numeric_count": len(kinded(parts)), "not_numeric_split": {e: list(kinded(parts).values()).count(e) for e in EMPTINESS.values()}}
             for u, parts in built]   # plan 1160 A11: lines and a count, never a cell; A16: the count split EMPTY / TEXT, summing to it by construction
    outs = [(name, fr, u) for u, parts in built for name, fr in parts]
    rendered = [(render(fr), name, fr, u) for name, fr, u in outs]
    outputs = [({"path": name, "unit": u, "broadcast": sorted(fr.broadcast), "rows": len(fr.rows), "columns": len(fr.names), "sha256": _sha(b), "bytes": len(b),
                 "cells": m}, b) for (b, m), name, fr, u in rendered]
    frames = [_in(_entry(f), frame(raws[f["from"]], f["steps"], ct)) for f in conv["file"]]
    return units, outputs, frames, [(name, len(fr.rows), tuple(t for t, _ in fr.names)) for name, fr, u in outs]


def _named_ok(outputs):
    names = [r["path"] for r, _ in outputs]
    bad = [n for n in names if OUT_NAME.fullmatch(n) is None or n == MANIFEST or names.count(n) > 1]
    return gate([(lambda: not bad, "OUTPUT_NAME_REFUSED", lambda: detail(file=", ".join(f"output '{n}'" for n in sorted(set(bad))[:3])))], lambda: outputs)


def _frames_ok(frames, then):
    bad = [f for f in frames if isinstance(f, Refuse)]
    return {True: lambda: bad[0], False: then}[len(bad) > 0]()


def _write(conv, out, raws, units, outputs, verified, listing):
    out.mkdir(parents=True, exist_ok=True)
    for r, b in outputs:
        (out / r["path"]).write_bytes(b)
    srcs = list(dict.fromkeys(f["from"] for f in conv["file"]))
    (out / MANIFEST).write_text(json.dumps({
        "schema": 1, "kind": "conversion-manifest", "source": conv["source"], "out": conv["out"], "files": conv["file"],
        "sources": [{"path": s, "sha256": _sha(raws[s]), "bytes": len(raws[s])} for s in srcs], "units": units, "outputs": [r for r, _ in outputs],
        "code_hash": schema.code_hash(intake_bytes.ROOT), "converter_sha256": _sha(Path(__file__).read_bytes()),
        "format_sha256": _sha((intake_bytes.ROOT / "intake" / "CONVERSION.toml").read_bytes()), "time": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}) + "\n")
    split = tuple((f"{conv['file'][u['file']]['from']} -> {conv['file'][u['file']]['to']}", u["not_numeric_split"]) for u in units
                  if "DROP_ROWS_NOT_NUMERIC" in [x["op"] for x in conv["file"][u["file"]]["steps"]])   # (A16) as s3 names a converted file
    return Pass(Converted(conv["out"], verified, tuple(listing), split))


def convert(root, ident, t, ct):
    """bin/cc intake convert <id>: S0, the roots, a bank that does not exist yet, the sources, the plan and the run of every file, the
    output names, the identity test on the bytes about to be written; then the bank and its manifest. Pass(Converted) | Refuse."""
    d = Path(root) / "declarations" / ident
    def go(conv):
        def placed(where):
            src, out = where
            loader = intake_bytes._t23().Loader({str(src): "converted-from"}, d / "conversion-access.log")
            def built(raws, b):
                units, outputs, frames, listing = _records(conv, ct, raws, b)
                return _bind(_named_ok(outputs), lambda o: _frames_ok(frames, lambda: _bind(verify(conv["file"], units, o, [f for f in frames]),
                                                                                             lambda v: _write(conv, out, raws, units, o, v.evidence, listing))))
            return gate([(lambda: not (out.is_dir() and any(out.iterdir())), "BANK_EXISTS", lambda: detail(words=[f"out '{conv['out']}'"]))],
                        lambda: _bind(_sources(conv, src, loader), lambda raws: _bind(_built(conv, ct, raws), lambda b: built(raws, b))))
        return _bind(_where(conv, t), placed)
    return _bind(declared(_text(d / "CONVERSION.toml"), ct), go)


def _manifest(text):
    """The manifest as plain values, or None when it is absent, not JSON, or not of the converter's shape: the one place that becomes a value."""
    try:
        m = json.loads(text)
        ok = (all(isinstance(m[k], list) for k in ("files", "sources", "units", "outputs")) and all(isinstance(r["cells"], list) for r in m["outputs"])
              and all(isinstance(u["not_numeric"], list) and isinstance(u["not_numeric_count"], int) for u in m["units"]))   # plan 1160 A18, A18b: both required (no default)
        return {True: m, False: None}[ok]
    except (ValueError, KeyError, TypeError):
        return None


def _manifest_in(read):
    """The manifest a reader of a bank finds: _manifest of its text, or None when the bank holds no manifest file."""
    return _bind(read(MANIFEST), lambda b: {True: lambda: None, False: lambda: _manifest(b.decode("utf-8", "replace"))}[b is None]())


def chained(m, raw_of, bank_of, ct, want):
    """The chain of a bank: its manifest (m, or None), each raw file's sha256 and each bank file's against it, `want` (key -> declared value)
    against it, then the identity test on those very bytes. Pass(Verified) | Refuse (CONVERSION_CHAIN_BROKEN, or the identity's reason)."""
    return {True: lambda: Refuse("CONVERSION_CHAIN_BROKEN", detail(words=[f"no {MANIFEST} the converter wrote"])),
            False: lambda: _chained(m, raw_of, bank_of, ct, want)}[m is None]()


def _chained(m, raw_of, bank_of, ct, want):
    raws = {s["path"]: raw_of(s["path"]) for s in m["sources"]}
    banks = [(r, bank_of(r["path"])) for r in m["outputs"]]
    broken = lambda: ([f"{k} is not the manifest's" for k, v in want.items() if m[k] != v] + [f"raw '{s['path']}'" for s in m["sources"] if raws[s["path"]] is None or _sha(raws[s["path"]]) != s["sha256"]]
                      + [f"bank '{r['path']}'" for r, b in banks if b is None or _sha(b) != r["sha256"]])
    frames = lambda: [_in(_entry(m["files"][u["file"]]), frame(raws[m["sources"][u["source"]]["path"]], m["files"][u["file"]]["steps"], ct)) for u in m["units"]]
    return gate([(lambda: not broken(), "CONVERSION_CHAIN_BROKEN", lambda: detail(words=broken()[:3], counts={"files or fields that differ": len(broken())}))],
                lambda: _frames_ok(frames(), lambda: verify(m["files"], m["units"], banks, frames())))


def _reader(base, loader):
    return lambda rel: {True: lambda: None, False: lambda: loader.read(_inside(base, rel))}[_inside(base, rel) is None]()


def verified(root, ident, t, ct):
    """bin/cc intake convert <id> --verify: the declaration, its bank's chain and the identity test on the bytes on disk."""
    d = Path(root) / "declarations" / ident
    def go(conv):
        def placed(where):
            src, out = where
            loader = intake_bytes._t23().Loader({str(src): "converted-from", str(out): "bank"}, d / "conversion-access.log")
            m = _manifest_in(_reader(out, loader))
            return chained(m, _reader(src, loader), _reader(out, loader), ct, {"files": conv["file"], "source": conv["source"], "out": conv["out"]})
        return _bind(_where(conv, t), placed)
    return _bind(declared(_text(d / "CONVERSION.toml"), ct), go)


def s3(declaration, d, t, then):
    """S3 SOURCE_INTEGRITY for a CONVERTED source: the chain from converted_from to the bank (CONVERSION_CHAIN_BROKEN, every read through
    the logged loader into declarations/<id>/access.log), then then(loader) (the bank read exactly as a DEPOSIT, through the same loader: plan 1160 P4)."""
    src = declaration.data["source"]
    bank, raw = intake_bytes.located(src["root"], t["roots"]), intake_bytes.located(src["converted_from"], t["roots"])
    def go():
        loader = intake_bytes._t23().Loader({raw: "converted-from", bank: "universe", str(Path(bank).parent): "outside-universe"}, Path(d) / "access.log")
        m = _manifest_in(_reader(bank, loader))
        got = chained(m, _reader(raw, loader), _reader(bank, loader), ctables(), {"source": src["converted_from"], "out": src["root"]})
        broken = {True: lambda: got, False: lambda: Refuse("CONVERSION_CHAIN_BROKEN", got.evidence.within(got.evidence.file, got.reason))}
        dropped = lambda: tuple((f"{m['files'][u['file']]['from']} -> {m['files'][u['file']]['to']}", u["not_numeric_count"]) for u in m["units"]
                                if "DROP_ROWS_NOT_NUMERIC" in [x["op"] for x in m["files"][u["file"]]["steps"]])   # plan 1160 A11: the census prints the count
        return {True: lambda: _bind(then(loader), lambda p: Pass(replace(p.evidence, dropped=dropped()))),
                False: lambda: broken[got.reason == "CONVERSION_CHAIN_BROKEN"]()}[isinstance(got, Pass)]()
    return gate([(lambda: "" not in (bank, raw) and Path(bank).is_dir() and Path(raw).is_dir(), "ROOT_UNRESOLVED",
                  lambda: detail(words=[f"root '{src['root']}'", f"converted_from '{src['converted_from']}'"]))], go)


def convert_cli(root, ident, args, t):
    ct = ctables()
    res = {True: lambda: verified(root, ident, t, ct), False: lambda: convert(root, ident, t, ct)}["--verify" in args]()
    print(f"convert {ident}{' --verify' * ('--verify' in args)}: " + res.text(ct["sentences"]))
    return {True: 1, False: 0}[isinstance(res, Refuse)]


def _cells(line):
    """A head line's cells, for peek: cut as a CSV line at , ; or tab when the line holds one (quotes honoured, as DELIMITER cuts), else at
    runs of blanks; empty cells are no cells, and a blank line (blank) has none."""
    cut = {True: lambda: next(csv.reader([re.sub(r"[;\t]", ",", line)]), []), False: lambda: line.split()}[re.search(r"[,;\t]", line) is not None]()
    return {True: [], False: [c.strip() for c in cut if c.strip()]}[blank(cut)]


def _named(cs):
    """Names as peek prints them: counts, and each TEXT name masked (a numeral in it as #); a NUMERIC name is counted, never printed."""
    text = [c for c in cs if classify(c) is Name.TEXT]
    named = {True: lambda: ": " + ", ".join(f"'{masked(c)}'" for c in text), False: lambda: ""}[len(text) > 0]()
    return f"{len(text)} text name{'s' * (len(text) != 1)} + {len(cs) - len(text)} numeric name{'s' * (len(cs) - len(text) != 1)}{named}"


def _said(k, cs):
    """One head line as peek prints it (_named), or blank."""
    return {True: lambda: f"line {k}: blank", False: lambda: f"line {k}: {_named(cs)}"}[blank(cs)]()


def _book_names(raw):
    """The sheet names of a workbook through openpyxl (plan 1145: xlsx is read with openpyxl or not at all), or None for bytes it cannot open."""
    import openpyxl
    try:   # the decoding boundary, as intake_read._xlsx_cells: openpyxl raises zipfile, KeyError, ValueError and its own errors
        return openpyxl.load_workbook(io.BytesIO(raw), read_only=True).sheetnames
    except Exception:
        return None


NAME_SHOWN = {Name.TEXT: lambda n: f"'{masked(n)}'", Name.NUMERIC: lambda n: "a numeric name"}   # (A21, A31) a name a file states: a numeral in it as #


def _addressed(names):
    """(plan 1160 A21) The sheets as addresses: each by its 1-based position, which --sheet and `sheet =` take, then its name as a column's
    is printed by peek (a TEXT name masked, a numeric name never)."""
    return ", ".join(f"#{k} {NAME_SHOWN[classify(n)](n)}" for k, n in enumerate(names, 1))


SHEET_WORDS = {   # (is openpyxl installed, the names it read or None) -> the words of SHEET_REQUIRED's Detail (plan 1160 A10); the names as _addressed (A21)
    (True, True): lambda names: [f"the workbook's sheets: {_addressed(names)}; name one with --sheet k (its position) or --sheet NAME"],
    (True, False): lambda names: ["openpyxl cannot open the workbook, so its sheet names cannot be listed (CONTAINER_UNREADABLE)"],
    (False, False): lambda names: ["openpyxl is not installed on this machine, so the sheet names cannot be listed here; peek on the data host"],
}


def _sheets(raw):
    """peek on an xlsx with no --sheet: SHEET_REQUIRED, its Detail the workbook's sheet names (a name is metadata; never a zip byte)."""
    has = importlib.util.find_spec("openpyxl") is not None
    names = {True: lambda: _book_names(raw), False: lambda: None}[has]()
    return Refuse("SHEET_REQUIRED", detail(words=SHEET_WORDS[(has, names is not None)](names)))


def _xlsx(raw):
    """Is it an xlsx workbook: a zip archive whose members hold xl/workbook.xml (the structural route; a name only, no byte read)."""
    z = _zipped(raw)
    return z is not None and "xl/workbook.xml" in z.namelist()


def _head(raw, sheet, encoding):
    """The lines peek may look at: [(line number, cells)] of a text file (decoded from `encoding`, utf-8-sig unless --encoding names one of
    DECODE's alphabet; an undecodable byte replaced) or of one xlsx sheet; an xlsx with no sheet named is refused SHEET_REQUIRED with its sheet names."""
    rows = lambda: _bind(sheet_rows(raw, sheet), lambda rows: [(n, [c.strip() for c in cs if c.strip()]) for n, cs in rows])
    return {(True, False): lambda: [(n, _cells(t)) for n, t in _split(raw.decode(encoding, "replace"))], (True, True): lambda: _sheets(raw),
            (False, False): rows, (False, True): rows}[(sheet == "", _xlsx(raw))]()   # plan 1160 A10: an xlsx with no --sheet is SHEET_REQUIRED


def decodes(raw, codes):
    """(plan 1160 A22) Which encodings of DECODE's alphabet decode the bytes whole: words of the alphabet only, never a byte of the file."""
    ok = [e for e in codes if _decoded(raw, e) is not None]
    return f"decodes as: {', '.join(ok) or '(none of them)'}; not as: {', '.join(e for e in codes if e not in ok) or '(none of them)'}"


def peek(raw, sheet, depth, encoding):
    """The lines peek prints: at most depth + 2 head lines, stopping before the first line whose every cell is a number (a data line)."""
    def lines(rows):
        stop = [i for i, (_, cs) in enumerate(rows) if cs and all(classify(c) is Name.NUMERIC for c in cs)] + [len(rows)]
        shown_ = rows[:min(stop[0], depth + 2)]
        return [_said(n, cs) for n, cs in shown_], {True: "a line of numbers (not printed)", False: "depth + 2 lines"}[stop[0] <= depth + 2 and stop[0] < len(rows)]
    return _bind(_head(raw, sheet, encoding), lines)


def listed(rel, base):
    """(plan 1160 A42) The file a root-named path names under the <cc-datasets> root, by MEMBERSHIP: each part after "<cc-datasets>" must be
    a name in the actual listing of the directory before it, so any name the file system allows (spaces too) is found, and a `..` part, an
    absolute path, another root or a bare name never is (no listing holds "..", "" or another root's name). "" for none."""
    parts = rel.split("/")
    step = lambda at, p: {True: lambda: {c.name: c for c in at.iterdir()}, False: dict}[at is not None and at.is_dir()]().get(p)
    at = functools.reduce(step, parts[1:], {True: Path(base), False: None}[parts[0] == "<cc-datasets>" and len(parts) > 1])
    return {True: lambda: str(at), False: lambda: ""}[at is not None and at.is_file()]()


def peek_cli(root, ident, args, t):
    """bin/cc intake peek <id> <cc-datasets>/<name>/raw/<file> [--sheet NAME|k] [--depth N] [--encoding E]: first which encodings of DECODE's
    alphabet decode the file whole (A22; --encoding, one of them, decodes the head lines), then the head of a file named by its root-named path
    (plan 1160 A19: nothing is derived from the id, which names only declarations/<id>/), resolved under the <cc-datasets> root alone and
    read through the logged loader; appended to declarations/<id>/peek.log (what was asked and how many lines were printed, never a line)."""
    d, ct = Path(root) / "declarations" / ident, ctables()
    codes, enc = list(ct["fields"]["file"]["fields"]["steps"]["variants"]["DECODE"]["encoding"]["values"]), flag(args, "--encoding", "utf-8-sig")   # (A22)
    rel, depth = {True: lambda: args[0], False: lambda: ""}[len(args) > 0](), flag(args, "--depth", "1")
    sheet = {True: int, False: str}[re.fullmatch(r"[1-9]\d*", flag(args, "--sheet", "")) is not None](flag(args, "--sheet", ""))   # (A21) a position, or a name
    base = t["roots"]["<cc-datasets>"]
    at = listed(rel, base)   # (A42: was intake_bytes.located, a character class) "" for any other root, an absolute path, a ".." part or a bare name
    ok = rel != "" and not rel.startswith("--") and re.fullmatch(r"\d+", depth) is not None
    def go():
        loader = intake_bytes._t23().Loader({base: "converted-from"}, d / "conversion-access.log")
        raw = {True: lambda: None, False: lambda: _reader(base, loader)(Path(at).relative_to(base))}[at == ""]()
        got = gate([(lambda: raw is not None, "SOURCE_FILE_ABSENT", lambda: detail(words=[f"'{rel}' (a file under the <cc-datasets> root)"])),
                    (lambda: enc in codes, "VALUE_NOT_LISTED", lambda: detail(words=[f"--encoding '{enc}'", f"DECODE's alphabet: {', '.join(codes)}"]))],
                   lambda: _bind(_in(f"file '{rel}'", peek(raw, sheet, int(depth), enc)), lambda g: (g[0], g[1], decodes(raw, codes))))   # (A22)
        with open(d / "peek.log", "a") as f:
            f.write(json.dumps({"time": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "file": rel, "sheet": sheet, "depth": depth, "encoding": enc,
                                "printed": {True: lambda: 0, False: lambda: len(got[0])}[isinstance(got, Refuse)](),
                                "stopped": {True: lambda: got.reason, False: lambda: got[1]}[isinstance(got, Refuse)]()}) + "\n")
        print({True: lambda: f"peek {ident} {rel}: " + got.text(ct["sentences"]),
               False: lambda: f"peek {ident} {rel}:\n  {got[2]}\n" + "".join(f"  {x}\n" for x in got[0]) + f"  stopped: {got[1]}"}[isinstance(got, Refuse)]())
        return {True: 1, False: 0}[isinstance(got, Refuse)]
    return {True: go, False: lambda: print("bin/cc intake peek: usage: peek <id> <cc-datasets>/<name>/raw/<file> [--sheet NAME|k] [--depth N] [--encoding E]") or 1}[ok]()
