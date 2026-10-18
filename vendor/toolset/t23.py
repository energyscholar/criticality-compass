"""t23.py — T23 (CONTRACTS v1, v1.1, v1.2 G): exploration log + sealed tests + claim register, with a LOGGING LOADER and a seal checker
that NEVER claims complete protection. NOT REGISTERED (Argus gates and registers).

DECLARED RULES (written before any control ran):
 R1 Partitions are DECLARED: a map {path prefix -> partition name}. A path under no declared prefix is partition "undeclared".
 R2 Every read through Loader.read()/np_load() appends ONE JSON line to the append-only ACCESS LOG (O_APPEND) BEFORE the bytes are returned:
    {t_ns, partition, path, sha256 (of the bytes read), size, argv, pid, git_head, route:"loader"}. Reproducible identifiers = path + sha256 + git HEAD.
 R3 In-process bypass (a Python open() of a declared-partition path NOT via the loader) is caught by a sys.addaudithook and logged with
    route:"in-process-bypass". This is the only bypass class the module can SEE.
 R4 UNENFORCED read paths are LISTED in every checker output (constant UNENFORCED below) — never omitted, never summarised away:
    direct shell reads (cat/less/head/cp/rsync/scp), other processes and external tools (MATLAB, editors, another Python without this module,
    Jupyter kernels), reads on another host or another copy of the bytes, memory of a human who looked.
 R5 atime TRIPWIRE (weak evidence only): a file whose st_atime_ns > st_mtime_ns and lies inside no logged loader read's [t_start, t_log] span
    is reported UNLOGGED_ACCESS_EVIDENCE (amended after debug run 2: 'later than every logged read' was a logic error, see results). Under relatime a read updates atime only if atime <= mtime (or > 24 h old): a SILENT tripwire is NOT evidence
    of no read (an empty output is not a zero). FIRED is evidence.
 R6 Seal: seal(test_text) appends {t_ns, sha256(text)} to the append-only SEAL LOG and writes the sealed test file. Seal time is the log time.
 R7 Checker verdict = lookup in a TOTAL table over three booleans (seal exists, first logged confirmatory read predates the seal,
    unlogged-access evidence before the seal [bypass log line or tripwire]):
        no seal                                  -> REFUSED_NO_SEAL
        seal, read before seal                   -> REFUSED_SEAL_POSTDATES_READ
        seal, no logged pre-seal read, evidence  -> REFUSED_UNLOGGED_ACCESS_EVIDENCE
        seal, no logged pre-seal read, no evid.  -> ADMITTED_ON_LOGGED_PATHS_ONLY
    The verdict type has NO "protected"/"complete" value: every verdict carries the UNENFORCED list (R4).
"""
import hashlib
import json
import os
import subprocess
import sys
import time
from pathlib import Path

COARSE_NS = 10_000_000   # tolerance (named, finite precision): kernel atime uses the COARSE clock, which lags time.time_ns() by up to a tick
UNENFORCED = ("direct shell reads (cat, less, head, cp, rsync, scp) — not logged",
              "other processes / external tools (MATLAB, editors, a Python without this module, Jupyter) — not logged",
              "reads of another copy of the bytes (other host, backup, download cache) — not logged",
              "atime tripwire is weak: relatime/noatime mounts suppress updates; SILENT is not evidence of no read")
VERDICT = {(False, False, False): "REFUSED_NO_SEAL", (False, False, True): "REFUSED_NO_SEAL",
           (False, True, False): "REFUSED_NO_SEAL", (False, True, True): "REFUSED_NO_SEAL",
           (True, True, False): "REFUSED_SEAL_POSTDATES_READ", (True, True, True): "REFUSED_SEAL_POSTDATES_READ",
           (True, False, True): "REFUSED_UNLOGGED_ACCESS_EVIDENCE",
           (True, False, False): "ADMITTED_ON_LOGGED_PATHS_ONLY"}            # total over 2^3 (seal, pre-seal read, evidence)


def _append(path, rec):
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o644)    # plumbing: append-only by open mode
    os.write(fd, (json.dumps(rec, sort_keys=True) + "\n").encode()); os.close(fd)


def _head(where):
    r = subprocess.run(["git", "-C", str(where), "rev-parse", "HEAD"], capture_output=True, text=True)
    return r.stdout.strip() or "NO-GIT"                                    # plumbing: honest null when not a repo


class Loader:
    def __init__(self, partitions, access_log, hook=True):
        self.parts = {str(Path(k).resolve()): v for k, v in partitions.items()}
        self.log = Path(access_log)
        self._inside = False
        self.head = _head(Path(next(iter(self.parts))).parent) if self.parts else "NO-GIT"
        if hook:
            sys.addaudithook(self._audit)

    def partition(self, path):
        p = str(Path(path).resolve())
        hits = [v for k, v in self.parts.items() if p == k or p.startswith(k + os.sep)]
        return (hits + ["undeclared"])[0]

    def _rec(self, path, data, route):
        return dict(t_ns=time.time_ns(), partition=self.partition(path), path=str(Path(path).resolve()), route=route,
                    sha256=hashlib.sha256(data).hexdigest() if data is not None else None, size=None if data is None else len(data),
                    argv=sys.argv, pid=os.getpid(), git_head=self.head)

    def read(self, path):
        self._inside = True
        t0 = time.time_ns()
        try:
            data = Path(path).read_bytes()
        finally:
            self._inside = False
        _append(self.log, dict(self._rec(path, data, "loader"), t_start_ns=t0))   # R2: logged before the bytes are returned
        return data

    def np_load(self, path):
        import io
        import numpy as np
        return np.load(io.BytesIO(self.read(path)))

    def _audit(self, event, args):
        reading = event == "open" and (isinstance(args[1], str) and "r" in args[1] and "+" not in args[1]
                                       or args[1] is None and isinstance(args[2], int) and args[2] & os.O_ACCMODE == os.O_RDONLY)
        if reading and not self._inside and isinstance(args[0], (str, bytes, os.PathLike)) and str(args[0]) != str(self.log):
            part = self.partition(os.fsdecode(args[0]))
            if part != "undeclared":                                       # R3: only declared-partition paths are bypasses
                _append(self.log, self._rec(os.fsdecode(args[0]), None, "in-process-bypass"))


def seal(text, sealed_file, seal_log):
    Path(sealed_file).write_text(text)
    rec = dict(t_ns=time.time_ns(), sha256=hashlib.sha256(text.encode()).hexdigest(), file=str(Path(sealed_file).resolve()))
    _append(seal_log, rec)
    return rec


def _lines(p):
    return [json.loads(x) for x in Path(p).read_text().splitlines()] if Path(p).exists() else []


def check(claim, seal_log, access_log, files):
    """claim = {id, sealed_sha, partition}. files = the confirmatory files the claim rests on (access lines and tripwire are restricted to them)."""
    seals = [s for s in _lines(seal_log) if s["sha256"] == claim["sealed_sha"]]
    t_seal = min([s["t_ns"] for s in seals], default=None)
    paths = {str(Path(f).resolve()) for f in files}
    acc = [a for a in _lines(access_log) if a["partition"] == claim["partition"] and a["path"] in paths]   # the claim's declared files only
    logged = [a["t_ns"] for a in acc if a["route"] == "loader"]
    bypass = [a["t_ns"] for a in acc if a["route"] == "in-process-bypass"]
    trip = {str(f): os.stat(f).st_atime_ns for f in files}
    fired = {f: t for f, t in trip.items() if t > os.stat(f).st_mtime_ns
             and not any(a["path"] == f and a["route"] == "loader" and a["t_start_ns"] - COARSE_NS <= t <= a["t_ns"] for a in acc)}
    # R5: atime after mtime, and no logged loader read whose [start, log] span contains that atime (the read that set it)
    has_seal = t_seal is not None
    tref = t_seal if has_seal else 0
    pre_read = has_seal and any(t < tref for t in logged)
    evidence = has_seal and (any(t < tref for t in bypass) or any(t < tref for t in fired.values()))
    return dict(claim=claim["id"], verdict=VERDICT[(has_seal, pre_read, evidence)], seal_t_ns=t_seal, logged_reads=len(logged),
                in_process_bypass=len(bypass), tripwire={f: ("FIRED" if f in fired else "SILENT (not evidence of no read)") for f in trip},
                unenforced=UNENFORCED)
