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
from intake_blind import NUMBER, RESTARTS, SWEEP, Declaration, Pass, Refuse, detail, gate, numbered, shown

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
    """The sampling label of a census: counts and structure, never a value (plan 1160 P0). Invariant: n_min <= n_median <= n_max points over
    `curves` curves; `distinct` is the count of distinct fast values over every curve; `with_slow` is the count of curves that carry a slow value
    (0 under [selection.slow] source NONE, plan 1160 P1; else every curve); `readings` is (min, max) readings per point (plan 1160 P2: more
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
class Census:
    """S5 CENSUS: the sampling label (curves, points per curve, distinct fast values, alignment) and the curves as (where, points) in census
    order. Invariant: carries the Pinned it counted; it holds counts and names, never a value (plan 1160 P0)."""
    pinned: Pinned
    label: Sampling
    curves: tuple

    def summary(self):
        x = self.label
        return (f"Every file has the first file's columns; no slow value or fast value repeats; no curve contradicts the declared direction. Sampling: {x.curves} curves; points per curve "
                f"min {x.n_min}, median {x.n_median:g}, max {x.n_max}; {x.distinct} distinct {x.fast} values; {x.alignment.name}; curves_with_slow = {x.with_slow}; "
                f"readings per point min {x.readings[0]}, max {x.readings[1]}; distinct_slow_in_block max = {x.drift}")

    def listing(self):
        """The report's census section: each curve by ordinal and file name (a LONG_TABLE block by its ordinal), never by its slow value."""
        return [f"{i}. {where}: {n} points" for i, (where, n) in enumerate(self.curves, 1)]

    def confirmed(self):
        return False


@dataclass(frozen=True)
class Lineage:
    """S6 ADMISSIBILITY: the loader's admission verdict and the UNENFORCED list. Invariant: carries the Census it audits; built only when every
    pinned file has a loader line in the access log with its path and sha256, and the log holds no in-process bypass line (plan 1160 P4)."""
    census: Census
    verdict: str
    unenforced: tuple

    def summary(self):
        return (f"{self.verdict}: every pinned file has a loader line in the access log with its sha256, and the log holds no in-process bypass. "
                f"Not enforced (no check here can see them): {'; '.join(self.unenforced)}")

    def confirmed(self):
        return False


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
    "DEPOSIT": lambda declaration, d, t: _deposit(declaration, d, t, lambda loc: _t23().Loader({loc: "universe", str(Path(loc).parent): "outside-universe"}, Path(d) / "access.log")),
    "CONVERTED": lambda declaration, d, t: _converted(declaration, d, t),
}


def source_integrity(declaration, d, t):
    """S3 SOURCE_INTEGRITY: its body for the declared [source] kind (SOURCE). A CONVERTED source (plan 1160 P3) first proves the chain from
    converted_from to the bank (CONVERSION_CHAIN_BROKEN), then its bank is read exactly as a DEPOSIT."""
    return SOURCE[declaration.data["source"]["kind"]](declaration, d, t)


def _converted(declaration, d, t):
    """S3 for a CONVERTED source: cc/intake_convert.py's chain check (imported here: it imports this module), then _deposit through the same
    loader (plan 1160 P4: one loader per run, so no loader's audit hook logs another loader's read as a bypass, which S6 would refuse)."""
    import intake_convert
    return intake_convert.s3(declaration, d, t, lambda loader: _deposit(declaration, d, t, lambda loc: loader))


def _deposit(declaration, d, t, made):
    """S3 for a DEPOSIT. Invariant: ROOT_UNRESOLVED | UNIVERSE_CHANGED (names and sizes against the seal, only when a SEAL.json exists) |
    PATH_OUTSIDE_ROOT | PATH_ON_TRUTH_SIDE | PATH_NOT_A_FILE (ADMIT) are decided before any byte is read; then each file is read once through the logged loader, and PIN_MISMATCH when its
    sha256 differs from the sha256 at its first logged loader read (the pin). made(loc) is the run's one logged loader (SOURCE, _converted)."""
    src, sel = declaration.data["source"], declaration.data["selection"]
    loc, rec = located(src["root"], t["roots"]), intake_seal.record(d)
    names = intake_seal.selected(sel)
    return gate([(lambda: loc != "" and Path(loc).is_dir(), "ROOT_UNRESOLVED", lambda: detail(words=[f"root '{src['root']}' (names in intake/ROOTS.toml: {sorted(t['roots'])})"])),
                 (lambda: rec == {} or intake_seal.listing(loc, src["universe"]) == rec["universe"]["listing"], "UNIVERSE_CHANGED",
                  lambda: detail(counts={"names now": len(intake_seal.listing(loc, src["universe"])), "names sealed": len(rec["universe"]["listing"])})),
                 *admission(loc, names, src)],
                lambda: _read(declaration, d, loc, names, made(loc)))


def _read(declaration, d, loc, names, loader):
    """Each admitted file read once through the logged loader (the access log is declarations/<id>/access.log; the bank's parent directory is
    a declared partition too, so an in-process open of the truth side beside the bank is logged as a bypass); then each pin compared."""
    files = tuple(File(n, hashlib.sha256(b).hexdigest(), b) for n in names for b in [loader.read(Path(loc) / n)])
    pins = {}
    for a in intake_seal.lines(Path(d) / "access.log"):
        pins.setdefault(a["path"], a["sha256"]) if a["route"] == "loader" else None
    moved = lambda: [f.name for f in files if pins[str((Path(loc) / f.name).resolve())] != f.sha256]
    return gate([(lambda: not moved(), "PIN_MISMATCH", lambda: detail(words=moved()[:3], counts={"files that differ from their pins": len(moved())}))], lambda: Pass(Pinned(declaration, files)))


def admissibility(census, d, t):
    """S6 ADMISSIBILITY (reads no data byte; it reads declarations/<id>/access.log, which lies in no declared partition). READ_NOT_LOGGED: a
    pinned file with no loader line holding its resolved path and its sha256 | BYPASS_READ_LOGGED: a line with route in-process-bypass (the
    loader's audit hook saw an open of a declared-partition path outside the loader). LINEAGE_OFF_GRAPH has no row: the terminal is table-driven
    from the sealed declaration, so an off-graph step is unreachable by construction (STAGES.toml)."""
    loc, log = located(census.pinned.declaration.data["source"]["root"], t["roots"]), intake_seal.lines(Path(d) / "access.log")
    logged = {(a["path"], a["sha256"]) for a in log if a["route"] == "loader"}
    unlogged = [f.name for f in census.pinned.files if (str((Path(loc) / f.name).resolve()), f.sha256) not in logged]
    bypass = [a for a in log if a["route"] == "in-process-bypass"]
    return gate([(lambda: not unlogged, "READ_NOT_LOGGED", lambda: detail(words=unlogged[:3], counts={"pinned files with no loader line": len(unlogged)})),
                 (lambda: not bypass, "BYPASS_READ_LOGGED",
                  lambda: detail(words=sorted({f"partition {a['partition']}" for a in bypass}), counts={"in-process bypass lines": len(bypass)}))],
                lambda: Pass(Lineage(census, "ADMITTED_ON_LOGGED_PATHS_ONLY", tuple(t["stages"]["report"]["unenforced"]))))


def read(t, d, f):
    """One pinned file through the declaration's reader: intake_read.Grid | intake_read.Unreadable (never an exception)."""
    return intake_read.readers(t)[d["reader"]["name"]](f.data, d)


@dataclass(frozen=True)
class Curve:
    """One curve of a census. Invariant: `rows` are the readable rows of one curve in file order, each in role order (fast first); `slow` is
    the tuple of slow-knob values its source gives it (plan 1160 P1): after S5's SLOW_KEY_UNRESOLVED row holds, one value, or none under
    [selection.slow] source NONE; `where` names the file (PER_FILE) or the file and its block's ordinal (LONG_TABLE), never a value (plan 1160 P0);
    `drift` is the count of distinct slow values its rows hold (plan 1160 P2: more than 1 only in a FAST_RESTART block; a count, never a value)."""
    where: str
    slow: tuple
    rows: tuple
    drift: int


BREAK = {   # LONG_TABLE [selection] block -> (the declaration) -> (previous row, row) -> does a new curve begin at row; total over FORMAT's blocks
    "EXACT": lambda d: lambda p, r: p[-1] != r[-1],   # the slow value (the last role column) changes
    "FAST_RESTART": lambda d: lambda p, r: RESTARTS[SWEEP[d["acquisition"]["row_order"]](d["acquisition"])](p[0], r[0]),   # the fast knob turns back (S1: it has a direction)
}


def _blocks(f, g, d):
    """LONG_TABLE: the blocks of consecutive rows the declared block rule (BREAK) cuts the file into, in file order, each one Curve whose slow
    value is its FIRST row's (a value as measured, never a mean; plan 1160 P2)."""
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
CURVES = {   # [selection] layout -> (declaration, files, their grids) -> the curves, in file order; total over FORMAT's layouts (plan 1145)
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
                 (lambda: not unordered(), "ROW_ORDER_DIFFERS", lambda: detail(words=unordered()[:3] + [f"not {d['acquisition']['row_order']} in {d['knobs']['fast']['name']}"], counts={"curves": len(unordered())}))],
                lambda: Pass(Shaped(pinned, g.columns)))


REPLICATE = {   # ([selection] layout, [replicate] identity) -> (may two curves share a slow value, can the reader resolve the identity); total
    **{(lay, k): v for lay in ("PER_FILE", "LONG_TABLE") for k, v in (("NONE", (False, True)), ("SEED", (False, False)), ("RUN", (False, False)), ("SAMPLE", (False, False)),
                                                                     ("SAME_FAST_VALUE", (False, True)))},   # 1160 P2: replicate readings of a point, inside one curve
    ("PER_FILE", "FILE"): (True, True),
    ("LONG_TABLE", "FILE"): (False, False),   # one file holds every curve: the file tells no two curves apart
}

POINTS = {   # [replicate] identity -> a curve's rows -> its points as (fast value, readings); total over FORMAT's identities (plan 1160 P2)
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
                lambda: Pass(Census(pinned, label(curves(), [points(c) for c in curves()], d["knobs"]["fast"]["name"]), tuple((c.where, len(points(c))) for c in curves()))))


def label(curves, points, fast):
    """The sampling label of curves and their points (fast value, readings), counted per point (plan 1160 P2)."""
    ns, xs, rs = [len(p) for p in points], [x for p in points for x, _ in p], [n for p in points for _, n in p]
    seqs = {tuple(x for x, _ in p) for p in points}
    return Sampling(len(curves), sum(len(c.slow) for c in curves), min(ns), statistics.median(ns), max(ns), fast, len(set(xs)),
                    {True: Alignment.ALIGNED, False: Alignment.MISALIGNED}[len(seqs) == 1], (min(rs), max(rs)), max(c.drift for c in curves))


def bodies(t, d):
    """The registered data-stage bodies of one run (S3, S4, S5; plan 1139; S6, plan 1160 P4), closed over the tables and the declaration directory. Each has
    exactly its SIGNATURE row (tests/test_intake.py)."""
    def s3(declaration: Declaration) -> Pass | Refuse:
        return source_integrity(declaration, d, t)

    def s4(pinned: Pinned) -> Pass | Refuse:
        return shape(pinned, t)

    def s5(pinned: Pinned, shaped: Shaped) -> Pass | Refuse:
        return census(pinned, shaped, t)

    def s6(census: Census) -> Pass | Refuse:
        return admissibility(census, d, t)
    return {"S3": s3, "S4": s4, "S5": s5, "S6": s6}
