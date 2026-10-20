"""intake_feature - plan 1176 phase B (ruling R1): the per-curve feature, a declared projection in M, and the real-data side oracle over it
(role intake_feature with its own cap, tests/test_budget.py FEATURE_CAP, so CORE_CAP stays 1200).
The projection (POLICY [feature_projection.FEATURE_ARGMAX_FAST]) gives each curve one typed Feature: Located(rank, lo, hi) | AtSpanEnd | Absent.
rank is the argmax sample rank (samples in ascending fast order, ties to the first); [lo, hi] is the sigma-plateau, the maximal run of
consecutive samples around rank whose value + Z sigma >= max - Z sigma_max (Z = POLICY's tier_z): a declared interval, never a guard. With no
sigma column the bracket is [rank, rank] and the tiering UNTIERED (reported, not refused). AtSpanEnd when lo = 0 or hi = n - 1; Absent when
n < 3. The cross-curve relation is the declared slow order of the curves (curve rank = 0-based slow order). Nothing between measured points is
ever formed: a locus is a cell (curve_rank, sample_rank), never a value.
The oracle answers linenav's side alphabet {NEG, POS, MID, UNRES, SINGLE} by member NAME from SIDE, total over FEATURES x LOCI (one-curve family:
SINGLE). Its evidence is always FiniteStored(source = "<declaration id>:<seal hash>"), never Sharp. It reads only the Census object (the pinned
bytes it carries) and the tables as values: it constructs no Path and opens nothing."""
import enum
from dataclasses import dataclass

import numpy as np

import intake_census
from intake_blind import look
from intake_seal import SealStatus

KEY = "FEATURE_ARGMAX_FAST"   # the POLICY row this projection cites (intake/POLICY.toml [feature_projection])


class Side(enum.Enum):
    """linenav's side alphabet (tools/linenav.py v2.1-T Side), by member name. The oracle reads SIDE's names through its `alphabet`, so a
    caller that holds linenav.Side passes it and gets linenav's members (phase D); this enum is the default."""
    NEG = "NEG"; POS = "POS"; MID = "MID"; UNRES = "UNRES"; SINGLE = "SINGLE"


class Locus(enum.Enum):
    """Where a cell's sample rank sits against its curve's bracket. ATOMS: Below | Inside | Above | OffSpan. Axiom: exactly one holds
    (OffSpan when the rank is outside [0, n - 1]; else below lo, inside [lo, hi], or above hi)."""
    Below = "Below"; Inside = "Inside"; Above = "Above"; OffSpan = "OffSpan"


@dataclass(frozen=True)
class Located:
    """An interior feature: the bracket [lo, hi] holds rank and touches neither end of the curve's span."""
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


FEATURES = (Located, AtSpanEnd, Absent)
LOCI = tuple(Locus)
SIDE = {   # (feature kind, locus) -> linenav side NAME; total over FEATURES x LOCI (tests/test_feature.py B5). Only a Located bracket sides.
    (Located, Locus.Below): "NEG", (Located, Locus.Inside): "MID", (Located, Locus.Above): "POS", (Located, Locus.OffSpan): "UNRES",
    **{(k, c): "UNRES" for k in (AtSpanEnd, Absent) for c in LOCI},
}
FAMILY = {   # is the family one curve -> (the oracle's side lookup) -> side NAME; total over the two answers
    True: lambda look_up: "SINGLE",   # one curve: one state everywhere, no line can separate it (linenav SINGLE)
    False: lambda look_up: look_up(),
}
PLACE = (Locus.Below, Locus.Inside, Locus.Above)   # indexed by (s >= lo) + (s > hi), s the cell's sample rank
IN_SPAN = {True: lambda s, f: PLACE[int(s >= f.lo) + int(s > f.hi)], False: lambda s, f: Locus.OffSpan}


def plateau(v, s, z, rank):
    """The sigma-plateau around rank: the maximal run of consecutive samples i with v[i] + z s[i] >= v[rank] - z s[rank] (rank is in it)."""
    tied = (v + z * s >= v[rank] - z * s[rank]).astype(int)
    return rank - int(np.cumprod(tied[rank::-1]).sum()) + 1, rank + int(np.cumprod(tied[rank:]).sum()) - 1


BRACKET = {   # [measured.uncertainty] kind -> (values, the sigma column (zeros under NONE, unread), Z, rank) -> (lo, hi, tiering); total over FORMAT's kinds
    "COLUMN": lambda v, s, z, rank: (*plateau(v, s, z, rank), "TIERED"),
    "NONE": lambda v, s, z, rank: (rank, rank, "UNTIERED"),   # no sigma: the argmax sample alone, reported UNTIERED
}
EDGE = {True: AtSpanEnd, False: Located}   # does the bracket touch a span end -> the feature kind
SIGMA_COL = {"COLUMN": lambda a: a[:, 2], "NONE": lambda a: np.zeros(len(a))}   # role order: fast, measured, uncertainty (intake_read.role_columns)


def located(a, z, kind):
    """The Feature of a curve of n >= 3 samples `a` (rows in ascending fast order): the argmax rank, its bracket, and the kind EDGE gives it."""
    r = int(np.argmax(a[:, 1]))
    lo, hi, tiering = BRACKET[kind](a[:, 1], SIGMA_COL[kind](a), z, r)
    return EDGE[lo == 0 or hi == len(a) - 1](len(a), r, lo, hi, tiering)


SIZED = {   # has the curve at least three samples -> (its rows, Z, uncertainty kind) -> its Feature; total over the two answers
    False: lambda rows, z, kind: Absent(len(rows)),
    True: lambda rows, z, kind: located(np.asarray(sorted(rows, key=lambda r: r[0]), float), z, kind),   # stable: the stored order breaks a fast tie
}


def feature(rows, z, kind):
    """One curve's Feature from its rows (role order), its samples taken in ascending fast order."""
    return SIZED[len(rows) >= 3](rows, z, kind)


SOURCE = {   # S2's seal status -> (declaration id, SEAL.json record) -> the FiniteStored source; total over SealStatus
    SealStatus.SEALED: lambda ident, rec: f"{ident}:{rec['declaration_sha256']}",
    SealStatus.SEALED_THEN_EDITED: lambda ident, rec: f"{ident}:{rec['declaration_sha256']}",   # S2 reports the edit; the hash is the seal's
    SealStatus.UNSEALED: lambda ident, rec: f"{ident}:UNSEALED",   # no seal exists: the source says so, never an empty hash
}


@dataclass(frozen=True)
class FiniteStored:
    """linenav's evidence class of a finite-size reader of STORED data (plan 1109): FINITE, it can never claim the line ends. source names the
    stored object. The oracle's evidence is always this class, never Sharp."""
    source: str


@dataclass(frozen=True)
class Oracle:
    """The real-data side oracle: one Feature per curve in slow order; called on a cell u = (curve_rank, sample_rank) it returns a member of
    `alphabet` (linenav's Side, or this module's) named by SIDE. A curve rank outside the family is Absent (UNRES): no default side exists."""
    features: tuple
    evidence: FiniteStored
    alphabet: type = Side

    def __call__(self, u):
        c, s = int(round(float(u[0]))), int(round(float(u[1])))
        f = look(dict(enumerate(self.features)), c, Absent(0))
        return self.alphabet[FAMILY[len(self.features) == 1](lambda: SIDE[(type(f), IN_SPAN[0 <= s <= f.n - 1](s, f))])]


@dataclass(frozen=True)
class Unprojected:
    """The typed refusal PROJECTION_UNDECLARED: POLICY holds no [feature_projection.FEATURE_ARGMAX_FAST] row, so no projection is declared in M."""
    reason: str = "PROJECTION_UNDECLARED"

    def words(self):
        return f"{self.reason}: intake/POLICY.toml has no [feature_projection.{KEY}] row (estimand, preserves, discards); no feature is projected without it"


DECLARED = {True: lambda t, census, seal, alphabet: _build(t, census, seal, alphabet), False: lambda t, census, seal, alphabet: Unprojected()}


def oracle(t, census, seal, alphabet=Side):
    """The side oracle of a census (S5's evidence) under S2's seal state: an Oracle, or Unprojected when POLICY declares no feature projection."""
    return DECLARED[KEY in look(t["policy"], "feature_projection", {})](t, census, seal, alphabet)


def _build(t, census, seal, alphabet):
    d, files = census.pinned.declaration.data, census.pinned.files
    cs = sorted(intake_census.CURVES[d["selection"]["layout"]](d, files, [intake_census.read(t, d, f) for f in files]), key=lambda c: c.slow)
    z, kind = t["policy"]["policy"]["tier_z"], d["measured"]["uncertainty"]["kind"]
    ev = FiniteStored(SOURCE[seal.status](census.pinned.declaration.id, seal.record))
    return Oracle(tuple(feature(c.rows, z, kind) for c in cs), ev, alphabet)
