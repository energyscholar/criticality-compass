# Intake conversion: from a deposit to a bank the intake can read

Plan 1160 P3. This page is for whoever turns a deposited data set into a bank the strict intake reads. It assumes you know nothing else
about the Compass. Read the rule first, then the steps, then the op you need.

**The rule: a conversion is not allowed to change a number; if your deposit needs one changed, the Compass cannot take it.**

A conversion moves cells. It drops header lines, cuts lines into cells, picks columns, renames them, splits rows into files and turns a
wide table into a long one. It never computes anything. Each cell is text from the moment it is read to the moment it is written. There
is no op to interpolate, smooth, resample, change a unit, average, round, sort rows or fill a gap. A declaration that asks for one is
refused OPERATION_NOT_LISTED. The one change to a cell's text is DECIMAL_MARK (`1,5` becomes `1.5`), and the identity test still demands
the same number. The one drop of a data row is DROP_ROWS_NOT_NUMERIC (plan 1160 A11): a row whose declared column holds no number (an
empty or text cell) is dropped, recorded by its line number, and the identity test refuses the drop if that cell is a number.

## What you do

```
bin/cc new intake <id>                                      # first: declarations/<id>/, which peek and convert need
bin/cc intake peek <id> <cc-datasets>/<name>/raw/<file> [--sheet NAME|k] [--depth N] [--encoding E]   # a raw file's head, no value
#   write declarations/<id>/CONVERSION.toml (below)
bin/cc intake convert <id>                                  # write <cc-banks>/<id>/bank and its CONVERSION-MANIFEST.json
bin/cc intake convert <id> --verify                         # re-check the bank against the raw files, at any later time
#   then declare the bank in declarations/<id>/intake.toml: [source] kind = "CONVERTED"
```

Run `new intake` first: peek needs `declarations/<id>/`, and refuses "name a declaration" until it exists. One id serves the conversion
and the declaration, so peek.log, CONVERSION.toml, conversion-access.log and the intake declaration sit together, and the seal's ordering
note counts the conversion's reads (plan 1160 A13).

1. The deposit sits under the `<cc-datasets>` root (a root name of intake/ROOTS.toml: `~/scratch/cc-datasets` on the data host);
   `<cc-datasets>/<name>/raw` is an example. The root-named path you declare (`source`, and peek's file argument) names the files; the
   id is free and names only `declarations/<id>/` (plan 1160 A19): a declaration `a-r3` peeks `<cc-datasets>/a/raw/<file>`.
2. `peek` takes the file by its root-named path under `<cc-datasets>` (another root, an absolute path or a `..` part is
   SOURCE_FILE_ABSENT). It first prints which encodings of DECODE's alphabet decode the whole file (`decodes as: …; not as: …`, words of
   the alphabet only), and `--encoding E` (one of them) decodes the head lines (plan 1160 A22). It prints the first lines of one raw file as counts and text names only, so you can see where the names line is without seeing a
   value. It prints at most depth + 2 lines (depth 1 unless you say) and stops before the first line whose every cell is a number. A
   number in a text name prints as `#`. Each peek is recorded in `declarations/<id>/peek.log`. For an xlsx, `--sheet` is required; to learn
   the sheet names, peek without `--sheet`: it refuses SHEET_REQUIRED, and its Detail lists the workbook's sheet names, each after its
   position (`#1 'notes'`, `#2 a numeric name`: a text name masked, a numeric name never printed). `--sheet` and `sheet =` take the name or
   the 1-based position (`--sheet 2`, `sheet = 2`), so a sheet whose name does not print is still addressed (plan 1160 A21). Listing the names needs openpyxl, as SHEET_TO_CSV does, so peek on
   the data host (plan 1160 A10). Peek every file of the family, not one per kind: files of one family can differ in header length and
   column order. The Detail of a conversion refusal names the file (`file '<from>' -> '<to>'`), so you know which one to peek again
   (plan 1160 A12). Peek's `blank` is the converter's blank: a line with no text in any cell, which the converter records as blank and
   never as a row. Peek decodes as the default DECODE does (utf-8-sig), so a byte-order mark is no part of the first name.
3. You write `declarations/<id>/CONVERSION.toml`.
4. `convert` writes the bank to `<cc-banks>/<id>/bank` (`~/scratch/cc-banks` on the data host). It never overwrites a bank: remove the
   old one, or use a new id (BANK_EXISTS). Its summary lists each output's columns as names are printed everywhere: a numeral in a
   text name as `#`, a numeric name never (plan 1160 A31). A conversion takes seconds; one that runs for minutes is a defect, report it. A killed
   conversion writes no bank; `declarations/<id>/conversion-access.log` lists the files it had read (plan 1160 A23). It writes nothing unless the identity test passes on the exact bytes it is about to write.
5. In the intake declaration, `[source]` says `kind = "CONVERTED"`, `converted_from = "<cc-datasets>/<name>/raw"` (the deposit you converted) and
   `root = "<cc-banks>/<id>/bank"`, and `[selection]` excludes `CONVERSION-MANIFEST.json`. At S3 the intake checks the chain from the raw
   files to the bank (CONVERSION_CHAIN_BROKEN) and then reads the bank exactly as a deposit.

## The declaration

```toml
schema = 1
kind = "conversion"
source = "<cc-datasets>/run7/raw"
out = "<cc-banks>/run7/bank"

[[file]]                     # one entry per raw file you convert
from = "run1.dat"            # a file under source
to = "curve_000.csv"         # its name in the bank (letters, digits, _ . -)
steps = [{op = "DROP_LINES", rule = {kind = "MARKER", marker = "[Data]"}}]
```

A file moves through four stages: RAW (bytes), TEXT (lines), TABLE (rows of cells) and NAMED (a names line and rows). Every output ends
NAMED and is written as comma-separated UTF-8. When a step needs a later stage than the file is in, the default step of each stage in
between runs first: DECODE `utf-8-sig`, then DELIMITER `COMMA`, then NAMES_LINE `FIRST`. So `steps = []` reads a plain CSV as it is. A
step that needs an earlier stage than the file is already in is refused STEP_OUT_OF_ORDER. For example, DROP_LINES after DELIMITER is
refused, because the lines are already cut into cells.

A line with no text in any cell is skipped and recorded as blank. Every other line ends up in exactly one place: written, dropped by a
DROP_LINES step, or the names line. The manifest records which.

## The ops, each on a planted file

Each example below is a case of tests/test_intake_convert.py (V1): the output is checked byte for byte.

### UNPACK

RAW to RAW: the bytes of one member of a zip archive.
`a.zip` holds `run1.csv` = `T,C` / `1.5,0.25`.
`steps = [{op = "UNPACK", member = "run1.csv"}]` writes `T,C` / `1.5,0.25`.
If the archive does not hold the member, the refusal is SOURCE_FILE_ABSENT. If the bytes are not a zip archive, it is CONTAINER_UNREADABLE.

### DECODE

RAW to TEXT: the bytes decoded from `encoding`, one of `utf-8`, `utf-8-sig`, `latin-1`, `cp1252` and `utf-16`.
A latin-1 file `T,µ` / `1.5,0.25` with `steps = [{op = "DECODE", encoding = "latin-1"}]` is written as UTF-8 `T,µ` / `1.5,0.25`.
Bytes that are not that encoding are refused ENCODING_INVALID.

### DROP_LINES

TEXT to TEXT. Each dropped line is recorded in the manifest with its step. There are three rules:

- `rule = {kind = "MARKER", marker = "[Data]"}` drops every line up to and including the first line that is exactly `[Data]` (blanks
  around it ignored). This is a MultiVu-like file:
  `[Header]` / `TITLE,run 1` / `[Data]` / `Time,Temp (K),Moment` / `1.0,300.5,1e-3` / `2.0,301.25,2e-3`.
  It is written as `Time,Temp (K),Moment` / `1.0,300.5,1e-3` / `2.0,301.25,2e-3`. If no line is the marker, the refusal is MARKER_LINE_ABSENT.
- `rule = {kind = "FIRST", count = 2}` drops the first two lines: `sample A` / `operator note` / `T,C` / `1.5,0.25` is written as `T,C` / `1.5,0.25`.
- `rule = {kind = "PREFIX", prefix = "#"}` drops every line that begins with `#`: `# run 1` / `T,C` / `# pause` / `1.5,0.25` is written
  as `T,C` / `1.5,0.25`.

### DELIMITER

TEXT to TABLE: each line cut into cells at `from`. `COMMA`, `SEMICOLON` and `TAB` are CSV dialects (quotes are honoured).
`WHITESPACE` cuts at runs of blanks. A cell's text is never changed.
`T⇥C` / `1.5⇥0.25` with `{op = "DELIMITER", from = "TAB"}` is written as `T,C` / `1.5,0.25`.
`T   C` / `  1.5  0.25` / (blank) / `1.6 0.5` with `from = "WHITESPACE"` is written as `T,C` / `1.5,0.25` / `1.6,0.5` (the blank line is recorded as blank).
`WHITESPACE` has no empty cell: a run of blanks is one separator, so an empty cell vanishes and its row comes out narrower. A row
narrower than the names line is refused EMPTY_CELL_UNDER_WHITESPACE. If cells can be empty, declare `TAB` or `COMMA`, which keep the
empty cell, and DROP_ROWS_NOT_NUMERIC can then drop the row (plan 1160 A32).

### SHEET_TO_CSV

RAW to TABLE: the rows of one sheet of an xlsx workbook. A number cell is written as Python writes it, and an empty cell as nothing.
A workbook with sheets `notes` and `data`, where `data` holds `T`,`C` / 1.5,0.25: `steps = [{op = "SHEET_TO_CSV", sheet = "data"}]`
writes `T,C` / `1.5,0.25`. This needs openpyxl (without it the refusal is XLSX_READER_ABSENT; run it on the data host). If the workbook
has no such sheet, the refusal is SHEET_ABSENT. Bytes that are no workbook are refused CONTAINER_UNREADABLE. After SHEET_TO_CSV the file is
already a TABLE, so DROP_LINES (a TEXT op) is STEP_OUT_OF_ORDER: write NAMES_LINE WRITE for every column and remove the label rows with
DROP_ROWS_NOT_NUMERIC (plan 1160 S11.9 W2).

### NAMES_LINE

TABLE to NAMED: which row is the names line.

- `rule = {kind = "FIRST"}`: the first row (the default).
- `rule = {kind = "WRITE", names = ["T", "C"]}`: the file has no names line, and these names are written. `1.5,0.25` / `1.6,0.5` is
  written as `T,C` / `1.5,0.25` / `1.6,0.5`. No row is taken from the file. SELECT_COLUMNS then NAMES_LINE WRITE: every converted file
  of one declaration must carry identical names, so write them in each file's steps (plan 1160 A26). Write one name per column: a
  names list of another length than a row's cells is refused NAMES_COUNT_MISMATCH, never written as a partial header (plan 1160 A29).
- `rule = {kind = "REPLACE_PREFIXED", prefix = "##"}`: the first row must begin with `##` (MARKER_LINE_ABSENT otherwise). It is the
  names line without the prefix: `##T,C` / `1.5,0.25` is written as `T,C` / `1.5,0.25`.

### DECIMAL_MARK

NAMED to NAMED: in every data cell and every names cell, the decimal mark `,` becomes `.`. The only mark is `,`.
`T;C` / `1,5;0,25` with `steps = [{op = "DELIMITER", from = "SEMICOLON"}, {op = "DECIMAL_MARK", mark = ","}]` is written as `T,C` / `1.5,0.25`.
The identity test compares `1.5` with the source cell `1,5` after the same replacement, so the number is unchanged.

### SELECT_COLUMNS

NAMED to NAMED: the columns you name, in your order. Name a column by its name or by its 1-based position.
`T,C,s` / `1.5,0.25,0.01` with `{op = "SELECT_COLUMNS", columns = ["C", 1]}` is written as `C,T` / `0.25,1.5`.
A name that no column holds, or that two columns hold, a position out of range, or a row too short for a named column is refused COLUMN_ABSENT.

### RENAME

NAMED to NAMED: a names cell `from` becomes `to`. The cells below it are untouched.
`Temp,C` / `1.5,0.25` with `{op = "RENAME", pairs = [{from = "Temp", to = "T"}]}` is written as `T,C` / `1.5,0.25`.
If no single column is named `from`, the refusal is COLUMN_ABSENT.

### SPLIT_ROWS

NAMED to NAMED: one file becomes several. Rows are copied verbatim, in order, and each output repeats the names line.

- `rule = {kind = "RANGES", parts = [{name = "up.csv", first = 1, last = 2}, {name = "down.csv", first = 3, last = 3}]}`: data rows
  1 to 2 go to `up.csv`, and row 3 to `down.csv` (rows count from 1, after the names line).
  `T,C` / `1.5,0.25` / `1.6,0.5` / `1.5,0.75` is written as `up.csv` = `T,C` / `1.5,0.25` / `1.6,0.5` and `down.csv` = `T,C` / `1.5,0.75`.
  Every data row must land in exactly one part. A row in no part, or in two parts, is refused CELL_MAP_NOT_A_PERMUTATION.
- `rule = {kind = "CHANGE", column = "h"}`: a new output starts each time the text of column `h` changes. The outputs are named after
  `to`: `out.csv` gives `out_000.csv`, `out_001.csv` and so on.
  `T,C,h` / `1.5,0.25,0.1` / `1.6,0.5,0.1` / `1.5,0.75,0.2` is written as `out_000.csv` (the two `0.1` rows) and `out_001.csv` (the `0.2` row).

### WIDE_TO_LONG

NAMED to NAMED: a wide table, whose names line is a key column followed by numbers, becomes a long table. Each source row becomes one block
of rows, and each row of the block holds `fast` (the names cell, verbatim), `measured` (the row's cell) and the key cell.
`h,1.5,1.6` / `0.1,0.25,0.5` / `0.2,0.75,1.0` with `{op = "WIDE_TO_LONG", key = "h", fast = "T", measured = "C"}` is written as
`T,C,h` / `1.5,0.25,0.1` / `1.6,0.5,0.1` / `1.5,0.75,0.2` / `1.6,1.0,0.2`.
Every name except the key's must be a number (NAMES_NOT_NUMERIC otherwise). A row shorter than the names line is refused COLUMN_ABSENT.
Declare the bank as a LONG_TABLE whose slow column is the key.

### DROP_ROWS_NOT_NUMERIC

NAMED to NAMED (plan 1160 A11): each data row in which any of `columns` holds a cell that is not a number (an empty cell, or text) is
dropped. Name a column by its name or by its 1-based position. Every kept row is written unchanged.
`T,C` / `1.5,0.25` / `1.6,` / `1.7,n/a` / `1.8,0.5` with `{op = "DROP_ROWS_NOT_NUMERIC", columns = ["C"]}` is written as `T,C` / `1.5,0.25` / `1.8,0.5`.
The manifest records each dropped row's source line number, its step, the line and column of the cell that is not a number, and the count;
never the cell. The identity test refuses (CELL_MAP_NOT_A_PERMUTATION) a drop whose recorded cell is a number. The census of the run that
reads the bank prints, per converted file, how many rows were dropped.
Declare it after DECIMAL_MARK (a `1,5` is not a number until the mark is replaced, and the identity test would refuse its drop), and before
WIDE_TO_LONG (a wide row becomes many long rows: drop the whole source row, or none of it).

**When to use it, and when not.** Use it when a declared column of a data row holds an empty cell or a word such as `n/a` (a reading
the instrument did not record). A row dropped this way loses its other cells too. If the rows it would drop are a second header block in
mid-file, a repeated names line, or a comment line, the column is not wrong: those are not data rows, and DROP_LINES (PREFIX or FIRST) or
SPLIT_ROWS (one output per block) handles them, so that each block keeps its own names line. If most rows of a column would be dropped,
it is a sign the column is the wrong one: peek again and declare another column.

## Shapes that convert (tests/test_intake_convert.py V3)

- **MultiVu-like** (`[Header]` ... `[Data]`, then a names line): `DROP_LINES` with rule MARKER `[Data]`.
- **Semicolons, decimal commas and a `##` names line** such as `##Temp./°C;C;sigma`: `DELIMITER SEMICOLON`, `NAMES_LINE REPLACE_PREFIXED "##"`,
  `DECIMAL_MARK ","`, then `RENAME` `Temp./°C` to `T`.
- **WIDE** (a key column, and a names line of fast values): `WIDE_TO_LONG`, then a LONG_TABLE declaration.
- **A workbook with two sheets**: `SHEET_TO_CSV` of the data sheet, `SELECT_COLUMNS`, then `SPLIT_ROWS RANGES` into one file per curve
  and a PER_FILE declaration. This needs openpyxl, so it runs on the data host.

## The identity test and the manifest

Before writing, the converter checks two things on the exact bytes it is about to write:

- **The cell map is a permutation.** Every output cell names one source cell (line and column). No source cell feeds two output cells,
  except the repeated fast and key columns of WIDE_TO_LONG. Every source line is written, dropped by a declared DROP_LINES step, dropped by
  DROP_ROWS_NOT_NUMERIC for a cell that is not a number, blank, or a names line, exactly once. Otherwise the refusal is CELL_MAP_NOT_A_PERMUTATION.
- **The identity holds.** Two numbers must be bitwise equal as floats, and any other cell must have equal text. Rows must stay in
  source order. Otherwise the refusal is IDENTITY_FAILED.

`CONVERSION-MANIFEST.json` in the bank records the following, and never a cell value:

- the raw files: path, sha256 and size;
- the outputs: path, sha256, size, rows, number of columns and the cell map, as line and column numbers;
- the dropped and names lines, by number, each dropped line with its step; for DROP_ROWS_NOT_NUMERIC, the line and column of the cell
  that is not a number, and the count of rows dropped, split into EMPTY (every cell of the row that is not a number is empty) and TEXT
  (at least one such cell holds text). Each dropped row is classed once, so the two counts sum to the count. The convert summary prints
  the same split per file;
- the steps as you declared them;
- the code hash and the time.

`convert <id> --verify` and S3 recompute everything from the files on disk. If a raw file or a bank file no longer has its recorded sha256,
the refusal is CONVERSION_CHAIN_BROKEN. If the cells no longer match, the refusal is the identity test's. Order: `convert <id>` writes the
bank and its manifest; `--verify` re-checks an existing bank, so on a bank that was never converted it refuses CONVERSION_CHAIN_BROKEN.

## Refusals

Every refusal names the first check that failed. Its Detail gives counts, file names and text names, never a value. The sentences are
in intake/CONVERSION.toml (`[[reason]]`). The S0 codes (TOML_INVALID, SCHEMA_UNSUPPORTED, FIELD_MISSING, FIELD_TYPE_WRONG, FIELD_UNKNOWN,
VALUE_NOT_LISTED, VALUE_STILL_TODO, ROOT_NOT_UNDER_CC_BANKS and OPERATION_NOT_LISTED) mean the declaration itself needs fixing. The
others are:

| Code | What to do |
|---|---|
| ROOT_UNRESOLVED | `source` or `out` names a root that intake/ROOTS.toml lacks, or the raw directory does not exist |
| BANK_EXISTS | the bank directory already has files; remove it or use a new id |
| OUTPUT_NAME_REFUSED | an output name is not letters, digits, `_ . -`, is used twice, or is CONVERSION-MANIFEST.json |
| STEP_OUT_OF_ORDER | move the step earlier: see the stages above |
| SOURCE_FILE_ABSENT | `from` (or an UNPACK member) is not in the deposit |
| CONTAINER_UNREADABLE, XLSX_READER_ABSENT, SHEET_ABSENT | the archive or workbook cannot be read as declared |
| SHEET_REQUIRED | peek on an xlsx with no `--sheet`: the Detail lists the sheets by position; peek again with `--sheet k` or `--sheet NAME` |
| MARKER_LINE_ABSENT | no line is the marker, or the first row lacks the prefix |
| COLUMN_ABSENT | a named column is missing or ambiguous, or a row is too short for it |
| ENCODING_INVALID | the bytes are not the declared encoding: peek's `decodes as:` line names those that decode; choose one |
| NAMES_NOT_NUMERIC | WIDE_TO_LONG met a text name besides the key; SELECT_COLUMNS it away first |
| NAMES_COUNT_MISMATCH | NAMES_LINE WRITE names a different number of columns than a row holds: write one name per column |
| EMPTY_CELL_UNDER_WHITESPACE | a row is narrower than the names line under WHITESPACE: declare DELIMITER TAB or COMMA |
| CELL_MAP_NOT_A_PERMUTATION, IDENTITY_FAILED | the steps would lose, repeat, reorder or change a cell; this is the rule at the top |
| CONVERSION_CHAIN_BROKEN | the raw files or the bank changed after the conversion; convert again under a new id |

If a data row holds an empty or text cell in a declared column, the intake refuses it (CELL_NOT_A_NUMBER; `nan` is text). Declare
DROP_ROWS_NOT_NUMERIC on that column if the row is a reading the instrument did not record; declare another column if that column is the
wrong one; or report the deposit as unreadable. A conversion cannot fill a row, and it drops one only through DROP_ROWS_NOT_NUMERIC.
