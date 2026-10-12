"""test_golden - recorded `bin/cc` transcripts (both modes) of tests/golden/golden.toml, byte for byte.
Each transcript is KEYED by its recorded READ SET (plan 0882 P3): tests/golden/<id>.<mode>.reads.toml lists every path the command
(and its `before` commands) touched in its copy of the repo, as the tracer (tests/trace/sitecustomize.py) OBSERVED it - files read or
stat'ed, directories listed - plus the data files it read. The key is a hash of the LIVE state of exactly those paths (absent, a
directory, or a file's sha256; a directory that was listed by its sorted entries), of the case (argv, before, plants, mode), of the
plant sources and of this harness. An equal key means the same function of the same inputs: the transcript is not run and the line
reads `ok ... (keyed)`. Anything else runs the command and compares bytes, as before.
CC_REGOLDEN=1 (bin/cc test --regolden) runs every transcript traced, rewrites the differing or missing ones (REGOLDENED) and the
read sets that moved (REKEYED), and never deletes. CC_UNKEYED=1 runs every transcript and compares bytes (the Auditor's gate)."""
import difflib
import fnmatch
import hashlib
import json
import os
import platform
import shutil
import subprocess
import sys
import tempfile
import time
import tomllib
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np
import frozen  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent

GOLD = ROOT / "tests" / "golden"
TRACE = ROOT / "tests" / "trace"
sys.path[:0] = [str(ROOT / "cc")]
import schema  # noqa: E402
DATA = schema.resolve_data_root(tomllib.loads((ROOT / "cc.toml").read_text()))[0]   # where the data IS here: CC_DATA_ROOT, else the clone's data/
TOOLSET = DATA.parent   # the toolset root: a transducer's `update` sha check reads the sampler files here (plan 0890 P3)
REGOLDEN = os.environ.get("CC_REGOLDEN") == "1"
VERBOSE = os.environ.get("CC_VERBOSE") == "1"
UNKEYED = os.environ.get("CC_UNKEYED") == "1"
NOT_READ = ("__pycache__", ".git", "*.reads.toml")   # the copy leaves these out, so they are never part of what a transcript read
                                                      # (the read sets are the key store: a key that listed its own file could not exist)


def transcript(case, mode, traced=False):
    """Run one case in a fresh writable copy of the repo: `before`, the plants, then the command.
    (text, trace log text): the log is empty unless `traced`."""
    with tempfile.TemporaryDirectory() as t:
        repo = Path(t).resolve() / "repo"
        shutil.copytree(ROOT, repo, ignore=shutil.ignore_patterns(*NOT_READ))
        frozen.thaw(repo)   # the copy only; the live tree is frozen
        log, env = Path(t).resolve() / "trace.log", None
        if traced:
            log.touch()
            env = {**os.environ, "PYTHONPATH": os.pathsep.join([str(TRACE), *filter(None, [os.environ.get("PYTHONPATH")])]),
                   "CC_TRACE_LOG": str(log), "CC_TRACE_ROOT": str(repo), "CC_TRACE_DATA": str(DATA), "CC_TRACE_TOOLSET": str(TOOLSET)}

        def cc(args):
            return subprocess.run([sys.executable, str(repo / "bin" / "cc"), *args], capture_output=True, text=True, cwd=repo, env=env)
        for b in case.get("before", []):
            cc(b)
        for src, dst in case.get("plant", {}).items():
            shutil.copyfile(ROOT / "tests" / "planted" / "golden" / src, repo / dst)
        argv = case["argv"] + (["--advanced"] if mode == "advanced" else [])
        r = cc(argv)
        return f"$ bin/cc {' '.join(argv)}\n{r.stdout}{r.stderr}exit {r.returncode}\n", (log.read_text() if traced else ""), str(repo)


def read_set(log, repo):
    """{path: kinds} from a trace log: repo-relative paths ('.' is the repo itself), '~data/<rel>' for the data root; kinds is a
    sorted string over R (read), S (stat) and D (directory listed). bin/cc is the command every transcript runs, so it is in every set."""
    out = {"bin/cc": {"R"}}
    for line in log.splitlines():
        kind, p = line.split(" ", 1)
        d, ts = str(DATA).rstrip("/"), str(TOOLSET).rstrip("/")
        rel = ((".", p[len(repo) + 1:])[p != repo] if p == repo or p.startswith(repo + "/") else "~data" + p[len(d):] if p == d or p.startswith(d + "/")
               else "~toolset" + p[len(ts):] if p == ts or p.startswith(ts + "/") else None)
        if rel is not None and not any(fnmatch.fnmatch(part, pat) for part in rel.split("/") for pat in NOT_READ):
            out.setdefault(rel, set()).add(kind)
    return {p: "".join(sorted(k)) for p, k in sorted(out.items())}


_SHA = {}   # {path: sha256}: the live tree is read, never written, while keys are computed, so each file is hashed once


def sha(path):
    if path not in _SHA:
        with open(path, "rb") as f:
            _SHA[path] = hashlib.file_digest(f, "sha256").hexdigest()
    return _SHA[path]


def live_path(rel):
    return DATA / rel[len("~data/"):] if rel.startswith("~data") else TOOLSET / rel[len("~toolset/"):] if rel.startswith("~toolset") else ROOT / rel


def listing(p):
    """The sorted entry names of a live directory ('/' marks a directory), without what the copy never holds."""
    names = sorted(n + "/" * (p / n).is_dir() for n in os.listdir(p) if not any(fnmatch.fnmatch(n, pat) for pat in NOT_READ))
    return hashlib.sha256("\0".join(names).encode()).hexdigest()


def state(rel, kinds):
    """What a recorded path is in the live tree: absent, a directory (with its listing when the transcript listed it), or a file's sha."""
    p = live_path(rel)
    if not p.exists():
        return "absent"
    if p.is_dir():
        return "dir " + (listing(p) if "D" in kinds else "")
    return "file " + sha(p)


def key_of(case, mode, paths):
    """The key of a transcript: a hash of its case, its plant sources, the harness and the live state of every path it read."""
    h = hashlib.sha256()
    plants = {src: sha(ROOT / "tests" / "planted" / "golden" / src) for src in sorted(case.get("plant", {}))}
    for fact in (json.dumps(case, sort_keys=True), mode, json.dumps(plants), sha(Path(__file__)), sha(TRACE / "sitecustomize.py"),
                 f"python {platform.python_version()} numpy {np.__version__}"):
        h.update(fact.encode() + b"\n")
    for rel, kinds in sorted(paths.items()):
        h.update(f"{kinds} {rel}\0{state(rel, kinds)}\n".encode())
    return h.hexdigest()


def reads_text(key, paths):
    body = "".join(f'  "{k} {p}",\n' for p, k in paths.items())
    return ("# tests/golden/<id>.<mode>.reads.toml - the RECORDED READ SET of one transcript (written by bin/cc test --regolden test_golden;\n"
            "# never typed). Each entry: kinds (R read, S stat, D directory listed) and a path (~data/ = the data root, ~toolset/ = the rest of the toolset root).\n"
            f'schema = 1\nkind = "golden-reads"\nkey = "{key}"\npaths = [\n{body}]\n')


def recorded(f):
    """({path: kinds}, key) of a read set, or None when the transcript has none (it is then run, never keyed)."""
    if not f.is_file():
        return None
    d = tomllib.loads(f.read_text())
    return {e.split(" ", 1)[1]: e.split(" ", 1)[0] for e in d["paths"]}, d["key"]


def timed(job):
    t0 = time.time()
    return transcript(*job), time.time() - t0


cases = tomllib.loads((GOLD / "golden.toml").read_text())["case"]
jobs = [(case, mode) for case in cases for mode in ("basic", "advanced")]
gold = lambda case, mode, ext: GOLD / f"{case['id']}.{mode}.{ext}"   # noqa: E731
keyed = set()
if not REGOLDEN and not UNKEYED:
    for i, (case, mode) in enumerate(jobs):
        rec = recorded(gold(case, mode, "reads.toml"))
        if rec and gold(case, mode, "txt").is_file() and key_of(case, mode, rec[0]) == rec[1]:
            keyed.add(i)
todo = [(i, (*job, REGOLDEN)) for i, job in enumerate(jobs) if i not in keyed]
with ThreadPoolExecutor(max(1, (os.cpu_count() or 3) - 2)) as pool:   # each transcript has its own temp copy
    done = dict(zip((i for i, _ in todo), pool.map(timed, [job for _, job in todo])))   # in order: the output below is the same as when run serially
bad, written, rekeyed = [], [], []
for i, (case, mode) in enumerate(jobs):
    f = gold(case, mode, "txt")
    if i in keyed:
        print(f"ok   {f.name} (keyed)")
        continue
    (got, log, repo), secs = done[i]
    if VERBOSE:
        print(f"seconds {secs:7.1f}  {f.name}")
    want = f.read_text() if f.is_file() else None
    if got == want:
        print(f"ok   {f.name}")
    elif REGOLDEN:
        f.write_text(got)
        written.append(f.name)
        print(f"REGOLDENED tests/golden/{f.name}")
    else:
        diff = list(difflib.unified_diff((want or "").splitlines(), got.splitlines(), f.name, "now", lineterm=""))
        bad.append(f.name)
        print(f"FAIL {f.name}" + ("" if want is not None else " (no transcript yet)"))
        print("\n".join(diff[:40]))
        print("Next: if the change is intended, bin/cc test --regolden test_golden, read the new files, and list them in your report")
    if REGOLDEN:
        paths = read_set(log, repo)
        text, r = reads_text(key_of(case, mode, paths), paths), gold(case, mode, "reads.toml")
        if not r.is_file() or r.read_text() != text:
            r.write_text(text)
            rekeyed.append(r.name)
            print(f"REKEYED tests/golden/{r.name}")
print(f"test_golden: {'FAILED ' + str(len(bad)) if bad else 'all passed'}" + (f" (regoldened {len(written)})" if written else "")
      + (f" (rekeyed {len(rekeyed)})" if rekeyed else "") + f" (ran {len(todo)}, keyed {len(keyed)})")
sys.exit(1 if bad else 0)
