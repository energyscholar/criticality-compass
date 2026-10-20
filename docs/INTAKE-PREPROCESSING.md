# Intake pre-processing: profile the files before you declare them

Read this page first, before `peek`, before a conversion, before `intake.toml` (plan 1165). Pre-processing reads **every byte** of
every file under a path and writes a description of their structure, the PROFILE. You declare against the PROFILE, not against a
guess from the head of one file. The PROFILE holds no data value: counts, kinds, line numbers, file names, and column names with
every numeral masked as `#`. So you may profile a RESERVED set, and reading its PROFILE.md does not unblind it (for a RESERVED set,
profile the blinded view `<cc-blind>/<id>`, never the raw names).

## Where it sits

```
deposit (raw/)                                 the files as retrieved; never edited
  │
  ├─ bin/cc new intake <id>                                         declarations/<id>/, which the profile writes into
  ├─ bin/cc intake profile <id> <cc-datasets>/<name>/raw            PRE-PROCESSING: reads every byte, writes the PROFILE
  │       PROFILE.json, PROFILE.md, profile.log, profile-access.log in declarations/<id>/; ## Profile in <cc-datasets>/<name>/MANIFEST.md
  │
  ├─ (read PROFILE.md: each finding names its one response, the table below)
  │
  ├─ declarations/<id>/CONVERSION.toml → bin/cc intake convert <id>  when a response is a conversion op (docs/INTAKE-CONVERSION.md)
  │       bin/cc intake profile <id> <cc-banks>/<id>/bank             PRE-PROCESSING again, on the bank the run will read
  │
  ├─ declarations/<id>/intake.toml, transducer.toml                  the declaration, written against the profile
  │
  ├─ bin/cc intake profile <id> --check     the cross-check: declaration against profile, no byte read; exit 1 on any contradiction
  ├─ bin/cc intake lint <id>
  ├─ bin/cc intake seal <id> ...             the seal also records the profile's sha256 (and the conversion manifest's)
  └─ bin/cc intake run <id>                  S3 re-runs the cross-check against the pinned files; S4, S5 re-confirm
```

The path is root-named: `<cc-datasets>/<name>/raw`, `<cc-banks>/<id>/bank`, `<intake-synth>/<name>`, `<cc-blind>/<id>`. Any other
form (a bare or absolute path) is refused ROOT_UNRESOLVED. The profile writes nothing under the path it reads. Profiling again
overwrites PROFILE.json (it is derived) and appends one line to profile.log. A CONVERTED declaration's PROFILE.json is the profile of
the **bank**; `bin/cc intake profile <id> --raw <cc-datasets>/<name>/raw` keeps the deposit's profile beside it as PROFILE-raw.json.

## What the profile says, per file

- **name, bytes, sha256.** Every file, whatever its kind.
- **kind.** By content, never by extension: TEXT_TABLE (text that decodes), XLSX (a zip holding `xl/workbook.xml`), ZIP (another
  zip: its members by masked name and size), UNPROFILED_FORMAT (anything else: HDF5, .mat, .npz, TIFF; no reader exists for it).
- **encoding.** UTF8, UTF8_SIG (a byte-order mark), UTF16, LATIN1_ONLY (not UTF-8) for a text file; UNDECODABLE for an empty or binary file
  (UNPROFILED_FORMAT); NOT_APPLICABLE for a zip or an xlsx (their cells are read as a workbook or members, never decoded as text).
- **delimiter.** COMMA, SEMICOLON, TAB, WHITESPACE or NONE: the cut that gives the most lines the same width of two or more cells;
  ties go to that order. The widths under all four are printed beside it, so you see the alternative.
- **sheets.** XLSX only: each sheet by position and masked name, then profiled as a table.
- **lines, blank lines, comment lines.** Blank lines as ranges; lines beginning `#`, `%`, `;`, `//`, `!` or `[` counted by prefix.
- **rows: the block structure.** Every line is one of BLANK (no cell holds text), NUMERIC (every filled cell is a number), NUMERIC_WITH_EMPTY
  (and a cell is empty), TEXT (a filled cell is not a number: a names line, a title, an `n/a`, a units line, a mid-file header). The
  rows are runs of (kind, width): **a block boundary is a change of kind or width.** A text block in mid-file is a TEXT run between
  two NUMERIC runs; a ragged file is a NUMERIC run whose width differs from its neighbour's. Line numbers are 1-based, the numbers
  CONVERSION-MANIFEST.json and SPLIT_ROWS RANGES use.
- **header lines.** The lines before the first NUMERIC run (at most 12), masked as peek prints them. The names line is among them.
- **columns.** For each position of the dominant width: its masked name (`#k` for a numeric name), the counts of number, empty and
  text cells (with the lines of the text cells, never their text), how many monotone runs its numbers make and the direction of the
  first, its runs of equal consecutive values (by length: 2, 3-9, 10+, and the longest), how many values come back after another
  value intervened (revisited), and how many distinct values it holds.

PROFILE.md is the same facts for a reader, then the **Findings**: each finding's code, where it is (file, lines, column position),
and its one response.

## Finding → response

The response is computed by the table, not chosen. Where two responses are listed, the first is the one the profile prints; the
second prints as "or ...". A BLOCKS response names the lines; you copy them. The profile never writes CONVERSION.toml: which block is a
curve and which is a hold is your declaration, not the tool's.

Each finding says where (fix S11.P2b F4), value-free: its `ranges` (every [first, last] line range of its structure: each monotone
segment for NOT_MONOTONE, each equal run for EQUAL_RUNS_SHORT / EQUAL_RUN_LONG, each run of a value seen before for REVISITED_VALUES, the
lines utf-8 cannot read for ENCODING_NOT_UTF8), `lines` their span, and for COLUMNS_DIFFER_ACROSS_FILES the names line and `compared`, the
first table file of the path it differs from. PROFILE.md prints the first 12 ranges and "+N more in PROFILE.json".

| FindingKind | the structure that raises it | Response | predicts (the refusal the run would otherwise meet) |
|---|---|---|---|
| ENCODING_NOT_UTF8 | `encoding` LATIN1_ONLY or UTF16 | CONVERT(DECODE encoding = latin-1 / utf-16) | S4 NOT_UTF8; converter ENCODING_INVALID; r3 defect 7 |
| BOM_PRESENT | `encoding` UTF8_SIG | NONE (the readers and DECODE default strip it) | the BOM in a first name |
| DELIMITER_NOT_COMMA | `delimiter` SEMICOLON / TAB / WHITESPACE | CONVERT(DELIMITER from = …) or DECLARE(`[reader.format] kind` TAB / WHITESPACE) when the reader has it | S4 ROW_WIDTH_DIFFERS (a one-column file); COLUMN_NAME_ABSENT |
| NO_DELIMITER | `delimiter` NONE | REFUSE_DEPOSIT(NOT_A_TABLE) | NO_DATA_ROW |
| HEADER_LINES_BEFORE_NAMES | TEXT lines before the names line (the last TEXT line before the first NUMERIC run) | CONVERT(DROP_LINES MARKER / FIRST count = n) or DECLARE(`[reader.header] rows = n`) | HEADER_LINE_ABSENT; MARKER_LINE_ABSENT; D8 |
| NAMES_LINE_ABSENT | the first run is NUMERIC | CONVERT(NAMES_LINE WRITE names = …) | COLUMN_NAME_ABSENT |
| NAMES_LINE_NUMERIC | the last TEXT line before the body is all NUMERIC cells but one | CONVERT(WIDE_TO_LONG key = …) | COLUMN_NAME_ABSENT (F3) |
| COMMENT_LINES | lines with a comment prefix inside or around the body | DECLARE(`comment = [prefix]`) or CONVERT(DROP_LINES PREFIX) | CELL_NOT_A_NUMBER; ROW_WIDTH_DIFFERS |
| TEXT_RUN_IN_BODY | a TEXT run between two NUMERIC runs | **BLOCKS** (SPLIT_ROWS RANGES at the run's lines; each NUMERIC run its own output / curve) — or CONVERT(DROP_LINES PREFIX) when every line of the run shares a comment prefix | CELL_NOT_A_NUMBER on Z16/Z19; the r3 "text rows" |
| TEXT_RUN_TRAILING | a TEXT run after the last NUMERIC run | BLOCKS (RANGES ending at the last NUMERIC line) | CELL_NOT_A_NUMBER |
| TEXT_CELLS_IN_COLUMN | a column with `text > 0` inside NUMERIC-width runs (a `n/a` in one column, the row otherwise numeric) | DECLARE another column when another column has `text = 0`; else CONVERT(DROP_ROWS_NOT_NUMERIC) **pending §9 D2** | CELL_NOT_A_NUMBER |
| EMPTY_CELLS_IN_COLUMN | a column with `empty > 0` (NUMERIC_WITH_EMPTY rows) | CONVERT(DROP_ROWS_NOT_NUMERIC columns = [k]) (an empty cell is a reading not taken — the owner's n3: "a blank is not the same as zero") | CELL_NOT_A_NUMBER |
| WIDTH_CHANGES | NUMERIC runs of different widths in one file | BLOCKS when the widths bound blocks; CONVERT(SELECT_COLUMNS) when the extra columns are trailing empties (`empty = lines` for every column past the narrower width) | ROW_WIDTH_DIFFERS; r3 defect 12 (6 to 10 columns) |
| COLUMNS_DIFFER_ACROSS_FILES | the masked names lines of two files of the path differ, or their dominant widths differ | DECLARE(`[selection] files` per family) with CONVERT(SELECT_COLUMNS / RENAME) to one names line | S4 COLUMNS_DIFFER; S5 FILE_DIFFERS_FROM_FIRST (Z02); D8; r3 defect 8 |
| NOT_MONOTONE | a column with `monotone_runs > 1` | DECLARE(`[acquisition] row_order = ACQUISITION, direction = UNORDERED`) for a dithering knob; BLOCKS when the runs are sweeps (FAST_RESTART, or RANGES per run) | S4 ROW_ORDER_DIFFERS (Z04, Z13, Z20-32, both directions) |
| DIRECTION_DESCENDING | `monotone_runs = 1`, `first_direction` DESCENDING | DECLARE(`row_order = DESCENDING`) | ROW_ORDER_DIFFERS (opposite order) |
| EQUAL_RUNS_SHORT | `equal_runs[2] > 0` or `["3-9"] > 0`, `revisited = 0` | DECLARE(`[replicate] identity = SAME_FAST_VALUE`) (K1, K3) | S5 FAST_VALUE_REPEATED (Z04-r3, Z13-r3, Z16-r3b) |
| EQUAL_RUN_LONG | `longest ≥ 10` | BLOCKS (the hold is a segment: RANGES around it, or `excluded`) (K4) | FAST_VALUE_REPEATED (Z19-r3b) |
| REVISITED_VALUES | `revisited > 0` | DECLARE(`[knobs.fast] control = MEASURED`) (A17; K2) | FAST_VALUE_REPEATED; ROW_ORDER_DIFFERS |
| XLSX_SHEETS | `kind` XLSX with `sheets` | CONVERT(SHEET_TO_CSV sheet = <one of the masked names>) or DECLARE(`[reader.format] kind = XLSX, sheet = …`) | SHEET_REQUIRED; SHEET_ABSENT; D5 |
| ZIP_MEMBERS | `kind` ZIP | CONVERT(UNPACK member = …) per member | SOURCE_FILE_ABSENT; CONTAINER_UNREADABLE |
| UNPROFILED_FORMAT | `kind` UNPROFILED_FORMAT | REFUSE_DEPOSIT(NO_READER_FOR_FORMAT) — the alphabet has no op; the card's `reader_needed` says so | ROOT_UNRESOLVED-class dead ends; the HDF5/mat/NeXus sets of INDEX.md |
| LARGE_FILE | `lines ≥ 10 000` in a TEXT_TABLE | NONE — printed so the declarer expects the conversion's cost (Z19: tens of thousands of rows; DIAG item 2's fix is separate) | r3 defect 3 (28 min) |
| ONE_FILE | the path holds one TEXT_TABLE | DECLARE(`[selection] layout = LONG_TABLE`) with `slow` COLUMN from the column whose `distinct` is smallest and `equal_runs` longest | TOO_FEW_CURVES on a PER_FILE of one file |
| NOT_A_TABLE | a TEXT_TABLE file with no NUMERIC run (a README, a script, a CONVERSION-MANIFEST.json); it raises no DELIMITER / NO_DELIMITER / HEADER / COMMENT finding (those are of a table's head, and it has no body) | DECLARE(`[selection] files` without it: no numeric row, so no curve) | (fix S11.P2b F3; before it, such a file raised HEADER / COMMENT / DELIMITER noise) |

(The table is plan 1165 §4 verbatim. The owner ruled D2 on 2026-10-19: DROP_ROWS_NOT_NUMERIC stays for EMPTY cells and for a lone
TEXT cell in an otherwise numeric row; a TEXT **run** (whole rows of text, as a mid-file header) is a block boundary, and its response
is BLOCKS, never a row drop. The cross-check refuses a conversion that drops a TEXT run: see below.)

## The cross-check: `bin/cc intake profile <id> --check`

Run it after writing intake.toml and before lint. It reads no byte: it checks the declaration against PROFILE.json (and, for a
CONVERTED bank, against the bank's CONVERSION-MANIFEST.json) and prints every contradiction as `CODE file: where` (positions, counts,
masked names). Exit 0 with `0 contradictions`; exit 1 on any contradiction, on no PROFILE.json (PROFILE_ABSENT) or on a declaration that
does not pass FORMAT.

| Contradiction | holds when |
|---|---|
| FILE_NOT_PROFILED | a selected file is not in the profile |
| ENCODING_CONTRADICTS_PROFILE | a file is LATIN1_ONLY or UTF16 and no DECODE step converts it |
| DELIMITER_CONTRADICTS_PROFILE | the declared `[reader.format] kind` is not the delimiter the profile elects, and no DELIMITER step converts it |
| HEADER_CONTRADICTS_PROFILE | `[reader.header] rows` is not the count of lines before the first NUMERIC run |
| COLUMN_CONTRADICTS_PROFILE | a declared column name is not among the file's masked names, or is there twice; a declared position exceeds the width |
| CELLS_CONTRADICT_PROFILE | a declared column holds text or empty cells, or a TEXT run lies in the body, and no DROP_ROWS_NOT_NUMERIC covers it; or a DROP_ROWS_NOT_NUMERIC dropped a TEXT run (a row with no number cell: D2, BLOCKS) |
| WIDTH_CONTRADICTS_PROFILE | a body line's width differs from the names line's |
| ORDER_CONTRADICTS_PROFILE | PER_FILE, `row_order` ASCENDING / DESCENDING, and the fast column has more than one monotone run or the opposite first direction |
| REPEATS_CONTRADICT_PROFILE | PER_FILE, `control = SET`, identity not SAME_FAST_VALUE, and the fast column has equal runs or revisited values |
| SHEET_CONTRADICTS_PROFILE | a declared sheet is not among the workbook's sheets |
| FILES_CONTRADICT_PROFILE | PER_FILE, and the selected files' masked names lines are not all equal |

## What the run does with it (S3)

Every run's S3 checks, after the pins: **PROFILE_ABSENT** (no PROFILE.json: profile first), **PROFILE_STALE** (a pinned file is not
in the profile, or its bytes differ from the bytes profiled: profile again), **MANIFEST_STALE** (the bank's CONVERSION-MANIFEST.json
differs from the one the seal recorded), **PROFILE_CONTRADICTED** (the cross-check above finds a contradiction; the Detail names the
first and counts the rest). The report's **Profile** line says `PROFILED <sha> (n files, m findings, k contradictions)` or `NOT PROFILED`.
A refusal at S4 or S5 that the profile should have predicted ends its Detail with "the profile did not predict this": that is a hole
in the table, to be reported, not a declaration error.
