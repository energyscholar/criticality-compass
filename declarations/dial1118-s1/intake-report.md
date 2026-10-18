# Intake report: dial1118-s1

Written by `bin/cc intake run dial1118-s1`. Stage table 1139-v1, policy 1136-v1.

- **Mode** (the declarer's sealed statement of what they had seen): EXPLORATORY
- **PRIMARY verdict: PRIMARY_REFUSED_AT** at S3. Missing: S1 CHOICES.
- **ROBUSTNESS verdict: ROBUSTNESS_WITHHELD**. Missing: none.
- **S10 KERNEL_HANDOFF** (outside both verdicts): WITHHELD.
- **Seal status** (advisory; sealing is recommended and not enforced): SEALED. A seal holds this declaration exactly as it is now. Sealed at 2026-10-18T16:47:47Z (seal-log t_ns 1792342067119065918) by Claude (plan 1136 phase 1) (AI_DRAFT), confirmed_by '', mode EXPLORATORY; declaration sha256 d6f4186c418ddea67e21cab6808d23823221a6dd5bbd9dcf2436f80df340adc5; universe '<p1118-bank>' (located at a directory named 'p1118-bank-FIXTURE'): 63 files, names and sizes in SEAL.json
- **Ordering** (information, never a refusal): NO_DATA_READ_LOGGED. The access log holds no data read of this declaration.

| stage | name | state | reads data bytes | execution |
|---|---|---|---|---|
| S0 | FORMAT | LIVE | NONE | EXECUTED |
| S1 | CHOICES | STUB | NONE | STUB |
| S2 | SEAL | LIVE | NONE | EXECUTED |
| S3 | SOURCE_INTEGRITY | LIVE | ALL_FILES | EXECUTED |
| S4 | SHAPE | LIVE | FIRST_FILE | WITHHELD |
| S5 | CENSUS | LIVE | ALL_FILES | WITHHELD |
| S6 | ADMISSIBILITY | STUB | NONE | WITHHELD |
| S7 | INTERVAL_FEASIBILITY | STUB | NONE | WITHHELD |
| S8 | RESOLUTION_AND_IDENTIFIABILITY | STUB | NONE | WITHHELD |
| S9 | ALTERNATIVE_INTAKE | STUB | NONE | WITHHELD |
| S10 | KERNEL_HANDOFF | STUB | ALL_FILES | WITHHELD |

- **S0 FORMAT** (LIVE): EXECUTED, PASS. The declaration 'dial1118-s1' parses, and every field of format v1 is present, typed and listed (mode EXPLORATORY)
- **S1 CHOICES** (STUB): STUB. This stage has no body yet, so nothing was checked; a stub is never a pass.
- **S2 SEAL** (LIVE): EXECUTED, PASS. SEALED. A seal holds this declaration exactly as it is now. Sealed at 2026-10-18T16:47:47Z (seal-log t_ns 1792342067119065918) by Claude (plan 1136 phase 1) (AI_DRAFT), confirmed_by '', mode EXPLORATORY; declaration sha256 d6f4186c418ddea67e21cab6808d23823221a6dd5bbd9dcf2436f80df340adc5; universe '<p1118-bank>' (located at a directory named 'p1118-bank-FIXTURE'): 63 files, names and sizes in SEAL.json
- **S3 SOURCE_INTEGRITY** (LIVE): EXECUTED, REFUSE ROOT_UNRESOLVED. The declared source root is not a name of intake/ROOTS.toml followed by a relative path, or it names no directory on this machine. Detail: root '<p1118-bank>' (names in intake/ROOTS.toml: ['<intake-synth>'])
- **S4 SHAPE** (LIVE): WITHHELD AFTER_REFUSAL (S3). Not run: an earlier stage refused, and no later check can redeem a refusal.
- **S5 CENSUS** (LIVE): WITHHELD AFTER_REFUSAL (S3). Not run: an earlier stage refused, and no later check can redeem a refusal.
- **S6 ADMISSIBILITY** (STUB): WITHHELD AFTER_REFUSAL (S3). Not run: an earlier stage refused, and no later check can redeem a refusal.
- **S7 INTERVAL_FEASIBILITY** (STUB): WITHHELD AFTER_REFUSAL (S3). Not run: an earlier stage refused, and no later check can redeem a refusal.
- **S8 RESOLUTION_AND_IDENTIFIABILITY** (STUB): WITHHELD AFTER_REFUSAL (S3). Not run: an earlier stage refused, and no later check can redeem a refusal.
- **S9 ALTERNATIVE_INTAKE** (STUB): WITHHELD AFTER_REFUSAL (S3). Not run: an earlier stage refused, and no later check can redeem a refusal.
- **S10 KERNEL_HANDOFF** (STUB): WITHHELD AFTER_REFUSAL (S3). Not run: an earlier stage refused, and no later check can redeem a refusal.

## What the seal proves

Sealing is recommended and not enforced. It records what you declared and when; it is an integrity practice, like a lab notebook. A seal proves INTEGRITY (the declaration's sha256) and ORDERING (the seal time against the first logged data read). It never proves ignorance: mode is the declarer's sealed statement of what they had seen.

## What no stage can see

- direct shell reads (cat, less, head, cp, rsync, scp) — not logged
- other processes / external tools (MATLAB, editors, a Python without this module, Jupyter) — not logged
- reads of another copy of the bytes (other host, backup, download cache) — not logged
- atime tripwire is weak: relatime/noatime mounts suppress updates; SILENT is not evidence of no read
