#!/bin/sh
# ci-local.sh - plan 1640: the CI job, run on this machine against a fresh clone (nothing untracked, no data root), so the workflow can be seen to work
# before it is ever pushed.
# usage: release/ci-local.sh [--repo DIR] [--rev REV] [--python PY] [--result FILE]
#   --repo   the repository to clone (default: this one)     --rev     the commit to test (default HEAD; with --repo of a bare copy, its main)
#   --python the interpreter that makes the venv (default python3)   --result the result file (default ci-local-result.txt in the current directory)
# The result file: `tree <sha>` of the tested commit's tree, one `FAILED <stem>` line per failed test, one `SKIPPED ...` line per skip, then `exit <n>`.
# Exit 0 only if ci-run.sh exited 0.
set -u
HERE=$(cd "$(dirname "$0")/.." && pwd)
REPO="$HERE"; REV=""; PYX=python3; RESULT="$(pwd)/ci-local-result.txt"
while [ $# -gt 0 ]; do
  case "$1" in
    --repo) REPO="$2"; shift 2 ;; --rev) REV="$2"; shift 2 ;; --python) PYX="$2"; shift 2 ;; --result) RESULT="$2"; shift 2 ;;
    *) echo "ci-local: unknown argument $1"; exit 2 ;;
  esac
done
case "$RESULT" in /*) ;; *) RESULT="$(pwd)/$RESULT" ;; esac
[ -n "$REV" ] || REV=$(git -C "$REPO" rev-parse --verify -q HEAD || git -C "$REPO" rev-parse --verify main)
W=$(mktemp -d "${TMPDIR:-/tmp}/ci-local.XXXXXX")
trap 'rm -rf "$W"' EXIT
git clone -q --no-local "$REPO" "$W/c" || { echo "ci-local: clone failed"; exit 2; }
git -C "$W/c" checkout -q "$REV" || { echo "ci-local: no such rev $REV"; exit 2; }
TREE=$(git -C "$W/c" rev-parse 'HEAD^{tree}')
"$PYX" -m venv "$W/venv" || { echo "ci-local: venv failed"; exit 2; }
"$W/venv/bin/python" -m pip install -q -e "$W/c[test]" >"$W/pip.txt" 2>&1 || { tail -5 "$W/pip.txt"; echo "ci-local: pip install failed"; exit 2; }
env -u CC_DATA_ROOT PYTHON="$W/venv/bin/python" sh "$W/c/release/ci-run.sh" >"$W/run.txt" 2>&1
RC=$?
{
  echo "tree $TREE"
  sed -n 's/^FAIL \([A-Za-z0-9_]*\)$/FAILED \1/p' "$W/run.txt"
  grep '^SKIPPED ' "$W/run.txt"
  echo "exit $RC"
} > "$RESULT"
tail -3 "$W/run.txt"
echo "ci-local: result $RESULT (exit $RC)"
exit $RC
