"""test_budget - the plumbing line budget (plan 0863 appendix 13; plan 0870 P-1: Origin declaration Q7 as corrected 2026-10-03).
Counts non-blank lines of every plumbing file in checks.toml, minus the verbatim copies; CAP = 5000. Tests are
printed, never capped. Raising CAP is the Auditor's planned edit, never the Generator's.
Plan 1145: the intake pipeline (checks.toml [roles] intake) has its own role and its own cap, INTAKE_CAP = 1200 non-blank lines
(1145 measured 1023 at the end of phase 1); it is no longer counted in plumbing.
Plan 1160 P5: S7, S8 and S9 (cc/intake_feasible.py) are the role intake_feasible, FEASIBLE_CAP = 120 (83 at P5). Seen RED: FEASIBLE_CAP
made 80 (the cap assert FAILS); cc/intake_feasible.py also listed under plumbing (the disjointness assert FAILS).
Plan 1164: the intake core is split by invariant (Layout C): each module is its own role with its own cap (CORE below), and CORE_CAP = 1200,
the old INTAKE_CAP, still bounds the sum of the split core, so no line cap is raised. Seen RED: FOLD_CAP made 100 (the cap assert FAILS); the sum
bound made 1000 (CORE_CAP FAILS); cc/intake_fold.py also listed under intake (the disjointness assert FAILS).
Plan 1160 P6: S10 and the terminal (cc/intake_terminal.py) are the role intake_terminal, TERMINAL_CAP = 200 (see its line). Seen RED: TERMINAL_CAP
made 100 (the cap assert FAILS); cc/intake_terminal.py also listed under intake (the disjointness assert FAILS)."""
import tomllib
from pathlib import Path

CAP = 5000
CORE_CAP = 1200   # plan 1164: was INTAKE_CAP over the one role intake; now the sum over the roles of CORE, the core split by invariant
CORE = {"intake": 100, "intake_fold": 160, "intake_evidence": 150, "intake_bytes": 100, "intake_census": 140, "intake_say": 100,   # plan 1164: role -> cap
        "intake_blind": 200, "intake_seal": 160, "intake_read": 200}   # (BLOAT-REVIEW 1160 section 4, Layout C)
HANDOFF_CAP = 900   # plan 1160 P3: checks.toml [roles] intake_handoff, the conversion and peek (cc/intake_convert.py)
CHOICES_CAP = 120   # plan 1160 P4: checks.toml [roles] intake_choices, S1 CHOICES (every row), moved out of intake_blind so INTAKE_CAP is not raised
NAMES_CAP = 120
FEASIBLE_CAP = 120   # plan 1160 P5: checks.toml [roles] intake_feasible, S7, S8 and S9 (cc/intake_feasible.py), so INTAKE_CAP is not raised   # plan 1160 P2: checks.toml [roles] intake_names, the name classifier and Detail, moved out of the intake so INTAKE_CAP is not raised
BLINDVIEW_CAP = 80   # plan 1160 A41: checks.toml [roles] intake_blindview, `bin/cc intake blind` (cc/intake_blindview.py), so CORE_CAP is not raised
DIFFERS_CAP = 60   # plan 1160 A34: checks.toml [roles] intake_differs, what a file differs from the first in (cc/intake_differs.py), so CORE_CAP is not raised
NEW_CAP = 60   # plan 1164: checks.toml [roles] intake_new, `bin/cc new intake` (cc/intake_new.py), moved out of the intake
TERMINAL_CAP = 200   # plan 1160 P6: checks.toml [roles] intake_terminal, S10 KERNEL_HANDOFF and the terminal (cc/intake_terminal.py), so INTAKE_CAP is not raised
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
core = {r: {f: lines(f) for f in roles[r]} for r in CORE}
intake = {f: n for r in CORE for f, n in core[r].items()}   # every file of the split core
names = {f: lines(f) for f in roles["intake_names"]}
choices = {f: lines(f) for f in roles["intake_choices"]}
feasible = {f: lines(f) for f in roles["intake_feasible"]}
handoff = {f: lines(f) for f in roles["intake_handoff"]}
terminal = {f: lines(f) for f in roles["intake_terminal"]}
new = {f: lines(f) for f in roles["intake_new"]}
differs = {f: lines(f) for f in roles["intake_differs"]}
blindview = {f: lines(f) for f in roles["intake_blindview"]}
for f, n in {**counts, **intake, **names, **choices, **tests, **maths}.items():
    print(f"  {f}: {n}")
total = sum(counts.values())
print(f"plumbing total {total} of {CAP}; tests (reported, not capped) {sum(tests.values())}; maths (reported, not capped) {sum(maths.values())}")
print(f"intake core total {sum(intake.values())} of {CORE_CAP}: " + ", ".join(f"{r} {sum(core[r].values())} of {c}" for r, c in CORE.items()))
print(f"intake_names total {sum(names.values())} of {NAMES_CAP}")
print(f"intake_choices total {sum(choices.values())} of {CHOICES_CAP}")
print(f"intake_feasible total {sum(feasible.values())} of {FEASIBLE_CAP}")
print(f"intake_handoff total {sum(handoff.values())} of {HANDOFF_CAP}")
print(f"intake_terminal total {sum(terminal.values())} of {TERMINAL_CAP}")
print(f"intake_new total {sum(new.values())} of {NEW_CAP}")
print(f"intake_differs total {sum(differs.values())} of {DIFFERS_CAP}")
print(f"intake_blindview total {sum(blindview.values())} of {BLINDVIEW_CAP}")
assert not set(intake) & set(roles["plumbing"]), f"a file in both plumbing and intake: {sorted(set(intake) & set(roles['plumbing']))}"
assert sum(intake.values()) <= CORE_CAP, f"intake line budget exceeded: {sum(intake.values())} > {CORE_CAP}; stop and report which files grew"
for r, c in CORE.items():
    assert sum(core[r].values()) <= c, f"{r} line budget exceeded: {sum(core[r].values())} > {c}"
    assert not set(core[r]) & {f for q in CORE if q != r for f in core[q]}, f"{r} shares a file with another role of the core"
assert sum(names.values()) <= NAMES_CAP, f"intake_names line budget exceeded: {sum(names.values())} > {NAMES_CAP}"
assert not set(names) & (set(intake) | set(roles["plumbing"])), "intake_names shares a file with another capped role"
assert sum(choices.values()) <= CHOICES_CAP, f"intake_choices line budget exceeded: {sum(choices.values())} > {CHOICES_CAP}"
assert not set(choices) & (set(intake) | set(names) | set(roles["intake_handoff"]) | set(roles["plumbing"])), "intake_choices shares a file with another capped role"
assert sum(feasible.values()) <= FEASIBLE_CAP, f"intake_feasible line budget exceeded: {sum(feasible.values())} > {FEASIBLE_CAP}"
assert not set(feasible) & (set(intake) | set(names) | set(choices) | set(roles["intake_handoff"]) | set(roles["plumbing"])), "intake_feasible shares a file with another capped role"
assert sum(handoff.values()) <= HANDOFF_CAP, f"intake_handoff line budget exceeded: {sum(handoff.values())} > {HANDOFF_CAP}"
assert not set(handoff) & (set(intake) | set(names) | set(roles["plumbing"])), "intake_handoff shares a file with another capped role"
assert sum(terminal.values()) <= TERMINAL_CAP, f"intake_terminal line budget exceeded: {sum(terminal.values())} > {TERMINAL_CAP}"
assert not set(terminal) & (set(intake) | set(names) | set(choices) | set(feasible) | set(handoff) | set(roles["plumbing"])), "intake_terminal shares a file with another capped role"
assert sum(new.values()) <= NEW_CAP, f"intake_new line budget exceeded: {sum(new.values())} > {NEW_CAP}"
assert not set(new) & (set(intake) | set(names) | set(choices) | set(feasible) | set(handoff) | set(terminal) | set(roles["plumbing"])), "intake_new shares a file with another capped role"
assert sum(differs.values()) <= DIFFERS_CAP, f"intake_differs line budget exceeded: {sum(differs.values())} > {DIFFERS_CAP}"
assert not set(differs) & (set(intake) | set(names) | set(choices) | set(feasible) | set(handoff) | set(terminal) | set(new) | set(roles["plumbing"])), "intake_differs shares a file with another capped role"
assert sum(blindview.values()) <= BLINDVIEW_CAP, f"intake_blindview line budget exceeded: {sum(blindview.values())} > {BLINDVIEW_CAP}"
assert not set(blindview) & (set(intake) | set(names) | set(choices) | set(feasible) | set(handoff) | set(terminal) | set(new) | set(differs) | set(roles["plumbing"])), "intake_blindview shares a file with another capped role"
assert total <= CAP, f"line budget exceeded: {total} > {CAP}; stop and report which files grew"
print("test_budget: all passed")
