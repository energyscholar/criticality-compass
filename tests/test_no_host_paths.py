"""test_no_host_paths - plan 0985 phase 1 breaker: no tracked text file names a home directory, a user's tree, or one of the author's machines (phase 2: or a private person; NOTICE keeps its copyright holder line).
Plan 1639 (declared edit): the first name pattern no longer matches when the surname follows: the credit of the kernel authors (NOTICE, README Acknowledgements, CITATION.cff) is allowed text; any other use of the first name still FAILS.
The writer emits data paths relative to the declared data root (`<data-root>/...`, cc.toml [data] name), so an absolute path cannot be stored;
this test walks every tracked file and fails on one. A planted line must be seen to fail (breaker below).
Plan 1281 B1 (ruling 2026-10-26): a results record SEALED in the toolset (its sha256 pinned by a toolset SHA256SUMS) that predates plan 0985 keeps its
old data-root keys; tests/sealed-records.toml lists each by path and sha256. A listed file is exempt ONLY while its bytes hash to its row's sha256:
a listed file that changed or is missing FAILS, and a listed path outside results/ FAILS. Content-keyed and closed: no pattern or glob is exempt.
Seen RED (plan 1281, in a scratch copy): one byte of a sealed file flipped; a new unlisted results file with a host path; a tests/ file listed."""
import hashlib
import re
import tomllib
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
# built from parts so this file does not match itself
PATTERNS = [re.compile(p) for p in (
    "/ho" + "me/", "/Us" + "ers/", "~/soft" + "ware", r"(?i)\bpen" + r"guin\b", r"(?i)\bji" + r"ll\b", r"(?i)\bporch" + r"light\b",
    "hal-" + "main", "has-anyone-" + "looked", "aura" + "sys",
    r"(?<![\w-])soft" + r"ware/(scratch|criticality)", r"structure-" + "checks",
    r"\bRo" + r"bin\b(?! Macomber)", r"\bBr" + r"uce\b(?! Stephenson)", r"\bBR" + r"UCE\b")]   # Path.home() / "<tree>/..." spells no "~"


def hits(text):
    return [(i + 1, p.pattern) for i, ln in enumerate(text.splitlines()) for p in PATTERNS if p.search(ln)]


def files(root):
    r = subprocess.run(["git", "-C", str(root), "ls-files", "-z"], capture_output=True)
    names = [n for n in r.stdout.decode().split("\0") if n] if r.returncode == 0 and r.stdout else [
        str(q.relative_to(root)) for q in Path(root).rglob("*") if q.is_file() and "__pycache__" not in q.parts]
    return [n for n in names if (Path(root) / n).is_file()]


bad = []
SEALED = {r["path"]: r["sha256"] for r in tomllib.loads((ROOT / "tests" / "sealed-records.toml").read_text())["record"]}
for p, h in SEALED.items():
    q = ROOT / p
    why = ("listed outside results/ (only a sealed results record may be listed)" if not p.startswith("results/") else
           "sealed record missing" if not q.is_file() else
           "sealed record changed (its sha256 is not its row's)" if hashlib.sha256(q.read_bytes()).hexdigest() != h else "")
    if why:
        bad.append(f"tests/sealed-records.toml: {p}: {why}")
exempt = {p for p, h in SEALED.items() if p.startswith("results/") and (ROOT / p).is_file() and hashlib.sha256((ROOT / p).read_bytes()).hexdigest() == h}
planted = hits("a = 1\npath = '" + "~/soft" + "ware/x'\n")
print(("ok   " if planted == [(2, PATTERNS[2].pattern)] else "FAIL ") + "breaker: a planted home-tree path is found")
if planted != [(2, PATTERNS[2].pattern)]:
    bad.append("breaker")
n = 0
for f in files(ROOT):
    data = (ROOT / f).read_bytes()
    if b"\0" in data:
        continue
    n += 1
    if f in exempt:
        continue
    for line, pat in hits(data.decode("utf-8", "replace")):
        bad.append(f"{f}:{line} ({pat})")
print(f"scanned {n} tracked text files ({len(exempt)} sealed records exempt by sha256, tests/sealed-records.toml); {len(bad)} finding(s)")
print("\n".join(bad[:40]) + (f"\n... {len(bad) - 40} more" if len(bad) > 40 else ""))
print("test_no_host_paths: " + ("FAILED" if bad else "ok"))
sys.exit(1 if bad else 0)
