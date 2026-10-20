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
 E4. explain (docs/INTAKE.md) and every report carry the rows that are not live.
Seen RED (1160 P3): intake_convert.s3 returning then() without the chain check: both CONVERSION_CHAIN_BROKEN plants FAIL (PASS) and E2's
totality FAILS (CONVERSION_CHAIN_BROKEN live, never reached).
Seen RED (1160 P4): each S1 row's holds made `lambda: True` in cc/intake_choices.py (KNOBS_SAME_QUANTITY, MEASURED_IS_A_KNOB,
PROJECTION_REQUIRED, PROJECTION_ESTIMAND_MIXED, SECOND_LANE_MISSING, LANES_IDENTICAL, REPLICATE_IS_SWEEP_NEIGHBOUR, OPERATION_NOT_PERMITTED,
PROVENANCE_HAS_NO_KERNEL_ROUTE, METHOD_NEEDS_UNCERTAINTY_COLUMN), one at a time: that row's plant(s) FAIL (PASS, or a later stage's code)
and E2's totality FAILS (the row live, never reached); intake_seal.SEEN["PROSPECTIVE"] made True: the MODE_CONTRADICTS_SOURCE plant FAILS
(PASS) and E2's totality FAILS; S6's READ_NOT_LOGGED or BYPASS_READ_LOGGED holds made True: that plant FAILS (PASS: the deleted loader
lines, the direct open()) and E2's totality FAILS; a CONVERTED source's bank read through a second loader (P3's two loaders): the converted
PASS plant FAILS (BYPASS_READ_LOGGED: the chain loader's audit hook logged the bank loader's reads).
Seen RED (1160 P5, cc/intake_feasible.py, one at a time): REPLICATED["block"] False: the ONE_READING_PER_POINT plant FAILS; FLOOR["block"]
made []: the BELOW_METHOD_FLOOR plant and the FLOOR block check FAIL; k_gamma replaced by 1: the FLOOR gamma check FAILS; chains 0..n (one
too many): the FLOOR chains check FAILS; HAS_FLOOR["iid"] True: the METHOD_HAS_NO_FLOOR plant FAILS; TIERING["STATED"] REPLICATES: the
evidence check FAILS; with_slow >= 2: the two-curve TOO_FEW_CURVES plant FAILS; n < 2: the TOO_FEW_POINTS_IN_CURVE plant and totality
FAIL; COVERED["VALIDATED_BRACKET"] True: the NO_COVERAGE_EVIDENCE plant and totality FAIL; ENDS["ARGMAX_FAST"] or PAIRS["PAIR_NEAREST_FAST"]
made empty: that SECOND_LANE_INFEASIBLE plant FAILS (PASS). (1160 A39: ENDS is DOMAIN, and SECOND_LANE_INFEASIBLE is NO_INTERIOR_FAST_MAXIMUM
and ANCHOR_OUTSIDE_NEIGHBOUR_SPAN; the S10 PROJECTION_EMPTY_ON_CURVE plant is new, seen red in tests/test_intake_loop4.py T39.2.)
Seen RED (1160 A7): intake_names.ORDER_CLASS[(False, True)] made "in neither order (not monotone)": the descending-blocks A7 check FAILS;
intake_names.OPPOSITE["ASCENDING"] made "ASCENDING": the descending-blocks A7 check FAILS."""
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
import intake_fold  # noqa: E402
import intake_say  # noqa: E402
import intake_feasible  # noqa: E402
import readout  # noqa: E402
import intake_read as rd  # noqa: E402
import intake_seal  # noqa: E402
import intake_synth  # noqa: E402
from intake_plant import ALL_ALTERNATIVE, PRIMARY_PAIR, SHIFT, ARGMAX_LANE, BLOCK, BLOCK_NO_FLOOR, IID, PAIR_LANE, SAME_FAST, VALIDATED, CHOICE_PLANTS, converted, key_lines, long_table, outcome, per_file, rooted, run, slow_source, write_long, xlsx  # noqa: E402

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
    """The code of the first refusal of a run, a reader reason for S4 READER_REFUSED (its Detail's first word, plan 1160 P0), else 'PASS'."""
    ref = [e.result for e in out.values() if e.mark is intake.Mark.REFUSED]
    code = {True: lambda: ref[0].reason, False: lambda: "PASS"}[bool(ref)]()
    SEEN.add(code)
    return {True: lambda: ref[0].evidence.words[0], False: lambda: code}[code == "READER_REFUSED"]()


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

    def grow(text, name):
        """(1160 P1) One more entry `name` in files and one more LISTED value, so S1 still passes."""
        return text.replace("files = [", f'files = ["{name}", ', 1).replace("values = [", 'values = ["9.5", ', 1)

    def convert(text, root, frm="<cc-datasets>/pf/raw"):
        """(1160 P1) The declaration with [source] kind CONVERTED, its root `root`, converted_from `frm` (1160 P3: CONVERSION-MANIFEST.json
        excluded where MANIFEST.json was)."""
        return re.sub(r'root = "[^"]*"', f'root = "{root}"', text.replace('kind = "DEPOSIT"', f'kind = "CONVERTED"\nconverted_from = "{frm}"', 1)
                      .replace('file = "MANIFEST.json"', 'file = "CONVERSION-MANIFEST.json"', 1), count=1)

    def conv(edit=lambda raw, bank: None):
        """(1160 P3) The PER_FILE declaration of a bank `bin/cc intake convert` wrote from pf's curve files (each converted as it is), after
        `edit` (on the raw directory and the bank directory): its first code."""
        name = f"cv{next(n)}"
        converted(T, tmp, name, [(f["name"], f["name"], "") for f in m["files"]], {f["name"]: (banks / "pf" / f["name"]).read_bytes() for f in m["files"]})
        edit(tmp / "cc-datasets" / name / "raw", tmp / "cc-banks" / name / "bank")
        return pf("pf", lambda t: convert(t, f"<cc-banks>/{name}/bank", f"<cc-datasets>/{name}/raw"))

    def slow_label(name, source):
        """(1160 P1) The S5 census label of a PER_FILE declaration of bank `name` with slow source `source`."""
        ident = f"d{next(n)}"
        restate = {"LISTED": lambda t: t, "FILE_KEY": lambda t: slow_source(t, "FILE_KEY"), "NONE": lambda t: slow_source(t, "NONE")}[source]
        got = outcome(run(T, tmp, ident, restate(per_file(m, ident).replace("<long-test>/pf", f"<long-test>/{name}"))), "S5")
        return getattr(got[1], "label", got[0])

    def mint(bank, times=1, edit=lambda t: t):
        """(1160 A20: was mint(universe, ...), the directory given beside the root) Seal a PER_FILE declaration whose root is <long-test>/<bank>."""
        ident = f"d{next(n)}"
        text = edit(per_file(m, ident).replace("<long-test>/pf", f"<long-test>/{bank}"))
        d = tmp / "declarations" / ident
        d.mkdir(parents=True)
        (d / "intake.toml").write_text(text)
        (d / "transducer.toml").write_text("# planted: the seal hashes this file; S0's transducer check is not run here\n")
        decl = blind.format_stage(text, [], T).evidence
        who = {"author": "plan 1145 test", "author_kind": intake_seal.AUTHOR_KIND["ai-draft"], "confirmed_by": ""}
        got = [intake_seal.mint(decl, d, who, ROOT, rooted(T, tmp)) for _ in range(times)][-1]
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
        intake_seal.mint(blind.format_stage(text, [], T).evidence, d, who, ROOT, rooted(T, tmp))
        between(banks / name)
        return first(run(T, tmp, ident, text))

    def at_s6(edit):
        """(1160 P4) A PER_FILE declaration of pf folded over the stage table with `edit` (on the declaration directory and the bank directory)
        applied between S5 and S6: S6's body then reads the access log as edited. One loader per run, as bin/cc intake run has."""
        ident = f"d{next(n)}"
        d, text = tmp / "declarations" / ident, per_file(m, ident)
        d.mkdir(parents=True)
        (d / "intake.toml").write_text(text)
        b = intake.bodies(rooted(T, tmp), d, text, [])
        return first(intake_fold.fold(T["stages"]["stage"], {**b, "S6": lambda census: (edit(d, banks / "pf"), b["S6"](census))[1]}))

    def unlog(d, name):
        """(1160 P4) The access log without the loader lines of file `name`."""
        (d / "access.log").write_text("".join(ln + "\n" for ln in (d / "access.log").read_text().splitlines() if not json.loads(ln)["path"].endswith("/" + name)))

    base = per_file(m, "s0")
    s0 = lambda text, findings=(): {True: lambda g: g.reason, False: lambda g: "PASS"}[isinstance(blind.format_stage(text, list(findings), T), blind.Refuse)](blind.format_stage(text, list(findings), T))
    nu = 'kind = "NAMES_UNITS"\nrows = 2\nnames = 1\nunits = 2'
    xl = lambda sheet: lambda t: t.replace('[reader.format]\nkind = "COMMA"', f'[reader.format]\nkind = "XLSX"\nsheet = "{sheet}"')
    rows = [[float(x) for x in r.split(",")] + [h] for h, rs in curves for r in rs]
    asc = lambda t: t.replace('row_order = "ASCENDING"', 'row_order = "ACQUISITION"')
    tripled = [(h, [r for r in rs for _ in range(3)]) for h, rs in curves]   # 1160 P5
    top = max(range(len(curves[2][1])), key=lambda i: float(curves[2][1][i].split(",")[1]))
    top4 = max(range(len(curves[4][1])), key=lambda i: float(curves[4][1][i].split(",")[1]))   # 1160 P6: block 5's maximum row
    cut = [(h, rs[:top + 1] if i == 2 else rs) for i, (h, rs) in enumerate(curves)]   # 1160 P5: block 3 ends at its maximum
    moved = [(h, [",".join([str(float(r.split(",")[0]) + 1000)] + r.split(",")[1:]) for r in rs] if i == 4 else rs) for i, (h, rs) in enumerate(curves)]   # 1160 P5
    PLANTS = [
        # S0 FORMAT, on the declaration text
        ("DECLARATION_FILE_ABSENT", "(1164) a declaration directory with no intake.toml (what S0 receives: intake.declared)", lambda: s0(intake.declared(tmp / "nowhere"))),
        ("TOML_INVALID", "not TOML", lambda: s0(base + "\n[[[")),
        ("SCHEMA_UNSUPPORTED", "schema = 4, the format before 1160 A35 (1160 A35: was schema = 3, the format before A17; 1160 A17: was schema = 4 over a schema-3 format)", lambda: s0(base.replace("schema = 5", "schema = 4", 1))),
        ("COMMENT_PREFIX_EMPTY", "(1160) comment = [\"\"] on table-curve-v1", lambda: s0(long_table(m, "s0").replace('comment = ["#"]', 'comment = [""]', 1))),
        ("ROOT_NOT_UNDER_CC_BANKS", "(1160) a CONVERTED source whose root is the deposit's", lambda: s0(convert(base, "<long-test>/pf"))),
        ("ROOT_NOT_UNDER_CC_BLIND", "(1160 A41) a BLINDED source whose root is the deposit's",
         lambda: s0(re.sub(r'root = "[^"]*"', 'root = "<long-test>/pf"\nblinded_from = "<long-test>/pf"\nkey_sha256 = "0"', base.replace('kind = "DEPOSIT"', 'kind = "BLINDED"', 1), count=1))),
        ("FIELD_MISSING", "[knobs.fast] deleted", lambda: s0(re.sub(r"(?s)\[knobs\.fast\].*?(?=\[measured\])", "", base))),
        ("FIELD_MISSING", "(1160 A4) a block interval without min_blocks (FORMAT [interval_fields.block] requires it)", lambda: s0(BLOCK_NO_FLOOR(base))),
        ("FIELD_UNKNOWN", "a field the format does not define", lambda: s0(base.replace("[intake]\n", "[intake]\ncolour = \"red\"\n"))),
        ("FIELD_TYPE_WRONG", "a column key that is a boolean", lambda: s0(base.replace('key = "C"', "key = true", 1))),
        ("VALUE_NOT_LISTED", "layout BY_ROW", lambda: s0(base.replace('layout = "PER_FILE"', 'layout = "BY_ROW"'))),
        ("VALUE_STILL_TODO", "intake.mode TODO (1160 P4: the plant's mode is RETROSPECTIVE_PREDECLARED)", lambda: s0(base.replace('mode = "RETROSPECTIVE_PREDECLARED"', 'mode = "TODO"', 1))),
        ("BIAS_KEY_UNDECLARED", "a free-text bias", lambda: s0(base.replace('bias = "MAX_MEASURED"', 'bias = "the largest C"'))),
        ("FIELD_IS_STAMPED", "a typed timestamp", lambda: s0(base.replace("[intake]\n", '[intake]\nsealed_at = "2026-10-18T09:00:00Z"\n'))),
        ("FIELD_IS_DERIVED", "a derived field typed", lambda: s0(base.replace("[acquisition]\n", "[acquisition]\ncorrelated = true\n"))),
        ("STEP_IS_INTERPOLATION", "an interpolation bridge", lambda: s0(base.replace('template = "CHAIN_SLOW"', 'template = "INTERPOLATE"'))),
        ("BRIDGE_NONE_FITS", "no bridge fits", lambda: s0(base.replace('template = "CHAIN_SLOW"', 'template = "NONE_FITS"'))),
        ("BASIS_NOT_METADATA", "a figure in the basis", lambda: s0(re.sub(r'class = "[A-Z_]+"', 'class = "FIGURE"', base, count=1))),
        ("TRANSDUCER_FILE_REFUSED", "a planted transducer finding", lambda: s0(base, ["transducer.update[0]: planted"])),
        # S1 CHOICES (plan 1160 P1-P2; P4: every row, the plants of intake_plant.CHOICE_PLANTS, each run through every stage)
        *[(code, f"(1160 P4) {what}", lambda edit=edit: pf("pf", edit)) for code, what, edit in CHOICE_PLANTS],
        ("BLOCK_RULE_HAS_NO_DIRECTION", "(1160 P2) block FAST_RESTART, rows in acquisition order, direction UNORDERED", lambda: lt(bank(), asc, block='"FAST_RESTART"')),
        ("SELECTION_EMPTY", "(1160 P2, A1) files = [] and values = []", lambda: pf("pf", lambda t: re.sub(r"values = \[[^\]]*\]", "values = []", re.sub(r"files = \[[^\]]*\]", "files = []", t, count=1), count=1))),
        ("SLOW_VALUES_NOT_ONE_PER_FILE", "(1160) one LISTED value fewer than the files", lambda: pf("pf", lambda t: re.sub(r'values = \["[^"]*", ', 'values = [', t, count=1))),
        # S2 SEAL (bin/cc intake seal)
        ("ALREADY_SEALED", "a second seal", lambda: mint("pf", 2)),
        ("UNIVERSE_ROOT_ABSENT", "a universe that is no directory", lambda: mint("nowhere")),
        ("SELECTION_OUTSIDE_UNIVERSE", "an empty universe", lambda: mint([p.name for p in [banks / "empty"] if p.mkdir() is None][0])),
        ("SELECTION_OUTSIDE_UNIVERSE", "(1160) a files entry the universe does not hold", lambda: mint("pf", edit=lambda t: grow(t, "curve_999.csv"))),
        ("MODE_CONTRADICTS_SOURCE", "(1160 P4) mode PROSPECTIVE, sealed over a universe that holds the selected files",
         lambda: mint("pf", edit=lambda t: t.replace('mode = "RETROSPECTIVE_PREDECLARED"', 'mode = "PROSPECTIVE"', 1))),
        ("SELECTION_DUPLICATE", "(1160) a file named twice in files", lambda: mint("pf", edit=lambda t: grow(t, m["files"][2]["name"]))),
        ("UNIVERSE_NOT_PARTITIONED", "(1160) a universe file in no part", lambda: mint(copy(lambda b: (b / "notes.txt").write_text("planted\n")))),
        ("UNIVERSE_NOT_PARTITIONED", "(1160) a file both selected and excluded", lambda: mint("pf", edit=lambda t: t.replace('why = "metadata', f'why = "x" }}, {{ file = "{m["files"][1]["name"]}", why = "metadata', 1))),
        ("UNIVERSE_NOT_PARTITIONED", "(1160) an excluded entry with an empty why", lambda: mint("pf", edit=lambda t: re.sub(r'why = "[^"]*"', 'why = ""', t, count=1))),
        ("UNIVERSE_NOT_PARTITIONED", "(1160) an excluded file the universe does not hold", lambda: mint("pf", edit=lambda t: t.replace('file = "MANIFEST.json"', 'file = "MANIFEST.json", why = "x" }, { file = "README.md"', 1))),
        ("PASS", "(1160) the partition holds: files, MANIFEST.json excluded (the truth sits outside the bank)", lambda: mint(copy(lambda b: None))),
        # S3 SOURCE_INTEGRITY
        ("ROOT_UNRESOLVED", "a root name ROOTS.toml does not hold", lambda: pf("pf", lambda t: t.replace("<long-test>/pf", "<no-such-root>/pf"))),
        ("PATH_OUTSIDE_ROOT", "(1160) a files entry ../pf/<a curve file>: a file of another bank, outside this root", lambda: pf(copy(lambda b: None), lambda t: t.replace(f'files = ["{m["files"][0]["name"]}"', f'files = ["../pf/{m["files"][0]["name"]}"', 1))),
        ("PATH_ON_TRUTH_SIDE", "(1160) truth_side names a selected file (unsealed: the seal would refuse the partition)", lambda: pf("pf", lambda t: t.replace('truth_side = ["truth.json"]', f'truth_side = ["truth.json", "{m["files"][3]["name"]}"]', 1))),
        ("PATH_NOT_A_FILE", "a selected file deleted (1160: was PATH_NOT_ADMITTED)", lambda: pf(copy(lambda b: (b / m["files"][3]["name"]).unlink()))),
        ("PATH_NOT_A_FILE", "(1160) a selected name that is a directory", lambda: pf(copy(lambda b: ((b / m["files"][3]["name"]).unlink(), (b / m["files"][3]["name"]).mkdir())))),
        ("PIN_MISMATCH", "a file's bytes changed after its first logged read", lambda: twice(copy(lambda b: None), lambda d, b, t: (b / m["files"][2]["name"]).write_text((b / m["files"][2]["name"]).read_text() + "3.5,0.5,0.03\n"))),
        ("UNIVERSE_CHANGED", "a file added to the universe after the seal", lambda: sealed_then(lambda b: (b / "late.csv").write_text("T,C,sigma\n"))),
        ("CONVERSION_CHAIN_BROKEN", "(1160 P3) a converted bank whose CONVERSION-MANIFEST.json was deleted (was CONVERSION_NOT_LIVE)", lambda: conv(lambda raw, bank: (bank / "CONVERSION-MANIFEST.json").unlink())),
        ("CONVERSION_CHAIN_BROKEN", "(1160 P3) one byte of a raw file changed after the conversion", lambda: conv(lambda raw, bank: (raw / m["files"][2]["name"]).write_bytes(
            (raw / m["files"][2]["name"]).read_bytes().replace(b"T", b"t", 1)))),
        ("PASS", "(1160 P3) a converted bank passes S3 and reads as a DEPOSIT", lambda: conv()),
        # S6 ADMISSIBILITY (plan 1160 P4), each edit applied between S5 and S6 of one run
        ("PASS", "(1160 P4) the access log as the run wrote it", lambda: at_s6(lambda d, b: None)),
        ("READ_NOT_LOGGED", "(1160 P4) the loader lines of one pinned file deleted from the access log", lambda: at_s6(lambda d, b: unlog(d, m["files"][4]["name"]))),
        ("BYPASS_READ_LOGGED", "(1160 P4) a bank file opened directly in the test process (open(), not the loader)", lambda: at_s6(lambda d, b: (b / m["files"][1]["name"]).read_bytes())),
        # S7 INTERVAL_FEASIBILITY (plan 1160 P5): `tripled` holds every row three times in a row (three readings per point under SAME_FAST_VALUE)
        ("ONE_READING_PER_POINT", "(1160 P5) block, b 1, min_blocks 2, on a bank of one reading per point", lambda: pf("pf", BLOCK(2))),
        ("BELOW_METHOD_FLOOR", "(1160 P5) block, b 1, min_blocks 30, three readings per point", lambda: lt(bank(tripled), lambda t: BLOCK(30)(SAME_FAST(t)))),
        ("PASS", "(1160 P5) block, b 1, min_blocks 3, three readings per point", lambda: lt(bank(tripled), lambda t: BLOCK(3)(SAME_FAST(t)))),
        ("METHOD_HAS_NO_FLOOR", "(1160 P5) iid, three readings per point", lambda: lt(bank(tripled), lambda t: IID(SAME_FAST(t)))),
        ("PASS", "(1160 P5) interval NONE on a bank of one reading per point", lambda: pf("pf", lambda t: t.replace('method = "STATED"', 'method = "NONE"', 1))),
        # S8 RESOLUTION_AND_IDENTIFIABILITY (plan 1160 P5)
        ("TOO_FEW_CURVES", "(1160 P5) a LONG_TABLE of two curves", lambda: lt(bank(curves[:2]))),
        ("TOO_FEW_POINTS_IN_CURVE", "(1160 P5) block 5 cut to its first two rows", lambda: lt(bank([(h, rs[:2] if i == 4 else rs) for i, (h, rs) in enumerate(curves)]))),
        ("NO_COVERAGE_EVIDENCE", "(1160 P5) [bracket] required VALIDATED_BRACKET (no coverage evidence exists)", lambda: pf("pf", VALIDATED)),
        # S9 ALTERNATIVE_INTAKE (plan 1160 P5)
        ("NO_INTERIOR_FAST_MAXIMUM", "(1160 P5) ARGMAX_FAST, block 3 cut after its maximum (its maximum at its fast end) (1160 A39: was SECOND_LANE_INFEASIBLE)", lambda: lt(bank(cut), ARGMAX_LANE)),
        ("PASS", "(1160 P5) ARGMAX_FAST on the uncut bank (every maximum interior)", lambda: lt(bank(), ARGMAX_LANE)),
        ("ANCHOR_OUTSIDE_NEIGHBOUR_SPAN", "(1160 P5) PAIR_NEAREST_FAST on C, block 5's T moved beyond every neighbour's span (1160 A39: was SECOND_LANE_INFEASIBLE)", lambda: lt(bank(moved), PAIR_LANE)),
        ("PROJECTION_EMPTY_ON_CURVE", "(1160 A39.1) the PRIMARY projection ARGMAX_FAST, block 3 cut after its maximum", lambda: lt(bank(cut), lambda t: t.replace('bias = "MAX_MEASURED"', 'bias = "ARGMAX_FAST"', 1))),
        ("PASS", "(1160 P5) PAIR_NEAREST_FAST on C on the unmoved bank", lambda: lt(bank(), PAIR_LANE)),
        # S10 KERNEL_HANDOFF (plan 1160 P6)
        ("NO_KERNEL_ROUTE", "(1160 P6) the PRIMARY bridge PAIR_NEAREST_FAST on raw C (plan 1118's PAIR: no door template in CC)", lambda: pf("pf", PRIMARY_PAIR)),
        ("NO_KERNEL_ROUTE", "(1160 P6) the projection and the bridge both ALTERNATIVE: no PRIMARY bridge", lambda: pf("pf", ALL_ALTERNATIVE)),
        ("DOOR_REFUSED", "(1160 P6) [shift] c = nan: every r_k + c is not finite", lambda: pf("pf", SHIFT("nan"))),
        ("DOOR_REFUSED", "(1160 P6) block 5's sigma cell at its maximum is '1e400' (a decimal number S4 admits; it overflows to inf)",
         lambda: lt(bank([(h, [",".join(r.split(",")[:2] + ["1e400"]) if (i == 4 and j == top4) else r for j, r in enumerate(rs)]) for i, (h, rs) in enumerate(curves)]))),
        ("PASS", "(1160 P6) [shift] c = -1000.5 (x + c, applied at S10 only)", lambda: pf("pf", SHIFT("-1000.5"))),
        # S4 SHAPE
        ("READER_NOT_LIVE", "reader P1", lambda: pf("pf", lambda t: t.replace('name = "csv-curve-v1"', 'name = "P1"'))),
        ("COLUMNS_DIFFER", "csv-curve-v1, the first file's header T,Q,sigma", lambda: pf(copy(lambda b: (b / m["files"][0]["name"]).write_text((b / m["files"][0]["name"]).read_text().replace("T,C,sigma", "T,Q,sigma", 1))))),
        ("UNIT_DIFFERS", "(1160 P2) a NAMES_UNITS_IN_NAMES names line 'T (K),...'", lambda: lt(bank(head="T (K),C (dimensionless),sigma (dimensionless),h (dimensionless)\n"),
                                                                                          header='kind = "NAMES_UNITS_IN_NAMES"\nrows = 1\nnames = 1\nunit_syntax = "PAREN"')),
        ("UNIT_DIFFERS", "E3: a NAMES_UNITS header stating T in K", lambda: lt(bank(head="T,C,sigma,h\nK,dimensionless,dimensionless,dimensionless\n"), header=nu)),
        ("ROW_ORDER_DIFFERS", "one swapped pair inside block 5", lambda: lt(bank([(h, rs[:3] + [rs[4], rs[3]] + rs[5:]) if i == 4 else (h, rs) for i, (h, rs) in enumerate(curves)]))),
        # S5 CENSUS
        ("FILE_DIFFERS_FROM_FIRST", "a later file's header T,C,err", lambda: pf(copy(lambda b: (b / m["files"][5]["name"]).write_text((b / m["files"][5]["name"]).read_text().replace("T,C,sigma", "T,C,err", 1))))),
        ("CURVE_REPEATED", "a slow value in two non-adjacent blocks", lambda: lt(bank(curves + curves[:1]))),
        ("FAST_VALUE_REPEATED", "two adjacent runs of one slow value (one block, its T repeated)", lambda: lt(bank(curves[:1] + curves), asc)),
        ("SLOW_KEY_UNRESOLVED", "(1160) FILE_KEY h, one file's key line names another key", lambda: pf(copy(lambda b: (key_lines(b, m), (b / m["files"][4]["name"]).write_text("g" + (b / m["files"][4]["name"]).read_text()[1:]))),
                                                                                                         lambda t: slow_source(t, "FILE_KEY"))),
        ("SLOW_KEY_UNRESOLVED", "(1160) FILE_KEY h, a key line whose value is not a number", lambda: pf(copy(lambda b: key_lines(b, m, lambda h: f"h,{h}x\n")), lambda t: slow_source(t, "FILE_KEY"))),
        ("PASS", "(1160) FILE_KEY h, every file's key line a number", lambda: pf(copy(lambda b: key_lines(b, m)), lambda t: slow_source(t, "FILE_KEY"))),
        ("SLOW_NONE_HAS_NO_PATH", "(1160) slow source NONE (1160 A24: was TOO_FEW_CURVES at S8, now refused at S1; 1160 P5: was PASS)", lambda: pf("pf", lambda t: slow_source(t, "NONE"))),
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
    def s4(blocks):
        """(1160 A7) The counts of S4 ROW_ORDER_DIFFERS's Detail on a LONG_TABLE of `blocks` declared row_order ASCENDING (or S4's mark)."""
        ident = f"d{next(n)}"
        got = run(T, tmp, ident, long_table(m, ident).replace("<long-test>/pf", f"<long-test>/{bank(blocks)}"))["S4"].result
        return getattr(getattr(got, "evidence", None), "counts", got)
    cls = lambda a, b, c: {"in the declared order": a, "in the opposite order": b, "in neither order (not monotone)": c}
    check("E2. (1160 A7) ROW_ORDER_DIFFERS classifies the first file's curves by counts: one swapped pair in block 5 is 8 declared, 0 opposite, 1 neither",
          s4([(h, rs[:3] + [rs[4], rs[3]] + rs[5:]) if i == 4 else (h, rs) for i, (h, rs) in enumerate(curves)]) == {"curves": 1, **cls(8, 0, 1)}, "")
    check("E2. (1160 A7) every block written in descending T, declared ASCENDING: 0 declared, 9 opposite, 0 neither (a count, no value)",
          s4([(h, rs[::-1]) for h, rs in curves]) == {"curves": 9, **cls(0, 9, 0)}, str(s4([(h, rs[::-1]) for h, rs in curves])))
    def folded(text_of, blocks=None):
        """(1160 A9) The fold of a declaration (a PER_FILE of pf, or a LONG_TABLE of `blocks`), edited by text_of."""
        ident = f"d{next(n)}"
        base = {True: lambda: per_file(m, ident), False: lambda: long_table(m, ident).replace("<long-test>/pf", f"<long-test>/{bank(blocks)}")}[blocks is None]()
        return run(T, tmp, ident, text_of(base))
    for what, blocks, lane, code in (("ARGMAX_FAST, block 3 cut after its maximum", cut, ARGMAX_LANE, "NO_INTERIOR_FAST_MAXIMUM"),
                                     ("PAIR_NEAREST_FAST on C, block 5's T moved", moved, PAIR_LANE, "ANCHOR_OUTSIDE_NEIGHBOUR_SPAN")):
        out9 = folded(lane, blocks)
        p9, r9 = intake_fold.verdicts(T, out9)
        check(f"E2. (1160 A9) {what}: S9 refuses {code} (1160 A39: was SECOND_LANE_INFEASIBLE), S10 still EXECUTES and passes, PRIMARY misses only confirmation, ROBUSTNESS_REFUSED at S9",
              outcome(out9, "S9")[0] == code and out9["S10"].mark is intake.Mark.PASSED and p9.missing == ("confirmation",)
              and (r9.kind, r9.at) == (intake_fold.Robustness.ROBUSTNESS_REFUSED, "S9"), str((out9["S10"].mark, p9, r9)))
    words = lambda edit: " | ".join(getattr(getattr(folded(edit)["S1"], "result", None), "evidence", blind.detail()).words)
    check("E2. (1160 A9) OPERATION_NOT_PERMITTED names the link the step is permitted on: PAIR_NEAREST_FAST on C_max wants RAW (the measured name)",
          "PAIR_NEAREST_FAST on 'C_max' (DERIVED_OBSERVABLE; it is permitted on RAW (the measured name))" in words(CHOICE_PLANTS[7][2]), words(CHOICE_PLANTS[7][2]))
    check("E2. (1160 A9) ... and CHAIN_SLOW on the raw C wants the `to` of a projection of the same lane",
          "CHAIN_SLOW on 'C' (RAW; it is permitted on DERIVED_OBSERVABLE (the `to` of a projection of the same lane))" in words(lambda t: t.replace('on = "C_max"', 'on = "C"', 1)),
          words(lambda t: t.replace('on = "C_max"', 'on = "C"', 1)))
    none = slow_label("pf", "NONE")
    check("E2. (1160 A24; was P1: NONE reached the census with curves_with_slow = 0) slow source NONE is refused at S1 before any byte is read",
          none == "SLOW_NONE_HAS_NO_PATH", str(none))
    keyed = slow_label(copy(lambda b: key_lines(b, m)), "FILE_KEY")
    check("E2. (1160 P1) FILE_KEY reaches the census with every curve's slow value, as LISTED does", (getattr(keyed, "with_slow", None), getattr(keyed, "curves", None)) == (len(m["files"]),) * 2
          and keyed == slow_label("pf", "LISTED"), str(keyed))
    # ---- (1160 P5) the S7 floors are CC's (cc/declare.py), on counts; the evidence of a run that passes S7, S8 and S9
    pts = lambda n: (("curve_a", 1, n), ("curve_a", 2, n))
    gam, ch = {"method": "gamma", "tau_declared": 1}, {"method": "chains", "m": 3, "r": readout.rank(3, 0.25), "alpha": 0.25}
    k = T["interval_fields"]["gamma"]["k_gamma"]
    check("E2. (1160 P5) FLOOR gamma is CC's gamma_floor: n = k_gamma * tau_declared readings meet it, one fewer does not",
          not intake_feasible.FLOOR["gamma"](gam, pts(k), T) and bool(intake_feasible.FLOOR["gamma"](gam, pts(k - 1), T)), str(k))
    check("E2. (1160 P5) FLOOR chains is CC's chain_cells: m = 3 readings per point (chains 0..2) meet it, 2 do not",
          not intake_feasible.FLOOR["chains"](ch, pts(3), T) and bool(intake_feasible.FLOOR["chains"](ch, pts(2), T)), str(ch))
    check("E2. (1160 P5) FLOOR block is CC's block_floor: b 1, min_blocks 3 is met by 3 readings, not by 2",
          not intake_feasible.FLOOR["block"]({"method": "block", "b": 1, "min_blocks": 3}, pts(3), T) and bool(intake_feasible.FLOOR["block"]({"method": "block", "b": 1, "min_blocks": 3}, pts(2), T)), "")
    ev = run(T, tmp, "p5", per_file(m, "p5"))
    s7, s8, s9 = (outcome(ev, x)[1] for x in ("S7", "S8", "S9"))
    check("E2. (1160 P5) the plant's run passes S7 with tiering STATED, S8 with CANDIDATE_BRACKET and the identifiability value, S9 with no ALTERNATIVE lane",
          (getattr(s7, "tiering", None), getattr(s8, "max_bracket", None), getattr(s8, "identifiability", None), getattr(s9, "lanes", None))
          == ("STATED", "CANDIDATE_BRACKET", intake_feasible.IDENTIFIABILITY, ()), str((s7, s8, s9))[:400])
    lanes = {k: intake_fold.verdicts(T, run(T, tmp, f"rl{k}", e(per_file(m, f"rl{k}"))))[1].kind for k, e in ((1, lambda t: t), (2, ARGMAX_LANE))}
    check("E2. (1160 A5) ROBUSTNESS is NOT_EXAMINED on the one-lane plant's run and COMPLETE on its ARGMAX_FAST two-lane run",
          lanes == {1: intake_fold.Robustness.ROBUSTNESS_NOT_EXAMINED, 2: intake_fold.Robustness.ROBUSTNESS_COMPLETE}, str(lanes))
    tiers = {meth: getattr(outcome(run(T, tmp, f"t{meth}", edit(per_file(m, f"t{meth}"))), "S7")[1], "tiering", None)
             for meth, edit in (("NONE", lambda t: t.replace('method = "STATED"', 'method = "NONE"', 1)),)}
    check("E2. (1160 P5) interval NONE passes S7 with tiering NONE", tiers == {"NONE": "NONE"}, str(tiers))
    check("E2. READER_REFUSED: the reader-reason plants arrived through S4 READER_REFUSED", "READER_REFUSED" in SEEN, str(sorted(SEEN)))
    reached |= SEEN & {"READER_REFUSED"}
    print(f"  openpyxl {'installed' if HAS_XLSX else 'NOT installed'} on this machine; NOT REACHED HERE: {NOT_HERE or 'none'}")
    check("E2. the codes the plants reach are exactly the live rows (with the machine's NOT REACHED rows)",
          (reached - {"XLSX_GRID", "PASS"}) | set(NOT_HERE) == LIVE, f"live, never reached: {sorted(LIVE - reached - set(NOT_HERE))}; reached, not live: {sorted(reached - LIVE - {'XLSX_GRID', 'PASS'})}")   # 1160: PASS plants (FILE_KEY, NONE)

    # ---- E4. explain and the report carry the rows that are not live
    dead = [f"- {s['id']} {r['code']}" for s, _, r in ROWS if not r["live"]]
    doc = (ROOT / "docs" / "INTAKE.md").read_text()
    check("E4. docs/INTAKE.md (explain) lists every row that is not live, and marks it NOT LIVE in its stage table",
          (bool(dead) or "- none: every row is live (plan 1160 P6)" in doc) and all(x in doc for x in dead) and all(f"| {r['code']} | NOT LIVE |" in doc for _, _, r in ROWS if not r["live"]), str([x for x in dead if x not in doc][:3]))
    rep = intake_say.report(rooted(T, tmp), "pf", run(T, tmp, "rep", per_file(m, "rep")), (intake_seal.Ordering.NO_DATA_READ_LOGGED, "planted"))
    check("E4. a run's report lists every row that is not live", all(x in rep for x in dead), str([x for x in dead if x not in rep][:3]))

print("test_intake_reach: " + ("FAILED " + "; ".join(bad) if bad else "all passed"))
sys.exit(1 if bad else 0)
