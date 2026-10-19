# Intake report: dial1118-s1-v3

Written by `bin/cc intake run dial1118-s1-v3`. Stage table 1160-v4, policy 1136-v1.

- **Mode** (the declarer's sealed statement of what they had seen): EXPLORATORY
- **PRIMARY verdict: PRIMARY_REFUSED_AT** at S3. Missing: none.
- **ROBUSTNESS verdict: ROBUSTNESS_WITHHELD**. Missing: none.
- **S10 KERNEL_HANDOFF** (outside both verdicts): WITHHELD.
- **Seal status** (advisory; sealing is recommended and not enforced): SEALED. A seal holds this declaration exactly as it is now. Sealed at 2026-10-19T11:46:37Z (seal-log t_ns 1792410397062602076) by Claude (plan 1160 P1) (AI_DRAFT), confirmed_by '', mode EXPLORATORY; declaration sha256 1c886138c3704d2aa4b29ee030856744c461e96fe9decfbb69966b417f4f64b8; universe '<p1118-bank>' (located at a directory named 'p1118-bank-FIXTURE'): 63 files, names and sizes in SEAL.json
- **Ordering** (information, never a refusal): NO_DATA_READ_LOGGED. The access log holds no data read of this declaration.

| stage | name | state | reads data bytes | execution |
|---|---|---|---|---|
| S0 | FORMAT | LIVE | NONE | EXECUTED |
| S1 | CHOICES | LIVE | NONE | EXECUTED |
| S2 | SEAL | LIVE | NONE | EXECUTED |
| S3 | SOURCE_INTEGRITY | LIVE | ALL_FILES | EXECUTED |
| S4 | SHAPE | LIVE | FIRST_FILE | WITHHELD |
| S5 | CENSUS | LIVE | ALL_FILES | WITHHELD |
| S6 | ADMISSIBILITY | LIVE | NONE | WITHHELD |
| S7 | INTERVAL_FEASIBILITY | LIVE | NONE | WITHHELD |
| S8 | RESOLUTION_AND_IDENTIFIABILITY | LIVE | NONE | WITHHELD |
| S9 | ALTERNATIVE_INTAKE | LIVE | ALL_FILES | WITHHELD |
| S10 | KERNEL_HANDOFF | STUB | ALL_FILES | WITHHELD |

- **S0 FORMAT** (LIVE): EXECUTED, PASS. The declaration 'dial1118-s1-v3' parses, and every field of format v3 is present, typed and listed (mode EXPLORATORY)
- **S1 CHOICES** (LIVE): EXECUTED, PASS. Checked: KNOBS_SAME_QUANTITY, MEASURED_IS_A_KNOB, SELECTION_EMPTY, SLOW_VALUES_NOT_ONE_PER_FILE, BLOCK_RULE_HAS_NO_DIRECTION, PROJECTION_REQUIRED, PROJECTION_ESTIMAND_MIXED, SECOND_LANE_MISSING, LANES_IDENTICAL, REPLICATE_IS_SWEEP_NEIGHBOUR, OPERATION_NOT_PERMITTED, PROVENANCE_HAS_NO_KERNEL_ROUTE, METHOD_NEEDS_UNCERTAINTY_COLUMN. The S1 rows that are not live are listed under the reasons no body can return yet
- **S2 SEAL** (LIVE): EXECUTED, PASS. SEALED. A seal holds this declaration exactly as it is now. Sealed at 2026-10-19T11:46:37Z (seal-log t_ns 1792410397062602076) by Claude (plan 1160 P1) (AI_DRAFT), confirmed_by '', mode EXPLORATORY; declaration sha256 1c886138c3704d2aa4b29ee030856744c461e96fe9decfbb69966b417f4f64b8; universe '<p1118-bank>' (located at a directory named 'p1118-bank-FIXTURE'): 63 files, names and sizes in SEAL.json
- **S3 SOURCE_INTEGRITY** (LIVE): EXECUTED, REFUSE ROOT_UNRESOLVED. The declared source root is not a name of intake/ROOTS.toml followed by a relative path, or it names no directory on this machine. Detail: root '<p1118-bank>' (names in intake/ROOTS.toml: ['<cc-banks>', '<cc-datasets>', '<intake-synth>'])
- **S4 SHAPE** (LIVE): WITHHELD AFTER_REFUSAL (S3). Not run: an earlier stage refused, and no later check can redeem a refusal.
- **S5 CENSUS** (LIVE): WITHHELD AFTER_REFUSAL (S3). Not run: an earlier stage refused, and no later check can redeem a refusal.
- **S6 ADMISSIBILITY** (LIVE): WITHHELD AFTER_REFUSAL (S3). Not run: an earlier stage refused, and no later check can redeem a refusal.
- **S7 INTERVAL_FEASIBILITY** (LIVE): WITHHELD AFTER_REFUSAL (S3). Not run: an earlier stage refused, and no later check can redeem a refusal.
- **S8 RESOLUTION_AND_IDENTIFIABILITY** (LIVE): WITHHELD AFTER_REFUSAL (S3). Not run: an earlier stage refused, and no later check can redeem a refusal.
- **S9 ALTERNATIVE_INTAKE** (LIVE): WITHHELD AFTER_REFUSAL (S3). Not run: an earlier stage refused, and no later check can redeem a refusal.
- **S10 KERNEL_HANDOFF** (STUB): WITHHELD AFTER_REFUSAL (S3). Not run: an earlier stage refused, and no later check can redeem a refusal.

## What the seal proves

Sealing is recommended and not enforced. It records what you declared and when; it is an integrity practice, like a lab notebook. A seal proves INTEGRITY (the declaration's sha256) and ORDERING (the seal time against the first logged data read). It never proves ignorance: mode is the declarer's sealed statement of what they had seen.

## Reasons no body can return yet

Each row below has live = false in intake/STAGES.toml: no body returns it today (a STUB stage's rows are never live), so a run cannot show it and its absence says nothing.

- S10 NO_KERNEL_ROUTE
- S10 DOOR_REFUSED

## What no stage can see

- direct shell reads (cat, less, head, cp, rsync, scp) — not logged
- other processes / external tools (MATLAB, editors, a Python without this module, Jupyter) — not logged
- reads of another copy of the bytes (other host, backup, download cache) — not logged
- atime tripwire is weak: relatime/noatime mounts suppress updates; SILENT is not evidence of no read
