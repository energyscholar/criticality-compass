"""intake_feature - plan 1176 phase B (ruling R1): the per-curve feature, a declared projection in M, and the real-data side oracle over it
(role intake_feature with its own cap, tests/test_budget.py FEATURE_CAP, so CORE_CAP stays 1200).
The projection (POLICY [feature_projection.FEATURE_ARGMAX_FAST]) gives each curve one typed Feature: Located(rank, lo, hi) | Broad | AtSpanEnd | Absent.
E0: its DOMAIN is the declared [plane.fast_window] if any (else the span); no curve is edited, a window edge IS a span end. rank is the argmax
sample rank (samples in ascending fast order, ties to the first); [lo, hi] is the sigma-plateau, the maximal run of consecutive samples around rank
whose value + Z sigma >= max - Z sigma_max (Z = POLICY's tier_z): a declared interval, never a guard. With no sigma column the bracket is [rank,
rank] and the tiering UNTIERED (reported, not refused). AtSpanEnd when lo = 0 or hi = n - 1; Absent when n < 3. Broad (plan 1176 C', ruling 10-20;
C'' in span units) when the interior bracket is WIDER THAN w_c of the fast span (its END SAMPLES' fast values farther apart than w_c x the plane's
fast span width): a point's uncertainty is never larger than the verdict's tolerance, so a Broad curve sides nowhere (UNRES). w_c is the frozen
linenav PARAMS[corridor]["wc"] of the declared [suspect] corridor word, never a knob here. The cross-curve relation is the declared slow order of
the curves (curve rank = 0-based slow order). The plane (C'', O4): the declared knobs' physical units, each normalised to its declared span by the
declared affine coordinate map Span (POLICY [coordinate.PLANE_SPAN_UNIT]), a coordinate map, never a value transform; linenav reads it in CONTINUOUS
mode on [0, 1] x [0, 1]. At a point u: the NEAREST CURVE by slow (a tie to the lower rank), then the ORDER of u's fast against that curve's bracket
END SAMPLE values (Below | Inside | Above; outside the curve's measured span OffSpan). Nothing between measured points is formed: a side changes
only at a sample. On output a located point is re-projected to its ENCLOSING MEASURED PAIR (Oracle.measured, Oracle.ranks). The oracle answers
linenav's side alphabet {NEG, POS, MID, UNRES, SINGLE} by member NAME from SIDE, total over FEATURES x LOCI (one-curve family: SINGLE). Its evidence
is always FiniteStored(source = "<declaration id>:<seal hash>"), never Sharp. It reads only the Census object (the pinned bytes it carries) and the
tables as values: it constructs no Path and opens nothing."""
import enum
from dataclasses import dataclass

import numpy as np

import intake_census
import linenav
from intake_blind import look
from intake_seal import SealStatus

KEY = "FEATURE_ARGMAX_FAST"   # the POLICY row this projection cites (intake/POLICY.toml [feature_projection])
SPAN_KEY = "PLANE_SPAN_UNIT"   # the POLICY row the plane's coordinate map cites (intake/POLICY.toml [coordinate]; plan 1176 C'')


Side, FiniteStored = linenav.Side, linenav.FiniteStored   # plan 1176 D (B-E3): linenav's own alphabet and evidence class (cc/linenav.py, frozen
# v2.1-T), no stand-in: the oracle reads SIDE's names through its `alphabet` (default linenav.Side); FiniteStored(source) is the class of a
# finite-size reader of STORED data, so it can never claim the line ends, and the oracle's evidence is never Sharp


class Locus(enum.Enum):
    """Where a cell's sample rank sits against its curve's bracket. ATOMS: Below | Inside | Above | OffSpan. Axiom: exactly one holds
    (OffSpan when the rank is outside [0, n - 1]; else below lo, inside [lo, hi], or above hi)."""
    Below = "Below"; Inside = "Inside"; Above = "Above"; OffSpan = "OffSpan"


@dataclass(frozen=True)
class Located:
    """An interior feature: the bracket [lo, hi] holds rank, touches neither end of the curve's span, and is at most w_c of the fast span wide."""
    n: int
    rank: int
    lo: int
    hi: int
    tiering: str


@dataclass(frozen=True)
class Broad:
    """An interior bracket wider than the corridor (its end samples' fast values farther apart than w_c of the fast span): the maximum is
    sigma-indistinguishable over more of the plane than the verdict tolerates, so no point of the curve is read as on the line or to one side
    of it (plan 1176 C', O1; C'' in span units)."""
    n: int
    rank: int
    lo: int
    hi: int
    tiering: str


@dataclass(frozen=True)
class AtSpanEnd:
    """The bracket touches the first or the last sample (lo = 0 or hi = n - 1): the feature may lie beyond the measured span."""
    n: int
    rank: int
    lo: int
    hi: int
    tiering: str


@dataclass(frozen=True)
class Absent:
    """Fewer than three samples: no interior sample exists, so no feature can be located. The bracket is the whole span (no place)."""
    n: int

    @property
    def lo(self):
        return 0

    @property
    def hi(self):
        return self.n - 1


FEATURES = (Located, Broad, AtSpanEnd, Absent)
LOCI = tuple(Locus)
SIDE = {   # (feature kind, locus) -> linenav side NAME; total over FEATURES x LOCI (tests/test_feature.py B5). Only a Located bracket sides; a Broad one never.
    (Located, Locus.Below): "NEG", (Located, Locus.Inside): "MID", (Located, Locus.Above): "POS", (Located, Locus.OffSpan): "UNRES",
    **{(Broad, c): "UNRES" for c in LOCI},
    **{(k, c): "UNRES" for k in (AtSpanEnd, Absent) for c in LOCI},
}
FAMILY = {   # is the family one curve -> (the oracle's side lookup) -> side NAME; total over the two answers
    True: lambda look_up: "SINGLE",   # one curve: one state everywhere, no line can separate it (linenav SINGLE)
    False: lambda look_up: look_up(),
}
PLACE = (Locus.Below, Locus.Inside, Locus.Above)   # indexed by (x >= v[lo]) + (x > v[hi]): the ORDER of a fast value x against the bracket's end samples
IN_SPAN = {True: lambda x, v, f: PLACE[int(x >= v[f.lo]) + int(x > v[f.hi])], False: lambda x, v, f: Locus.OffSpan}   # is x within [v[0], v[n - 1]]


def plateau(v, s, z, rank):
    """The sigma-plateau around rank: the maximal run of consecutive samples i with v[i] + z s[i] >= v[rank] - z s[rank] (rank is in it)."""
    tied = (v + z * s >= v[rank] - z * s[rank]).astype(int)
    return rank - int(np.cumprod(tied[rank::-1]).sum()) + 1, rank + int(np.cumprod(tied[rank:]).sum()) - 1


BRACKET = {   # [measured.uncertainty] kind -> (values, the sigma column (zeros under NONE, unread), Z, rank) -> (lo, hi, tiering); total over FORMAT's kinds
    "COLUMN": lambda v, s, z, rank: (*plateau(v, s, z, rank), "TIERED"),
    "NONE": lambda v, s, z, rank: (rank, rank, "UNTIERED"),   # no sigma: the argmax sample alone, reported UNTIERED
}
KIND = {   # (does the bracket touch a span end, is it wider than w_c of the fast span) -> the feature kind; total over the four answers (a span end first)
    (True, True): AtSpanEnd, (True, False): AtSpanEnd, (False, True): Broad, (False, False): Located,
}
SIGMA_COL = {"COLUMN": lambda a: a[:, 2], "NONE": lambda a: np.zeros(len(a))}   # role order: fast, measured, uncertainty (intake_read.role_columns)


def located(a, z, kind, wc, width, i):
    """The Feature of rows `a` (ascending fast) read over its in-domain ranks i (>= 3, consecutive; its ends are span ends): the argmax, its bracket,
    the kind KIND gives it (width in span units: (fast at hi - fast at lo) / the fast span width), as the curve's own ranks; n is every sample."""
    w = np.asarray(a, float)[i]
    r = int(np.argmax(w[:, 1]))
    lo, hi, tiering = BRACKET[kind](w[:, 1], SIGMA_COL[kind](w), z, r)
    return KIND[(lo == 0 or hi == len(w) - 1, (w[hi, 0] - w[lo, 0]) / width > wc)](len(a), *(int(x + i[0]) for x in (r, lo, hi)), tiering)


SIZED = {   # has the curve at least three samples in its domain -> (samples, Z, uncertainty kind, w_c, span width, in-domain ranks) -> its Feature
    False: lambda a, z, kind, wc, width, i: Absent(len(a)), True: located}   # E0: fewer than 2 in-window samples (and 2: no interior) is Absent


def feature(rows, z, kind, wc, width, ends=(-np.inf, np.inf)):
    """One curve's Feature from its rows (role order), its samples taken in ascending fast order (stable: the stored order breaks a fast tie);
    wc = the corridor's w_c in span units, width = the fast span width (Span.width[1]); ends = the domain, by fast VALUE (E0; never rank)."""
    a = sorted(rows, key=lambda r: r[0])
    i = np.flatnonzero([ends[0] <= r[0] <= ends[1] for r in a])
    return SIZED[len(i) >= 3](a, z, kind, wc, width, i)


WIDTH = {True: lambda lo, hi: 1.0, False: lambda lo, hi: hi - lo}   # is a knob's span one point -> its declared width (a point span: 1, the map a translation)


@dataclass(frozen=True)
class Span:
    """The declared affine coordinate map of a plane (POLICY [coordinate.PLANE_SPAN_UNIT], plan 1176 C'', O4): each knob normalised to its
    declared span, the plane's measured extent (slow: the least to the greatest curve slow value; fast: the least to the greatest sample over
    every curve), so the plane is [0, 1] x [0, 1]. u = (x - lo) / width per axis. It moves where the plane puts a value, never the value."""
    lo: tuple
    width: tuple

    def u(self, x):
        return tuple((float(a) - lo) / w for a, lo, w in zip(x, self.lo, self.width))

    def x(self, u):
        return tuple(lo + float(a) * w for a, lo, w in zip(u, self.lo, self.width))


FAST_ENDS = {True: lambda cs, w: (min(r[0] for c in cs for r in c.rows), max(r[0] for c in cs for r in c.rows)), False: lambda cs, w: w}   # no window?


def span(cs, window=None):
    """The Span of the curves `cs` (each with one slow value and its rows in role order, fast first); fast: the declared window (E0) if any."""
    ends = ((min(c.slow[0] for c in cs), max(c.slow[0] for c in cs)), FAST_ENDS[window is None](cs, window))
    return Span(tuple(float(a) for a, _ in ends), tuple(float(WIDTH[a == b](a, b)) for a, b in ends))


def pair(v, x):
    """The enclosing measured pair of x in the ascending values v, as ranks (the greatest v <= x, the least v >= x): read through the rank
    list padded with its own ends, so a point beyond an end gets that end twice and every index exists."""
    padded = np.concatenate(([0], np.arange(len(v)), [len(v) - 1]))
    return int(padded[np.searchsorted(v, x, side="right")]), int(padded[np.searchsorted(v, x, side="left") + 1])


SOURCE = {   # S2's seal status -> (declaration id, SEAL.json record) -> the FiniteStored source; total over SealStatus
    SealStatus.SEALED: lambda ident, rec: f"{ident}:{rec['declaration_sha256']}",
    SealStatus.SEALED_THEN_EDITED: lambda ident, rec: f"{ident}:{rec['declaration_sha256']}",   # S2 reports the edit; the hash is the seal's
    SealStatus.UNSEALED: lambda ident, rec: f"{ident}:UNSEALED",   # no seal exists: the source says so, never an empty hash
}


@dataclass(frozen=True)
class Oracle:
    """The side oracle over a plane in span units (plan 1176 C''): per curve in slow order its Feature, slow value and ascending fast values, and
    the Span. On a point u of [0, 1]^2 it returns the `alphabet` member SIDE names (nearest curve's feature x u's fast order vs its bracket)."""
    features: tuple
    slows: tuple
    fasts: tuple
    span: Span
    evidence: FiniteStored
    alphabet: type = Side

    def curve(self, u):
        """The rank of the curve whose slow value is nearest u's (a tie to the lower rank): a measured curve, never one between two."""
        s = self.span.x(u)[0]
        return min(range(len(self.slows)), key=lambda k: (abs(self.slows[k] - s), k))

    def at(self, k, x):
        """The side NAME on curve rank k at the physical fast value x: SIDE of its feature and x's order against its bracket's end samples."""
        f, v = self.features[k], self.fasts[k]
        return FAMILY[len(self.features) == 1](lambda: SIDE[(type(f), IN_SPAN[bool(v[0] <= x <= v[-1])](x, v, f))])

    def __call__(self, u):
        return self.alphabet[self.at(self.curve(u), self.span.x(u)[1])]

    def kind(self, u):
        """The Feature kind NAME of the curve nearest u (plan 1176 C', O2: the census of a traced point)."""
        return type(self.features[self.curve(u)]).__name__

    def ranks(self, u):
        """(nearest curve rank, its enclosing sample ranks (lo, hi)) of a located point: its re-projection to ranks, value-free."""
        k = self.curve(u)
        return k, pair(self.fasts[k], self.span.x(u)[1])

    def measured(self, u):
        """The re-projection of a located point to its ENCLOSING MEASURED PAIR (plan 1176 C''): ([slow lo, slow hi] of the two curves that
        enclose its slow, [fast lo, fast hi] of the two samples of its nearest curve that enclose its fast); measured values only."""
        x, (k, (i, j)) = self.span.x(u), self.ranks(u)
        a, b = pair(self.slows, x[0])
        return [float(self.slows[a]), float(self.slows[b])], [float(self.fasts[k][i]), float(self.fasts[k][j])]

    def census(self):
        """{Feature kind name: how many of the family's curves have it}, total over FEATURES (O2: value-free)."""
        return {k.__name__: sum(type(f) is k for f in self.features) for k in FEATURES}


@dataclass(frozen=True)
class Unprojected:
    """A typed refusal, PROJECTION_UNDECLARED or COORDINATE_UNDECLARED (C''): POLICY lacks the row (UNDECLARED), so nothing is declared in M."""
    reason: str = "PROJECTION_UNDECLARED"

    def words(self):
        return f"{self.reason}: intake/POLICY.toml has no {UNDECLARED[self.reason]} row (estimand, preserves, discards); no oracle is built without it"


UNDECLARED = {"PROJECTION_UNDECLARED": f"[feature_projection.{KEY}]", "COORDINATE_UNDECLARED": f"[coordinate.{SPAN_KEY}]"}   # reason -> the missing row
DECLARED = {   # (is the projection declared, is the coordinate map declared) -> (t, curves, census, seal, corridor, alphabet) -> Oracle | Unprojected
    (True, True): lambda *a: _build(*a), (True, False): lambda *a: Unprojected("COORDINATE_UNDECLARED"),
    (False, True): lambda *a: Unprojected(), (False, False): lambda *a: Unprojected(),
}


def oracle(t, census, seal, corridor, alphabet=Side):
    """The side oracle of a census (S5's evidence) under S2's seal state, over all its curves: an Oracle, or Unprojected (no projection in M).
    corridor: the declared [suspect] corridor word (a key of linenav.PARAMS); its frozen w_c is the Broad width."""
    d, files = census.pinned.declaration.data, census.pinned.files
    cs = sorted(intake_census.CURVES[d["selection"]["layout"]](d, files, [intake_census.read(t, d, f) for f in files]), key=lambda c: c.slow)
    return on(t, cs, census, seal, corridor, alphabet)


def on(t, cs, census, seal, corridor, alphabet=Side, window=None):
    """The side oracle over the curves `cs` of a census, in slow order (plan 1176 D, A-E6: a plane's curves, intake_suspect.Plane.source, so
    the oracle's curve rank is the suspect's), its domain the plane's window (E0): an Oracle, or Unprojected when POLICY declares no projection."""
    return DECLARED[(KEY in look(t["policy"], "feature_projection", {}), SPAN_KEY in look(t["policy"], "coordinate", {}))](t, cs, census, seal, corridor, alphabet, window)


def _build(t, cs, census, seal, corridor, alphabet, window=None):
    d = census.pinned.declaration.data
    z, kind, wc = t["policy"]["policy"]["tier_z"], d["measured"]["uncertainty"]["kind"], linenav.PARAMS[corridor]["wc"]   # w_c: the frozen PARAMS, never a knob here
    ev, sp = FiniteStored(SOURCE[seal.status](census.pinned.declaration.id, seal.record)), span(cs, window)
    return Oracle(tuple(feature(c.rows, z, kind, wc, sp.width[1], FAST_ENDS[window is None](cs, window)) for c in cs), tuple(float(c.slow[0]) for c in cs),
                  tuple(np.asarray(sorted(r[0] for r in c.rows), float) for c in cs), sp, ev, alphabet)
