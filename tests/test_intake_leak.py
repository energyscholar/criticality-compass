"""test_intake_leak - plan 1160 P0: no output of the intake carries a data value. Planted inputs only (no real data).
 K1. Two sentinel banks, a PER_FILE bank (five csv-curve-v1 files) and a LONG_TABLE bank (one table-curve-v1 file), whose every numeric cell,
     and every declared slow value, is drawn from a sentinel alphabet: decimal text that begins "-7357.", so each of its printed forms (the raw
     text, repr(float), f"{v:g}", f"{v:.6g}") holds "-7357." or rounds to a string no other output holds. Both pass S5 CENSUS.
 K2. Every live reason row of intake/STAGES.toml (and every live S4 reader reason) is planted on those banks, through the commands a declarer
     runs: `bin/cc intake lint | seal | run` (intake.cli, in process, on a copy of the Compass whose ROOTS.toml names the banks). The plant
     table is total: the codes reached are exactly the live rows (with the machine's NOT REACHED xlsx rows, as test_intake_reach). Plan 1160
     P0 said "reuse test_intake_reach.PLANTS"; that table is built inside a temporary directory over the synthetic bank and is not importable,
     so this test carries its own plant per row over the sentinel banks, with the same totality check.
 K3. No byte of intake-report.md, SEAL.json, seal.log, access.log, stdout or stderr of any plant holds any sentinel cell in any of its forms.
 K4. The report's census section lists the curves by ordinal and file name.
     (1160 A13) The ordering note of a bank converted under its declaration's id and sealed after the conversion counts the raw files the
     conversion read before the seal (CONVERSION_READ_BEFORE_SEAL (n files)), and names none.
 K5. (1160 P2) A FAST_RESTART drift bank (22 sweeps, 579 rows, every slow value a distinct sentinel) forms 22 curves and its report gives
     distinct_slow_in_block max = 27, a count.
 K7. (1160 P6) RESULT.json (the terminal's record, written when S10 passed) holds numbers ONLY in these fields: the ranks and counts
     (schema, m, lo_rank, hi_rank, end, n_tied, n_curves), the declared Z (tier_z) and the slow values of the span (span_slow, end_slow; a
     sentinel there is the declared slow value of a curve, as the declaration itself states it). Every other byte of RESULT.json is in K3's
     scan; the S10 report line (the COMPLETION output: result type, ranks, tier, n_tied, n_curves, identifiability) is in intake-report.md.
 K6. (1160 P3) No byte of `bin/cc intake convert` stdout (convert and --verify), CONVERSION-MANIFEST.json, conversion-access.log, `bin/cc
     intake peek` stdout or peek.log holds a sentinel: the sentinel PER_FILE files converted as they are, and a WIDE sentinel file (its
     names line h + sentinel numeric names) peeked and converted by WIDE_TO_LONG. The copy's <cc-datasets> and <cc-banks> name <tmp>.
Seen RED (each mutation applied by hand, the test run, the mutation reverted):
 - (1160 A13) intake_seal.ordering's conversion clause keyed always False: K4 "(1160 A13)" FAILS.
 - the fast-span summary reinstated in cc/intake_evidence.py Census.summary (`{x.fast} span [{lo:g}, {hi:g}]`): K3 FAILS on the two PASS runs;
 - _blocks' where reinstated as f"{f.name} block {i} ({g.columns[-1]} = {h:g})": K3 FAILS (the LONG_TABLE census section and CURVE_REPEATED);
 - _resolve's COLUMN_NAME_ABSENT detail printing the names line (f"... {names}"): K3 FAILS on the numeric-names plant;
 - Census.listing printing the slow value instead of the where: K4 and K3 FAIL;
 - (1160 P2, A1) intake_blind.SELECTED["PER_FILE"] made 1: the SELECTION_EMPTY plant passes S1 and the run crashes at S4 (files[0]);
 - (1160 P2) BREAK["FAST_RESTART"] made the EXACT rule: K2 FAILS on the two-sweep FAST_RESTART PASS plant (CURVE_REPEATED) and K5 FAILS (579 one-point curves);
 - (1160 P2) intake_names.masked returning the stated text unmasked: K3 FAILS on both UNIT_DIFFERS plants whose unit holds a sentinel
   (NAMES_UNITS 'K -7357.15', NAMES_UNITS_IN_NAMES 'T/K -7357.25').;
 - (1160 A11) intake_convert.s3 setting no dropped counts: K4 FAILS (the census section of the DROP_ROWS_NOT_NUMERIC plant);
 - (1160 A10) intake_convert._named printing every sheet name unmasked: K6 FAILS where openpyxl is installed (here, without openpyxl, the
   names are not listed: NOT seen red on this machine; the word table is seen red in test_intake_convert V4);
 - (1160 P3) intake_convert._said printing every head cell unmasked (numeric names included): K6 FAILS (peek stdout and peek.log);
 - (1160 P3) intake_convert._records adding each output's first data line to its manifest record: K6 FAILS on all four conversions;
 - (1160 P4) each S1 row's holds made `lambda: True` in cc/intake_choices.py, one at a time (the ten rows of intake_plant.CHOICE_PLANTS):
   that row's K2 plant(s) FAIL (PASS, or a later stage's code) and K2's totality FAILS; intake_seal.SEEN["PROSPECTIVE"] made True: the
   MODE_CONTRADICTS_SOURCE plant and K2's totality FAIL; S6's READ_NOT_LOGGED or BYPASS_READ_LOGGED holds made True: that plant (the
   deleted loader lines; the direct open()) and K2's totality FAIL; a CONVERTED bank read through a second loader: the converted PASS plant
   FAILS (BYPASS_READ_LOGGED).
 - (1160 P5) ENDS["ARGMAX_FAST"] or PAIRS["PAIR_NEAREST_FAST"] made empty in cc/intake_feasible.py: that K2 SECOND_LANE_INFEASIBLE plant
   FAILS (PASS); S9's PASS evidence given the first curve's anchor as a word (f"anchor {v!r}"): K3 FAILS on every PASS run; S9's refusal
   detail given the anchor inside a word: K3 FAILS on both SECOND_LANE_INFEASIBLE plants. (The anchor as a bare-number word did NOT go
   red: intake_names.detail prints it as "a numeric word", the structural mask.)"""
import contextlib
import hashlib
import io
import json
import re
import shutil
import sys
import tempfile
import types
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path[:0] = [str(ROOT / "cc"), str(ROOT / "tests")]
import importlib.util  # noqa: E402

import intake  # noqa: E402
import intake_blind as blind  # noqa: E402
import intake_fold  # noqa: E402
import intake_say  # noqa: E402
import intake_seal  # noqa: E402
import intake_synth  # noqa: E402
from intake_plant import ALL_ALTERNATIVE, PRIMARY_PAIR, SHIFT, BLOCK, BLOCK_NO_FLOOR, IID, PAIR_LANE, SAME_FAST, VALIDATED, CHOICE_PLANTS, conversion, long_table, per_file, slow_source, workbook, write_long, xlsx  # noqa: E402

bad = []


def check(name, ok, why=""):
    print(("ok   " if ok else "FAIL ") + name + ("" if ok else f": {why}"))
    if not ok:
        bad.append(name)


HAS_XLSX = importlib.util.find_spec("openpyxl") is not None
K = 5   # curves
SENT = re.compile(rb"-7357\.\d+")   # a sentinel cell as written in a bank file or a declaration
cell = lambda k, j, r: f"-7357.{8 - k}{99 - j:02d}{r}"   # curve k, point j, role r (1 fast, 2 measured, 3 sigma): fast ascends in j; no rounding carry
slow = lambda k: f"-7357.{k + 1}5"
CURVES = [(slow(k), [f"{cell(k, j, 1)},{cell(k, j, 2)},{cell(k, j, 3)}" for j in range(6 + k)]) for k in range(K)]
M = {"seed": 7357, "reader": "csv-curve-v1", "pattern": "curve_{index:03d}.csv", "columns": ["T", "C", "sigma"], "replicate": "NONE",
     "slow": {"name": "h", "unit": "dimensionless"}, "fast": {"name": "T", "unit": "dimensionless", "column": "T"},
     "measured": {"name": "C", "unit": "dimensionless", "column": "C"}, "files": [{"name": f"curve_{i:03d}.csv", "h": float(h)} for i, (h, _) in enumerate(CURVES)],
     "generator": {"path": "cc/intake_synth.py", "sha256": hashlib.sha256((ROOT / "cc" / "intake_synth.py").read_bytes()).hexdigest()}}
TRANS = intake_synth.declare(M, "x", "pf")[2]


@dataclass(frozen=True)
class AtS6:
    """(1160 P4) A plant step: `bin/cc intake run` in process (report written and printed as run writes it) with edit(bank dir, declaration
    dir) applied between S5 and S6, so S6's body reads the access log as edited; one loader per run, as the command has."""
    edit: object


def forms(text):
    """Every printed form of one sentinel cell: the raw text, repr(float), f"{v:g}", f"{v:.6g}"."""
    v = float(text)
    return {text, repr(v), f"{v:g}", f"{v:.6g}"}


with tempfile.TemporaryDirectory() as tmp:
    tmp = Path(tmp)
    w, banks = tmp / "cc", tmp / "banks"
    shutil.copytree(ROOT, w, ignore=shutil.ignore_patterns(".git", "__pycache__", "results", "benchmark", "fixtures", "data", "scratch"))
    roots = [ln for ln in (w / "intake" / "ROOTS.toml").read_text().splitlines() if not ln.startswith(('"<cc-datasets>"', '"<cc-banks>"'))]   # 1160 P3: both under tmp
    (w / "intake" / "ROOTS.toml").write_text("\n".join(roots) + f'\n"<leak>" = "{banks}"   # test_intake_leak: the sentinel banks\n'
                                             f'"<cc-datasets>" = "{tmp / "cc-datasets"}"\n"<cc-banks>" = "{tmp / "cc-banks"}"\n')
    n = iter(range(1000))

    def pf_bank(edit=lambda b: None, curves=CURVES):
        name = f"pf{next(n)}"
        (banks / name).mkdir(parents=True)
        for i, (_, rows) in enumerate(curves):
            (banks / name / f"curve_{i:03d}.csv").write_text("T,C,sigma\n" + "".join(r + "\n" for r in rows))
        (banks / name / "MANIFEST.json").write_text('{"planted": "test_intake_leak"}\n')   # plan 1160 P1: the file the declaration excludes (the seal partitions the universe)
        edit(banks / name)
        return name

    def lt_bank(blocks=CURVES, raw=None, **k):
        name = f"lt{next(n)}"
        (banks / name).mkdir(parents=True)
        write_long(banks / name, blocks, **k)
        {True: lambda: None, False: lambda: (banks / name / "bank.csv").write_bytes(raw)}[raw is None]()
        return name

    def pf(bank, edit=lambda t: t):
        return lambda ident: edit(per_file(M, ident).replace("<long-test>/pf", f"<leak>/{bank}"))

    def lt(bank, edit=lambda t: t, **k):
        return lambda ident: edit(long_table(M, ident, **k).replace("<long-test>/pf", f"<leak>/{bank}"))

    def cli(*args):
        """One `bin/cc intake ...` command in process: (stdout + stderr)."""
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            intake.cli(w, list(args))
        return out.getvalue() + err.getvalue()

    SEAL = ("seal", "--author", "plan 1160 leak test", "--as", "ai-draft", "--unconfirmed")   # (1160 A20: was SEAL(u) with --universe u; the universe is the root)

    def plant(text, bank, steps, trans=TRANS, ident=None):
        """Write the declaration, run `steps` (each a tuple of CLI words after the id, or a function of the bank dir), and return (its code,
        everything it printed and wrote). Its code is the first REFUSE code printed (the reader reason for READER_REFUSED), else PASS. The id is
        a new one, or (1160 A13) `ident`: a conversion's own id, whose declarations/<id>/ holds its CONVERSION.toml and conversion-access.log."""
        ident = {True: lambda: f"d{next(n)}", False: lambda: ident}[ident is None]()
        d = w / "declarations" / ident
        d.mkdir(parents=True, exist_ok=True)
        (d / "intake.toml").write_text(text(ident))
        (d / "transducer.toml").write_text(trans.replace('id = "x"', f'id = "{ident}"'))
        step = {tuple: lambda s: cli(s[0], ident, *s[1:]), types.FunctionType: lambda s: (s(banks / bank), "")[1], AtS6: lambda s: at_s6(ident, bank, s.edit)}   # total over the step kinds
        said = "".join(step[type(s)](s) for s in steps)
        wrote = "".join((d / x).read_text() for x in ("intake-report.md", "SEAL.json", "seal.log", "access.log") if (d / x).is_file())
        wrote += {True: lambda: scrubbed(d / "RESULT.json", ident), False: lambda: ""}[(d / "RESULT.json").is_file()]()   # 1160 P6 (K7)
        m = re.search(r"REFUSE (\w+)\. [^\n]*?Detail: (?:[^;\n]*; )?(\w*)", said)
        code = {True: lambda: "PASS", False: lambda: {True: lambda: m[2], False: lambda: m[1]}[m[1] == "READER_REFUSED"]()}[m is None]()
        return code, said + wrote, ident

    NUMBERS = {"schema", "m", "lo_rank", "hi_rank", "end", "n_tied", "n_curves", "tier_z", "span_slow", "end_slow"}   # (1160 P6, K7) RESULT.json's numeric fields
    SLOW_FIELDS = {"span_slow", "end_slow"}   # the only ones that hold a data value: the declared slow values of the span
    RESULTS, MISPLACED = {}, []

    def numbers(x, key=""):
        """Every (field, number) of a JSON value; a number inside a list belongs to the list's field."""
        walk = {dict: lambda: [p for k, v in x.items() for p in numbers(v, k)], list: lambda: [p for v in x for p in numbers(v, key)]}
        return walk.get(type(x), lambda: [(key, x)] * (type(x) in (int, float)))()

    def scrubbed(path, ident):
        """(1160 P6, K7) RESULT.json as K3 scans it: the text with the slow-value fields removed (their numbers are exempt, declared above);
        a number in any field outside NUMBERS is recorded as MISPLACED."""
        rec = json.loads(path.read_text())
        RESULTS[ident] = path.read_text()
        MISPLACED.extend((ident, k) for k, _ in numbers(rec) if k not in NUMBERS)
        drop = lambda x: {dict: lambda: {k: drop(v) for k, v in x.items() if k not in SLOW_FIELDS}, list: lambda: [drop(v) for v in x]}.get(type(x), lambda: x)()
        return json.dumps(drop(rec))

    def at_s6(ident, bank, edit):
        """(1160 P4) The run of an AtS6 step: intake.run's fold, with S6's body called after edit(bank dir, declaration dir)."""
        t, d = intake.tables(w), w / "declarations" / ident
        b = intake.bodies(t, d, (d / "intake.toml").read_text(), intake._findings(w, d, ident))
        out = intake_fold.fold(t["stages"]["stage"], {**b, "S6": lambda census: (edit(banks / bank, d), b["S6"](census))[1]})
        text = intake_say.report(t, ident, out, intake_seal.ordering(d, t))
        (d / "intake-report.md").write_text(text)
        return text

    def unlog(d, name):
        """(1160 P4) The access log without the loader lines of file `name`."""
        (d / "access.log").write_text("".join(ln + "\n" for ln in (d / "access.log").read_text().splitlines() if not json.loads(ln)["path"].endswith("/" + name)))

    PF, LT = pf_bank(), lt_bank()

    def convert(text, root, frm="<cc-datasets>/leak/raw"):
        """(1160 P1) [source] kind CONVERTED, its root `root`, converted_from `frm` (1160 P3: CONVERSION-MANIFEST.json excluded where
        MANIFEST.json was)."""
        return re.sub(r'root = "[^"]*"', f'root = "{root}"', text.replace('kind = "DEPOSIT"', f'kind = "CONVERTED"\nconverted_from = "{frm}"', 1)
                      .replace('file = "MANIFEST.json"', 'file = "CONVERSION-MANIFEST.json"', 1), count=1)

    CONVERTED = {}   # (1160 P3) K6: what each conversion printed and wrote

    def conv_bank(raws, files, edit=lambda raw, bank: None):
        """(1160 P3) <tmp>/cc-datasets/<name>/raw holding `raws` ({file: bytes}), converted by `bin/cc intake convert` (and --verify) per
        `files` ([(from, to, steps)]), then `edit` (on the raw and bank directories): the name."""
        name = cid = f"cv{next(n)}"   # one id: declarations/<id>/CONVERSION.toml converts <cc-datasets>/<id>/raw, where peek <id> looks
        raw, bank, d = tmp / "cc-datasets" / name / "raw", tmp / "cc-banks" / name / "bank", w / "declarations" / cid
        raw.mkdir(parents=True)
        d.mkdir(parents=True)
        [(raw / f).write_bytes(b) for f, b in raws.items()]
        (d / "CONVERSION.toml").write_text(conversion(f"<cc-datasets>/{name}/raw", f"<cc-banks>/{name}/bank", files))
        said = cli("convert", cid) + cli("convert", cid, "--verify")
        CONVERTED[name] = said + "".join(q.read_text() for q in (bank / "CONVERSION-MANIFEST.json", d / "conversion-access.log") if q.is_file())
        edit(raw, bank)
        return name

    curve_files = {f"curve_{i:03d}.csv": (banks / PF / f"curve_{i:03d}.csv").read_bytes() for i in range(K)}
    as_is = [(f, f, "") for f in curve_files]
    NN = {f: b.replace(b"\n", f"\n{cell(i, 60, 1)},n/a,{cell(i, 60, 3)}\n".encode(), 1) for i, (f, b) in enumerate(curve_files.items())}   # (1160 A11) a not-numeric row
    cv = lambda name: (pf(PF, lambda t: convert(t, f"<cc-banks>/{name}/bank", f"<cc-datasets>/{name}/raw")), PF)

    def keyed(line):
        """(1160 P1) A bank edit: each curve file i gets `line(i)` above its names line (a FILE_KEY header line)."""
        return lambda b: [(b / f"curve_{i:03d}.csv").write_text(line(i) + (b / f"curve_{i:03d}.csv").read_text()) for i in range(K)]
    full = lambda bank: (("lint",), SEAL, ("run",))
    unsealed = (("lint",), ("run",))
    append = lambda name, text: lambda b: (b / name).write_text((b / name).read_text() + text)
    asc = lambda t: t.replace('row_order = "ASCENDING"', 'row_order = "ACQUISITION"')
    nu = 'kind = "NAMES_UNITS"\nrows = 2\nnames = 1\nunits = 2'
    inn = lambda syntax: f'kind = "NAMES_UNITS_IN_NAMES"\nrows = 1\nnames = 1\nunit_syntax = "{syntax}"'   # 1160 P2
    xl = lambda t: t.replace('[reader.format]\nkind = "COMMA"', '[reader.format]\nkind = "XLSX"\nsheet = "data"')
    rows = [[float(x) for x in r.split(",")] + [float(h)] for h, rs in CURVES for r in rs]
    numeric_names = ("T,C,sigma,h\n" + "".join(f"{r},{h}\n" for h, rs in CURVES for r in rs)).replace("T,C,sigma,h", "h," + ",".join(cell(0, j, 1) for j in range(3)), 1).encode()
    (_, r0), (_, r1) = CURVES[1], CURVES[0]   # (1160 P2) sweep 1 in curve 1's T cells, sweep 2 in curve 0's (lower): T turns back between them
    SWEEPS = [(slow(1), r0[:2]), (slow(2), r0[2:4]), (slow(3), r0[4:]), (slow(4), r1[:2]), (slow(1), r1[2:4]), (slow(2), r1[4:])]
    drift22 = ("T,C,sigma,h\n" + "".join(f"-7357.{99 - j:02d}1,-7357.{b:02d}{j:02d}3,-7357.{b:02d}{j:02d}9,-7357.{b:02d}{j:02d}7\n"
                                          for b in range(22) for j in range(27 - (b >= 7)))).encode()   # 7 sweeps of 27 rows, 15 of 26: 579 rows
    S0 = lambda edit, trans=TRANS: (pf(PF, edit), PF, full(PF), trans)
    GONE = "# plan 1164: this intake.toml is deleted by the plant's first step\n"
    ON_SENTINEL = {   # (1160 P5) a CHOICE_PLANTS PASS control the sentinel banks carry past S1 to a later refusal, and why
        "origin EXPERIMENT with two lanes that differ (ALTERNATIVE: C to T_star by ARGMAX_FAST, chained)": "SECOND_LANE_INFEASIBLE"}   # C ascends with T: every maximum at the fast end
    PLANTS = [
        ("PASS", "the PER_FILE sentinel bank, sealed", (pf(PF), PF, full(PF))),
        ("PASS", "the LONG_TABLE sentinel bank, sealed", (lt(LT), LT, full(LT))),
        # S0 FORMAT
        ("DECLARATION_FILE_ABSENT", "(1164) the declaration's intake.toml deleted before lint and run (the directory stays)",
         (lambda ident: GONE, PF, (lambda b: [f.unlink() for f in (w / "declarations").glob("*/intake.toml") if f.read_text() == GONE], ("lint",), ("run",)))),
        ("TOML_INVALID", "not TOML", S0(lambda t: t + "\n[[[")),
        ("SCHEMA_UNSUPPORTED", "schema = 4, the format before 1160 A35 (1160 A35: was schema = 3, the format before A17; 1160 A17: was schema = 4 over a schema-3 format)", S0(lambda t: t.replace("schema = 5", "schema = 4", 1))),
        ("COMMENT_PREFIX_EMPTY", "(1160) comment = [\"\"] on table-curve-v1", (lt(LT, lambda t: t.replace('comment = ["#"]', 'comment = [""]', 1)), LT, full(LT))),
        ("ROOT_NOT_UNDER_CC_BANKS", "(1160) a CONVERTED source whose root is the deposit's", S0(lambda t: convert(t, f"<leak>/{PF}"))),
        # S1 CHOICES
        ("SELECTION_EMPTY", "(1160 P2, A1) files = [] and values = [] (unsealed: S4 would read files[0])",
         (pf(PF, lambda t: re.sub(r"values = \[[^\]]*\]", "values = []", re.sub(r"files = \[[^\]]*\]", "files = []", t, count=1), count=1)), PF, unsealed)),
        ("SLOW_VALUES_NOT_ONE_PER_FILE", "(1160) one LISTED value fewer than the files", S0(lambda t: re.sub(r'values = \["[^"]*", ', 'values = [', t, count=1))),
        ("FIELD_MISSING", "[knobs.fast] deleted", S0(lambda t: re.sub(r"(?s)\[knobs\.fast\].*?(?=\[measured\])", "", t))),
        ("FIELD_MISSING", "(1160 A4) a block interval without min_blocks", S0(BLOCK_NO_FLOOR)),
        ("FIELD_UNKNOWN", "a field the format does not define", S0(lambda t: t.replace("[intake]\n", '[intake]\ncolour = "red"\n'))),
        ("FIELD_TYPE_WRONG", "a column key that is a boolean", S0(lambda t: t.replace('key = "C"', "key = true", 1))),
        ("VALUE_NOT_LISTED", "layout BY_ROW", S0(lambda t: t.replace('layout = "PER_FILE"', 'layout = "BY_ROW"'))),
        ("VALUE_STILL_TODO", "intake.mode TODO (1160 P4: the plant's mode is RETROSPECTIVE_PREDECLARED)", S0(lambda t: t.replace('mode = "RETROSPECTIVE_PREDECLARED"', 'mode = "TODO"', 1))),
        ("BIAS_KEY_UNDECLARED", "a free-text bias", S0(lambda t: t.replace('bias = "MAX_MEASURED"', 'bias = "the largest C"'))),
        ("FIELD_IS_STAMPED", "a typed timestamp", S0(lambda t: t.replace("[intake]\n", '[intake]\nsealed_at = "2026-10-18T09:00:00Z"\n'))),
        ("FIELD_IS_DERIVED", "a derived field typed", S0(lambda t: t.replace("[acquisition]\n", "[acquisition]\ncorrelated = true\n"))),
        ("STEP_IS_INTERPOLATION", "an interpolation bridge", S0(lambda t: t.replace('template = "CHAIN_SLOW"', 'template = "INTERPOLATE"'))),
        ("BRIDGE_NONE_FITS", "no bridge fits", S0(lambda t: t.replace('template = "CHAIN_SLOW"', 'template = "NONE_FITS"'))),
        ("BASIS_NOT_METADATA", "a figure in the basis", S0(lambda t: re.sub(r'class = "[A-Z_]+"', 'class = "FIGURE"', t, count=1))),
        ("TRANSDUCER_FILE_REFUSED", "a transducer.toml with no [reduction]", S0(lambda t: t, re.sub(r"(?s)\[reduction\].*?(?=\[interval\])", "", TRANS))),
        *[(ON_SENTINEL.get(what, code), f"(1160 P4) {what}", S0(edit)) for code, what, edit in CHOICE_PLANTS],   # every live S1 row (and its PASS controls), linted, sealed, run
        ("BLOCK_RULE_HAS_NO_DIRECTION", "(1160 P2) block FAST_RESTART, rows in acquisition order, direction UNORDERED", (lt(LT, asc, block='"FAST_RESTART"'), LT, full(LT))),
        # S2 SEAL
        ("ALREADY_SEALED", "a second seal", (pf(PF), PF, (SEAL, SEAL))),
        ("UNIVERSE_ROOT_ABSENT", "a root that names no directory (1160 A20: was a --universe that is none)", (pf("nowhere"), PF, (SEAL,))),
        ("SELECTION_OUTSIDE_UNIVERSE", "an empty universe", (pf("empty"), PF, (lambda b: (banks / "empty").mkdir(), SEAL))),
        ("MODE_CONTRADICTS_SOURCE", "(1160 P4) mode PROSPECTIVE, sealed over the bank that holds the selected files", S0(lambda t: t.replace('mode = "RETROSPECTIVE_PREDECLARED"', 'mode = "PROSPECTIVE"', 1))),
        ("SELECTION_DUPLICATE", "(1160) a file named twice in files", (pf(PF, lambda t: t.replace("files = [", 'files = ["curve_002.csv", ', 1).replace("values = [", f'values = ["{slow(2)}", ', 1)), PF, full(PF))),
        ("UNIVERSE_NOT_PARTITIONED", "(1160) a universe file in no part", (pf(UP := pf_bank(lambda b: (b / "notes.txt").write_text("planted\n"))), UP, full(UP))),
        # S3 SOURCE_INTEGRITY
        ("ROOT_UNRESOLVED", "a root name ROOTS.toml does not hold (1160 A20: unsealed, was full: the seal now refuses it first, UNIVERSE_ROOT_ABSENT)", (pf(PF, lambda t: t.replace("<leak>/", "<no-such-root>/")), PF, unsealed)),
        ("PATH_OUTSIDE_ROOT", "(1160) a files entry naming a file of another bank (unsealed)", (pf(PO := pf_bank(), lambda t: t.replace('files = ["curve_000.csv"', f'files = ["../{PF}/curve_000.csv"', 1)), PO, unsealed)),
        ("PATH_ON_TRUTH_SIDE", "(1160) truth_side names a selected file (unsealed)", (pf(PF, lambda t: t.replace('truth_side = ["truth.json"]', 'truth_side = ["truth.json", "curve_003.csv"]', 1)), PF, unsealed)),
        ("PATH_NOT_A_FILE", "a selected file deleted (unsealed: the seal would refuse it; 1160: was PATH_NOT_ADMITTED)", (pf(pf_bank(lambda b: (b / "curve_003.csv").unlink())), PF, unsealed)),
        ("PIN_MISMATCH", "a file's bytes changed after its first logged read (unsealed: the seal would see the size)",
         (pf(PIN := pf_bank()), PIN, unsealed + (append("curve_002.csv", f"{cell(2, 50, 1)},{cell(2, 50, 2)},{cell(2, 50, 3)}\n"), ("run",)))),
        ("UNIVERSE_CHANGED", "a file added after the seal", (pf(UC := pf_bank()), UC, full(UC)[:2] + (lambda b: (b / "late.csv").write_text("T,C,sigma\n"), ("run",)))),
        ("CONVERSION_CHAIN_BROKEN", "(1160 P3) a converted sentinel bank whose CONVERSION-MANIFEST.json was deleted (was CONVERSION_NOT_LIVE)",
         (*cv(conv_bank(curve_files, as_is, lambda raw, bank: (bank / "CONVERSION-MANIFEST.json").unlink())), unsealed)),
        ("CONVERSION_CHAIN_BROKEN", "(1160 P3) one byte of a raw sentinel file changed after the conversion",
         (*cv(conv_bank(curve_files, as_is, lambda raw, bank: (raw / "curve_001.csv").write_bytes((raw / "curve_001.csv").read_bytes().replace(b"T", b"t", 1)))), unsealed)),
        ("PASS", "(1160 P3) the converted PER_FILE sentinel bank, sealed", (*cv(CV := conv_bank(curve_files, as_is)), (("lint",), SEAL, ("run",)))),
        ("PASS", "(1160 A11) the converted PER_FILE sentinel bank, a sentinel row with C = n/a in each file dropped by DROP_ROWS_NOT_NUMERIC, sealed",
         (*cv(DNN := conv_bank(NN, [(f, f, '{op = "DROP_ROWS_NOT_NUMERIC", columns = ["C"]}') for f in NN])), (("lint",), SEAL, ("run",)), TRANS, DNN)),
        # S6 ADMISSIBILITY (1160 P4): linted, sealed, then run with the edit between S5 and S6
        ("READ_NOT_LOGGED", "(1160 P4) the loader lines of curve_002.csv deleted from the access log", (pf(PF), PF, full(PF)[:2] + (AtS6(lambda b, d: unlog(d, "curve_002.csv")),))),
        ("BYPASS_READ_LOGGED", "(1160 P4) curve_001.csv opened directly in the test process (open(), not the loader)", (pf(PF), PF, full(PF)[:2] + (AtS6(lambda b, d: (b / "curve_001.csv").read_bytes()),))),
        # S4 SHAPE
        ("READER_NOT_LIVE", "reader P1", (pf(PF, lambda t: t.replace('name = "csv-curve-v1"', 'name = "P1"')), PF, full(PF))),
        ("COLUMNS_DIFFER", "csv-curve-v1, the first file's names line holds a NUMERIC name",
         (pf(CD := pf_bank(lambda b: (b / "curve_000.csv").write_text((b / "curve_000.csv").read_text().replace("T,C,sigma", f"T,{cell(0, 0, 2)},sigma", 1)))), CD, full(CD))),
        ("UNIT_DIFFERS", "a NAMES_UNITS header stating T in K", (lt(UD := lt_bank(head="T,C,sigma,h\nK,dimensionless,dimensionless,dimensionless\n"), header=nu), UD, full(UD))),
        ("UNIT_DIFFERS", "(1160 P2) a NAMES_UNITS header whose unit of T holds a sentinel number ('K -7357.15'): the stated unit prints masked",
         (lt(US := lt_bank(head=f"T,C,sigma,h\nK {slow(0)},dimensionless,dimensionless,dimensionless\n"), header=nu), US, full(US))),
        ("PASS", "(1160 P2) NAMES_UNITS_IN_NAMES PAREN, every names cell 'name (dimensionless)', sealed",
         (lt(IP := lt_bank(head="T (dimensionless),C (dimensionless),sigma (dimensionless),h (dimensionless)\n"), header=inn("PAREN")), IP, full(IP))),
        ("UNIT_DIFFERS", "(1160 P2) NAMES_UNITS_IN_NAMES SLASH, T's names cell 'T/K -7357.25' (a sentinel in the unit): the unit prints masked",
         (lt(IS := lt_bank(head=f"T/K {slow(1)},C/dimensionless,sigma/dimensionless,h/dimensionless\n"), header=inn("SLASH")), IS, full(IS))),
        ("ROW_ORDER_DIFFERS", "one swapped pair inside block 5",
         (lt(RO := lt_bank([(h, rs[:3] + [rs[4], rs[3]] + rs[5:]) if i == 4 else (h, rs) for i, (h, rs) in enumerate(CURVES)])), RO, full(RO))),
        # S5 CENSUS
        ("FILE_DIFFERS_FROM_FIRST", "a later file's header T,C,err",
         (pf(FD := pf_bank(lambda b: (b / "curve_004.csv").write_text((b / "curve_004.csv").read_text().replace("T,C,sigma", "T,C,err", 1)))), FD, full(FD))),
        ("CURVE_REPEATED", "a slow value in two non-adjacent blocks", (lt(CR := lt_bank(CURVES + CURVES[:1])), CR, full(CR))),
        ("FAST_VALUE_REPEATED", "two adjacent runs of one slow value", (lt(FV := lt_bank(CURVES[:1] + CURVES), asc), FV, full(FV))),
        ("PASS", "(1160 P2) SAME_FAST_VALUE: block 3 holds each even point's row three times in a row, sealed",
         (lt(SF := lt_bank([(h, [x for j, r in enumerate(rs) for x in [r] * (1 + 2 * (i == 2 and j % 2 == 0))]) for i, (h, rs) in enumerate(CURVES)]),
             lambda t: t.replace('identity = "NONE"', 'identity = "SAME_FAST_VALUE"')), SF, full(SF))),
        ("FAST_VALUE_REPEATED", "(1160 P2) the same bank under identity NONE (row_order ASCENDING)", (lt(SF), SF, full(SF))),
        ("CURVE_REPEATED", "(1160 P2) block EXACT: two sweeps whose slow column drifts (b, c, d; e, b, c) repeat b and c non-adjacently", (lt(DR := lt_bank(SWEEPS)), DR, full(DR))),
        ("TOO_FEW_CURVES", "(1160 P2) the same file under block FAST_RESTART: two curves, sealed (1160 P5: was PASS; S8 needs three)", (lt(DR, block='"FAST_RESTART"'), DR, full(DR))),
        ("PASS", "(1160 P2) block FAST_RESTART on a drift bank: 22 sweeps, 579 distinct slow values, sealed", (lt(D22 := lt_bank(raw=drift22), block='"FAST_RESTART"'), D22, full(D22))),
        ("SLOW_KEY_UNRESOLVED", "(1160) FILE_KEY h, each key line's value a sentinel followed by 'x'",
         (pf(SK := pf_bank(keyed(lambda i: f"h,{slow(i)}x\n")), lambda t: slow_source(t, "FILE_KEY")), SK, full(SK))),
        ("PASS", "(1160) FILE_KEY h on the PER_FILE sentinel bank, sealed", (pf(FK := pf_bank(keyed(lambda i: f"h,{slow(i)}\n")), lambda t: slow_source(t, "FILE_KEY")), FK, full(FK))),
        ("SLOW_NONE_HAS_NO_PATH", "(1160) slow source NONE on the PER_FILE sentinel bank, sealed (1160 A24: was TOO_FEW_CURVES at S8; 1160 P5: was PASS)", (pf(PF, lambda t: slow_source(t, "NONE")), PF, full(PF))),
        ("REPLICATE_KEY_UNRESOLVED", "a FILE identity on a LONG_TABLE", (lt(RK := lt_bank(CURVES + CURVES[:1]), lambda t: t.replace('identity = "NONE"', 'identity = "FILE"')), RK, full(RK))),
        ("ACQUISITION_ORDER_DIFFERS", "ascending rows in acquisition order, declared DESCENDING",
         (lt(AO := lt_bank(), lambda t: asc(t).replace('direction = "UNORDERED"', 'direction = "DESCENDING"')), AO, full(AO))),
        # S7 INTERVAL_FEASIBILITY, S8 RESOLUTION_AND_IDENTIFIABILITY, S9 ALTERNATIVE_INTAKE (plan 1160 P5), sealed and run
        ("ONE_READING_PER_POINT", "(1160 P5) block, b 1, min_blocks 2, on the PER_FILE sentinel bank (one reading per point)", S0(BLOCK(2))),
        ("BELOW_METHOD_FLOOR", "(1160 P5) the SAME_FAST_VALUE bank (three readings at block 3's even points), block, b 1, min_blocks 30",
         (lt(SF, lambda t: BLOCK(30)(SAME_FAST(t))), SF, full(SF))),
        ("METHOD_HAS_NO_FLOOR", "(1160 P5) the SAME_FAST_VALUE bank, iid", (lt(SF, lambda t: IID(SAME_FAST(t))), SF, full(SF))),
        ("TOO_FEW_POINTS_IN_CURVE", "(1160 P5) block 4 cut to its first two rows", (lt(TP := lt_bank([(h, rs[:2] if i == 3 else rs) for i, (h, rs) in enumerate(CURVES)])), TP, full(TP))),
        ("NO_COVERAGE_EVIDENCE", "(1160 P5) [bracket] required VALIDATED_BRACKET", S0(VALIDATED)),
        ("SECOND_LANE_INFEASIBLE", "(1160 P5) PAIR_NEAREST_FAST on C: each curve's T span is disjoint from its neighbours'", S0(PAIR_LANE)),
        # S10 KERNEL_HANDOFF (plan 1160 P6), sealed and run
        ("NO_KERNEL_ROUTE", "(1160 P6) the PRIMARY bridge PAIR_NEAREST_FAST on raw C", S0(PRIMARY_PAIR)),
        ("NO_KERNEL_ROUTE", "(1160 P6) no PRIMARY bridge (the projection and the bridge both ALTERNATIVE)", S0(ALL_ALTERNATIVE)),
        ("DOOR_REFUSED", "(1160 P6) [shift] c = nan", S0(SHIFT("nan"))),
        # S4 reader reasons (table-curve-v1), each the detail of READER_REFUSED
        ("NOT_UTF8", "a byte that is not UTF-8", (lt(B1 := lt_bank(raw=f"T,C,sigma,h\n{cell(0, 0, 1)},{cell(0, 0, 2)}\xff,{cell(0, 0, 3)},{slow(0)}\n".encode("latin-1"))), B1, full(B1))),
        ("HEADER_LINE_ABSENT", "two header lines declared, one present", (lt(B2 := lt_bank(raw=b"T,C,sigma,h\n"), header=nu), B2, full(B2))),
        ("NO_DATA_ROW", "a header and no data row", (lt(B3 := lt_bank(raw=b"# nothing yet\nT,C,sigma,h\n")), B3, full(B3))),
        ("ROW_WIDTH_DIFFERS", "a short row", (lt(B4 := lt_bank(raw=f"T,C,sigma,h\n{cell(0, 0, 1)},{cell(0, 0, 2)},{cell(0, 0, 3)},{slow(0)}\n{cell(0, 1, 1)},{cell(0, 1, 2)},{cell(0, 1, 3)}\n".encode())), B4, full(B4))),
        ("COLUMN_NAME_ABSENT", "a names line whose names are values (a WIDE table: F3)", (lt(B5 := lt_bank(raw=numeric_names)), B5, full(B5))),
        ("COLUMN_NAME_AMBIGUOUS", "two columns named h", (lt(B6 := lt_bank(raw=f"T,C,sigma,h,h\n{cell(0, 0, 1)},{cell(0, 0, 2)},{cell(0, 0, 3)},{slow(0)},{slow(0)}\n".encode())), B6, full(B6))),
        ("COLUMN_POSITION_OUT_OF_RANGE", "the slow column at position 9", (lt(LT, slow="9"), LT, full(LT))),
        ("CELL_NOT_A_NUMBER", "a cell 'n/a'", (lt(B7 := lt_bank(raw=f"T,C,sigma,h\n{cell(0, 0, 1)},n/a,{cell(0, 0, 3)},{slow(0)}\n".encode())), B7, full(B7))),
    ]
    XL = lt_bank(raw=xlsx([["T", "C", "sigma", "h"]] + rows, "data"))
    PLANTS += {False: [("XLSX_READER_ABSENT", "an xlsx sentinel bank without openpyxl", (lt(XL, xl), XL, full(XL)))],
               True: [("NOT_AN_XLSX", "bytes that are no workbook", (lt(B8 := lt_bank(raw=b"T,C,sigma,h\n"), xl), B8, full(B8))),
                      ("SHEET_ABSENT", "sheet 'data' declared, the workbook holds 'Sheet1'", (lt(B9 := lt_bank(raw=xlsx([["T", "C", "sigma", "h"]] + rows, "Sheet1")), xl), B9, full(B9))),
                      ("PASS", "the xlsx sentinel bank", (lt(XL, xl), XL, full(XL)))]}[HAS_XLSX]
    NOT_HERE = {False: ["NOT_AN_XLSX", "SHEET_ABSENT"], True: ["XLSX_READER_ABSENT"]}[HAS_XLSX]

    # ---- K1. the sentinel alphabet: every numeric cell of every bank and every declared slow value
    cells = {m.decode() for q in banks.rglob("*") if q.is_file() for m in SENT.findall(q.read_bytes())} | {slow(k) for k in range(K)}
    numeric = [q for q in banks.rglob("*.csv") for ln in q.read_text(errors="replace").splitlines()[1:] for c in ln.split(",") if re.fullmatch(r"[-+.\d]+", c) and not c.startswith("-7357.")]
    check("K1. every numeric cell of every csv bank is a sentinel", not numeric and len(cells) > 100, f"{len(numeric)} non-sentinel numeric cells, first {numeric[:3]}; {len(cells)} sentinels")
    every = {f for c in cells for f in forms(c)}
    check("K1. every printed form of every sentinel holds -7357 (so no form is a short common string)", all("-7357" in f for f in every), str([f for f in every if "-7357" not in f][:5]))

    # ---- K2, K3. every live row planted, and nothing printed or written holds a sentinel
    hit = lambda text: sorted({f for f in every if f in text})
    check("K3. the scan sees a sentinel when one is printed (a check that cannot see must not convict)", hit(f"T span [{float(cell(0, 0, 1)):g}, 1]") != [])
    live = {r["code"] for s in intake.tables(ROOT)["stages"]["stage"] for k in ("reason", "reader_reason") for r in blind.look(s, k, []) if r["live"]}
    reached, said = set(), {}
    for code, what, (text, bank, steps, *trans) in PLANTS:
        got, out, ident = plant(text, bank, steps, *trans)
        reached |= {got}
        said[code + " " + what] = out
        check(f"K2. {code}: {what}", got == code, got)
        check(f"K3. {code}: no sentinel in its stdout, stderr, intake-report.md, SEAL.json, seal.log or access.log", not hit(out), f"{hit(out)[:5]} in {ident}")
    reached |= {True: {"READER_REFUSED"}, False: set()}[any("REFUSE READER_REFUSED" in o for o in said.values())]   # the reader-reason plants arrived through S4
    print(f"  openpyxl {'installed' if HAS_XLSX else 'NOT installed'} on this machine; NOT REACHED HERE: {NOT_HERE}")
    check("K2. the codes the plants reach are exactly the live rows (with the machine's NOT REACHED rows)", (reached - {"PASS"}) | set(NOT_HERE) == live,
          f"live, never reached: {sorted(live - reached - set(NOT_HERE))}; reached, not live: {sorted(reached - live - {'PASS'})}")

    # ---- K7. (1160 P6) RESULT.json: written on the PASS runs, its numbers only in the declared fields, the slow values there the only data values
    check("K7. RESULT.json was written on the two sentinel PASS runs (S10 passed)", len(RESULTS) >= 2, str(sorted(RESULTS)))
    check("K7. every number of every RESULT.json is in a declared numeric field", not MISPLACED and all(numbers(json.loads(r)) for r in RESULTS.values()), str(MISPLACED[:5]))
    check("K7. the exemption is needed and no wider: each RESULT.json's raw text holds a sentinel, and only inside span_slow or end_slow",
          all(hit(r) and not hit(json.dumps({k: v for k, v in json.loads(r).items() if k != "results"})) for r in RESULTS.values())
          and all({f for f in every if f in json.dumps(x)} <= {f for f in every if f in json.dumps([x.get(k) for k in SLOW_FIELDS])} for r in RESULTS.values() for x in json.loads(r)["results"]),
          str([hit(r)[:3] for r in RESULTS.values()])[:300])

    # ---- K6. (1160 P3) convert, its manifest and peek print and write no sentinel
    wide = (f"h,{cell(0, 0, 1)},{cell(0, 1, 1)},{cell(0, 2, 1)}\n" + "".join(f"{slow(k)},{cell(k, 0, 2)},{cell(k, 1, 2)},{cell(k, 2, 2)}\n" for k in range(K))).encode()
    WD = conv_bank({"wide.csv": wide}, [("wide.csv", "long.csv", '{op = "WIDE_TO_LONG", key = "h", fast = "T", measured = "C"}')])
    raw = lambda ident, f: f"<cc-datasets>/{ident}/raw/{f}"   # (1160 A19) peek names its file by the root-named path (was the bare name)
    peeked = "".join(cli("peek", WD, raw(WD, "wide.csv"), "--depth", str(k)) for k in (0, 1, 5)) + cli("peek", CV, raw(CV, "curve_000.csv"), "--depth", "3")
    check("K6. (1160 A19) peek reads the files it is given (no SOURCE_FILE_ABSENT), so the scan below is not vacuous", "SOURCE_FILE_ABSENT" not in peeked and "line 1:" in peeked, peeked[:300])
    # (1160 A10) an xlsx peeked with no --sheet: SHEET_REQUIRED, its sheets named by a sentinel numeric name and a text name holding one
    XB = conv_bank({"book.xlsx": workbook({cell(0, 0, 1): [[cell(0, 1, 2)]], f"run {cell(1, 0, 1)}": [["T"], [float(cell(1, 1, 2))]]})},
                   [("book.xlsx", "x.csv", '{op = "SHEET_TO_CSV", sheet = "data"}')])
    xpeek = cli("peek", XB, raw(XB, "book.xlsx"))
    check("K6. (1160 A10) peek on the sentinel xlsx with no --sheet refuses SHEET_REQUIRED", "SHEET_REQUIRED" in xpeek, xpeek[:400])
    peeked += xpeek
    peeked += (w / "declarations" / WD / "peek.log").read_text() + (w / "declarations" / CV / "peek.log").read_text() + (w / "declarations" / XB / "peek.log").read_text()
    check("K6. the WIDE sentinel file converts (WIDE_TO_LONG) and verifies", CONVERTED[WD].count("PASS.") == 2, CONVERTED[WD][:400])
    check("K6. peek on the WIDE sentinel file prints '1 text name + 3 numeric names' and stops before the first line of numbers",
          "1 text name + 3 numeric names: 'h'" in peeked and "stopped: a line of numbers (not printed)" in peeked, peeked[:400])
    for name, out in CONVERTED.items():
        check(f"K6. {name}: no sentinel in convert's stdout, CONVERSION-MANIFEST.json or conversion-access.log", not hit(out), str(hit(out)[:5]))
    check("K6. no sentinel in peek's stdout or peek.log", not hit(peeked), str(hit(peeked)[:5]))

    # ---- K4. the census section: curves by ordinal and file name
    for key, want in (("PASS the PER_FILE sentinel bank, sealed", [f"{i + 1}. curve_{i:03d}.csv: {6 + i} points" for i in range(K)]),
                      ("PASS the LONG_TABLE sentinel bank, sealed", [f"{i + 1}. bank.csv block {i + 1}: {6 + i} points" for i in range(K)])):
        sec = said[key].split("## Census\n", 1)[-1].split("\n## ", 1)[0]
        check(f"K4. {key.split(' ', 1)[1]}: the census section lists each curve by ordinal and file name", "## Census\n" in said[key] and all(x in sec.splitlines() for x in want), sec[:400])

    # ---- K4. (1160 A11) the census of the bank DROP_ROWS_NOT_NUMERIC converted prints the dropped count per converted file, no value
    out = said["PASS (1160 A11) the converted PER_FILE sentinel bank, a sentinel row with C = n/a in each file dropped by DROP_ROWS_NOT_NUMERIC, sealed"]
    sec = out.split("## Census\n", 1)[-1].split("\n## ", 1)[0]
    check("K4. (1160 A11) the census section prints, per converted file, the rows DROP_ROWS_NOT_NUMERIC dropped (1 each)",
          all(f"- converted curve_{i:03d}.csv -> curve_{i:03d}.csv: rows dropped as not numeric (DROP_ROWS_NOT_NUMERIC): 1" in sec.splitlines() for i in range(K)), sec[:600])
    check("K4. (1160 A11) the dropped sentinel rows reach no output: the bank files are the deposit's", all((tmp / "cc-banks" / DNN / "bank" / f).read_bytes() == b for f, b in curve_files.items()))
    note = [ln for ln in out.splitlines() if ln.startswith("- **Ordering**")]
    check(f"K4. (1160 A13) the converted bank sealed after its conversion: the ordering note counts the raw files the conversion read before the seal ({K}), "
          "and names none", note != [] and all(f" CONVERSION_READ_BEFORE_SEAL ({K} files). " in x and not any(f in x for f in curve_files) for x in note), str(note))

    # ---- K5. (1160 P2) the drift bank's census: 22 curves, its drift reported as a count
    out = said["PASS (1160 P2) block FAST_RESTART on a drift bank: 22 sweeps, 579 distinct slow values, sealed"]
    check("K5. the drift bank is 579 rows of 579 distinct slow sentinels", drift22.count(b"\n") == 580 and len({ln.split(b",")[3] for ln in drift22.splitlines()[1:]}) == 579)
    check("K5. FAST_RESTART forms 22 curves on the drift bank and reports distinct_slow_in_block max = 27 (a count)",
          "Sampling: 22 curves;" in out and "distinct_slow_in_block max = 27" in out, out[:600])

print("test_intake_leak: " + ("FAILED " + "; ".join(bad) if bad else "all passed"))
sys.exit(1 if bad else 0)
