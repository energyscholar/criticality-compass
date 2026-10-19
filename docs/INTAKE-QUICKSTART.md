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
4. You replace each TODO. The example's interval method is `STATED`: the bank's `sigma` column is each point's interval, since the bank
   holds one reading per point (plan 1160 P5: a resampling method such as `iid` or `block` needs more, and S7 refuses it with
   ONE_READING_PER_POINT). A resampling method also needs its fields (cc.toml `[interval_fields.<method>]`); lint names any that are missing.
5. `lint` runs the stages that read no data. It should pass FORMAT and CHOICES. CHOICES checks the choices against each other: two distinct
   knobs and a measured number that is neither, a selection that names a file with one slow value per file, a direction for a FAST_RESTART
   block, the projections and bridges (a permitted step at each link, one estimand per projection, the lanes the source needs and lanes that
   differ), replicates that are not neighbouring points, a source class with a kernel route, and an uncertainty column for interval method
   STATED. `bin/cc intake explain` lists every row. The mode `RETROSPECTIVE_PREDECLARED` below says the files exist and you declare before
   looking at their values; `PROSPECTIVE` (no file exists yet) cannot be sealed over files that exist (MODE_CONTRADICTS_SOURCE).
6. `seal` is optional. Sealing is recommended and not enforced. It records what you declared and when; it is an integrity practice, like a
   lab notebook. Write your own name for `<name>`.
7. `run` runs every stage. SOURCE_INTEGRITY, SHAPE and CENSUS read the bank through the logged loader. ADMISSIBILITY then checks the
   access log: every file read has a loader line with its sha256, and no in-process read went around the loader. Then (plan 1160 P5)
   INTERVAL_FEASIBILITY checks the interval method against the readings per point, RESOLUTION_AND_IDENTIFIABILITY counts the curves and the
   points per curve and states the bracket the census permits, and ALTERNATIVE_INTAKE checks a second lane when one is declared. Last,
   (plan 1160 P6) KERNEL_HANDOFF, the terminal, brackets the maximum over the chain of curves and writes `declarations/demo1/RESULT.json`;
   docs/INTAKE-COMPLETION.md says what its result means.

## A filled example

These are the TODO lines of `declarations/demo1/intake.toml` and one choice for each, by section. A resampling method's fields
would go under `[interval]` after `method`; `STATED` has none. Any other admissible choice is equally valid; this one is only an example.

```toml
[intake]
mode = "RETROSPECTIVE_PREDECLARED"
[source]
admissibility = "RAW"
[acquisition]
mode = "INDEPENDENT"
direction = "UNORDERED"
row_order = "ASCENDING"
[interval]
method = "STATED"
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

- lint: `S0 EXECUTED, PASS` (FORMAT) and `S1 EXECUTED, PASS` (CHOICES).
- run: S3 SOURCE_INTEGRITY, S4 SHAPE, S5 CENSUS and S6 ADMISSIBILITY `EXECUTED, PASS` (S6 reads `ADMITTED_ON_LOGGED_PATHS_ONLY` and lists what it cannot see). The census reads
  `Sampling: 9 curves; points per curve min 44, median 78, max 116; 159 distinct T values; MISALIGNED; curves_with_slow = 9; readings per point min 1, max 1; distinct_slow_in_block max = 1`, and the report's
  `## Census` section lists the nine curves by ordinal and file name. No report prints a data value (a span, a slow value or a cell).
- S7 INTERVAL_FEASIBILITY, S8 RESOLUTION_AND_IDENTIFIABILITY and S9 ALTERNATIVE_INTAKE `EXECUTED, PASS`: tiering `STATED`, max_bracket
  `CANDIDATE_BRACKET`, identifiability `TRANSITION_TOPOLOGY_NOT_IDENTIFIABLE_FROM_AVAILABLE_OBSERVABLES`, and no ALTERNATIVE lane to check.
- Seal status `SEALED`, or `UNSEALED` if you skipped the seal. If you edit the declaration after sealing, the status is `SEALED_THEN_EDITED`.
- S10 KERNEL_HANDOFF `EXECUTED, PASS`: `Located, span ranks 4..6 (maximum at rank 5), tier RESOLVED, n_tied 1 of 9 curves`, and the
  identifiability value. The report prints ranks only; `declarations/demo1/RESULT.json` holds the slow values of the span, and says why
  RESOLVED here is no coverage claim (CANDIDATE_BRACKET).
- `PRIMARY verdict: PRIMARY_INCOMPLETE`, missing only `confirmation`: every PRIMARY stage and the terminal passed, and the seal is not
  confirmed. RESULT.json is written with `confirmation = UNCONFIRMED`. To reach `PRIMARY_READY`, a human confirms the seal: see
  "From INCOMPLETE to READY" in docs/INTAKE-COMPLETION.md.

To start again: `rm -r scratch/intake-synth/demo1 scratch/intake-synth/demo1-TRUTH declarations/demo1`.
