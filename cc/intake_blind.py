"""intake_blind - stage S0 FORMAT of the intake (plan 1136): the declaration text against intake/FORMAT.toml, as a value.
Invariant (blindness, plan 1136 contract 4): this module receives TEXT and plain values only and can open nothing. Its imports are tomllib,
dataclasses, typing and intake_names (as blind as it); it calls no open, exec, eval or __import__ (tests/test_intake.py checks both over the AST). Every refusal is a
reason code of intake/STAGES.toml S0, emitted by walking the FORMAT table; no message text is ever matched. It also holds the two StageResult values, which
every intake module shares and which need no import beyond dataclasses and enum, and re-exports Detail, the one type of every refusal's
detail (plan 1160 P0), with the name classifier it prints through (both in cc/intake_names.py since plan 1160 P2)."""
import enum
import tomllib
from dataclasses import dataclass

from intake_names import NUMBER, Detail, Name, classify, detail, numbered, shown   # noqa: F401 - the classifier and Detail (plan 1160 P2: own role)

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


@dataclass(frozen=True)
class Declaration:
    """S0's PASS evidence: the parsed declaration as plain values. Invariant: built only from a text whose every field S0 admitted; holds no
    path and no opener, so a stage that receives it can read no byte."""
    id: str
    mode: str
    data: dict

    def summary(self):
        return f"The declaration '{self.id}' parses, and every field of format v3 is present, typed and listed (mode {self.mode})"

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
    "ref": lambda v: isinstance(v, str) or (isinstance(v, int) and not isinstance(v, bool)),   # a column: a name, or a 1-based position
    "numeral": lambda v: isinstance(v, str) and NUMBER.fullmatch(v.strip()) is not None,   # a decimal number written as TEXT (plan 1160 P1: LISTED values)
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
    """VARIANT: the `select` field first, CLOSED over the keys of `variants` (a value of no row is the spec's `absent` reason, plan 1160 P3);
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
                                                                                     for i, x in enumerate(v) if x == ""],   # plan-1145 E8
    "TABLE": lambda spec, v, loc, tables: section(spec["fields"], v, loc, tables),
    "TABLES": lambda spec, v, loc, tables: [f for i, x in enumerate(v) for f in {True: lambda: section(spec["fields"], x, f"{loc}[{i}]", tables),
                                                                                  False: lambda: [Finding("FIELD_TYPE_WRONG", f"{loc}[{i}]", "want a table")]}[TYPE["table"](x)]()],
    "INTERVAL": _interval,
    "REF": lambda spec, v, loc, tables: [],   # a name or a position, typed by TYPE["ref"]; "TODO" is refused before any check (typed)
    "VARIANT": _variant,
    "VARIANTS": lambda spec, v, loc, tables: [f for i, x in enumerate(v) for f in {True: lambda: _variant(spec, x, f"{loc}[{i}]", tables),   # 1160 P3: a list of
                                                                                   False: lambda: [Finding("FIELD_TYPE_WRONG", f"{loc}[{i}]", "want a table")]}[TYPE["table"](x)]()],   # VARIANT tables
}


def typed(spec, v, loc, tables):
    """A present field: VALUE_STILL_TODO when it is the template's "TODO" (whatever its type, plan 1139: `bin/cc new intake` writes TODO in
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
            False: lambda: Refuse(found[0].reason, detail(words=[f"{f.reason} at {f.loc or 'the file'}: {f.detail}" for f in found]))}[not found]()


def gate(checks, then):
    """then() (a Pass or a Refuse) when every (holds, reason, detail) row holds, else Refuse(reason, detail()) of the first row that does not.
    Rows are evaluated in order and lazily (each `holds` and `detail` is a function): zip with range(1) draws at most one failing row, so no
    row after it runs. (Moved here from intake_data by plan 1160 P1, so S1 uses it within this module's import allow-list.)"""
    failed = [c for _, c in zip(range(1), (c for c in checks if not c[0]()))]
    return {True: then, False: lambda: Refuse(failed[0][1], failed[0][2]())}[not failed]()


ONE_PER_FILE = {   # [selection.slow] source -> does the declaration give one slow value per selected file; total over FORMAT's sources (test)
    "LISTED": lambda sel: len(sel["slow"]["values"]) == len(sel["files"]),
    "FILE_KEY": lambda sel: True,   # each file states its own value in a header line (S5 reads it there, or refuses SLOW_KEY_UNRESOLVED)
    "NONE": lambda sel: True,       # no slow knob: no value is declared, so none is missing or extra
    "COLUMN": lambda sel: True,     # LONG_TABLE: the slow knob is a column of the one file
}

SWEEP = {   # [acquisition] row_order -> (the [acquisition] table) -> the direction the fast knob runs within a curve (plan 1160 P2); total
    "ASCENDING": lambda acq: "ASCENDING", "DESCENDING": lambda acq: "DESCENDING", "ACQUISITION": lambda acq: acq["direction"],
}
RESTARTS = {   # a direction a curve runs in -> (previous fast value, fast value) -> does a new sweep begin (the fast knob turns back)
    "ASCENDING": lambda a, b: b < a, "DESCENDING": lambda a, b: b > a,   # UNORDERED has no row: S1 refuses BLOCK_RULE_HAS_NO_DIRECTION first
}
DIRECTED = {   # [selection] layout -> does the curve rule of the declaration have the direction it needs; total over FORMAT's layouts (test)
    "PER_FILE": lambda d: True,   # a file is a curve
    "LONG_TABLE": lambda d: {"EXACT": True, "FAST_RESTART": SWEEP[d["acquisition"]["row_order"]](d["acquisition"]) in RESTARTS}[d["selection"]["block"]],
}

SELECTED = {   # [selection] layout -> how many files the declaration selects; total over FORMAT's layouts (test). Amendment A1 of plan 1160
    "PER_FILE": lambda sel: len(sel["files"]), "LONG_TABLE": lambda sel: 1,   # LONG_TABLE names its one `file`
}


@dataclass(frozen=True)
class Chosen:
    """S1 CHOICES' PASS evidence (plan 1160 P1). Invariant: built only from a Declaration for which every row in `checked` held; `checked` is
    exactly the rows the body runs (tests/test_intake.py: the S1 rows with live = true), and the summary says the other rows were not checked."""
    declaration: Declaration
    checked: tuple

    def summary(self):
        return (f"Checked: {', '.join(self.checked)}. The other S1 rows have no body yet (plan 1160 P4), so they were not checked; the report "
                f"lists them under the reasons no body can return yet")

    def confirmed(self):
        return False


def choices(declaration):
    """S1 CHOICES (reads no byte). Plan 1160 P1 makes one row live, SLOW_VALUES_NOT_ONE_PER_FILE, so that a LISTED count that differs from the
    files count is refused before the loader and never zipped short; plan 1160 P2 adds SELECTION_EMPTY (amendment A1: an empty `files` would
    crash S4, which reads the first file) and BLOCK_RULE_HAS_NO_DIRECTION, so a FAST_RESTART block rule
    always has a direction (RESTARTS has a row for it); plan 1160 P4 adds the other rows."""
    sel = declaration.data["selection"]
    rows = [(lambda: SELECTED[sel["layout"]](sel) > 0, "SELECTION_EMPTY", lambda: detail(words=[f"layout {sel['layout']}"], counts={"files selected": 0})),   # A1: S4 reads files[0]
            (lambda: ONE_PER_FILE[sel["slow"]["source"]](sel), "SLOW_VALUES_NOT_ONE_PER_FILE",
             lambda: detail(counts={"files": len(sel["files"]), "slow values": len(sel["slow"]["values"])})),
            (lambda: DIRECTED[sel["layout"]](declaration.data), "BLOCK_RULE_HAS_NO_DIRECTION",   # plan 1160 P2: FAST_RESTART needs a direction
             lambda: detail(words=["block FAST_RESTART", "row_order ACQUISITION", f"direction {declaration.data['acquisition']['direction']}"]))]
    return gate(rows, lambda: Pass(Chosen(declaration, tuple(r[1] for r in rows))))
