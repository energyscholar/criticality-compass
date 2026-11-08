"""host.py - what THIS host holds of the resources validate reads beyond the repository's files (plan 1273): the data root, and the toolset's
git history (found as the data root's parent). Each is probed ONCE per Ctx, and the probe's result is a VALUE whose type selects the check:
a Held resource runs it, an Absent one yields NotEvaluableHere at that check. A check of an absent resource is never run-and-failed, and no
finding is ever classified afterwards by its text."""
import os
import subprocess
from collections import namedtuple
from functools import lru_cache, singledispatch
from pathlib import Path
from schema import load

NEXT = "commit from a host with {0} (the data root: --data-root PATH or CC_DATA_ROOT; the toolset: a clone holding registry.toml's source_commit, at the data root's parent)"


class NotEvaluableHere(namedtuple("NotEvaluableHere", "resource loc reason nxt")):
    """A finding about the HOST, never about the files: `resource` is absent here, so the check at `loc` was not evaluated. Not a pass and not a
    content failure (a content finding is schema.F). It reads like one (loc, msg, nxt), so a type-blind reader (run, intake S0) still refuses on it."""
    __slots__ = ()
    msg = property(lambda f: f"not evaluable here: {f.reason}")


class Held(namedtuple("Held", "name where")):
    """A resource this host holds at `where`: the check runs on it."""
    def each(self, check, p, field):
        return check(self.where)


class Absent(namedtuple("Absent", "name reason")):
    """A resource this host does not hold: the check at p:field is NotEvaluableHere."""
    def each(self, check, p, field):
        return [NotEvaluableHere(self.name, f"{p}:{field}", self.reason, NEXT.format(self.name))]


@singledispatch
def resource(x):
    return x   # already a Held or an Absent


@resource.register(Path)
def _(x):
    return Held("toolset", x)   # a caller that names the toolset by its path located it: held


def git_bytes(where, *args):
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}   # a hook's GIT_DIR / GIT_INDEX_FILE would point -C at the hook's repo
    r = subprocess.run(["git", "-C", str(where), *args], capture_output=True, env=env)
    return r.stdout if r.returncode == 0 else None


def _git(where, *a):
    return (lambda b: None if b is None else b.decode().strip())(git_bytes(where, *a))   # git_bytes decoded: the text and stripped


@lru_cache(maxsize=None)
def probe(c):
    """(data root, toolset) of this host for the Ctx `c`. The data root is held when it holds an entry besides the in-repo `local` data; the toolset when
    the data root is held and its parent holds registry.toml's source (the commit in its git history, or a REGISTRY.toml with the blob's content)."""
    root, local = Path(c.data_root), set(c.cfg["data"].get("local", []))
    data = root.is_dir() and any(e.name not in local for e in root.iterdir())
    reg, ts = load(Path(c.root) / "registry.toml", c.root)[0] or {}, root.parent
    hist = data and (_git(ts, "cat-file", "-e", f"{reg.get('source_commit')}^{{commit}}") is not None
                     or _git(ts, "hash-object", "taxonomy/REGISTRY.toml") == reg.get("source_blob", ""))
    why = {True: f"the toolset at {ts} holds neither registry.toml's source_commit {str(reg.get('source_commit'))[:12]} nor its REGISTRY.toml blob",
           False: f"the toolset is found as the parent of the data root, which holds no data on this host ({root}, {c.data_root_source})"}[data]
    return ({True: Held("data_root", root), False: Absent("data_root", f"the data root {root} ({c.data_root_source}) holds no data on this host")}[data],
            {True: Held("toolset", ts), False: Absent("toolset", why)}[hist])


def holder(c, path):
    """The resource a [[data.files]] path lives in: the repository for a `local` first directory (always held), else the data root."""
    return {True: Held("repo", Path(c.root) / "data"), False: probe(c)[0]}[c.is_local(path)]
