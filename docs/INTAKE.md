# The intake pipeline (stage table 1145-v1, policy 1136-v1)

Generated from intake/STAGES.toml and intake/POLICY.toml by `bin/cc intake explain` (docs/gen-intake.py); never edit it by hand.
This is the intake's explain. `bin/cc explain <input> <point>` is a different command: it explains one point of a measured input.

A declaration `declarations/<id>/` (intake.toml and the CC transducer.toml) goes through the stages below in order. Each stage is LIVE (it has a body) or a STUB (it has none, so nothing was checked; a stub is never a pass). An executed stage gives PASS or REFUSE with a named reason; after a refusal every later stage is WITHHELD.

- **PRIMARY** verdict, over the PRIMARY stages: PRIMARY_REFUSED_AT when one refused; else PRIMARY_INCOMPLETE when one is not executed or no seal with a non-empty confirmed_by holds the declaration now; else PRIMARY_READY.
- **ROBUSTNESS** verdict, over the ROBUSTNESS stage: ROBUSTNESS_COMPLETE, ROBUSTNESS_INCOMPLETE, ROBUSTNESS_REFUSED, or ROBUSTNESS_WITHHELD after a PRIMARY refusal.
- The HANDOFF stage is outside both verdicts.
- The ADVISORY stage (the seal) is outside every verdict. It never refuses: every report carries its seal status, SEALED, UNSEALED or SEALED_THEN_EDITED, and an ordering note.

**The seal.** Sealing is recommended and not enforced. It records what you declared and when; it is an integrity practice, like a lab notebook. A seal proves INTEGRITY (the declaration's sha256) and ORDERING (the seal time against the first logged data read). It never proves ignorance: mode is the declarer's sealed statement of what they had seen.

| id | name | state | reads data bytes | needs | verdict |
|---|---|---|---|---|---|
| S0 | FORMAT | LIVE | NONE | - | PRIMARY |
| S1 | CHOICES | STUB | NONE | S0 | PRIMARY |
| S2 | SEAL | LIVE | NONE | S0 | ADVISORY |
| S3 | SOURCE_INTEGRITY | LIVE | ALL_FILES | S0 | PRIMARY |
| S4 | SHAPE | LIVE | FIRST_FILE | S3 | PRIMARY |
| S5 | CENSUS | LIVE | ALL_FILES | S3, S4 | PRIMARY |
| S6 | ADMISSIBILITY | STUB | NONE | S5 | PRIMARY |
| S7 | INTERVAL_FEASIBILITY | STUB | NONE | S5 | PRIMARY |
| S8 | RESOLUTION_AND_IDENTIFIABILITY | STUB | NONE | S5 | PRIMARY |
| S9 | ALTERNATIVE_INTAKE | STUB | NONE | S5 | ROBUSTNESS |
| S10 | KERNEL_HANDOFF | STUB | ALL_FILES | S6, S7, S8 | HANDOFF |

## S0 FORMAT (LIVE)

The declaration parses, holds every required field with the right type, and every closed-list field holds a listed value.

| reason | what it means |
|---|---|
| TOML_INVALID | The declaration is not valid TOML; fix the syntax at the line shown. |
| SCHEMA_UNSUPPORTED | The file does not say schema = 2 and kind = "intake"; this tool reads intake format v2 only (a v1 declaration is history: restate it in v2 under a new id). |
| FIELD_MISSING | A required field is absent; every field of format v2 must be written, even when its honest value is a refusal value such as NONE_FITS. |
| FIELD_UNKNOWN | A field the format does not define is present; check its spelling against bin/cc intake explain. |
| FIELD_TYPE_WRONG | A field holds the wrong kind of value (for example text where a list is required). |
| VALUE_NOT_LISTED | A closed-list field holds a value its list does not name; use one of the listed values. |
| VALUE_STILL_TODO | A field still holds the template's TODO; declare it, or write the field's refusal value if nothing honest fits. |
| BIAS_KEY_UNDECLARED | A bias key is not a row of intake/POLICY.toml for this projection or bridge; free text is never a bias. |
| FIELD_IS_STAMPED | A field the seal writes (a time, a hash, the author, the source universe listing, the sampling label) is typed in the declaration; delete it, the seal stamps it. |
| FIELD_IS_DERIVED | A field that is derived from another (correlated, from acquisition.mode) is typed; delete it. |
| STEP_IS_INTERPOLATION | A projection or bridge forms a value between measured points; interpolation is not admissible in any form. |
| BRIDGE_NONE_FITS | The declaration says no bridge fits these data; this is an honest answer, and such an intake cannot be sealed. |
| BASIS_NOT_METADATA | The declaration lists a source read before sealing that is not metadata (data values, a figure, or analysis code); the choice was made after seeing values. |
| TRANSDUCER_FILE_REFUSED | The declaration's transducer.toml is refused by the CC transducer check; its findings are listed with their Next lines. |

## S1 CHOICES (STUB)

The declared choices are consistent with each other, and the declared operation graph uses only permitted operations (static admissibility).

| reason | what it means |
|---|---|
| KNOBS_SAME_QUANTITY | The slow and fast knob name the same quantity or column; the Compass needs two distinct knobs. |
| MEASURED_IS_A_KNOB | The measured number is one of the knobs. |
| SLOW_VALUES_NOT_ONE_PER_FILE | Slow-knob values are declared per file, but the list does not give exactly one value per selected file. |
| PROJECTION_REQUIRED | The raw observation is not one number per locus (a picture, positions, a series), and no projection to one number is declared before the bridge. |
| PROJECTION_ESTIMAND_MIXED | One projection names two estimands (for example a location and a height); declare one projection per estimand. |
| SECOND_LANE_MISSING | The source is real data and only one intake lane is declared; real data are taken in through two declared lanes (policy, intake/POLICY.toml). |
| LANES_IDENTICAL | The two declared lanes use the same projection and bridge; the alternative must differ. |
| REPLICATE_IS_SWEEP_NEIGHBOUR | Replicates are declared as adjacent points of one sweep; a replicate is a repeated preparation, never a neighbouring point. |
| OPERATION_NOT_PERMITTED | A declared step is not a permitted operation for its link of the chain (Raw, Projection, DerivedObservable, Bridge, KernelInput). |
| SHIFT_BEFORE_KERNEL_INPUT | A constant shift x + c is declared upstream of the kernel input; x + c applies only at the KernelInput boundary. |
| PROVENANCE_HAS_NO_KERNEL_ROUTE | The deposit's admissibility record (raw-admissibility.toml) gives the component carrying the measured number no kernel route. |
| MODE_CONTRADICTS_SOURCE | The declared mode is PROSPECTIVE, but the selected files already exist, or the source is a published set whose figures have been seen. |

## S2 SEAL (LIVE)

Report the seal status: whether a seal (time, author, mode, code and protocol identity, the source universe's names and sizes, and the declaration's hash; written by bin/cc intake seal) holds this declaration now. Advisory: it never refuses and blocks nothing.

| reason | what it means |
|---|---|
| ALREADY_SEALED | This declaration is already sealed; a seal is never replaced, so declare a new id. |
| UNIVERSE_ROOT_ABSENT | The declared source universe root was not given or is not a directory on this machine; give its location with --universe. |
| SELECTION_OUTSIDE_UNIVERSE | A selected file is not in the source universe listing. |

| seal status | what it means |
|---|---|
| SEALED | A seal holds this declaration exactly as it is now. |
| UNSEALED | This declaration has no seal. Sealing is recommended and not enforced: bin/cc intake seal <id>. |
| SEALED_THEN_EDITED | This declaration was sealed and has been edited since; the seal records an earlier text. Declare a new id to seal the new text. |

## S3 SOURCE_INTEGRITY (LIVE)

Each selected file is admitted before it is read, read once through the logged loader, and its sha256 is pinned at its first logged read; a re-run compares against the pin, and a sealed universe listing against the universe now.

| reason | what it means |
|---|---|
| ROOT_UNRESOLVED | The declared source root is not a name of intake/ROOTS.toml followed by a relative path, or it names no directory on this machine. |
| PATH_NOT_ADMITTED | The loader's admission refused this path before reading it (truth side of the deposit, the slow-knob source does not resolve, or the file is absent). |
| PIN_MISMATCH | The file's bytes do not match their pinned sha256; the data changed since they were pinned. |
| UNIVERSE_CHANGED | The source universe now lists files that differ from the sealed listing (added, removed, or resized). |

## S4 SHAPE (LIVE)

The first selected file has the declared columns or keys, units and axes, as its declared reader admits them.

| reason | what it means |
|---|---|
| READER_NOT_LIVE | The declared reader has no body in the Compass yet (csv-curve-v1 and table-curve-v1 are live); the file cannot be read. |
| READER_REFUSED | The declared reader refused the file; its own reason is shown. |
| COLUMNS_DIFFER | The file's columns or keys differ from the declared ones (count, names or order; the declared columns are fast, measured, the uncertainty column if declared, and the slow column of a long table). |
| UNIT_DIFFERS | The file states a unit that differs from the declared unit. |
| ROW_ORDER_DIFFERS | The rows of a curve are not stored in the declared order of the fast knob. |

## S5 CENSUS (LIVE)

Every selected file matches the first, and the sampling label is recorded: curves, points per curve, spacing, missingness, ordering and replicate identity.

| reason | what it means |
|---|---|
| FILE_DIFFERS_FROM_FIRST | A selected file's shape, columns or keys differ from the first file's. |
| CURVE_REPEATED | Two curves carry the same slow-knob value (two files; or, in a long table, two blocks that are not adjacent) and are not declared replicates. |
| FAST_VALUE_REPEATED | A curve holds two points at the same fast-knob value and they are not declared replicates. |
| REPLICATE_KEY_UNRESOLVED | The declared replicate identity cannot be read for a file or point. |
| ACQUISITION_ORDER_DIFFERS | A curve stored in acquisition order (row_order ACQUISITION) does not run in the declared direction along the fast knob. |

## S6 ADMISSIBILITY (STUB)

The actual lineage obeys the sealed operation graph: every value reached the intake through the logged loader and the declared projections only (dynamic admissibility).

| reason | what it means |
|---|---|
| READ_NOT_LOGGED | A record exists whose bytes have no loader line in the access log. |
| BYPASS_READ_LOGGED | The access log holds an in-process read of a data path that did not go through the loader. |
| LINEAGE_OFF_GRAPH | A value's lineage includes a step that the sealed operation graph does not declare. |

## S7 INTERVAL_FEASIBILITY (STUB)

The sampling admits the declared interval method's floor at every point, for every method (the iid gap, plan 1134).

| reason | what it means |
|---|---|
| ONE_READING_PER_POINT | Each point holds one reading (a continuous ramp); there is nothing to put an interval on. |
| BELOW_METHOD_FLOOR | Some point holds fewer samples than the declared interval method's floor requires; the Next line names the routes. |
| METHOD_HAS_NO_FLOOR | The declared interval method has no floor in CC yet; an interval method without a floor is not admitted. |

## S8 RESOLUTION_AND_IDENTIFIABILITY (STUB)

The census makes the declared lanes feasible to attempt, and the evidence records what the available observables can and cannot identify.

| reason | what it means |
|---|---|
| TOO_FEW_CURVES | Fewer than three slow-knob values: no interior node exists, so no bracket can be formed. |
| TOO_FEW_POINTS_IN_CURVE | A curve holds fewer than three fast-knob points: no interior maximum can be formed on it. |
| NO_COVERAGE_EVIDENCE | The declaration requires a validated bracket ([bracket] required = "VALIDATED_BRACKET"), and no frozen planted coverage evidence exists for this lane at this density. |

## S9 ALTERNATIVE_INTAKE (STUB)

The second declared lane passes the same census-level checks as the first, so that both lanes can be run; concordance is measured later, from values.

| reason | what it means |
|---|---|
| SECOND_LANE_INFEASIBLE | The census does not support the second lane (for example a pairing finds no neighbouring point). |

## S10 KERNEL_HANDOFF (STUB)

Mint the kernel input (NodeField and Relations) through the provenance route and the door, applying x + c only here.

| reason | what it means |
|---|---|
| NO_KERNEL_ROUTE | A column's provenance class and evidence have no kernel route. |
| DOOR_REFUSED | The door refused the declared relations or values (cycle, endpoint, missing provenance, a non-finite value). |

## Policy (POLICY, 1136-v1)

The plan 1118 banks were used to CHOOSE these rows; they cannot validate them (A1.10). Validation needs fresh held-out planted banks.

- projection **ARGMAX_FAST**: estimand = location of the curve's maximum along the fast knob (a measured fast-knob value, never between points); measured_by = plan 1118 (PAIR's T*), choosing banks only; cannot = place the maximum between measured points; tell a critical POINT from a LINE; depends_on = the fast-knob density of each curve near its peak; fails_when = a curve's grid misses its own peak
- projection **MAX_MEASURED**: estimand = height of the curve's maximum measured value; measured_by = plan 1118 (REDUCE's r_k), choosing banks only; cannot = tell a critical POINT from a LINE; correct for a grid that misses the peak (the height is biased low); depends_on = where the points sit around each curve's peak; fails_when = neighbouring curves' differences are inside the noise width
- bridge **CHAIN_SLOW**: relation = consecutive curves in slow-knob order; measured_by = plan 1118 (REDUCE path), choosing banks only; cannot = relate non-adjacent curves; depends_on = slow-knob spacing; fails_when = the maximum is at either end of the path
- bridge **PAIR_NEAREST_FAST**: relation = per adjacent curve pair, the measured fast-knob point on the neighbour nearest to each curve's argmax (ties to the lower value); measured_by = plan 1118 (PAIR), choosing banks only; cannot = compare points at equal fast-knob values when the grids are misaligned; depends_on = per-curve grid alignment; fails_when = the ridge moves between neighbouring curves by more than the grid step
- policy: real_data_lanes = 2; primary_projection = MAX_MEASURED

## What no stage can see

- direct shell reads (cat, less, head, cp, rsync, scp) — not logged
- other processes / external tools (MATLAB, editors, a Python without this module, Jupyter) — not logged
- reads of another copy of the bytes (other host, backup, download cache) — not logged
- atime tripwire is weak: relatime/noatime mounts suppress updates; SILENT is not evidence of no read
