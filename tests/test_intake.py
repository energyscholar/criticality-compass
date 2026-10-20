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
 loader is byte-identical to its pin.
Seen RED (1160 P4; each mutation applied, the test run, the mutation reverted): NEEDS_COLUMN without NONE, or with a method BOGUS: the
interval-alphabet check FAILS; PERMITTED without (PAIR_NEAREST_FAST, NO_LINK): the PERMITTED totality check FAILS; ROUTE without DECLARABLE,
and intake_seal.SEEN without EXPLORATORY: the S1-tables totality check FAILS; STAGES LANES_IDENTICAL live = false: the S1 live-rows-in-order
check FAILS (and the INTAKE.md checks); S1's first two rows swapped in intake_choices.choices: the in-order check FAILS; `import os` in
cc/intake_choices.py: its blindness check FAILS.
Seen RED (1160 P5, A3): a LINEAGE_OFF_GRAPH row (live = false) put back in S6, or a SHIFT_BEFORE_KERNEL_INPUT row put back in S1: the
A3 check (no row of an implemented stage is live = false, neither deleted code is a row) FAILS.
Seen RED (1160 P5, S7-S9): REPLICATED without NONE: the S7-tables totality check FAILS; TIERING[STATED] made REPLICATES: the same check
FAILS (TIERING's values); COVERED without CANDIDATE_BRACKET: the COVERED/ENDS/PAIRS totality check FAILS; TOO_FEW_CURVES renamed in
cc/intake_feasible.py: the S7-S9 codes check FAILS.
Seen RED (1160 P6, S10): see the P6 lines of $S/p6-seenred.txt (the terminal tables' totality, its codes, its signature, the 3-way S10 enumeration).
Seen RED (1160 A9): S9's block moved back before S10 in intake/STAGES.toml: the run-order check, the ROBUSTNESS-after check and test 3's
reached-cells check FAIL ((READY, REFUSED) unreached; (REFUSED_AT, STUB) and (REFUSED_AT, PASSED) reached); the (READY, REFUSED) row
deleted from cc/intake.py ROBUSTNESS: test 3's partition check FAILS."""
import ast
import dataclasses
import enum
import hashlib
import inspect
import itertools
import json
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
import intake_choices  # noqa: E402
import intake_bytes  # noqa: E402
import intake_census  # noqa: E402
import intake_evidence  # noqa: E402
import intake_fold  # noqa: E402
import intake_names  # noqa: E402
import intake_seal  # noqa: E402

# The stage-signature oracle (it was cc/intake_data.py's SIGNATURE/EVIDENCE/sig until plan 1164, production code only this test read): every data stage -> the
# evidence of its needs, in needs order.
D = intake_evidence


def sig(**params):
    """A stage signature: the named evidence parameters in order, returning a StageResult (Pass | Refuse)."""
    return inspect.Signature([inspect.Parameter(n, inspect.Parameter.POSITIONAL_OR_KEYWORD, annotation=t) for n, t in params.items()],
                             return_annotation=blind.Pass | blind.Refuse)


EVIDENCE = {"S0": blind.Declaration, "S3": D.Pinned, "S4": D.Shaped, "S5": D.Census, "S6": D.Lineage, "S7": D.IntervalPlan, "S8": D.Feasibility,
            "S9": D.SecondLane, "S10": D.KernelInput}
SIGNATURE = {
    "S3": sig(declaration=blind.Declaration),
    "S4": sig(pinned=D.Pinned),
    "S5": sig(pinned=D.Pinned, shaped=D.Shaped),
    "S6": sig(census=D.Census),
    "S7": sig(census=D.Census),
    "S8": sig(census=D.Census),
    "S9": sig(census=D.Census),
    "S10": sig(lineage=D.Lineage, plan=D.IntervalPlan, feasibility=D.Feasibility),
}

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
EXAMPLE = ROOT / "declarations" / "dial1118-s1-v5"   # plan 1160 A35: the worked example restated in format v5 (dial1118-s1 is v1, -v2 is v2, -v3 is v3, -v4 is v4: history; was -v4)
FIXTURE = ROOT / "tests" / "planted" / "intake" / "p1118-bank-FIXTURE"

# ---- 1. the stage table and the runner
check("1. the bodies are exactly the stages with implemented = true", set(intake.bodies(T, EXAMPLE, "", [])) == {s["id"] for s in ST if s["implemented"]},
      f"{sorted(intake.bodies(T, EXAMPLE, '', []))} against {[s['id'] for s in ST if s['implemented']]}")
check("1. the stages are S0..S8, S10, S9 in run order (amendment A2 Q13; plan 1160 A9: S10 before S9, was S0..S10)", IDS == [f"S{i}" for i in range(9)] + ["S10", "S9"], str(IDS))
check("1. (1160 A9) the ROBUSTNESS stage runs after every PRIMARY and HANDOFF stage, so its refusal can withhold none of them",
      all(IDS.index(s["id"]) < IDS.index(next(r["id"] for r in ST if r["verdict"] == "ROBUSTNESS")) for s in ST if s["verdict"] in ("PRIMARY", "HANDOFF")), str(IDS))
check("1. every need names an earlier stage", all(n in IDS[:IDS.index(s["id"])] for s in ST for n in s["needs"]), "")
check("1. every stage that reads data bytes has S0 and never the seal stage in its transitive needs (amendment A3)",
      all("S0" in intake_fold.closure(T, s["id"]) and SEAL not in intake_fold.closure(T, s["id"]) for s in ST if s["reads_bytes"] != "NONE"), "")
check("1. the seal stage is ADVISORY and in no stage's transitive needs", [s["verdict"] for s in ST if s["id"] == SEAL] == ["ADVISORY"] and all(SEAL not in intake_fold.closure(T, i) for i in IDS), "")
READS = {s["id"] for s in ST if s["reads_bytes"] != "NONE"}
check("1. SIGNATURE has a row for exactly the data stages (they read bytes, or a stage they need does)",
      set(SIGNATURE) == {s["id"] for s in ST if s["id"] in READS or intake_fold.closure(T, s["id"]) & READS}, str(sorted(SIGNATURE)))
check("1. the seal status and ordering rows are exactly the atoms of SealStatus and Ordering",
      [r["code"] for s in ST if s["id"] == SEAL for r in s["status"]] == [x.name for x in intake_seal.SealStatus]
      and [r["code"] for r in T["stages"]["report"]["ordering"]] == [x.name for x in intake_seal.Ordering], "")
check("1. reads_bytes and verdict hold atoms of ReadsBytes and Scope", all(s["reads_bytes"] in intake_fold.ReadsBytes.__members__ and s["verdict"] in intake_fold.Scope.__members__ for s in ST), "")
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
check("1. (1160 P1) the [source] kinds are DEPOSIT and CONVERTED, and SOURCE (the S3 body per kind) is total over them", KINDS == {"DEPOSIT", "CONVERTED"} and set(intake_bytes.SOURCE) == KINDS, str(KINDS))
check("1. (1160 P1) the PER_FILE slow sources are LISTED, FILE_KEY, NONE; SLOW and UNKEYED are total over them",
      SLOWS["PER_FILE"] == {"LISTED", "FILE_KEY", "NONE"} and set(intake_census.SLOW) == set(intake_census.UNKEYED) == SLOWS["PER_FILE"], str(SLOWS))
check("1. (1160 A24) SLOW_PATH (S1) is total over every slow source of every layout, and NONE alone has no path",
      set(intake_choices.SLOW_PATH) == set().union(*SLOWS.values()) and {k for k, v in intake_choices.SLOW_PATH.items() if not v} == {"NONE"}, str(intake_choices.SLOW_PATH))
KINDS_SLOW = set(F["knobs"]["fields"]["slow"]["fields"]["kind"]["values"])   # (1160 A35) the [knobs.slow] kind alphabet
check("1. (1160 A35) METRIC (S1 SLOW_KNOB_HAS_NO_METRIC) is total over the [knobs.slow] kinds QUANTITY and ORDINAL, and ORDINAL alone has no metric",
      KINDS_SLOW == {"QUANTITY", "ORDINAL"} and set(intake_choices.METRIC) == KINDS_SLOW and {k for k, v in intake_choices.METRIC.items() if not v} == {"ORDINAL"}, str(intake_choices.METRIC))
check("1. (1160 P1) ONE_PER_FILE (S1) is total over every slow source of every layout", set(intake_choices.ONE_PER_FILE) == set().union(*SLOWS.values()), str(sorted(intake_choices.ONE_PER_FILE)))
check("1. (1160 P1) KEYS and CURVES are total over the layouts", set(intake_census.KEYS) == set(intake_census.CURVES) == set(F["selection"]["variants"]), "")
check("1. (1160 P1) [source] admissibility is RAW | DECLARABLE | FIGURE_LEVEL | PROCESSED_UNDECLARABLE in every kind",
      all(set(F["source"]["variants"][k]["admissibility"]["values"]) == {"RAW", "DECLARABLE", "FIGURE_LEVEL", "PROCESSED_UNDECLARABLE"} for k in KINDS), "")
check("1. (1160 P1) converted_from is a field of the CONVERTED row only", ["converted_from" in F["source"]["variants"][k] for k in ("DEPOSIT", "CONVERTED")] == [False, True], "")
check("1. (1160 P1) PATH_PATTERN, pattern and index are gone", "PATH_PATTERN" not in str(F) and not {"pattern", "index"} & set(F["selection"]["variants"]["PER_FILE"]), "")
check("1. (1160 P1) PATH_NOT_ADMITTED is gone from STAGES.toml and the code; its three causes are three S3 rows, in ADMIT order",
      "PATH_NOT_ADMITTED" not in codes and "PATH_NOT_ADMITTED" not in Path(intake_bytes.__file__).read_text()
      and [c for c, _, _ in intake_bytes.ADMIT] == [c for c in REASONS["S3"] if c.startswith("PATH_")] == ["PATH_OUTSIDE_ROOT", "PATH_ON_TRUTH_SIDE", "PATH_NOT_A_FILE"], str(REASONS["S3"]))
S1_ROWS = [r for s in ST if s["id"] == "S1" for r in s["reason"]]
NOT_LIVE_S1 = []   # plan 1160 P5 (A3): SHIFT_BEFORE_KERNEL_INPUT is deleted, unreachable by construction (was: ["SHIFT_BEFORE_KERNEL_INPUT"], P4)
CHOSEN = intake_choices.choices(blind.format_stage((EXAMPLE / "intake.toml").read_text(), [], T).evidence, T["policy"])
check("1. (1160 P4, P5) S1's live rows are every S1 row, and the rows its body checks are exactly them, in STAGES.toml order",
      [r["code"] for r in S1_ROWS if not r["live"]] == NOT_LIVE_S1 and isinstance(CHOSEN, blind.Pass) and list(CHOSEN.evidence.checked) == [r["code"] for r in S1_ROWS if r["live"]],
      str(CHOSEN)[:300])
DELETED = ("SHIFT_BEFORE_KERNEL_INPUT", "LINEAGE_OFF_GRAPH")   # plan 1160 P5, amendment A3: each unreachable by construction, named in STAGES.toml's comment
check("1. (1160 P5, A3) no row of an implemented stage is live = false, and SHIFT_BEFORE_KERNEL_INPUT and LINEAGE_OFF_GRAPH are no row of STAGES.toml",
      not [r["code"] for s in ST if s["implemented"] for r in s["reason"] + blind.look(s, "reader_reason", []) if not r["live"]] and not set(DELETED) & set(codes),
      str([r["code"] for s in ST if s["implemented"] for r in s["reason"] if not r["live"]]))
ALPHA = set(T["format"]["fields"]["interval"]["method"]["values"]) | set(tomllib.loads((ROOT / "cc.toml").read_text())["alphabets"]["interval_method"])
check("1. (1160 P4) the intake's interval alphabet is cc.toml's with STATED and NONE; NEEDS_COLUMN is total over it and every method has its fields",
      ALPHA == set(intake_choices.NEEDS_COLUMN) and {"STATED", "NONE"} < ALPHA and ALPHA <= set(T["interval_fields"]), str(sorted(ALPHA)))
CCB, FB = tomllib.loads((ROOT / "cc.toml").read_text())["interval_fields"]["block"], T["format"]["interval_fields"]["block"]
check("1. (1160 A4) FORMAT's [interval_fields.block] is cc.toml's with min_blocks moved from optional to required (no other drift)",
      FB == {"required": {**CCB["required"], "min_blocks": CCB["optional"]["min_blocks"]}, "optional": {k: v for k, v in CCB["optional"].items() if k != "min_blocks"}}
      and T["interval_fields"]["block"] == FB, str(FB))
import intake_feasible  # noqa: E402  (plan 1160 P5: S7, S8, S9)
check("1. (1160 P5) the S7 tables REPLICATED, TIERING, HAS_FLOOR and FLOOR are total over the interval alphabet; TIERING says STATED | REPLICATES | NONE",
      all(set(tab) == ALPHA for tab in (intake_feasible.REPLICATED, intake_feasible.TIERING, intake_feasible.HAS_FLOOR, intake_feasible.FLOOR))
      and set(intake_feasible.TIERING.values()) == {"STATED", "REPLICATES", "NONE"}, "")
check("1. (1160 P5) COVERED (S8) is total over [bracket] required's values; ENDS and PAIRS (S9) over POLICY's projections and bridges",
      set(intake_feasible.COVERED) == set(T["format"]["fields"]["bracket"]["fields"]["required"]["values"]) and set(intake_feasible.ENDS) == set(T["policy"]["projection"])
      and set(intake_feasible.PAIRS) == set(T["policy"]["bridge"]), "")
FEAS = {n.value for n in ast.walk(ast.parse(Path(intake_feasible.__file__).read_text())) if isinstance(n, ast.Constant) and n.value in set(codes)}
check("1. (1160 P5) every reason code cc/intake_feasible.py names is a row of S7, S8 or S9, and every row of S7, S8 and S9 is named there",
      FEAS == set(REASONS["S7"]) | set(REASONS["S8"]) | set(REASONS["S9"]), str(sorted(FEAS ^ (set(REASONS["S7"]) | set(REASONS["S8"]) | set(REASONS["S9"])))))
import intake_terminal  # noqa: E402  (plan 1160 P6: S10 and the terminal)
TIERINGS = set(intake_feasible.TIERING.values())
check("1. (1160 P6) the terminal tables are total: ROUTE over POLICY's bridges, VALUE and LOCATE over its projections, SIGMA over (projection x tiering), "
      "HONEST over [bracket] required's values, WRITE over the marks",
      set(intake_terminal.ROUTE) == set(T["policy"]["bridge"]) and set(intake_terminal.VALUE) == set(intake_terminal.LOCATE) == set(T["policy"]["projection"])
      and set(intake_terminal.SIGMA) == set(itertools.product(T["policy"]["projection"], TIERINGS)) and set(intake_terminal.HONEST) == set(intake_feasible.COVERED)
      and set(intake_terminal.WRITE) == set(blind.Mark) and set(intake_terminal.SD) == {True, False} and set(intake_terminal.TIER) == {True, False}, "")
check("1. (1160 P6) POLICY declares the tier boundary Z as a finite positive number", isinstance(T["policy"]["policy"].get("tier_z"), float) and 0 < T["policy"]["policy"]["tier_z"] < float("inf"), "")
TERM = {n.value for n in ast.walk(ast.parse(Path(intake_terminal.__file__).read_text())) if isinstance(n, ast.Constant) and n.value in set(codes)}
check("1. (1160 P6) every reason code cc/intake_terminal.py names is a row of S10, and every row of S10 is named there", TERM == set(REASONS["S10"]), str(sorted(TERM ^ set(REASONS["S10"]))))
FM = T["format"]["fields"]
check("1. (1160 P4) the S1 tables are total: SLOW_IDS over the slow sources, SCALAR over the shapes, LANES over the origins, NEIGHBOUR over the "
      "identities, ROUTE over the admissibility classes, HAS_COLUMN over the uncertainty kinds; SEEN (S2) over the modes",
      set(intake_choices.SLOW_IDS) == set().union(*SLOWS.values()) and set(intake_choices.SCALAR) == set(FM["measured"]["fields"]["shape"]["values"])
      and all(set(intake_choices.LANES) == set(FM["source"]["variants"][k]["origin"]["values"]) for k in FM["source"]["variants"])
      and set(intake_choices.NEIGHBOUR) == set(FM["replicate"]["fields"]["identity"]["values"])
      and all(set(intake_choices.ROUTE) == set(FM["source"]["variants"][k]["admissibility"]["values"]) for k in FM["source"]["variants"])
      and set(intake_choices.HAS_COLUMN) == set(FM["measured"]["fields"]["uncertainty"]["variants"]) and set(intake_seal.SEEN) == set(FM["intake"]["fields"]["mode"]["values"]), "")
check("1. (1160 P4) PERMITTED is total over ({PROJECTION} | POLICY's bridges) x (RAW, DERIVED_OBSERVABLE, NO_LINK)",
      set(intake_choices.PERMITTED) == set(itertools.product({"PROJECTION"} | set(T["policy"]["bridge"]), ("RAW", "DERIVED_OBSERVABLE", "NO_LINK"))), "")
BLOCKS = set(F["selection"]["variants"]["LONG_TABLE"]["block"]["values"])
check("1. (1160 P2, A1) SELECTED (S1 SELECTION_EMPTY) is total over the layouts", set(intake_choices.SELECTED) == set(F["selection"]["variants"]), "")
check("1. (1160 P2) the LONG_TABLE blocks are EXACT and FAST_RESTART; BREAK is total over them, DIRECTED over the layouts, SWEEP over row_order",
      BLOCKS == {"EXACT", "FAST_RESTART"} and set(intake_census.BREAK) == BLOCKS and set(intake_choices.DIRECTED) == set(F["selection"]["variants"])
      and set(blind.SWEEP) == set(F["acquisition"]["fields"]["row_order"]["values"]), str(BLOCKS))
HEADS = F["reader"]["variants"]["table-curve-v1"]["header"]["variants"]
import intake_read  # noqa: E402
check("1. (1160 P2) the header kinds hold NAMES_UNITS_IN_NAMES; HEADER and NAMED are total over them, UNIT_SYNTAX over its unit_syntax values",
      "NAMES_UNITS_IN_NAMES" in HEADS and set(intake_read.HEADER) == set(intake_read.NAMED) == set(HEADS)
      and set(intake_names.UNIT_SYNTAX) == set(HEADS["NAMES_UNITS_IN_NAMES"]["unit_syntax"]["values"]), str(sorted(HEADS)))
IDENT = set(F["replicate"]["fields"]["identity"]["values"])
CONTROL = set(F["knobs"]["fields"]["fast"]["fields"]["control"]["values"])
KEYKINDS = F["replicate"]["fields"]["key"]["variants"]   # (1160 A33) the [replicate.key] kinds   # (1160 A17, T17.3) the [knobs.fast] control alphabet
check("1. (1160 P2; A17 T17.3) the replicate identities hold SAME_FAST_VALUE; POINTS is total over control x identity (1160 A17: was over the identities)"
      " and KEYED over the identities, DECLARED over (key kind, layout) (1160 A33: was REPLICATE over (layout, identity)); IDENTITIES is FORMAT's"
      " identity alphabet; POINTED (S1) is total over the controls",
      "SAME_FAST_VALUE" in IDENT and CONTROL == {"SET", "MEASURED"} and set(intake_census.POINTS) == set(itertools.product(CONTROL, IDENT))
      and set(intake_census.IDENTITIES) == IDENT and set(intake_census.KEYED) == IDENT
      and set(intake_census.DECLARED) == set(KEYKINDS) == set(intake_choices.KEYCOL) and all(set(r) == set(F["selection"]["variants"]) for r in intake_census.DECLARED.values())
      and all(callable(intake_census.KEYED[i](lay, k)) for i in IDENT for lay in F["selection"]["variants"] for k in KEYKINDS)
      and set(intake_choices.POINTED) == CONTROL, str(sorted(IDENT)))
check("1. every admit source of FORMAT.toml is a source the tables provide", all(src in T["admit"] for spec in [T["format"]["fields"]["interval"]["method"]] for src in spec["admit"]), "")

# ---- 2. the generated docs page
gen = subprocess.run([sys.executable, "docs/gen-intake.py"], capture_output=True, text=True, cwd=ROOT)
check("2. docs/gen-intake.py reproduces docs/INTAKE.md byte for byte", gen.returncode == 0 and gen.stdout == (ROOT / "docs" / "INTAKE.md").read_text(), gen.stderr[-300:])
exp = subprocess.run([str(ROOT / "bin" / "cc"), "intake", "explain"], capture_output=True, text=True, cwd=ROOT)
check("2. bin/cc intake explain prints docs/INTAKE.md", exp.returncode == 0 and exp.stdout == (ROOT / "docs" / "INTAKE.md").read_text(), exp.stderr[-300:])

# ---- 3. the verdict tables are total, every cell is reached or IMPOSSIBLE, and a stub never produces READY
product = set(itertools.product(intake_fold.Primary, blind.Mark))
check("3. ROBUSTNESS and IMPOSSIBLE partition (PRIMARY x Mark)", set(intake_fold.ROBUSTNESS) | set(intake_fold.IMPOSSIBLE) == product and not set(intake_fold.ROBUSTNESS) & set(intake_fold.IMPOSSIBLE), "")
check("3. PRIMARY is total over (R, U, C)", set(intake_fold.PRIMARY) == set(itertools.product((False, True), repeat=3)), "")
check("3. EXEC is total over (implemented, Upstream)", set(intake_fold.EXEC) == set(itertools.product((False, True), intake_fold.Upstream)), "")


@dataclasses.dataclass(frozen=True)
class Ev:
    conf: bool
    n_lanes: int = 2   # (1160 A5) the lanes declared, read by ROBUSTNESS's PASSED cells (cc/intake.py EXAMINED)

    def summary(self):
        return "planted"

    def confirmed(self):
        return self.conf


CHOICE = {"stub": None, "pass": lambda *a: blind.Pass(Ev(False)), "refuse": lambda *a: blind.Refuse(REASONS["S0"][0], "planted")}
SEAL_CHOICE = {"pass": CHOICE["pass"], "pass-confirmed": lambda *a: blind.Pass(Ev(True))}   # the ADVISORY seal is LIVE and never refuses (A3)
ROB = [s["id"] for s in ST if s["verdict"] == "ROBUSTNESS"][0]
ROB_CHOICE = {**CHOICE, "pass-one-lane": lambda *a: blind.Pass(Ev(False, 1))}   # (1160 A5) the ROBUSTNESS stage passed with one lane declared
hit_p, hit_r, stub_ready, body_on_stub, folds = set(), set(), [], [], 0
prim = [s["id"] for s in ST if s["verdict"] in ("PRIMARY", "HANDOFF")]   # (1160 P6) the HANDOFF stage counts toward PRIMARY
axes = [{SEAL: SEAL_CHOICE, ROB: ROB_CHOICE}.get(i, CHOICE) for i in IDS]   # (1160 P6) every stage, S10 among them (it was a stub: IDS[:-1])
hit_rv, refused_missing = set(), []
for combo in itertools.product(*[list(a) for a in axes]):
    pick = dict(zip(IDS, combo))
    rows = [{**s, "implemented": pick.get(s["id"], "stub") != "stub"} for s in ST]
    bodies = {i: {**CHOICE, **SEAL_CHOICE, **ROB_CHOICE}[c] for i, c in pick.items() if c != "stub"}
    t = {**T, "stages": {**T["stages"], "stage": rows}}
    out = intake_fold.fold(rows, bodies)
    p, r = intake_fold.verdicts(t, out)
    folds += 1
    marks = {out[i].mark for i in prim}
    hit_p.add((blind.Mark.REFUSED in marks, len(intake_fold._missing(prim, out)) > 0, out[SEAL].confirmed()))
    hit_r.add((p.kind, out[ROB].mark))
    hit_rv.add(r.kind)
    refused_missing += [pick] * (p.kind is intake_fold.Primary.PRIMARY_REFUSED_AT and p.missing != ())
    stub_ready += [pick] * (p.kind is intake_fold.Primary.PRIMARY_READY and any(not s["implemented"] for s in rows if s["id"] in prim))
    body_on_stub += [pick] * any(isinstance(out[s["id"]], intake_fold.Executed) for s in rows if not s["implemented"])
print(f"  {folds} folds of the stage table enumerated")
check("3. a stub never produces PRIMARY_READY (over every fold)", not stub_ready, str(stub_ready[:1]))
check("3. a stage with no body is never EXECUTED (over every fold)", not body_on_stub, str(body_on_stub[:1]))
check("3. every PRIMARY cell is reached", hit_p == set(intake_fold.PRIMARY), str(set(intake_fold.PRIMARY) - hit_p))
check("3. the reached ROBUSTNESS cells are exactly the table's, and no IMPOSSIBLE cell is reached", hit_r == set(intake_fold.ROBUSTNESS), str(hit_r ^ set(intake_fold.ROBUSTNESS)))
check("3. (1160 P6, E9) a PRIMARY_REFUSED_AT verdict lists no Missing stage (over every fold)", not refused_missing, str(refused_missing[:1]))
check("3. (1160 A5) every ROBUSTNESS verdict is reached, NOT_EXAMINED (one lane) and COMPLETE (two) among them", hit_rv == set(intake_fold.Robustness), str(set(intake_fold.Robustness) - hit_rv))
check("3. (1160 A5) EXAMINED is total over FORMAT's lane counts (1 and 2: PRIMARY | ALTERNATIVE)", set(intake_fold.EXAMINED) == set(range(1, 1 + len(FM["projection"]["fields"]["lane"]["values"]))), str(intake_fold.EXAMINED))

# ---- 4. the seal is advisory (plan 1139, A3): a status value, never a refusal; plan 1136's test 4 (Sealed-carrying signatures) is retired
for sid, sig in SIGNATURE.items():
    ann = [p.annotation for p in sig.parameters.values()]
    need = [EVIDENCE[n] for n in next(s for s in ST if s["id"] == sid)["needs"]]
    check(f"4. {sid}'s signature takes the evidence of its needs and no seal", ann == need and not any("Seal" in a.__name__ for a in ann), f"{ann} against {need}")
check("4. every registered data-stage body has its SIGNATURE row (1160 P5, P6: the S7-S9 and S10 bodies too)", all(inspect.signature(b) == SIGNATURE[k]
      for k, b in {**intake_bytes.bodies(T, EXAMPLE), **intake_census.bodies(T, EXAMPLE), **intake_feasible.bodies(T, EXAMPLE), **intake_terminal.bodies(T, EXAMPLE)}.items()), "")
with tempfile.TemporaryDirectory() as tmp:
    d = Path(tmp) / "decl"
    d.mkdir()
    for n in intake_seal.FILES:
        shutil.copyfile(EXAMPLE / n, d / n)
    decl = blind.format_stage((d / "intake.toml").read_text(), [], T).evidence
    status = lambda: intake_seal.verify(decl, d, T)
    check("4. S2 before any seal passes UNSEALED, unconfirmed", isinstance(status(), blind.Pass) and status().evidence.status is intake_seal.SealStatus.UNSEALED and not status().confirmed(), str(status()))
    raw = lambda t_ns, path, part="converted-from": json.dumps({"t_ns": t_ns, "route": "loader", "partition": part, "path": path}) + "\n"
    (d / "conversion-access.log").write_text(raw(1, "/r/a.csv") + raw(2, "/r/a.csv") + raw(2, "/r/b.csv") + raw(3, "/b/a.csv", "bank") + raw(2 ** 62, "/r/c.csv"))
    check("4. the ordering note before any seal is NOT_SEALED", intake_seal.ordering(d, T)[0] is intake_seal.Ordering.NOT_SEALED, "")
    check("4. (1160 A13) with no seal, no conversion read precedes one: the note says nothing of the conversion", "CONVERSION_READ" not in intake_seal.ordering(d, T)[1], intake_seal.ordering(d, T)[1])
    who = {"author": "test", "author_kind": "AI_DRAFT", "confirmed_by": ""}
    FX = {**T, "roots": {**T["roots"], "<p1118-bank>": str(FIXTURE)}}   # (1160 A20) the example's root named at the fixture (was: mint's universe argument)
    check("4. (1160 A20: was 'a universe that is not a directory') mint refuses a declared root that names no directory here",
          intake_seal.mint(decl, d, who, ROOT, {**T, "roots": {**T["roots"], "<p1118-bank>": str(Path(tmp) / "none")}}).reason == "UNIVERSE_ROOT_ABSENT", "")
    minted = intake_seal.mint(decl, d, who, ROOT, FX)
    check("4. mint seals the example against the fixture (63 names, sizes 0)", isinstance(minted, blind.Pass) and len(minted.evidence.record["universe"]["listing"]) == 63, str(minted)[:300])
    check("4. (1160 P1) the seal counts each part of the universe as a list: 61 selected, 1 excluded, 1 truth side (63 names, each once)",
          minted.evidence.record["universe"]["partition"] == {"selected": 61, "excluded": 1, "truth_side": 1}, str(minted.evidence.record["universe"].get("partition")))
    check("4. a second mint is ALREADY_SEALED", intake_seal.mint(decl, d, who, ROOT, FX).reason == "ALREADY_SEALED", "")
    check("4. S2 after the seal passes SEALED (unconfirmed: confirmed_by is empty)", status().evidence.status is intake_seal.SealStatus.SEALED and not status().confirmed(), str(status())[:200])
    check("4. the ordering note with no logged read is NO_DATA_READ_LOGGED", intake_seal.ordering(d, T)[0] is intake_seal.Ordering.NO_DATA_READ_LOGGED, "")
    check("4. (1160 A13) conversion-access.log's raw reads before the seal are counted by distinct file (2: a bank read and a read after the seal are not),"
          " as information: the ordering atom is unchanged", intake_seal.ordering(d, T)[1].endswith(" CONVERSION_READ_BEFORE_SEAL (2 files). " + T["stages"]["report"]["conversion_read"]),
          intake_seal.ordering(d, T)[1])
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
    ("(extra) another schema (6; 1160 A35: was 5, now the format; 1160 A17: was 4)", base.replace("schema = 5", "schema = 6", 1), "SCHEMA_UNSUPPORTED"),
    ("(1160) a v2 declaration (format v2 is history)", (ROOT / "declarations" / "dial1118-s1-v2" / "intake.toml").read_text(), "SCHEMA_UNSUPPORTED"),
    ("(1160 A17) a v3 declaration (format v3 is history)", (ROOT / "declarations" / "dial1118-s1-v3" / "intake.toml").read_text(), "SCHEMA_UNSUPPORTED"),
    ("(1160 A35) a v4 declaration (format v4 is history)", (ROOT / "declarations" / "dial1118-s1-v4" / "intake.toml").read_text(), "SCHEMA_UNSUPPORTED"),
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
    got = intake_choices.choices(blind.format_stage(text, [], T).evidence, T["policy"])
    check(f"5. S1 {name}: {want or 'PASS'}", {True: lambda: isinstance(got, blind.Pass), False: lambda: isinstance(got, blind.Refuse) and got.reason == want}[want is None](), str(got)[:300])
got = blind.format_stage(base, ["transducer.update[0]: planted"], T)
check("5. (extra) a transducer finding: refused TRANSDUCER_FILE_REFUSED", isinstance(got, blind.Refuse) and got.reason == "TRANSDUCER_FILE_REFUSED", str(got)[:200])

# ---- binding rule: enum names are Boolean formulas
ENUMS = [intake_fold.Execution, intake_fold.Cause, intake_fold.Upstream, intake_fold.Primary, intake_fold.Robustness, intake_fold.ReadsBytes, intake_fold.Scope, blind.Mark, intake_seal.SealStatus, intake_seal.Ordering]


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

# ---- blindness of S0 and S1: imports and calls of cc/intake_blind.py, cc/intake_names.py (plan 1160 P2: the classifier moved there) and
# cc/intake_choices.py (plan 1160 P4: S1 moved there)
ALLOWED = {blind: {"tomllib", "enum", "dataclasses", "typing", "intake_names"}, intake_names: {"re", "enum", "dataclasses"},
           intake_choices: {"dataclasses", "intake_blind", "intake_names"}}
for mod, allowed in ALLOWED.items():
    tree = ast.parse(Path(mod.__file__).read_text())
    mods = {a.name.split(".")[0] for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names} | {(n.module or "").split(".")[0] for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)}
    check(f"blind: {Path(mod.__file__).name} imports only {', '.join(sorted(allowed))}", mods <= allowed, str(mods))
    calls = {n.func.id for n in ast.walk(tree) if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)} & {"open", "exec", "eval", "compile", "__import__", "getattr", "globals"}
    check(f"blind: {Path(mod.__file__).name} calls no open, exec, eval, compile or __import__", not calls, str(calls))

# ---- plan 1164: the core split by invariant (Layout C); each module is checked for the one thing it must never do. Seen RED: `import os`
# added to cc/intake_fold.py (its imports check FAILS); `open("x")` added to cc/intake_say.py (its no-open check and the reader check FAIL);
# `def _x(): return Path("x")` added to cc/intake_evidence.py (its no-Path check FAILS); `def _x(): print("x")` added to
# cc/intake_census.py (the printer check FAILS); an empty cc/intake_data.py (the retired check FAILS).
import intake_say  # noqa: E402
FENCED = {intake_fold: {"enum", "dataclasses", "intake_blind"}, intake_evidence: {"enum", "dataclasses", "intake_blind"},
          intake_say: {"intake_blind", "intake_fold"}}


def called(tree):
    """The names a module calls: f(...) and x.f(...)."""
    return ({n.func.id for n in ast.walk(tree) if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)}
            | {n.func.attr for n in ast.walk(tree) if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)})


for mod, allowed in FENCED.items():
    tree = ast.parse(Path(mod.__file__).read_text())
    mods = {a.name.split(".")[0] for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names} | {(n.module or "").split(".")[0] for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)}
    check(f"split: {Path(mod.__file__).name} imports only {', '.join(sorted(allowed))}", mods <= allowed, str(mods))
    check(f"split: {Path(mod.__file__).name} calls no open, read_bytes or read_text", not called(tree) & {"open", "read_bytes", "read_text"}, str(called(tree) & {"open", "read_bytes", "read_text"}))
    named = {n.id for n in ast.walk(tree) if isinstance(n, ast.Name)} | {n.attr for n in ast.walk(tree) if isinstance(n, ast.Attribute)}
    check(f"split: {Path(mod.__file__).name} names no Path (it constructs none)", "Path" not in named, "")
INTAKE_MODULES = {f.stem: ast.parse(f.read_text()) for f in sorted((ROOT / "cc").glob("intake*.py"))}
READS = {"intake_bytes", "intake_seal",   # the two modules of the split that may open a file (the data bytes through the t23 loader; the seal files)
         "intake",   # declared exception: the tables and the declaration's text, never a data byte
         "intake_new",   # declared exception: the two templates and the synth MANIFEST
         "intake_convert", "intake_terminal", "intake_synth"}   # outside the split: the conversion, RESULT.json's code hash, the planted bank
readers = {m for m, tr in INTAKE_MODULES.items() if called(tr) & {"open", "read_bytes", "read_text"}}
check("split: open, read_bytes and read_text are called only in intake_bytes, intake_seal and the declared exceptions", readers <= READS, str(sorted(readers - READS)))
PRINTS = {"intake",   # the only module of the split that prints or exits
          "intake_convert", "intake_synth"}   # outside the split: they print already (convert and peek; the planted bank)
printers = {m for m, tr in INTAKE_MODULES.items() if called(tr) & {"print", "exit"}}
check("split: print and sys.exit are called only in intake.py and the declared modules outside the split", printers <= PRINTS, str(sorted(printers - PRINTS)))
check("split: cc/intake_data.py is retired (its parts are intake_evidence, intake_bytes and intake_census)", "intake_data" not in INTAKE_MODULES, "")

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
