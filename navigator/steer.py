"""Plan 1533: the alphabet of report schema 2 and its total tables (contract/SCHEMA-1533.md). Pure: it imports only math,
opens nothing and prints nothing. Every token of the schema is named here once. A value outside a table's domain has no
cell: the lookup raises KeyError, there is no fallback row."""
import math

READING = ("SIG-", "UNRES", "SIG+")
NOT_EVALUATED = "n/e"
STEP_KINDS = ("narrow", "lean-lo", "lean-hi", "unresolved", "not-evaluated")
OUTCOME_KINDS = ("Located", "PAST-LO", "PAST-HI", "UNDECIDED", "REFUSE")
REFUSE_REASONS = ("floor", "budget")
PHASES = ("bracketing",)
MODES = ("OFF", "ON")
DECLARE, MEASURE, NUDGE = "declare", "measure", "nudge"
ORDERED_SIDES = ("+K", "-K")
SLOTS = ("knobs_K", "ordered_side", "L", "tau", "k", "index_unit", "index_kind", "observable", "nlev", "system", "roles")
UNKNOWN = "unknown"
SIGMA_UNIT = "g"
SIGMA_MEASURED = "not-defined"
NEEDLE_V1 = "recover-adaptive-v1"
LOCATED, REFUSE = OUTCOME_KINDS[0], OUTCOME_KINDS[4]
NARROW, LEAN_LO, LEAN_HI, UNRESOLVED, NOT_EVALUATED_KIND = STEP_KINDS

_FLIP = dict(zip(READING, reversed(READING)))
_VIEW = {ORDERED_SIDES[0]: {c: c for c in READING}, ORDERED_SIDES[1]: _FLIP}
# the step table for the declared order `+K`, keyed on (reading class at the low end, reading class at the high end)
_STEP_TABLE = {
    ("SIG-", "SIG+"): NARROW,
    ("SIG-", "SIG-"): LEAN_HI,
    ("UNRES", "SIG-"): LEAN_HI,
    ("SIG+", "SIG+"): LEAN_LO,
    ("SIG+", "UNRES"): LEAN_LO,
    ("SIG-", "UNRES"): UNRESOLVED,
    ("UNRES", "SIG+"): UNRESOLVED,
    ("UNRES", "UNRES"): UNRESOLVED,
    ("SIG+", "SIG-"): UNRESOLVED,
}
# the fold of the set of step kinds: the rows that name one outcome; the mixed row is built from the kinds that were said
_FOLD_ROWS = {
    (): (REFUSE, REFUSE_REASONS[0]),
    (NARROW,): (LOCATED, None),
    (LEAN_LO,): (OUTCOME_KINDS[1], LEAN_LO),
    (LEAN_HI,): (OUTCOME_KINDS[2], LEAN_HI),
}


def end_class(d, s, z):
    """the position of the interval [d - z*s, d + z*s] against 0: wholly below, holding it, wholly above."""
    w = z * s
    return READING[(d > w) - (d < -w) + 1]


def end_classes(D, Gs_err, z):
    """(low class, high class): only the two ends of the grid are read; s is narrow's own expression."""
    return tuple(end_class(D[i], math.sqrt(Gs_err[i][1] ** 2 + Gs_err[i][0] ** 2), z) for i in (0, -1))


def scan_verdict(lo_class, hi_class, ordered_side):
    """(kind, reason) for the two end classes read as the grid gives them. KeyError for an unknown side or class."""
    view = _VIEW[ordered_side]
    return _STEP_TABLE[(view[lo_class], view[hi_class])], f"{lo_class}|{hi_class}"


def not_evaluated():
    return NOT_EVALUATED_KIND, NOT_EVALUATED


def outcome(kinds):
    """(kind, reason): the fold of the SET of step kinds. A missing reading is a budget refusal; no step is a floor."""
    said = tuple(k for k in STEP_KINDS if k in kinds)
    if NOT_EVALUATED_KIND in said:
        return REFUSE, REFUSE_REASONS[1]
    return _FOLD_ROWS.get(said, (OUTCOME_KINDS[3], "+".join(said)))   # the mixed row is a declared row, not a default


def mode_of(ops):
    """OFF when no `nudge` is held (it may still place the knob), ON when it is."""
    return MODES[NUDGE in ops]
