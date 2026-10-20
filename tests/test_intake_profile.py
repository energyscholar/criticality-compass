"""test_intake_profile - plan 1165: pre-processing, the PROFILE (cc/intake_profile.py). Planted inputs only (no real data), each written here.
 T0  RESPONSE is total over FindingKind; PREDICTS + NOT_PREDICTABLE cover every live S4 reason, S4 reader reason and S5 reason of
     intake/STAGES.toml (plan 1165 section 5), and no code is in both.
 K8  Two sentinel banks (every numeric cell and slow value "-7357.", as test_intake_leak): a PER_FILE bank of five csv files and a LONG_TABLE
     file whose comment line holds a sentinel, with a MANIFEST.md beside them; profiled by profile_cli: no byte of its stdout, PROFILE.json,
     PROFILE.md, profile.log, profile-access.log or the MANIFEST holds any printed form of any sentinel cell.
 K9  A planted file whose names line is `T=-7357.5K,C,h -7357.25` and whose body holds `n/a` and `nan` cells: the names print through
     intake_names.masked (`T=#K`, `C`, `h #`: masked writes each numeral as one #, not one # per digit as plan 1165 K9's example shows);
     the n/a cell is a TEXT cell of column 2 at its line; neither text is in PROFILE.json.
 K10 The JSON walk: every leaf of PROFILE.json is an int, a sha256, a name of the profiled listing, an enum atom of the profile's enums, the
     profiled path, a comment-prefix class, or a masked string holding no numeral except in a #k position name.
 T1  (P1) one planted file per RowKind transition and per encoding and delimiter, each asserting the exact `rows` (first, last, kind,
     width[, prefix]): a title row, a names line, a body, a mid-file header, a blank line and trailing text; a ragged tail; an `n/a`
     column; an empty cell; a semicolon, a tab and a blank-separated file; a comma file with a blank after each comma (COMMA and
     WHITESPACE tie: COMMA, the first in Delimiter order); a latin-1, a utf-16 and a BOM file; a zip (members by masked name and size);
     a binary and an empty file (UNPROFILED_FORMAT, UNDECODABLE); the evidence names all four delimiters.
 T2  (P2) the order and repeat fields: the leak test's drift bank (22 FAST_RESTART sweeps, 579 rows): column 1 has monotone_runs 22,
     ASCENDING; a SAME_FAST_VALUE plant (each value 3 times): equal_runs (0, 9, 0); a revisited plant (1, 2, 1, 2, ...): revisited 2,
     equal_runs (0, 0, 0), monotone_runs 5; a runs-of-2 plant: equal_runs (2, 0, 0); a hold plant (40 equal values after 9 rising ones): longest 40, equal_runs (0, 0, 1). An XLSX (by content: a
     zip holding xl/workbook.xml) is kind XLSX; without openpyxl its sheets are NONE_READER_ABSENT (XLSX_READER_ABSENT), with it each
     sheet is profiled (a planted workbook of two sheets); the test names the case it cannot reach on a NOT REACHED HERE line.
     monotone_runs counts maximal monotone SEGMENTS of the values (intake_profile.segments: a reset between sweeps opens one segment, so
     22 sweeps are 22); intake_names.repeats' "monotone runs" counts runs of STEPS (a reset is its own run: 43 on this bank), so the
     profile takes repeats' longest run and values revisited and computes its segments itself.
 T3  (P3) RAISES is total over FindingKind; a two-file plant raises exactly its findings (code, file, lines, column), each with its RESPONSE
     row; `bin/cc intake profile` (profile_cli, in process, the plant roots of intake_plant.rooted) on <cc-datasets>/set/raw: exit 0, the
     findings printed, PROFILE.json, PROFILE.md and one profile.log line written, the MANIFEST.md beside raw/ gains one `## Profile`
     section (counts only) and keeps its other sections; profiled twice, the MANIFEST is the same but for the time and the log has two
     lines (idempotent); nothing under the profiled path changes (a hash of the tree before and after); --raw writes PROFILE-raw.json;
     a bare path is refused ROOT_UNRESOLVED (exit 1); `profile` is a row of intake.INTAKE.
 K11 A two-file plant the test never opens: profile-access.log holds two loader lines of partition "profiled" and no in-process-bypass line
     (the profile's own hooked loader sees any other open of those paths in the process).
Seen RED (each mutation applied by hand, the test run, the mutation reverted):
 - T0: a RESPONSE row deleted (ONE_FILE): FAIL; a code (CURVE_REPEATED) removed from NOT_PREDICTABLE: FAIL.
 - K8: ColumnProfile given a `first_value` field (the first cell of the column): FAIL; HeaderLine cells as the raw cells (not _name): FAIL.
 - K9: masked replaced by the identity in intake_profile._name: FAIL.
 - K10: a float leaf planted (ColumnProfile.longest given 0.5): FAIL.
 - T1: NUMERIC_WITH_EMPTY folded into NUMERIC in kind(): FAIL (the empty-cell plant's rows); the tie order reversed (CUT built from
   the four delimiters in reverse): FAIL (the tab plant elects WHITESPACE, the comma-and-blank plant WHITESPACE). Plan 1165 P1 words
   this mutation "the whitespace plant elects TAB"; reversed, ties go to WHITESPACE, so the plants that turn are the tab and the
   comma-and-blank ones.
 - T2: BIN[2] made 1 (a run of 2 counted under 3-9): FAIL (the runs-of-2 plant); revisited computed over consecutive pairs only (`sum(a == b for a, b in zip(xs, xs[1:]))`): FAIL (the revisited plant).
 - T3: a RAISES row deleted (ONE_FILE): FAIL; the section appended, never replaced (`[m is not None]` made `[False]`): FAIL (two
   `## Profile` sections); the MANIFEST written under the profiled path (the write target made Path(base) / "MANIFEST.md"): FAIL (the
   tree hash, and no section beside raw/).
 - K11: profiled reading one file with Path.read_bytes() beside the loader: FAIL (a bypass line).
"""
import contextlib
import hashlib
import io
import json
import re
import sys
import tempfile
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path[:0] = [str(ROOT / "cc"), str(ROOT / "tests")]
import intake  # noqa: E402
import intake_plant  # noqa: E402
import intake_against as A  # noqa: E402
import intake_profile as P  # noqa: E402

bad = []


def check(name, ok, why=""):
    print(("ok   " if ok else "FAIL ") + name + ("" if ok else f": {why}"))
    if not ok:
        bad.append(name)


T = intake.tables()
cell = lambda k, j, r: f"-7357.{8 - k}{99 - j:02d}{r}"   # curve k, point j, role r: as test_intake_leak
slow = lambda k: f"-7357.{k + 1}5"
CURVES = [(slow(k), [f"{cell(k, j, 1)},{cell(k, j, 2)},{cell(k, j, 3)}" for j in range(6 + k)]) for k in range(5)]
SENT = re.compile(rb"-7357\.\d+")


def forms(text):
    v = float(text)
    return {text, repr(v), f"{v:g}", f"{v:.6g}"}


def roots(tmp):
    return {**T, "roots": {**T["roots"], "<long-test>": str(Path(tmp) / "banks")}}


def run(tmp, ident, bank):
    (Path(tmp) / "declarations" / ident).mkdir(parents=True, exist_ok=True)
    return P.profile(tmp, ident, f"<long-test>/{bank}", roots(tmp))


def cli(tmp, ident, args, t=None):
    """profile_cli in process: (exit code, stdout)."""
    (Path(tmp) / "declarations" / ident).mkdir(parents=True, exist_ok=True)
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        code = P.profile_cli(tmp, ident, args, t or intake_plant.rooted(T, tmp))
    return code, buf.getvalue()


def outputs(tmp, ident):
    d = Path(tmp) / "declarations" / ident
    return {f.name: f.read_bytes() for f in d.iterdir() if f.is_file()}


# ---- T1: the text profiler, one plant per transition (no file: profiled is a function of bytes)
def rows(raw):
    p = P.profiled("plant.csv", raw)
    return p, [tuple(r for r in (x.first, x.last, x.kind, x.width, x.prefix) if r != "") for t in p.tables for x in t.rows]


ZIP = __import__("io").BytesIO()
with __import__("zipfile").ZipFile(ZIP, "w") as z:
    z.writestr("run_12.csv", "x,y\n1,2\n")
PLANTS = [   # (what, bytes, kind, encoding, delimiter, rows)
    ("title, names, body, mid-file header, blank, trailing text", b"# title line\nT,C,S\n1,2,3\n4,5,6\nT,C,S\n7,8,9\n\nend of file\n", "TEXT_TABLE",
     "UTF8", "COMMA", [(1, 1, "TEXT", 1, "#"), (2, 2, "TEXT", 3), (3, 4, "NUMERIC", 3), (5, 5, "TEXT", 3), (6, 6, "NUMERIC", 3), (7, 7, "BLANK", 0), (8, 8, "TEXT", 1)]),
    ("ragged tail", b"T,C\n1,2\n3,4\n5\n6\n", "TEXT_TABLE", "UTF8", "COMMA", [(1, 1, "TEXT", 2), (2, 3, "NUMERIC", 2), (4, 5, "NUMERIC", 1)]),
    ("an n/a column", b"T,C,S\n1,2,3\n4,n/a,6\n7,8,9\n", "TEXT_TABLE", "UTF8", "COMMA", [(1, 1, "TEXT", 3), (2, 2, "NUMERIC", 3), (3, 3, "TEXT", 3), (4, 4, "NUMERIC", 3)]),
    ("an empty cell", b"T,C,S\n1,,3\n4,5,6\n", "TEXT_TABLE", "UTF8", "COMMA", [(1, 1, "TEXT", 3), (2, 2, "NUMERIC_WITH_EMPTY", 3), (3, 3, "NUMERIC", 3)]),
    ("semicolon", b"T;C\n1.5;2\n", "TEXT_TABLE", "UTF8", "SEMICOLON", [(1, 1, "TEXT", 2), (2, 2, "NUMERIC", 2)]),
    ("tab", b"T\tC\n1\t2\n", "TEXT_TABLE", "UTF8", "TAB", [(1, 1, "TEXT", 2), (2, 2, "NUMERIC", 2)]),
    ("blank-separated", b"T  C\n1 2\n", "TEXT_TABLE", "UTF8", "WHITESPACE", [(1, 1, "TEXT", 2), (2, 2, "NUMERIC", 2)]),
    ("comma and blank tie", b"T, C\n1, 2\n", "TEXT_TABLE", "UTF8", "COMMA", [(1, 1, "TEXT", 2), (2, 2, "NUMERIC", 2)]),
    ("latin-1", "T,\u00b5\n1,2\n".encode("latin-1"), "TEXT_TABLE", "LATIN1_ONLY", "COMMA", [(1, 1, "TEXT", 2), (2, 2, "NUMERIC", 2)]),
    ("utf-16", "T,C\r\n1,2\r\n".encode("utf-16"), "TEXT_TABLE", "UTF16", "COMMA", [(1, 1, "TEXT", 2), (2, 2, "NUMERIC", 2)]),
    ("BOM", b"\xef\xbb\xbfT,C\n1,2\n", "TEXT_TABLE", "UTF8_SIG", "COMMA", [(1, 1, "TEXT", 2), (2, 2, "NUMERIC", 2)]),
    ("zip", ZIP.getvalue(), "ZIP", "UNDECODABLE", None, []),
    ("binary", b"\x89HDF\r\n\x1a\n\x00\x00\x01", "UNPROFILED_FORMAT", "UNDECODABLE", None, []),
    ("empty", b"", "UNPROFILED_FORMAT", "UNDECODABLE", None, []),
]
for what, raw, k, enc, d, want in PLANTS:
    p, got = rows(raw)
    check(f"T1 {what}: {k}, {enc}, {d}, rows", (p.kind, p.encoding, [t.delimiter for t in p.tables][:1] or [None], got) == (k, enc, [d], want),
          str((p.kind, p.encoding, [t.delimiter for t in p.tables], got)))
p = rows(PLANTS[0][1])[0]
t = p.tables[0]
check("T1 blank lines, comment prefixes, header lines (masked cells) and the four delimiters' evidence", (t.blank_lines, t.comment_prefixes,
      [h.line for h in t.header_lines], [d for d, _ in t.widths]) == (((7, 7),), (("#", 1),), [1, 2], ["COMMA", "SEMICOLON", "TAB", "WHITESPACE"]), str(t))
check("T1 the n/a cell is a TEXT cell of column 2 at line 3; the empty cell an empty one of column 2 at line 2",
      (rows(PLANTS[2][1])[0].tables[0].columns[1].text_lines, rows(PLANTS[3][1])[0].tables[0].columns[1].empty_lines) == (((3, 3),), ((2, 2),)))
check("T1 the zip's members by masked name and size", rows(ZIP.getvalue())[0].members == (("run_#csv", 8),), str(rows(ZIP.getvalue())[0].members))

# ---- T2: order, repeats, xlsx
col = lambda raw: P.profiled("plant.csv", raw).tables[0].columns[0]
drift22 = ("T,C,sigma,h\n" + "".join(f"-7357.{99 - j:02d}1,-7357.{b:02d}{j:02d}3,-7357.{b:02d}{j:02d}9,-7357.{b:02d}{j:02d}7\n"
                                      for b in range(22) for j in range(27 - (b >= 7)))).encode()   # test_intake_leak's drift bank
c = col(drift22)
check("T2 the drift bank: monotone_runs 22, ASCENDING", (c.monotone_runs, c.first_direction) == (22, "ASCENDING"), str(c)[:300])
column = lambda vs: ("T\n" + "".join(f"{v}\n" for v in vs)).encode()
c = col(column([v for v in range(9) for _ in range(3)]))
check("T2 SAME_FAST_VALUE (each of 9 values 3 times): equal_runs (0, 9, 0), longest 3", (c.equal_runs, c.longest, c.revisited) == ((0, 9, 0), 3, 0), str(c))
c = col(column([1, 2] * 5))
check("T2 revisited (1, 2 five times): revisited 2, equal_runs (0, 0, 0), monotone_runs 5", (c.revisited, c.equal_runs, c.monotone_runs, c.distinct)
      == (2, (0, 0, 0), 5, 2), str(c))
c = col(column(list(range(9)) + [9] * 40))
check("T2 hold (40 equal values after 9 rising): longest 40, equal_runs (0, 0, 1)", (c.longest, c.equal_runs, c.monotone_runs) == (40, (0, 0, 1), 1), str(c))
c = col(column([1, 1, 2, 2, 3]))
check("T2 runs of 2: equal_runs (2, 0, 0)", c.equal_runs == (2, 0, 0), str(c))
BOOK = __import__("io").BytesIO()
with __import__("zipfile").ZipFile(BOOK, "w") as z:
    z.writestr("xl/workbook.xml", "<workbook/>")
HAS_XLSX = __import__("importlib.util").util.find_spec("openpyxl") is not None
check("T2 a zip holding xl/workbook.xml is XLSX by content", P.profiled("plant.bin", BOOK.getvalue()).kind == "XLSX")
if HAS_XLSX:
    import openpyxl
    wb = openpyxl.Workbook()
    wb.active.title = "run 7"
    for r in [("T", "C"), (1, 2), (2, 3)]:
        wb.active.append(r)
    wb.create_sheet("notes").append(("a note",))
    out = __import__("io").BytesIO()
    wb.save(out)
    sh = P.profiled("plant.xlsx", out.getvalue()).sheets
    check("T2 with openpyxl: two sheets, by position and masked name, the first profiled", [(x.position, x.name, x.rows, x.columns) for x in sh]
          == [(1, "run #", 3, 2), (2, "notes", 1, 1)] and [(r.first, r.last, r.kind) for r in sh[0].table.rows] == [(1, 1, "TEXT"), (2, 3, "NUMERIC")], str(sh))
else:
    check("T2 without openpyxl: sheets NONE_READER_ABSENT", P.profiled("plant.bin", BOOK.getvalue()).sheets == P.READER_ABSENT)
print(f"  openpyxl {'installed' if HAS_XLSX else 'NOT installed'} on this machine; NOT REACHED HERE: {'the reader-absent case' if HAS_XLSX else 'the profiled sheets'}")

# ---- T3: findings, the command, the artefacts
check("T3 RAISES is total over FindingKind", set(P.RAISES) == {k.name for k in P.FindingKind}, str(set(P.RAISES) ^ {k.name for k in P.FindingKind}))
A_CSV = b"# Title\nh = 5 T\nT,C,S\n1,2,3\n2,n/a,4\n3,,5\nT,C,S\n9,8,7\n8,7,6\n\nend\n"
B_CSV = b"T;C\n1;2\n1;2\n1;2\n"
got = [(x.code, x.file, x.lines, x.column) for x in P.findings((P.profiled("a.csv", A_CSV), P.profiled("b.csv", B_CSV)))]
want = [("HEADER_LINES_BEFORE_NAMES", "a.csv", (1, 2), 0), ("COMMENT_LINES", "a.csv", (1, 1), 0), ("TEXT_RUN_IN_BODY", "a.csv", (7, 7), 0),
        ("TEXT_RUN_TRAILING", "a.csv", (11, 11), 0), ("TEXT_CELLS_IN_COLUMN", "a.csv", (5, 5), 2), ("EMPTY_CELLS_IN_COLUMN", "a.csv", (6, 6), 2),
        ("NOT_MONOTONE", "a.csv", (), 1), ("NOT_MONOTONE", "a.csv", (), 2), ("NOT_MONOTONE", "a.csv", (), 3), ("DELIMITER_NOT_COMMA", "b.csv", (), 0),
        ("COLUMNS_DIFFER_ACROSS_FILES", "b.csv", (), 0), ("EQUAL_RUNS_SHORT", "b.csv", (), 1), ("EQUAL_RUNS_SHORT", "b.csv", (), 2)]
check("T3 the two-file plant raises exactly its 13 findings", got == want, str(got))
one = P.findings((P.profiled("only.csv", b"T,C\n1,2\n3,2\n2,2\n"), P.profiled("w.bin", intake_plant.xlsx([("T", "C"), (1, 2)])),
                  P.profiled("z.bin", b"\x00\x01binary")))
check("T3 ONE_FILE, XLSX_SHEETS, UNPROFILED_FORMAT, and each finding's response is its RESPONSE row", [x.code for x in one] ==
      ["NOT_MONOTONE", "EQUAL_RUNS_SHORT", "ONE_FILE", "XLSX_SHEETS", "UNPROFILED_FORMAT"]
      and all((x.response, x.does, x.otherwise) == (P.RESPONSE[x.code][0].name,) + P.RESPONSE[x.code][1:] for x in one), str([(x.code, x.column) for x in one]))
with tempfile.TemporaryDirectory() as tmp:
    raw = Path(tmp) / "cc-datasets" / "set" / "raw"
    raw.mkdir(parents=True)
    (raw / "a.csv").write_bytes(A_CSV)
    (raw / "b.csv").write_bytes(B_CSV)
    manifest = raw.parent / "MANIFEST.md"
    manifest.write_text("# set\n\n## Files\n\n| file |\n|---|\n| a.csv |\n\n## Profile\n\nan old section\n\n## Notes\n\nkept\n")
    tree = lambda: sorted((str(q.relative_to(raw)), hashlib.sha256(q.read_bytes()).hexdigest()) for q in raw.rglob("*"))
    before = tree()
    code, said = cli(tmp, "t3", ["<cc-datasets>/set/raw"])
    first = manifest.read_text()
    code2, _ = cli(tmp, "t3", ["<cc-datasets>/set/raw"])
    second = manifest.read_text()
    d = Path(tmp) / "declarations" / "t3"
    untimed = lambda text: re.sub(r"Profiled \S+ ", "Profiled <time> ", text)
    check("T3 exit 0, the findings printed (13), PROFILE.json and PROFILE.md written", (code, code2) == (0, 0) and said.count("\n  ") >= 13
          and "TEXT_RUN_IN_BODY: a.csv lines 7-7" in said and (d / "PROFILE.json").is_file() and (d / "PROFILE.md").is_file(), said[:300])
    check("T3 the MANIFEST: one ## Profile section, its other sections kept, the old section gone", first.count("## Profile") == 1 and "## Files" in first
          and "## Notes\n\nkept" in first and "an old section" not in first and "| a.csv | TEXT_TABLE | UTF8 | COMMA | 11 | 4 | 1 | 3 | 9 |" in first, first)
    check("T3 profiled twice: the MANIFEST is the same but for the time; profile.log has two lines", untimed(first) == untimed(second)
          and len((d / "profile.log").read_text().splitlines()) == 2, second)
    check("T3 nothing under the profiled path changed", tree() == before, str(tree()))
    code, said = cli(tmp, "t3", ["--raw", "<cc-datasets>/set/raw"])
    check("T3 --raw writes PROFILE-raw.json and PROFILE-raw.md", code == 0 and (d / "PROFILE-raw.json").is_file() and (d / "PROFILE-raw.md").is_file(), said)
    code, said = cli(tmp, "t3", ["raw"])
    check("T3 a bare path is refused ROOT_UNRESOLVED, exit 1", code == 1 and "REFUSE ROOT_UNRESOLVED" in said, said)
    check("T3 `profile` is a row of intake.INTAKE", "profile" in intake.INTAKE)

# ---- T0: the tables
st = tomllib.loads((ROOT / "intake" / "STAGES.toml").read_text())
live = {r["code"] for s in st["stage"] if s["id"] in ("S4", "S5") for r in s["reason"] + s.get("reader_reason", []) if r["live"]}
check("T0 RESPONSE is total over FindingKind", set(P.RESPONSE) == {k.name for k in P.FindingKind}, str(set(P.RESPONSE) ^ {k.name for k in P.FindingKind}))
check("T0 every RESPONSE row is a Response atom with its texts", all(isinstance(r, P.Response) and isinstance(a, str) and isinstance(b, str) for r, a, b in P.RESPONSE.values()))
check("T0 every live S4 / S4 reader / S5 reason is mapped or NOT PREDICTABLE (with a reason)", live == set(A.PREDICTS) | set(A.NOT_PREDICTABLE)
      and all(w.strip() for w in A.NOT_PREDICTABLE.values()), str(live ^ (set(A.PREDICTS) | set(A.NOT_PREDICTABLE))))
check("T0 no code both mapped and NOT PREDICTABLE; every mapping is a Contradiction", not set(A.PREDICTS) & set(A.NOT_PREDICTABLE)
      and all(isinstance(c, A.Contradiction) for c in A.PREDICTS.values()))

with tempfile.TemporaryDirectory() as tmp:
    banks = Path(tmp) / "banks"
    (banks / "pf").mkdir(parents=True)
    for i, (_, rows) in enumerate(CURVES):
        (banks / "pf" / f"curve_{i:03d}.csv").write_text("T,C,sigma\n" + "".join(r + "\n" for r in rows))
    (banks / "long").mkdir()
    (banks / "long" / "bank.csv").write_text("# a sentinel long table, h = -7357.95\nT,C,sigma,h\n" + "".join(f"{r},{h}\n" for h, rows in CURVES for r in rows))
    sentinels = {m.decode() for b in ("pf", "long") for f in (banks / b).iterdir() for m in SENT.findall(f.read_bytes())}
    every = {x.encode() for s in sentinels for x in forms(s)}

    # ---- K8
    (banks / "MANIFEST.md").write_text("# the sentinel banks\n\n## Files\n\n- pf, long\n")
    for b in ("pf", "long"):
        code, said = cli(tmp, f"k8-{b}", [f"<long-test>/{b}"], roots(tmp))
        got = {**outputs(tmp, f"k8-{b}"), "stdout": said.encode(), "MANIFEST.md": (banks / "MANIFEST.md").read_bytes()}
        leaked = sorted({(n, x.decode()) for n, data in got.items() for x in every if x in data})
        check(f"K8 {b}: profiled (exit {code}); stdout, PROFILE.json, PROFILE.md, profile.log, profile-access.log and the MANIFEST hold no sentinel form",
              code == 0 and set(got) >= {"PROFILE.json", "PROFILE.md", "profile.log", "profile-access.log"} and "## Profile" in got["MANIFEST.md"].decode()
              and not leaked, f"{len(leaked)} leaks, first in {leaked[:1] and leaked[0][0]}")

    # ---- K9
    (banks / "k9").mkdir()
    (banks / "k9" / "t.csv").write_text("T=-7357.5K,C,h -7357.25\n1,2,3\n4,n/a,6\n7,nan,9\n")
    p = run(tmp, "k9", "k9")
    js = (Path(tmp) / "declarations" / "k9" / "PROFILE.json").read_text()
    t9 = p.files[0].tables[0]
    check("K9 the names print masked: T=#K, C, h #", [c.name for c in t9.columns] == ["T=#K", "C", "h #"], str([c.name for c in t9.columns]))
    check("K9 the n/a and nan cells are TEXT cells of column 2 at lines 3 and 4", t9.columns[1].text_lines == ((3, 4),) and t9.columns[1].text == 2,
          str(t9.columns[1]))
    check("K9 neither the n/a text, the nan text nor an unmasked name is in PROFILE.json", "n/a" not in js and not re.search(r"\bnan\b", js)
          and "7357" not in js and "h -" not in js)

    # ---- K10
    enums = {a.name for e in (P.FileKind, P.Encoding, P.Delimiter, P.RowKind, P.FindingKind, P.Response, A.Contradiction) for a in e}

    def leaves(x):
        return {dict: lambda: [y for v in x.values() for y in leaves(v)], list: lambda: [y for v in x for y in leaves(v)]}.get(type(x), lambda: [x])()

    for b in ("pf", "long", "k9"):
        data = json.loads((Path(tmp) / "declarations" / ("k8-" * (b != "k9") + b) / "PROFILE.json").read_text())
        names, path = set(P.listing(banks / b)), f"<long-test>/{b}"
        ok = lambda v: (type(v) is int or isinstance(v, str) and (re.fullmatch(r"[0-9a-f]{64}", v) or v in names or v in enums or v == path
                        or v in P.CLASSES or re.fullmatch(r"#\d+", v) or not re.search(r"\d", v)))
        wrong = [v for v in leaves(data) if not ok(v)]
        check(f"K10 {b}: every leaf of PROFILE.json is an int, a sha256, a listed name, an enum atom, the path or a masked string", not wrong, str(wrong[:3]))

    # ---- K11
    (banks / "res").mkdir()
    for n in ("a.csv", "b.csv"):
        (banks / "res" / n).write_text("x,y\n1,2\n")
    run(tmp, "k11", "res")
    log = [json.loads(x) for x in (Path(tmp) / "declarations" / "k11" / "profile-access.log").read_text().splitlines()]
    check("K11 two loader lines of partition 'profiled', no in-process bypass", sorted((a["route"], a["partition"]) for a in log)
          == [("loader", "profiled")] * 2, str([(a["route"], a["partition"]) for a in log]))

print("test_intake_profile:", "all passed" if not bad else f"{len(bad)} FAILED: {bad}")
sys.exit(1 if bad else 0)
