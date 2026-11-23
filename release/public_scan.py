"""public_scan - plan 1640: the tree and history scans for a public release. A closed table of pattern classes, HARD or SOFT, plus the private name list
the caller supplies (`--private-patterns FILE`, sections [hard] and [soft], one regex per line; never committed: it would publish the names it hides).
  --tree DIR                         every tracked text file: HARD and SOFT hits all fail, except a file listed by sha256 in DIR/release/public-tree-exempt.toml
                                     (a row whose file changed or is missing is itself a hit) and the project email and the declared public identity (release/public-identity.toml), matched exactly.
  --history BARE --private-era REV   every blob, message and identity of every ref: a HARD hit fails; a SOFT hit (kept in history by ruling) is counted, and fails
                                     only in a blob that REV (or several, comma-joined) does not reach (a SOFT class that entered after the private era).
Lines: SEV<TAB>class<TAB>where<TAB>detail, untruncated; exit 0 clean, 1 hits, 2 refused. Patterns that would match this file are spelt from parts."""
import hashlib
import re
import subprocess
import sys
import tomllib
from collections import Counter
from pathlib import Path

EMAIL = "energyscholar+criticality-compass@gmail.com"   # the one email any tracked file may carry
PUBLIC_ID = tomllib.loads((Path(__file__).resolve().parent / "public-identity.toml").read_text())["email"]   # plan 1640 amendment E: the declared public identity is public by ruling; read, never spelt here
TABLE = [   # (class, severity, regex): the closed table of what a public release must not carry
    ("secret", "HARD", re.compile(r"pypi-[A-Za-z0-9_-]{20,}|gh[pousr]_[A-Za-z0-9]{30,}|AKIA[0-9A-Z]{16}|-----BEGIN [A-Z ]*PRIVATE KEY|xox[abp]-[A-Za-z0-9-]{10,}")),
    ("ruo-content", "HARD", re.compile(r"(?i)thermo" + r"[-_ ]?acoustic|rij" + r"ke tube|western " + r"systems coordinating|\bws" + r"cc\b|IEEE.9" + r".bus")),
    ("home-path", "SOFT", re.compile("/ho" + r"me/\w|/Us" + r"ers/\w")),   # a path in an old blob is kept by ruling OQ2; in the tree it fails like every SOFT hit
    ("email", "SOFT", re.compile(r"(?<![^\s<(\"'`,;=\[])[\w.+-]+@(?![\w-]+(?:\.[\w-]+)*\.(?:json|npz|toml|txt|md|py|csv|sha256)\b)[\w-]+(?:\.[\w-]+)+")),   # an address starts a word; `results/x@v03-rules.json` and `*-ch@v10-rules.json` (result stems) do not, and neither does a domain ending in a file extension
]
RUO_PATH = re.compile(r"(?i)thermo" + r"[-_ ]?acoustic|rij" + r"ke|(^|[/_.-])(ws" + r"cc|we" + r"cc)([/_.-]|$)")   # research-use-only data, by path
LOCAL = re.compile(r"<[^>]*@[^>]*\.local>")   # an author or committer identity on a machine's .local domain


def refuse(why):
    print(f"public_scan: REFUSED: {why}")
    sys.exit(2)


def load_patterns(path):
    if not path or not Path(path).is_file():
        refuse("--private-patterns FILE is required (the private name list is never in the tree)")
    got, sec = {"hard": [], "soft": []}, None
    for ln in Path(path).read_text().splitlines():
        ln = ln.rstrip("\n")
        if not ln.strip() or ln.startswith("#"):
            continue
        if re.fullmatch(r"\[(hard|soft)\]", ln.strip()):
            sec = ln.strip()[1:-1]
        elif sec is None:
            refuse("a pattern outside a [hard] or [soft] section")
        else:
            got[sec].append(re.compile(ln))
    if not got["hard"] or not got["soft"]:
        refuse("the patterns file needs both a [hard] and a [soft] section with patterns")
    return TABLE + [("private-hard", "HARD", r) for r in got["hard"]] + [("private-soft", "SOFT", r) for r in got["soft"]]


def line_hits(text, table):
    """(class, severity, line number, line) for every line of `text` a class matches; the project email is removed first, matched exactly."""
    text = text.replace(EMAIL, "").replace(PUBLIC_ID, "")
    out = []
    for cls, sev, rx in table:
        if rx.search(text):   # one pass over the whole text first: only a matching text is walked line by line
            out += [(cls, sev, i, ln.strip()) for i, ln in enumerate(text.splitlines(), 1) if rx.search(ln)]
    return out


def git(repo, *a, check=True):
    r = subprocess.run(["git", "-C", str(repo), *a], capture_output=True)
    if check and r.returncode:
        refuse(f"git {' '.join(a[:3])} failed in {repo}: {r.stderr.decode()[:120]}")
    return r.stdout


def tree(root, table):
    root = Path(root)
    names = [n for n in git(root, "ls-files", "-z").decode().split("\0") if n]
    ex = root / "release" / "public-tree-exempt.toml"
    rows = tomllib.loads(ex.read_text()).get("exempt", []) if ex.is_file() else []
    out, listed = [], {}
    for r in rows:
        q = root / r["path"]
        if not q.is_file() or hashlib.sha256(q.read_bytes()).hexdigest() != r["sha256"]:
            out.append(("HIT", "exempt-stale", r["path"], "the exempt file changed or is missing"))
        else:
            listed[r["path"]] = r["reason"]
    for n in names:
        if n in listed or not (root / n).is_file():
            continue
        if RUO_PATH.search(n):
            out.append(("HIT", "ruo-path", n, "research-use-only data by path"))
        data = (root / n).read_bytes()
        if b"\0" not in data[:8192]:
            out += [("HIT", c, f"{n}:{i}", ln) for c, _, i, ln in line_hits(data.decode("utf-8", "replace"), table)]
    return out, len(names), len(listed)


def history(repo, era, table):
    out = []
    for rec in git(repo, "log", "--all", "--format=%H%x1f%an <%ae>%x1f%cn <%ce>%x1f%B%x1e").decode("utf-8", "replace").split("\x1e"):
        if not rec.strip():
            continue
        h, a, c, msg = rec.strip("\n").split("\x1f", 3)
        out += [("HARD", "identity", f"commit:{h}", who) for who in sorted({a, c}) if LOCAL.search(who)]
        out += [("SOFT" if s == "SOFT" else s, k, f"commit:{h}:msg:{i}", ln) for k, s, i, ln in line_hits(msg, table)]
    kept = {ln.split()[0] for ln in git(repo, "rev-list", "--objects", *era.split(",")).decode().splitlines()}   # the private era: one rev, or several joined by commas
    paths = {}
    for ln in git(repo, "rev-list", "--objects", "--all").decode("utf-8", "replace").splitlines():
        o, _, p = ln.partition(" ")
        paths.setdefault(o, p)
    oids = "\n".join(paths) + "\n"
    cat = subprocess.run(["git", "-C", str(repo), "cat-file", "--batch"], input=oids.encode(), capture_output=True).stdout
    pos = 0
    while pos < len(cat):
        end = cat.index(b"\n", pos)
        o, typ, size = cat[pos:end].decode().split()
        body, pos = cat[end + 1:end + 1 + int(size)], end + 2 + int(size)
        if typ != "blob":
            continue
        where = f"blob:{o[:12]}:{paths[o]}"
        if paths[o] and RUO_PATH.search(paths[o]):
            out.append(("HARD", "ruo-path", where, "research-use-only data by path"))
        if b"\0" in body[:8192]:
            continue
        for k, s, i, ln in line_hits(body.decode("utf-8", "replace"), table):
            out.append((s if s == "HARD" or o in kept else "LATE", k, f"{where}:{i}", ln))
    return out


def main(argv):
    arg = {a: argv[i + 1] for i, a in enumerate(argv[:-1]) if a.startswith("--")}
    table = load_patterns(arg.get("--private-patterns"))
    if "--tree" in arg:
        out, n, ne = tree(arg["--tree"], table)
        for row in out:
            print("\t".join(row))
        print(f"public_scan: tree: {n} tracked files, {ne} exempt by sha256, {len(out)} hit(s)")
        return 1 if out else 0
    if "--history" in arg and "--private-era" in arg:
        out = history(arg["--history"], arg["--private-era"], table)
        for row in out:
            print("\t".join(row))
        n = Counter(r[0] for r in out)
        soft = Counter(r[1] for r in out if r[0] == "SOFT")
        print(f"public_scan: history: HARD {n['HARD']}, LATE {n['LATE']}, SOFT {n['SOFT']} kept by ruling " + str(dict(sorted(soft.items()))))
        return 1 if n["HARD"] or n["LATE"] else 0
    refuse("give --tree DIR, or --history BARE --private-era SHA")


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
