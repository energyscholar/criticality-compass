#!/bin/sh
# release/cleanroom.sh (plan 1639 phase 6): install the built wheel(s) into a NEW venv, run one horizon-1 Ising hold, check the record.
# usage: cleanroom.sh [--python PY] [--data-wheel W] [--print] <wheel> | --index testpypi
# Exit 0 only when every step passes. --print shows the four run/ hashes (to re-record the constants after a change to the run).
PY=python3; DATA=; PRINT=; SRC=; INDEX=
while [ $# -gt 0 ]; do case "$1" in
  --python) PY=$2; shift 2;; --data-wheel) DATA=$2; shift 2;; --print) PRINT=1; shift;;
  --index) INDEX=$2; shift 2;; *) SRC=$1; shift;; esac; done
# Constants: sha256 of run/{score,truth}.json, run/{map,report}.jsonl of the static world at horizon 1 (needle settled, default seed).
# Recorded 2026-11-21 on macOS arm64 (python 3.11.17, numpy 2.4.x, scipy 1.17.x); Linux x86_64 gave the same bytes in recon.
# Phase 4 (1569's stamps) changes run_id and so these hashes: re-measure with --print after Phase 4.
EXPECT_score=58bc92e11acffeff736e71116c781d9415ca620ede26244637ac7fecee1baa0f; EXPECT_truth=fab35c28ed19faaa371b8851fd7296b996681a642010070a242fec16139c3a53; EXPECT_map=ac22e20411fa66576a9f192139134498aa0625267630d2fefb59faa83b7e2bd9; EXPECT_report=76dbba8209e4937d511640e3f6e4c1c2e7427f7259431e047568dc8cf310d3cb
fail() { echo "CLEANROOM FAIL: $*"; exit 1; }
"$PY" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 11) else 1)' || fail "need Python 3.11 or later: $PY"
T=$(mktemp -d "${TMPDIR:-/tmp}/cleanroom.XXXXXX") || fail "no temp dir"; trap 'rm -rf "$T"' EXIT
V=$T/venv; "$PY" -m venv "$V" || fail "venv"
if [ -n "$INDEX" ]; then
  "$V/bin/python" -m pip install -q --index-url https://test.pypi.org/simple/ --extra-index-url https://pypi.org/simple/ criticality-compass criticality-compass-data || fail "install from $INDEX"
else
  [ -f "$SRC" ] || fail "no wheel given"
  "$V/bin/python" -m pip install -q "$SRC" ${DATA:+"$DATA"} || fail "pip install"
fi
SP=$("$V/bin/python" -c 'import sysconfig; print(sysconfig.get_paths()["purelib"])')
snap() { (cd "$SP" && find . -type f -not -name '*.pyc' -not -path '*/__pycache__/*' | LC_ALL=C sort | cksum); }
BEFORE=$(snap)
C=$V/bin/compass; mkdir "$T/cwd"; cd "$T/cwd" || fail "cwd"
export COMPASS_RUNS=$T/runs; unset PYTHONPATH CC_DATA_ROOT
"$C" hold --list > "$T/list.out" 2>&1; grep -q ising "$T/list.out" || fail "hold --list does not name ising"
"$V/bin/python" - "$SP" "$T/world.toml" <<'PYEOF' || fail "no static world in the install"
import re, sys, pathlib
w = pathlib.Path(sys.argv[1], "criticality_compass/workspace/system-instantiated/plugins/ising/ising-apparatus-static.toml").read_text()
pathlib.Path(sys.argv[2]).write_text(re.sub(r"(?m)^horizon\s*=.*$", "horizon = 1", w))
PYEOF
perl -e 'alarm 300; exec @ARGV' "$C" hold ising "$T/world.toml" --needle settled > "$T/hold.out" 2>&1 || { tail -5 "$T/hold.out"; fail "hold run"; }
REC=$(ls -d "$T"/runs/*/ 2>/dev/null | head -1); [ -n "$REC" ] || fail "no record written"
"$C" hold --verify "$REC" > /dev/null 2>&1 || fail "--verify"
[ -f "$V/share/man/man1/compass.1" ] || fail "man page missing"
[ "$BEFORE" = "$(snap)" ] || fail "something was written inside site-packages"
HP="/Us""ers/|/ho""me/"; if grep -rIlE "$HP" "$REC" > /dev/null 2>&1; then fail "a host path is in the record"; fi
H() { "$V/bin/python" -c 'import hashlib,sys; print(hashlib.sha256(open(sys.argv[1],"rb").read()).hexdigest())' "$REC/run/$1"; }
for f in score.json truth.json map.jsonl report.jsonl; do k=${f%%.*}; got=$(H "$f")
  if [ -n "$PRINT" ]; then echo "EXPECT_$k=$got"; continue; fi
  eval "want=\$EXPECT_$k"; [ "$got" = "$want" ] || fail "run/$f differs: $got (want $want)"
done
echo "CLEANROOM OK: $("$V/bin/python" -V) on $(uname -sm); run $(basename "$REC")"
