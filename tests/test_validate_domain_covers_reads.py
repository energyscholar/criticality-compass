"""test_validate_domain_covers_reads - cc.toml [check] validate_domain is PROVEN to cover what validate reads (plan 1273, T3). A fixture copy of the
repository runs validate_scored (what `bin/cc check` runs) in a child under an audit hook (sys.addaudithook: open, os.listdir, os.scandir), from
the import of declare onward, so the validator's own code is traced too. Every path the child opened inside the fixture must match a declared
glob, and every directory it listed must be one a declared glob reaches into. A miss is fixed by widening the DECLARATION, never by narrowing the
trace. The test can fail: the same trace against the domain minus one glob reports misses. Seen RED on 272c843 (no validate_domain)."""
import fnmatch
import json
import os
import shutil
import subprocess
import sys
import tempfile
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
bad = []


def check(name, ok, why=""):
    print(("ok   " if ok else "FAIL ") + name + ("" if ok else f": {why}"))
    if not ok:
        bad.append(name)


CHILD = r"""
import json, os, sys
root, seen = os.path.realpath(sys.argv[1]), set()
def hook(event, args):
    kind = {"open": "R", "os.listdir": "D", "os.scandir": "D"}.get(event)
    if kind and args and isinstance(args[0], (str, bytes, os.PathLike)):
        p = os.path.realpath(os.fsdecode(args[0]) or ".")
        if p == root or p.startswith(root + os.sep):
            seen.add((kind, os.path.relpath(p, root)))
sys.addaudithook(hook)
sys.path[:0] = [root + "/cc", root + "/cc/instruments"]
import declare
found, n, lines = declare.validate_scored(root)
print(json.dumps(sorted(seen)))
"""


def misses(seen, globs):
    """The traced paths no declared glob covers: a file read must match one; a directory listed must be reached into by one."""
    return sorted(p for kind, p in seen if not any(fnmatch.fnmatch(p if kind == "R" else p + "/x", g) for g in globs))


domain = tomllib.loads((ROOT / "cc.toml").read_text())["check"].get("validate_domain")
check("cc.toml [check] declares validate_domain as a list of globs", isinstance(domain, list) and domain and all(isinstance(g, str) for g in domain), str(domain))
tmp = Path(tempfile.mkdtemp(prefix="cc-domain-"))
try:
    fx = tmp / "cc"
    shutil.copytree(ROOT, fx, ignore=shutil.ignore_patterns(".git", "__pycache__", "*.pyc"))
    env = {k: v for k, v in os.environ.items() if k != "CC_DATA_ROOT" and not k.startswith("GIT_")}
    r = subprocess.run([sys.executable, "-c", CHILD, str(fx)], capture_output=True, text=True, cwd=fx, env=env)
    seen = [tuple(x) for x in json.loads(r.stdout.strip().splitlines()[-1])] if r.returncode == 0 else []
    check("the traced child ran validate", r.returncode == 0 and seen, r.stderr[-600:])
    reads = sorted({p for k, p in seen if k == "R"})
    print(f"observed: {len(reads)} files read, {len({p for k, p in seen if k == 'D'})} directories listed under the fixture; top level: "
          + " ".join(sorted({p.split('/')[0] + ('/' if '/' in p else '') for k, p in seen})))
    print("observed directories listed: " + " ".join(sorted(p for k, p in seen if k == "D")))
    miss = misses(seen, domain or [])
    check("every path validate read lies in the declared validate_domain", seen and not miss, " ".join(miss[:20]))
    check("the trace saw the validator's own code (cc/declare.py) and its config (cc.toml)", ("R", "cc/declare.py") in seen and ("R", "cc.toml") in seen, str(reads[:10]))
    for g in ("tables/*", "cc/*"):
        check(f"can fail: the domain minus {g} misses a traced path", misses(seen, [x for x in (domain or []) if x != g]) != [], g)
finally:
    shutil.rmtree(tmp, ignore_errors=True)
print("test_validate_domain_covers_reads: " + ("FAILED" if bad else "all passed"))
sys.exit(1 if bad else 0)
