"""schema.py - what a measurement READS: paths, parsing, the context, the content hashes and the measure key (plumbing; plan 0886).
Everything here is called by cc/detect.py, cc/door.py, cc/reverdict.py (or a helper of what they call). What `validate` CHECKS lives in
cc/declare.py, outside the measurement closure (checks.toml [closure.measure]): a validator edit moves no measure key."""
import ast
import copy
import hashlib
import os
import subprocess
import tomllib
from collections import namedtuple
from contextlib import contextmanager
from functools import lru_cache
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
F = namedtuple("F", "loc msg nxt")


def at(p, field, msg, nxt):
    """One finding located at file:field (the file alone when field is empty)."""
    return F(f"{p}:{field}" if field else p, msg, nxt)


def rel(p, root=ROOT):
    p = Path(p)
    return str(p.relative_to(root)) if p.is_absolute() and root in p.parents else str(p)


@lru_cache(maxsize=None)
def _parsed(text):
    return tomllib.loads(text)


def parse(text):
    """tomllib.loads, once per distinct text per process (a pure function of its argument; every caller gets its own copy)."""
    return copy.deepcopy(_parsed(text))


def load(p, root=ROOT):
    try:
        return parse(Path(p).read_text()), []
    except (OSError, tomllib.TOMLDecodeError) as e:
        return None, [at(rel(p, root), "", f"cannot read: {e}", "fix the TOML syntax of this file")]


def row_lines(text, key="row"):
    return [i + 1 for i, ln in enumerate(text.splitlines()) if ln.strip() == f"[[{key}]]"]


DATA_ROOT_FLAG = None   # set once by bin/cc from the global option --data-root PATH (plan 0929: the physical location of the data, never its name)


def resolve_data_root(cfg, flag=None, env=None):
    """(path, source) of the data root: WHERE the data is on this machine. cc.toml [data] name is only its NAME (the prefix of every stored path), never a location.
    Precedence flag (--data-root PATH) > env (CC_DATA_ROOT) > the clone's own data/: a table in that order, the first one given wins, and the source is recorded."""
    env = os.environ.get("CC_DATA_ROOT") if env is None else env
    given = [(src, v) for src, v in (("flag", flag), ("env", env), ("default", str(ROOT / "data"))) if v]
    src, v = given[0]
    return Path(os.path.expanduser(v)), src


class Ctx:
    """What the checks cross-reference: cc.toml, the registry, checks.toml, the data root (overridable).
    The declared name `cfg['data']['name']` is the prefix of a data file in a result's `read` map (reuse compares it);
    `data_root` is where that name is found on this machine, `data_root_source` says who chose it."""

    def __init__(self, root=ROOT, **over):
        self.root, self.over, self.shapes, self.heads = Path(root), over, {}, {}
        self.cfg = tomllib.loads((self.root / "cc.toml").read_text())
        self.reg = {f.stem: load(f)[0] or {} for f in sorted((self.root / "instruments").glob("*.toml"))}
        self.checks = tomllib.loads(Path(over.get("checks") or self.root / "checks.toml").read_text())
        self.data_root, self.data_root_source = ((Path(over["data_root"]), "override") if over.get("data_root")
                                                 else resolve_data_root(self.cfg, DATA_ROOT_FLAG))
        self.alpha = self.cfg["alphabets"]

    def file(self, path):
        """Where the data file a [[data.files]] `path` names is: under the repo's data/ when its first directory is declared in cc.toml [data] local, else under the data root."""
        return self.root / "data" / path if path.split("/")[0] in self.cfg["data"].get("local", []) else self.data_root / path

    def physical(self, key):
        """Where the file a `read` key names is on this machine: the declared data root maps to the effective one."""
        name = self.cfg["data"]["name"]
        return self.file(key[len(name) + 1:]) if key.startswith(name + "/") else self.root / key


def unit_blocks(m, inst):
    """(sizes, starts) the instrument reads at every point: the matched pair, all sizes, the start pair."""
    rels, ax = m.get("relations", {}), m["axes"]
    sizes = ([rels["matched"]["big"], rels["matched"]["small"]] if "matched" in inst["relations"]
             else list(dict.fromkeys(x for pr in rels["chain"]["pairs"] for x in pr)) if "chain" in inst["relations"] else list(ax["size"]))
    pair = rels.get("start", {}).get("pairs", [[ax["main_start"]]])[0]
    return sizes, (list(pair) if "starts" in inst["axes"] else [inst.get("start", ax["main_start"])])   # `start`: read this start, not main_start (plan 0867)


_SHA_ONCE = None   # {absolute path: sha256} while a READ-ONLY operation holds hashing_once(); None otherwise


@contextmanager
def hashing_once():
    """Within the block each file is hashed once. For an operation that writes none of the files it hashes (validate, tabulate):
    the memo lives exactly as long as the block, so it is a function of what the block read and can never outlive a write."""
    global _SHA_ONCE
    outer = _SHA_ONCE
    _SHA_ONCE = {} if outer is None else outer
    try:
        yield
    finally:
        _SHA_ONCE = outer


def _sha(path):
    with open(path, "rb") as f:
        return hashlib.file_digest(f, "sha256").hexdigest()


def sha(path):
    if _SHA_ONCE is None:
        return _sha(path)
    key = os.path.abspath(path)
    if key not in _SHA_ONCE:
        _SHA_ONCE[key] = _sha(path)
    return _SHA_ONCE[key]


MEASURE_SEEDED = "# measure-key: seeded"   # on the one line that imports an instrument module by its declared name: the key seeds every instrument module the input declares


def import_closure(root, starts):
    """{path relative to root: content sha} of the import closure, within cc/, of the module files `starts` (paths relative to root).
    Imports are READ from the syntax tree (every Import / ImportFrom node, lazy ones inside functions too), never listed by hand.
    A module that cannot be followed statically (a dynamic import, exec, eval) is refused, never widened to 'all of cc/'."""
    root, seen, todo = Path(root), {}, list(starts)
    where = lambda name: next((r for r in (f"cc/{name}.py", f"cc/instruments/{name}.py") if (root / r).is_file()), None)   # noqa: E731
    while todo:
        rel = todo.pop()
        if rel in seen:
            continue
        seen[rel] = sha(root / rel)
        text = (root / rel).read_text()
        for n in ast.walk(ast.parse(text)):
            if isinstance(n, ast.Call) and (nm := getattr(n.func, "id", getattr(n.func, "attr", None))) in ("__import__", "import_module", "exec", "eval") \
                    and MEASURE_SEEDED not in text.splitlines()[n.lineno - 1]:
                raise ValueError(f"{rel} line {n.lineno} calls {nm}: its import closure cannot be computed statically\n"
                                 "  Next: import the module with an import statement, so the measurement key can read it")
            mods = [a.name for a in n.names] if isinstance(n, ast.Import) else [n.module or ""] if isinstance(n, ast.ImportFrom) and not n.level else []
            if isinstance(n, ast.ImportFrom) and n.level:
                raise ValueError(f"{rel} line {n.lineno}: a relative import is not followed\n  Next: use an absolute import (import <module>)")
            todo += [r for m in mods if (r := where(m.split(".")[0])) is not None]
    return seen


def interval_methods(root, tset, setdir=None):
    """The [interval] methods the table set `tset` reads (plan 0937): its own tables/<set>/interval.toml `methods`, else cc.toml [interval_binding] default.
    A total table over the sets: a set without the file reads the resampling methods and cannot read a chains result, and a set that carries the file (v10-rules) reads
    only what it names, so a block result under v10-rules, or a chains result under v09 and before, is refused by the loader (detect.run_keyed, reverdict_refusal)."""
    f = Path(setdir or Path(root) / "tables" / tset) / "interval.toml"   # setdir: a set kept outside root/tables (a test's scratch dir); cc.toml is always the root's
    return list((tomllib.loads(f.read_text()) if f.is_file() else tomllib.loads((Path(root) / "cc.toml").read_text())["interval_binding"])["methods" if f.is_file() else "default"])


def measure_hash(root, instrument_modules):
    """sha256 over (path, content sha) of what MEASURES: the import closure, within cc/, of cc/detect.py (the measurement entry:
    readout, sign and what they read), cc/door.py and each module in `instrument_modules` (cc/instruments/<m>.py). A result's
    reuse key is this plus its `read`; `code_hash` stays provenance."""
    files = import_closure(root, ["cc/detect.py", "cc/door.py", *(f"cc/instruments/{m}.py" for m in sorted(set(instrument_modules)))])
    h = hashlib.sha256()
    for rel in sorted(files):
        h.update(f"{rel}\0{files[rel]}\n".encode())
    return h.hexdigest()


def code_hash(root, committed=False):
    """sha256 over (path, content sha) of every file of cc/ and bin/cc: as read from disk, or from the HEAD tree
    when `committed` and the repo has one. A result records the first; freeze demands it equals the second."""
    root, git = Path(root), ["git", "-C", str(root)]
    use_git = committed and (root / ".git").exists()
    if use_git:
        rels = subprocess.run(git + ["ls-tree", "-r", "--name-only", "HEAD", "--", "cc", "bin/cc"],
                              capture_output=True, text=True, check=True).stdout.split()
    else:
        rels = [str(q.relative_to(root)) for q in (root / "cc").rglob("*") if q.is_file() and "__pycache__" not in q.parts]
        rels.append("bin/cc")
    h = hashlib.sha256()
    for rel in sorted(rels):
        data = (subprocess.run(git + ["show", f"HEAD:{rel}"], capture_output=True, check=True).stdout
                if use_git else (root / rel).read_bytes())
        h.update(f"{rel}\0{hashlib.sha256(data).hexdigest()}\n".encode())
    return h.hexdigest()


def code_cols(d):
    return {**d["columns"].get("helper", {}), **d["columns"].get("signature", {})}


def declared_cols(d):
    """{column: 'declared.<kind>'} of the code columns a codes.toml reads from an input's declaration, not from data."""
    return {k: v["from"] for k, v in code_cols(d).items() if isinstance(v.get("from"), str) and v["from"].startswith("declared.")}
