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

import intake_data
import intake_read
import schema
from intake_blind import NUMBER, Name, Pass, Refuse, classify, detail, gate, look, parse, shown
from intake_names import masked

MANIFEST = "CONVERSION-MANIFEST.json"
LINES = re.compile(r"\r\n|\r|\n")
OUT_NAME = re.compile(r"\w[\w.-]*")


def ctables():
    """intake/CONVERSION.toml of this code's own tree (as S3 reads it, and the manifest hashes it) and its sentences."""
    ct = tomllib.loads((intake_data.ROOT / "intake" / "CONVERSION.toml").read_text())
    return {**ct, "sentences": {r["code"]: r["sentence"] for r in ct["reason"]}}


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
    row DROP_ROWS_NOT_NUMERIC dropped (its [line, column]: a coordinate, never the cell's text; plan 1160 A11)."""
    raw: bytes = b""
    lines: tuple = ()
    rows: tuple = ()
    names: tuple = ()
    dropped: tuple = ()
    named: tuple = ()
    broadcast: frozenset = frozenset()
    not_numeric: tuple = ()


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


SPLIT = {   # DELIMITER from -> one line to its cells; total over its values. A cell's text is never changed
    "COMMA": lambda ln: next(csv.reader([ln], delimiter=","), []),
    "SEMICOLON": lambda ln: next(csv.reader([ln], delimiter=";"), []),
    "TAB": lambda ln: next(csv.reader([ln], delimiter="\t"), []),
    "WHITESPACE": lambda ln: ln.split(),
}


def _tabled(fr, cut):
    """Rows of cells, each cell naming its (line, column); a row with no text in any cell is recorded as blank (step -1), never a row."""
    blank = lambda cs: not any(c.strip() for c in cs)
    return replace(fr, raw=b"", lines=(), rows=tuple((n, tuple((c, (n, j)) for j, c in enumerate(cs))) for n, cs in cut if not blank(cs)),
                   dropped=fr.dropped + tuple((n, -1) for n, cs in cut if blank(cs)))


def _delimit(fr, step, k):
    return _tabled(fr, [(n, SPLIT[step["from"]](t)) for n, t in fr.lines])


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


def _named(fr, step, k):
    return NAMES[step["rule"]["kind"]](step["rule"], fr)


def _mark(fr, step, k):
    swap = lambda cs: tuple((t.replace(step["mark"], "."), at) for t, at in cs)
    return replace(fr, names=swap(fr.names), rows=tuple((n, swap(cs)) for n, cs in fr.rows))


POSITION = {   # a column ref's type -> (names texts, ref) -> its 0-based index, or None (absent, ambiguous or out of range)
    int: lambda texts, ref: {True: ref - 1, False: None}[1 <= ref <= len(texts)],
    str: lambda texts, ref: {True: texts.index(ref) if ref in texts else None, False: None}[texts.count(ref) <= 1],
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


def _not_numeric(fr, step, k):
    """DROP_ROWS_NOT_NUMERIC (plan 1160 A11): each data row in which a named column's cell is no number (NUMBER: empty, or text) is dropped,
    recorded with its step and the source cell that is no number; every kept row is unchanged, so the identity test still holds on it."""
    def drop(at):
        bad = lambda cs: [cs[a][1] for a in at if NUMBER.fullmatch(cs[a][0].strip()) is None]
        gone = [(n, bad(cs)[0]) for n, cs in fr.rows if bad(cs)]
        return replace(fr, rows=tuple((n, cs) for n, cs in fr.rows if not bad(cs)), dropped=fr.dropped + tuple((n, k) for n, _ in gone),
                       not_numeric=fr.not_numeric + tuple(c for _, c in gone))
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


def verify(files, units, outputs, frames):
    """The identity test. files: the [[file]] entries as declared; units: per entry {dropped, names}; outputs: [(record {unit, broadcast,
    cells}, its bytes)]; frames: per entry its source frame (or a Refuse). Pass(counts) | Refuse CELL_MAP_NOT_A_PERMUTATION | IDENTITY_FAILED."""
    grid = [{at: t for _, cs in f.rows for t, at in cs} for f in frames]
    lines = [{n for n, _ in f.rows} | {n for n, _ in f.dropped} for f in frames]
    blank = [{n for n, s in f.dropped if s == -1} for f in frames]
    data = [list(csv.reader(io.StringIO(b.decode("utf-8"))))[1:] for _, b in outputs]
    cells = lambda: [(r["unit"], j in r["broadcast"], tuple(c), out) for (r, _), rows in zip(outputs, data) for row, outs in zip(r["cells"], rows) for j, (c, out) in enumerate(zip(row, outs))]
    shape = lambda: [r["path"] for (r, _), rows in zip(outputs, data) if [len(x) for x in r["cells"]] != [len(x) for x in rows] or not all(c is None or _cell_ok(c) for x in r["cells"] for c in x)]
    sourceless = lambda: [c for u, _, c, _ in cells() if c not in grid[u]]
    used = lambda: [(u, c) for u, b, c, _ in cells() if not b]
    twice = lambda: len(used()) - len(set(used()))
    mapped = lambda u: {c[0] for v, c in used() if v == u}
    held = lambda u: sorted(mapped(u)) + sorted(n for n, _ in units[u]["dropped"]) + sorted(units[u]["names"])
    nonnumber = lambda u: {c[0] for c in units[u].get("not_numeric", []) if _cell_ok(c) and tuple(c) in grid[u] and NUMBER.fullmatch(src(u, tuple(c)).strip()) is None}
    why = {"DROP_LINES": lambda u, n: True, "DROP_ROWS_NOT_NUMERIC": lambda u, n: n in nonnumber(u)}   # plan 1160 A11: a row's drop needs its cell no number
    unjustified = lambda u: [n for n, s in units[u]["dropped"] if not ({True: lambda: n in blank[u], False: lambda: look(why, files[u]["steps"][s]["op"], lambda u, n: False)(u, n)}[s == -1]())]
    unpartitioned = lambda: [u for u in range(len(frames)) if sorted(held(u)) != sorted(lines[u]) or len(set(held(u))) != len(held(u)) or unjustified(u)]
    mark = lambda u: [s["mark"] for s in files[u]["steps"] if s["op"] == "DECIMAL_MARK"]
    src = lambda u, c: functools.reduce(lambda t, m: t.replace(m, "."), mark(u), grid[u][c])
    differ = lambda: [c for u, _, c, out in cells() if not _same(out, src(u, c))]
    keys = lambda r: [min([tuple(c) for j, c in enumerate(row) if j not in r["broadcast"]], default=()) for row in r["cells"]]
    unordered = lambda: [r["path"] for r, _ in outputs if any(a >= b for a, b in zip(keys(r), keys(r)[1:]))]
    cmap = "CELL_MAP_NOT_A_PERMUTATION"
    return gate([(lambda: not shape(), cmap, lambda: detail(words=shape()[:3] + ["the cell map's shape is not the output's rows and columns"])),
                 (lambda: not sourceless(), cmap, lambda: detail(counts={"output cells with no source cell": len(sourceless())})),
                 (lambda: twice() == 0, cmap, lambda: detail(counts={"source cells written twice outside a broadcast column": twice()})),
                 (lambda: not unpartitioned(), cmap, lambda: detail(words=[files[u]["from"] for u in unpartitioned()][:3] + [
                     "a source line is not exactly one of: written, dropped by a declared DROP_LINES step, dropped by DROP_ROWS_NOT_NUMERIC for a cell that is no number, blank, a names line"])),
                 (lambda: not differ(), "IDENTITY_FAILED", lambda: detail(rows=sorted({c[0] for c in differ()})[:3], counts={"output cells not identical to their source cell": len(differ())})),
                 (lambda: not unordered(), "IDENTITY_FAILED", lambda: detail(words=unordered()[:3] + ["rows not in source order"]))],
                lambda: Pass(Verified(len(outputs), sum(len(x) for x in data), len(cells()))))


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

    def summary(self):
        return (f"wrote {len(self.listing)} output files and {MANIFEST} to {self.out}; {self.verified.summary()}.\n"
                + "\n".join(f"  {n}: {r} rows, {len(cs)} columns ({', '.join(shown(cs))})" for n, r, cs in self.listing))


def declared(text, ct):
    """S0 of a conversion: the declaration as plain values, or the first finding's Refuse (every finding listed)."""
    p = parse(text)
    found = p.findings((), {"format": ct, "admit": {}})
    return {True: lambda: p.data, False: lambda: Refuse(found[0].reason, detail(words=[f"{f.reason} at {f.loc or 'the file'}: {f.detail}" for f in found]))}[not found]()


def _text(p):
    return {True: lambda: Path(p).read_text(), False: lambda: ""}[Path(p).is_file()]()


def _sha(b):
    return hashlib.sha256(b).hexdigest()


def _inside(base, rel):
    """base/rel when it is a file under base, else None (a name that leaves base is no file of it)."""
    q = Path(base) / rel
    return {True: q, False: None}[q.resolve().is_relative_to(Path(base).resolve()) and q.is_file()]


def _where(conv, t):
    src, out = intake_data.located(conv["source"], t["roots"]), intake_data.located(conv["out"], t["roots"])
    return gate([(lambda: src != "" and Path(src).is_dir() and out != "", "ROOT_UNRESOLVED", lambda: detail(words=[f"source '{conv['source']}'", f"out '{conv['out']}'"]))],
                lambda: (Path(src), Path(out)))


def _sources(conv, src, loader):
    """{relative path: bytes} of every declared `from`, read once through the logged loader, or SOURCE_FILE_ABSENT."""
    rels = list(dict.fromkeys(f["from"] for f in conv["file"]))
    absent = [r for r in rels if _inside(src, r) is None]
    return gate([(lambda: not absent, "SOURCE_FILE_ABSENT", lambda: detail(words=absent[:3], counts={"files absent": len(absent)}))],
                lambda: {r: loader.read(src / r) for r in rels})


def _built(conv, ct, raws):
    """Every file entry planned and run: [(entry index, [(name, frame)])], or the first Refuse."""
    got = [_bind(plan(f["steps"], ct), lambda p, f=f: run(raws[f["from"]], f["to"], p)) for f in conv["file"]]
    bad = [g for g in got if isinstance(g, Refuse)]
    return {True: lambda: bad[0], False: lambda: [(u, parts) for u, parts in enumerate(got)]}[len(bad) > 0]()


def _records(conv, ct, raws, built):
    """(units, outputs, frames): the manifest's records and the bytes they describe."""
    srcs = list(dict.fromkeys(f["from"] for f in conv["file"]))
    units = [{"file": u, "source": srcs.index(conv["file"][u]["from"]), "dropped": sorted({tuple(x) for _, fr in parts for x in fr.dropped}),
              "names": sorted({n for _, fr in parts for n in fr.named}), "not_numeric": [{True: lambda c=c: list(c), False: lambda: None}[c is not None]()
                                                                                 for c in dict.fromkeys(c for _, fr in parts for c in fr.not_numeric)],
              "not_numeric_count": len(dict.fromkeys(c for _, fr in parts for c in fr.not_numeric))} for u, parts in built]   # plan 1160 A11: lines and a count, never a cell
    outs = [(name, fr, u) for u, parts in built for name, fr in parts]
    rendered = [(render(fr), name, fr, u) for name, fr, u in outs]
    outputs = [({"path": name, "unit": u, "broadcast": sorted(fr.broadcast), "rows": len(fr.rows), "columns": len(fr.names), "sha256": _sha(b), "bytes": len(b),
                 "cells": m}, b) for (b, m), name, fr, u in rendered]
    frames = [frame(raws[f["from"]], f["steps"], ct) for f in conv["file"]]
    return units, outputs, frames, [(name, len(fr.rows), tuple(t for t, _ in fr.names)) for name, fr, u in outs]


def _named_ok(outputs):
    names = [r["path"] for r, _ in outputs]
    bad = [n for n in names if OUT_NAME.fullmatch(n) is None or n == MANIFEST or names.count(n) > 1]
    return gate([(lambda: not bad, "OUTPUT_NAME_REFUSED", lambda: detail(words=sorted(set(bad))[:3]))], lambda: outputs)


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
        "code_hash": schema.code_hash(intake_data.ROOT), "converter_sha256": _sha(Path(__file__).read_bytes()),
        "format_sha256": _sha((intake_data.ROOT / "intake" / "CONVERSION.toml").read_bytes()), "time": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}) + "\n")
    return Pass(Converted(conv["out"], verified, tuple(listing)))


def convert(root, ident, t, ct):
    """bin/cc intake convert <id>: S0, the roots, a bank that does not exist yet, the sources, the plan and the run of every file, the
    output names, the identity test on the bytes about to be written; then the bank and its manifest. Pass(Converted) | Refuse."""
    d = Path(root) / "declarations" / ident
    def go(conv):
        def placed(where):
            src, out = where
            loader = intake_data._t23().Loader({str(src): "converted-from"}, d / "conversion-access.log")
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
        ok = all(isinstance(m[k], list) for k in ("files", "sources", "units", "outputs")) and all(isinstance(r["cells"], list) for r in m["outputs"])
        return {True: m, False: None}[ok]
    except (ValueError, KeyError, TypeError):
        return None


def chained(m, raw_of, bank_of, ct, want):
    """The chain of a bank: its manifest (m, or None), each raw file's sha256 and each bank file's against it, `want` (key -> declared value)
    against it, then the identity test on those very bytes. Pass(Verified) | Refuse (CONVERSION_CHAIN_BROKEN, or the identity's reason)."""
    raws = {s["path"]: raw_of(s["path"]) for s in m["sources"]} if m is not None else {}
    banks = [(r, bank_of(r["path"])) for r in m["outputs"]] if m is not None else []
    broken = lambda: ([f"{k} is not the manifest's" for k, v in want.items() if m[k] != v] + [f"raw '{s['path']}'" for s in m["sources"] if raws[s["path"]] is None or _sha(raws[s["path"]]) != s["sha256"]]
                      + [f"bank '{r['path']}'" for r, b in banks if b is None or _sha(b) != r["sha256"]])
    frames = lambda: [frame(raws[m["sources"][u["source"]]["path"]], m["files"][u["file"]]["steps"], ct) for u in m["units"]]
    return gate([(lambda: m is not None, "CONVERSION_CHAIN_BROKEN", lambda: detail(words=[f"no {MANIFEST} the converter wrote"])),
                 (lambda: not broken(), "CONVERSION_CHAIN_BROKEN", lambda: detail(words=broken()[:3], counts={"files or fields that differ": len(broken())}))],
                lambda: _frames_ok(frames(), lambda: verify(m["files"], m["units"], banks, frames())))


def _reader(base, loader):
    return lambda rel: {True: lambda: None, False: lambda: loader.read(_inside(base, rel))}[_inside(base, rel) is None]()


def verified(root, ident, t, ct):
    """bin/cc intake convert <id> --verify: the declaration, its bank's chain and the identity test on the bytes on disk."""
    d = Path(root) / "declarations" / ident
    def go(conv):
        def placed(where):
            src, out = where
            loader = intake_data._t23().Loader({str(src): "converted-from", str(out): "bank"}, d / "conversion-access.log")
            m = _bind(_reader(out, loader)(MANIFEST), lambda b: {True: lambda: None, False: lambda: _manifest(b.decode("utf-8", "replace"))}[b is None]())
            return chained(m, _reader(src, loader), _reader(out, loader), ct, {"files": conv["file"], "source": conv["source"], "out": conv["out"]})
        return _bind(_where(conv, t), placed)
    return _bind(declared(_text(d / "CONVERSION.toml"), ct), go)


def s3(declaration, d, t, then):
    """S3 SOURCE_INTEGRITY for a CONVERTED source: the chain from converted_from to the bank (CONVERSION_CHAIN_BROKEN, every read through
    the logged loader into declarations/<id>/access.log), then then(loader) (the bank read exactly as a DEPOSIT, through the same loader: plan 1160 P4)."""
    src = declaration.data["source"]
    bank, raw = intake_data.located(src["root"], t["roots"]), intake_data.located(src["converted_from"], t["roots"])
    def go():
        loader = intake_data._t23().Loader({raw: "converted-from", bank: "universe", str(Path(bank).parent): "outside-universe"}, Path(d) / "access.log")
        m = _bind(_reader(bank, loader)(MANIFEST), lambda b: {True: lambda: None, False: lambda: _manifest(b.decode("utf-8", "replace"))}[b is None]())
        got = chained(m, _reader(raw, loader), _reader(bank, loader), ctables(), {"source": src["converted_from"], "out": src["root"]})
        broken = {True: lambda: got, False: lambda: Refuse("CONVERSION_CHAIN_BROKEN", got.evidence.within("", got.reason))}
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
    """A head line's cells, for peek: split at , ; or tab when the line holds one, else at runs of blanks; empty cells are no cells."""
    return [c.strip() for c in {True: lambda: re.split(r"[,;\t]", line), False: lambda: line.split()}[re.search(r"[,;\t]", line) is not None]() if c.strip()]


def _named(cs):
    """Names as peek prints them: counts, and each TEXT name masked (a numeral in it as #); a NUMERIC name is counted, never printed."""
    text = [c for c in cs if classify(c) is Name.TEXT]
    named = {True: lambda: ": " + ", ".join(f"'{masked(c)}'" for c in text), False: lambda: ""}[len(text) > 0]()
    return f"{len(text)} text name{'s' * (len(text) != 1)} + {len(cs) - len(text)} numeric name{'s' * (len(cs) - len(text) != 1)}{named}"


def _said(k, cs):
    """One head line as peek prints it (_named), or blank."""
    return {True: lambda: f"line {k}: blank", False: lambda: f"line {k}: {_named(cs)}"}[len(cs) == 0]()


def _book_names(raw):
    """The sheet names of a workbook through openpyxl (plan 1145: xlsx is read with openpyxl or not at all), or None for bytes it cannot open."""
    import openpyxl
    try:   # the decoding boundary, as intake_read._xlsx_cells: openpyxl raises zipfile, KeyError, ValueError and its own errors
        return openpyxl.load_workbook(io.BytesIO(raw), read_only=True).sheetnames
    except Exception:
        return None


SHEET_WORDS = {   # (is openpyxl installed, the names it read or None) -> the words of SHEET_REQUIRED's Detail (plan 1160 A10); the names as _named
    (True, True): lambda names: [f"the workbook's sheets: {_named(names)}"],
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


def _flag(args, name, absent):
    return {True: lambda: args[args.index(name) + 1], False: lambda: absent}[name in args and args.index(name) + 1 < len(args)]()


def _head(raw, sheet):
    """The lines peek may look at: [(line number, cells)] of a text file (utf-8, an undecodable byte replaced) or of one xlsx sheet; an xlsx
    with no sheet named is refused SHEET_REQUIRED with its sheet names."""
    rows = lambda: _bind(sheet_rows(raw, sheet), lambda rows: [(n, [c.strip() for c in cs if c.strip()]) for n, cs in rows])
    return {(True, False): lambda: [(n, _cells(t)) for n, t in _split(raw.decode("utf-8", "replace"))], (True, True): lambda: _sheets(raw),
            (False, False): rows, (False, True): rows}[(sheet == "", _xlsx(raw))]()   # plan 1160 A10: an xlsx with no --sheet is SHEET_REQUIRED


def peek(raw, sheet, depth):
    """The lines peek prints: at most depth + 2 head lines, stopping before the first line whose every cell is a number (a data line)."""
    def lines(rows):
        stop = [i for i, (_, cs) in enumerate(rows) if cs and all(classify(c) is Name.NUMERIC for c in cs)] + [len(rows)]
        shown_ = rows[:min(stop[0], depth + 2)]
        return [_said(n, cs) for n, cs in shown_], {True: "a line of numbers (not printed)", False: "depth + 2 lines"}[stop[0] <= depth + 2 and stop[0] < len(rows)]
    return _bind(_head(raw, sheet), lines)


def peek_cli(root, ident, args, t):
    """bin/cc intake peek <id> <file> [--sheet NAME] [--depth N]: the head of <cc-datasets>/<id>/raw/<file>, read through the logged loader;
    appended to declarations/<id>/peek.log (what was asked and how many lines were printed, never a line)."""
    d, ct = Path(root) / "declarations" / ident, ctables()
    rel, sheet, depth = {True: lambda: args[0], False: lambda: ""}[len(args) > 0](), _flag(args, "--sheet", ""), _flag(args, "--depth", "1")
    base = intake_data.located(f"<cc-datasets>/{ident}/raw", t["roots"])
    ok = rel != "" and not rel.startswith("--") and re.fullmatch(r"\d+", depth) is not None
    def go():
        loader = intake_data._t23().Loader({base: "converted-from"}, d / "conversion-access.log")
        raw = _reader(base, loader)(rel)
        got = {True: lambda: Refuse("SOURCE_FILE_ABSENT", detail(words=[f"'{rel}' under <cc-datasets>/{ident}/raw"])), False: lambda: peek(raw, sheet, int(depth))}[raw is None]()
        with open(d / "peek.log", "a") as f:
            f.write(json.dumps({"time": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "file": rel, "sheet": sheet, "depth": depth,
                                "printed": {True: lambda: 0, False: lambda: len(got[0])}[isinstance(got, Refuse)](),
                                "stopped": {True: lambda: got.reason, False: lambda: got[1]}[isinstance(got, Refuse)]()}) + "\n")
        print({True: lambda: f"peek {ident} {rel}: " + got.text(ct["sentences"]),
               False: lambda: f"peek {ident} {rel}:\n" + "".join(f"  {x}\n" for x in got[0]) + f"  stopped: {got[1]}"}[isinstance(got, Refuse)]())
        return {True: 1, False: 0}[isinstance(got, Refuse)]
    return {True: go, False: lambda: print("bin/cc intake peek: usage: peek <id> <file under <cc-datasets>/<id>/raw> [--sheet NAME] [--depth N]") or 1}[ok]()
