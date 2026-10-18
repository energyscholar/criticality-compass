"""intake_data - the data stages of the intake, S3 to S10 (plan 1136; plan 1139): their evidence types, signatures and bodies.
Invariant: every data stage takes, as its only arguments, the PASS evidence of its `needs` (intake/STAGES.toml); S3 SOURCE_INTEGRITY takes
the Declaration and every later evidence type carries the Pinned bytes S3 read; no data stage takes a seal (amendment A3: sealing is
advisory). A stage with no body is a STUB by absence (a stub is never a pass); each registered body's signature equals its SIGNATURE row
(tests/test_intake.py)."""
from dataclasses import dataclass
from inspect import Parameter, Signature

from intake_blind import Declaration, Pass, Refuse


@dataclass(frozen=True)
class Pinned:
    """S3 SOURCE_INTEGRITY: one pin (path, sha256 at the first logged read) per selected file. Invariant: carries the Declaration it read."""
    declaration: Declaration
    pins: tuple


@dataclass(frozen=True)
class Shaped:
    """S4 SHAPE: the first file's admitted columns or keys, units and axes. Invariant: carries the Pinned it was read from."""
    pinned: Pinned
    columns: tuple


@dataclass(frozen=True)
class Census:
    """S5 CENSUS: the sampling label (curves, points per curve, spacing, missingness, order, replicate groups). Invariant: carries the Pinned."""
    pinned: Pinned
    label: tuple


@dataclass(frozen=True)
class Lineage:
    """S6 ADMISSIBILITY: the loader's admission verdict and the UNENFORCED list. Invariant: carries the Census it audits."""
    census: Census
    verdict: str
    unenforced: tuple


@dataclass(frozen=True)
class IntervalPlan:
    """S7 INTERVAL_FEASIBILITY: per point the method, n and the floor margin. Invariant: carries the Census it was planned on."""
    census: Census
    floors: tuple


@dataclass(frozen=True)
class Feasibility:
    """S8 RESOLUTION_AND_IDENTIFIABILITY: the most bracket the census permits and the identifiability value. Invariant: carries the Census."""
    census: Census
    max_bracket: str
    identifiability: str


@dataclass(frozen=True)
class SecondLane:
    """S9 ALTERNATIVE_INTAKE: the second lane's feasibility. Invariant: carries the Census."""
    census: Census
    feasibility: Feasibility


@dataclass(frozen=True)
class KernelInput:
    """S10 KERNEL_HANDOFF: the kernel columns and relations. Invariant: carries the Lineage that admitted them."""
    lineage: Lineage
    columns: tuple


def sig(**params):
    """A stage signature: the named evidence parameters in order, returning a StageResult (Pass | Refuse)."""
    return Signature([Parameter(n, Parameter.POSITIONAL_OR_KEYWORD, annotation=t) for n, t in params.items()], return_annotation=Pass | Refuse)


EVIDENCE = {"S0": Declaration, "S3": Pinned, "S4": Shaped, "S5": Census, "S6": Lineage, "S7": IntervalPlan, "S8": Feasibility, "S9": SecondLane, "S10": KernelInput}
SIGNATURE = {   # every data stage -> its signature: the evidence of its needs, in needs order (tests/test_intake.py)
    "S3": sig(declaration=Declaration),
    "S4": sig(pinned=Pinned),
    "S5": sig(pinned=Pinned, shaped=Shaped),
    "S6": sig(census=Census),
    "S7": sig(census=Census),
    "S8": sig(census=Census),
    "S9": sig(census=Census),
    "S10": sig(lineage=Lineage, plan=IntervalPlan, feasibility=Feasibility),
}
BODIES = {}   # stage id -> body
