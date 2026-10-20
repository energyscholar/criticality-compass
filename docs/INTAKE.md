# The intake pipeline (stage table 1160-v10, policy 1136-v1)

Generated from intake/STAGES.toml and intake/POLICY.toml by `bin/cc intake explain` (docs/gen-intake.py); never edit it by hand.
This is the intake's explain. `bin/cc explain <input> <point>` is a different command: it explains one point of a measured input.

A declaration `declarations/<id>/` (intake.toml and the CC transducer.toml) goes through the stages below in order. Each stage is LIVE (it has a body) or a STUB (it has none, so nothing was checked; a stub is never a pass). An executed stage gives PASS or REFUSE with a named reason; after a refusal every later stage is WITHHELD.

- **PRIMARY** verdict, over the PRIMARY stages and the HANDOFF stage (the terminal): PRIMARY_REFUSED_AT when one refused; else PRIMARY_INCOMPLETE when one is not executed or no seal with a non-empty confirmed_by holds the declaration now; else PRIMARY_READY.
- **ROBUSTNESS** verdict, over the ROBUSTNESS stage: ROBUSTNESS_COMPLETE (it passed with two lanes declared), ROBUSTNESS_NOT_EXAMINED (it passed with one lane declared: nothing was examined), ROBUSTNESS_INCOMPLETE, ROBUSTNESS_REFUSED, or ROBUSTNESS_WITHHELD after a PRIMARY refusal.
- The HANDOFF stage is the terminal (docs/INTAKE-COMPLETION.md): PRIMARY_READY needs it executed. It runs before the ROBUSTNESS stage, so a ROBUSTNESS refusal never withholds it (plan 1160 A9).
- The ADVISORY stage (the seal) is outside every verdict. It never refuses: every report carries its seal status, SEALED, UNSEALED or SEALED_THEN_EDITED, and an ordering note.

**The seal.** Sealing is recommended and not enforced. It records what you declared and when; it is an integrity practice, like a lab notebook. A seal proves INTEGRITY (the declaration's sha256) and ORDERING (the seal time against the first logged data read). It never proves ignorance: mode is the declarer's sealed statement of what they had seen.

| id | name | state | reads data bytes | needs | verdict |
|---|---|---|---|---|---|
| S0 | FORMAT | LIVE | NONE | - | PRIMARY |
| S1 | CHOICES | LIVE | NONE | S0 | PRIMARY |
| S2 | SEAL | LIVE | NONE | S0 | ADVISORY |
| S3 | SOURCE_INTEGRITY | LIVE | ALL_FILES | S0 | PRIMARY |
| S4 | SHAPE | LIVE | FIRST_FILE | S3 | PRIMARY |
| S5 | CENSUS | LIVE | ALL_FILES | S3, S4 | PRIMARY |
| S6 | ADMISSIBILITY | LIVE | NONE | S5 | PRIMARY |
| S7 | INTERVAL_FEASIBILITY | LIVE | NONE | S5 | PRIMARY |
| S8 | RESOLUTION_AND_IDENTIFIABILITY | LIVE | NONE | S5 | PRIMARY |
| S10 | KERNEL_HANDOFF | LIVE | ALL_FILES | S6, S7, S8 | HANDOFF |
| S9 | ALTERNATIVE_INTAKE | LIVE | ALL_FILES | S5 | ROBUSTNESS |

## S0 FORMAT (LIVE)

The declaration parses, holds every required field with the right type, and every closed-list field holds a listed value.

| reason | live | what it means |
|---|---|---|
| DECLARATION_FILE_ABSENT | live | declarations/<id>/ holds no intake.toml, and a directory alone declares nothing; write the file (docs/INTAKE-QUICKSTART.md starts one with bin/cc new intake). |
| TOML_INVALID | live | The declaration is not valid TOML; fix the syntax at the line shown. |
| SCHEMA_UNSUPPORTED | live | The file does not say schema = 5 and kind = "intake"; this tool reads intake format v5 only (a v1, v2, v3 or v4 declaration is history: restate it in v5 under a new id; v4 to v5 adds [knobs.slow] kind = "QUANTITY", the v4 meaning, and writes the v4 [replicate] key = "" as [replicate.key] kind = "NONE"; v3 to v4 added [knobs.fast] control = "SET", the v3 meaning). |
| FIELD_MISSING | live | A required field is absent; every field of format v5 must be written, even when its honest value is a refusal value such as NONE_FITS. |
| FIELD_UNKNOWN | live | A field the format does not define is present; check its spelling against bin/cc intake explain. |
| FIELD_TYPE_WRONG | live | A field holds the wrong kind of value (for example text where a list is required). |
| VALUE_NOT_LISTED | live | A closed-list field holds a value its list does not name; use one of the listed values. |
| VALUE_STILL_TODO | live | A field still holds the template's TODO; declare it, or write the field's refusal value if nothing honest fits. |
| BIAS_KEY_UNDECLARED | live | A bias key is not a row of intake/POLICY.toml for this projection or bridge; free text is never a bias. |
| FIELD_IS_STAMPED | live | A field the seal writes (a time, a hash, the author, the source universe listing, the sampling label) is typed in the declaration; delete it, the seal stamps it. |
| FIELD_IS_DERIVED | live | A field that is derived from another (correlated, from acquisition.mode) is typed; delete it. |
| STEP_IS_INTERPOLATION | live | A projection or bridge forms a value between measured points; interpolation is not admissible in any form. |
| BRIDGE_NONE_FITS | live | The declaration says no bridge fits these data; this is an honest answer, and such an intake cannot be sealed. |
| BASIS_NOT_METADATA | live | The declaration lists a source read before sealing that is not metadata (data values, a figure, or analysis code); the choice was made after seeing values. |
| ROOT_NOT_UNDER_CC_BANKS | live | A CONVERTED source's root is not under <cc-banks>/: a converted bank is written there by its declared conversion, never beside the deposit. |
| COMMENT_PREFIX_EMPTY | live | A reader's comment list holds an empty prefix ""; every line starts with it, so every line would be dropped as a comment. Use [] for no comment lines. |
| TRANSDUCER_FILE_REFUSED | live | The declaration's transducer.toml is refused by the CC transducer check; its findings are listed with their Next lines. |

## S1 CHOICES (LIVE)

The declared choices are consistent with each other, and the declared operation graph uses only permitted operations (static admissibility).

| reason | live | what it means |
|---|---|---|
| KNOBS_SAME_QUANTITY | live | The slow and fast knob name the same quantity or column; the Compass needs two distinct knobs. |
| MEASURED_IS_A_KNOB | live | The measured number is one of the knobs. |
| SELECTION_EMPTY | live | The selection names no file (`files = []`); a census needs at least one curve file. |
| SLOW_VALUES_NOT_ONE_PER_FILE | live | Slow-knob values are declared per file (LISTED), but `values` does not give exactly one value per file of `files`. |
| SLOW_NONE_HAS_NO_PATH | live | The slow knob is declared NONE ([selection.slow] source NONE): no curve carries a slow value, so S8 would refuse TOO_FEW_CURVES and no declaration of any layout reaches S10. Declare the slow knob (LISTED, FILE_KEY or COLUMN), or report the deposit as one with no slow knob. |
| SLOW_KNOB_HAS_NO_METRIC | live | The slow knob is declared ORDINAL ([knobs.slow] kind ORDINAL): an index or a category (a run number, a cycle index, a sample label) has no metric, so no distance between two slow values, and a bracket on it would be a bracket on the order the curves were numbered in. Declare the physical quantity the curves differ by as the slow knob (QUANTITY), or report the deposit as one with no slow quantity. |
| BLOCK_RULE_HAS_NO_DIRECTION | live | A LONG_TABLE declares block FAST_RESTART, but the fast knob has no declared direction (row_order ACQUISITION with direction UNORDERED), so no restart of a sweep can be seen. |
| PROJECTION_REQUIRED | live | The raw observation is not one number per locus (a picture, positions, a series), and a bridge takes it with no projection to one number before it. |
| PROJECTION_ESTIMAND_MIXED | live | One projection names two estimands (for example a location and a height); declare one projection per estimand. |
| SECOND_LANE_MISSING | live | The source is real data and only one intake lane is declared; real data are taken in through two declared lanes (policy, intake/POLICY.toml). |
| LANES_IDENTICAL | live | The two declared lanes use the same projection and bridge; the alternative must differ. |
| REPLICATE_IS_SWEEP_NEIGHBOUR | live | Replicates are declared as adjacent points of one sweep (the replicate key is the fast knob); a replicate is a repeated preparation, never a neighbouring point. |
| MEASURED_KNOB_HAS_NO_POINTS | live | The fast knob is measured, not set, so its rows are not readings of grid points: declare replicate identity NONE and an interval method STATED or NONE. |
| OPERATION_NOT_PERMITTED | live | A declared step is not a permitted operation for its link of the chain (Raw, Projection, DerivedObservable, Bridge, KernelInput). |
| PROVENANCE_HAS_NO_KERNEL_ROUTE | live | The source's admissibility ([source] admissibility, the deposit's class as the declarer read it from metadata) is FIGURE_LEVEL or PROCESSED_UNDECLARABLE, which has no kernel route. |
| METHOD_NEEDS_UNCERTAINTY_COLUMN | live | The interval method is STATED (each point's interval is the declared uncertainty column), and [measured.uncertainty] declares none (kind NONE). |

## S2 SEAL (LIVE)

Report the seal status: whether a seal (time, author, mode, code and protocol identity, the source universe's names and sizes, and the declaration's hash; written by bin/cc intake seal) holds this declaration now. Advisory: it never refuses and blocks nothing.

| reason | live | what it means |
|---|---|---|
| ALREADY_SEALED | live | This declaration is already sealed; a seal is never replaced, so declare a new id. |
| UNIVERSE_ROOT_ABSENT | live | The declared [source] root names no directory on this machine (a name of intake/ROOTS.toml, then a path under it); the seal lists the universe there, so name it in the root. |
| SELECTION_DUPLICATE | live | A file name is given more than once in `files` (or in `excluded`); each file is one curve, named once. |
| MODE_CONTRADICTS_SOURCE | live | The declared mode is PROSPECTIVE, but a selected file is already in the source universe listing at the seal (plan 1160 P4: moved here from S1, which sees no listing). |
| SELECTION_OUTSIDE_UNIVERSE | live | A selected file is not in the source universe listing. |
| UNIVERSE_NOT_PARTITIONED | live | The universe is not exactly the selected files, the excluded files and the truth side, each file in one part: a file is in none or in two, an excluded file is not in the universe, or an excluded entry has no why. |

| seal status | what it means |
|---|---|
| SEALED | A seal holds this declaration exactly as it is now. |
| UNSEALED | This declaration has no seal. Sealing is recommended and not enforced: bin/cc intake seal <id>. |
| SEALED_THEN_EDITED | This declaration was sealed and has been edited since; the seal records an earlier text. Declare a new id to seal the new text. |

## S3 SOURCE_INTEGRITY (LIVE)

Each selected file is admitted before it is read, read once through the logged loader, and its sha256 is pinned at its first logged read; a re-run compares against the pin, and a sealed universe listing against the universe now.

| reason | live | what it means |
|---|---|---|
| CONVERSION_CHAIN_BROKEN | live | The source is CONVERTED, and its bank is not what `bin/cc intake convert` wrote from converted_from: the bank has no CONVERSION-MANIFEST.json, a raw or bank file's sha256 is not the manifest's, or the identity test fails on those bytes (plan 1160 P3). |
| ROOT_UNRESOLVED | live | The declared source root is not a name of intake/ROOTS.toml followed by a relative path, or it names no directory on this machine. |
| PATH_OUTSIDE_ROOT | live | A selected name resolves outside the source root (a .. part or a link); the loader reads nothing outside the root. |
| PATH_ON_TRUTH_SIDE | live | A selected name has a path part on the truth side of the deposit ([source] truth_side); no stage reads the truth. |
| PATH_NOT_A_FILE | live | A selected name is not a file under the source root (absent, or a directory); nothing was read. |
| PIN_MISMATCH | live | The file's bytes do not match their pinned sha256; the data changed since they were pinned. |
| UNIVERSE_CHANGED | live | The source universe now lists files that differ from the sealed listing (added, removed, or resized). |

## S4 SHAPE (LIVE)

The first selected file has the declared columns or keys, units and axes, as its declared reader admits them.

| reason | live | what it means |
|---|---|---|
| READER_NOT_LIVE | live | The declared reader has no body in the Compass yet (csv-curve-v1 and table-curve-v1 are live); the file cannot be read. |
| READER_REFUSED | live | The declared reader refused the file; its own reason is shown. |
| COLUMNS_DIFFER | live | The file's columns or keys differ from the declared ones (count, names or order; the declared columns are fast, measured, the uncertainty column if declared, and the slow column of a long table). |
| UNIT_DIFFERS | live | The file states a unit that differs from the declared unit. |
| ROW_ORDER_DIFFERS | live | The rows of a curve are not stored in the declared order of the fast knob. |

| reader reason (READER_REFUSED) | live | what it means |
|---|---|---|
| NOT_UTF8 | live | A text file's bytes are not UTF-8. |
| HEADER_LINE_ABSENT | live | The file holds fewer header lines than declared, or the declared names or units line is not among them. |
| NO_DATA_ROW | live | After the header the file holds no data row. |
| ROW_WIDTH_DIFFERS | live | A data row holds another number of cells than the names line (or the first data row); its row is shown. |
| COLUMN_NAME_ABSENT | live | A column declared by name is not in the names line (or the header declares no names line). |
| COLUMN_NAME_AMBIGUOUS | live | A column declared by name names two or more columns of the names line. |
| COLUMN_POSITION_OUT_OF_RANGE | live | A column declared by 1-based position is not a column of the table. |
| CELL_NOT_A_NUMBER | live | A cell of a declared column is not a number as written (an empty cell, nan and text are not numbers); its row and column are shown. |
| XLSX_READER_ABSENT | live | The file is declared xlsx and openpyxl is not installed on this machine, so it cannot be read here. |
| NOT_AN_XLSX | live | The file is declared xlsx and its bytes are not a workbook openpyxl can open. |
| SHEET_ABSENT | live | The declared sheet is not a sheet of the workbook. |

## S5 CENSUS (LIVE)

Every selected file matches the first, and the sampling label is recorded: curves, points per curve, spacing, missingness, ordering and replicate identity.

| reason | live | what it means |
|---|---|---|
| FILE_DIFFERS_FROM_FIRST | live | A selected file's shape, columns or keys differ from the first file's. |
| CURVE_REPEATED | live | Two curves carry the same slow-knob value (two files; or, in a long table, two blocks that are not adjacent) and are not declared replicates. |
| FAST_VALUE_REPEATED | live | A curve holds two points at the same fast-knob value and they are not declared replicates. Its detail counts the repeats: consecutive runs (one value on adjacent rows) are readings of one point if the knob was set (replicate identity SAME_FAST_VALUE); a value revisited after the knob left it is a measured knob (declare [knobs.fast] control = "MEASURED") or, for a set knob, a loop of two branches (convert with SPLIT_ROWS, one branch per file). |
| SLOW_KEY_UNRESOLVED | live | The slow knob is declared FILE_KEY, and a file's header does not hold exactly one line whose first cell is the key and whose second cell is a number. |
| REPLICATE_KEY_UNRESOLVED | live | The declared replicate identity cannot be read for a file or point. |
| ACQUISITION_ORDER_DIFFERS | live | A curve stored in acquisition order (row_order ACQUISITION) does not run in the declared direction along the fast knob. |

## S6 ADMISSIBILITY (LIVE)

The actual lineage obeys the sealed operation graph: every value reached the intake through the logged loader and the declared projections only (dynamic admissibility).

| reason | live | what it means |
|---|---|---|
| READ_NOT_LOGGED | live | A record exists whose bytes have no loader line in the access log. |
| BYPASS_READ_LOGGED | live | The access log holds an in-process read of a data path that did not go through the loader. |

## S7 INTERVAL_FEASIBILITY (LIVE)

The sampling admits the declared interval method's floor at every point, for every method (the iid gap, plan 1134).

| reason | live | what it means |
|---|---|---|
| ONE_READING_PER_POINT | live | Each point holds one reading (a continuous ramp); there is nothing to put an interval on. |
| BELOW_METHOD_FLOOR | live | Some point holds fewer samples than the declared interval method's floor requires; the Next line names the routes. |
| METHOD_HAS_NO_FLOOR | live | The declared interval method has no floor in CC yet; an interval method without a floor is not admitted. |

## S8 RESOLUTION_AND_IDENTIFIABILITY (LIVE)

The census makes the declared lanes feasible to attempt, and the evidence records what the available observables can and cannot identify.

| reason | live | what it means |
|---|---|---|
| TOO_FEW_CURVES | live | Fewer than three slow-knob values: no interior node exists, so no bracket can be formed. |
| TOO_FEW_POINTS_IN_CURVE | live | A curve holds fewer than three fast-knob points: no interior maximum can be formed on it. |
| NO_COVERAGE_EVIDENCE | live | The declaration requires a validated bracket ([bracket] required = "VALIDATED_BRACKET"), and no frozen planted coverage evidence exists for this lane at this density (none exists under intake/coverage/PRIMARY/ yet, so this always refuses today: declare CANDIDATE_BRACKET). |

## S10 KERNEL_HANDOFF (LIVE)

Mint the kernel input (NodeField and Relations) through the provenance route and the door, applying x + c only here.

| reason | live | what it means |
|---|---|---|
| NO_KERNEL_ROUTE | live | The PRIMARY lane has no bridge, or a PRIMARY bridge's template has no door template in CC (PAIR_NEAREST_FAST, plan 1118's PAIR, is not yet one), so no value reaches the kernel. |
| DOOR_REFUSED | live | The door refused a value of the kernel input: a curve's value at its maximum (after x + c) or its sigma is not finite (door.nodefield's Null). The chain relation itself cannot be refused: it is acyclic by construction. |

## S9 ALTERNATIVE_INTAKE (LIVE)

The second declared lane passes the same census-level checks as the first, so that both lanes can be run; concordance is measured later, from values.

| reason | live | what it means |
|---|---|---|
| SECOND_LANE_INFEASIBLE | live | The census does not support the second lane: its projection ARGMAX_FAST finds a curve's maximum at a fast end, or its bridge PAIR_NEAREST_FAST finds a curve's anchor outside a slow neighbour's fast span. |

## Policy (POLICY, 1136-v1)

The plan 1118 banks were used to CHOOSE these rows; they cannot validate them (A1.10). Validation needs fresh held-out planted banks.

- projection **ARGMAX_FAST**: estimand = location of the curve's maximum along the fast knob (a measured fast-knob value, never between points); measured_by = plan 1118 (PAIR's T*), choosing banks only; cannot = place the maximum between measured points; tell a critical POINT from a LINE; depends_on = the fast-knob density of each curve near its peak; fails_when = a curve's grid misses its own peak
- projection **MAX_MEASURED**: estimand = height of the curve's maximum measured value; measured_by = plan 1118 (REDUCE's r_k), choosing banks only; cannot = tell a critical POINT from a LINE; correct for a grid that misses the peak (the height is biased low); depends_on = where the points sit around each curve's peak; fails_when = neighbouring curves' differences are inside the noise width
- bridge **CHAIN_SLOW**: relation = consecutive curves in slow-knob order; measured_by = plan 1118 (REDUCE path), choosing banks only; cannot = relate non-adjacent curves; depends_on = slow-knob spacing; fails_when = the maximum is at either end of the path
- bridge **PAIR_NEAREST_FAST**: relation = per adjacent curve pair, the measured fast-knob point on the neighbour nearest to each curve's argmax (ties to the lower value); measured_by = plan 1118 (PAIR), choosing banks only; cannot = compare points at equal fast-knob values when the grids are misaligned; depends_on = per-curve grid alignment; fails_when = the ridge moves between neighbouring curves by more than the grid step
- policy: real_data_lanes = 2; primary_projection = MAX_MEASURED; tier_z = 2.0

## Reasons no body can return yet

Each row below has live = false in intake/STAGES.toml: no body returns it today (a STUB stage's rows are never live), so a run cannot show it and its absence says nothing.

- none: every row is live (plan 1160 P6)

## What no stage can see

- direct shell reads (cat, less, head, cp, rsync, scp) — not logged
- other processes / external tools (MATLAB, editors, a Python without this module, Jupyter) — not logged
- reads of another copy of the bytes (other host, backup, download cache) — not logged
- atime tripwire is weak: relatime/noatime mounts suppress updates; SILENT is not evidence of no read
