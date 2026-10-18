"""intake_blind - stage S0 FORMAT of the intake (plan 1136): the declaration text against intake/FORMAT.toml, as a value.
Invariant (blindness, plan 1136 contract 4): this module receives TEXT and plain values only and can open nothing. Its imports are tomllib,
re, dataclasses and typing; it calls no open, exec, eval or __import__ (tests/test_intake.py checks both over the AST). Every refusal is a
reason code of intake/STAGES.toml S0, emitted by walking the FORMAT table; no message text is ever matched. It also holds the two StageResult values, which
every intake module shares and which need no import beyond dataclasses and enum."""
import enum
import tomllib
from dataclasses import dataclass

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
    """StageResult atom REFUSE. Invariant: `reason` is a reason code of its stage in intake/STAGES.toml; `evidence` is the detail shown."""
    reason: str
    evidence: str
    mark = Mark.REFUSED

    def text(self, sentences):
        return f"REFUSE {self.reason}. {sentences[self.reason]} Detail: {self.evidence}"

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


@dataclass(frozen=True)
class Declaration:
    """S0's PASS evidence: the parsed declaration as plain values. Invariant: built only from a text whose every field S0 admitted; holds no
    path and no opener, so a stage that receives it can read no byte."""
    id: str
    mode: str
    data: dict

    def summary(self):
        return f"The declaration '{self.id}' parses, and every field of format v1 is present, typed and listed (mode {self.mode})"

    def confirmed(self):
        return False


def look(table, key, absent):
    """Total lookup: the row of `key`, or `absent` when `key` is no row. Membership is the boolean key of a two-row table (no default value)."""
    return {True: lambda: table[key], False: lambda: absent}[key in table]()


TYPE = {   # a FORMAT field's type word -> its membership test; total over the type words FORMAT.toml uses (tests/test_intake.py)
    "str": lambda v: isinstance(v, str),
    "int": lambda v: isinstance(v, int) and not isinstance(v, bool),
    "num": lambda v: isinstance(v, (int, float)) and not isinstance(v, bool),
    "list": lambda v: isinstance(v, list),
    "table": lambda v: isinstance(v, dict),
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


CHECK = {   # a FORMAT field's check word -> its findings for a value of the right type; total over FORMAT.toml's check words (test)
    "TEXT": lambda spec, v, loc, tables: {True: [Finding("VALUE_STILL_TODO", loc, "TODO")], False: []}[v == TODO],
    "NUMBER": lambda spec, v, loc, tables: [],   # SCALAR: a cc.toml [interval_fields] field (str, int or num), TODO refused
    "SCALAR": lambda spec, v, loc, tables: {True: [Finding("VALUE_STILL_TODO", loc, "TODO")], False: []}[v == TODO],
    "CLOSED": _closed,
    "ITEMS": lambda spec, v, loc, tables: [Finding("FIELD_TYPE_WRONG", f"{loc}[{i}]", f"want {spec['item']}") for i, x in enumerate(v) if not TYPE[spec["item"]](x)],
    "TABLE": lambda spec, v, loc, tables: section(spec["fields"], v, loc, tables),
    "TABLES": lambda spec, v, loc, tables: [f for i, x in enumerate(v) for f in {True: lambda: section(spec["fields"], x, f"{loc}[{i}]", tables),
                                                                                  False: lambda: [Finding("FIELD_TYPE_WRONG", f"{loc}[{i}]", "want a table")]}[TYPE["table"](x)]()],
    "INTERVAL": _interval,
}


def typed(spec, v, loc, tables):
    """A present field: FIELD_TYPE_WRONG, or the findings of its check."""
    return {True: lambda: CHECK[spec["check"]](spec, v, loc, tables),
            False: lambda: [Finding("FIELD_TYPE_WRONG", loc, f"{type(v).__name__}, want {spec['type']}")]}[TYPE[spec["type"]](v)]()


def field(spec, d, key, loc, tables, required=True):
    """One field of a section: absent (FIELD_MISSING when required, nothing when optional) or present (typed)."""
    return {True: lambda: typed(spec, d[key], loc, tables), False: lambda: {True: [Finding("FIELD_MISSING", loc, "absent")], False: []}[required]}[key in d]()


def unknown(d, rows, loc, tables):
    """Keys that are no field row: STAMPED, DERIVED, or UNKNOWN, by a total lookup."""
    cls = {**{k: "FIELD_IS_STAMPED" for k in tables["format"]["stamped"]}, **{k: "FIELD_IS_DERIVED" for k in tables["format"]["derived"]}}
    return [Finding(look(cls, k, "FIELD_UNKNOWN"), f"{loc}.{k}".lstrip("."), "not a field of format v1") for k in d if k not in rows]


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
    """S0 FORMAT. (declaration text, the transducer file's findings as text lines, the intake tables) -> Pass(Declaration) | Refuse.
    Invariant: PASS exactly when there is no finding; a REFUSE names the first finding's reason and lists every finding."""
    p = parse(text)
    found = p.findings(tuple(transducer_findings), tables)
    return {True: lambda: Pass(Declaration(p.data["id"], p.data["intake"]["mode"], p.data)),
            False: lambda: Refuse(found[0].reason, "; ".join(f"{f.reason} at {f.loc or 'the file'}: {f.detail}" for f in found))}[not found]()
