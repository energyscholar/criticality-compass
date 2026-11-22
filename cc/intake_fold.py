"""intake_fold - the execution of each stage, the run fold and the two verdict tables of the intake. Invariant: total and blind: it imports
only enum, dataclasses and intake_blind, constructs no Path, opens nothing, and every dispatch is a dict total over a key the test enumerates."""
import enum
from dataclasses import dataclass

from intake_blind import Mark


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
    return Verdict(Primary.PRIMARY_REFUSED_AT, (), [i for i in ids if out[i].mark is Mark.REFUSED][0])


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
    return p, Verdict(r, (rob,) if r is Robustness.ROBUSTNESS_INCOMPLETE else (), rob if r is Robustness.ROBUSTNESS_REFUSED else "")


def closure(t, sid):
    """The transitive needs of a stage."""
    row = {s["id"]: s for s in t["stages"]["stage"]}
    return {n for m in row[sid]["needs"] for n in {m} | closure(t, m)}


def before_data(t):
    """The stages of lint and seal: they read no data byte, no stage in their transitive needs reads one, and they are not the ADVISORY seal."""
    reads = {s["id"] for s in t["stages"]["stage"] if ReadsBytes[s["reads_bytes"]] is not ReadsBytes.NONE}
    return [s for s in t["stages"]["stage"] if Scope[s["verdict"]] is not Scope.ADVISORY and s["id"] not in reads and not closure(t, s["id"]) & reads]
