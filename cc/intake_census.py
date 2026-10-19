"""intake_census - S4 SHAPE and S5 CENSUS of the intake: the pinned files through the declared reader, cut into curves and counted.
Invariant: it reads bytes only from a Pinned (what S3 read), never from a path, and its tables are total over FORMAT's alphabets; it
constructs no Path and opens nothing, and it holds counts and names, never a value, in what it passes on."""
import itertools
import statistics

import intake_read
from intake_blind import NUMBER, RESTARTS, SWEEP, Pass, Refuse, detail, gate, numbered, sweeps
from intake_evidence import Alignment, Census, Curve, Pinned, Sampling, Shaped


def read(t, d, f):
    """One pinned file through the declaration's reader: intake_read.Grid | intake_read.Unreadable (never an exception)."""
    return intake_read.readers(t)[d["reader"]["name"]](f.data, d)


BREAK = {   # LONG_TABLE [selection] block -> (the declaration) -> (previous row, row) -> does a new curve begin at row; total over FORMAT's blocks
    "EXACT": lambda d: lambda p, r: p[-1] != r[-1],   # the slow value (the last role column) changes
    "FAST_RESTART": lambda d: lambda p, r: RESTARTS[SWEEP[d["acquisition"]["row_order"]](d["acquisition"])](p[0], r[0]),   # the fast knob turns back (S1: it has a direction)
}


def _blocks(f, g, d):
    """LONG_TABLE: the blocks of consecutive rows the declared block rule (BREAK) cuts the file into, in file order, each one Curve whose slow
    value is its FIRST row's (a value as measured, never a mean)."""
    brk, rows = BREAK[d["selection"]["block"]](d), tuple(g.rows)
    ids = itertools.accumulate(int(brk(p, r)) for p, r in zip(rows[:1] + rows[:-1], rows))
    runs = [[r for _, r in rs] for _, rs in itertools.groupby(zip(ids, rows), key=lambda x: x[0])]
    return [Curve(f"{f.name} block {i}", (rs[0][-1],), tuple(rs), len({r[-1] for r in rs})) for i, rs in enumerate(runs, 1)]


SLOW = {   # PER_FILE [selection.slow] source -> (its row, the files' grids) -> each curve's slow values (a tuple); total over FORMAT's PER_FILE sources
    "LISTED": lambda slow, grids: [(float(v),) for v in slow["values"]],   # numerals (S0), one per listed file (S1), in `files` order
    "FILE_KEY": lambda slow, grids: [tuple(float(v) for v in intake_read.keyed(g, slow["key"]) if NUMBER.fullmatch(v)) for g in grids],   # S5 checks one each
    "NONE": lambda slow, grids: [()] * len(grids),   # no slow knob
}


UNKEYED = {   # PER_FILE [selection.slow] source -> (its row, files, grids) -> the files whose slow value their header does not state exactly once, as a number
    "LISTED": lambda slow, files, grids: [],
    "FILE_KEY": lambda slow, files, grids: [f.name for f, g in zip(files, grids) if [NUMBER.fullmatch(v) is not None for v in intake_read.keyed(g, slow["key"])] != [True]],
    "NONE": lambda slow, files, grids: [],
}


KEYS = {   # [selection] layout -> (declaration, files, grids) -> the files whose slow value does not resolve; total over FORMAT's layouts
    "PER_FILE": lambda d, files, grids: UNKEYED[d["selection"]["slow"]["source"]](d["selection"]["slow"], files, grids),
    "LONG_TABLE": lambda d, files, grids: [],   # the slow knob is a column, every cell a number (S4, the reader)
}


CURVES = {   # [selection] layout -> (declaration, files, their grids) -> the curves, in file order; total over FORMAT's layouts
    "PER_FILE": lambda d, files, grids: [Curve(f.name, s, g.rows, len(s)) for f, g, s in zip(files, grids, SLOW[d["selection"]["slow"]["source"]](d["selection"]["slow"], grids))],
    "LONG_TABLE": lambda d, files, grids: [c for f, g in zip(files, grids) for c in _blocks(f, g, d)],
}


ORDER = {   # [acquisition] row_order -> does a sequence of fast values hold it; total over FORMAT's row_order values
    "ASCENDING": lambda xs: all(a <= b for a, b in zip(xs, xs[1:])),
    "DESCENDING": lambda xs: all(a >= b for a, b in zip(xs, xs[1:])),
    "ACQUISITION": lambda xs: True,   # stored in acquisition order: no claim about the fast knob to check
}


DIRECTION = {   # (are rows stored in acquisition order, [acquisition] direction) -> does a curve's stored fast sequence hold it; total
    **{(False, k): (lambda xs: True) for k in ("ASCENDING", "DESCENDING", "UNORDERED")},   # rows sorted: the file records no acquisition order
    (True, "ASCENDING"): ORDER["ASCENDING"], (True, "DESCENDING"): ORDER["DESCENDING"], (True, "UNORDERED"): lambda xs: True,
}


UNIT = {   # a role of intake_read.role_columns -> its declared unit (the uncertainty is in the measured quantity's unit); total over the roles
    "fast": lambda d: d["knobs"]["fast"]["unit"], "measured": lambda d: d["measured"]["unit"],
    "uncertainty": lambda d: d["measured"]["unit"], "slow": lambda d: d["knobs"]["slow"]["unit"],
}


def shape(pinned, t):
    """S4 SHAPE on the first file only. Invariant: READER_NOT_LIVE | READER_REFUSED | COLUMNS_DIFFER | UNIT_DIFFERS | ROW_ORDER_DIFFERS (within
    each curve of the first file), in that order. The declared columns are intake_read.role_columns, in role order."""
    d, f = pinned.declaration.data, pinned.files[0]
    g, cols = read(t, d, f), tuple(ref for _, ref in intake_read.role_columns(d))
    units = lambda: [(r, u, UNIT[r](d)) for r, u in g.units if u != UNIT[r](d)]
    unordered = lambda: [c.where for c in CURVES[d["selection"]["layout"]](d, pinned.files[:1], [g]) if not ORDER[d["acquisition"]["row_order"]]([r[0] for r in c.rows])]
    return gate([(lambda: d["reader"]["name"] in intake_read.LIVE, "READER_NOT_LIVE", lambda: detail(words=[f"reader '{d['reader']['name']}'"])),
                 (lambda: g.readable, "READER_REFUSED", lambda: g.detail.within(f.name, g.reason)),
                 (lambda: g.columns == cols, "COLUMNS_DIFFER", lambda: detail(f.name, columns=numbered(g.columns) + cols, counts={"columns in the file": len(g.columns), "declared": len(cols)})),
                 (lambda: not units(), "UNIT_DIFFERS", lambda: detail(f.name, words=[f"{r} declared {w}" for r, u, w in units()], stated=[(r, u) for r, u, w in units()])),
                 (lambda: not unordered(), "ROW_ORDER_DIFFERS", lambda: detail(words=unordered()[:3] + [f"not {d['acquisition']['row_order']} in {d['knobs']['fast']['name']}"], counts={"curves": len(unordered()), **sweeps([[r[0] for r in c.rows] for c in CURVES[d["selection"]["layout"]](d, pinned.files[:1], [g])], d["acquisition"]["row_order"], ORDER)}))],
                lambda: Pass(Shaped(pinned, g.columns)))


REPLICATE = {   # ([selection] layout, [replicate] identity) -> (may two curves share a slow value, can the reader resolve the identity); total
    **{(lay, k): v for lay in ("PER_FILE", "LONG_TABLE") for k, v in (("NONE", (False, True)), ("SEED", (False, False)), ("RUN", (False, False)), ("SAMPLE", (False, False)),
                                                                     ("SAME_FAST_VALUE", (False, True)))},   # replicate readings of a point, inside one curve
    ("PER_FILE", "FILE"): (True, True),
    ("LONG_TABLE", "FILE"): (False, False),   # one file holds every curve: the file tells no two curves apart
}


POINTS = {   # [replicate] identity -> a curve's rows -> its points as (fast value, readings); total over FORMAT's identities
    **{k: (lambda rows: [(r[0], 1) for r in rows]) for k in ("NONE", "SEED", "RUN", "SAMPLE", "FILE")},   # every row is one point
    "SAME_FAST_VALUE": lambda rows: [(x, len(list(rs))) for x, rs in itertools.groupby(rows, key=lambda r: r[0])],   # a run of one fast value is one point
}


def census(pinned, shaped, t):
    """S5 CENSUS over every file. Invariant: FILE_DIFFERS_FROM_FIRST | SLOW_KEY_UNRESOLVED | REPLICATE_KEY_UNRESOLVED | CURVE_REPEATED (a slow value on two curves:
    two files, or two non-adjacent blocks of a LONG_TABLE) | FAST_VALUE_REPEATED | ACQUISITION_ORDER_DIFFERS, in that order; then the sampling
    label (curves; points per curve min, median, max; the fast span; ALIGNED or MISALIGNED), the same for every layout."""
    d = pinned.declaration.data
    grids = [read(t, d, f) for f in pinned.files]
    rep, acq = REPLICATE[(d["selection"]["layout"], d["replicate"]["identity"])], d["acquisition"]
    other = [f.name for f, g in zip(pinned.files, grids) if g.columns != shaped.columns]
    curves = lambda: CURVES[d["selection"]["layout"]](d, pinned.files, grids)
    hs = lambda: [v for c in curves() for v in c.slow]   # the slow values of every curve that has one (none under NONE)
    unkeyed = lambda: KEYS[d["selection"]["layout"]](d, pinned.files, grids)
    points = lambda c: POINTS[d["replicate"]["identity"]](c.rows)   # grouped BEFORE the repeat check: a run of readings is never a repeat
    twice = lambda: [c.where for c in curves() if len({x for x, _ in points(c)}) != len(points(c))]
    against = lambda: [c.where for c in curves() if not DIRECTION[(acq["row_order"] == "ACQUISITION", acq["direction"])]([r[0] for r in c.rows])]
    again = lambda: [c.where for c in curves() if any(hs().count(v) > 1 for v in c.slow)]
    return gate([(lambda: not other, "FILE_DIFFERS_FROM_FIRST", lambda: detail(words=other[:3], counts={"files": len(other)})),
                 (lambda: not unkeyed(), "SLOW_KEY_UNRESOLVED", lambda: detail(words=unkeyed()[:3] + [f"key '{d['selection']['slow']['key']}'"], counts={"files": len(unkeyed())})),
                 (lambda: rep[1], "REPLICATE_KEY_UNRESOLVED", lambda: detail(words=[f"identity {d['replicate']['identity']}: reader {d['reader']['name']} with layout {d['selection']['layout']} carries no replicate key"])),
                 (lambda: rep[0] or len(set(hs())) == len(hs()), "CURVE_REPEATED", lambda: detail(words=again()[:3], counts={"curves whose slow value another curve has": len(again())})),
                 (lambda: not twice(), "FAST_VALUE_REPEATED", lambda: detail(words=twice()[:3], counts={"curves": len(twice())})),
                 (lambda: not against(), "ACQUISITION_ORDER_DIFFERS", lambda: detail(words=against()[:3] + [f"stored in acquisition order, not {acq['direction']}"], counts={"curves": len(against())}))],
                lambda: Pass(Census(pinned, label(curves(), [points(c) for c in curves()], d["knobs"]["fast"]["name"]), tuple((c.where, len(points(c))) for c in curves()),
                                     tuple(tuple(n for _, n in points(c)) for c in curves()))))


def label(curves, points, fast):
    """The sampling label of curves and their points (fast value, readings), counted per point."""
    ns, xs, rs = [len(p) for p in points], [x for p in points for x, _ in p], [n for p in points for _, n in p]
    seqs = {tuple(x for x, _ in p) for p in points}
    return Sampling(len(curves), sum(len(c.slow) for c in curves), min(ns), statistics.median(ns), max(ns), fast, len(set(xs)),
                    {True: Alignment.ALIGNED, False: Alignment.MISALIGNED}[len(seqs) == 1], (min(rs), max(rs)), max(c.drift for c in curves))


def bodies(t, d):
    """The registered bodies of S4 and S5, closed over the tables (each has its signature row, tests/test_intake.py)."""
    def s4(pinned: Pinned) -> Pass | Refuse:
        return shape(pinned, t)

    def s5(pinned: Pinned, shaped: Shaped) -> Pass | Refuse:
        return census(pinned, shaped, t)
    return {"S4": s4, "S5": s5}
