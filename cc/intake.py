"""intake - the intake pipeline: its tables, the execution of each stage, the run fold, the two verdict tables, the report and
`bin/cc intake explain | lint | seal | run`. Invariant: every stage, reason and sentence comes from intake/STAGES.toml; a stage with no
body is a STUB and a STUB is never a pass; a result is a value, never an exception; each dispatch below is a dict total over a named key."""
import enum
import tomllib
from dataclasses import dataclass
from pathlib import Path

import intake_blind as blind
import intake_choices
import intake_data
import intake_feasible
import intake_terminal
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
    """The ROBUSTNESS verdict over (PRIMARY, the ROBUSTNESS stage). ATOMS: ROBUSTNESS_COMPLETE | ROBUSTNESS_NOT_EXAMINED | ROBUSTNESS_INCOMPLETE | ROBUSTNESS_REFUSED |
    ROBUSTNESS_WITHHELD. Axiom: exactly one holds (the second lane passed; it passed with one lane, nothing examined; is not executed; refused; withheld)."""
    ROBUSTNESS_COMPLETE = frozenset({"ROBUSTNESS_COMPLETE"})
    ROBUSTNESS_NOT_EXAMINED = frozenset({"ROBUSTNESS_NOT_EXAMINED"})
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
    stage (ADVISORY: the seal stage, outside every verdict; it reports the seal status and never refuses)."""
    PRIMARY = frozenset({"PRIMARY"})
    ROBUSTNESS = frozenset({"ROBUSTNESS"})
    HANDOFF = frozenset({"HANDOFF"})
    ADVISORY = frozenset({"ADVISORY"})


def scoped(t, *scopes):
    """The ids of the stages whose verdict (STAGES.toml, an atom of Scope) is one of `scopes`, in table order."""
    return [s["id"] for s in t["stages"]["stage"] if Scope[s["verdict"]] in scopes]


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


def _missing(ids, out):   # WITHHELD_AFTER_REFUSAL too: a stage withheld after a refusal was not executed
    return tuple(i for i in ids if out[i].mark in (Mark.STUB, Mark.WITHHELD_INPUT_ABSENT, Mark.WITHHELD_AFTER_REFUSAL))


def _refused(ids, out):   # no Missing list on a refusal (it would name the stubs before the refusing stage)
    return Verdict(Primary.PRIMARY_REFUSED_AT, (), _first_refusal(ids, out))


def _first_refusal(ids, out):
    return [i for i in ids if out[i].mark is Mark.REFUSED][0]


PRIMARY = {   # design Table 2, total over (R some stage refused, U some stage not executed, C confirmed)
    (False, False, True): lambda ids, out: Verdict(Primary.PRIMARY_READY),
    (False, False, False): lambda ids, out: Verdict(Primary.PRIMARY_INCOMPLETE, ("confirmation",)),
    (False, True, True): lambda ids, out: Verdict(Primary.PRIMARY_INCOMPLETE, _missing(ids, out)),
    (False, True, False): lambda ids, out: Verdict(Primary.PRIMARY_INCOMPLETE, _missing(ids, out) + ("confirmation",)),
    (True, False, True): _refused, (True, False, False): _refused, (True, True, True): _refused, (True, True, False): _refused,
}
EXAMINED = {1: Robustness.ROBUSTNESS_NOT_EXAMINED, 2: Robustness.ROBUSTNESS_COMPLETE}   # a passed ROBUSTNESS stage's lane count (FORMAT: PRIMARY | ALTERNATIVE)
ROBUSTNESS = {   # design Table 3, the reachable cells of (PRIMARY, the ROBUSTNESS stage's mark) -> (its execution -> the verdict)
    (Primary.PRIMARY_READY, Mark.STUB): lambda e: Robustness.ROBUSTNESS_INCOMPLETE,
    (Primary.PRIMARY_READY, Mark.PASSED): lambda e: EXAMINED[e.result.evidence.n_lanes],
    (Primary.PRIMARY_READY, Mark.REFUSED): lambda e: Robustness.ROBUSTNESS_REFUSED,   # it runs after the HANDOFF stage
    (Primary.PRIMARY_INCOMPLETE, Mark.STUB): lambda e: Robustness.ROBUSTNESS_INCOMPLETE,
    (Primary.PRIMARY_INCOMPLETE, Mark.WITHHELD_INPUT_ABSENT): lambda e: Robustness.ROBUSTNESS_INCOMPLETE,
    (Primary.PRIMARY_INCOMPLETE, Mark.PASSED): lambda e: EXAMINED[e.result.evidence.n_lanes],
    (Primary.PRIMARY_INCOMPLETE, Mark.REFUSED): lambda e: Robustness.ROBUSTNESS_REFUSED,
    (Primary.PRIMARY_REFUSED_AT, Mark.WITHHELD_AFTER_REFUSAL): lambda e: Robustness.ROBUSTNESS_WITHHELD,
}
IMPOSSIBLE = {   # the other cells of the product; the fold never produces them (tests/test_intake.py enumerates every fold of the table)
    (Primary.PRIMARY_READY, Mark.WITHHELD_INPUT_ABSENT): "READY means every PRIMARY stage passed, and those include the stage's needs",
    (Primary.PRIMARY_READY, Mark.WITHHELD_AFTER_REFUSAL): "READY means no PRIMARY stage refused, and the seal stage never refuses",
    (Primary.PRIMARY_INCOMPLETE, Mark.WITHHELD_AFTER_REFUSAL): "INCOMPLETE means no PRIMARY stage refused, and the seal stage never refuses",
    (Primary.PRIMARY_REFUSED_AT, Mark.WITHHELD_INPUT_ABSENT): "after a refusal the upstream state is REFUSED_EARLIER, never SOME_ABSENT",
    (Primary.PRIMARY_REFUSED_AT, Mark.STUB): "plan 1160 A9: the stage runs after every PRIMARY and HANDOFF stage, so a PRIMARY refusal is earlier and a stub after it is WITHHELD",
    (Primary.PRIMARY_REFUSED_AT, Mark.PASSED): "plan 1160 A9: as above; after the PRIMARY refusal no body runs",
    (Primary.PRIMARY_REFUSED_AT, Mark.REFUSED): "plan 1160 A9: as above; after the PRIMARY refusal no body runs, so this stage cannot refuse",
}


def verdicts(t, out):
    """(PRIMARY Verdict, ROBUSTNESS Verdict) of a fold over the whole table."""
    ids = scoped(t, Scope.PRIMARY, Scope.HANDOFF)   # the HANDOFF stage (the terminal) counts toward PRIMARY
    marks = {out[i].mark for i in ids}
    p = PRIMARY[(Mark.REFUSED in marks, len(_missing(ids, out)) > 0, out[t["stages"]["seal_stage"]].confirmed())](ids, out)
    rob = scoped(t, Scope.ROBUSTNESS)[0]
    r = ROBUSTNESS[(p.kind, out[rob].mark)](out[rob])
    return p, Verdict(r, {True: (rob,), False: ()}[r is Robustness.ROBUSTNESS_INCOMPLETE], {True: rob, False: ""}[r is Robustness.ROBUSTNESS_REFUSED])


def tables(root=ROOT):
    """The intake's tables as plain values: STAGES, POLICY and FORMAT, cc.toml's alphabets and interval fields (with FORMAT's own), every sentence."""
    load = {n: tomllib.loads((Path(root) / "intake" / f"{n.upper()}.toml").read_text()) for n in ("stages", "policy", "format")}
    cfg = tomllib.loads((Path(root) / "cc.toml").read_text())
    admit = {"policy.projection": load["policy"]["projection"], "policy.bridge": load["policy"]["bridge"],
             **{f"alphabet.{k}": v for k, v in cfg["alphabets"].items()}}
    sentences = {r["code"]: r["sentence"] for s in load["stages"]["stage"] for r in s["reason"]}
    roots = {k: str(Path(root) / Path(v).expanduser()) for k, v in tomllib.loads((Path(root) / "intake" / "ROOTS.toml").read_text())["root"].items()}
    fields = {**cfg["interval_fields"], **load["format"]["interval_fields"]}   # the intake's methods STATED and NONE (FORMAT.toml)
    return {**load, "admit": admit, "interval_fields": fields, "sentences": sentences, "roots": roots}


def state(s):
    return {True: "LIVE", False: "STUB"}[s["implemented"]]


LIVE = {True: "live", False: "NOT LIVE"}


def not_live(t):
    """The reason rows no body can return yet (live = false in intake/STAGES.toml), as a Markdown section that explain and every
    report carry: a refusal named there cannot be seen today, so its absence from a report says nothing."""
    rows = [f"- {s['id']} {r['code']}" for s in t["stages"]["stage"] for k in ("reason", "reader_reason") for r in blind.look(s, k, []) if not r["live"]]
    return t["stages"]["report"]["not_live"] + (rows or [t["stages"]["report"]["all_live"]]) + [""]


def unseen(t):
    """The tail of explain and of every report: the reason rows no body can return yet, then what no stage can see."""
    return not_live(t) + ["## What no stage can see", ""] + [f"- {u}" for u in t["stages"]["report"]["unenforced"]]


def explain(t):
    """The stage table as Markdown: `bin/cc intake explain` prints it and docs/INTAKE.md is it, byte for byte (docs/gen-intake.py)."""
    st, po = t["stages"], t["policy"]
    out = [f"# The intake pipeline (stage table {st['version']}, policy {po['version']})", "",
           *st["report"]["explain"],
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
    out += [f"- policy: " + "; ".join(f"{k} = {v}" for k, v in po["policy"].items()), ""] + unseen(t)
    return "\n".join(out) + "\n"


def bodies(t, d, text, findings):
    """The registered bodies of one run: S0 FORMAT, S1 CHOICES (cc/intake_choices.py), S2 SEAL (verify, advisory), plus
    intake_data.bodies (the data stages with a body) and intake_feasible.bodies (S7, S8, S9) and intake_terminal.bodies (S10). Invariant: its keys are exactly the stages whose implemented = true (tests/test_intake.py)."""
    return {"S0": lambda: blind.format_stage(text, findings, t), "S1": lambda declaration: intake_choices.choices(declaration, t["policy"]),
            "S2": lambda declaration: intake_seal.verify(declaration, d, t),
            **intake_data.bodies(t, d), **intake_feasible.bodies(t, d), **intake_terminal.bodies(t, d)}


def report(t, ident, out, note):
    """intake-report.md of a run: the verdicts, the seal status and the ordering note (`note`, an (Ordering, sentence) read after the run), then
    every stage in plain sentences, then the seal claim and what no stage can see."""
    seal = t["stages"]["seal_stage"]
    p, r = verdicts(t, out)
    names = {s["id"]: s["name"] for s in t["stages"]["stage"]}
    words = lambda v: ", ".join(f"{m} {blind.look(names, m, '')}".strip() for m in v.missing) or "none"
    handoff = scoped(t, Scope.HANDOFF)[0]
    lines = [f"# Intake report: {ident}", "", f"Written by `bin/cc intake run {ident}`. Stage table {t['stages']['version']}, policy {t['policy']['version']}.", "",
             f"- **Mode** (the declarer's sealed statement of what they had seen): {out['S0'].result.mode()}",
             f"- **PRIMARY verdict: {p.kind.name}**" + {True: f" at {p.at}", False: ""}[p.at != ""] + f". Missing: {words(p)}.",
             f"- **ROBUSTNESS verdict: {r.kind.name}**" + {True: f" at {r.at}", False: ""}[r.at != ""] + f". Missing: {words(r)}.",
             f"- **{handoff} {names[handoff]}** (the terminal; it counts toward PRIMARY): {out[handoff].atom.name}.",
             "- **Seal status** (advisory; sealing is recommended and not enforced): " + {True: lambda: out[seal].result.evidence.summary(),
                                                                                           False: lambda: "not reported: " + out[seal].text(t)}[out[seal].mark is Mark.PASSED](),
             f"- **Ordering** (information, never a refusal): {note[0].name}. {note[1]}"]
    lines += {True: [f"- **confirmation**: {t['stages']['report']['confirmation']}"], False: []}["confirmation" in p.missing]
    lines += ["",
             "| stage | name | state | reads data bytes | execution |", "|---|---|---|---|---|"]
    lines += [f"| {s['id']} | {s['name']} | {state(s)} | {s['reads_bytes']} | {out[s['id']].atom.name} |" for s in t["stages"]["stage"]]
    lines += [""] + [f"- **{s['id']} {s['name']}** ({state(s)}): {out[s['id']].text(t)}" for s in t["stages"]["stage"]]
    census = [s["id"] for s in t["stages"]["stage"] if s["name"] == "CENSUS"][0]   # the census section: only when the census passed
    lines += {True: lambda: ["", "## Census", "", f"The curves of {census} CENSUS, by ordinal and file name (never by slow value):", ""] + out[census].result.evidence.listing(),
              False: lambda: []}[out[census].mark is Mark.PASSED]()
    lines += ["", "## What the seal proves", "", t["stages"]["report"]["seal_claim"], ""] + unseen(t)
    return "\n".join(lines) + "\n"


def closure(t, sid):
    """The transitive needs of a stage."""
    row = {s["id"]: s for s in t["stages"]["stage"]}
    return {n for m in row[sid]["needs"] for n in {m} | closure(t, m)}


def before_data(t):
    """The stages of lint and seal: they read no data byte, no stage in their transitive needs reads one, and they are not the ADVISORY seal."""
    reads = {s["id"] for s in t["stages"]["stage"] if ReadsBytes[s["reads_bytes"]] is not ReadsBytes.NONE}
    return [s for s in t["stages"]["stage"] if Scope[s["verdict"]] is not Scope.ADVISORY and s["id"] not in reads and not closure(t, s["id"]) & reads]


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


def _before(root, ident):
    """(tables, declaration dir, fold, refused) of the stages before data (lint and seal), each execution printed."""
    t, d, out = _go(root, ident, before_data)
    print("\n".join(f"{k} {e.text(t)}" for k, e in out.items()))
    return t, d, out, any(e.mark is Mark.REFUSED for e in out.values())


def lint(root, ident, args):
    return {True: 1, False: 0}[_before(root, ident)[3]]


def _mint(root, ident, args, t, d, out):
    who = {"author": blind.flag(args, "--author", ""), "author_kind": intake_seal.AUTHOR_KIND[blind.flag(args, "--as", "")], "confirmed_by": blind.flag(args, "--confirmed-by", "")}
    res = intake_seal.mint(out["S0"].result.evidence, d, blind.flag(args, "--universe", ""), who, root, t)
    print(f"seal {ident}: " + res.text(t["sentences"]))
    return {Mark.PASSED: 0, Mark.REFUSED: 1}[res.mark]


def seal(root, ident, args):
    usage = [u for ok, u in ((blind.flag(args, "--author", "") != "", "--author NAME"), (blind.flag(args, "--as", "") in intake_seal.AUTHOR_KIND, "--as human|ai-draft"),
                             ((blind.flag(args, "--confirmed-by", "") != "") != ("--unconfirmed" in args), "exactly one of --confirmed-by NAME | --unconfirmed")) if not ok]
    return {True: lambda: _usage(f"seal needs {'; '.join(usage)}"), False: lambda: _seal(root, ident, args)}[len(usage) > 0]()


def _seal(root, ident, args):
    t, d, out, refused = _before(root, ident)
    return {True: lambda: 1, False: lambda: _mint(root, ident, args, t, d, out)}[refused]()


def run(root, ident, args):
    t, d, out = _go(root, ident, lambda t: t["stages"]["stage"])
    text = report(t, ident, out, intake_seal.ordering(d, t))
    (d / "intake-report.md").write_text(text)
    intake_terminal.write(root, t, d, out, verdicts(t, out)[0].kind.name)   # RESULT.json when S10 passed, else removed
    print(text, end="")
    return {Primary.PRIMARY_READY: 0, Primary.PRIMARY_INCOMPLETE: 0, Primary.PRIMARY_REFUSED_AT: 1}[verdicts(t, out)[0].kind]


def _usage(why):
    print(f"bin/cc intake: {why}\n  usage: bin/cc intake explain | synth <id> --seed N [--curves K] [--out DIR] | lint <id> | seal <id> --universe DIR --author NAME --as human|ai-draft "
          "(--confirmed-by NAME | --unconfirmed) | run <id> | convert <id> [--verify] | peek <id> <file> [--sheet NAME] [--depth N]\n  Next: bin/cc intake explain")
    return 1


def _with_id(f):
    """A subcommand that names a declaration: it runs only when declarations/<id>/ is a directory."""
    return lambda root, a: {True: lambda: f(root, a[0], a[1:]),
                            False: lambda: _usage("name a declaration: declarations/<id>/ must be a directory")}[len(a) > 0 and (Path(root) / "declarations" / a[0]).is_dir()]()


def synth(root, args):
    """bin/cc intake synth: the planted bank generator (cc/intake_synth.py, test infrastructure), imported here only: no stage imports it."""
    import intake_synth
    return intake_synth.cli(root, args)


def _handoff(pick):
    """bin/cc intake convert | peek: the conversion before the intake (cc/intake_convert.py, role intake_handoff), imported when asked for."""
    def go(root, ident, a):
        import intake_convert
        return pick(intake_convert)(root, ident, a, tables(root))
    return _with_id(go)


INTAKE = {"explain": lambda root, a: print(explain(tables(root)), end="") or 0, "lint": _with_id(lint), "seal": _with_id(seal), "run": _with_id(run),
          "synth": synth, "convert": _handoff(lambda m: m.convert_cli), "peek": _handoff(lambda m: m.peek_cli)}


def cli(root, args):
    """bin/cc intake <sub>: a total lookup over the subcommands of INTAKE; any other word is a usage refusal."""
    sub = {True: lambda: args[0], False: lambda: ""}[len(args) > 0]()
    return blind.look(INTAKE, sub, lambda root, a: _usage(f"unknown subcommand '{sub}'"))(root, args[1:])
