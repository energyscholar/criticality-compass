"""handoff_check - plan 1639 phase 8: the hand-off checklist. Reads release/blockers.toml, runs the named check of every closed row (never trusts the row), prints the table.
Exit 1 if a row is open, a check fails, an owner-gated row has no ruling, or an expected row is missing. --no-run skips the checks (the table only); --blockers FILE reads another table."""
import os
import subprocess
import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = Path(os.environ.get("HANDOFF_OUT", Path.home() / "1639-out"))
EXPECTED = ['test-wheel-green', 'env-file-host-paths', '1569-stamps', 'scan-extended', 'records-clean', 'R4', 'R5', 'R8', 'D1', 'D2', 'D3', 'D4', 'D5', 'D6', 'D7', 'O1', 'O2', 'O3', 'O4', 'O5', 'stub-0.0.1-uploaded', 'upload-go-0.1.0', 'repo-url-at-release', 'plan-numbers-rejudged', 'opsec-review', 'notice-names-kernel-port', 'kernel-extra-dropped', 'cleanroom-macos-arm64', 'cleanroom-linux-x86_64', 'a2-section4-list-ruled']


def run_test(stem, cache):
    if stem not in cache:
        r = subprocess.run([sys.executable, str(ROOT / stem)], capture_output=True, text=True, cwd=ROOT)
        cache[stem] = (r.returncode, [ln for ln in (r.stdout + r.stderr).splitlines() if ln.startswith(("ok ", "FAIL "))])
    return cache[stem]


def evaluate(check, cache):
    """-> (passed, why). Silence is not a pass: a named text must have an ok line."""
    if check.startswith("file:"):
        f = OUT / check[5:]
        return (f.is_file() and "CLEANROOM OK" in f.read_text(), f"{f.name} lacks CLEANROOM OK")
    stem, _, text = check.partition("#")
    rc, lines = run_test(stem, cache)
    if not text:
        return rc == 0, f"{stem} exits {rc}"
    bad = [ln for ln in lines if ln.startswith("FAIL ") and text in ln]
    return (not bad and any(ln.startswith("ok ") and text in ln for ln in lines), f"{stem}: " + (bad[0][:90] if bad else f"no ok line holds `{text}`"))


def main(argv):
    path = Path(argv[argv.index("--blockers") + 1]) if "--blockers" in argv else ROOT / "release" / "blockers.toml"
    rows = {r["id"]: r for r in tomllib.loads(path.read_text()).get("row", [])}
    cache, trouble = {}, []
    for i in EXPECTED:
        if i not in rows:
            trouble.append(f"{i}: MISSING from the table")
    for i, r in rows.items():
        s, note = r.get("state"), ""
        if s == "open":
            trouble.append(f"{i}: open ({r.get('ruling', '')})")
        elif s == "owner-gated" and not r.get("ruling", "").strip():
            trouble.append(f"{i}: owner-gated, no recorded ruling")
        elif s == "closed" and "--no-run" not in argv:
            ok, note = evaluate(r.get("check", ""), cache) if r.get("check") else (False, "a closed row names no check")
            if not ok:
                trouble.append(f"{i}: closed but its check fails ({note})")
        elif s not in ("closed", "owner-gated"):
            trouble.append(f"{i}: unknown state {s!r}")
        print(f"{i:28} {s:12} {'FAIL' if any(t.startswith(i + ':') for t in trouble) else 'ok'}")
    print(f"{len(rows)} rows, {len(trouble)} problem(s)")
    for t in trouble:
        print("  " + t)
    return 1 if trouble else 0


sys.exit(main(sys.argv[1:]))
