"""intake_blind - stage S0 FORMAT of the intake: the declaration text against intake/FORMAT.toml, as a value.
Invariant (blindness): this module receives TEXT and plain values only and can open nothing. Its imports are tomllib, dataclasses, typing
and intake_names (as blind as it); it calls no open, exec, eval or __import__ (tests/test_intake.py checks both over the AST). Every refusal
is a reason code of intake/STAGES.toml S0, emitted by walking the FORMAT table; no message text is ever matched. It also holds what every
intake module shares and which needs no import beyond dataclasses and enum: the two StageResult values, the Evidence base, `gate`, `look`
and `flag`; and it re-exports Detail, the one type of every refusal's detail, with the name classifier it prints through (cc/intake_names.py)."""
import enum
import tomllib
from dataclasses import dataclass

from intake_names import NUMBER, Detail, Name, classify, detail, numbered, shown, sweeps   # noqa: F401 - the classifier and Detail

TODO = "TODO"


class Mark(enum.Enum):
    """What one stage's execution contributes to the verdicts. ATOMS: STUB | WITHHELD_AFTER_REFUSAL | WITHHELD_INPUT_ABSENT | PASSED | REFUSED.
    Axiom: exactly one holds for each stage of a run (a stage has no body; or it was withheld after a refusal; or withheld for a need that did
    not pass; or its body passed; or its body refused)."""
    STUB = frozenset({"STUB"})
    WITHHELD_AFTER_REFUSAL = frozenset({"WITHHELD_AFTER_REFUSAL"})
    WITHHELD_INPUT_ABSENT = frozenset({"WITHHELD_INPUT_ABSENT"})
    PASSED = frozenset({"PASSED"})
    REFUSED = frozenset({"REFUSED"})


@dataclass(frozen=True)
class Pass:
    """StageResult atom PASS (StageResult ATOMS: PASS | REFUSE; exactly one holds for an executed stage). Invariant: `evidence` is the stage's
    own evidence type, the only carrier of what a downstream stage receives."""
    evidence: object
    mark = Mark.PASSED

    def text(self, sentences):
        return "PASS. " + self.evidence.summary()

    def confirmed(self):
        return self.evidence.confirmed()

    def mode(self):
        return self.evidence.mode


@dataclass(frozen=True)
class Refuse:
    """StageResult atom REFUSE. Invariant: `reason` is a reason code of its stage in intake/STAGES.toml; `evidence` is its Detail."""
    reason: str
    evidence: Detail
    mark = Mark.REFUSED

    def text(self, sentences):
        return f"REFUSE {self.reason}. {sentences[self.reason]} Detail: {Detail.__str__(self.evidence)}"   # Detail's formatter: a str evidence cannot print

    def confirmed(self):
        return False

    def mode(self):
        return "not known (the declaration did not pass FORMAT)"


@dataclass(frozen=True)
class Finding:
    """One refused field. Invariant: `reason` is an S0 reason code of intake/STAGES.toml; `loc` is the dotted field; `detail` is shown, never read."""
    reason: str
    loc: str
    detail: str


class Evidence:
    """The base of every stage's PASS evidence. Invariant: no evidence is a human confirmation, so confirmed() is False; only the seal's
    SealState (cc/intake_seal.py) answers otherwise, and it does not derive from this class."""

    def confirmed(self):
        return False


@dataclass(frozen=True)
class Declaration(Evidence):
    """S0's PASS evidence: the parsed declaration as plain values. Invariant: built only from a text whose every field S0 admitted; holds no
    path and no opener, so a stage that receives it can read no byte."""
    id: str
    mode: str
    data: dict

    def summary(self):
        return f"The declaration '{self.id}' parses, and every field of format v3 is present, typed and listed (mode {self.mode})"


def look(table, key, absent):
    """Total lookup: the row of `key`, or `absent` when `key` is no row. Membership is the boolean key of a two-row table (no default value)."""
    return {True: lambda: table[key], False: lambda: absent}[key in table]()


def flag(args, name, absent):
    """The word after `name` in a command line, or `absent` when the flag is not there or is the last word."""
    return {True: lambda: args[args.index(name) + 1], False: lambda: absent}[name in args and args.index(name) + 1 < len(args)]()


TYPE = {   # a FORMAT field's type word -> its membership test; total over the type words FORMAT.toml uses (tests/test_intake.py)
    "str": lambda v: isinstance(v, str),
    "int": lambda v: isinstance(v, int) and not isinstance(v, bool),
    "num": lambda v: isinstance(v, (int, float)) and not isinstance(v, bool),
    "list": lambda v: isinstance(v, list),
    "table": lambda v: isinstance(v, dict),
    "ref": lambda v: isinstance(v, str) or (isinstance(v, int) and not isinstance(v, bool)),   # a column: a name, or a 1-based position
    "numeral": lambda v: isinstance(v, str) and NUMBER.fullmatch(v.strip()) is not None,   # a decimal number written as TEXT (LISTED values)
}


def admitted(spec, tables):
    """The CLOSED table of a field: TODO, the inline `values`, and ADMIT for every key of each declared `admit` source."""
    keys = {k: "ADMIT" for src in spec["admit"] for k in tables["admit"][src]}
    return {TODO: "VALUE_STILL_TODO", **keys, **spec["values"]}


def _closed(spec, v, loc, tables):
    code = look(admitted(spec, tables), v, spec["absent"])
    return {True: [], False: [Finding(code, loc, f"'{v}'")]}[code == "ADMIT"]


def _interval(spec, v, loc, tables):
    """[interval]: `method` first; its own fields are cc.toml [interval_fields.<method>], required and optional (no per-method code here)."""
    method = str(look(v, "method", ""))   # str(): a mistyped method is a key of no row
    first = field(spec["method"], v, "method", f"{loc}.method", tables, True)
    fields = look(tables["interval_fields"], method, {"required": {}, "optional": {}})
    rows = {**{k: (t, True) for k, t in fields["required"].items()}, **{k: (t, False) for k, t in fields["optional"].items()}}
    rest = [f for k, (t, req) in rows.items() if k != "method" for f in field({"type": t, "check": "SCALAR"}, v, k, f"{loc}.{k}", tables, req)]
    return first + rest + unknown(v, {**rows, "method": None}, loc, tables)


def _variant(spec, v, loc, tables):
    """VARIANT: the `select` field first, CLOSED over the keys of `variants` (a value of no row is the spec's `absent` reason);
    then exactly the fields of the row it names (none when it names no row, so every other key is FIELD_UNKNOWN after the selector's own
    finding). Invariant: no field of another row is ever admitted."""
    sel = spec["select"]
    closed = {"type": "str", "check": "CLOSED", "admit": [], "absent": spec["absent"], "values": {k: "ADMIT" for k in spec["variants"]}}
    return section({sel: closed, **look(spec["variants"], str(look(v, sel, "")), {})}, v, loc, tables)


CHECK = {   # a FORMAT field's check word -> its findings for a value of the right type; total over FORMAT.toml's check words (test)
    "TEXT": lambda spec, v, loc, tables: {True: [Finding("VALUE_STILL_TODO", loc, "TODO")], False: []}[v == TODO],
    "UNDER": lambda spec, v, loc, tables: {True: [], False: [Finding("ROOT_NOT_UNDER_CC_BANKS", loc, f"want '{spec['under']}<id>/bank'")]}[v.startswith(spec["under"])],   # TODO: refused by typed
    "NUMBER": lambda spec, v, loc, tables: [],   # SCALAR: a cc.toml [interval_fields] field (str, int or num), TODO refused
    "SCALAR": lambda spec, v, loc, tables: {True: [Finding("VALUE_STILL_TODO", loc, "TODO")], False: []}[v == TODO],
    "CLOSED": _closed,
    "ITEMS": lambda spec, v, loc, tables: [Finding("FIELD_TYPE_WRONG", f"{loc}[{i}]", f"want {spec['item']}") for i, x in enumerate(v) if not TYPE[spec["item"]](x)],
    "PREFIXES": lambda spec, v, loc, tables: CHECK["ITEMS"](spec, v, loc, tables) + [Finding("COMMENT_PREFIX_EMPTY", f"{loc}[{i}]", "an empty prefix marks every line a comment")
                                                                                     for i, x in enumerate(v) if x == ""],
    "TABLE": lambda spec, v, loc, tables: section(spec["fields"], v, loc, tables),
    "TABLES": lambda spec, v, loc, tables: [f for i, x in enumerate(v) for f in {True: lambda: section(spec["fields"], x, f"{loc}[{i}]", tables),
                                                                                  False: lambda: [Finding("FIELD_TYPE_WRONG", f"{loc}[{i}]", "want a table")]}[TYPE["table"](x)]()],
    "INTERVAL": _interval,
    "REF": lambda spec, v, loc, tables: [],   # a name or a position, typed by TYPE["ref"]; "TODO" is refused before any check (typed)
    "VARIANT": _variant,
    "VARIANTS": lambda spec, v, loc, tables: [f for i, x in enumerate(v) for f in {True: lambda: _variant(spec, x, f"{loc}[{i}]", tables),   # a list of
                                                                                   False: lambda: [Finding("FIELD_TYPE_WRONG", f"{loc}[{i}]", "want a table")]}[TYPE["table"](x)]()],   # VARIANT tables
}


def typed(spec, v, loc, tables):
    """A present field: VALUE_STILL_TODO when it is the template's "TODO" (whatever its type: `bin/cc new intake` writes TODO in
    every field), else FIELD_TYPE_WRONG, or the findings of its check."""
    return {True: lambda: [Finding("VALUE_STILL_TODO", loc, "TODO")],
            False: lambda: {True: lambda: CHECK[spec["check"]](spec, v, loc, tables),
                            False: lambda: [Finding("FIELD_TYPE_WRONG", loc, f"{type(v).__name__}, want {spec['type']}")]}[TYPE[spec["type"]](v)]()}[v == TODO]()


def field(spec, d, key, loc, tables, required=True):
    """One field of a section: absent (FIELD_MISSING when required, nothing when optional) or present (typed)."""
    return {True: lambda: typed(spec, d[key], loc, tables), False: lambda: {True: [Finding("FIELD_MISSING", loc, "absent")], False: []}[required]}[key in d]()


def unknown(d, rows, loc, tables):
    """Keys that are no field row: STAMPED, DERIVED, or UNKNOWN, by a total lookup."""
    cls = {**{k: "FIELD_IS_STAMPED" for k in tables["format"]["stamped"]}, **{k: "FIELD_IS_DERIVED" for k in tables["format"]["derived"]}}
    return [Finding(look(cls, k, "FIELD_UNKNOWN"), f"{loc}.{k}".lstrip("."), "not a field of format v3") for k in d if k not in rows]


def section(rows, d, loc, tables):
    """Every field of a table, in FORMAT order, then its unknown keys."""
    pre = {True: "", False: loc + "."}[loc == ""]
    return [f for k, spec in rows.items() for f in field(spec, d, k, pre + k, tables)] + unknown(d, rows, loc, tables)


@dataclass(frozen=True)
class Unparsed:
    """The text is not TOML. Invariant: its only finding is TOML_INVALID; no field is examined."""
    error: str

    def findings(self, transducer_findings, tables):
        return [Finding("TOML_INVALID", "", self.error)]


@dataclass(frozen=True)
class Absent:
    """declarations/<id>/intake.toml is no file: what S0 receives in place of the text. Invariant: its only finding is DECLARATION_FILE_ABSENT."""
    path: str

    def findings(self, transducer_findings, tables):
        return [Finding("DECLARATION_FILE_ABSENT", "", f"{self.path} is no file")]


@dataclass(frozen=True)
class Parsed:
    """The text is TOML. Invariant: findings are the header, then every FORMAT field, then the transducer file's findings, in that order."""
    data: dict

    def findings(self, transducer_findings, tables):
        head = [Finding("SCHEMA_UNSUPPORTED", k, f"want {k} = {v!r}") for k, v in tables["format"]["header"].items() if not (k in self.data and self.data[k] == v)]
        trans = [Finding("TRANSDUCER_FILE_REFUSED", "transducer.toml", " | ".join(transducer_findings))] * (len(transducer_findings) > 0)
        return head + section(tables["format"]["fields"], self.data, "", tables) + trans


def parse(text):
    """Parsed or Unparsed: the one place a TOML error (an exception of tomllib) becomes a value."""
    try:
        return Parsed(tomllib.loads(text))
    except tomllib.TOMLDecodeError as e:
        return Unparsed(str(e))


def format_stage(text, transducer_findings, tables):
    """S0 FORMAT. (declaration text or Absent, the transducer file's findings as text lines, the intake tables) -> Pass(Declaration) | Refuse.
    Invariant: PASS exactly when there is no finding; a REFUSE names the first finding's reason and lists every finding."""
    p = {str: parse, Absent: lambda a: a}[type(text)](text)
    found = p.findings(tuple(transducer_findings), tables)
    return {True: lambda: Pass(Declaration(p.data["id"], p.data["intake"]["mode"], p.data)),
            False: lambda: Refuse(found[0].reason, detail(words=[f"{f.reason} at {f.loc or 'the file'}: {f.detail}" for f in found]))}[not found]()


def gate(checks, then, refuse=Refuse):
    """then() (a Pass or a Refuse) when every (holds, reason, detail) row holds, else refuse(reason, detail()) of the first row that does not
    (a Refuse; a reader's is intake_read.Unreadable). Rows are evaluated in order and lazily (each `holds` and `detail` is a function): zip
    with range(1) draws at most one failing row, so no row after it runs."""
    failed = [c for _, c in zip(range(1), (c for c in checks if not c[0]()))]
    return {True: then, False: lambda: refuse(failed[0][1], failed[0][2]())}[not failed]()


SWEEP = {   # [acquisition] row_order -> (the [acquisition] table) -> the direction the fast knob runs within a curve; total
    "ASCENDING": lambda acq: "ASCENDING", "DESCENDING": lambda acq: "DESCENDING", "ACQUISITION": lambda acq: acq["direction"],
}
RESTARTS = {   # a direction a curve runs in -> (previous fast value, fast value) -> does a new sweep begin (the fast knob turns back); S1's tables
    # (cc/intake_choices.py) and S5's (intake_census.BREAK) both read SWEEP and RESTARTS
    "ASCENDING": lambda a, b: b < a, "DESCENDING": lambda a, b: b > a,   # UNORDERED has no row: S1 refuses BLOCK_RULE_HAS_NO_DIRECTION first
}
