#!/bin/sh
# ci-run.sh - plan 1640: the one command the CI workflow runs (and release/ci-local.sh runs the same). The test set is DERIVED, never listed here:
# the fast set = checks.toml [roles].tests minus cc.toml [check].slow; of it, a stem in [check].needs_data, [check].needs_rust or [check].needs_commit_host is SKIPPED (one
# line each, saying which list), the rest RUN through `bin/cc test`. The two sets are checked to be disjoint and total over the fast set (a stem
# in neither, or in both, is a refusal, exit 1).
# usage: release/ci-run.sh [--list]     --list prints RUN / SKIPPED lines and exits 0 (or 1 if the sets are not total and disjoint)
set -eu
ROOT=$(cd "$(dirname "$0")/.." && pwd)
PY=${PYTHON:-python3}; command -v "$PY" >/dev/null 2>&1 || PY=python
SETS=$("$PY" - "$ROOT" <<'PYEOF'
import sys, tomllib
from pathlib import Path
root = Path(sys.argv[1])
stems = [Path(f).stem for f in tomllib.loads((root / "checks.toml").read_text())["roles"]["tests"]]
cfg = tomllib.loads((root / "cc.toml").read_text())["check"]
fast = [s for s in stems if s not in cfg["slow"]]
why = {"needs_data": "needs the author's data root or toolset", "needs_rust": "needs the Rust kernel build", "needs_commit_host": "needs a requirement of the commit host (openpyxl)"}
skip = {}
for lst in ("needs_data", "needs_rust", "needs_commit_host"):   # a stem in both lists is reported under the second
    for s in cfg[lst]:
        if s in fast:
            skip[s] = f"SKIPPED {s}: {why[lst]} (cc.toml [check].{lst})"
run = [s for s in fast if s not in skip]
assert set(run) | set(skip) == set(fast) and not set(run) & set(skip), "the RUN and SKIPPED sets are not disjoint and total over the fast set"
print("\n".join([f"RUN {s}" for s in run] + [skip[s] for s in fast if s in skip]))
PYEOF
) || { echo "ci-run: REFUSED: the run set could not be derived from checks.toml and cc.toml"; exit 1; }
if [ "${1:-}" = "--list" ]; then echo "$SETS"; exit 0; fi
echo "$SETS" | sed -n '/^SKIPPED /p'   # sed prints the matching lines and exits 0 when there are none (grep exits 1, which `set -e` turns into a failed run)
STEMS=$(echo "$SETS" | sed -n 's/^RUN //p' | tr '\n' ' ')
CC_SLOTS=$(mktemp -d "${TMPDIR:-/tmp}/cc-slots.XXXXXX"); CC_JOBS=${CC_JOBS:-2}   # two workers unless the caller says more: the 2-core limit of the hosts the suite is measured on (plan 1640 F3)
export CC_SLOTS CC_JOBS
trap 'rm -rf "$CC_SLOTS"' EXIT
cd "$ROOT"
echo "ci-run: bin/cc validate (printed for its NOT EVALUABLE line; its status is not CI's)"
"$PY" bin/cc validate 2>&1 | tail -3 || true
echo "ci-run: bin/cc test: $(echo "$STEMS" | wc -w | tr -d ' ') tests, CC_JOBS=$CC_JOBS"
# shellcheck disable=SC2086
"$PY" bin/cc test $STEMS
