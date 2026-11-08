"""test_budget - the plumbing line budget (plan 0863 appendix 13; plan 0870 P-1: Origin declaration Q7 as corrected 2026-10-03).
Counts non-blank lines of every plumbing file in checks.toml, minus the verbatim copies; CAP = 5031. Tests are
printed, never capped. Raising CAP is the Auditor's planned edit, never the Generator's.
Plan 1145: the intake pipeline (checks.toml [roles] intake) has its own role and its own cap, INTAKE_CAP = 1200 non-blank lines
(1145 measured 1023 at the end of phase 1); it is no longer counted in plumbing.
Plan 1160 P5: S7, S8 and S9 (cc/intake_feasible.py) are the role intake_feasible, FEASIBLE_CAP = 120 (83 at P5). Seen RED: FEASIBLE_CAP
made 80 (the cap assert FAILS); cc/intake_feasible.py also listed under plumbing (the disjointness assert FAILS).
Plan 1164: the intake core is split by invariant (Layout C): each module is its own role with its own cap (CORE below), and CORE_CAP = 1200,
the old INTAKE_CAP, still bounds the sum of the split core, so no line cap is raised. Seen RED: FOLD_CAP made 100 (the cap assert FAILS); the sum
bound made 1000 (CORE_CAP FAILS); cc/intake_fold.py also listed under intake (the disjointness assert FAILS).
Plan 1160 P6: S10 and the terminal (cc/intake_terminal.py) are the role intake_terminal, TERMINAL_CAP = 200 (see its line). Seen RED: TERMINAL_CAP
made 100 (the cap assert FAILS); cc/intake_terminal.py also listed under intake (the disjointness assert FAILS).
Plan 1165: pre-processing (cc/intake_profile.py) is the role intake_profile, PROFILE_CAP = 320 (plan 1165 D5). Seen RED: PROFILE_CAP made 100 (the
cap assert FAILS); cc/intake_profile.py also listed under intake_handoff (the disjointness assert FAILS). The cross-check is the role intake_against,
AGAINST_CAP = 80 (D5's split). Seen RED: AGAINST_CAP made 10 (the cap assert FAILS); cc/intake_against.py also under intake_profile (FAILS: intake_profile's cap first, 338 > 320).
Plan 1165 fix S11.P2b F3: the findings table (cc/intake_findings.py) is the role intake_findings, FINDINGS_CAP = 160, split from intake_profile
(318 of 320, no room for NOT_A_TABLE); no cap rises. Seen RED: FINDINGS_CAP made 10 (the cap assert FAILS); cc/intake_findings.py also listed
under intake_against (FAILS: intake_against's cap first, 178 > 80); also listed under intake_handoff (FAILS "intake_findings shares a file with
another capped role").
Plan 1176 phase B: the R1 feature projection and side oracle (cc/intake_feature.py) is the role intake_feature, FEATURE_CAP = 200; no cap rises.
Seen RED (tests/test_feature.py B9): FEATURE_CAP made 100 (the cap assert FAILS); cc/intake_feature.py also listed under intake_handoff (the disjointness assert FAILS).
Plan 1176 phase A: FORMAT v14's [plane] and [suspect] in cells (cc/intake_suspect.py) is the role intake_suspect, SUSPECT_CAP = 160; no cap rises.
Seen RED (tests/test_suspect.py A6): SUSPECT_CAP made 100 (the cap assert FAILS); cc/intake_suspect.py also listed under intake_handoff (the disjointness assert FAILS).
Plan 1176 phase D: family mode of `cc navigate` (cc/navfamily.py) is the role navigate_family, NAVFAMILY_CAP = 200; no cap rises (cc/linenav.py,
the vendored frozen navigator, is in maths, uncapped). Seen RED (tests/test_navfamily.py D6): NAVFAMILY_CAP made 100 (the cap assert FAILS);
cc/navfamily.py also listed under intake_handoff (the disjointness assert FAILS).
Plan 1273 A1: what this HOST holds (cc/host.py) is the role host, HOST_CAP = 80 (50 at A1); plumbing was 4994 of 5000 with it, so no cap rises. Seen RED:
HOST_CAP made 40 (the cap assert FAILS); cc/host.py also listed under plumbing (the disjointness assert FAILS).
Plan 1282 P1a: the sampler adapter (cc/sampler.py) is the role sampler, SAMPLER_CAP = 200 (P1a holds it at 160 or fewer; P1b adds), disjoint from every other role, host included.
Seen RED: SAMPLER_CAP made 10 (the cap assert FAILS); cc/sampler.py also listed under plumbing (the disjointness assert FAILS).
Plan 1282 P1c: the seal refusals (cc/seal_reach.py) are the role seal_reach, SEAL_REACH_CAP = 120, disjoint from every other role, host and sampler included.
Seen RED: SEAL_REACH_CAP made 10 (the cap assert FAILS); cc/seal_reach.py also listed under plumbing (the disjointness assert FAILS).
Plan 1335: CAP 5000 -> 5030 (Auditor-authorised; macOS platform table). Seen RED: at CAP 5000 after edits 1-3 the cap assert FAILS.
Plan 1282 P1b: CAP 5030 -> 5031 (owner-granted up to +4; the door's one call into cc/sampler.py for the L check). Seen RED: at CAP 5030 after the edit the cap assert FAILS.
Plan 1282 P2a: R-P2.1, CAP 5031 -> 5034 (owner-ruled at most 5034: the couplings no-[data] finding in cc/declare.py and the import of the one instrument loader in
cc/schema.py and cc/detect.py). The loader (cc/instrument_decl.py) is the role instrument_decl, INSTRUMENT_DECL_CAP = 20, disjoint from every other role.
Seen RED: at CAP 5031 after the edits the cap assert FAILS; INSTRUMENT_DECL_CAP made 10 (the cap assert FAILS).
Plan 1427 P1: CORE_CAP 1240 -> 1248 (Auditor-authorised; homes of D3/D4/D9 in intake_blind/intake_seal; the plan is net-negative overall). Seen RED: at 1240 after P1 the cap assert FAILS.
Plan 1427 P3: CORE_CAP 1248 -> 1249 (Auditor-authorised; `import registry` in the intake modules that hashed a file). Seen RED: at 1248 after P3 the cap assert FAILS (p3-budget-red.txt)."""
import tomllib
from pathlib import Path

CAP = 5034   # plan 1282 P2a: R-P2.1
CORE_CAP = 1249   # plan 1427 P3: was 1248. plan 1427 P1: was 1240. plan 1205 P1 (Auditor): +40 for the hdf5-table-v1 reader. plan 1164: was INTAKE_CAP over the one role intake; now the sum over the roles of CORE, the core split by invariant
CORE = {"intake": 100, "intake_fold": 160, "intake_evidence": 150, "intake_bytes": 100, "intake_census": 140, "intake_say": 100,   # plan 1164: role -> cap
        "intake_blind": 200, "intake_seal": 160, "intake_read": 215}   # (BLOAT-REVIEW 1160 section 4, Layout C)
HANDOFF_CAP = 900   # plan 1160 P3: checks.toml [roles] intake_handoff, the conversion and peek (cc/intake_convert.py)
CHOICES_CAP = 120   # plan 1160 P4: checks.toml [roles] intake_choices, S1 CHOICES (every row), moved out of intake_blind so INTAKE_CAP is not raised
NAMES_CAP = 120
FEASIBLE_CAP = 120   # plan 1160 P5: checks.toml [roles] intake_feasible, S7, S8 and S9 (cc/intake_feasible.py), so INTAKE_CAP is not raised   # plan 1160 P2: checks.toml [roles] intake_names, the name classifier and Detail, moved out of the intake so INTAKE_CAP is not raised
BLINDVIEW_CAP = 80   # plan 1160 A41: checks.toml [roles] intake_blindview, `bin/cc intake blind` (cc/intake_blindview.py), so CORE_CAP is not raised
DIFFERS_CAP = 60   # plan 1160 A34: checks.toml [roles] intake_differs, what a file differs from the first in (cc/intake_differs.py), so CORE_CAP is not raised
AGAINST_CAP = 85   # plan 1205 P1 (Auditor): +5 for the 8 hdf5 reader codes. plan 1165 D5: checks.toml [roles] intake_against, the cross-check split from intake_profile (cc/intake_against.py)
FINDINGS_CAP = 160   # plan 1165 fix S11.P2b F3: checks.toml [roles] intake_findings, the findings table split from intake_profile (cc/intake_findings.py)
PROFILE_CAP = 320   # plan 1165 D5: checks.toml [roles] intake_profile, `bin/cc intake profile` (cc/intake_profile.py), so CORE_CAP is not raised
NEW_CAP = 60   # plan 1164: checks.toml [roles] intake_new, `bin/cc new intake` (cc/intake_new.py), moved out of the intake
FEATURE_CAP = 200   # plan 1176 phase B: checks.toml [roles] intake_feature, the R1 feature projection and side oracle (cc/intake_feature.py), so CORE_CAP is not raised
NAVFAMILY_CAP = 200   # plan 1176 phase D: checks.toml [roles] navigate_family, `cc navigate family | score` (cc/navfamily.py)
SUSPECT_CAP = 160   # plan 1176 phase A: checks.toml [roles] intake_suspect, FORMAT v14's [plane] and [suspect] in cells (cc/intake_suspect.py), so CORE_CAP is not raised
TERMINAL_CAP = 200   # plan 1160 P6: checks.toml [roles] intake_terminal, S10 KERNEL_HANDOFF and the terminal (cc/intake_terminal.py), so INTAKE_CAP is not raised
HOST_CAP = 80   # plan 1273 A1: checks.toml [roles] host, what this host holds of the data root and the toolset (cc/host.py), split from plumbing so CAP is not raised
SAMPLER_CAP = 200   # plan 1282 P1a: checks.toml [roles] sampler, the declared sampler adapter (cc/sampler.py), its own role so CAP is not raised
SEAL_REACH_CAP = 120   # plan 1282 P1c: checks.toml [roles] seal_reach, the seal's seed, reach and licence refusals (cc/seal_reach.py), its own role so CAP is not raised
INSTRUMENT_DECL_CAP = 20   # plan 1282 P2a (R-P2.3): checks.toml [roles] instrument_decl, the one instrument loader (cc/instrument_decl.py), its own role
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
profile = {f: lines(f) for f in roles["intake_profile"]}
against = {f: lines(f) for f in roles["intake_against"]}
findings = {f: lines(f) for f in roles["intake_findings"]}
feature = {f: lines(f) for f in roles["intake_feature"]}
suspect = {f: lines(f) for f in roles["intake_suspect"]}
navfamily = {f: lines(f) for f in roles["navigate_family"]}
host = {f: lines(f) for f in roles["host"]}
sampler = {f: lines(f) for f in roles["sampler"]}
seal_reach = {f: lines(f) for f in roles["seal_reach"]}
instrument_decl = {f: lines(f) for f in roles["instrument_decl"]}
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
print(f"intake_profile total {sum(profile.values())} of {PROFILE_CAP}")
print(f"intake_against total {sum(against.values())} of {AGAINST_CAP}")
print(f"intake_findings total {sum(findings.values())} of {FINDINGS_CAP}")
print(f"intake_feature total {sum(feature.values())} of {FEATURE_CAP}")
print(f"intake_suspect total {sum(suspect.values())} of {SUSPECT_CAP}")
print(f"navigate_family total {sum(navfamily.values())} of {NAVFAMILY_CAP}")
print(f"host total {sum(host.values())} of {HOST_CAP}")
print(f"sampler total {sum(sampler.values())} of {SAMPLER_CAP}")
print(f"seal_reach total {sum(seal_reach.values())} of {SEAL_REACH_CAP}")
print(f"instrument_decl total {sum(instrument_decl.values())} of {INSTRUMENT_DECL_CAP}")
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
assert sum(profile.values()) <= PROFILE_CAP, f"intake_profile line budget exceeded: {sum(profile.values())} > {PROFILE_CAP}"
assert not set(profile) & (set(intake) | set(names) | set(choices) | set(feasible) | set(handoff) | set(terminal) | set(new) | set(differs) | set(blindview) | set(against) | set(roles["plumbing"])), "intake_profile shares a file with another capped role"
assert sum(against.values()) <= AGAINST_CAP, f"intake_against line budget exceeded: {sum(against.values())} > {AGAINST_CAP}"
assert not set(against) & (set(intake) | set(names) | set(choices) | set(feasible) | set(handoff) | set(terminal) | set(new) | set(differs) | set(blindview) | set(roles["plumbing"])), "intake_against shares a file with another capped role"
assert sum(findings.values()) <= FINDINGS_CAP, f"intake_findings line budget exceeded: {sum(findings.values())} > {FINDINGS_CAP}"
assert not set(findings) & (set(intake) | set(names) | set(choices) | set(feasible) | set(handoff) | set(terminal) | set(new) | set(differs) | set(blindview) | set(against) | set(profile) | set(roles["plumbing"])), "intake_findings shares a file with another capped role"
assert sum(feature.values()) <= FEATURE_CAP, f"intake_feature line budget exceeded: {sum(feature.values())} > {FEATURE_CAP}"
assert not set(feature) & (set(intake) | set(names) | set(choices) | set(feasible) | set(handoff) | set(terminal) | set(new) | set(differs) | set(blindview) | set(against) | set(profile) | set(findings) | set(roles["plumbing"])), "intake_feature shares a file with another capped role"
assert sum(suspect.values()) <= SUSPECT_CAP, f"intake_suspect line budget exceeded: {sum(suspect.values())} > {SUSPECT_CAP}"
assert not set(suspect) & (set(intake) | set(names) | set(choices) | set(feasible) | set(handoff) | set(terminal) | set(new) | set(differs) | set(blindview) | set(against) | set(profile) | set(findings) | set(feature) | set(roles["plumbing"])), "intake_suspect shares a file with another capped role"
assert sum(navfamily.values()) <= NAVFAMILY_CAP, f"navigate_family line budget exceeded: {sum(navfamily.values())} > {NAVFAMILY_CAP}"
assert not set(navfamily) & (set(intake) | set(names) | set(choices) | set(feasible) | set(handoff) | set(terminal) | set(new) | set(differs) | set(blindview) | set(against) | set(profile) | set(findings) | set(feature) | set(suspect) | set(roles["plumbing"])), "navigate_family shares a file with another capped role"
assert sum(host.values()) <= HOST_CAP, f"host line budget exceeded: {sum(host.values())} > {HOST_CAP}"
assert not set(host) & (set(intake) | set(names) | set(choices) | set(feasible) | set(handoff) | set(terminal) | set(new) | set(differs) | set(blindview) | set(against) | set(profile) | set(findings) | set(feature) | set(suspect) | set(navfamily) | set(roles["plumbing"])), "host shares a file with another capped role"
assert sum(sampler.values()) <= SAMPLER_CAP, f"sampler line budget exceeded: {sum(sampler.values())} > {SAMPLER_CAP}"
assert not set(sampler) & {f for r, fs in roles.items() if r != "sampler" for f in fs}, "sampler shares a file with another role"
assert sum(seal_reach.values()) <= SEAL_REACH_CAP, f"seal_reach line budget exceeded: {sum(seal_reach.values())} > {SEAL_REACH_CAP}"
assert not set(seal_reach) & {f for r, fs in roles.items() if r != "seal_reach" for f in fs}, "seal_reach shares a file with another role"
assert sum(instrument_decl.values()) <= INSTRUMENT_DECL_CAP, f"instrument_decl line budget exceeded: {sum(instrument_decl.values())} > {INSTRUMENT_DECL_CAP}"
assert not set(instrument_decl) & {f for r, fs in roles.items() if r != "instrument_decl" for f in fs}, "instrument_decl shares a file with another role"
assert total <= CAP, f"line budget exceeded: {total} > {CAP}; stop and report which files grew"
print("test_budget: all passed")
