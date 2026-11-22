"""intake_census - S4 SHAPE and S5 CENSUS of the intake: the pinned files through the declared reader, cut into curves and counted.
Invariant: it reads bytes only from a Pinned (what S3 read), never from a path, and its tables are total over FORMAT's alphabets; it
constructs no Path and opens nothing, and it holds counts and names, never a value, in what it passes on."""
import functools
import itertools
import re
import statistics

import numpy as np

import intake_against
import intake_read
from intake_blind import NUMBER, RESTARTS, SWEEP, Pass, Refuse, detail, gate, numbered, sweeps
from intake_names import exits, repeats
from intake_differs import DIFFERS, differs
from intake_evidence import Alignment, Census, Curve, Pinned, Sampling, Shaped


def read(t, d, f):
    """One pinned file through the declaration's reader: intake_read.Grid | intake_read.Unreadable (never an exception)."""
    return intake_read.readers(t)[d["reader"]["name"]](f.data, d)


NAMING = lambda d: [i for i, (k, _) in enumerate(intake_read.role_columns(d)) if k in ("replicate", "slow")]   # the role columns that name a curve
BREAK = {   # LONG_TABLE [selection] block -> (the declaration) -> (previous rows, rows: arrays, one row each) -> does a new curve begin at each row; total over FORMAT's blocks
    "EXACT": lambda d: lambda p, r: np.any(p[:, NAMING(d)] != r[:, NAMING(d)], axis=1),   # the slow value or (1160 A33) a replicate column changes
    "FAST_RESTART": lambda d: lambda p, r: RESTARTS[SWEEP[d["acquisition"]["row_order"]](d["acquisition"])](p[:, 0], r[:, 0]),   # the fast knob turns back (S1: it has a direction)
}


def _blocks(f, g, d):
    """LONG_TABLE: the blocks of consecutive rows the declared block rule (BREAK) cuts the file into, in file order, each one Curve whose slow
    value is its FIRST row's (a value as measured, never a mean). (plan 1205 P1) The cut is one vectorised comparison of every row with its
    predecessor, never a row-by-row walk: the same blocks, at the size of a 4,000,000-row table."""
    a = np.array(g.rows, dtype=float).reshape(len(g.rows), -1)
    at = np.flatnonzero(np.concatenate([[True], BREAK[d["selection"]["block"]](d)(a[:-1], a[1:])]))
    ends = np.concatenate([at[1:], [len(a)]])
    return [Curve(f"{f.name} block {i}", (g.rows[b][-1],), g.rows[b:e], len(np.unique(a[b:e, -1]))) for i, (b, e) in enumerate(zip(at.tolist(), ends.tolist()), 1)]


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
    "replicate": lambda d: "dimensionless",   # (1160 A33) a replicate column names a run, a seed or a sample by a number: a count, no unit
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


ONE = lambda d, c: ""   # (1160 A33) no key: every curve has the same one, so a slow value on two curves is CURVE_REPEATED
NO = lambda d, c: None   # one file holds every curve: its name tells no two apart (REPLICATE_KEY_UNRESOLVED)
FIELD = lambda d, c: dict(enumerate(re.split(re.escape(d["replicate"]["key"]["separator"]), re.sub(r"\.[^.]*$", "", c.where)), 1)).get(d["replicate"]["key"]["field"])
CELL = lambda d, c: (lambda vs: {1: min(vs, default=None)}.get(len(vs)))({r[[k for k, _ in intake_read.role_columns(d)].index("replicate")] for r in c.rows})
DECLARED = {   # (1160 A33) [replicate.key] kind -> [selection] layout -> (declaration, curve) -> its key, None when the declared key is absent from
    "NONE": {"PER_FILE": ONE, "LONG_TABLE": ONE},   # it (no such field in the file name; not one value in the column); total over FORMAT's
    "FILE_NAME": {"PER_FILE": FIELD, "LONG_TABLE": NO},
    "COLUMN": {"PER_FILE": CELL, "LONG_TABLE": CELL},
}
KEYED = {   # [replicate] identity -> ([selection] layout, [replicate.key] kind) -> (declaration, curve) -> its replicate key | None; total over FORMAT's
    **{k: (lambda lay, kind: ONE) for k in ("NONE", "SAME_FAST_VALUE")},   # SAME_FAST_VALUE: replicate readings of a point, inside one curve
    "FILE": lambda lay, kind: {"PER_FILE": lambda d, c: c.where, "LONG_TABLE": NO}[lay],   # the file name (the 1160 P2 rule)
    **{k: (lambda lay, kind: DECLARED[kind][lay]) for k in ("SEED", "RUN", "SAMPLE")},   # (1160 A33: was unresolved on every layout)
}


IDENTITIES = ("NONE", "SEED", "RUN", "SAMPLE", "FILE", "SAME_FAST_VALUE")   # FORMAT's [replicate] identity alphabet
POINTS = {   # ([knobs.fast] control, [replicate] identity) -> a curve's rows -> its points as (key, fast value, readings); total over FORMAT's (plan 1160 A17)
    **{("SET", k): (lambda rows: [(r[0], r[0], 1) for r in rows]) for k in IDENTITIES[:5]},   # a set knob: every row one point, keyed by its fast value
    ("SET", "SAME_FAST_VALUE"): lambda rows: [(x, x, len(list(rs))) for x, rs in itertools.groupby(rows, key=lambda r: r[0])],   # a run of one fast value is one point
    **{("MEASURED", k): (lambda rows: [(i, r[0], 1) for i, r in enumerate(rows)]) for k in IDENTITIES},   # a measured knob: every row a point, keyed by its ordinal (S1 admits NONE only)
}


def census(pinned, shaped, t):
    """S5 CENSUS over every file. Invariant: FILE_DIFFERS_FROM_FIRST | SLOW_KEY_UNRESOLVED | REPLICATE_KEY_UNRESOLVED | CURVE_REPEATED (a slow value on two curves:
    two files, or two non-adjacent blocks of a LONG_TABLE) | FAST_VALUE_REPEATED | ACQUISITION_ORDER_DIFFERS, in that order; then the sampling
    label (curves; points per curve min, median, max; the fast span; ALIGNED or MISALIGNED), the same for every layout."""
    d = pinned.declaration.data
    grids = [read(t, d, f) for f in pinned.files]
    key, acq = KEYED[d["replicate"]["identity"]](d["selection"]["layout"], d["replicate"]["key"]["kind"]), d["acquisition"]
    other = [f.name for f, g in zip(pinned.files, grids) if g.columns != shaped.columns]
    what = [differs(pinned.files[0].data, f.data, d) for f, g in zip(pinned.files, grids) if g.columns != shaped.columns]   # 1160 A34: what each differs in
    curves = functools.cache(lambda: CURVES[d["selection"]["layout"]](d, pinned.files, grids))   # (plan 1205 P1) cut once: every clause below reads the same curves
    unkeyed = lambda: KEYS[d["selection"]["layout"]](d, pinned.files, grids)
    points = lambda c: POINTS[(d["knobs"]["fast"]["control"], d["replicate"]["identity"])](c.rows)   # grouped BEFORE the repeat check: a run of readings is never a repeat
    twice = lambda: [c.where for c in curves() if len({k for k, _, _ in points(c)}) != len(points(c))]
    kinds = lambda: repeats([[k for k, _, _ in points(c)] for c in curves() if c.where in twice()])   # A17: the repeat kinds, counts only
    against = lambda: [c.where for c in curves() if not DIRECTION[(acq["row_order"] == "ACQUISITION", acq["direction"])]([r[0] for r in c.rows])]
    named = lambda: [(c, key(d, c)) for c in curves()]   # (1160 A33) each curve with its replicate key
    unnamed = lambda: [c.where for c, k in named() if k is None]
    pairs = lambda: [(v, k) for c, k in named() for v in c.slow]   # (slow value, replicate key): a curve's place; two curves may share one only as replicates
    again = lambda: [c.where for c, k in named() if any(pairs().count((v, k)) > 1 for v in c.slow)]
    return gate([(lambda: not other, "FILE_DIFFERS_FROM_FIRST", lambda: detail(words=other[:3] + [f"{k}: {DIFFERS[k]}" for k in DIFFERS if k in what],
                                                                                 counts={"files": len(other), **{k: what.count(k) for k in DIFFERS if k in what}})),
                 (lambda: not unkeyed(), "SLOW_KEY_UNRESOLVED", lambda: detail(words=unkeyed()[:3] + [f"key '{d['selection']['slow']['key']}'"], counts={"files": len(unkeyed())})),
                 (lambda: not unnamed(), "REPLICATE_KEY_UNRESOLVED", lambda: detail(words=unnamed()[:3] + [f"identity {d['replicate']['identity']}, key {d['replicate']['key']['kind']}, layout {d['selection']['layout']}: no replicate key"], counts={"curves": len(unnamed()), "of": len(curves())})),
                 (lambda: len(set(pairs())) == len(pairs()), "CURVE_REPEATED", lambda: detail(words=again()[:3], counts={"curves whose slow value another curve has": len(again())})),
                 (lambda: not twice(), "FAST_VALUE_REPEATED", lambda: detail(words=twice()[:3] + exits(kinds()), counts={"curves refused": len(twice()), "of curves": len(curves()), **kinds()})),
                 (lambda: not against(), "ACQUISITION_ORDER_DIFFERS", lambda: detail(words=against()[:3] + [f"stored in acquisition order, not {acq['direction']}"], counts={"curves": len(against())}))],
                lambda: Pass(Census(pinned, label(curves(), [points(c) for c in curves()], d["knobs"]["fast"]["name"]), tuple((c.where, len(points(c))) for c in curves()),
                                     tuple(tuple(n for _, _, n in points(c)) for c in curves()))))


def label(curves, points, fast):
    """The sampling label of curves and their points (key, fast value, readings), counted per point."""
    ns, xs, rs = [len(p) for p in points], [x for p in points for _, x, _ in p], [n for p in points for _, _, n in p]
    seqs = {tuple(x for _, x, _ in p) for p in points}
    return Sampling(len(curves), sum(len(c.slow) for c in curves), min(ns), statistics.median(ns), max(ns), fast, len(set(xs)),
                    Alignment.ALIGNED if len(seqs) == 1 else Alignment.MISALIGNED, (min(rs), max(rs)), max(c.drift for c in curves))


def bodies(t, d):
    """The registered bodies of S4 and S5, closed over the tables (each has its signature row, tests/test_intake.py)."""
    def s4(pinned: Pinned) -> Pass | Refuse:
        return intake_against.unpredicted(pinned, shape(pinned, t))   # plan 1165: a refusal the profile should have predicted says so

    def s5(pinned: Pinned, shaped: Shaped) -> Pass | Refuse:
        return intake_against.unpredicted(pinned, census(pinned, shaped, t))
    return {"S4": s4, "S5": s5}
