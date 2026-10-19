"""intake - the intake pipeline (plan 1136): its tables, the execution of each stage, the run fold, the two verdict tables, the report and
`bin/cc intake explain | lint | seal | run`. Invariant: every stage, reason and sentence comes from intake/STAGES.toml; a stage with no
body is a STUB and a STUB is never a pass; a result is a value, never an exception; each dispatch below is a dict total over a named key."""
import enum
import json
import re
import tomllib
from dataclasses import dataclass
from pathlib import Path

import intake_blind as blind
import intake_data
import intake_seal
from intake_blind import Mark

ROOT = Path(__file__).resolve().parent.parent


class Execution(enum.Enum):
    """StageExecution. ATOMS: STUB | WITHHELD | EXECUTED. Axiom: exactly one holds for each stage of a run (STUB: no body is registered;
    WITHHELD: not run, after a refusal or for a need that did not pass; EXECUTED: the body returned a StageResult)."""
    STUB = frozenset({"STUB"})
    WITHHELD = frozenset({"WITHHELD"})
    EXECUTED = frozenset({"EXECUTED"})


class Cause(enum.Enum):
    """Why a stage was WITHHELD. ATOMS: AFTER_REFUSAL | INPUT_ABSENT. Axiom: exactly one holds for a withheld stage (an earlier stage refused;
    or none refused and a need did not pass)."""
    AFTER_REFUSAL = frozenset({"AFTER_REFUSAL"})
    INPUT_ABSENT = frozenset({"INPUT_ABSENT"})


class Upstream(enum.Enum):
    """The state a stage meets, in this order. ATOMS: REFUSED_EARLIER | SOME_ABSENT | ALL_PASSED. Axiom: exactly one holds (an earlier stage
    in run order refused; else some need did not pass; else every need passed)."""
    REFUSED_EARLIER = frozenset({"REFUSED_EARLIER"})
    SOME_ABSENT = frozenset({"SOME_ABSENT"})
    ALL_PASSED = frozenset({"ALL_PASSED"})


class Primary(enum.Enum):
    """The PRIMARY verdict over the PRIMARY stages. ATOMS: PRIMARY_READY | PRIMARY_INCOMPLETE | PRIMARY_REFUSED_AT. Axiom: exactly one holds
    (a stage refused; else a stage is not executed or no one confirmed the declaration; else every stage passed and it is confirmed)."""
    PRIMARY_READY = frozenset({"PRIMARY_READY"})
    PRIMARY_INCOMPLETE = frozenset({"PRIMARY_INCOMPLETE"})
    PRIMARY_REFUSED_AT = frozenset({"PRIMARY_REFUSED_AT"})


class Robustness(enum.Enum):
    """The ROBUSTNESS verdict over (PRIMARY, the ROBUSTNESS stage). ATOMS: ROBUSTNESS_COMPLETE | ROBUSTNESS_INCOMPLETE | ROBUSTNESS_REFUSED |
    ROBUSTNESS_WITHHELD. Axiom: exactly one holds (the second lane passed; is not executed; refused; or was withheld after a refusal)."""
    ROBUSTNESS_COMPLETE = frozenset({"ROBUSTNESS_COMPLETE"})
    ROBUSTNESS_INCOMPLETE = frozenset({"ROBUSTNESS_INCOMPLETE"})
    ROBUSTNESS_REFUSED = frozenset({"ROBUSTNESS_REFUSED"})
    ROBUSTNESS_WITHHELD = frozenset({"ROBUSTNESS_WITHHELD"})


class ReadsBytes(enum.Enum):
    """The data bytes a stage reads (STAGES.toml reads_bytes). ATOMS: NONE | FIRST_FILE | ALL_FILES. Axiom: exactly one holds per stage."""
    NONE = frozenset({"NONE"})
    FIRST_FILE = frozenset({"FIRST_FILE"})
    ALL_FILES = frozenset({"ALL_FILES"})


class Scope(enum.Enum):
    """The verdict a stage counts toward (STAGES.toml verdict). ATOMS: PRIMARY | ROBUSTNESS | HANDOFF | ADVISORY. Axiom: exactly one holds per
    stage (ADVISORY: the seal stage, outside every verdict; it reports the seal status and never refuses, amendment A3)."""
    PRIMARY = frozenset({"PRIMARY"})
    ROBUSTNESS = frozenset({"ROBUSTNESS"})
    HANDOFF = frozenset({"HANDOFF"})
    ADVISORY = frozenset({"ADVISORY"})


@dataclass(frozen=True)
class Stub:
    """Execution STUB. Invariant: it carries no result, so it can never be read as a pass."""
    atom = Execution.STUB
    mark = Mark.STUB

    def text(self, t):
        return "STUB. " + t["stages"]["report"]["stub"]

    def confirmed(self):
        return False


@dataclass(frozen=True)
class Withheld:
    """Execution WITHHELD. Invariant: `stage` is the refusing stage (AFTER_REFUSAL) or the first need that did not pass (INPUT_ABSENT)."""
    cause: Cause
    stage: str
    atom = Execution.WITHHELD

    @property
    def mark(self):
        return {Cause.AFTER_REFUSAL: Mark.WITHHELD_AFTER_REFUSAL, Cause.INPUT_ABSENT: Mark.WITHHELD_INPUT_ABSENT}[self.cause]

    def text(self, t):
        said = {Cause.AFTER_REFUSAL: "after_refusal", Cause.INPUT_ABSENT: "input_absent"}[self.cause]
        return f"WITHHELD {self.cause.name} ({self.stage}). " + t["stages"]["report"][said]

    def confirmed(self):
        return False


@dataclass(frozen=True)
class Executed:
    """Execution EXECUTED. Invariant: `result` is what the stage's registered body returned (Pass | Refuse)."""
    result: object
    atom = Execution.EXECUTED

    @property
    def mark(self):
        return self.result.mark

    def text(self, t):
        return "EXECUTED, " + self.result.text(t["sentences"])

    def confirmed(self):
        return self.result.confirmed()


UPSTREAM = {(True, True): Upstream.REFUSED_EARLIER, (True, False): Upstream.REFUSED_EARLIER,   # (an earlier stage refused, a need did not pass)
            (False, True): Upstream.SOME_ABSENT, (False, False): Upstream.ALL_PASSED}
EXEC = {   # design Table 1, total over (implemented, upstream); no cell takes a body for a stage with implemented = false
    (False, Upstream.ALL_PASSED): lambda s, bodies, out, refused, absent: Stub(),
    (False, Upstream.SOME_ABSENT): lambda s, bodies, out, refused, absent: Stub(),
    (False, Upstream.REFUSED_EARLIER): lambda s, bodies, out, refused, absent: Withheld(Cause.AFTER_REFUSAL, refused[0]),
    (True, Upstream.ALL_PASSED): lambda s, bodies, out, refused, absent: Executed(bodies[s["id"]](*[out[n].result.evidence for n in s["needs"]])),
    (True, Upstream.SOME_ABSENT): lambda s, bodies, out, refused, absent: Withheld(Cause.INPUT_ABSENT, absent[0]),
    (True, Upstream.REFUSED_EARLIER): lambda s, bodies, out, refused, absent: Withheld(Cause.AFTER_REFUSAL, refused[0]),
}


def fold(stages, bodies):
    """{stage id: execution}, in run order (table order). Invariant: a stage's body runs only in the cell (implemented, ALL_PASSED), and
    its arguments are the PASS evidence of its needs."""
    out = {}
    for s in stages:
        refused = [k for k, e in out.items() if e.mark is Mark.REFUSED]
        absent = [n for n in s["needs"] if out[n].mark is not Mark.PASSED]
        out[s["id"]] = EXEC[(s["implemented"], UPSTREAM[(len(refused) > 0, len(absent) > 0)])](s, bodies, out, refused, absent)
    return out


@dataclass(frozen=True)
class Verdict:
    """A PRIMARY or ROBUSTNESS verdict. Invariant: `missing` lists the stages not executed (and 'confirmation' when unconfirmed); `at` is the
    refusing stage of PRIMARY_REFUSED_AT or ROBUSTNESS_REFUSED, else ""."""
    kind: enum.Enum
    missing: tuple = ()
    at: str = ""


def _missing(ids, out):
    return tuple(i for i in ids if out[i].mark in (Mark.STUB, Mark.WITHHELD_INPUT_ABSENT))


def _refused(ids, out):
    return Verdict(Primary.PRIMARY_REFUSED_AT, _missing(ids[:ids.index(_first_refusal(ids, out))], out), _first_refusal(ids, out))


def _first_refusal(ids, out):
    return [i for i in ids if out[i].mark is Mark.REFUSED][0]


PRIMARY = {   # design Table 2 with amendment A2 Q6, total over (R some stage refused, U some stage not executed, C confirmed)
    (False, False, True): lambda ids, out: Verdict(Primary.PRIMARY_READY),
    (False, False, False): lambda ids, out: Verdict(Primary.PRIMARY_INCOMPLETE, ("confirmation",)),
    (False, True, True): lambda ids, out: Verdict(Primary.PRIMARY_INCOMPLETE, _missing(ids, out)),
    (False, True, False): lambda ids, out: Verdict(Primary.PRIMARY_INCOMPLETE, _missing(ids, out) + ("confirmation",)),
    (True, False, True): _refused, (True, False, False): _refused, (True, True, True): _refused, (True, True, False): _refused,
}
ROBUSTNESS = {   # design Table 3, the reachable cells of (PRIMARY, the ROBUSTNESS stage's mark)
    (Primary.PRIMARY_READY, Mark.STUB): Robustness.ROBUSTNESS_INCOMPLETE,
    (Primary.PRIMARY_READY, Mark.PASSED): Robustness.ROBUSTNESS_COMPLETE,
    (Primary.PRIMARY_READY, Mark.REFUSED): Robustness.ROBUSTNESS_REFUSED,
    (Primary.PRIMARY_INCOMPLETE, Mark.STUB): Robustness.ROBUSTNESS_INCOMPLETE,
    (Primary.PRIMARY_INCOMPLETE, Mark.WITHHELD_INPUT_ABSENT): Robustness.ROBUSTNESS_INCOMPLETE,
    (Primary.PRIMARY_INCOMPLETE, Mark.PASSED): Robustness.ROBUSTNESS_COMPLETE,
    (Primary.PRIMARY_INCOMPLETE, Mark.REFUSED): Robustness.ROBUSTNESS_REFUSED,
    (Primary.PRIMARY_REFUSED_AT, Mark.WITHHELD_AFTER_REFUSAL): Robustness.ROBUSTNESS_WITHHELD,
}
IMPOSSIBLE = {   # the other cells of the product; the fold never produces them (tests/test_intake.py enumerates every fold of the table)
    (Primary.PRIMARY_READY, Mark.WITHHELD_INPUT_ABSENT): "READY means every PRIMARY stage passed, and those include the stage's needs",
    (Primary.PRIMARY_READY, Mark.WITHHELD_AFTER_REFUSAL): "READY means no PRIMARY stage refused, and the stage runs right after them",
    (Primary.PRIMARY_INCOMPLETE, Mark.WITHHELD_AFTER_REFUSAL): "INCOMPLETE means no PRIMARY stage refused",
    (Primary.PRIMARY_REFUSED_AT, Mark.STUB): "after a refusal every later stage is WITHHELD(AFTER_REFUSAL), whether or not it has a body",
    (Primary.PRIMARY_REFUSED_AT, Mark.WITHHELD_INPUT_ABSENT): "after a refusal the upstream state is REFUSED_EARLIER, never SOME_ABSENT",
    (Primary.PRIMARY_REFUSED_AT, Mark.PASSED): "after a refusal no body runs",
    (Primary.PRIMARY_REFUSED_AT, Mark.REFUSED): "after a refusal no body runs",
}


def verdicts(t, out):
    """(PRIMARY Verdict, ROBUSTNESS Verdict) of a fold over the whole table."""
    ids = [s["id"] for s in t["stages"]["stage"] if s["verdict"] == "PRIMARY"]
    marks = {out[i].mark for i in ids}
    p = PRIMARY[(Mark.REFUSED in marks, len(_missing(ids, out)) > 0, out[t["stages"]["seal_stage"]].confirmed())](ids, out)
    rob = [s["id"] for s in t["stages"]["stage"] if s["verdict"] == "ROBUSTNESS"][0]
    r = ROBUSTNESS[(p.kind, out[rob].mark)]
    return p, Verdict(r, {True: (rob,), False: ()}[r is Robustness.ROBUSTNESS_INCOMPLETE], {True: rob, False: ""}[r is Robustness.ROBUSTNESS_REFUSED])


def tables(root=ROOT):
    """The intake's tables as plain values: STAGES, POLICY and FORMAT, cc.toml's alphabets and interval fields, and every reason's sentence."""
    load = {n: tomllib.loads((Path(root) / "intake" / f"{n.upper()}.toml").read_text()) for n in ("stages", "policy", "format")}
    cfg = tomllib.loads((Path(root) / "cc.toml").read_text())
    admit = {"policy.projection": load["policy"]["projection"], "policy.bridge": load["policy"]["bridge"],
             **{f"alphabet.{k}": v for k, v in cfg["alphabets"].items()}}
    sentences = {r["code"]: r["sentence"] for s in load["stages"]["stage"] for r in s["reason"]}
    roots = {k: str(Path(root) / v) for k, v in tomllib.loads((Path(root) / "intake" / "ROOTS.toml").read_text())["root"].items()}
    return {**load, "admit": admit, "interval_fields": cfg["interval_fields"], "sentences": sentences, "roots": roots}


def state(s):
    return {True: "LIVE", False: "STUB"}[s["implemented"]]


LIVE = {True: "live", False: "NOT LIVE"}


def not_live(t):
    """The reason rows no body can return yet (live = false in intake/STAGES.toml, plan-1139 E8), as a Markdown section that explain and every
    report carry: a refusal named there cannot be seen today, so its absence from a report says nothing."""
    rows = [f"- {s['id']} {r['code']}" for s in t["stages"]["stage"] for k in ("reason", "reader_reason") for r in blind.look(s, k, []) if not r["live"]]
    return ["## Reasons no body can return yet", "", "Each row below has live = false in intake/STAGES.toml: no body returns it today (a STUB stage's rows "
            "are never live), so a run cannot show it and its absence says nothing.", ""] + rows + [""]


def explain(t):
    """The stage table as Markdown: `bin/cc intake explain` prints it and docs/INTAKE.md is it, byte for byte (docs/gen-intake.py)."""
    st, po = t["stages"], t["policy"]
    out = [f"# The intake pipeline (stage table {st['version']}, policy {po['version']})", "",
           "Generated from intake/STAGES.toml and intake/POLICY.toml by `bin/cc intake explain` (docs/gen-intake.py); never edit it by hand.",
           "This is the intake's explain. `bin/cc explain <input> <point>` is a different command: it explains one point of a measured input.", "",
           "A declaration `declarations/<id>/` (intake.toml and the CC transducer.toml) goes through the stages below in order. "
           "Each stage is LIVE (it has a body) or a STUB (it has none, so nothing was checked; a stub is never a pass). "
           "An executed stage gives PASS or REFUSE with a named reason; after a refusal every later stage is WITHHELD.", "",
           "- **PRIMARY** verdict, over the PRIMARY stages: PRIMARY_REFUSED_AT when one refused; else PRIMARY_INCOMPLETE when one is not "
           "executed or no seal with a non-empty confirmed_by holds the declaration now; else PRIMARY_READY.",
           "- **ROBUSTNESS** verdict, over the ROBUSTNESS stage: ROBUSTNESS_COMPLETE, ROBUSTNESS_INCOMPLETE, ROBUSTNESS_REFUSED, or "
           "ROBUSTNESS_WITHHELD after a PRIMARY refusal.",
           "- The HANDOFF stage is outside both verdicts.",
           "- The ADVISORY stage (the seal) is outside every verdict. It never refuses: every report carries its seal status, SEALED, UNSEALED or "
           "SEALED_THEN_EDITED, and an ordering note.", "",
           f"**The seal.** {st['report']['seal_claim']}", "", "| id | name | state | reads data bytes | needs | verdict |", "|---|---|---|---|---|---|"]
    out += [f"| {s['id']} | {s['name']} | {state(s)} | {s['reads_bytes']} | {', '.join(s['needs']) or '-'} | {s['verdict']} |" for s in st["stage"]]
    for s in st["stage"]:
        out += ["", f"## {s['id']} {s['name']} ({state(s)})", "", s["purpose"], "", "| reason | live | what it means |", "|---|---|---|"]
        out += [f"| {r['code']} | {LIVE[r['live']]} | {r['sentence']} |" for r in s["reason"]]
        out += {True: lambda: ["", "| reader reason (READER_REFUSED) | live | what it means |", "|---|---|---|"] + [f"| {r['code']} | {LIVE[r['live']]} | {r['sentence']} |" for r in s["reader_reason"]],
                False: lambda: []}["reader_reason" in s]()
        out += {True: lambda: ["", "| seal status | what it means |", "|---|---|"] + [f"| {r['code']} | {r['sentence']} |" for r in s["status"]], False: lambda: []}["status" in s]()
    out += ["", f"## Policy ({po['status']}, {po['version']})", "", po["evidence_note"], ""]
    for link in ("projection", "bridge"):
        out += [f"- {link} **{k}**: " + "; ".join(f"{f} = {v}" for f, v in row.items()) for k, row in po[link].items()]
    out += [f"- policy: " + "; ".join(f"{k} = {v}" for k, v in po["policy"].items()), ""] + not_live(t) + [
            "## What no stage can see", ""] + [f"- {u}" for u in st["report"]["unenforced"]]
    return "\n".join(out) + "\n"


def bodies(t, d, text, findings):
    """The registered bodies of one run: S0 FORMAT and S2 SEAL (verify, advisory), plus intake_data.bodies (S3, S4, S5). Invariant: its keys are exactly the
    stages whose implemented = true (tests/test_intake.py)."""
    return {"S0": lambda: blind.format_stage(text, findings, t), "S2": lambda declaration: intake_seal.verify(declaration, d, t), **intake_data.bodies(t, d)}


def report(t, ident, out, note):
    """intake-report.md of a run: the verdicts, the seal status and the ordering note (`note`, an (Ordering, sentence) read after the run), then
    every stage in plain sentences, then the seal claim and what no stage can see."""
    seal = t["stages"]["seal_stage"]
    p, r = verdicts(t, out)
    names = {s["id"]: s["name"] for s in t["stages"]["stage"]}
    words = lambda v: ", ".join(f"{m} {blind.look(names, m, '')}".strip() for m in v.missing) or "none"
    handoff = [s["id"] for s in t["stages"]["stage"] if s["verdict"] == "HANDOFF"][0]
    lines = [f"# Intake report: {ident}", "", f"Written by `bin/cc intake run {ident}`. Stage table {t['stages']['version']}, policy {t['policy']['version']}.", "",
             f"- **Mode** (the declarer's sealed statement of what they had seen): {out['S0'].result.mode()}",
             f"- **PRIMARY verdict: {p.kind.name}**" + {True: f" at {p.at}", False: ""}[p.at != ""] + f". Missing: {words(p)}.",
             f"- **ROBUSTNESS verdict: {r.kind.name}**" + {True: f" at {r.at}", False: ""}[r.at != ""] + f". Missing: {words(r)}.",
             f"- **{handoff} {names[handoff]}** (outside both verdicts): {out[handoff].atom.name}.",
             "- **Seal status** (advisory; sealing is recommended and not enforced): " + {True: lambda: out[seal].result.evidence.summary(),
                                                                                           False: lambda: "not reported: " + out[seal].text(t)}[out[seal].mark is Mark.PASSED](),
             f"- **Ordering** (information, never a refusal): {note[0].name}. {note[1]}"]
    lines += {True: [f"- **confirmation**: {t['stages']['report']['confirmation']}"], False: []}["confirmation" in p.missing]
    lines += ["",
             "| stage | name | state | reads data bytes | execution |", "|---|---|---|---|---|"]
    lines += [f"| {s['id']} | {s['name']} | {state(s)} | {s['reads_bytes']} | {out[s['id']].atom.name} |" for s in t["stages"]["stage"]]
    lines += [""] + [f"- **{s['id']} {s['name']}** ({state(s)}): {out[s['id']].text(t)}" for s in t["stages"]["stage"]]
    lines += ["", "## What the seal proves", "", t["stages"]["report"]["seal_claim"], ""] + not_live(t) + [
              "## What no stage can see", ""] + [f"- {u}" for u in t["stages"]["report"]["unenforced"]]
    return "\n".join(lines) + "\n"


def closure(t, sid):
    """The transitive needs of a stage."""
    row = {s["id"]: s for s in t["stages"]["stage"]}
    return {n for m in row[sid]["needs"] for n in {m} | closure(t, m)}


def before_data(t):
    """The stages of lint and seal: they read no data byte, no stage in their transitive needs reads one, and they are not the ADVISORY seal."""
    reads = {s["id"] for s in t["stages"]["stage"] if s["reads_bytes"] != "NONE"}
    return [s for s in t["stages"]["stage"] if s["verdict"] != "ADVISORY" and s["id"] not in reads and not closure(t, s["id"]) & reads]


def _flag(args, name):
    """The value after `name`, or "" when the flag is absent (a usage table below refuses a required flag that is "")."""
    return {True: lambda: args[args.index(name) + 1], False: lambda: ""}[name in args and args.index(name) + 1 < len(args)]()


def _findings(root, d, ident):
    """The CC transducer check on the declaration's transducer.toml, as text lines (plumbing: it reads the toolset's git for the update pin)."""
    import schema
    import transducer
    data, bad = schema.load(d / "transducer.toml", root)
    found = {True: lambda: bad, False: lambda: transducer.chk_transducer(f"declarations/{ident}/transducer.toml", data, schema.Ctx(root), ident)}[data is None]()
    return [f"{f.loc}: {f.msg} (Next: {f.nxt})" for f in found]


def _go(root, ident, pick):
    t, d = tables(root), Path(root) / "declarations" / ident
    text = {True: lambda: (d / "intake.toml").read_text(), False: lambda: ""}[(d / "intake.toml").is_file()]()
    return t, d, fold(pick(t), bodies(t, d, text, _findings(root, d, ident)))


def lint(root, ident, args):
    t, d, out = _go(root, ident, before_data)
    print("\n".join(f"{k} {e.text(t)}" for k, e in out.items()))
    return {True: 1, False: 0}[any(e.mark is Mark.REFUSED for e in out.values())]


def _mint(root, ident, args, t, d, out):
    who = {"author": _flag(args, "--author"), "author_kind": intake_seal.AUTHOR_KIND[_flag(args, "--as")], "confirmed_by": _flag(args, "--confirmed-by")}
    res = intake_seal.mint(out["S0"].result.evidence, d, _flag(args, "--universe"), who, root, t)
    print(f"seal {ident}: " + res.text(t["sentences"]))
    return {Mark.PASSED: 0, Mark.REFUSED: 1}[res.mark]


def seal(root, ident, args):
    usage = [u for ok, u in ((_flag(args, "--author") != "", "--author NAME"), (_flag(args, "--as") in intake_seal.AUTHOR_KIND, "--as human|ai-draft"),
                             ((_flag(args, "--confirmed-by") != "") != ("--unconfirmed" in args), "exactly one of --confirmed-by NAME | --unconfirmed")) if not ok]
    return {True: lambda: _usage(f"seal needs {'; '.join(usage)}"), False: lambda: _seal(root, ident, args)}[len(usage) > 0]()


def _seal(root, ident, args):
    t, d, out = _go(root, ident, before_data)
    print("\n".join(f"{k} {e.text(t)}" for k, e in out.items()))
    refused = any(e.mark is Mark.REFUSED for e in out.values())
    return {True: lambda: 1, False: lambda: _mint(root, ident, args, t, d, out)}[refused]()


def run(root, ident, args):
    t, d, out = _go(root, ident, lambda t: t["stages"]["stage"])
    text = report(t, ident, out, intake_seal.ordering(d, t))
    (d / "intake-report.md").write_text(text)
    print(text, end="")
    return {Primary.PRIMARY_READY: 0, Primary.PRIMARY_INCOMPLETE: 0, Primary.PRIMARY_REFUSED_AT: 1}[verdicts(t, out)[0].kind]


def fill(text, values, dropped=frozenset()):
    """The template text with each `key = "TODO"` line of a [section] whose "section.key" is a key of `values` set to that TOML value, and
    without each line whose "section.key" is in `dropped`, or whose section is (its [section] line, its "# [section]:" comment line and every
    line under it): the fields of a VARIANT row that was not chosen."""
    out, sec = [], ""
    for ln in text.splitlines():
        sec, m, head = {True: ln.strip("[] "), False: sec}[ln.startswith("[")], re.match(r'(\w+) = "TODO"(.*)', ln), re.match(r"# \[([\w.]+)\]:", ln)
        about = {True: lambda: [head[1]], False: lambda: [sec] + [f"{sec}.{x[1]}" for x in [m] if x is not None]}[head is not None]()
        kept = {True: lambda: [], False: lambda: [{True: lambda: f"{m[1]} = {values[sec + '.' + m[1]]}{m[2]}", False: lambda: ln}[m is not None and f"{sec}.{m[1]}" in values]()]}
        out += kept[any(n in dropped for n in about)]()
    return "\n".join(out) + "\n"


def _write_new(root, d, ident, values, dropped, trans):
    d.mkdir(parents=True)
    (d / "intake.toml").write_text(fill((Path(root) / "intake" / "TEMPLATE.intake.toml.in").read_text().replace("<ID>", ident), values, dropped))
    (d / "transducer.toml").write_text(trans)
    todo = [f"  declarations/{ident}/{n}:{i}: {ln}" for n in ("intake.toml", "transducer.toml") for i, ln in enumerate((d / n).read_text().splitlines(), 1) if '"TODO"' in ln]
    print(f"wrote declarations/{ident}/intake.toml and transducer.toml; {len(todo)} TODO lines remain (yours to choose):\n" + "\n".join(todo)
          + f"\n  Next: replace each TODO (docs/INTAKE-QUICKSTART.md shows a filled example), then bin/cc intake lint {ident}")
    return 0


def _from_synth(root, d, ident, sid, synth):
    import intake_synth   # test infrastructure: it knows the MANIFEST it wrote
    return _write_new(root, d, ident, *intake_synth.declare(json.loads(synth.read_text()), ident, sid))


def new(root, ident, sid):
    """bin/cc new intake <id> [--from-synth <sid>]: declarations/<id>/ from the committed templates; with --from-synth, the synth MANIFEST's
    metadata filled in (intake_synth.declare) and every choice left TODO. Invariant: never overwrites; a refusal is a usage line with a Next."""
    d, synth = Path(root) / "declarations" / ident, Path(root) / tomllib.loads((Path(root) / "intake" / "ROOTS.toml").read_text())["root"]["<intake-synth>"] / sid / "MANIFEST.json"
    blank = lambda: _write_new(root, d, ident, {}, frozenset(), (Path(root) / "inputs" / "TEMPLATE.transducer.toml.in").read_text().replace("<ID>", ident))
    filled = lambda: _from_synth(root, d, ident, sid, synth)
    usage = [u for ok, u in ((re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]*", ident) is not None, f"an id (letters, digits, _ . -), not '{ident}'"),
                             (not d.exists(), f"declarations/{ident} exists; a declaration is never overwritten (choose another id)"),
                             (sid == "" or synth.is_file(), f"no synthetic bank '{sid}' (run bin/cc intake synth {sid} --seed N first)")) if not ok]
    return {True: lambda: print(f"bin/cc new intake: refused, {'; '.join(usage)}\n  Next: bin/cc new intake <id> [--from-synth <synth-id>]") or 1,
            False: {True: blank, False: filled}[sid == ""]}[len(usage) > 0]()


def _usage(why):
    print(f"bin/cc intake: {why}\n  usage: bin/cc intake explain | synth <id> --seed N [--curves K] [--out DIR] | lint <id> | seal <id> --universe DIR --author NAME --as human|ai-draft "
          "(--confirmed-by NAME | --unconfirmed) | run <id>\n  Next: bin/cc intake explain")
    return 1


def _with_id(f):
    """A subcommand that names a declaration: it runs only when declarations/<id>/ is a directory."""
    return lambda root, a: {True: lambda: f(root, a[0], a[1:]),
                            False: lambda: _usage("name a declaration: declarations/<id>/ must be a directory")}[len(a) > 0 and (Path(root) / "declarations" / a[0]).is_dir()]()


def synth(root, args):
    """bin/cc intake synth: the planted bank generator (cc/intake_synth.py, test infrastructure), imported here only: no stage imports it."""
    import intake_synth
    return intake_synth.cli(root, args)


INTAKE = {"explain": lambda root, a: print(explain(tables(root)), end="") or 0, "lint": _with_id(lint), "seal": _with_id(seal), "run": _with_id(run),
          "synth": synth}


def cli(root, args):
    """bin/cc intake <sub>: a total lookup over the subcommands of INTAKE; any other word is a usage refusal."""
    sub = {True: lambda: args[0], False: lambda: ""}[len(args) > 0]()
    return blind.look(INTAKE, sub, lambda root, a: _usage(f"unknown subcommand '{sub}'"))(root, args[1:])
