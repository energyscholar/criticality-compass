"""navmap.py - `cc navigate` in stored-map mode: the stored-map reader, its T23 access log and the transcript (plumbing). UNTESTED (plan 1114, docs/navigate.md).
A STORED MAP is an existing input whose [interval] method is `chains` (m independent chains per cell, each [[data.files]] block names its chain).
Anything else is refused with a typed Refusal (a value; exit status 1), never an exception. The walk reads ONLY stored nodes, lazily (a node is
read when the walk visits it), and every file it reads goes through AccessLog.read, which appends one JSON line BEFORE the bytes are used
(the record of the toolset's studies/TAX-B1b/t23.py R2)."""
import hashlib
import io
import json
import os
import subprocess
import sys
import time
import tomllib
from dataclasses import dataclass
from pathlib import Path
import numpy as np
import declare
import navigate
import readout
import schema

UNTESTED = ("UNTESTED: cc navigate (stored-map mode) ships untested. No transcript it prints has been scored against a known transition; "
            "nothing below is evidence of a located transition.")
UNLOGGED = "reads outside this loader (a shell, another process, another copy of the bytes) are not logged"   # t23.py R4, the unenforced paths


@dataclass(frozen=True)
class Refusal:
    code: str            # NOT_A_STORED_MAP
    reason: str
    next: str


@dataclass(frozen=True)
class StoredMap:
    id: str
    observable: str
    start: str
    nodes: tuple         # [axes] point, declared order
    files: dict          # (point, size) -> tuple of (chain, data path, array key, level) at the main start, chain order
    m: int
    alpha: float
    r_declared: int
    r: int               # readout.rank(m, alpha)


class AccessLog:
    """Append-only access log (O_APPEND). read(path, name) appends {t_ns, partition, path, sha256, size, argv, pid, git_head, route} and THEN returns the bytes."""

    def __init__(self, path, partition, head):
        self.path, self.partition, self.head, self.reads = Path(path), partition, head, 0

    def read(self, physical, name):
        data = Path(physical).read_bytes()
        rec = dict(t_ns=time.time_ns(), partition=self.partition, path=name, sha256=hashlib.sha256(data).hexdigest(), size=len(data),
                   argv=sys.argv[1:], pid=os.getpid(), git_head=self.head, route="loader")
        fd = os.open(self.path, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o644)   # plumbing: append-only by open mode
        os.write(fd, (json.dumps(rec, sort_keys=True) + "\n").encode())
        os.close(fd)
        self.reads += 1
        return data


def hook_log(path, base):
    """Open `path` append-only and record every later open of this process in it: one JSON line per open (`base` plus t_ns, path, mode), written
    with os.write on the log's own descriptor (os.write opens nothing, so the hook never records itself). Returns the log's path."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o644)   # plumbing: append-only by open mode
    line = lambda a: (json.dumps({**base, "t_ns": time.time_ns(), "path": str(a[0]), "mode": str(a[1])}, sort_keys=True) + "\n").encode()   # noqa: E731
    sys.addaudithook(lambda event, a: {True: lambda: os.write(fd, line(a)), False: lambda: 0}[event == "open"]())
    return path


def _head(root):
    r = subprocess.run(["git", "-C", str(root), "rev-parse", "HEAD"], capture_output=True, text=True)
    return r.stdout.strip() or "NO-GIT"   # plumbing: an honest null when not a repository


def _stored(root, input_id, m, key):
    iv, ax = m["interval"], m["axes"]
    files = {(p, L): [] for p in ax["point"] for L in ax["size"]}
    for f in sorted((f for f in m["data"]["files"] if f["start"] == ax["main_start"]), key=lambda f: f["chain"]):
        files.setdefault((f["point"], f["size"]), []).append((f["chain"], f["path"], f["arrays"]["G"]["key"], f["arrays"]["G"].get("level", 0)))   # form: no level = one stored level (column 0 of the one-column view)
    return StoredMap(input_id, m["observable"]["name"], ax["main_start"], tuple(ax["point"]), {k: tuple(v) for k, v in files.items()},
                     iv["m"], iv["alpha"], iv["r"], readout.rank(iv["m"], iv["alpha"]))


GOT = {True: "on every file", False: "missing on some files"}   # form: total over the bool


def _not_a_map(root, input_id, m, key):
    return Refusal("NOT_A_STORED_MAP", f"input '{input_id}' declares [interval] method \"{key[0]}\", [data] format \"{key[1]}\", arrays.G {GOT[key[2]]}; "
                   f"a stored map declares method \"{STORED[0]}\", format \"{STORED[1]}\", arrays.G {GOT[STORED[2]]}",
                   "navigate an input whose [interval] method is \"chains\" and whose chain files all declare arrays.G (bin/cc help lists the inputs)")


def _no_input(root, input_id):
    names = " ".join(sorted(q.parent.name for q in (root / "inputs").glob("*/m.toml")))
    return Refusal("NOT_A_STORED_MAP", f"no input '{input_id}' under inputs/ (inputs: {names})", "bin/cc navigate <an input whose [interval] method is \"chains\">")


STORED = ("chains", "npz-v1", True)   # declared (plan 1114): method chains (m independent chains per cell), format npz-v1, arrays.G (the g1 series) on every file


def _declared(root, input_id):
    m = tomllib.loads(declare.input_path(root, input_id).read_text())
    key = (m["interval"]["method"], m["data"]["format"], all("G" in f["arrays"] for f in m["data"]["files"]))
    return {STORED: _stored}.get(key, _not_a_map)(root, input_id, m, key)   # form: one declared shape is a stored map; every other shape is the refusal


def open_map(root, input_id):
    """StoredMap or Refusal for an input id."""
    known = {q.parent.name for q in (root / "inputs").glob("*/m.toml")}
    return {True: _declared, False: _no_input}[input_id in known](root, input_id)


def node_reader(smap, ctx, log, found):
    """read(j) -> navigate.Reading at node j: the stored chains of both sizes, every file through the access log; found[j] = (chains at L 81, at L 27).
    A declared file that is not on disk is not read: the node then holds fewer chains and navigator v2's eligibility reads it NOT_ESTABLISHED (a value)."""
    local = ctx.cfg["data"].get("local", [])
    name = lambda p: {True: "data/", False: ctx.cfg["data"]["name"] + "/"}[p.split("/")[0] in local] + p  # noqa: E731

    def series(point, L):
        return [(lambda g: g.reshape(len(g), -1)[:, level])(np.load(io.BytesIO(log.read(ctx.file(p), name(p))))[key])   # form: a 1-D series is a one-column stack
                for _, p, key, level in smap.files.get((point, L), ()) if ctx.file(p).is_file()]   # form: only stored files are read

    def read(j):
        a, b = series(smap.nodes[j], navigate.BIG), series(smap.nodes[j], navigate.SMALL)
        found[j] = (len(a), len(b))
        return navigate.needle(a, b, smap.m, smap.r)
    return read


def _f(x):
    return f"{x:+.4f}"


def _line(smap, j, rd, found):
    return {True: lambda: (f"  read {smap.nodes[j]} (node {j}): side {rd.side}, cell {rd.cell.value}, median d {_f(rd.median_diff)}, "
                           f"interval [{_f(rd.interval[0])}, {_f(rd.interval[1])}], pinned L{navigate.BIG} {rd.pinned[navigate.BIG]} / "
                           f"L{navigate.SMALL} {rd.pinned[navigate.SMALL]} -> {rd.move}"),
            False: lambda: (f"  read {smap.nodes[j]} (node {j}): {rd.status}: {found[j][0]} chains stored at L{navigate.BIG}, {found[j][1]} at L{navigate.SMALL}, "
                            f"fewer than m {rd.m} -> {rd.move}")}[
        rd.status == "ESTABLISHED"]()


OUTCOME = {
    "BRACKET": lambda s, w: f"outcome: BRACKET between {s.nodes[w.lo]} and {s.nodes[w.hi]} (adjacent nodes; a bracket, never a value)",
    "STOP": lambda s, w: f"outcome: STOP at {s.nodes[w.trace[-1][0]]} (resolved inside the margin EPS {navigate.EPS}), bracket {s.nodes[w.lo]} .. {s.nodes[w.hi]}",
    "UNRESOLVED": lambda s, w: (f"outcome: UNRESOLVED at {s.nodes[w.trace[-1][0]]} (cell UNRES at m {s.m}: the interval straddles 0 and a margin edge; "
                                f"the map stores m {s.m} chains, so the walk cannot escalate). No location is claimed; bracket {s.nodes[w.lo]} .. {s.nodes[w.hi]}"),
    "NOT_ESTABLISHED": lambda s, w: f"outcome: NOT_ESTABLISHED at {s.nodes[w.trace[-1][0]]} ({navigate.NE}); bracket {s.nodes[w.lo]} .. {s.nodes[w.hi]}",
    "REFUSE": lambda s, w: (f"outcome: REFUSE (the ends read {w.trace[0][1].move} at {s.nodes[0]} and {w.trace[1][1].move} at {s.nodes[-1]}; the walk needs "
                            f"lo (DIS) at the first node and hi (ORD) at the last, in the declared order of axes.point)"),
}   # form: total over navigate.Walk.outcome


def transcript(smap, walk, log, log_name, found):
    nodes = " | ".join(f"{p} [L{navigate.BIG}: {len(smap.files.get((p, navigate.BIG), ()))}, L{navigate.SMALL}: {len(smap.files.get((p, navigate.SMALL), ()))}]"
                       for p in smap.nodes)
    read = list(dict.fromkeys(smap.nodes[j] for j, _ in walk.trace))
    return [UNTESTED,
            f"map {smap.id} (stored-map mode): {len(smap.nodes)} nodes in the declared order of axes.point; observable {smap.observable}; start {smap.start}",
            f"reading: navigator v2 at m {smap.m}, r {smap.r} (rank(m, alpha {smap.alpha}); declared r {smap.r_declared}); pair L{navigate.BIG} vs "
            f"L{navigate.SMALL}; EPS {navigate.EPS}; sink bound {navigate.BOUND} at L{navigate.BIG}",
            f"nodes (chain files declared per size): {nodes}",
            f"walk: N0 bisection over nodes 0..{len(smap.nodes) - 1}; moves on the sign cell (UNRES -> unresolved, never MID)",
            *[_line(smap, j, rd, found) for j, rd in walk.trace],
            OUTCOME[walk.outcome](smap, walk),
            f"T23 access log: {log_name} ({log.reads} reads appended; nodes visited: {', '.join(read)}); {UNLOGGED}"]


def refusal_text(rf):
    return [UNTESTED, f"REFUSED {rf.code}: {rf.reason}", f"  Next: {rf.next}"]


def _run(root, smap, log_path):
    ctx = schema.Ctx(root)
    Path(log_path).parent.mkdir(parents=True, exist_ok=True)
    log = AccessLog(log_path, f"stored-map:{smap.id}", _head(root))
    found = {}
    w = navigate.walk(node_reader(smap, ctx, log, found), len(smap.nodes))
    shown = {True: lambda: str(Path(log_path).resolve().relative_to(root.resolve())), False: lambda: Path(log_path).name}[
        Path(log_path).resolve().is_relative_to(root.resolve())]()   # plumbing: never print a location on this machine
    return transcript(smap, w, log, shown, found), 0


def main(root, input_id, log_path=None):
    """(lines, exit status). Every output's first line is UNTESTED."""
    smap = open_map(root, input_id)
    return {Refusal: lambda: (refusal_text(smap), 1),
            StoredMap: lambda: _run(root, smap, log_path or root / "results" / "navigate" / f"{input_id}.access.jsonl")}[type(smap)]()
