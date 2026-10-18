# Intake quickstart: synthetic data from the command line

Plan 1139. Run from the root of the Criticality Compass, with no environment variable set. Everything runs on this machine in seconds.
tests/test_intake_cli.py runs exactly the block below (test 5), with the edit step done by applying the filled example, so this page
cannot drift from what works.

```
bin/cc intake explain
bin/cc intake synth demo1 --seed 1
bin/cc new intake demo1 --from-synth demo1
#   edit declarations/demo1/intake.toml: replace each remaining TODO (the quickstart shows a filled example)
bin/cc intake lint demo1
bin/cc intake seal demo1 --universe scratch/intake-synth/demo1 --author "<name>" --as human --unconfirmed    # optional
bin/cc intake run demo1
cat declarations/demo1/intake-report.md
```

What each line does:

1. `explain` prints the stages, which of them are LIVE, and what each refusal means.
2. `synth` writes a planted bank of 9 curves to `scratch/intake-synth/demo1/` (gitignored) and the planted truth to
   `scratch/intake-synth/demo1-TRUTH/truth.json`, a sibling outside the bank that no stage reads.
3. `new intake --from-synth` writes `declarations/demo1/intake.toml` and `transducer.toml`. It fills what the bank's MANIFEST states
   as metadata and prints the TODO lines left. Those are the choices, and they are yours.
4. You replace each TODO. The method `iid` also needs its fields (cc.toml `[interval_fields.iid]`); lint names any that are missing.
5. `lint` runs the stages that read no data. It should pass FORMAT.
6. `seal` is optional. Sealing is recommended and not enforced. It records what you declared and when; it is an integrity practice, like a
   lab notebook. Write your own name for `<name>`.
7. `run` runs every stage. SOURCE_INTEGRITY, SHAPE and CENSUS read the bank through the logged loader. The other stages are STUBs, so the
   PRIMARY verdict is PRIMARY_INCOMPLETE and the report lists them.

## A filled example

These are the TODO lines of `declarations/demo1/intake.toml` and one choice for each, by section. The lines under `[interval]` after
`method` are added below it. Any other admissible choice is equally valid; this one is only an example.

```toml
[intake]
mode = "PROSPECTIVE"
[acquisition]
mode = "INDEPENDENT"
direction = "UNORDERED"
row_order = "ASCENDING"
[interval]
method = "iid"
resamples = 1000
level = 0.95
seed = 1139
tau_declared = 1
[bracket]
required = "CANDIDATE_BRACKET"
[[projection]]
lane = "PRIMARY"
from = "C"
to = "C_max"
bias = "MAX_MEASURED"
keeps = "the largest C on each curve"
discards = "every other point of the curve"
[[bridge]]
lane = "PRIMARY"
on = "C_max"
template = "CHAIN_SLOW"
bias = "CHAIN_SLOW"
[shift]
c = 0.0
```

## What to expect

- lint: `S0 EXECUTED, PASS` (FORMAT).
- run: S3 SOURCE_INTEGRITY, S4 SHAPE and S5 CENSUS `EXECUTED, PASS`. The census reads
  `Sampling: 9 curves; points per curve min 44, median 78, max 116; T span [1.5, 3.5]; MISALIGNED`.
- Seal status `SEALED`, or `UNSEALED` if you skipped the seal. If you edit the declaration after sealing, the status is `SEALED_THEN_EDITED`.
- `PRIMARY verdict: PRIMARY_INCOMPLETE`, listing the STUB stages it is missing.

To start again: `rm -r scratch/intake-synth/demo1 scratch/intake-synth/demo1-TRUTH declarations/demo1`.
