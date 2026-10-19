"""intake_data - the data stages of the intake, S3 to S10 (plan 1136; plan 1139): their evidence types, signatures and bodies.
Invariant: every data stage takes, as its only arguments, the PASS evidence of its `needs` (intake/STAGES.toml); S3 SOURCE_INTEGRITY takes
the Declaration and every later evidence type carries the Pinned bytes S3 read, so a data file is opened once, by the logged loader, in S3;
no data stage takes a seal (amendment A3: sealing is advisory). A stage with no body is a STUB by absence (a stub is never a pass); each
registered body's signature equals its SIGNATURE row (tests/test_intake.py). Every refusal is a value: a check is a (holds, reason, detail)
row and `gate` returns the first row that does not hold, so no check after it is evaluated."""
import enum
import hashlib
import importlib.util
import itertools
import re
import statistics
from dataclasses import dataclass
from inspect import Parameter, Signature
from pathlib import Path

import intake_read
import intake_seal
from intake_blind import NUMBER, Declaration, Pass, Refuse, detail, gate, numbered, shown

ROOT = Path(__file__).resolve().parent.parent


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
class Pinned:
    """S3 SOURCE_INTEGRITY: every selected file, admitted, read once through the logged loader and pinned. Invariant: carries the Declaration
    it read and the bytes, so no later stage opens a file."""
    declaration: Declaration
    files: tuple

    def summary(self):
        return (f"{len(self.files)} files admitted, read once each through the logged loader (declarations/{self.declaration.id}/access.log) "
                f"and each sha256 equal to its pin at the first logged read")

    def confirmed(self):
        return False


@dataclass(frozen=True)
class Shaped:
    """S4 SHAPE: the first file's columns, equal to the declared ones, its rows in the declared order. Invariant: carries the Pinned."""
    pinned: Pinned
    columns: tuple

    def summary(self):
        d = self.pinned.declaration.data
        return (f"The first file's columns are {', '.join(shown(self.columns))}, the declared columns, its stated units (if any) are the declared "
                f"units, and its rows are stored {d['acquisition']['row_order']} in {d['knobs']['fast']['name']} within each curve")

    def confirmed(self):
        return False


@dataclass(frozen=True)
class Sampling:
    """The sampling label of a census: counts and structure, never a value (plan 1160 P0). Invariant: n_min <= n_median <= n_max over `curves`
    curves; `distinct` is the count of distinct fast values over every curve; `with_slow` is the count of curves that carry a slow value (0
    under [selection.slow] source NONE, plan 1160 P1; else every curve)."""
    curves: int
    with_slow: int
    n_min: int
    n_median: float
    n_max: int
    fast: str
    distinct: int
    alignment: Alignment


@dataclass(frozen=True)
class Census:
    """S5 CENSUS: the sampling label (curves, points per curve, distinct fast values, alignment) and the curves as (where, points) in census
    order. Invariant: carries the Pinned it counted; it holds counts and names, never a value (plan 1160 P0)."""
    pinned: Pinned
    label: Sampling
    curves: tuple

    def summary(self):
        x = self.label
        return (f"Every file has the first file's columns; no slow value or fast value repeats; no curve contradicts the declared direction. Sampling: {x.curves} curves; points per curve "
                f"min {x.n_min}, median {x.n_median:g}, max {x.n_max}; {x.distinct} distinct {x.fast} values; {x.alignment.name}; curves_with_slow = {x.with_slow}")

    def listing(self):
        """The report's census section: each curve by ordinal and file name (a LONG_TABLE block by its ordinal), never by its slow value."""
        return [f"{i}. {where}: {n} points" for i, (where, n) in enumerate(self.curves, 1)]

    def confirmed(self):
        return False


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


def _t23():
    """The vendored logged loader (vendor/toolset/t23.py, pinned by vendor/toolset/PIN.toml), loaded by path: vendor/toolset is never put on
    sys.path, where its intake.py would shadow cc/intake.py."""
    spec = importlib.util.spec_from_file_location("t23", ROOT / "vendor" / "toolset" / "t23.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def located(text, roots):
    """The directory a declared source root names ("<name>/<relative path>", the name a row of intake/ROOTS.toml), or "" when it names none."""
    m = re.fullmatch(r"(<[\w.-]+>)((?:/[\w.-]+)*)", text)
    return {True: lambda: str(Path(roots[m[1]]) / m[2].lstrip("/")), False: lambda: ""}[m is not None and m[1] in roots and ".." not in m[2].split("/")]()


ADMIT = (   # plan 1160 P1: the loader's admission of one selected name before any byte is read, one row per reason, in this order
    ("PATH_OUTSIDE_ROOT", "names that resolve outside the source root", lambda loc, n, src: (Path(loc) / n).resolve().is_relative_to(Path(loc).resolve())),
    ("PATH_ON_TRUTH_SIDE", "names with a path part on the truth side", lambda loc, n, src: not set(Path(n).parts) & set(src["truth_side"])),
    ("PATH_NOT_A_FILE", "names that are not a file", lambda loc, n, src: (Path(loc) / n).is_file()),
)


def admission(loc, names, src):
    """One gate row per ADMIT row: (holds, reason, detail) over every selected name; the detail names the first three that fail."""
    failing = lambda ok: [n for n in names if not ok(loc, n, src)]
    return [(lambda ok=ok: not failing(ok), code, lambda ok=ok, what=what: detail(words=failing(ok)[:3], counts={what: len(failing(ok))})) for code, what, ok in ADMIT]


SOURCE = {   # [source] kind -> the S3 body of that kind; total over FORMAT's [source] kinds (plan 1160 P1)
    "DEPOSIT": lambda declaration, d, t: _deposit(declaration, d, t),
    "CONVERTED": lambda declaration, d, t: Refuse("CONVERSION_NOT_LIVE", detail(words=[f"converted from '{declaration.data['source']['converted_from']}'", "the conversion has no body yet (plan 1160 P3)"])),
}


def source_integrity(declaration, d, t):
    """S3 SOURCE_INTEGRITY: its body for the declared [source] kind (SOURCE). A CONVERTED source refuses CONVERSION_NOT_LIVE until plan 1160
    P3 gives the conversion a body, so a stub is never a pass."""
    return SOURCE[declaration.data["source"]["kind"]](declaration, d, t)


def _deposit(declaration, d, t):
    """S3 for a DEPOSIT. Invariant: ROOT_UNRESOLVED | UNIVERSE_CHANGED (names and sizes against the seal, only when a SEAL.json exists) |
    PATH_OUTSIDE_ROOT | PATH_ON_TRUTH_SIDE | PATH_NOT_A_FILE (ADMIT) are decided before any byte is read; then each file is read once through the logged loader, and PIN_MISMATCH when its
    sha256 differs from the sha256 at its first logged loader read (the pin)."""
    src, sel = declaration.data["source"], declaration.data["selection"]
    loc, rec = located(src["root"], t["roots"]), intake_seal.record(d)
    names = intake_seal.selected(sel)
    return gate([(lambda: loc != "" and Path(loc).is_dir(), "ROOT_UNRESOLVED", lambda: detail(words=[f"root '{src['root']}' (names in intake/ROOTS.toml: {sorted(t['roots'])})"])),
                 (lambda: rec == {} or intake_seal.listing(loc, src["universe"]) == rec["universe"]["listing"], "UNIVERSE_CHANGED",
                  lambda: detail(counts={"names now": len(intake_seal.listing(loc, src["universe"])), "names sealed": len(rec["universe"]["listing"])})),
                 *admission(loc, names, src)],
                lambda: _read(declaration, d, loc, names))


def _read(declaration, d, loc, names):
    """Each admitted file read once through the logged loader (the access log is declarations/<id>/access.log; the bank's parent directory is
    a declared partition too, so an in-process open of the truth side beside the bank is logged as a bypass); then each pin compared."""
    loader = _t23().Loader({loc: "universe", str(Path(loc).parent): "outside-universe"}, Path(d) / "access.log")
    files = tuple(File(n, hashlib.sha256(b).hexdigest(), b) for n in names for b in [loader.read(Path(loc) / n)])
    pins = {}
    for a in intake_seal.lines(Path(d) / "access.log"):
        pins.setdefault(a["path"], a["sha256"]) if a["route"] == "loader" else None
    moved = lambda: [f.name for f in files if pins[str((Path(loc) / f.name).resolve())] != f.sha256]
    return gate([(lambda: not moved(), "PIN_MISMATCH", lambda: detail(words=moved()[:3], counts={"files that differ from their pins": len(moved())}))], lambda: Pass(Pinned(declaration, files)))


def read(t, d, f):
    """One pinned file through the declaration's reader: intake_read.Grid | intake_read.Unreadable (never an exception)."""
    return intake_read.readers(t)[d["reader"]["name"]](f.data, d)


@dataclass(frozen=True)
class Curve:
    """One curve of a census. Invariant: `rows` are the readable rows of one curve in file order, each in role order (fast first); `slow` is
    the tuple of slow-knob values its source gives it (plan 1160 P1): after S5's SLOW_KEY_UNRESOLVED row holds, one value, or none under
    [selection.slow] source NONE; `where` names the file (PER_FILE) or the file and its block's ordinal (LONG_TABLE), never a value (plan 1160 P0)."""
    where: str
    slow: tuple
    rows: tuple


def _blocks(f, g):
    """LONG_TABLE: the blocks of consecutive rows with one slow value (the last role column), in file order, each one Curve."""
    return [Curve(f"{f.name} block {i}", (h,), tuple(rows)) for i, (h, rows) in enumerate(((h, list(rs)) for h, rs in itertools.groupby(g.rows, key=lambda r: r[-1])), 1)]


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
CURVES = {   # [selection] layout -> (declaration, files, their grids) -> the curves, in file order; total over FORMAT's layouts (plan 1145)
    "PER_FILE": lambda d, files, grids: [Curve(f.name, s, g.rows) for f, g, s in zip(files, grids, SLOW[d["selection"]["slow"]["source"]](d["selection"]["slow"], grids))],
    "LONG_TABLE": lambda d, files, grids: [c for f, g in zip(files, grids) for c in _blocks(f, g)],
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
                 (lambda: not units(), "UNIT_DIFFERS", lambda: detail(f.name, words=[x for r, u, w in units() for x in (f"{r} stated in", u, f"declared {w}")])),
                 (lambda: not unordered(), "ROW_ORDER_DIFFERS", lambda: detail(words=unordered()[:3] + [f"not {d['acquisition']['row_order']} in {d['knobs']['fast']['name']}"], counts={"curves": len(unordered())}))],
                lambda: Pass(Shaped(pinned, g.columns)))


REPLICATE = {   # ([selection] layout, [replicate] identity) -> (may two curves share a slow value, can the reader resolve the identity); total
    **{(lay, k): v for lay in ("PER_FILE", "LONG_TABLE") for k, v in (("NONE", (False, True)), ("SEED", (False, False)), ("RUN", (False, False)), ("SAMPLE", (False, False)))},
    ("PER_FILE", "FILE"): (True, True),
    ("LONG_TABLE", "FILE"): (False, False),   # one file holds every curve: the file tells no two curves apart
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
    twice = lambda: [c.where for c in curves() if len({r[0] for r in c.rows}) != len(c.rows)]
    against = lambda: [c.where for c in curves() if not DIRECTION[(acq["row_order"] == "ACQUISITION", acq["direction"])]([r[0] for r in c.rows])]
    again = lambda: [c.where for c in curves() if any(hs().count(v) > 1 for v in c.slow)]
    return gate([(lambda: not other, "FILE_DIFFERS_FROM_FIRST", lambda: detail(words=other[:3], counts={"files": len(other)})),
                 (lambda: not unkeyed(), "SLOW_KEY_UNRESOLVED", lambda: detail(words=unkeyed()[:3] + [f"key '{d['selection']['slow']['key']}'"], counts={"files": len(unkeyed())})),
                 (lambda: rep[1], "REPLICATE_KEY_UNRESOLVED", lambda: detail(words=[f"identity {d['replicate']['identity']}: reader {d['reader']['name']} with layout {d['selection']['layout']} carries no replicate key"])),
                 (lambda: rep[0] or len(set(hs())) == len(hs()), "CURVE_REPEATED", lambda: detail(words=again()[:3], counts={"curves whose slow value another curve has": len(again())})),
                 (lambda: not twice(), "FAST_VALUE_REPEATED", lambda: detail(words=twice()[:3], counts={"curves": len(twice())})),
                 (lambda: not against(), "ACQUISITION_ORDER_DIFFERS", lambda: detail(words=against()[:3] + [f"stored in acquisition order, not {acq['direction']}"], counts={"curves": len(against())}))],
                lambda: Pass(Census(pinned, label(curves(), d["knobs"]["fast"]["name"]), tuple((c.where, len(c.rows)) for c in curves()))))


def label(curves, fast):
    """The sampling label of curves whose rows hold the fast knob first."""
    ns, xs = [len(c.rows) for c in curves], [r[0] for c in curves for r in c.rows]
    seqs = {tuple(r[0] for r in c.rows) for c in curves}
    return Sampling(len(curves), sum(len(c.slow) for c in curves), min(ns), statistics.median(ns), max(ns), fast, len(set(xs)), {True: Alignment.ALIGNED, False: Alignment.MISALIGNED}[len(seqs) == 1])


def bodies(t, d):
    """The registered data-stage bodies of one run (S3, S4, S5; plan 1139), closed over the tables and the declaration directory. Each has
    exactly its SIGNATURE row (tests/test_intake.py)."""
    def s3(declaration: Declaration) -> Pass | Refuse:
        return source_integrity(declaration, d, t)

    def s4(pinned: Pinned) -> Pass | Refuse:
        return shape(pinned, t)

    def s5(pinned: Pinned, shaped: Shaped) -> Pass | Refuse:
        return census(pinned, shaped, t)
    return {"S3": s3, "S4": s4, "S5": s5}
