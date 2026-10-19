"""test_budget - the plumbing line budget (plan 0863 appendix 13; plan 0870 P-1: Origin declaration Q7 as corrected 2026-10-03).
Counts non-blank lines of every plumbing file in checks.toml, minus the verbatim copies; CAP = 5000. Tests are
printed, never capped. Raising CAP is the Auditor's planned edit, never the Generator's.
Plan 1145: the intake pipeline (checks.toml [roles] intake) has its own role and its own cap, INTAKE_CAP = 1200 non-blank lines
(1145 measured 1021 at the end of phase 1); it is no longer counted in plumbing."""
import tomllib
from pathlib import Path

CAP = 5000
INTAKE_CAP = 1200
VERBATIM = [
    "cc/admit.py", "cc/reduce.py", "cc/gamma.py", "tests/test_kernel.py", "tests/test_sign.py", "tests/test_resample.py",
    "tests/test_kernel_rs.py", "tests/reference/verdict_x.py",
]
ROOT = Path(__file__).resolve().parent.parent


def lines(rel):
    return sum(1 for ln in (ROOT / rel).read_text().splitlines() if ln.strip())


roles = tomllib.loads((ROOT / "checks.toml").read_text())["roles"]
capped = [f for f in roles["plumbing"] if f not in VERBATIM]
counts = {f: lines(f) for f in capped}
tests = {f: lines(f) for f in roles["tests"] if f not in VERBATIM}
maths = {f: lines(f) for f in roles["maths"]}
intake = {f: lines(f) for f in roles["intake"]}
for f, n in {**counts, **intake, **tests, **maths}.items():
    print(f"  {f}: {n}")
total = sum(counts.values())
print(f"plumbing total {total} of {CAP}; tests (reported, not capped) {sum(tests.values())}; maths (reported, not capped) {sum(maths.values())}")
print(f"intake total {sum(intake.values())} of {INTAKE_CAP}")
assert not set(intake) & set(roles["plumbing"]), f"a file in both plumbing and intake: {sorted(set(intake) & set(roles['plumbing']))}"
assert sum(intake.values()) <= INTAKE_CAP, f"intake line budget exceeded: {sum(intake.values())} > {INTAKE_CAP}; stop and report which files grew"
assert total <= CAP, f"line budget exceeded: {total} > {CAP}; stop and report which files grew"
print("test_budget: all passed")
