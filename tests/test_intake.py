"""test_intake - plan 1136 phase 1, tests 1 to 5 (amendment A2), and the binding checks of the intake's code.
 1. intake/STAGES.toml and the runner agree: the bodies are exactly the implemented rows; needs point back; every stage that reads data bytes
    has S0 FORMAT and never the seal in its transitive needs; every data stage has a signature; every reason code the code emits is a row of its stage.
 2. docs/INTAKE.md is docs/gen-intake.py's output byte for byte, and `bin/cc intake explain` prints the same text.
 3. A stub never produces PRIMARY_READY, and the verdict tables are total: EVERY fold of the stage table (each stage a stub, a passing or a
    refusing body; the seal confirmed or not) is run, and the cells it reaches are exactly the reachable cells, never an IMPOSSIBLE one.
 4. The seal is advisory (plan 1139, amendment A3; the plan-1136 test 4, "a Sealed cannot be built and every data stage takes it", is RETIRED):
    S2 in a run never refuses and reports UNSEALED before a seal, SEALED after one, SEALED_THEN_EDITED after an edit; the ordering note is
    information; no data stage's signature takes a seal; mint still refuses an absent universe and a second seal.
 5. Five planted bad declarations (the worked example with one planted edit each) are refused at S0 FORMAT with their named reasons.
 Plus: the enum names parse as Boolean formulas (binding rule); S0's module can open nothing (imports and calls, over the AST); the copied
 loader is byte-identical to its pin."""
import ast
import dataclasses
import enum
import hashlib
import inspect
import itertools
import os
import re
import shutil
import subprocess
import sys
import tempfile
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path[:0] = [str(ROOT / "cc")]
import intake  # noqa: E402
import intake_blind as blind  # noqa: E402
import intake_data  # noqa: E402
import intake_seal  # noqa: E402

bad = []


def check(name, ok, why=""):
    print(("ok   " if ok else "FAIL ") + name + ("" if ok else f": {why}"))
    if not ok:
        bad.append(name)


T = intake.tables(ROOT)
ST = T["stages"]["stage"]
IDS = [s["id"] for s in ST]
REASONS = {s["id"]: [r["code"] for r in s["reason"]] for s in ST}
SEAL = T["stages"]["seal_stage"]
EXAMPLE = ROOT / "declarations" / "dial1118-s1-v3"   # plan 1160 P1: the worked example restated in format v3 (dial1118-s1 is v1, -v2 is v2: history)
FIXTURE = ROOT / "tests" / "planted" / "intake" / "p1118-bank-FIXTURE"

# ---- 1. the stage table and the runner
check("1. the bodies are exactly the stages with implemented = true", set(intake.bodies(T, EXAMPLE, "", [])) == {s["id"] for s in ST if s["implemented"]},
      f"{sorted(intake.bodies(T, EXAMPLE, '', []))} against {[s['id'] for s in ST if s['implemented']]}")
check("1. the stages are S0..S10 in run order (amendment A2 Q13)", IDS == [f"S{i}" for i in range(11)], str(IDS))
check("1. every need names an earlier stage", all(n in IDS[:IDS.index(s["id"])] for s in ST for n in s["needs"]), "")
check("1. every stage that reads data bytes has S0 and never the seal stage in its transitive needs (amendment A3)",
      all("S0" in intake.closure(T, s["id"]) and SEAL not in intake.closure(T, s["id"]) for s in ST if s["reads_bytes"] != "NONE"), "")
check("1. the seal stage is ADVISORY and in no stage's transitive needs", [s["verdict"] for s in ST if s["id"] == SEAL] == ["ADVISORY"] and all(SEAL not in intake.closure(T, i) for i in IDS), "")
READS = {s["id"] for s in ST if s["reads_bytes"] != "NONE"}
check("1. SIGNATURE has a row for exactly the data stages (they read bytes, or a stage they need does)",
      set(intake_data.SIGNATURE) == {s["id"] for s in ST if s["id"] in READS or intake.closure(T, s["id"]) & READS}, str(sorted(intake_data.SIGNATURE)))
check("1. the seal status and ordering rows are exactly the atoms of SealStatus and Ordering",
      [r["code"] for s in ST if s["id"] == SEAL for r in s["status"]] == [x.name for x in intake_seal.SealStatus]
      and [r["code"] for r in T["stages"]["report"]["ordering"]] == [x.name for x in intake_seal.Ordering], "")
check("1. reads_bytes and verdict hold atoms of ReadsBytes and Scope", all(s["reads_bytes"] in intake.ReadsBytes.__members__ and s["verdict"] in intake.Scope.__members__ for s in ST), "")
check("1. one ROBUSTNESS stage and one HANDOFF stage", [s["verdict"] for s in ST].count("ROBUSTNESS") == 1 and [s["verdict"] for s in ST].count("HANDOFF") == 1, "")
codes = [c for v in REASONS.values() for c in v]
check("1. reason codes are unique across the table", len(codes) == len(set(codes)), str([c for c in codes if codes.count(c) > 1]))


def emitted(module, ctor):
    """The string constants passed first to `ctor(...)` in a module's source."""
    tree = ast.parse(Path(module.__file__).read_text())
    return {n.args[0].value for n in ast.walk(tree) if isinstance(n, ast.Call) and getattr(n.func, "id", "") == ctor and n.args and isinstance(n.args[0], ast.Constant)}


def fmt_codes(rows):
    out = set()
    for spec in rows.values():
        out |= {v for v in spec.get("values", {}).values() if v != "ADMIT"} | ({spec["absent"]} if "absent" in spec else set())
        out |= fmt_codes(spec.get("fields", {})) | (fmt_codes({"m": spec["method"]}) if "method" in spec else set())
        out |= {c for v in spec.get("variants", {}).values() for c in fmt_codes(v)}   # plan 1145: the fields of each VARIANT row
    return out


s0 = emitted(blind, "Finding") | fmt_codes(T["format"]["fields"]) | {"VALUE_STILL_TODO", "FIELD_IS_STAMPED", "FIELD_IS_DERIVED", "FIELD_UNKNOWN"}
check("1. every reason S0 emits (code and FORMAT.toml) is an S0 reason", s0 <= set(REASONS["S0"]), str(sorted(s0 - set(REASONS["S0"]))))
check("1. every reason S2 emits (intake_seal) is an S2 reason", emitted(intake_seal, "Refuse") <= set(REASONS[SEAL]), str(sorted(emitted(intake_seal, "Refuse") - set(REASONS[SEAL]))))


def words(rows, key):
    return ({spec[key] for spec in rows.values() if key in spec} | {w for spec in rows.values() for w in words(spec.get("fields", {}), key) | words({"m": spec["method"]} if "method" in spec else {}, key)}
            | {w for spec in rows.values() for v in spec.get("variants", {}).values() for w in words(v, key)})   # plan 1145: VARIANT rows


check("1. every check word of FORMAT.toml is a key of intake_blind.CHECK", words(T["format"]["fields"], "check") <= set(blind.CHECK), str(words(T["format"]["fields"], "check") - set(blind.CHECK)))
check("1. every type word of FORMAT.toml is a key of intake_blind.TYPE", words(T["format"]["fields"], "type") | words(T["format"]["fields"], "item") <= set(blind.TYPE), "")
F = T["format"]["fields"]
KINDS = set(F["source"]["variants"])
SLOWS = {lay: set(F["selection"]["variants"][lay]["slow"]["variants"]) for lay in F["selection"]["variants"]}
check("1. (1160 P1) the [source] kinds are DEPOSIT and CONVERTED, and SOURCE (the S3 body per kind) is total over them", KINDS == {"DEPOSIT", "CONVERTED"} and set(intake_data.SOURCE) == KINDS, str(KINDS))
check("1. (1160 P1) the PER_FILE slow sources are LISTED, FILE_KEY, NONE; SLOW and UNKEYED are total over them",
      SLOWS["PER_FILE"] == {"LISTED", "FILE_KEY", "NONE"} and set(intake_data.SLOW) == set(intake_data.UNKEYED) == SLOWS["PER_FILE"], str(SLOWS))
check("1. (1160 P1) ONE_PER_FILE (S1) is total over every slow source of every layout", set(blind.ONE_PER_FILE) == set().union(*SLOWS.values()), str(sorted(blind.ONE_PER_FILE)))
check("1. (1160 P1) KEYS and CURVES are total over the layouts", set(intake_data.KEYS) == set(intake_data.CURVES) == set(F["selection"]["variants"]), "")
check("1. (1160 P1) [source] admissibility is RAW | DECLARABLE | FIGURE_LEVEL | PROCESSED_UNDECLARABLE in every kind",
      all(set(F["source"]["variants"][k]["admissibility"]["values"]) == {"RAW", "DECLARABLE", "FIGURE_LEVEL", "PROCESSED_UNDECLARABLE"} for k in KINDS), "")
check("1. (1160 P1) converted_from is a field of the CONVERTED row only", ["converted_from" in F["source"]["variants"][k] for k in ("DEPOSIT", "CONVERTED")] == [False, True], "")
check("1. (1160 P1) PATH_PATTERN, pattern and index are gone", "PATH_PATTERN" not in str(F) and not {"pattern", "index"} & set(F["selection"]["variants"]["PER_FILE"]), "")
check("1. (1160 P1) PATH_NOT_ADMITTED is gone from STAGES.toml and the code; its three causes are three S3 rows, in ADMIT order",
      "PATH_NOT_ADMITTED" not in codes and "PATH_NOT_ADMITTED" not in Path(intake_data.__file__).read_text()
      and [c for c, _, _ in intake_data.ADMIT] == [c for c in REASONS["S3"] if c.startswith("PATH_")] == ["PATH_OUTSIDE_ROOT", "PATH_ON_TRUTH_SIDE", "PATH_NOT_A_FILE"], str(REASONS["S3"]))
check("1. (1160 P1) S1's live rows are exactly the rows its body checks", [r["code"] for s in ST if s["id"] == "S1" for r in s["reason"] if r["live"]] == ["SLOW_VALUES_NOT_ONE_PER_FILE"], "")
check("1. every admit source of FORMAT.toml is a source the tables provide", all(src in T["admit"] for spec in [T["format"]["fields"]["interval"]["method"]] for src in spec["admit"]), "")

# ---- 2. the generated docs page
gen = subprocess.run([sys.executable, "docs/gen-intake.py"], capture_output=True, text=True, cwd=ROOT)
check("2. docs/gen-intake.py reproduces docs/INTAKE.md byte for byte", gen.returncode == 0 and gen.stdout == (ROOT / "docs" / "INTAKE.md").read_text(), gen.stderr[-300:])
exp = subprocess.run([str(ROOT / "bin" / "cc"), "intake", "explain"], capture_output=True, text=True, cwd=ROOT)
check("2. bin/cc intake explain prints docs/INTAKE.md", exp.returncode == 0 and exp.stdout == (ROOT / "docs" / "INTAKE.md").read_text(), exp.stderr[-300:])

# ---- 3. the verdict tables are total, every cell is reached or IMPOSSIBLE, and a stub never produces READY
product = set(itertools.product(intake.Primary, blind.Mark))
check("3. ROBUSTNESS and IMPOSSIBLE partition (PRIMARY x Mark)", set(intake.ROBUSTNESS) | set(intake.IMPOSSIBLE) == product and not set(intake.ROBUSTNESS) & set(intake.IMPOSSIBLE), "")
check("3. PRIMARY is total over (R, U, C)", set(intake.PRIMARY) == set(itertools.product((False, True), repeat=3)), "")
check("3. EXEC is total over (implemented, Upstream)", set(intake.EXEC) == set(itertools.product((False, True), intake.Upstream)), "")


@dataclasses.dataclass(frozen=True)
class Ev:
    conf: bool

    def summary(self):
        return "planted"

    def confirmed(self):
        return self.conf


CHOICE = {"stub": None, "pass": lambda *a: blind.Pass(Ev(False)), "refuse": lambda *a: blind.Refuse(REASONS["S0"][0], "planted")}
SEAL_CHOICE = {"pass": CHOICE["pass"], "pass-confirmed": lambda *a: blind.Pass(Ev(True))}   # the ADVISORY seal is LIVE and never refuses (A3)
hit_p, hit_r, stub_ready, body_on_stub, folds = set(), set(), [], [], 0
prim = [s["id"] for s in ST if s["verdict"] == "PRIMARY"]
axes = [{True: SEAL_CHOICE, False: CHOICE}[i == SEAL] for i in IDS[:-1]]
for combo in itertools.product(*[list(a) for a in axes]):
    pick = dict(zip(IDS[:-1], combo))
    rows = [{**s, "implemented": pick.get(s["id"], "stub") != "stub"} for s in ST]
    bodies = {i: {**CHOICE, **SEAL_CHOICE}[c] for i, c in pick.items() if c != "stub"}
    t = {**T, "stages": {**T["stages"], "stage": rows}}
    out = intake.fold(rows, bodies)
    p, r = intake.verdicts(t, out)
    folds += 1
    marks = {out[i].mark for i in prim}
    hit_p.add((blind.Mark.REFUSED in marks, len(intake._missing(prim, out)) > 0, out[SEAL].confirmed()))
    hit_r.add((p.kind, out[IDS[-2]].mark))
    stub_ready += [pick] * (p.kind is intake.Primary.PRIMARY_READY and any(not s["implemented"] for s in rows if s["id"] in prim))
    body_on_stub += [pick] * any(isinstance(out[s["id"]], intake.Executed) for s in rows if not s["implemented"])
print(f"  {folds} folds of the stage table enumerated")
check("3. a stub never produces PRIMARY_READY (over every fold)", not stub_ready, str(stub_ready[:1]))
check("3. a stage with no body is never EXECUTED (over every fold)", not body_on_stub, str(body_on_stub[:1]))
check("3. every PRIMARY cell is reached", hit_p == set(intake.PRIMARY), str(set(intake.PRIMARY) - hit_p))
check("3. the reached ROBUSTNESS cells are exactly the table's, and no IMPOSSIBLE cell is reached", hit_r == set(intake.ROBUSTNESS), str(hit_r ^ set(intake.ROBUSTNESS)))

# ---- 4. the seal is advisory (plan 1139, A3): a status value, never a refusal; plan 1136's test 4 (Sealed-carrying signatures) is retired
for sid, sig in intake_data.SIGNATURE.items():
    ann = [p.annotation for p in sig.parameters.values()]
    need = [intake_data.EVIDENCE[n] for n in next(s for s in ST if s["id"] == sid)["needs"]]
    check(f"4. {sid}'s signature takes the evidence of its needs and no seal", ann == need and not any("Seal" in a.__name__ for a in ann), f"{ann} against {need}")
check("4. every registered data-stage body has its SIGNATURE row", all(inspect.signature(b) == intake_data.SIGNATURE[k] for k, b in intake_data.bodies(T, EXAMPLE).items()), "")
with tempfile.TemporaryDirectory() as tmp:
    d = Path(tmp) / "decl"
    d.mkdir()
    for n in intake_seal.FILES:
        shutil.copyfile(EXAMPLE / n, d / n)
    decl = blind.format_stage((d / "intake.toml").read_text(), [], T).evidence
    status = lambda: intake_seal.verify(decl, d, T)
    check("4. S2 before any seal passes UNSEALED, unconfirmed", isinstance(status(), blind.Pass) and status().evidence.status is intake_seal.SealStatus.UNSEALED and not status().confirmed(), str(status()))
    check("4. the ordering note before any seal is NOT_SEALED", intake_seal.ordering(d, T)[0] is intake_seal.Ordering.NOT_SEALED, "")
    who = {"author": "test", "author_kind": "AI_DRAFT", "confirmed_by": ""}
    check("4. mint refuses a universe that is not a directory", intake_seal.mint(decl, d, str(Path(tmp) / "none"), who, ROOT, T).reason == "UNIVERSE_ROOT_ABSENT", "")
    minted = intake_seal.mint(decl, d, str(FIXTURE), who, ROOT, T)
    check("4. mint seals the example against the fixture (63 names, sizes 0)", isinstance(minted, blind.Pass) and len(minted.evidence.record["universe"]["listing"]) == 63, str(minted)[:300])
    check("4. (1160 P1) the seal counts each part of the universe as a list: 61 selected, 1 excluded, 1 truth side (63 names, each once)",
          minted.evidence.record["universe"]["partition"] == {"selected": 61, "excluded": 1, "truth_side": 1}, str(minted.evidence.record["universe"].get("partition")))
    check("4. a second mint is ALREADY_SEALED", intake_seal.mint(decl, d, str(FIXTURE), who, ROOT, T).reason == "ALREADY_SEALED", "")
    check("4. S2 after the seal passes SEALED (unconfirmed: confirmed_by is empty)", status().evidence.status is intake_seal.SealStatus.SEALED and not status().confirmed(), str(status())[:200])
    check("4. the ordering note with no logged read is NO_DATA_READ_LOGGED", intake_seal.ordering(d, T)[0] is intake_seal.Ordering.NO_DATA_READ_LOGGED, "")
    (d / "access.log").write_text('{"t_ns": 1, "route": "loader", "path": "S1/S1_c000.npz"}\n')
    check("4. a loader read before the seal is an ordering note A_READ_PRECEDES_SEAL, and S2 still passes", intake_seal.ordering(d, T)[0] is intake_seal.Ordering.A_READ_PRECEDES_SEAL and isinstance(status(), blind.Pass), "")
    (d / "intake.toml").write_text((d / "intake.toml").read_text() + "# one edit after the seal\n")
    check("4. S2 after an edit passes SEALED_THEN_EDITED (never a refusal)", isinstance(status(), blind.Pass) and status().evidence.status is intake_seal.SealStatus.SEALED_THEN_EDITED and not status().confirmed(), str(status())[:200])

# ---- 5. planted bad declarations, each refused at S0 with its named reason
base = (EXAMPLE / "intake.toml").read_text()
check("5. the clean base (the worked example) passes S0 with no transducer finding", isinstance(blind.format_stage(base, [], T), blind.Pass), str(blind.format_stage(base, [], T))[:300])
PLANTED = [
    ("a missing knob ([knobs.fast] deleted)", re.sub(r"(?s)\[knobs\.fast\].*?(?=\[measured\])", "", base), "FIELD_MISSING"),
    ("a free-text bias", base.replace('bias = "MAX_MEASURED"', 'bias = "the largest C of each curve"'), "BIAS_KEY_UNDECLARED"),
    ("an interpolation bridge", base.replace('template = "CHAIN_SLOW"', 'template = "INTERPOLATE"'), "STEP_IS_INTERPOLATION"),
    ("a typed timestamp", base.replace('[intake]\n', '[intake]\nsealed_at = "2026-10-18T09:00:00Z"\n'), "FIELD_IS_STAMPED"),
    ("no bridge fits", base.replace('template = "CHAIN_SLOW"', 'template = "NONE_FITS"'), "BRIDGE_NONE_FITS"),
    ("(extra) a derived field typed", base.replace('[acquisition]\n', '[acquisition]\ncorrelated = true\n'), "FIELD_IS_DERIVED"),
    ("(extra) a figure in the basis", base.replace('class = "PAPER_METHODS"', 'class = "FIGURE"'), "BASIS_NOT_METADATA"),
    ("(extra) a TODO left", base.replace('mode = "EXPLORATORY"', 'mode = "TODO"'), "VALUE_STILL_TODO"),
    ("(extra) not TOML", base + "\n[[[", "TOML_INVALID"),
    ("(extra) another schema (4)", base.replace("schema = 3", "schema = 4", 1), "SCHEMA_UNSUPPORTED"),
    ("(1160) a v2 declaration (format v2 is history)", (ROOT / "declarations" / "dial1118-s1-v2" / "intake.toml").read_text(), "SCHEMA_UNSUPPORTED"),
    ("(1160) PATTERN is gone: a v2 pattern and index in a v3 file", base.replace("files = [", 'pattern = "S1/S1_c{index:03d}.npz"\nfiles = [', 1), "FIELD_UNKNOWN"),
    ("(1160) a LISTED value that is not a number written as text", base.replace('"-0.150"', '"minus 0.15"', 1), "FIELD_TYPE_WRONG"),
    ("(1160) a LISTED value written as a TOML number", base.replace('"-0.150"', '-0.150', 1), "FIELD_TYPE_WRONG"),
    ("(1160) a [source] kind naming no row", base.replace('kind = "DEPOSIT"', 'kind = "COPIED"', 1), "VALUE_NOT_LISTED"),
    ("(1160) converted_from on a DEPOSIT", base.replace('kind = "DEPOSIT"', 'kind = "DEPOSIT"\nconverted_from = "<cc-datasets>/x/raw"', 1), "FIELD_UNKNOWN"),
    ("(1160) a CONVERTED source without converted_from", base.replace('kind = "DEPOSIT"', 'kind = "CONVERTED"', 1).replace('root = "<p1118-bank>"', 'root = "<cc-banks>/dial1118-s1/bank"', 1), "FIELD_MISSING"),
    ("(1160) a CONVERTED source whose root is not under <cc-banks>", base.replace('kind = "DEPOSIT"', 'kind = "CONVERTED"\nconverted_from = "<cc-datasets>/x/raw"', 1), "ROOT_NOT_UNDER_CC_BANKS"),
    ("(1160) an admissibility naming no class", base.replace('admissibility = "RAW"', 'admissibility = "CLEAN"', 1), "VALUE_NOT_LISTED"),
    ("(1160) no admissibility", re.sub(r"admissibility = \"RAW\".*\n", "", base, count=1), "FIELD_MISSING"),
    ("(1145) a v1 declaration (format v1 is history)", (ROOT / "declarations" / "dial1118-s1" / "intake.toml").read_text(), "SCHEMA_UNSUPPORTED"),
    ("(1145) a field of another VARIANT row (a table-curve-v1 field under npz-curve-v1)", base.replace('[reader]\n', '[reader]\ncomment = ["#"]\n'), "FIELD_UNKNOWN"),
    ("(1145) a VARIANT selector naming no row (layout BY_ROW)", base.replace('layout = "PER_FILE"', 'layout = "BY_ROW"'), "VALUE_NOT_LISTED"),
    ("(1145) a VARIANT row's field missing ([selection.slow] LISTED without values; 1160: was per_file)", re.sub(r"(?s)values = \[.*?\]\n", "", base, count=1), "FIELD_MISSING"),
    ("(1145) a column that is neither a name nor a position (a list)", base.replace('key = "T"', 'key = ["T"]', 1), "FIELD_TYPE_WRONG"),
    ("(1145) a column that is a boolean", base.replace('key = "C"', 'key = true', 1), "FIELD_TYPE_WRONG"),
    ("(extra) an interval field of another method", base.replace("b = 100\n", "b = 100\nwindow_s = 1.0\n"), "FIELD_UNKNOWN"),
]
for name, text, want in PLANTED:
    got = blind.format_stage(text, [], T)
    check(f"5. {name}: refused {want}", text != base and isinstance(got, blind.Refuse) and got.reason == want, str(got)[:300])
for name, text, want in [("(1160) the same file count and values count", base, None),
                         ("(1160) one LISTED value short of the files", base.replace('"-0.150", ', "", 1), "SLOW_VALUES_NOT_ONE_PER_FILE"),
                         ("(1160) one file more than the LISTED values", base.replace('"S1/S1_c000.npz", ', '"S1/S1_c000.npz", "S1/S1_c000b.npz", ', 1), "SLOW_VALUES_NOT_ONE_PER_FILE")]:
    got = blind.choices(blind.format_stage(text, [], T).evidence)
    check(f"5. S1 {name}: {want or 'PASS'}", {True: lambda: isinstance(got, blind.Pass), False: lambda: isinstance(got, blind.Refuse) and got.reason == want}[want is None](), str(got)[:300])
got = blind.format_stage(base, ["transducer.update[0]: planted"], T)
check("5. (extra) a transducer finding: refused TRANSDUCER_FILE_REFUSED", isinstance(got, blind.Refuse) and got.reason == "TRANSDUCER_FILE_REFUSED", str(got)[:200])

# ---- binding rule: enum names are Boolean formulas
ENUMS = [intake.Execution, intake.Cause, intake.Upstream, intake.Primary, intake.Robustness, intake.ReadsBytes, intake.Scope, blind.Mark, intake_seal.SealStatus, intake_seal.Ordering]


def parse(name, atoms):
    """The set a constant name denotes: ATOM(_OR_ATOM)*, NOT_<ATOM> = the complement within the atoms; None when a part is no atom."""
    out = set()
    for part in name.split("_OR_"):
        neg = part.startswith("NOT_") and part[4:] in atoms
        lit = {True: atoms - {part[4:]}, False: {part} & atoms}[neg]
        if not lit:
            return None
        out |= lit
    return frozenset(out)


check("binding: the parser reads NOT_EXECUTED as {STUB, WITHHELD} (breaker: a wrong name is seen)", parse("NOT_EXECUTED", {"STUB", "WITHHELD", "EXECUTED"}) == {"STUB", "WITHHELD"}, "")
for E in ENUMS:
    m = re.search(r"ATOMS: ([A-Z_\s|]+?)\.", E.__doc__ or "")
    atoms = set(re.sub(r"\s", "", m[1]).split("|")) if m else set()
    vals = [x.value for x in E]
    check(f"binding: {E.__name__} declares ATOMS and an axiom, and its values partition them", bool(atoms) and "Axiom" in E.__doc__ and set().union(*vals) == atoms and sum(map(len, vals)) == len(atoms), str(atoms))
    check(f"binding: every {E.__name__} name parses to its set", all(parse(x.name, atoms) == x.value for x in E), str([x.name for x in E if parse(x.name, atoms) != x.value]))

# ---- blindness of S0: imports and calls of cc/intake_blind.py
tree = ast.parse(Path(blind.__file__).read_text())
mods = {a.name.split(".")[0] for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names} | {(n.module or "").split(".")[0] for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)}
check("blind: cc/intake_blind.py imports only tomllib, enum, dataclasses, typing, re", mods <= {"tomllib", "enum", "dataclasses", "typing", "re"}, str(mods))
calls = {n.func.id for n in ast.walk(tree) if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)} & {"open", "exec", "eval", "compile", "__import__", "getattr", "globals"}
check("blind: cc/intake_blind.py calls no open, exec, eval, compile or __import__", not calls, str(calls))

# ---- the copied loader is the toolset's, byte for byte (amendment A2 Q1)
pin = tomllib.loads((ROOT / "vendor" / "toolset" / "PIN.toml").read_text())
for f in pin["file"]:
    check(f"loader: {f['copy']} hashes to its recorded sha256", hashlib.sha256((ROOT / f["copy"]).read_bytes()).hexdigest() == f["sha256"], "")
tools = Path(os.path.expanduser(os.environ.get("CC_DATA_ROOT", str(ROOT / "data")))).parent
shown = [subprocess.run(["git", "-C", str(tools), "show", f"{pin['commit']}:{f['path']}"], capture_output=True) for f in pin["file"]]
reach = all(s.returncode == 0 for s in shown)
print({True: "  the toolset is reachable through the data root: its commit is compared too",
       False: "  INFO: the toolset is not reachable through the data root (CC_DATA_ROOT); only the recorded sha256 is checked"}[reach])
check("loader: the toolset commit holds each copied file with the recorded sha256 (when the toolset is reachable)",
      not reach or all(hashlib.sha256(s.stdout).hexdigest() == f["sha256"] for s, f in zip(shown, pin["file"])), "")
print("test_intake: " + ("FAILED " + "; ".join(bad) if bad else "all passed"))
sys.exit(1 if bad else 0)
