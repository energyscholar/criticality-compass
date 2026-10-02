"""test_budget - the plumbing + tests line budget (plan 0863 appendix 13).
Counts non-blank lines of every plumbing and tests file in checks.toml, minus the verbatim copies.
Raising CAP is the Auditor's planned edit, never the Generator's."""
import tomllib
from pathlib import Path

CAP = 3600
VERBATIM = [
    "cc/admit.py", "tests/test_kernel.py", "tests/test_sign.py", "tests/test_resample.py",
    "tests/test_kernel_rs.py", "tests/reference/verdict_x.py",
]
ROOT = Path(__file__).resolve().parent.parent


def lines(rel):
    return sum(1 for ln in (ROOT / rel).read_text().splitlines() if ln.strip())


roles = tomllib.loads((ROOT / "checks.toml").read_text())["roles"]
capped = [f for f in roles["plumbing"] + roles["tests"] if f not in VERBATIM]
counts = {f: lines(f) for f in capped}
maths = {f: lines(f) for f in roles["maths"]}
for f, n in {**counts, **maths}.items():
    print(f"  {f}: {n}")
total = sum(counts.values())
print(f"capped total {total} of {CAP}; maths (reported, not capped) {sum(maths.values())}")
assert total <= CAP, f"line budget exceeded: {total} > {CAP}; stop and report which files grew"
print("test_budget: all passed")
