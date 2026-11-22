#!/bin/sh
# release/release.sh (plan 1639 phase 9): build both distributions from a clean tree, check them, print sizes and sha256s.
# usage: release.sh [--upload testpypi|pypi]       env: CC_RELEASE_TOOLS = a python that has `build` and `twine` (default python3); CC_CLEAN_PY = python >= 3.11 for the clean room.
# Without --upload NOTHING leaves this machine: the gates (scan, hand-off check, clean room) are reported and only block an upload.
# With --upload the gates must all pass, the version must be >= 0.1.0, and the token comes from twine's own keyring/config; this script never reads or prints it.
cd "$(dirname "$0")/.." || exit 1
TOOLS=${CC_RELEASE_TOOLS:-python3}; CLEAN=${CC_CLEAN_PY:-python3}; UP=
[ "$1" = "--upload" ] && { UP=$2; case "$UP" in testpypi|pypi) ;; *) echo "REFUSED: --upload takes testpypi or pypi"; exit 1;; esac; }
[ -z "$(git status --porcelain)" ] || { echo "REFUSED: the tree is not clean (git status)"; exit 1; }
VER=$("$TOOLS" -c 'import tomllib; print(tomllib.load(open("pyproject.toml","rb"))["project"]["version"])')
"$TOOLS" -c 'import sys; v=tuple(int(x) for x in sys.argv[1].split(".")); sys.exit(0 if v >= (0,1,0) else 1)' "$VER" || { [ -z "$UP" ] || { echo "REFUSED: no upload below 0.1.0 (the 0.0.1 name stub is the Auditor's)"; exit 1; }; }
OUT=$(mktemp -d "${TMPDIR:-/tmp}/release.XXXXXX"); GATES=0
nice -n 19 "$TOOLS" -m build --sdist --wheel -o "$OUT" . > "$OUT.build.log" 2>&1 || { tail -5 "$OUT.build.log"; echo "FAIL: build"; exit 1; }
(cd release/data && nice -n 19 "$TOOLS" -m build --wheel -o "$OUT" . > "$OUT.build-data.log" 2>&1) || { tail -5 "$OUT.build-data.log"; echo "FAIL: build of the data wheel"; exit 1; }
"$TOOLS" -m twine check "$OUT"/*.whl "$OUT"/*.tar.gz || { echo "FAIL: twine check"; exit 1; }
echo "== scan: every file of every artifact (vocabulary, host paths, addresses)"
"$TOOLS" - "$OUT" <<'PYEOF' || { echo "GATE FAIL: the scan has hits"; GATES=1; }
import sys, glob
sys.path.insert(0, "tests")
import test_wheel
n = 0
for a in sorted(glob.glob(sys.argv[1] + "/*.whl") + glob.glob(sys.argv[1] + "/*.tar.gz")):
    for name, hits in sorted(test_wheel.scan_members(a).items()):
        n += 1; print(f"  {a.rsplit('/', 1)[-1]}: {name}: lines {[i for i, _ in hits][:6]}")
print(f"  {n} file(s) with hits"); sys.exit(1 if n else 0)
PYEOF
echo "== hand-off check"; "$TOOLS" release/handoff_check.py || { echo "GATE FAIL: the hand-off check"; GATES=1; }
echo "== clean room"
DW=$(ls "$OUT"/criticality_compass_data-*.whl); CW=$(ls "$OUT"/criticality_compass-*.whl)
nice -n 19 sh release/cleanroom.sh --python "$CLEAN" --data-wheel "$DW" "$CW" || { echo "GATE FAIL: the clean room"; GATES=1; }
echo "== sizes and sha256"
for f in "$OUT"/*.whl "$OUT"/*.tar.gz; do printf '%s  %s bytes  ' "$(basename "$f")" "$(wc -c < "$f" | tr -d ' ')"; "$TOOLS" -c 'import hashlib,sys; print(hashlib.sha256(open(sys.argv[1],"rb").read()).hexdigest())' "$f"; done
echo "artifacts in $OUT; gates: $([ $GATES = 0 ] && echo pass || echo 'NOT passed (blocks an upload only)')"
[ -n "$UP" ] || { echo "dry run: nothing uploaded"; exit 0; }
[ $GATES = 0 ] || { echo "REFUSED: a gate failed; nothing uploaded"; exit 1; }
exec "$TOOLS" -m twine upload --repository "$UP" "$OUT"/*.whl "$OUT"/*.tar.gz
