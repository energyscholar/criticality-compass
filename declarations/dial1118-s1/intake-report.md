# Intake report: dial1118-s1

Written by `bin/cc intake run dial1118-s1`. Stage table 1136-v1, policy 1136-v1.

- **Mode** (the declarer's sealed statement of what they had seen): EXPLORATORY
- **PRIMARY verdict: PRIMARY_INCOMPLETE**. Missing: S1 CHOICES, S3 SOURCE_INTEGRITY, S4 SHAPE, S5 CENSUS, S6 ADMISSIBILITY, S7 INTERVAL_FEASIBILITY, S8 RESOLUTION_AND_IDENTIFIABILITY, confirmation.
- **ROBUSTNESS verdict: ROBUSTNESS_INCOMPLETE**. Missing: S9 ALTERNATIVE_INTAKE.
- **S10 KERNEL_HANDOFF** (outside both verdicts): STUB.
- **confirmation**: No human has confirmed this declaration (confirmed_by is empty); PRIMARY_READY needs a non-empty confirmed_by.

| stage | name | state | reads data bytes | execution |
|---|---|---|---|---|
| S0 | FORMAT | LIVE | NONE | EXECUTED |
| S1 | CHOICES | STUB | NONE | STUB |
| S2 | SEAL | LIVE | NONE | EXECUTED |
| S3 | SOURCE_INTEGRITY | STUB | ALL_FILES | STUB |
| S4 | SHAPE | STUB | FIRST_FILE | STUB |
| S5 | CENSUS | STUB | ALL_FILES | STUB |
| S6 | ADMISSIBILITY | STUB | NONE | STUB |
| S7 | INTERVAL_FEASIBILITY | STUB | NONE | STUB |
| S8 | RESOLUTION_AND_IDENTIFIABILITY | STUB | NONE | STUB |
| S9 | ALTERNATIVE_INTAKE | STUB | NONE | STUB |
| S10 | KERNEL_HANDOFF | STUB | ALL_FILES | STUB |

- **S0 FORMAT** (LIVE): EXECUTED, PASS. The declaration 'dial1118-s1' parses, and every field of format v1 is present, typed and listed (mode EXPLORATORY)
- **S1 CHOICES** (STUB): STUB. This stage has no body yet, so nothing was checked; a stub is never a pass.
- **S2 SEAL** (LIVE): EXECUTED, PASS. Sealed at 2026-10-18T16:47:47Z (seal-log t_ns 1792342067119065918) by Claude (plan 1136 phase 1) (AI_DRAFT), confirmed_by '', mode EXPLORATORY; declaration sha256 d6f4186c418ddea67e21cab6808d23823221a6dd5bbd9dcf2436f80df340adc5; universe '<p1118-bank>' (located at a directory named 'p1118-bank-FIXTURE'): 63 files, names and sizes in SEAL.json
- **S3 SOURCE_INTEGRITY** (STUB): STUB. This stage has no body yet, so nothing was checked; a stub is never a pass.
- **S4 SHAPE** (STUB): STUB. This stage has no body yet, so nothing was checked; a stub is never a pass.
- **S5 CENSUS** (STUB): STUB. This stage has no body yet, so nothing was checked; a stub is never a pass.
- **S6 ADMISSIBILITY** (STUB): STUB. This stage has no body yet, so nothing was checked; a stub is never a pass.
- **S7 INTERVAL_FEASIBILITY** (STUB): STUB. This stage has no body yet, so nothing was checked; a stub is never a pass.
- **S8 RESOLUTION_AND_IDENTIFIABILITY** (STUB): STUB. This stage has no body yet, so nothing was checked; a stub is never a pass.
- **S9 ALTERNATIVE_INTAKE** (STUB): STUB. This stage has no body yet, so nothing was checked; a stub is never a pass.
- **S10 KERNEL_HANDOFF** (STUB): STUB. This stage has no body yet, so nothing was checked; a stub is never a pass.

## What the seal proves

The seal proves INTEGRITY (the declaration's sha256) and ORDERING (the seal time against the first logged data read). It never proves ignorance: mode is the declarer's sealed statement of what they had seen.

## What no stage can see

- direct shell reads (cat, less, head, cp, rsync, scp) — not logged
- other processes / external tools (MATLAB, editors, a Python without this module, Jupyter) — not logged
- reads of another copy of the bytes (other host, backup, download cache) — not logged
- atime tripwire is weak: relatime/noatime mounts suppress updates; SILENT is not evidence of no read
