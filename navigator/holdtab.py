"""Plan 1552: the alphabet and the total tables of the hold needle `hold-pair-v1` (contract/SCHEMA-1552.md). Pure: it imports
only navigator.steer, opens nothing and prints nothing. Every decision of the needle is a lookup in a table here; a value
outside a table's domain has no cell and raises KeyError."""
from navigator import steer as ST

NEEDLE = "hold-pair-v1"
MAP = "compass-map/1"
R_NOT_EVALUATED = "NOT EVALUATED"
NO_PREDECESSOR = "no-predecessor"
IN_TRANSIT = "in-transit"
UNVISITED = "unknown"

SAME = {c: c for c in ST.READING}
FLIP = dict(zip(ST.READING, reversed(ST.READING)))
ORIENT = {("+", "+"): SAME, ("-", "-"): SAME, ("+", "-"): FLIP, ("-", "+"): FLIP}
OPS = {"OFF": ("declare", "scan"), "ON": ("declare", "scan", "nudge")}

# the nine cells: (viewed class at the low probe, viewed class at the high probe) -> the call
CALL = {
    ("SIG-", "SIG-"): "raise", ("SIG-", "UNRES"): "raise", ("SIG-", "SIG+"): "stay",
    ("UNRES", "SIG-"): "no-signal", ("UNRES", "UNRES"): "no-signal", ("UNRES", "SIG+"): "lower",
    ("SIG+", "SIG-"): "no-signal", ("SIG+", "UNRES"): "no-signal", ("SIG+", "SIG+"): "lower",
}
DIRECTION = {"stay": 0, "raise": 1, "lower": -1, "no-signal": 0, "range-low": 0, "range-high": 0}
APPLIED = {"OFF": 0, "ON": 1}

LAST_KINDS = ("range-low", "range-high", "no-reading", "wire-lost")
OUTCOMES = {"range-low": "OFF-DIAL", "range-high": "OFF-DIAL", "no-reading": "HORIZON", "wire-lost": "WIRE-LOST"}
UNREAD = ("wire-lost", "no-reading")             # indexed by: the call did not fit before the declared horizon

PLAN = {"ON": lambda lo, hi: ([lo], [hi]), "OFF": lambda lo, hi: ([lo, hi],)}      # the calls of one hold pair: two nudges, or one scan

PAYLOAD ={"ignite": "grid", "approach": "leg", "hold": "pair"}

PLACE_STATES = {"SIG-": "disordered-side", "UNRES": "critical-bracketed", "SIG+": "ordered-side"}
STATES = tuple(sorted(set(PLACE_STATES.values()) | {IN_TRANSIT}))
_STATE = {(c, sign, ok): PLACE_STATES[ORIENT[("+", sign)][c]] if ok else IN_TRANSIT
          for c in ST.READING for sign in ("+", "-") for ok in (True, False)}


def classes(values, errors, z):
    """the classes as read: `steer.end_class` of each reading of the observable."""
    return [ST.end_class(d, e, z) for d, e in zip(values, errors)]


def placed(kind, c, g, T):
    """`range-low` when a centre c leaves the low probe off the dial, `range-high` for the high probe, else the kind itself."""
    return ("range-low", kind, "range-high")[1 + (c > T - g) - (c < g)]


def hold_kind(cls, view, mode, centre, step, g, T):
    """(kind, ticks applied) of one hold step: the call of the nine-cell table, placed at the centre it would give."""
    call = CALL[tuple(view[c] for c in cls)]
    kind = placed(call, centre + APPLIED[mode] * DIRECTION[call] * step, g, T)
    return kind, APPLIED[mode] * DIRECTION[kind] * step


def grid(lo, hi, width, margin, T):
    return [t for t in range(lo - margin * width, hi + margin * width + 1, width) if 0 <= t <= T]


def bracket(ticks, cls, view):
    """(last viewed SIG- tick, first viewed SIG+ tick) when the readings that resolve are one run of each; else ()."""
    kept = [(t, view[c]) for t, c in zip(ticks, cls) if c != "UNRES"]
    n = sum(1 for _, c in kept if c == "SIG-")
    run = [c for _, c in kept]
    one_run = run == ["SIG-"] * n + ["SIG+"] * (len(run) - n)
    return tuple(t for t, _ in kept[n - 1:n + 1]) * (one_run and 0 < n < len(run))


def ignite_kind(br, g, T):
    """`no-bracket` for no bracket, else `bracketed` placed at the bracket's midpoint."""
    return {0: "no-bracket", 2: placed("bracketed", sum(br) // 2, g, T)}[len(br)]


def legs(delta, max_nudge):
    """the whole strides of a walk of `delta` ticks: the last move (at most max_nudge) is left for the first probe."""
    sign = (delta > 0) - (delta < 0)
    return [sign * max_nudge] * max(0, -(-abs(delta) // max_nudge) - 1)


def cost(readings, n_eq, S, skip):
    return readings * (n_eq + S * skip)


def unread(index, c, horizon):
    return UNREAD[index + c > horizon]


def outcome(kind):
    return OUTCOMES[kind]


def commanded(cmd, since, to, at):
    """the lag model's state after commanding tick `to` at index `at`: a command to the tick already commanded moves nothing."""
    return to, (since, at)[to != cmd]


def settled(since, lag, first, skip):
    """the move had arrived before the first sampling sweep (a reading's window opens `skip` sweeps after it starts)."""
    return since + lag <= first - skip


def state(cls, ordered_sign, ok):
    return _STATE[(cls, ordered_sign, ok)]


def kernel_next(prior, x):
    """(A, B, the state after x) of one path in wire order: A = x - the reading before; B = A + the A of the edge before."""
    a = x - prior[0] if prior else NO_PREDECESSOR
    b = a + sum(prior[1:]) if prior else NO_PREDECESSOR
    return a, b, (x, a) if prior else (x,)
