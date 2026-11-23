#!/bin/sh
# public-verify.sh - plan 1640: V1-V8 on a rewritten copy against its origin.
# usage: release/public-verify.sh [--only V<n>] <rewritten bare repo> <origin bare repo>
# env:   CC_PRIVATE_PATTERNS  the private patterns file (V1 needs it present, V2 reads it)
#        CC_CI_BASELINE       a file of failure names, one per line (V7): the worktree's own `bin/cc check --fast` failures
# V1 gitleaks over every ref (.gitleaks.toml) | V2 our history scan, 0 HARD and 0 late SOFT | V3 identities are the allowed set | V4 nothing but the
# identity moved: trees, dates, parents, messages, count | V5 the origin's refs and files are what they were before the rewrite | V6 self-shas: a sha
# in the tree that moved is in the commit map, and no test passes a moved sha to git | V7 release/ci-local.sh on a clone of the rewritten main:
# its failure names equal CC_CI_BASELINE | V8 git fsck --full. Exit 0 = every selected check passed; 1 = a FAIL; 3 = a check could not run (printed, never silent).
set -u
ROOT=$(cd "$(dirname "$0")/.." && pwd)
PY=${PYTHON:-python3}; command -v "$PY" >/dev/null 2>&1 || PY=python
ONLY=""
if [ "${1:-}" = "--only" ]; then ONLY="${2:-}"; shift 2; fi
[ $# -eq 2 ] || { echo "usage: public-verify.sh [--only V<n>] <rewritten bare repo> <origin bare repo>"; exit 2; }
OUT=$(cd "$1" && pwd -P) || exit 2
ORIGIN=$(cd "$2" && pwd -P) || exit 2
IDENT="$ROOT/release/public-identity.toml"
idval() { "$PY" -c 'import sys, tomllib; print(tomllib.load(open(sys.argv[1], "rb"))[sys.argv[2]])' "$IDENT" "$1"; }
ALLOWED_OWNER=$(idval name) || { echo "public-verify: cannot read name from $IDENT (needs Python 3.11+ with tomllib)"; exit 2; }
ID_MAIL=$(idval email) || { echo "public-verify: cannot read email from $IDENT (needs Python 3.11+ with tomllib)"; exit 2; }
[ -n "$ALLOWED_OWNER" ] && [ -n "$ID_MAIL" ] || { echo "public-verify: $IDENT declares no name or email"; exit 2; }
BAD=0; NOTRUN=0
want() { [ -z "$ONLY" ] || [ "$ONLY" = "$1" ]; }
fail() { echo "$1 FAIL $2"; BAD=1; }
notrun() { echo "$1 NOT RUN: $2"; NOTRUN=1; }
hash256() { if command -v sha256sum >/dev/null 2>&1; then sha256sum "$@"; else shasum -a 256 "$@"; fi; }
snapshot() {
  git -C "$1" for-each-ref
  (cd "$1" && find HEAD packed-refs objects refs -type f ! -name '*.lock' 2>/dev/null | LC_ALL=C sort | while read -r f; do hash256 "$f"; done)
}
MAIN=$(git -C "$OUT" rev-parse --verify -q refs/heads/main || true)

if want V1; then
  if command -v gitleaks >/dev/null 2>&1; then
    if [ -z "${CC_PRIVATE_PATTERNS:-}" ]; then notrun V1 "CC_PRIVATE_PATTERNS is not set (gitleaks alone is half of V1+V2)"
    else
      o=$(gitleaks git --no-banner --exit-code 7 --config "$ROOT/.gitleaks.toml" --log-opts=--all "$OUT" 2>&1); rc=$?
      if [ $rc -eq 0 ]; then echo "V1 ok gitleaks: no leaks in any ref"; else fail V1 "gitleaks exit $rc: $(echo "$o" | tail -3 | tr '\n' ' ')"; fi
    fi
  else notrun V1 "no gitleaks on PATH"; fi
fi

if want V2; then
  if [ -z "${CC_PRIVATE_PATTERNS:-}" ]; then notrun V2 "CC_PRIVATE_PATTERNS is not set"
  elif [ -z "$MAIN" ]; then fail V2 "the copy has no refs/heads/main"
  else
    o=$("$PY" "$ROOT/release/public_scan.py" --private-patterns "$CC_PRIVATE_PATTERNS" --history "$OUT" --private-era "$MAIN" 2>&1); rc=$?
    if [ $rc -eq 0 ]; then echo "V2 ok $(echo "$o" | tail -1)"; else fail V2 "scan exit $rc: $(echo "$o" | grep -v '^SOFT' | head -3 | tr '\n' ' ')"; fi
  fi
fi

if want V3; then
  bad=$(git -C "$OUT" log --all --format='%an <%ae>%n%cn <%ce>' | sort -u | grep -v -x -e "$ALLOWED_OWNER <$ALLOWED_OWNER@gmail.com>" -e "$ALLOWED_OWNER <$ID_MAIL>" -e "Gene""rator <$ALLOWED_OWNER@gmail.com>")
  if [ -z "$bad" ]; then echo "V3 ok every author and committer is an allowed identity"; else fail V3 "identity outside the allowed set: $(echo "$bad" | head -3 | tr '\n' ';')"; fi
fi

if want V4; then
  if [ ! -f "$OUT/filter-repo/commit-map" ]; then fail V4 "no filter-repo/commit-map in the copy"
  else
    "$PY" - "$OUT" "$ORIGIN" "$ALLOWED_OWNER" "$ID_MAIL" <<'PYEOF'
import re, subprocess, sys
out, origin, PUBNAME, NOREPLY = sys.argv[1:5]
F = "%H%x00%T%x00%P%x00%ad%x00%cd%x00%an%x00%ae%x00%cn%x00%ce%x00%B%x01"
def load(repo, *revs):
    raw = subprocess.run(["git", "-C", repo, "log", "--date=raw", "--format=" + F, *revs], capture_output=True, text=True, check=True).stdout
    d = {}
    for rec in raw.split("\x01"):
        rec = rec.lstrip("\n")
        if rec:
            f = rec.split("\x00")
            d[f[0]] = dict(tree=f[1], par=f[2].split(), ad=f[3], cd=f[4], id=tuple(f[5:9]), msg=f[9])
    return d
A = load(origin, "refs/heads/compass-main")
B = load(out, "--all")
mp = dict(ln.split() for ln in open(out + "/filter-repo/commit-map").read().splitlines()[1:])
HEX = re.compile(r"\b[0-9a-f]{7,40}\b")
norm = lambda s: HEX.sub("H", s.rstrip())
errs = []
if len(A) != len(B): errs.append(("-", f"commit count {len(A)} in the origin, {len(B)} in the copy"))
for o, a in A.items():
    n = mp.get(o)
    if n is None or n not in B: errs.append((o, "not in the commit map / copy")); continue
    b = B[n]
    if a["tree"] != b["tree"]: errs.append((o, f"tree differs {a['tree'][:10]} -> {b['tree'][:10]}")); continue
    if (a["ad"], a["cd"]) != (b["ad"], b["cd"]): errs.append((o, "a date differs")); continue
    if [mp.get(p, p) for p in a["par"]] != b["par"]: errs.append((o, "topology differs")); continue
    if norm(a["msg"]) != norm(b["msg"]): errs.append((o, "message differs")); continue
    for who in (0, 2):
        an, ae = a["id"][who], a["id"][who + 1]; bn, be = b["id"][who], b["id"][who + 1]
        if ae.endswith(".local"):
            if (bn, be) != (PUBNAME, NOREPLY): errs.append((o, f"identity not mapped to the public one: {bn} <{be}>"))
        elif (an, ae) != (bn, be): errs.append((o, f"identity changed though it was not .local: {an} <{ae}> -> {bn} <{be}>"))
if errs:
    for o, why in errs[:5]: print("V4 FAIL", o, why)
    print(f"V4 FAIL {len(errs)} difference(s) in all")
    sys.exit(1)
moved = sum(1 for o in A if mp[o] != o)
print(f"V4 ok {len(A)} commits; trees, dates, parents, messages equal; {moved} moved (identity only)")
PYEOF
    [ $? -eq 0 ] || BAD=1
  fi
fi

if want V5; then
  b="$OUT/public-rewrite-meta/origin-before.txt"
  if [ ! -f "$b" ]; then fail V5 "no public-rewrite-meta/origin-before.txt in the copy"
  else
    snapshot "$ORIGIN" > "${TMPDIR:-/tmp}/v5.$$" 2>/dev/null
    if cmp -s "$b" "${TMPDIR:-/tmp}/v5.$$"; then echo "V5 ok the origin's refs and files are what they were before the rewrite"
    else fail V5 "the origin changed: $(diff "$b" "${TMPDIR:-/tmp}/v5.$$" | grep '^[<>]' | head -2 | cut -c1-120 | tr '\n' ' ')"; fi
    rm -f "${TMPDIR:-/tmp}/v5.$$"
  fi
fi

if want V6; then
  if [ -z "$MAIN" ] || [ ! -f "$OUT/filter-repo/commit-map" ]; then fail V6 "the copy has no main or no commit map"
  else
    "$PY" - "$OUT" "$ORIGIN" <<'PYEOF'
import ast, bisect, re, subprocess, sys
out, origin = sys.argv[1:3]
def g(repo, *a, inp=None): return subprocess.run(["git", "-C", repo, *a], input=inp, capture_output=True, check=True).stdout
mp = dict(ln.split() for ln in open(out + "/filter-repo/commit-map").read().splitlines()[1:])
olds = sorted(g(origin, "rev-list", "--all").decode().split())
rx = re.compile(r"(?<![0-9A-Za-z_])[0-9a-f]{7,40}(?![0-9A-Za-z_])")
callx = re.compile(r"[\"']git[\"']|\bgit\s+(?:diff|show|log|checkout|rev-parse|cat-file|merge-base|worktree|archive|reset|switch)\b|subprocess")
isTest = re.compile(r"^(tests|contract)/.*\.py$|(^|/)test_[^/]*\.py$")   # any python file of a test directory, or named test_*
names = [ln.split("\t", 1)[1] for ln in g(out, "ls-tree", "-r", "--full-name", "main").decode().splitlines()]
blobs = g(out, "cat-file", "--batch", inp=("\n".join("main:" + n for n in names) + "\n").encode())
pos = 0; moved_hits = []; kept = 0; test_bad = []
for n in names:
    hdr_end = blobs.index(b"\n", pos); hdr = blobs[pos:hdr_end].split(); size = int(hdr[2]); body = blobs[hdr_end + 1:hdr_end + 1 + size]; pos = hdr_end + 1 + size + 1
    try: t = body.decode()
    except UnicodeDecodeError: continue
    for i, ln in enumerate(t.splitlines(), 1):
        for m in rx.findall(ln):
            if not re.search(r"[a-f]", m) or not re.search(r"\d", m): continue
            k = bisect.bisect_left(olds, m); hit = [c for c in olds[k:k + 2] if c.startswith(m)]
            if len(hit) != 1: continue
            if mp.get(hit[0], hit[0]) == hit[0]: kept += 1; continue
            moved_hits.append((n, i, m))
            if isTest.search(n) and callx.search(ln): test_bad.append((n, i, m))
    # the M3 scan, at rehearsal time: a moved sha held as DATA (a string constant that is not a docstring and IS a revision: BASE = "55eba02") of a python test is a base the test
    # can hand to git whatever line it sits on (BASE = "55eba02"); prose (comments, docstrings, docs) naming a moved sha is only counted
    if isTest.search(n) and n.endswith(".py"):
        try: tree = ast.parse(t)
        except SyntaxError: continue
        doc = {id(b[0].value) for b in (x.body for x in ast.walk(tree) if isinstance(x, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)))
               if b and isinstance(b[0], ast.Expr) and isinstance(b[0].value, ast.Constant) and isinstance(b[0].value.value, str)}
        for node in ast.walk(tree):
            if isinstance(node, ast.Constant) and isinstance(node.value, str) and id(node) not in doc:
                head = re.match(r"\s*([0-9a-f]{7,40})(?:[~^:.@]\S*)?\s*$", node.value)   # the constant IS a revision (a sha, or a sha with a suffix); a sentence that names one is prose
                for m in ([head.group(1)] if head else []):
                    if not re.search(r"[a-f]", m) or not re.search(r"\d", m): continue
                    k = bisect.bisect_left(olds, m); hit = [c for c in olds[k:k + 2] if c.startswith(m)]
                    if len(hit) == 1 and mp.get(hit[0], hit[0]) != hit[0] and (n, node.lineno, m) not in test_bad: test_bad.append((n, node.lineno, m))
for n, i, m in test_bad: print(f"V6 FAIL {n}:{i} holds the moved sha {m} where a test can pass it to git")
if test_bad: sys.exit(1)
print(f"V6 ok {kept} self-shas preserved; {len(moved_hits)} moved (all in the commit map, none held by a test as data)")
PYEOF
    [ $? -eq 0 ] || BAD=1
  fi
fi

if want V7; then
  if [ ! -x "$ROOT/release/ci-local.sh" ] && [ ! -f "$ROOT/release/ci-local.sh" ]; then notrun V7 "release/ci-local.sh is absent"
  elif [ -z "${CC_CI_BASELINE:-}" ] || [ ! -f "${CC_CI_BASELINE:-}" ]; then notrun V7 "CC_CI_BASELINE (the worktree's own failure names) is not set"
  elif [ -z "$MAIN" ]; then fail V7 "the copy has no main"
  else
    d=$(mktemp -d "${TMPDIR:-/tmp}/v7.XXXXXX"); git clone -q -b main "$OUT" "$d/c" || { fail V7 "clone failed"; d=""; }
    if [ -n "$d" ]; then
      sh "$ROOT/release/ci-local.sh" --repo "$d/c" --result "$d/result.txt" --python "${PYTHON:-python3}" >"$d/log.txt" 2>&1
      sed -n 's/^FAILED //p' "$d/result.txt" | LC_ALL=C sort -u > "$d/names.txt"
      LC_ALL=C sort -u "$CC_CI_BASELINE" > "$d/base.txt"
      if cmp -s "$d/names.txt" "$d/base.txt"; then echo "V7 ok ci-local on a clone of the copy: failure names equal the worktree's own ($(wc -l < "$d/names.txt" | tr -d ' '))"
      else fail V7 "failure names differ from the baseline: $(diff "$d/base.txt" "$d/names.txt" | grep '^[<>]' | head -4 | tr '\n' ' ')"; fi
      rm -rf "$d"
    fi
  fi
fi

if want V8; then
  o=$(git -C "$OUT" fsck --full 2>&1); rc=$?
  if [ $rc -eq 0 ]; then echo "V8 ok git fsck --full is clean"; else fail V8 "git fsck exit $rc: $(echo "$o" | head -2 | tr '\n' ' ')"; fi
fi

[ $BAD -eq 0 ] || exit 1
[ $NOTRUN -eq 0 ] || exit 3
exit 0
