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

import intake_seal
from intake_blind import Declaration, Pass, Refuse

ROOT = Path(__file__).resolve().parent.parent


class Alignment(enum.Enum):
    """Whether the curves share one fast-knob grid. ATOMS: ALIGNED | MISALIGNED. Axiom: exactly one holds for a census (every curve holds the
    same fast values in the same order; or not)."""
    ALIGNED = frozenset({"ALIGNED"})
    MISALIGNED = frozenset({"MISALIGNED"})


@dataclass(frozen=True)
class File:
    """One selected file as S3 read it. Invariant: sha256 is the sha256 of `data`, and equals the pin at its first logged loader read."""
    name: str
    slow: float
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
class Grid:
    """A csv-curve-v1 file read from bytes. Invariant: `columns` is its header; every row of `rows` holds one float per column."""
    columns: tuple
    rows: tuple
    readable = True


@dataclass(frozen=True)
class Unreadable:
    """A file the csv-curve-v1 reader cannot read (not UTF-8, a cell that is not a number, a row of another width). Invariant: it holds no row,
    and `readable` is False, so S4 refuses READER_REFUSED and S5 FILE_DIFFERS_FROM_FIRST before any column is compared."""
    why: str
    columns = ()
    rows = ()
    readable = False


@dataclass(frozen=True)
class Shaped:
    """S4 SHAPE: the first file's columns, equal to the declared ones, its rows in the declared order. Invariant: carries the Pinned."""
    pinned: Pinned
    columns: tuple

    def summary(self):
        d = self.pinned.declaration.data
        return (f"The first file's header is {','.join(self.columns)}, the declared columns, and its rows are stored {d['acquisition']['row_order']} "
                f"in {d['knobs']['fast']['name']}")

    def confirmed(self):
        return False


@dataclass(frozen=True)
class Sampling:
    """The sampling label of a census. Invariant: n_min <= n_median <= n_max over `curves` curves; span is the (lowest, highest) fast value."""
    curves: int
    n_min: int
    n_median: float
    n_max: int
    fast: str
    span: tuple
    alignment: Alignment


@dataclass(frozen=True)
class Census:
    """S5 CENSUS: the sampling label (curves, points per curve, fast-knob span, alignment). Invariant: carries the Pinned it counted."""
    pinned: Pinned
    label: Sampling

    def summary(self):
        x = self.label
        return (f"Every file has the first file's columns; no slow value or fast value repeats. Sampling: {x.curves} curves; points per curve "
                f"min {x.n_min}, median {x.n_median:g}, max {x.n_max}; {x.fast} span [{x.span[0]:g}, {x.span[1]:g}]; {x.alignment.name}")

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


def gate(checks, then):
    """then() (a Pass or a Refuse) when every (holds, reason, detail) row holds, else Refuse(reason, detail()) of the first row that does not.
    Rows are evaluated in order and lazily (each `holds` and `detail` is a function), so a row runs only when every row before it held."""
    failed = list(itertools.islice((c for c in checks if not c[0]()), 1))
    return {True: then, False: lambda: Refuse(failed[0][1], failed[0][2]())}[not failed]()


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


NUMBER = re.compile(r"[-+]?\d+(\.\d*)?([eE][-+]?\d+)?")
SLOW = {   # [knobs.slow] source -> (resolves, value) per selected name, before any byte is read; total over FORMAT's sources
    "PER_FILE": lambda k, names: {True: lambda: [(True, float(v)) for v in k["per_file"]], False: lambda: [(False, 0.0)] * len(names)}[len(k["per_file"]) == len(names)](),
    "PATH_PATTERN": lambda k, names: [(m is not None and NUMBER.fullmatch(m[1]) is not None, float({True: lambda: m[1], False: lambda: "0"}[m is not None and NUMBER.fullmatch(m[1]) is not None]()))
                                      for m in (re.fullmatch(k["pattern"], n) for n in names)],
    "FILE_KEY": lambda k, names: [(False, 0.0)] * len(names),   # a value inside the file cannot be resolved before the file is admitted
}


def admit(loc, name, truth_side, slow):
    """Admission of one selected name before it is read: inside the source root, no path part on the truth side, its slow value resolves, a
    file. Returns the parts that fail (empty: admitted)."""
    path = Path(loc) / name
    return [w for ok, w in ((path.resolve().is_relative_to(Path(loc).resolve()), "outside the source root"), (not set(Path(name).parts) & set(truth_side), "on the truth side"),
                            (slow[0], "its slow value does not resolve"), (path.is_file(), "not a file")) if not ok]


def source_integrity(declaration, d, t):
    """S3 SOURCE_INTEGRITY. Invariant: ROOT_UNRESOLVED | UNIVERSE_CHANGED (names and sizes against the seal, only when a SEAL.json exists) |
    PATH_NOT_ADMITTED are decided before any byte is read; then each file is read once through the logged loader, and PIN_MISMATCH when its
    sha256 differs from the sha256 at its first logged loader read (the pin)."""
    src, sel, k = declaration.data["source"], declaration.data["selection"], declaration.data["knobs"]["slow"]
    loc, rec = located(src["root"], t["roots"]), intake_seal.record(d)
    names = [sel["pattern"].format(index=i) for i in range(sel["index"]["first"], sel["index"]["last"] + 1)]
    slow = SLOW[k["source"]](k, names)
    turned = lambda: [(n, w) for n, s in zip(names, slow) for w in admit(loc, n, src["truth_side"], s)]
    return gate([(lambda: loc != "" and Path(loc).is_dir(), "ROOT_UNRESOLVED", lambda: f"root '{src['root']}' (names in intake/ROOTS.toml: {sorted(t['roots'])})"),
                 (lambda: rec == {} or intake_seal.listing(loc, src["universe"]) == rec["universe"]["listing"], "UNIVERSE_CHANGED",
                  lambda: f"{len(intake_seal.listing(loc, src['universe']))} names now, {len(rec['universe']['listing'])} sealed"),
                 (lambda: not turned(), "PATH_NOT_ADMITTED", lambda: "; ".join(f"{n}: {w}" for n, w in turned()[:3]))],
                lambda: _read(declaration, d, loc, names, slow))


def _read(declaration, d, loc, names, slow):
    """Each admitted file read once through the logged loader (the access log is declarations/<id>/access.log; the bank's parent directory is
    a declared partition too, so an in-process open of the truth side beside the bank is logged as a bypass); then each pin compared."""
    loader = _t23().Loader({loc: "universe", str(Path(loc).parent): "outside-universe"}, Path(d) / "access.log")
    files = tuple(File(n, s[1], hashlib.sha256(b).hexdigest(), b) for n, s in zip(names, slow) for b in [loader.read(Path(loc) / n)])
    pins = {}
    for a in intake_seal.lines(Path(d) / "access.log"):
        pins.setdefault(a["path"], a["sha256"]) if a["route"] == "loader" else None
    moved = lambda: [f.name for f in files if pins[str((Path(loc) / f.name).resolve())] != f.sha256]
    return gate([(lambda: not moved(), "PIN_MISMATCH", lambda: f"{len(moved())} files differ from their pins, first {moved()[:3]}")], lambda: Pass(Pinned(declaration, files)))


def read_csv(data):
    """csv-curve-v1: a header line, then rows of numbers, comma-separated. Grid | Unreadable; the one place a decode or float error becomes a value."""
    try:
        lines = data.decode().splitlines()
        rows = tuple(tuple(float(x) for x in ln.split(",")) for ln in lines[1:])
    except (UnicodeDecodeError, ValueError) as e:
        return Unreadable(str(e))
    head = tuple(",".join(lines[:1]).split(","))
    return {True: lambda: Grid(head, rows), False: lambda: Unreadable(f"a row does not hold {len(head)} values")}[all(len(r) == len(head) for r in rows)]()


def readers(t):
    """The reader of each FORMAT [source] reader value: csv-curve-v1 is live; every other value reads to Unreadable (READER_NOT_LIVE)."""
    return {**{r: (lambda data, r=r: Unreadable(f"READER_NOT_LIVE: reader '{r}' has no body yet")) for r in t["format"]["fields"]["source"]["fields"]["reader"]["values"]},
            "csv-curve-v1": read_csv}


ORDER = {   # [acquisition] row_order -> does a sequence of fast values hold it; total over FORMAT's row_order values
    "ASCENDING": lambda xs: all(a <= b for a, b in zip(xs, xs[1:])),
    "DESCENDING": lambda xs: all(a >= b for a, b in zip(xs, xs[1:])),
    "ACQUISITION": lambda xs: True,   # stored in acquisition order: no claim about the fast knob to check
}
COLUMNS = {"csv-curve-v1": lambda d: (d["knobs"]["fast"]["key"], d["measured"]["key"], "sigma")}   # the reader's declared columns (FORMAT v1 has no field for the third)


def shape(pinned, t):
    """S4 SHAPE on the first file only. Invariant: READER_NOT_LIVE | READER_REFUSED | COLUMNS_DIFFER | ROW_ORDER_DIFFERS, in that order."""
    d = pinned.declaration.data
    g, live = readers(t)[d["source"]["reader"]](pinned.files[0].data), d["source"]["reader"] in COLUMNS
    return gate([(lambda: live, "READER_NOT_LIVE", lambda: f"reader '{d['source']['reader']}'"),
                 (lambda: g.readable, "READER_REFUSED", lambda: f"{pinned.files[0].name}: {g.why}"),
                 (lambda: g.columns == COLUMNS[d["source"]["reader"]](d), "COLUMNS_DIFFER", lambda: f"{pinned.files[0].name} header {','.join(g.columns)}, declared {','.join(COLUMNS[d['source']['reader']](d))}"),
                 (lambda: ORDER[d["acquisition"]["row_order"]]([r[0] for r in g.rows]), "ROW_ORDER_DIFFERS", lambda: f"{pinned.files[0].name} is not {d['acquisition']['row_order']} in {g.columns[0]}")],
                lambda: Pass(Shaped(pinned, g.columns)))


REPLICATE = {   # [replicate] identity -> (may two curves share a slow value, can csv-curve-v1 read the identity); total over FORMAT's identities
    "NONE": (False, True), "FILE": (True, True), "SEED": (False, False), "RUN": (False, False), "SAMPLE": (False, False),
}


def census(pinned, shaped, t):
    """S5 CENSUS over every file. Invariant: FILE_DIFFERS_FROM_FIRST | REPLICATE_KEY_UNRESOLVED | CURVE_REPEATED | FAST_VALUE_REPEATED, in that
    order; then the sampling label (curves; points per curve min, median, max; the fast span; ALIGNED or MISALIGNED)."""
    d = pinned.declaration.data
    grids = [readers(t)[d["source"]["reader"]](f.data) for f in pinned.files]
    rep, hs = REPLICATE[d["replicate"]["identity"]], [f.slow for f in pinned.files]
    other = [f.name for f, g in zip(pinned.files, grids) if g.columns != shaped.columns]
    twice = lambda: [f.name for f, g in zip(pinned.files, grids) if len({r[0] for r in g.rows}) != len(g.rows)]
    return gate([(lambda: not other, "FILE_DIFFERS_FROM_FIRST", lambda: f"{len(other)} files, first {other[:3]}"),
                 (lambda: rep[1], "REPLICATE_KEY_UNRESOLVED", lambda: f"identity {d['replicate']['identity']}: csv-curve-v1 carries no replicate key"),
                 (lambda: rep[0] or len(set(hs)) == len(hs), "CURVE_REPEATED", lambda: f"{d['knobs']['slow']['name']} values repeated: {sorted({h for h in hs if hs.count(h) > 1})}"),
                 (lambda: not twice(), "FAST_VALUE_REPEATED", lambda: f"{len(twice())} curves, first {twice()[:3]}")],
                lambda: Pass(Census(pinned, label(grids, d["knobs"]["fast"]["name"]))))


def label(grids, fast):
    """The sampling label of readable grids whose first column is the fast knob."""
    ns, xs = [len(g.rows) for g in grids], [r[0] for g in grids for r in g.rows]
    seqs = {tuple(r[0] for r in g.rows) for g in grids}
    return Sampling(len(grids), min(ns), statistics.median(ns), max(ns), fast, (min(xs), max(xs)), {True: Alignment.ALIGNED, False: Alignment.MISALIGNED}[len(seqs) == 1])


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
