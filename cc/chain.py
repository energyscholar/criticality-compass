"""chain - plan 1205 P2 (ruling R1, the plan 1201 fix F-a): `bin/cc chain <id> --grid <grid.toml> [--with <id2>]`.
A family at intake S5 (its plane: the curves in slow order and the declared fast window, E0) is read ONCE. Then every cell of a settings grid
(declared as DATA: w_c values x feature lanes, plan 1205 AMENDMENT 1) is evaluated in one pass. No suspect line is read; linenav is not called.
- A LANE is a declared projection in M (intake/POLICY.toml [feature_projection.FEATURE_<lane>]): ARGMAX_FAST and ARGMIN_FAST of the
  observable (intake_feature's projection over the observable, or over its negation for the minimum: a projection's definition, not a pre-A
  transform), and ARGMAX_ABS_A_FAST: the argmax of |A_fast(observable)|, where A_fast is the kernel's A over the declared fast neighbour
  relation (adjacent in-window samples in ascending fast order, edges (j, j+1)) and |.| is a projection after A. Before A only x + c (here c = 0).
- Per curve and cell: the Feature kind (Located | Broad | AtSpanEnd | Absent, intake_feature's KIND table; Broad depends on the cell's w_c),
  the position and bracket in fast span units, the curve rank and slow value.
- Per adjacent pair and cell: one Step atom. Nothing is walked, interpolated or bridged between curves (plan 1205 R3).
- SEGMENTS: the maximal runs of STEP_WITHIN_WC; per lane and cell a FamilyAtom; across the lane's cells a Robustness per segment, by the
  declared identity rule IDENTITY (CONTAINMENT in curve ranks, plan 1205 amendment A1: s recurs in a cell iff that cell holds a segment containing s).
- CO_LOCATION (--with <id2>): a second observable on the same family, per curve, lane and cell, read from <id2>'s own typed result
  (results/chain/<id2>.json, run first under the same grid): one intake run per process (intake_bytes: one loader per run).
The output is typed rows (results/chain/<id>.json) and ONE sentence per lane built from the rows. A segment is a feature line: it is never
a class, so the chain cannot classify (the E412 trap: a crossover ridge chains like any other line). Its words never name a verdict of
linenav or a class (tests/test_chain_1205.py greps the goldens)."""
import enum
import functools
import json
import os
import sys
import tomllib
from dataclasses import dataclass
from pathlib import Path

import numpy as np

import admit
import intake_feature as F
import intake_suspect
import kernel
import navfamily
import navmap
from intake_blind import Typed, bind, gate, look

REFUSAL = {   # code -> sentence; every code this module emits is a row (tests/test_chain_1205.py reaches each)
    "GRID_UNDECLARED": "No settings grid is named: the grid is declared data (--grid <grid.toml>), never a default.",
    "GRID_UNREADABLE": "The grid file is not a TOML table with `wc = [numbers in (0, 1]]` (at least one) and `lanes = [lane names]` (at least one).",
    "LANE_UNDECLARED": "A grid lane has no intake/POLICY.toml [feature_projection.FEATURE_<lane>] row: no projection is used undeclared.",
    "CO_LOCATION_UNRUN": "--with names an id with no results/chain/<id2>.json: run `bin/cc chain <id2> --grid <grid.toml>` first (each intake runs in its own process).",
    "CO_LOCATION_GRID_DIFFERS": "The second id's chain ran under another grid (its grid sha256 differs), so its cells are not this run's cells.",
    "CO_LOCATION_SPANS_DIFFER": "The two observables' planes have different fast spans, so one w_c cannot be read in both.",
}


class Refusal(Typed):
    """A typed refusal of this module. Invariant: `code` is a key of REFUSAL."""
    TABLE = REFUSAL


REFUSED = (*navfamily.REFUSED, Refusal)
NOT_A_CLASS = ("chain cannot classify: a segment is a feature line, never a class (a crossover ridge chains the same as any other line; "
               "the class belongs to the Detector's typed verdict)")


class Lane(enum.Enum):
    """A feature lane. ATOMS: ARGMAX_FAST | ARGMIN_FAST | ARGMAX_ABS_A_FAST. Axiom: a lane is exactly one atom, read literally: the fast
    location of the observable's maximum per curve; of its minimum; of the maximum of |A_fast(observable)| (the steepest step between
    adjacent fast samples)."""
    ARGMAX_FAST = "ARGMAX_FAST"; ARGMIN_FAST = "ARGMIN_FAST"; ARGMAX_ABS_A_FAST = "ARGMAX_ABS_A_FAST"


class Step(enum.Enum):
    """One adjacent pair of curves (ranks k, k + 1 in slow order) in one cell. ATOMS: STEP_WITHIN_WC | STEP_BEYOND_WC | UNMEASURED_BETWEEN.
    Axiom (a partition): UNMEASURED_BETWEEN when either curve's Feature is not Located; else, with d = |position(k + 1) - position(k)| in
    fast span units, STEP_WITHIN_WC when d <= w_c and STEP_BEYOND_WC when d > w_c. <= and > split the reals, so no tie exists."""
    STEP_WITHIN_WC = "STEP_WITHIN_WC"; STEP_BEYOND_WC = "STEP_BEYOND_WC"; UNMEASURED_BETWEEN = "UNMEASURED_BETWEEN"


class FamilyAtom(enum.Enum):
    """One lane in one cell. ATOMS: SEGMENT_SPANS_FAMILY | SEGMENTS_PARTIAL | NO_SEGMENT. Axiom: NO_SEGMENT when the cell has no segment;
    SEGMENT_SPANS_FAMILY when one segment holds every curve rank 0 .. n - 1; SEGMENTS_PARTIAL otherwise (at least one segment, none whole)."""
    SEGMENT_SPANS_FAMILY = "SEGMENT_SPANS_FAMILY"; SEGMENTS_PARTIAL = "SEGMENTS_PARTIAL"; NO_SEGMENT = "NO_SEGMENT"


class Robustness(enum.Enum):
    """How many of a lane's n cells hold a thing (a segment by IDENTITY, or a FamilyAtom): m of n. ATOMS: ROBUST | INTERMEDIATE | FRAGILE.
    Axiom: ROBUST when 4m >= 3n (at least three quarters); else FRAGILE when m = 1 (exactly one cell); else INTERMEDIATE."""
    ROBUST = "ROBUST"; INTERMEDIATE = "INTERMEDIATE"; FRAGILE = "FRAGILE"


class StrideFit(enum.Enum):
    """The declared stride of the edge lane against one curve's in-window samples (m of them, stride k samples; plan 1205 P2b). ATOMS:
    STRIDE_FITS_WINDOW | STRIDE_EXCEEDS_WINDOW. Axiom: STRIDE_FITS_WINDOW when the relation {(i, i + k)} holds at least 3 edges (m - k >= 3),
    else STRIDE_EXCEEDS_WINDOW: a typed cell, never a skipped one. (A curve with fewer than 4 in-window samples has no edge lane at any stride:
    it stays Absent, as in v3.)"""
    STRIDE_FITS_WINDOW = "STRIDE_FITS_WINDOW"; STRIDE_EXCEEDS_WINDOW = "STRIDE_EXCEEDS_WINDOW"


class CoLocation(enum.Enum):
    """One curve, lane and cell, read in two observables of one family. ATOMS: CO_LOCATED | APART_BEYOND_WC | NOT_COMPARABLE. Axiom:
    NOT_COMPARABLE when the curve's slow value is not a curve of both, or either Feature is not Located; else, with d = |position_1 -
    position_2| in fast span units, CO_LOCATED when d <= w_c and APART_BEYOND_WC when d > w_c. (The plan's first name for the middle atom,
    NOT_CO_LOCATED, reads by the binding rule as the complement of CO_LOCATED, which also holds NOT_COMPARABLE: two atoms, so it was renamed.)"""
    CO_LOCATED = "CO_LOCATED"; APART_BEYOND_WC = "APART_BEYOND_WC"; NOT_COMPARABLE = "NOT_COMPARABLE"


STEP = {(False, False): Step.UNMEASURED_BETWEEN, (False, True): Step.UNMEASURED_BETWEEN,   # (both Located, d <= w_c) -> Step; total
        (True, True): Step.STEP_WITHIN_WC, (True, False): Step.STEP_BEYOND_WC}
FAMILY = {(False, False): FamilyAtom.NO_SEGMENT, (False, True): FamilyAtom.NO_SEGMENT,   # (any segment, one spans 0 .. n - 1) -> atom; (False, True) is empty
          (True, True): FamilyAtom.SEGMENT_SPANS_FAMILY, (True, False): FamilyAtom.SEGMENTS_PARTIAL}
ROBUST = {(True, True): Robustness.ROBUST, (True, False): Robustness.ROBUST,   # (4m >= 3n, m == 1) -> Robustness; total
          (False, True): Robustness.FRAGILE, (False, False): Robustness.INTERMEDIATE}
CO = {(False, False): CoLocation.NOT_COMPARABLE, (False, True): CoLocation.NOT_COMPARABLE,   # (both Located, d <= w_c) -> CoLocation; total
      (True, True): CoLocation.CO_LOCATED, (True, False): CoLocation.APART_BEYOND_WC}
FIT = {True: StrideFit.STRIDE_FITS_WINDOW, False: StrideFit.STRIDE_EXCEEDS_WINDOW}   # (m - k >= 3) -> StrideFit; total
IDENTITY = ("a segment s = [lo, hi] of a lane in a cell RECURS in another cell of the lane iff that cell holds a segment [lo', hi'] with lo' <= lo and hi <= hi' "
            "(CONTAINMENT in curve ranks); m(s) counts the lane's cells in which s recurs, its own included")


def contained(a, b):
    """The declared identity rule IDENTITY over curve-rank ranges (lo, hi), inclusive: a is contained in b (b's range holds every rank of a)."""
    return b[0] <= a[0] and a[1] <= b[1]


@dataclass(frozen=True)
class Stride:
    """One declared stride of the fast relation {(i, i + k)}: `samples` (k as declared) or `span` (a fraction of the fast span, k = that
    fraction of the curve's in-window sample intervals, rounded to the nearest sample, at least 1). Exactly one of the two is not None."""
    samples: object = None
    span: object = None

    def k(self, m):
        """k in samples for a curve of m in-window samples (m - 1 intervals)."""
        return {True: lambda: max(1, int(self.samples)), False: lambda: max(1, int(np.floor(self.span * max(m - 1, 0) + 0.5)))}[self.samples is not None]()

    @property
    def label(self):
        return {True: lambda: f"{self.samples}smp", False: lambda: f"{self.span:g}span"}[self.samples is not None]()


S1 = Stride(samples=1)   # the v3 lane: adjacent samples


@dataclass(frozen=True)
class Placed:
    """One curve's Feature in one lane and cell: kind (an intake_feature kind NAME), the curve's own sample ranks (rank, lo, hi; an edge
    lane's are its first sample: edge j joins samples j and j + 1), the position and bracket in fast span units (None when Absent)."""
    kind: str
    rank: int
    lo: int
    hi: int
    pos: object
    bracket: object
    k: int = 1   # the edge lane's stride in samples (1 for the sample lanes)
    frac: object = None   # k as a fraction of the curve's in-window sample intervals (the edge lane only)


def _sample_lane(sign):
    """ARGMAX_FAST (sign +1) or ARGMIN_FAST (sign -1): intake_feature's projection of the observable (sign x: the minimum is the maximum of
    -x, the projection's definition), with its own bracket and KIND table."""
    def lane(rows, z, kind, wc, sp, ends, stride=S1):
        a = sorted(rows, key=lambda r: r[0])
        f = F.feature([(r[0], sign * r[1], *r[2:]) for r in rows], z, kind, wc, sp.width[1], ends)
        u = lambda i: (a[i][0] - sp.lo[1]) / sp.width[1]   # noqa: E731
        return {True: lambda: Placed("Absent", -1, f.lo, f.hi, None, None),
                False: lambda: Placed(type(f).__name__, f.rank, f.lo, f.hi, u(f.rank), (u(f.lo), u(f.hi)))}[isinstance(f, F.Absent)]()
    return lane


def _edges(a, i, z, kind, wc, sp, k):
    """The |A_fast| feature over the in-window samples a[i] (>= 4), over the declared relation {(j, j + k)}: m - k >= 3 edges."""
    w = np.asarray(a, float)[i]
    m = len(w)
    rel = admit.declare(m, [(j, j + k) for j in range(m - k)], [kernel.Provenance.CONTINUATION] * (m - k))
    g = np.abs(kernel.A(admit.nodefield(w[:, 1]), rel).spatial[0])   # A over the declared fast relation; |.| is a projection after A
    s = F.SIGMA_COL[kind](w)
    se = np.sqrt(s[:-k] ** 2 + s[k:] ** 2)   # an edge's sigma: of a difference of two independent readings
    place = (w[:-k, 0] + w[k:, 0]) / 2   # an edge's place: the midpoint of its two measured fast values (its coordinate, no value is formed)
    r = int(np.argmax(g))
    lo, hi, _ = F.BRACKET[kind](g, se, z, r)
    kd = F.KIND[(lo == 0 or hi == len(g) - 1, (place[hi] - place[lo]) / sp.width[1] > wc)]
    u = lambda e: (place[e] - sp.lo[1]) / sp.width[1]   # noqa: E731
    return Placed(kd.__name__, int(i[0] + r), int(i[0] + lo), int(i[0] + hi), u(r), (u(lo), u(hi)), k, k / (m - 1))


def _edge_lane(rows, z, kind, wc, sp, ends, stride=S1):
    a = sorted(rows, key=lambda r: r[0])
    i = np.flatnonzero([ends[0] <= r[0] <= ends[1] for r in a])
    k = stride.k(len(i))
    absent = lambda name: Placed(name, -1, 0, len(a) - 1, None, None, k)   # noqa: E731
    fit = FIT[len(i) - k >= 3]
    return {(True, StrideFit.STRIDE_FITS_WINDOW): lambda: _edges(a, i, z, kind, wc, sp, k),
            (True, StrideFit.STRIDE_EXCEEDS_WINDOW): lambda: absent(fit.name),
            (False, StrideFit.STRIDE_FITS_WINDOW): lambda: absent("Absent"),
            (False, StrideFit.STRIDE_EXCEEDS_WINDOW): lambda: absent("Absent")}[(len(i) >= 4, fit)]()


LANES = {Lane.ARGMAX_FAST: _sample_lane(1.0), Lane.ARGMIN_FAST: _sample_lane(-1.0), Lane.ARGMAX_ABS_A_FAST: _edge_lane}   # total over Lane


def located(p):
    return p.kind == "Located"


def steps(placed, wc):
    """One Step per adjacent pair (k, k + 1) of the curves' Placed features (slow order), by the table STEP."""
    d = lambda a, b: abs(b.pos - a.pos) <= wc   # noqa: E731
    return [STEP[(located(a) and located(b), located(a) and located(b) and d(a, b))] for a, b in zip(placed, placed[1:])]


def segments(st):
    """The maximal runs of STEP_WITHIN_WC as curve-rank ranges (lo, hi): a run of pairs j .. j' holds the curves j .. j' + 1."""
    w = np.diff(np.concatenate(([0], [int(s is Step.STEP_WITHIN_WC) for s in st], [0])))
    return [(int(a), int(b)) for a, b in zip(np.flatnonzero(w == 1), np.flatnonzero(w == -1))]


def family_atom(segs, n):
    return FAMILY[(len(segs) > 0, (0, n - 1) in segs)]


def robustness(m, n):
    return ROBUST[(4 * m >= 3 * n, m == 1)]


@dataclass(frozen=True)
class Grid:
    """The declared settings grid: the w_c values (fast span units) and the lanes, in declared order; its source file's sha256."""
    wc: tuple
    lanes: tuple
    sha256: str
    strides: tuple = ()   # plan 1205 P2b: the edge lane's declared strides (Stride), () = the v3 grid (stride 1 sample, no stride in the output)


def keys(g, lane):
    """A lane's cell keys in declared order: a w_c float, or (Stride, w_c) for the edge lane when the grid declares strides."""
    return {True: lambda: [(s, w) for s in g.strides for w in g.wc], False: lambda: list(g.wc)}[lane is Lane.ARGMAX_ABS_A_FAST and len(g.strides) > 0]()


def wc_of(key):
    return {True: lambda: key[1], False: lambda: key}[isinstance(key, tuple)]()


def stride_of(key):
    return {True: lambda: key[0], False: lambda: S1}[isinstance(key, tuple)]()


def grid(path):
    """The grid in the file at `path`, or Refusal GRID_UNDECLARED (no file named) / GRID_UNREADABLE."""
    p = Path(path or "").resolve()
    data = {True: lambda: _toml(p), False: lambda: None}[bool(path) and p.is_file()]()
    wcs, lanes = (data or {}).get("wc"), (data or {}).get("lanes")
    ss, sp_ = (data or {}).get("stride_samples"), (data or {}).get("stride_span")
    num = lambda x: isinstance(x, (int, float)) and not isinstance(x, bool)   # noqa: E731
    sok = ((ss is None or (isinstance(ss, list) and len(ss) > 0 and all(isinstance(x, int) and not isinstance(x, bool) and x >= 1 for x in ss)))
           and (sp_ is None or (isinstance(sp_, list) and len(sp_) > 0 and all(num(x) and 0 < x <= 1 for x in sp_))))
    strides = tuple(Stride(samples=x) for x in ss or ()) + tuple(Stride(span=float(x)) for x in sp_ or ())
    ok = (sok and isinstance(wcs, list) and len(wcs) > 0 and all(isinstance(x, (int, float)) and not isinstance(x, bool) and 0 < x <= 1 for x in wcs)
          and isinstance(lanes, list) and len(lanes) > 0 and all(isinstance(x, str) and x in Lane.__members__ for x in lanes))
    return {(False, False): lambda: Refusal("GRID_UNDECLARED", "no --grid <file>"), (False, True): lambda: Refusal("GRID_UNDECLARED", "no --grid <file>"),
            (True, False): lambda: Refusal("GRID_UNREADABLE", p.name),
            (True, True): lambda: Grid(tuple(float(x) for x in wcs), tuple(Lane[x] for x in lanes), _sha(p), strides)}[(bool(path), ok)]()


def _toml(p):
    try:
        return tomllib.loads(p.read_text())
    except (tomllib.TOMLDecodeError, UnicodeDecodeError):   # plumbing: an unreadable grid is the typed GRID_UNREADABLE
        return None


def _sha(p):
    import hashlib
    return hashlib.sha256(p.read_bytes()).hexdigest()


@dataclass(frozen=True)
class Family:
    """One family's plane, read once: curves (census objects, slow order), their slow values, the Span, the domain ends, Z and the sigma kind."""
    ident: str
    curves: tuple
    slows: tuple
    span: F.Span
    ends: tuple
    z: float
    kind: str
    unit: str


def family(root, ident):
    """The Family of a declaration (its intake run to S5, its plane under [plane]), or the first typed refusal."""
    tcs = then(navfamily.declared(root, ident), lambda i: navfamily.census(root, i))
    p = then(tcs, lambda x: intake_suspect.plane(x[0], x[1]))
    return then(p, lambda pl: _family(ident, tcs[0], tcs[1].pinned.declaration.data, pl))


def _family(ident, t, d, p):
    cs = p.source
    return Family(ident, cs, tuple(float(c.slow[0]) for c in cs), F.span(cs, p.window), F.FAST_ENDS[p.window is None](cs, p.window),
                  t["policy"]["policy"]["tier_z"], d["measured"]["uncertainty"]["kind"], look(look(d, "knobs", {}), "slow", {}).get("unit", ""))


def undeclared(t, g):
    """Refusal LANE_UNDECLARED naming the grid's lanes POLICY has no row for, or None."""
    miss = [ln.name for ln in g.lanes if f"FEATURE_{ln.name}" not in look(t["policy"], "feature_projection", {})]
    return {True: lambda: None, False: lambda: Refusal("LANE_UNDECLARED", ", ".join(f"FEATURE_{m}" for m in miss))}[len(miss) == 0]()


def evaluate(fam, g):
    """Every cell of the grid over the family read once: {lane: {key: (placed per curve, steps, segments, atom)}}; key = keys(g, lane)."""
    def cell(lane, key):
        wc = wc_of(key)
        placed = [LANES[lane](c.rows, fam.z, fam.kind, wc, fam.span, fam.ends, stride_of(key)) for c in fam.curves]
        st = steps(placed, wc)
        segs = segments(st)
        return placed, st, segs, family_atom(segs, len(placed))
    return {lane: {key: cell(lane, key) for key in keys(g, lane)} for lane in g.lanes}


def colocate(a, b, wc):
    """CoLocation per curve of `a` (curve rows {slow, kind, position} of two observables in one lane and cell; partners by slow value)."""
    other = {c["slow"]: c for c in b}
    both = lambda p, q: p["kind"] == "Located" and q is not None and q["kind"] == "Located"   # noqa: E731
    return [CO[(both(p, other.get(p["slow"])), both(p, other.get(p["slow"])) and abs(p["position"] - other[p["slow"]]["position"]) <= wc)] for p in a]


def stride_row(key):
    """The stride fields of an edge-lane cell that has a stride axis (none for any other cell): the declared stride, and per curve its k in
    samples and as a fraction of the fast span."""
    return {True: lambda: {"stride": key[0].label, "stride_declared": {"samples": key[0].samples, "span": key[0].span}}, False: lambda: {}}[isinstance(key, tuple)]()


def curve_stride(key, p):
    return {True: lambda: {"stride_samples": p.k, "stride_span": p.frac}, False: lambda: {}}[isinstance(key, tuple)]()


def label(c):
    """A cell's name in a sentence: its w_c, and its stride when the cell has one."""
    return f"{c['wc']:g}" + {True: lambda: f"@{c['stride']}", False: lambda: ""}["stride" in c]()


def rows(fam, g, ev):
    """The typed rows: the grid, per (lane, cell) the curves, steps, segments with robustness, the family atom; per lane the atom robustness."""
    n = {lane: len(keys(g, lane)) for lane in g.lanes}
    seg_m = lambda lane, s: sum(any(contained(s, o) for o in ev[lane][k][2]) for k in keys(g, lane))   # noqa: E731
    cells = [{"lane": lane.name, "wc": wc_of(key), **stride_row(key), "family": ev[lane][key][3].name,
              "curves": [{"rank": k, "slow": fam.slows[k], "kind": p.kind, "sample_ranks": [p.rank, p.lo, p.hi], "position": p.pos,
                          "bracket": list(p.bracket) if p.bracket else None, **curve_stride(key, p)} for k, p in enumerate(ev[lane][key][0])],
              "steps": [{"pair": [k, k + 1], "slow": [fam.slows[k], fam.slows[k + 1]], "step": s.name,
                         "d": abs(ev[lane][key][0][k + 1].pos - ev[lane][key][0][k].pos) if s is not Step.UNMEASURED_BETWEEN else None}
                        for k, s in enumerate(ev[lane][key][1])],
              "segments": [{"ranks": [lo, hi], "slow": [fam.slows[lo], fam.slows[hi]], "curves": hi - lo + 1,
                            "family_fraction": (hi - lo + 1) / len(fam.slows), "cells": seg_m(lane, (lo, hi)),
                            "robustness": robustness(seg_m(lane, (lo, hi)), n[lane]).name} for lo, hi in ev[lane][key][2]]}
             for lane in g.lanes for key in keys(g, lane)]
    atoms = {lane.name: {a.name: {"cells": sum(ev[lane][k][3] is a for k in keys(g, lane)), "robustness": robustness(sum(ev[lane][k][3] is a for k in keys(g, lane)), n[lane]).name}
                         for a in FamilyAtom if any(ev[lane][k][3] is a for k in keys(g, lane))} for lane in g.lanes}
    return cells, atoms


def sentence(fam, g, lane, cells, atoms):
    """ONE sentence per lane, assembled from the typed rows only."""
    mine = [c for c in cells if c["lane"] == lane.name]
    u = fam.unit
    nl = len(mine)
    seg = lambda s: f"{s['slow'][0]:g} -> {s['slow'][1]:g} {u} ({s['curves']} curves, in {s['cells']} of {nl} cells, {s['robustness']})"   # noqa: E731
    per = "; ".join(f"w_c {label(c)}: {c['family']}" + "".join(f", feature line segment {seg(s)}" for s in c["segments"]) for c in mine)
    breaks = {}
    [breaks.setdefault((st["step"], st["slow"][0], st["slow"][1]), []).append(label(c)) for c in mine for st in c["steps"] if st["step"] != "STEP_WITHIN_WC"]
    br = "; ".join(f"{k[0]} at {k[1]:g}|{k[2]:g} {u} (w_c {', '.join(v)})" for k, v in breaks.items()) or "none"
    at = ", ".join(f"{a} in {v['cells']} of {nl} cells ({v['robustness']})" for a, v in atoms[lane.name].items())
    axes = {True: lambda: f"{nl} cells ({len(g.strides)} strides x {len(g.wc)} w_c)", False: lambda: f"{nl} w_c cells"}["stride" in mine[0]]()
    return (f"Lane {lane.name} over {len(fam.slows)} curves ({fam.slows[0]:g} -> {fam.slows[-1]:g} {u}), {axes}: {at}. "
            f"Per cell, {per}. Breaks: {br}. Nothing is walked or bridged between curves; {NOT_A_CLASS}.")


def co_rows(cells, other):
    """Per (lane, cell) of this run, the CoLocation of each curve against the same cell of the second id's result `other`."""
    theirs = {(c["lane"], c["wc"], c.get("stride")): c["curves"] for c in other["cells"]}
    return [{"lane": c["lane"], "wc": c["wc"], **({"stride": c["stride"]} if "stride" in c else {}), "with": other["id"],
             "curves": [{"slow": p["slow"], "co_location": x.name} for p, x in zip(c["curves"], colocate(c["curves"], theirs[(c["lane"], c["wc"], c.get("stride"))], c["wc"]))]}
            for c in cells]


def logged(root, ident):
    """The chain's access log (append-only): one JSON line per open of this process, as navfamily.logged writes its own (T23)."""
    return navmap.hook_log(Path(root) / "results" / "chain" / f"{ident}.access.jsonl",
                           dict(partition=f"chain:{ident}", argv=sys.argv[1:], pid=os.getpid(), git_head=navmap._head(root), route="open:chain"))


def _second(root, fam, other, g):
    """The second id's typed result (results/chain/<id2>.json), or the first refusal: unrun, another grid, another fast span."""
    p = Path(root) / "results" / "chain" / f"{other}.json"
    doc = {True: lambda: json.loads(p.read_text()), False: lambda: None}[p.is_file() and other not in ("", fam.ident)]()
    return gate_rows([(lambda: doc is not None, "CO_LOCATION_UNRUN", f"results/chain/{other}.json"),
                      (lambda: doc["grid"]["sha256"] == g.sha256, "CO_LOCATION_GRID_DIFFERS", f"{other}: grid {doc and doc['grid']['sha256'][:12]}; this run {g.sha256[:12]}"),
                      (lambda: doc["fast_span"] == [fam.span.lo[1], fam.span.width[1]], "CO_LOCATION_SPANS_DIFFER", f"{fam.ident} vs {other}")], doc)


def gate_rows(rows, then):
    """`then` when every (holds, code, detail) row holds (lazily, in order), else the Refusal of the first that does not."""
    return gate([(h, c, (lambda d=d: d)) for h, c, d in rows], lambda: then, Refusal)


then = functools.partial(bind, kinds=REFUSED)   # f(x), unless x is already a typed refusal (it passes through unchanged)


def run(root, ident, grid_path, other=None):
    """(lines, exit status) of `bin/cc chain <id> --grid <grid.toml> [--with <id2>]`."""
    t_have = then(navfamily.declared(root, ident), lambda i: (logged(root, i), i)[1])
    g = then(t_have, lambda _: grid(grid_path))
    fam = then(g, lambda _: family(root, ident))
    lanes = then(fam, lambda _: undeclared(_tables(root), g) or fam)
    fb = then(lanes, lambda f: {True: lambda: None, False: lambda: _second(root, f, other, g)}[other is None]())
    bad = [x for x in (t_have, g, fam, lanes, fb) if isinstance(x, REFUSED)]
    return {True: lambda: ([f"REFUSED {bad[0].words()}"], 1), False: lambda: _done(root, fam, g, fb)}[len(bad) > 0]()


def _tables(root):
    import intake
    return intake.tables(root)


def _done(root, fam, g, fb):
    ev = evaluate(fam, g)
    cells, atoms = rows(fam, g, ev)
    co = {True: lambda: [], False: lambda: co_rows(cells, fb)}[fb is None]()
    out = Path(root) / "results" / "chain" / f"{fam.ident}.json"
    doc = {"schema": 1, "kind": "chain", "id": fam.ident, "grid": {"wc": list(g.wc), "lanes": [ln.name for ln in g.lanes], "sha256": g.sha256,
                    **({"strides": [{"label": x.label, "samples": x.samples, "span": x.span} for x in g.strides]} if g.strides else {})},
           "identity_rule": IDENTITY, "limit": NOT_A_CLASS, "slow_unit": fam.unit,
           "fast_span": [fam.span.lo[1], fam.span.width[1]], "cells": cells, "family_atoms": atoms, "co_location": co}
    out.write_text(json.dumps(doc, indent=1) + "\n")
    lines = [f"chain {fam.ident}: {len(fam.slows)} curves in slow order; fast span [{fam.span.lo[1]:g}, {fam.span.lo[1] + fam.span.width[1]:g}]; "
             f"grid {len(g.wc)} w_c x {len(g.lanes)} lanes{f' x {len(g.strides)} strides (edge lane)' if g.strides else ''} (sha256 {g.sha256[:12]}), the data read once",
             *[f"cell {c['lane']} w_c {label(c)}: {c['family']}; steps " + " ".join(s["step"] for s in c["steps"]) + "; kinds " + " ".join(x["kind"] for x in c["curves"]) for c in cells],
             *[f"co-location {c['lane']} w_c {label(c)} with {c['with']}: " + " ".join(x["co_location"] for x in c["curves"]) for c in co],
             *[sentence(fam, g, lane, cells, atoms) for lane in g.lanes],
             f"results: results/chain/{fam.ident}.json (typed rows: per cell the curves, steps, segments with robustness; per lane the family atoms)"]
    return lines, 0
