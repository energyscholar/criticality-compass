#!/bin/sh
# public-rewrite.sh - plan 1640: the one history rewrite for the public repository, on a COPY.
# usage: release/public-rewrite.sh --origin <bare repo> --out <new dir>
# Clones the origin's compass-main (only that branch) into a NEW bare repository <out>, rewrites every author and committer identity whose email
# domain ends in .local to the one public identity below, renames the branch to main, and records the commit map. Nothing else changes: no tree,
# no date, no message text but the abbreviated shas filter-repo itself maps. The origin is only ever read; its refs and files are recorded
# before and after into <out>/public-rewrite-meta/. Refuses (exit 2) an out dir that exists, lies inside the origin, or contains it.
# Needs git-filter-repo on PATH. Never run with --force; never run on the origin.
set -eu
die() { echo "public-rewrite: REFUSED: $*"; exit 2; }
ORIGIN=""; OUT=""
while [ $# -gt 0 ]; do
  case "$1" in
    --origin) ORIGIN="${2:-}"; shift 2 ;;
    --out) OUT="${2:-}"; shift 2 ;;
    *) die "unknown argument $1 (use --origin <bare repo> --out <new dir>)" ;;
  esac
done
[ -n "$ORIGIN" ] && [ -n "$OUT" ] || die "give --origin <bare repo> and --out <new dir>"
[ -d "$ORIGIN" ] || die "origin is not a directory: $ORIGIN"
ORIGIN=$(cd "$ORIGIN" && pwd -P)
[ "$(git -C "$ORIGIN" rev-parse --is-bare-repository)" = true ] || die "origin is not a bare repository (point at a bare copy, never at a working tree)"
[ ! -e "$OUT" ] || die "out dir already exists: $OUT"
PARENT=$(cd "$(dirname "$OUT")" 2>/dev/null && pwd -P) || die "the parent of the out dir does not exist"
OUT="$PARENT/$(basename "$OUT")"
[ "$OUT" != "$ORIGIN" ] || die "out dir is the origin"
case "$OUT/" in "$ORIGIN"/*) die "out dir is inside the origin" ;; esac
case "$ORIGIN/" in "$OUT"/*) die "the origin is inside the out dir" ;; esac
command -v git-filter-repo >/dev/null 2>&1 || die "git-filter-repo is not on PATH"

hash256() { if command -v sha256sum >/dev/null 2>&1; then sha256sum "$@"; else shasum -a 256 "$@"; fi; }
snapshot() {   # refs and the hash of every file git keeps its history in, relative to the repo
  git -C "$1" for-each-ref
  (cd "$1" && find HEAD packed-refs objects refs -type f ! -name '*.lock' 2>/dev/null | LC_ALL=C sort | while read -r f; do hash256 "$f"; done)
}

U=energyscholar
NEW_NAME="$U"
NEW_MAIL="${U}@users.noreply.github.com"   # the one public identity (the owner confirms it at the flip: runbook step 1)
git clone -q --bare --no-local --single-branch -b compass-main "$ORIGIN" "$OUT"
mkdir "$OUT/public-rewrite-meta"
snapshot "$ORIGIN" > "$OUT/public-rewrite-meta/origin-before.txt"
cd "$OUT"
git filter-repo --commit-callback "
for who in ('author', 'committer'):
    if getattr(commit, who + '_email').endswith(b'.local'):
        setattr(commit, who + '_name', b'$NEW_NAME')
        setattr(commit, who + '_email', b'$NEW_MAIL')
" >/dev/null 2>&1 || die "git filter-repo failed in $OUT (is the origin a fresh bare copy?)"
git branch -m compass-main main
git symbolic-ref HEAD refs/heads/main
snapshot "$ORIGIN" > "$OUT/public-rewrite-meta/origin-after.txt"
MAP="$OUT/filter-repo/commit-map"
TOTAL=$(awk 'NR>1' "$MAP" | wc -l | tr -d ' ')
MOVED=$(awk 'NR>1 && $1!=$2' "$MAP" | wc -l | tr -d ' ')
echo "public-rewrite: $(git filter-repo --version 2>&1 | head -1) | commit map $MAP | $TOTAL commits, $MOVED moved | out $OUT"
