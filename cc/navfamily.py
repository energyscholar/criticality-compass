"""navfamily - plan 1176 phase D: `bin/cc navigate family <id>` and `bin/cc navigate score <id> <checkpoints.toml>`, family mode over the
frozen line navigator (cc/linenav.py, a byte-for-byte copy of the toolset's tools/linenav.py v2.1-T; docs/navigate.md records its sha256).
Role navigate_family, its own cap (tests/test_budget.py NAVFAMILY_CAP). It is an ADAPTER: the frozen geometry is never edited and its PARAMS
are read as they are (grid mode, w_c 5 cells).
A family is an intake declaration (declarations/<id>/intake.toml) whose run reaches S5 CENSUS with no stage refused. Its plane and its suspect
are phase A's (cc/intake_suspect.py: curve rank x sample rank, the declarer's guess in cells); its side oracle is phase B's
(cc/intake_feature.py) built over THE SAME Plane (Plane.source, A-E6: the sliced curves), so a curve rank names one curve in both. linenav
reads linenav.Side through the oracle's `alphabet` and its evidence is linenav's FiniteStored (B-E3). Every refusal is a typed value printed
as `REFUSED <code>: ...` with exit status 1: this module's own (REFUSAL), the intake's first refused stage, intake_suspect.Refused and
intake_feature.Unprojected (B-E2, A-E2).
The checkpoints (`score`) are a STRUCTURAL hold-out: they live outside declarations/, only score() names them, and family() takes no
argument that could reach them. Every file a command opens is appended to its own access log (T23, extended to every open of this process
by an audit hook): results/navigate/<id>.access.jsonl for family, results/navigate/<id>.score.access.jsonl for score (LOG)."""
import json
import os
import sys
import time
import tomllib
from dataclasses import dataclass
from pathlib import Path

import numpy as np

import intake
import intake_feature
import intake_suspect
import linenav
import navmap
from intake_fold import Primary, verdicts

UNTESTED = ("UNTESTED: cc navigate (family mode) is tested on planted families only (tests/test_navfamily.py); no real family's transcript "
            "has been scored against a known line.")
REFUSAL = {   # code -> sentence; every code this module emits is a row (tests/test_navfamily.py)
    "NO_DECLARATION": "There is no declarations/<id>/ directory: family mode navigates an intake declaration.",
    "INTAKE_REFUSED_AT": "The intake refused the declaration at a stage, so it has no census to navigate (bin/cc intake run <id> shows why).",
    "CHECKPOINTS_INSIDE_DECLARATIONS": "Checkpoints are a hold-out: they must live outside declarations/, where no family reader looks.",
    "CHECKPOINTS_UNREADABLE": "The checkpoints file is not a TOML table with `points = [[slow, fast], ...]` of at least one vertex.",
}
LOG = {"family": "{id}.access.jsonl", "score": "{id}.score.access.jsonl"}   # command -> its access log under results/navigate/ (never shared)
DIRS = {-1: "backward", 1: "forward"}   # linenav's direction keys -> words


@dataclass(frozen=True)
class Refusal:
    """A typed refusal of this module. Invariant: `code` is a key of REFUSAL."""
    code: str
    detail: str

    def words(self):
        return f"{self.code}: {REFUSAL[self.code]} Detail: {self.detail}"


REFUSED = (Refusal, intake_suspect.Refused, intake_feature.Unprojected)   # every typed refusal a step may return (each has words())


def then(x, f):
    """f(x), unless x is already a typed refusal (it passes through unchanged): the steps of a walk stop at the first refusal."""
    return {True: lambda: x, False: lambda: f(x)}[isinstance(x, REFUSED)]()


@dataclass(frozen=True)
class Walked:
    """One family walked: its plane and suspect (phase A), its oracle (phase B, over the same plane) and linenav's record."""
    ident: str
    cells: intake_suspect.Cells
    oracle: intake_feature.Oracle
    rec: dict


def logged(root, ident, command):
    """Open the command's access log (append-only) and record every later open of this process in it: one JSON line per open, written
    with os.write on the log's own descriptor (os.write opens nothing, so the hook never records itself). Returns the log's path."""
    path = Path(root) / "results" / "navigate" / LOG[command].format(id=ident)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o644)   # plumbing: append-only by open mode
    base = dict(partition=f"family:{ident}", argv=sys.argv[1:], pid=os.getpid(), git_head=navmap._head(root), route=f"open:{command}")
    line = lambda a: (json.dumps({**base, "t_ns": time.time_ns(), "path": str(a[0]), "mode": str(a[1])}, sort_keys=True) + "\n").encode()   # noqa: E731
    sys.addaudithook(lambda event, a: {True: lambda: os.write(fd, line(a)), False: lambda: 0}[event == "open"]())
    return path


def census(root, ident):
    """(tables, S5's Census, S2's seal state) of the declaration's intake run, or Refusal INTAKE_REFUSED_AT naming the first refused stage."""
    t, d, out = intake._go(root, ident, lambda t: t["stages"]["stage"])
    p = verdicts(t, out)[0]
    return {True: lambda: Refusal("INTAKE_REFUSED_AT", f"stage {p.at}: {out[p.at].text(t) if p.at else ''}"),
            False: lambda: (t, out["S5"].result.evidence, out["S2"].result.evidence)}[p.kind is Primary.PRIMARY_REFUSED_AT]()


def declared(root, ident):
    """ident, when it names a directory of declarations/ (a name, never a path), else Refusal NO_DECLARATION."""
    names = {p.name for p in (Path(root) / "declarations").iterdir() if p.is_dir()}
    return {True: lambda: ident, False: lambda: Refusal("NO_DECLARATION", f"declarations/{ident}/")}[ident in names]()


def oracle_for(t, cells, census, seal):
    """The side oracle over the suspect's OWN plane (A-E6: Plane.source, the sliced curves in slow order), answering in linenav.Side with
    linenav's FiniteStored evidence (B-E3): a curve rank names the same curve for the suspect and for the oracle."""
    return intake_feature.on(t, cells.plane.source, census, seal, linenav.Side)


def walk(root, ident):
    """Walked, or the first typed refusal: its intake run, its suspect in cells, the oracle over the suspect's plane, linenav."""
    tcs = census(root, ident)
    cells = then(tcs, lambda x: intake_suspect.suspect(x[0], x[1]))
    orc = then(cells, lambda c: oracle_for(tcs[0], c, tcs[1], tcs[2]))
    return then(orc, lambda o: Walked(ident, cells, o, linenav.navigate([[float(a), float(b)] for a, b in cells.cells], o, plane(cells), mode="grid")))


def plane(cells):
    """linenav's grid plane of a suspect's family: (0, 0) .. (curves - 1, n_max - 1) in cells."""
    return linenav.Plane(lo=(0, 0), hi=(cells.curves - 1, cells.n_max - 1), grid=True)


def path_of(rec):
    """The traced polyline as a list of cell pairs (empty when the line was not acquired)."""
    return {True: lambda: [tuple(float(x) for x in p) for p in rec["path"]], False: lambda: []}[rec["path"] is not None]()


def cell_text(p):
    return f"({p[0]:g}, {p[1]:g})"


def terminals(rec):
    return {True: lambda: ", ".join(f"{DIRS[k]} {v['term'].name}" for k, v in sorted(rec["dirs"].items())),
            False: lambda: "none (the line was not acquired)"}[len(rec["dirs"]) > 0]()


def measured(pl, c, s):
    """The physical bracket of a cell: ([slow at floor c, slow at ceil c], [the measured fast values at ranks floor s, ceil s on those
    curves]) - the measured values at the neighbouring cells, never a value between them; a rank beyond a curve's samples contributes none."""
    ks = sorted({int(np.floor(c)), int(np.ceil(c))})
    fast = sorted(float(pl.curves[k][1][j]) for k in ks for j in sorted({int(np.floor(s)), int(np.ceil(s))}) if j < len(pl.curves[k][1]))
    return [float(pl.curves[ks[0]][0][0]), float(pl.curves[ks[-1]][0][0])], fast[:1] + fast[-1:]


def toml_text(w):
    pl, rec = w.cells.plane, w.rec
    pts = [measured(pl, c, s) for c, s in path_of(rec)]
    return (f'schema = 1\nkind = "navigate-family"\nid = "{w.ident}"\nverdict = "{rec["verdict"].name}"\nterminals = "{terminals(rec)}"\n'
            f'evidence = "{w.oracle.evidence.source}"\n# the traced polyline: in cells, and per point the measured values of its neighbouring cells '
            f'([slow lo, slow hi], [fast lo, fast hi]); nothing between measured points is formed\n'
            f'cells = [{", ".join(f"[{c!r}, {s!r}]" for c, s in path_of(rec))}]\n'
            f'physical = [{", ".join(f"[{sl!r}, {fa!r}]" for sl, fa in pts)}]\n')


def transcript(w, shown, log_name):
    c = w.cells
    return [UNTESTED,
            f"family {w.ident} (family mode): {c.curves} curves x up to {c.n_max} samples; plane (0, 0) .. ({c.curves - 1}, {c.n_max - 1}) in cells",
            f"oracle: {intake_feature.KEY} side oracle over the suspect's plane; evidence {type(w.oracle.evidence).__name__}({w.oracle.evidence.source})",
            f"suspect: {' '.join(cell_text(p) for p in c.cells)} (corridor {c.corridor}: linenav grid PARAMS, w_c {linenav.PARAMS['grid']['wc']} cells)",
            f"verdict: {w.rec['verdict'].name}",
            f"terminals: {terminals(w.rec)}",
            f"path (cells): {' '.join(cell_text(p) for p in path_of(w.rec)) or '(none)'}",
            f"reads: {w.rec['calls']} distinct cells of budget {linenav.PARAMS['grid']['budget']}",
            f"results: {shown} (the polyline in physical units, as measured brackets)",
            f"T23 access log: {log_name} (every open of this process); {navmap.UNLOGGED}"]


def refusal_text(r):
    return [UNTESTED, f"REFUSED {r.words()}"]


def rel(root, p):
    return str(Path(p).resolve().relative_to(Path(root).resolve()))


def _wrote(root, w, log):
    out = Path(root) / "results" / "navigate" / f"{w.ident}.toml"
    out.write_text(toml_text(w))
    return transcript(w, rel(root, out), rel(root, log)), 0


def _family(root, ident):
    log = logged(root, ident, "family")
    w = walk(root, ident)
    return {True: lambda: (refusal_text(w), 1), False: lambda: _wrote(root, w, log)}[isinstance(w, REFUSED)]()


def family(root, ident):
    """(lines, exit status) of `bin/cc navigate family <id>`. It takes no checkpoints: the hold-out is out of its reach by signature."""
    have = declared(root, ident)
    return {True: lambda: (refusal_text(have), 1), False: lambda: _family(root, ident)}[isinstance(have, REFUSED)]()


def points(root, f):
    """The checkpoints file's vertices, or a Refusal: it must lie outside declarations/ and hold `points` (>= 1 vertex)."""
    p = Path(f).resolve()
    data = {True: lambda: tomllib.loads(p.read_text()), False: lambda: {}}[p.is_file()]()
    return {(False, True): lambda: data["points"], (False, False): lambda: Refusal("CHECKPOINTS_UNREADABLE", p.name),
            (True, True): lambda: Refusal("CHECKPOINTS_INSIDE_DECLARATIONS", p.name), (True, False): lambda: Refusal("CHECKPOINTS_INSIDE_DECLARATIONS", p.name)}[
        (p.is_relative_to((Path(root) / "declarations").resolve()), isinstance(data.get("points"), list) and len(data.get("points")) > 0)]()


def distance(path, u):
    """Distance in cells from a checkpoint cell to the traced polyline (linenav.seg_dist); None when no line was traced."""
    return {True: lambda: linenav.seg_dist(np.asarray(u, float), path), False: lambda: None}[len(path) > 0]()


WITHIN = {True: lambda d: d <= linenav.PARAMS["grid"]["wc"], False: lambda d: False}   # was a line traced -> (distance) -> within w_c
SCORE = {True: "FOLLOWED", False: "NOT_FOLLOWED"}   # is every checkpoint within w_c of the traced line


def _scored(w, cps):
    path = path_of(w.rec)
    ds = [distance(path, u) for u in cps]
    ok = [WITHIN[d is not None](d) for d in ds]
    rows = [f"  checkpoint {i} {cell_text(u)}: distance {('none' if d is None else f'{d:.3f}')} cells -> {('within' if k else 'beyond')} w_c" for i, (u, d, k) in enumerate(zip(cps, ds, ok))]
    return [UNTESTED, f"score {w.ident}: navigator verdict {w.rec['verdict'].name}; {len(cps)} checkpoints converted by the suspect's rules", *rows,
            f"score: {sum(ok)} of {len(cps)} checkpoints within w_c {linenav.PARAMS['grid']['wc']} cells -> {SCORE[all(ok)]}"], 0


def score(root, ident, f):
    """(lines, exit status) of `bin/cc navigate score <id> <checkpoints.toml>`: the family walked again, then each checkpoint converted to a
    cell on the suspect's plane (exact slow, in-span nearest sample) and its distance to the traced line."""
    have = declared(root, ident)
    w = then(have, lambda i: (logged(root, i, "score"), walk(root, i))[1])
    pts = then(w, lambda _: points(root, f))
    cps = then(pts, lambda ps: (lambda each: ([c for c in each if isinstance(c, REFUSED)] + [tuple(each)])[0])([intake_suspect.cell(w.cells.plane, i, v) for i, v in enumerate(ps)]))
    return {True: lambda: (refusal_text(cps), 1), False: lambda: _scored(w, cps)}[isinstance(cps, REFUSED)]()
