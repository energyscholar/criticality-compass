# Intake report: dial1118-s1-v5

Written by `bin/cc intake run dial1118-s1-v5`. Stage table 1160-v10, policy 1136-v1.

- **Mode** (the declarer's sealed statement of what they had seen): EXPLORATORY
- **PRIMARY verdict: PRIMARY_REFUSED_AT** at S4. Missing: none.
- **ROBUSTNESS verdict: ROBUSTNESS_WITHHELD**. Missing: none.
- **S10 KERNEL_HANDOFF** (the terminal; it counts toward PRIMARY): WITHHELD.
- **Seal status** (advisory; sealing is recommended and not enforced): SEALED. A seal holds this declaration exactly as it is now. Sealed at 2026-10-20T00:05:02Z (seal-log t_ns 1792454702952478333) by Claude (plan 1160 loop4 A33) (AI_DRAFT), confirmed_by '', mode EXPLORATORY; declaration sha256 0ca08e029982d3e93cb7b42cc73fdd3ddb725bed4a7d4ec5ee2d686c6b0bacef; universe '<p1118-bank>' (located at a directory named 'p1118-bank-FIXTURE'): 63 files, names and sizes in SEAL.json
- **Ordering** (information, never a refusal): READS_FOLLOW_SEAL. Every logged data read of this declaration came after its seal.

| stage | name | state | reads data bytes | execution |
|---|---|---|---|---|
| S0 | FORMAT | LIVE | NONE | EXECUTED |
| S1 | CHOICES | LIVE | NONE | EXECUTED |
| S2 | SEAL | LIVE | NONE | EXECUTED |
| S3 | SOURCE_INTEGRITY | LIVE | ALL_FILES | EXECUTED |
| S4 | SHAPE | LIVE | FIRST_FILE | EXECUTED |
| S5 | CENSUS | LIVE | ALL_FILES | WITHHELD |
| S6 | ADMISSIBILITY | LIVE | NONE | WITHHELD |
| S7 | INTERVAL_FEASIBILITY | LIVE | NONE | WITHHELD |
| S8 | RESOLUTION_AND_IDENTIFIABILITY | LIVE | NONE | WITHHELD |
| S10 | KERNEL_HANDOFF | LIVE | ALL_FILES | WITHHELD |
| S9 | ALTERNATIVE_INTAKE | LIVE | ALL_FILES | WITHHELD |

- **S0 FORMAT** (LIVE): EXECUTED, PASS. The declaration 'dial1118-s1-v5' parses, and every field of format v5 is present, typed and listed (mode EXPLORATORY)
- **S1 CHOICES** (LIVE): EXECUTED, PASS. Checked: KNOBS_SAME_QUANTITY, MEASURED_IS_A_KNOB, SELECTION_EMPTY, SLOW_VALUES_NOT_ONE_PER_FILE, SLOW_NONE_HAS_NO_PATH, SLOW_KNOB_HAS_NO_METRIC, BLOCK_RULE_HAS_NO_DIRECTION, PROJECTION_REQUIRED, PROJECTION_ESTIMAND_MIXED, SECOND_LANE_MISSING, LANES_IDENTICAL, REPLICATE_IS_SWEEP_NEIGHBOUR, MEASURED_KNOB_HAS_NO_POINTS, OPERATION_NOT_PERMITTED, PROVENANCE_HAS_NO_KERNEL_ROUTE, METHOD_NEEDS_UNCERTAINTY_COLUMN. The S1 rows that are not live are listed under the reasons no body can return yet
- **S2 SEAL** (LIVE): EXECUTED, PASS. SEALED. A seal holds this declaration exactly as it is now. Sealed at 2026-10-20T00:05:02Z (seal-log t_ns 1792454702952478333) by Claude (plan 1160 loop4 A33) (AI_DRAFT), confirmed_by '', mode EXPLORATORY; declaration sha256 0ca08e029982d3e93cb7b42cc73fdd3ddb725bed4a7d4ec5ee2d686c6b0bacef; universe '<p1118-bank>' (located at a directory named 'p1118-bank-FIXTURE'): 63 files, names and sizes in SEAL.json
- **S3 SOURCE_INTEGRITY** (LIVE): EXECUTED, PASS. 61 files admitted, read once each through the logged loader (declarations/dial1118-s1-v5/access.log) and each sha256 equal to its pin at the first logged read
- **S4 SHAPE** (LIVE): EXECUTED, REFUSE READER_NOT_LIVE. The declared reader has no body in the Compass yet (csv-curve-v1 and table-curve-v1 are live); the file cannot be read. Detail: reader 'npz-curve-v1'
- **S5 CENSUS** (LIVE): WITHHELD AFTER_REFUSAL (S4). Not run: an earlier stage refused, and no later check can redeem a refusal.
- **S6 ADMISSIBILITY** (LIVE): WITHHELD AFTER_REFUSAL (S4). Not run: an earlier stage refused, and no later check can redeem a refusal.
- **S7 INTERVAL_FEASIBILITY** (LIVE): WITHHELD AFTER_REFUSAL (S4). Not run: an earlier stage refused, and no later check can redeem a refusal.
- **S8 RESOLUTION_AND_IDENTIFIABILITY** (LIVE): WITHHELD AFTER_REFUSAL (S4). Not run: an earlier stage refused, and no later check can redeem a refusal.
- **S10 KERNEL_HANDOFF** (LIVE): WITHHELD AFTER_REFUSAL (S4). Not run: an earlier stage refused, and no later check can redeem a refusal.
- **S9 ALTERNATIVE_INTAKE** (LIVE): WITHHELD AFTER_REFUSAL (S4). Not run: an earlier stage refused, and no later check can redeem a refusal.

## What the seal proves

Sealing is recommended and not enforced. It records what you declared and when; it is an integrity practice, like a lab notebook. A seal proves INTEGRITY (the declaration's sha256) and ORDERING (the seal time against the first logged data read). It never proves ignorance: mode is the declarer's sealed statement of what they had seen.

## Reasons no body can return yet

Each row below has live = false in intake/STAGES.toml: no body returns it today (a STUB stage's rows are never live), so a run cannot show it and its absence says nothing.

- none: every row is live (plan 1160 P6)

## What no stage can see

- direct shell reads (cat, less, head, cp, rsync, scp) — not logged
- other processes / external tools (MATLAB, editors, a Python without this module, Jupyter) — not logged
- reads of another copy of the bytes (other host, backup, download cache) — not logged
- atime tripwire is weak: relatime/noatime mounts suppress updates; SILENT is not evidence of no read
