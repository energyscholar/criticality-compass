"""intake_bytes - S3 SOURCE_INTEGRITY and S6 ADMISSIBILITY of the intake.
Invariant: the only intake stage module that opens a data byte, and only through the vendored t23 logged loader (declarations/<id>/access.log),
once per file, in S3; and the only one that reads that access log (S6). Every refusal is a value: a check is a (holds, reason, detail) row and
`gate` returns the first row that does not hold."""
import hashlib
import importlib.util
import re
from pathlib import Path

import intake_seal
from intake_blind import Declaration, Pass, Refuse, detail, gate
from intake_evidence import Census, File, Lineage, Pinned


ROOT = Path(__file__).resolve().parent.parent


def _t23():
    """The vendored logged loader (vendor/toolset/t23.py, pinned by vendor/toolset/PIN.toml), loaded by path: vendor/toolset is never put on
    sys.path, where its intake.py would shadow cc/intake.py."""
    spec = importlib.util.spec_from_file_location("t23", ROOT / "vendor" / "toolset" / "t23.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def located(text, roots):
    """The directory a declared source root names ("<name>/<relative path>", the name a row of intake/ROOTS.toml), or "" when it names none.
    The pattern admits only a declared name (the never-matching (?!) keeps the alternation total) and no ".." part."""
    m = re.fullmatch("(" + "|".join([*map(re.escape, roots), "(?!)"]) + r")((?:/(?!\.\.(?:/|$))[\w.-]+)*)", text)
    return {True: lambda: str(Path(roots[m[1]]) / m[2].lstrip("/")), False: lambda: ""}[m is not None]()


ADMIT = (   # the loader's admission of one selected name before any byte is read, one row per reason, in this order
    ("PATH_OUTSIDE_ROOT", "names that resolve outside the source root", lambda loc, n, src: (Path(loc) / n).resolve().is_relative_to(Path(loc).resolve())),
    ("PATH_ON_TRUTH_SIDE", "names with a path part on the truth side", lambda loc, n, src: not set(Path(n).parts) & set(src["truth_side"])),
    ("PATH_NOT_A_FILE", "names that are not a file", lambda loc, n, src: (Path(loc) / n).is_file()),
)


def admission(loc, names, src):
    """One gate row per ADMIT row: (holds, reason, detail) over every selected name; the detail names the first three that fail."""
    failing = lambda ok: [n for n in names if not ok(loc, n, src)]
    return [(lambda ok=ok: not failing(ok), code, lambda ok=ok, what=what: detail(words=failing(ok)[:3], counts={what: len(failing(ok))})) for code, what, ok in ADMIT]


SOURCE = {   # [source] kind -> the S3 body of that kind; total over FORMAT's [source] kinds
    "DEPOSIT": lambda declaration, d, t: _deposit(declaration, d, t, lambda loc: _t23().Loader({loc: "universe", str(Path(loc).parent): "outside-universe"}, Path(d) / "access.log")),
    "CONVERTED": lambda declaration, d, t: _converted(declaration, d, t),
}


def source_integrity(declaration, d, t):
    """S3 SOURCE_INTEGRITY: its body for the declared [source] kind (SOURCE). A CONVERTED source first proves the chain from
    converted_from to the bank (CONVERSION_CHAIN_BROKEN), then its bank is read exactly as a DEPOSIT."""
    return SOURCE[declaration.data["source"]["kind"]](declaration, d, t)


def _converted(declaration, d, t):
    """S3 for a CONVERTED source: cc/intake_convert.py's chain check (imported here: it imports this module), then _deposit through the same
    loader (one loader per run, so no loader's audit hook logs another loader's read as a bypass, which S6 would refuse)."""
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
    pins = dict(reversed([(a["path"], a["sha256"]) for a in intake_seal.lines(Path(d) / "access.log") if a["route"] == "loader"]))   # the first read wins
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


def bodies(t, d):
    """The registered bodies of S3 and S6, closed over the tables and the declaration directory (each has its signature row, tests/test_intake.py)."""
    def s3(declaration: Declaration) -> Pass | Refuse:
        return source_integrity(declaration, d, t)

    def s6(census: Census) -> Pass | Refuse:
        return admissibility(census, d, t)
    return {"S3": s3, "S6": s6}
