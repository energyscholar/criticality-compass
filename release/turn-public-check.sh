#!/bin/sh
# turn-public-check.sh - plan 1640 phase 6: may this branch be turned public? Reads release/public-blockers.toml, runs the check of every closed row, prints
# the table. Exit 0: no row is open, every closed row's check passed, every expected row is present, the built-in tree scan is clean (owner-gated rows are
# listed and do not fail it: they are the owner's steps; so are latent rows: findings about something outside the public tree, reported and not run). Exit 1: any other state. Exit 2: refused, CC_PRIVATE_PATTERNS (the private patterns file, never
# committed) is not set to a file. The built-in tree scan runs whatever the table says; on a directory that is not a git checkout it scans a scratch git
# copy of it (and says so), never nothing.
# usage: release/turn-public-check.sh        env: CC_PRIVATE_PATTERNS (required), PYTHON (3.11 or newer), whatever a row's check needs (its ruling names it)
set -u
ROOT=$(cd "$(dirname "$0")/.." && pwd)
PY=${PYTHON:-python3}; command -v "$PY" >/dev/null 2>&1 || PY=python
if [ -z "${CC_PRIVATE_PATTERNS:-}" ] || [ ! -f "$CC_PRIVATE_PATTERNS" ]; then
  echo "turn-public-check: REFUSED: CC_PRIVATE_PATTERNS must name the private patterns file (it is never committed); without it the scans cannot run"
  exit 2
fi
export ROOT PY CC_PRIVATE_PATTERNS
exec "$PY" - <<'PYEOF'
import os
import shutil
import subprocess
import sys
import tempfile
import tomllib
from pathlib import Path

ROOT = Path(os.environ["ROOT"])
PY = os.environ["PY"]
PAT = os.environ["CC_PRIVATE_PATTERNS"]
STATES = ("closed", "open", "owner-gated", "latent")
EXPECTED = ["1639-handoff", "idiom-followon", "tree-scan", "history-rehearsal", "gitleaks-tree", "ci-file", "ci-local-macos", "ci-local-linux", "public-face", "base", "moved-base-shas",
            "undeclared-failing-test_claims", "undeclared-failing-test_intake_example", "undeclared-failing-test_intake_reach", "undeclared-failing-test_intake_leak",
            "undeclared-failing-test_intake_terminal", "toolset-commit-missing",
            "OQ1", "OQ2", "OQ3", "OQ4", "OQ5", "gh-noreply-form", "create-repo", "flip", "project-urls-0.1.0", "readme-clone-url"]
problems = []
lines = []


def tail(text, n=4):
    return [ln for ln in text.splitlines() if ln.strip()][-n:]


try:
    rows = tomllib.loads((ROOT / "release" / "public-blockers.toml").read_text()).get("row", [])
except (OSError, tomllib.TOMLDecodeError) as e:
    print(f"turn-public-check: cannot read release/public-blockers.toml: {e}")
    sys.exit(1)

names = [r.get("name") for r in rows]
for n in EXPECTED:
    if names.count(n) == 0:
        problems.append(f"MISSING row {n}")
    elif names.count(n) > 1:
        problems.append(f"DUPLICATE row {n}")

for r in rows:
    n, st = r.get("name"), r.get("state")
    if not n or st not in STATES or not r.get("ruling"):
        problems.append(f"MALFORMED row {n!r}: needs a name, a ruling and a state in {STATES}")
        continue
    if st == "open":
        lines.append((n, "OPEN", ""))
        problems.append(f"OPEN row {n}")
    elif st == "owner-gated":
        lines.append((n, "OWNER-GATED", ""))
    elif st == "latent":
        lines.append((n, "LATENT", "a finding outside the public tree; listed, never run"))
    else:
        chk = r.get("check")
        if not chk:
            lines.append((n, "CLOSED", "no check"))
            problems.append(f"CLOSED row {n} names no check")
            continue
        p = subprocess.run(["sh", "-c", chk], cwd=ROOT, capture_output=True, text=True)
        if p.returncode == 0:
            lines.append((n, "CLOSED", "check passed"))
        else:
            lines.append((n, "CLOSED", f"CHECK FAILED (exit {p.returncode}): " + " | ".join(tail(p.stdout + p.stderr))))
            problems.append(f"CLOSED row {n}: its check failed")

# the floor: the tree scan, whatever the table says
scratch = None
root = ROOT
if not (ROOT / ".git").exists():
    scratch = tempfile.mkdtemp(prefix="turn-public.")
    root = Path(scratch) / "tree"
    shutil.copytree(ROOT, root, ignore=shutil.ignore_patterns("results", "__pycache__"))
    for cmd in (["git", "init", "-q"], ["git", "add", "-A"]):
        subprocess.run(cmd, cwd=root, capture_output=True)
    print("turn-public-check: not a git checkout: the built-in tree scan runs on a scratch git copy of the directory")
p = subprocess.run([PY, str(ROOT / "release" / "public_scan.py"), "--private-patterns", PAT, "--tree", str(root)], capture_output=True, text=True)
if scratch:
    shutil.rmtree(scratch, ignore_errors=True)
if p.returncode == 0:
    lines.append(("(built-in tree scan)", "CLEAN", tail(p.stdout, 1)[0] if p.stdout.strip() else ""))
else:
    lines.append(("(built-in tree scan)", "HITS", f"exit {p.returncode}: " + " | ".join(tail(p.stdout + p.stderr))))
    problems.append("the built-in tree scan found hits or could not run")

w = max(len(n) for n, _, _ in lines)
for n, st, why in lines:
    print(f"{n:<{w}}  {st:<12} {why}".rstrip())
counts = {s: sum(1 for r in rows if r.get("state") == s) for s in STATES}
print(f"turn-public-check: {len(rows)} rows: {counts['closed']} closed, {counts['open']} open, {counts['owner-gated']} owner-gated; {len(problems)} problem(s)")
for q in problems:
    print("  " + q)
sys.exit(1 if problems else 0)
PYEOF
