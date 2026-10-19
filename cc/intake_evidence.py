"""intake_evidence - the PASS evidence types of the data stages S3 to S10, and the Curve a census counts.
Invariant: value-free and blind: every field is a count, a name, a code, the pinned bytes or an upstream evidence, and every summary()
prints through shown and counts only; it imports only enum, dataclasses and intake_blind, constructs no Path and opens nothing."""
import enum
from dataclasses import dataclass

from intake_blind import Declaration, Evidence, shown


class Alignment(enum.Enum):
    """Whether the curves share one fast-knob grid. ATOMS: ALIGNED | MISALIGNED. Axiom: exactly one holds for a census (every curve holds the
    same fast values in the same order; or not)."""
    ALIGNED = frozenset({"ALIGNED"})
    MISALIGNED = frozenset({"MISALIGNED"})


@dataclass(frozen=True)
class File:
    """One selected file as S3 read it. Invariant: sha256 is the sha256 of `data`, and equals the pin at its first logged loader read. It holds
    no slow value: a curve's slow value is the declaration's (LISTED), a header line of the file (FILE_KEY), a column of the file (LONG_TABLE)
    or none (NONE), see CURVES."""
    name: str
    sha256: str
    data: bytes


@dataclass(frozen=True)
class Pinned(Evidence):
    """S3 SOURCE_INTEGRITY: every selected file, admitted, read once through the logged loader and pinned. Invariant: carries the Declaration
    it read and the bytes, so no later stage opens a file. `dropped`: per converted file that declares DROP_ROWS_NOT_NUMERIC, (its name, the rows
    dropped), set by intake_convert.s3 from the manifest."""
    declaration: Declaration
    files: tuple
    dropped: tuple = ()

    def summary(self):
        return (f"{len(self.files)} files admitted, read once each through the logged loader (declarations/{self.declaration.id}/access.log) "
                f"and each sha256 equal to its pin at the first logged read")


@dataclass(frozen=True)
class Shaped(Evidence):
    """S4 SHAPE: the first file's columns, equal to the declared ones, its rows in the declared order. Invariant: carries the Pinned."""
    pinned: Pinned
    columns: tuple

    def summary(self):
        d = self.pinned.declaration.data
        return (f"The first file's columns are {', '.join(shown(self.columns))}, the declared columns, its stated units (if any) are the declared "
                f"units, and its rows are stored {d['acquisition']['row_order']} in {d['knobs']['fast']['name']} within each curve")


@dataclass(frozen=True)
class Sampling:
    """The sampling label of a census: counts and structure, never a value. Invariant: n_min <= n_median <= n_max points over
    `curves` curves; `distinct` is the count of distinct fast values over every curve; `with_slow` is the count of curves that carry a slow value
    (0 under [selection.slow] source NONE; else every curve); `readings` is (min, max) readings per point (more
    than 1 only under [replicate] identity SAME_FAST_VALUE); `drift` is the most distinct slow values in one curve (a FAST_RESTART block)."""
    curves: int
    with_slow: int
    n_min: int
    n_median: float
    n_max: int
    fast: str
    distinct: int
    alignment: Alignment
    readings: tuple
    drift: int


@dataclass(frozen=True)
class Census(Evidence):
    """S5 CENSUS: the sampling label (curves, points per curve, distinct fast values, alignment), the curves as (where, points) in census
    order, and per curve the readings of each point in row order (S7's floor). Invariant: carries the Pinned it counted; it holds
    counts and names, never a value."""
    pinned: Pinned
    label: Sampling
    curves: tuple
    readings: tuple

    def summary(self):
        x = self.label
        return (f"Every file has the first file's columns; no slow value or fast value repeats; no curve contradicts the declared direction. Sampling: {x.curves} curves; points per curve "
                f"min {x.n_min}, median {x.n_median:g}, max {x.n_max}; {x.distinct} distinct {x.fast} values; {x.alignment.name}; curves_with_slow = {x.with_slow}; "
                f"readings per point min {x.readings[0]}, max {x.readings[1]}; distinct_slow_in_block max = {x.drift}")

    def listing(self):
        """The report's census section: each curve by ordinal and file name (a LONG_TABLE block by its ordinal), never by its slow value."""
        return [f"{i}. {where}: {n} points" for i, (where, n) in enumerate(self.curves, 1)] + [f"- converted {f}: rows dropped as not numeric (DROP_ROWS_NOT_NUMERIC): {k}" for f, k in self.pinned.dropped]


@dataclass(frozen=True)
class Lineage(Evidence):
    """S6 ADMISSIBILITY: the loader's admission verdict and the UNENFORCED list. Invariant: carries the Census it audits; built only when every
    pinned file has a loader line in the access log with its path and sha256, and the log holds no in-process bypass line."""
    census: Census
    verdict: str
    unenforced: tuple

    def summary(self):
        return (f"{self.verdict}: every pinned file has a loader line in the access log with its sha256, and the log holds no in-process bypass. "
                f"Not enforced (no check here can see them): {'; '.join(self.unenforced)}")


@dataclass(frozen=True)
class IntervalPlan(Evidence):
    """S7 INTERVAL_FEASIBILITY (cc/intake_feasible.py): the method, the tiering it gives the terminal (STATED | REPLICATES | NONE)
    and the points (curve, ordinal, readings) its floor was checked on. Invariant: carries the Census it was planned on."""
    census: Census
    method: str
    tiering: str
    floors: tuple

    def summary(self):
        return f"interval method {self.method}: {len(self.floors)} points meet its floor; tiering = {self.tiering}"


@dataclass(frozen=True)
class Feasibility(Evidence):
    """S8 RESOLUTION_AND_IDENTIFIABILITY: the most bracket the census permits and the identifiability value. Invariant: carries the Census."""
    census: Census
    max_bracket: str
    identifiability: str

    def summary(self):
        return f"at least 3 curves with a slow value and 3 points per curve; max_bracket = {self.max_bracket}; identifiability = {self.identifiability}"


@dataclass(frozen=True)
class SecondLane(Evidence):
    """S9 ALTERNATIVE_INTAKE: the ALTERNATIVE lane's steps checked on the census, as words (a Feasibility is
    what only S8 builds). Invariant: carries the Census."""
    census: Census
    lanes: tuple
    n_lanes: int   # the lanes with a bridge, 1 or 2 (S1 SECOND_LANE_MISSING needs one; FORMAT's lane alphabet has two); NOT_EXAMINED at 1

    def summary(self):
        return f"ALTERNATIVE lane steps feasible on the census: {', '.join(self.lanes) or 'none declared (one lane: nothing for S9 to check)'}"


@dataclass(frozen=True)
class KernelInput(Evidence):
    """S10 KERNEL_HANDOFF (cc/intake_terminal.py): one Handoff per PRIMARY bridge (its kernel input's result). Invariant: carries
    the Lineage that admitted them; its summary prints result types, ranks, tiers and counts (never a value) and the identifiability value."""
    lineage: Lineage
    columns: tuple
    identifiability: str

    def summary(self):
        return "; ".join(h.words() for h in self.columns) + f". Identifiability: {self.identifiability}"


@dataclass(frozen=True)
class Curve:
    """One curve of a census. Invariant: `rows` are the readable rows of one curve in file order, each in role order (fast first); `slow` is
    the tuple of slow-knob values its source gives it: after S5's SLOW_KEY_UNRESOLVED row holds, one value, or none under
    [selection.slow] source NONE; `where` names the file (PER_FILE) or the file and its block's ordinal (LONG_TABLE), never a value;
    `drift` is the count of distinct slow values its rows hold (more than 1 only in a FAST_RESTART block; a count, never a value)."""
    where: str
    slow: tuple
    rows: tuple
    drift: int
