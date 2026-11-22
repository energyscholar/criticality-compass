"""partition - plan 1639 phase 2: which stored result goes in which distribution, DERIVED, never a hand-kept list.
sealed = the records tests/sealed-records.toml lists (host paths in their read maps) and their .npz siblings: in NO distribution.
code   = the results FROZEN.json names (a rulebook run refuses without them) + every result a shipped document names (`$ compass|bin/cc <cmd> <input> [--tables T]`, or `<input>@<set>`).
data   = every other tracked result: the data wheel (criticality-compass-data, CC BY 4.0) installs it into the same workspace/results/ directory.
`keep(rel)` is the sdist filter: the sdist holds what the code wheel holds, the frozen tests and the sealed-record list."""
import functools
import json
import re
import tomllib
from pathlib import Path

DOCS = ("README.md", "HOWTO.md", "TUTORIAL.md", "KERNEL-IN-CC.md", "CLAIMS.md", "docs/FIRST-HOUR.md", "docs/READING-THE-CODE.md", "AGENTS.md", "docs/man/compass.1")


def results(root):
    return sorted(p.name for p in (Path(root) / "results").glob("*") if p.is_file())


def sealed(root):
    f = Path(root) / "tests" / "sealed-records.toml"
    stems = {Path(r["path"]).stem for r in tomllib.loads(f.read_text())["record"]} if f.is_file() else set()
    return {n for n in results(root) if Path(n).stem in stems}


def named(root):
    root, out = Path(root), set()
    inputs = {p.name for p in (root / "inputs").iterdir()} if (root / "inputs").is_dir() else set()
    default = tomllib.loads((root / "cc.toml").read_text())["defaults"]["tables"]
    for d in DOCS:
        if not (root / d).is_file():
            continue
        text = (root / d).read_text()
        out |= {f"{m[0]}@{m[1]}" for m in re.findall(r"([\w.-]+)@(v\d+[\w-]*-rules|verdict-x-rules)", text)}
        for ln in text.splitlines():
            s = ln.strip().lstrip("$ ").strip()
            if ln.strip().startswith("$ ") and re.match(r"(compass|bin/cc) ", s):
                toks = s.split()
                tset = next((toks[i + 1] for i, t in enumerate(toks[:-1]) if t == "--tables"), default)
                out |= {f"{t}@{tset}" for t in toks if t in inputs}
    return {n for n in results(root) if Path(n).stem in out}


def frozen(root):
    files = json.loads((Path(root) / "FROZEN.json").read_text())["files"]
    return {Path(k).name for k in files if k.startswith("results/")}


@functools.lru_cache(maxsize=None)
def _split(root):
    """-> (code, data, sealed): three disjoint sets of file names under results/ whose union is every result file."""
    allr, seal = set(results(root)), sealed(root)
    code = ((frozen(root) | named(root)) & allr) - seal | {n for n in allr if not n.endswith((".json", ".npz"))}   # results/README.md and any other non-result file travel with the code
    return code, allr - seal - code, seal


def split(root):
    return _split(str(Path(root).resolve()))


def keep(root, rel):
    """The sdist filter: True when `rel` (posix, relative to the root) belongs in the sdist."""
    if rel.startswith("results/"):
        return Path(rel).name in split(root)[0]
    if rel.startswith("tests/"):
        files = json.loads((Path(root) / "FROZEN.json").read_text())["files"]
        return rel in files or rel == "tests/sealed-records.toml"
    return True
