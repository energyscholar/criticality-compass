"""test_intake_reach - plan 1145 phase 1, plan-1139 error E8: every reason row of intake/STAGES.toml says whether it is live, and every live
row is returnable. Planted inputs only; each check was seen RED under a stated mutation (the plan-1145 report lists them).
 E1. Every reason row and every S4 reader_reason row carries live = true | false (a boolean, never absent); no row of a STUB stage is live.
 E2. A planted case reaches each live row: PLANTS below holds one case per row, each run through the code path a declarer meets (S0 on the
     declaration text, S2 through mint, S3-S5 folded in-process over the stage table, a reader reason as S4 READER_REFUSED's detail). Every
     case returns the code it names, and the codes reached are exactly the live rows.
     The xlsx rows depend on the machine: with openpyxl, NOT_AN_XLSX and SHEET_ABSENT are reached through S4 and XLSX_READER_ABSENT through
     the reader table's no-openpyxl row (intake_read.XLSX[False]); without it, XLSX_READER_ABSENT is reached through S4 and the two others
     cannot be reached here: the test names them on a NOT REACHED line (they are reached on the data host, docs/INTAKE-ON-A-DATA-HOST.md).
 E3. UNIT_DIFFERS is reached through a file whose header states units (header kind NAMES_UNITS).
 E4. explain (docs/INTAKE.md) and every report carry the rows that are not live."""
import importlib.util
import json
import re
import shutil
import sys
import tempfile
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path[:0] = [str(ROOT / "cc"), str(ROOT / "tests")]
import intake  # noqa: E402
import intake_blind as blind  # noqa: E402
import intake_read as rd  # noqa: E402
import intake_seal  # noqa: E402
import intake_synth  # noqa: E402
from intake_plant import long_table, outcome, per_file, rooted, run, write_long, xlsx  # noqa: E402

bad = []


def check(name, ok, why=""):
    print(("ok   " if ok else "FAIL ") + name + ("" if ok else f": {why}"))
    if not ok:
        bad.append(name)


T = intake.tables(ROOT)
ST = tomllib.loads((ROOT / "intake" / "STAGES.toml").read_text())
ROWS = [(s, k, r) for s in ST["stage"] for k in ("reason", "reader_reason") for r in blind.look(s, k, [])]
HAS_XLSX = importlib.util.find_spec("openpyxl") is not None

# ---- E1. the live flag
check("E1. every reason and reader_reason row carries live = true | false", all(type(blind.look(r, "live", None)) is bool for _, _, r in ROWS),
      str([r["code"] for _, _, r in ROWS if type(blind.look(r, "live", None)) is not bool]))
check("E1. no row of a STUB stage is live", not [r for s, _, r in ROWS if not s["implemented"] and r["live"]], str([r["code"] for s, _, r in ROWS if not s["implemented"] and r["live"]]))
LIVE = {r["code"] for _, _, r in ROWS if r["live"] is True}
check("E2. the root name <cc-datasets> resolves under the home directory (~/scratch/cc-datasets), never under the Compass root",
      T["roots"]["<cc-datasets>"] == str(Path.home() / "scratch" / "cc-datasets"), T["roots"]["<cc-datasets>"])


SEEN = set()   # every stage reason a run returned, READER_REFUSED among them (first() reports its detail's reader reason instead)


def first(out):
    """The code of the first refusal of a run, a reader reason for S4 READER_REFUSED (its detail is '<file>: <REASON>: <detail>'), else 'PASS'."""
    ref = [e.result for e in out.values() if e.mark is intake.Mark.REFUSED]
    code = {True: lambda: ref[0].reason, False: lambda: "PASS"}[bool(ref)]()
    SEEN.add(code)
    return {True: lambda: ref[0].evidence.split(": ")[1], False: lambda: code}[code == "READER_REFUSED"]()


with tempfile.TemporaryDirectory() as tmp:
    tmp = Path(tmp)
    banks = tmp / "banks"
    intake_synth.write(banks / "pf", tmp / "pf-TRUTH", "pf", 1, 9)
    m = json.loads((banks / "pf" / "MANIFEST.json").read_text())
    curves = [(f["h"], (banks / "pf" / f["name"]).read_text().splitlines()[1:]) for f in m["files"]]
    n = iter(range(1000))

    def bank(blocks=curves, raw=None, **k):
        """A planted LONG_TABLE bank directory under <tmp>/banks: the blocks written as one file, or `raw` bytes as that file."""
        name = f"b{next(n)}"
        (banks / name).mkdir()
        write_long(banks / name, blocks, **k)
        {True: lambda: None, False: lambda: (banks / name / "bank.csv").write_bytes(raw)}[raw is None]()
        return name

    def copy(edit):
        """A copy of the PER_FILE bank pf with one edit applied to its directory."""
        name = f"b{next(n)}"
        shutil.copytree(banks / "pf", banks / name)
        edit(banks / name)
        return name

    def lt(name, edit=lambda x: x, **k):
        ident = f"d{next(n)}"
        return first(run(T, tmp, ident, edit(long_table(m, ident, **k).replace("<long-test>/pf", f"<long-test>/{name}"))))

    def census(name, edit=lambda x: x):
        """The S5 census label of a LONG_TABLE declaration of bank `name` (its reason when S5 did not pass)."""
        ident = f"d{next(n)}"
        got = outcome(run(T, tmp, ident, edit(long_table(m, ident).replace("<long-test>/pf", f"<long-test>/{name}"))), "S5")
        return getattr(got[1], "label", got[0])

    def pf(name, edit=lambda x: x):
        ident = f"d{next(n)}"
        return first(run(T, tmp, ident, edit(per_file(m, ident).replace("<long-test>/pf", f"<long-test>/{name}"))))

    def twice(name, between, edit=lambda x: x):
        """Run a PER_FILE declaration of bank `name`, apply `between` (to the declaration dir and the bank dir), run it again."""
        ident = f"d{next(n)}"
        text = edit(per_file(m, ident).replace("<long-test>/pf", f"<long-test>/{name}"))
        run(T, tmp, ident, text)
        between(tmp / "declarations" / ident, banks / name, text)
        return first(run(T, tmp, ident, text))

    def mint(universe, times=1):
        ident = f"d{next(n)}"
        text = per_file(m, ident)
        d = tmp / "declarations" / ident
        d.mkdir(parents=True)
        (d / "intake.toml").write_text(text)
        (d / "transducer.toml").write_text("# planted: the seal hashes this file; S0's transducer check is not run here\n")
        decl = blind.format_stage(text, [], T).evidence
        who = {"author": "plan 1145 test", "author_kind": intake_seal.AUTHOR_KIND["ai-draft"], "confirmed_by": ""}
        got = [intake_seal.mint(decl, d, str(universe), who, ROOT, rooted(T, tmp)) for _ in range(times)][-1]
        return {True: lambda: got.reason, False: lambda: "PASS"}[got.mark is blind.Mark.REFUSED]()

    def sealed_then(between):
        """Seal a PER_FILE declaration of a copy of pf over that copy, apply `between` to the copy, then run."""
        name = copy(lambda b: None)
        ident = f"d{next(n)}"
        text = per_file(m, ident).replace("<long-test>/pf", f"<long-test>/{name}")
        d = tmp / "declarations" / ident
        d.mkdir(parents=True)
        (d / "intake.toml").write_text(text)
        (d / "transducer.toml").write_text("# planted: the seal hashes this file; S0's transducer check is not run here\n")
        who = {"author": "plan 1145 test", "author_kind": intake_seal.AUTHOR_KIND["ai-draft"], "confirmed_by": ""}
        intake_seal.mint(blind.format_stage(text, [], T).evidence, d, str(banks / name), who, ROOT, rooted(T, tmp))
        between(banks / name)
        return first(run(T, tmp, ident, text))

    base = per_file(m, "s0")
    s0 = lambda text, findings=(): {True: lambda g: g.reason, False: lambda g: "PASS"}[isinstance(blind.format_stage(text, list(findings), T), blind.Refuse)](blind.format_stage(text, list(findings), T))
    nu = 'kind = "NAMES_UNITS"\nrows = 2\nnames = 1\nunits = 2'
    xl = lambda sheet: lambda t: t.replace('[reader.format]\nkind = "COMMA"', f'[reader.format]\nkind = "XLSX"\nsheet = "{sheet}"')
    rows = [[float(x) for x in r.split(",")] + [h] for h, rs in curves for r in rs]
    asc = lambda t: t.replace('row_order = "ASCENDING"', 'row_order = "ACQUISITION"')
    PLANTS = [
        # S0 FORMAT, on the declaration text
        ("TOML_INVALID", "not TOML", lambda: s0(base + "\n[[[")),
        ("SCHEMA_UNSUPPORTED", "schema = 3", lambda: s0(base.replace("schema = 2", "schema = 3", 1))),
        ("FIELD_MISSING", "[knobs.fast] deleted", lambda: s0(re.sub(r"(?s)\[knobs\.fast\].*?(?=\[measured\])", "", base))),
        ("FIELD_UNKNOWN", "a field the format does not define", lambda: s0(base.replace("[intake]\n", "[intake]\ncolour = \"red\"\n"))),
        ("FIELD_TYPE_WRONG", "a column key that is a boolean", lambda: s0(base.replace('key = "C"', "key = true", 1))),
        ("VALUE_NOT_LISTED", "layout BY_ROW", lambda: s0(base.replace('layout = "PER_FILE"', 'layout = "BY_ROW"'))),
        ("VALUE_STILL_TODO", "intake.mode TODO", lambda: s0(base.replace('mode = "PROSPECTIVE"', 'mode = "TODO"', 1))),
        ("BIAS_KEY_UNDECLARED", "a free-text bias", lambda: s0(base.replace('bias = "MAX_MEASURED"', 'bias = "the largest C"'))),
        ("FIELD_IS_STAMPED", "a typed timestamp", lambda: s0(base.replace("[intake]\n", '[intake]\nsealed_at = "2026-10-18T09:00:00Z"\n'))),
        ("FIELD_IS_DERIVED", "a derived field typed", lambda: s0(base.replace("[acquisition]\n", "[acquisition]\ncorrelated = true\n"))),
        ("STEP_IS_INTERPOLATION", "an interpolation bridge", lambda: s0(base.replace('template = "CHAIN_SLOW"', 'template = "INTERPOLATE"'))),
        ("BRIDGE_NONE_FITS", "no bridge fits", lambda: s0(base.replace('template = "CHAIN_SLOW"', 'template = "NONE_FITS"'))),
        ("BASIS_NOT_METADATA", "a figure in the basis", lambda: s0(re.sub(r'class = "[A-Z_]+"', 'class = "FIGURE"', base, count=1))),
        ("TRANSDUCER_FILE_REFUSED", "a planted transducer finding", lambda: s0(base, ["transducer.update[0]: planted"])),
        # S2 SEAL (bin/cc intake seal)
        ("ALREADY_SEALED", "a second seal", lambda: mint(banks / "pf", 2)),
        ("UNIVERSE_ROOT_ABSENT", "a universe that is no directory", lambda: mint(tmp / "nowhere")),
        ("SELECTION_OUTSIDE_UNIVERSE", "an empty universe", lambda: mint([p for p in [tmp / "empty"] if p.mkdir() is None][0])),
        # S3 SOURCE_INTEGRITY
        ("ROOT_UNRESOLVED", "a root name ROOTS.toml does not hold", lambda: pf("pf", lambda t: t.replace("<long-test>/pf", "<no-such-root>/pf"))),
        ("PATH_NOT_ADMITTED", "a selected file deleted", lambda: pf(copy(lambda b: (b / m["files"][3]["name"]).unlink()))),
        ("PIN_MISMATCH", "a file's bytes changed after its first logged read", lambda: twice(copy(lambda b: None), lambda d, b, t: (b / m["files"][2]["name"]).write_text((b / m["files"][2]["name"]).read_text() + "3.5,0.5,0.03\n"))),
        ("UNIVERSE_CHANGED", "a file added to the universe after the seal", lambda: sealed_then(lambda b: (b / "late.csv").write_text("T,C,sigma\n"))),
        # S4 SHAPE
        ("READER_NOT_LIVE", "reader P1", lambda: pf("pf", lambda t: t.replace('name = "csv-curve-v1"', 'name = "P1"'))),
        ("COLUMNS_DIFFER", "csv-curve-v1, the first file's header T,Q,sigma", lambda: pf(copy(lambda b: (b / m["files"][0]["name"]).write_text((b / m["files"][0]["name"]).read_text().replace("T,C,sigma", "T,Q,sigma", 1))))),
        ("UNIT_DIFFERS", "E3: a NAMES_UNITS header stating T in K", lambda: lt(bank(head="T,C,sigma,h\nK,dimensionless,dimensionless,dimensionless\n"), header=nu)),
        ("ROW_ORDER_DIFFERS", "one swapped pair inside block 5", lambda: lt(bank([(h, rs[:3] + [rs[4], rs[3]] + rs[5:]) if i == 4 else (h, rs) for i, (h, rs) in enumerate(curves)]))),
        # S5 CENSUS
        ("FILE_DIFFERS_FROM_FIRST", "a later file's header T,C,err", lambda: pf(copy(lambda b: (b / m["files"][5]["name"]).write_text((b / m["files"][5]["name"]).read_text().replace("T,C,sigma", "T,C,err", 1))))),
        ("CURVE_REPEATED", "a slow value in two non-adjacent blocks", lambda: lt(bank(curves + curves[:1]))),
        ("FAST_VALUE_REPEATED", "two adjacent runs of one slow value (one block, its T repeated)", lambda: lt(bank(curves[:1] + curves), asc)),
        ("REPLICATE_KEY_UNRESOLVED", "a FILE identity on a LONG_TABLE", lambda: lt(bank(curves + curves[:1]), lambda t: t.replace('identity = "NONE"', 'identity = "FILE"'))),
        ("ACQUISITION_ORDER_DIFFERS", "ascending rows in acquisition order, declared DESCENDING", lambda: lt(bank(), lambda t: asc(t).replace('direction = "UNORDERED"', 'direction = "DESCENDING"'))),
        # S4 reader reasons (table-curve-v1), each the detail of READER_REFUSED
        ("NOT_UTF8", "a byte that is not UTF-8", lambda: lt(bank(raw=b"T,C,sigma,h\n1.5,0.2\xff,0.03,0.1\n"))),
        ("HEADER_LINE_ABSENT", "two header lines declared, one present", lambda: lt(bank(raw=b"T,C,sigma,h\n"), header=nu)),
        ("NO_DATA_ROW", "a header and no data row", lambda: lt(bank(raw=b"# nothing yet\nT,C,sigma,h\n"))),
        ("ROW_WIDTH_DIFFERS", "a short row", lambda: lt(bank(raw=b"T,C,sigma,h\n1.5,0.2,0.03,0.1\n1.6,0.2,0.03\n"))),
        ("COLUMN_NAME_ABSENT", "the slow column 'hh'", lambda: lt(bank(), slow='"hh"')),
        ("COLUMN_NAME_AMBIGUOUS", "two columns named h", lambda: lt(bank(raw=b"T,C,sigma,h,h\n1.5,0.2,0.03,0.1,0.1\n"))),
        ("COLUMN_POSITION_OUT_OF_RANGE", "the slow column at position 9", lambda: lt(bank(), slow="9")),
        ("CELL_NOT_A_NUMBER", "a cell 'n/a'", lambda: lt(bank(raw=b"T,C,sigma,h\n1.5,n/a,0.03,0.1\n"))),
    ]
    XLSX = {False: [("XLSX_READER_ABSENT", "an xlsx bank without openpyxl (S4)", lambda: lt(bank(raw=xlsx([["T", "C", "sigma", "h"]] + rows, "data")), xl("data")))],
            True: [("XLSX_READER_ABSENT", "the reader table's no-openpyxl row (intake_read.XLSX[False])", lambda: rd.XLSX[False](b"", {}).reason),
                   ("NOT_AN_XLSX", "bytes that are no workbook", lambda: lt(bank(raw=b"T,C,sigma,h\n"), xl("data"))),
                   ("SHEET_ABSENT", "sheet 'data' declared, the workbook holds 'Sheet1'", lambda: lt(bank(raw=xlsx([["T", "C", "sigma", "h"]] + rows, "Sheet1")), xl("data"))),
                   ("XLSX_GRID", "(not a reason) an xlsx bank passes S5 with the comma bank's census label", lambda: {True: "XLSX_GRID", False: "x"}[
                       census(bank(raw=xlsx([["T", "C", "sigma", "h"]] + rows, "data")), xl("data")) == census(bank())])]}[HAS_XLSX]
    NOT_HERE = {False: ["NOT_AN_XLSX", "SHEET_ABSENT"], True: []}[HAS_XLSX]
    reached = set()
    for code, what, plant in PLANTS + XLSX:
        got = plant()
        reached |= {got}
        check(f"E2. {code}: {what}", got == code, got)
    check("E2. READER_REFUSED: the reader-reason plants arrived through S4 READER_REFUSED", "READER_REFUSED" in SEEN, str(sorted(SEEN)))
    reached |= SEEN & {"READER_REFUSED"}
    print(f"  openpyxl {'installed' if HAS_XLSX else 'NOT installed'} on this machine; NOT REACHED HERE: {NOT_HERE or 'none'}")
    check("E2. the codes the plants reach are exactly the live rows (with the machine's NOT REACHED rows)",
          (reached - {"XLSX_GRID"}) | set(NOT_HERE) == LIVE, f"live, never reached: {sorted(LIVE - reached - set(NOT_HERE))}; reached, not live: {sorted(reached - LIVE - {'XLSX_GRID'})}")

    # ---- E4. explain and the report carry the rows that are not live
    dead = [f"- {s['id']} {r['code']}" for s, _, r in ROWS if not r["live"]]
    doc = (ROOT / "docs" / "INTAKE.md").read_text()
    check("E4. docs/INTAKE.md (explain) lists every row that is not live, and marks it NOT LIVE in its stage table",
          bool(dead) and all(x in doc for x in dead) and all(f"| {r['code']} | NOT LIVE |" in doc for _, _, r in ROWS if not r["live"]), str([x for x in dead if x not in doc][:3]))
    rep = intake.report(rooted(T, tmp), "pf", run(T, tmp, "rep", per_file(m, "rep")), (intake_seal.Ordering.NO_DATA_READ_LOGGED, "planted"))
    check("E4. a run's report lists every row that is not live", all(x in rep for x in dead), str([x for x in dead if x not in rep][:3]))

print("test_intake_reach: " + ("FAILED " + "; ".join(bad) if bad else "all passed"))
sys.exit(1 if bad else 0)
