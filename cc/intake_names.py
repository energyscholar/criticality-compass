"""intake_names - the name classifier of the intake and the one type of every refusal's detail (plan 1160 P0; moved here from intake_blind
by plan 1160 P2, role `intake_names` with its own line cap, tests/test_budget.py NAMES_CAP). Invariant (blindness, as intake_blind): it
receives TEXT and plain values only and can open nothing; its imports are re, enum and dataclasses, and it calls no open, exec, eval or
__import__ (tests/test_intake.py checks both over the AST). It decides what of a name or a text may be printed: a NUMERIC name never prints,
and a text a file states (a unit) prints with every numeral in it shown as #."""
import enum
import re
from dataclasses import dataclass, replace

NUMBER = re.compile(r"[-+]?(\d+(\.\d*)?|\.\d+)([eE][-+]?\d+)?")   # a decimal number as written; "nan", "inf" and "" are not numbers


class Name(enum.Enum):
    """The class of a name a file or a declaration states. ATOMS: TEXT | NUMERIC. Axiom: exactly one holds for a string (its stripped text is a
    decimal number as written, NUMBER; or not). A NUMERIC name is a value (a WIDE table's names line is the fast axis), so it never prints.
    A text a file states (a unit, plan 1160 P2) is a run of TEXT and NUMERIC tokens, a NUMERIC token being each numeral in it (NUMBER found
    anywhere); it prints with each NUMERIC token as #, so a unit that holds a number never prints the number."""
    TEXT = frozenset({"TEXT"})
    NUMERIC = frozenset({"NUMERIC"})


def classify(name):
    return Name.NUMERIC if NUMBER.fullmatch(str(name).strip()) is not None else Name.TEXT


def masked(text):
    """A text a file states, as a Detail prints it: each NUMERIC token (a numeral anywhere in it) as #; a text with no character as (none)."""
    return NUMBER.sub("#", text) if text.strip() != "" else "(none)"


SHOW_COLUMN = {   # (the column's type, its Name class) -> how a Detail prints it; total over (str, int) x Name
    (str, Name.TEXT): lambda c: f"'{c}'", (str, Name.NUMERIC): lambda c: "a numeric name",
    (int, Name.TEXT): lambda c: f"#{c}", (int, Name.NUMERIC): lambda c: f"#{c}",   # an int is a 1-based position (column #k)
}
SHOW_WORD = {Name.TEXT: lambda w: w, Name.NUMERIC: lambda w: "a numeric word"}


def shown(columns):
    """Columns as a Detail prints them: a TEXT name quoted, a position as #k, a NUMERIC name never."""
    return [SHOW_COLUMN[(type(c), classify(c))](c) for c in columns]


def numbered(names):
    """A names line with each NUMERIC name replaced by its 1-based position, so it prints as column #k."""
    return tuple({Name.TEXT: lambda: c, Name.NUMERIC: lambda: k}[classify(c)]() for k, c in enumerate(names, 1))


UNIT_SYNTAX = {   # [reader.header] NAMES_UNITS_IN_NAMES unit_syntax -> a names cell "name (unit)" | "name/unit" (plan 1160 P2); total over FORMAT's
    "PAREN": re.compile(r"(.*?)\s*\(([^()]*)\)"),   # the unit is a trailing parenthesis: "Temperature (K)"
    "SLASH": re.compile(r"([^/]*?)\s*/\s*(.+)"),     # the unit follows the first slash: "Temp./°C", "M/emu/g" (unit emu/g)
}


def split_unit(cell, syntax):
    """A names cell to (name, unit) by the declared unit syntax; a cell that holds no unit in that syntax is (the cell, "") - it states none."""
    m = UNIT_SYNTAX[syntax].fullmatch(cell)
    return (m[1].strip(), m[2].strip()) if m is not None else (cell, "")


OPPOSITE = {"ASCENDING": "DESCENDING", "DESCENDING": "ASCENDING", "ACQUISITION": "ACQUISITION"}   # [acquisition] row_order -> its reverse; total
ORDER_CLASS = {   # (does a curve's fast sequence hold the declared row_order, does it hold the opposite) -> its class (plan 1160 A7); total over bool x bool
    (True, True): "in the declared order", (True, False): "in the declared order",   # every fast value equal holds both: it is in the declared order
    (False, True): "in the opposite order", (False, False): "in neither order (not monotone)"}


def sweeps(seqs, row_order, order):
    """(plan 1160 A7) S4 ROW_ORDER_DIFFERS's classification of the curves of the refused file, as COUNTS only (no value): how many hold the
    declared row_order, how many the opposite one, how many neither. `order` is the row_order table (intake_census.ORDER); seqs are fast sequences."""
    got = [ORDER_CLASS[(order[row_order](xs), order[OPPOSITE[row_order]](xs))] for xs in seqs]
    return {k: got.count(k) for k in dict.fromkeys(ORDER_CLASS.values())}


def _runs(xs):
    """A sequence as its runs (key, length): adjacent equal keys merged (None is no key: the first item always starts a run)."""
    starts = [i for i, (a, b) in enumerate(zip([None] + list(xs), xs)) if a != b]
    return [(xs[i], j - i) for i, j in zip(starts, starts[1:] + [len(xs)])]


def repeats(seqs):
    """(plan 1160 A17) S5 FAST_VALUE_REPEATED's classification of the refused curves' point keys, as COUNTS only, summed over seqs (one
    sequence per curve; longest run is the longest over them, 0 over none): consecutive runs (a key on two or more adjacent points), longest
    run, values revisited (a key in two or more separate runs) and monotone runs (maximal runs of one direction, equal keys merged)."""
    runs = [_runs(xs) for xs in seqs]
    keys = [[k for k, _ in rs] for rs in runs]
    twice = lambda ks: len({a for a, b in zip(sorted(ks), sorted(ks)[1:]) if a == b})   # the keys in two or more runs
    steps = lambda ks: [b > a for a, b in zip(ks, ks[1:])]   # each step up (True) or down; equal keys are one run, never a step
    turns = lambda ks: sum(p != q for p, q in zip(steps(ks), steps(ks)[1:]))   # the direction changes along a curve
    return {"consecutive runs": sum(n > 1 for rs in runs for _, n in rs), "longest run": max([n for rs in runs for _, n in rs], default=0),
            "values revisited": sum(twice(ks) for ks in keys), "monotone runs": sum(1 + turns(ks) for ks in keys)}


REPEAT_EXIT = {   # (plan 1160 A30) a repeat kind of `repeats` -> the exit FAST_VALUE_REPEATED's Detail names when the kind is found; total over the kinds it names
    "consecutive runs": "consecutive repeats: if the knob was set, they are readings of one point (replicate identity SAME_FAST_VALUE); if it was read, declare [knobs.fast] control MEASURED",
    "values revisited": "non-consecutive repeats (a value revisited): if the knob was read, declare [knobs.fast] control MEASURED; a set knob's loop is two branches (SPLIT_ROWS, one per file)",
}


def exits(counts):
    """The exit words of the kinds `repeats` found (a count above 0), in REPEAT_EXIT order."""
    return [w for k, w in REPEAT_EXIT.items() if counts[k] > 0]


@dataclass(frozen=True)
class Detail:
    """The detail of every refusal (plan 1160 P0). Invariant: it holds a file name, row numbers, columns (a name or a 1-based position), named
    counts, words (reason codes, declared words, file and curve names) and texts a file states (plan 1160 P2: a unit, as a pair (the
    role word, the text)), and no data value:
    str() is its only formatter, and it prints a column or a word only through the name classifier, so a NUMERIC name prints as a position or
    not at all, and a stated text only masked (a numeral in it as #)."""
    file: str
    rows: tuple
    columns: tuple
    counts: dict
    words: tuple
    stated: tuple = ()

    def __str__(self):
        cols = shown(self.columns)
        parts = ([self.file] * (self.file != "") + [SHOW_WORD[classify(w)](w) for w in self.words] + [f"{w} stated '{masked(t)}'" for w, t in self.stated]
                 + [f"row{'s' * (len(self.rows) > 1)} {', '.join(map(str, self.rows))}"] * (len(self.rows) > 0)
                 + [f"column{'s' * (len(cols) > 1)} {', '.join(cols)}"] * (len(cols) > 0) + [f"{k} = {n}" for k, n in self.counts.items()])
        return "; ".join(parts)

    def within(self, file, word):
        """The same detail placed in a file, after a leading word (S4 READER_REFUSED: the file, then the reader reason)."""
        return replace(self, file=file, words=(word,) + self.words)


def detail(file="", rows=(), columns=(), counts=(), words=(), stated=()):
    """A Detail with the slots a site names (the others empty)."""
    return Detail(file, tuple(rows), tuple(columns), dict(counts), tuple(words), tuple(stated))
