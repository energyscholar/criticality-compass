# The intake on a data host

Plan 1145. The data sets live on another machine, the data host, under `~/scratch/cc-datasets/<id>/`. This page puts a branch of the
Criticality Compass on that host and runs `bin/cc intake` there. The data never leave the host. Only the branch travels, as a git bundle.

`<host>` below is your own command that runs one shell command on the data host and passes its standard input through, for example
`ssh <user>@<address>`. This page names no machine.

## 1. Put the branch on the host

On the machine that has the repository:

```
git bundle create cc-intake.bundle <branch>
<host> 'mkdir -p ~/scratch && cat > ~/scratch/cc-intake.bundle' < cc-intake.bundle
<host> 'git clone -b <branch> ~/scratch/cc-intake.bundle ~/scratch/cc-intake'
```

To update an existing clone later, copy a new bundle the same way, then run
`<host> 'cd ~/scratch/cc-intake && git pull ~/scratch/cc-intake.bundle <branch>'`.

A clone that has been used before may hold declarations with the same ids; move them away or choose new ids. `bin/cc new intake <id>`
never overwrites one: it refuses an id whose `declarations/<id>` exists, and names it ("declarations/<id> exists; a declaration is never
overwritten (choose another id)").

The host needs Python 3.11 or later and numpy. The xlsx format of the reader `table-curve-v1` also needs openpyxl. Without it an xlsx file
is Unreadable XLSX_READER_ABSENT (a named refusal, never an exception). `bin/cc intake explain` lists every reason.

## 2. Check the clone on the synthetic bank

```
<host> 'cd ~/scratch/cc-intake && bin/cc intake synth demo1 --seed 1 && bin/cc new intake demo1 --from-synth demo1'
```

Then fill the TODO lines of `~/scratch/cc-intake/declarations/demo1/intake.toml` on the host. The filled example in
`docs/INTAKE-QUICKSTART.md` fits. Then:

```
<host> 'cd ~/scratch/cc-intake && bin/cc intake lint demo1 && bin/cc intake run demo1'
<host> 'cd ~/scratch/cc-intake && python3 tests/test_intake_read.py && python3 tests/test_intake_reach.py'
```

Expect the census label the quickstart shows. The two tests also cover the xlsx rows when openpyxl is installed: the reach test's NOT REACHED
line then says `none`.

## 3. Declare a data set

The root name `<cc-datasets>` (intake/ROOTS.toml) is `~/scratch/cc-datasets` under the home directory. A declaration names its files as
`root = "<cc-datasets>/<name>"` (an example: the root-named path is the declaration, and the id is free; it names only
`declarations/<id>/`, plan 1160 A19). Peek names a file the same way: `bin/cc intake peek <id> <cc-datasets>/<name>/raw/<file>`. On a machine without that directory, S3 refuses ROOT_UNRESOLVED. That refusal is honest: the data are not
there.

```
<host> 'cd ~/scratch/cc-intake && bin/cc new intake <id>'
<host> 'cd ~/scratch/cc-intake && bin/cc intake profile <id> <cc-datasets>/<name>/raw'
```

(Plan 1165.) Profile before you fill a TODO: the profile reads every byte of the path and writes declarations/<id>/PROFILE.json and
PROFILE.md, and a `## Profile` section in `<cc-datasets>/<name>/MANIFEST.md` (counts only). Read PROFILE.md first; each finding names its
one response (docs/INTAKE-PREPROCESSING.md). For a CONVERTED bank profile the bank too (`<cc-banks>/<id>/bank`); for a RESERVED set
profile the blinded view (`<cc-blind>/<id>`). After the TODO lines are filled, `bin/cc intake profile <id> --check` checks the declaration
against the profile (exit 1 on any contradiction); S3 refuses a run with no profile (PROFILE_ABSENT), a stale one (PROFILE_STALE) or a
contradicted one (PROFILE_CONTRADICTED).

The new declaration's TODO lines are the choices. It is intake format v5 (`schema = 5`); a v2, v3 or v4 declaration is refused
SCHEMA_UNSUPPORTED, so restate it in v5 under a new id (v4 to v5 adds `[knobs.slow] kind = "QUANTITY"`, the v4 meaning, and writes `[replicate] key = ""` as `[replicate.key] kind = "NONE"`; v3 to v4 added
`[knobs.fast] control = "SET"`, the v3 meaning).

`[source]` says what the files are:

- `kind`: `DEPOSIT` (the files as deposited, read directly) or `CONVERTED` (a bank written by a declared conversion; it also carries
  `converted_from`, and its `root` is under `<cc-banks>/`). `bin/cc intake convert <id>` writes that bank
  from the raw files and declarations/<id>/CONVERSION.toml (docs/INTAKE-CONVERSION.md); S3 refuses CONVERSION_CHAIN_BROKEN unless the
  bank's CONVERSION-MANIFEST.json still matches the raw files and the bank, then reads the bank as a DEPOSIT. Exclude
  CONVERSION-MANIFEST.json from `[selection]`, as MANIFEST.json is.
- `admissibility`: `RAW`, `DECLARABLE`, `FIGURE_LEVEL` or `PROCESSED_UNDECLARABLE`, read from the deposit's metadata. It is sealed with the
  declaration.
- `universe`: a glob, relative to `root`, of every file the seal lists. For a CONVERTED bank (or a BLINDED view) write
  `universe = "*"`: the bank directory holds the outputs and CONVERSION-MANIFEST.json, nothing else (plan 1160 A38).

For a table, `[reader]` is `table-curve-v1`:

- `[reader.format]` sets `kind`: `COMMA`, `TAB`, `WHITESPACE`, or `XLSX` with a `sheet`.
- `[reader.header]` sets `kind`:
  - `SKIP` with `rows`;
  - `NAMES` with `rows` and the line of `names`;
  - `NAMES_UNITS` with `rows`, the line of `names` and the line of `units`.
  - `NAMES_UNITS_IN_NAMES` with `rows`, the line of `names` and `unit_syntax`: each names cell holds its unit, as `T (K)` (`PAREN`) or
    `T/K` (`SLASH`, split at the first slash). Declare a column by its bare name (`T`). A names cell with no unit states none, and a
    unit that differs from the declared one is refused UNIT_DIFFERS. A refusal prints a stated unit with every number in it as `#`.
- `comment` holds the line prefixes to drop, for example `["#"]`, or `[]` for none. An empty prefix `""` would drop every line, so it is
  refused COMMENT_PREFIX_EMPTY. Comment lines are dropped before the header is counted: `rows` counts the lines that are left. When
  every line above the data is a comment line, declare `kind = "SKIP"` with `rows = 0` and the `comment` prefix, and name the columns
  by position; `rows = 1` would take the first data row as a header line. A prefix drops every line it begins, so `comment = ["#"]`
  also drops a `##T,C` names line, and the reader then finds no names line: convert the file instead, with NAMES_LINE
  REPLACE_PREFIXED `"##"` (docs/INTAKE-CONVERSION.md) (plan 1160 A38).

Columns are named in `[knobs.fast]`, `[measured]` and `[measured.uncertainty]` (COLUMN or NONE): by NAME (a string) or by 1-based POSITION
(an integer). A report prints a column declared by name in quotes (`'T'`) and one declared by position as `#k`, its 1-based position. S4
lists the declared columns in role order: fast, measured, the uncertainty column when one is declared, then the slow column of a
LONG_TABLE. So `columns are #2, #3, #1` means the fast knob is column 2, the measured quantity column 3 and the slow knob column 1.
The reader takes the declared columns only: extra columns, and rows of differing width beyond them, do not matter. When a card (a
README, a column index) disagrees with the file, the file wins: peek it and declare what it holds (plan 1160 A23).

`[acquisition]` says how the rows were taken and stored. `row_order` is how the rows are stored: `ASCENDING` or `DESCENDING` (sorted by
the fast knob) or `ACQUISITION` (in the order they were taken). `direction` is the order they were taken in along the fast knob:
`ASCENDING`, `DESCENDING` or `UNORDERED`. If the deposit does not state the order the rows were written in, declare `row_order =
ACQUISITION` and `direction = UNORDERED`; ASCENDING and DESCENDING assert a monotone sweep and S4 refuses a file that is not one. When S4
refuses ROW_ORDER_DIFFERS, its Detail counts the curves of the refused file that are in the declared order, in the opposite order, and in
neither order (not monotone). These are counts only, never a value. A curve in the opposite order means the other direction fits it;
a curve in neither order means no sorted order fits, and `ACQUISITION` with `UNORDERED` is the declaration that does. A guessed
`direction` is a declaration S5 tests (ACQUISITION_ORDER_DIFFERS), so a wrong guess is refused, never taken silently (plan 1160 A23).
(A LONG_TABLE with block `FAST_RESTART` needs a direction; see below.)

There are two layouts in `[selection]`:

- `PER_FILE`: one curve per file. `files` lists them, in curve order. An empty `files` is refused SELECTION_EMPTY at S1. `[selection.slow]` says where each curve's slow-knob value comes
  from:
  - `LISTED` with `values`: one number per file of `files`, in that order, each written as text (`["-0.15", "-0.10"]`). A count that
    differs from `files` is refused SLOW_VALUES_NOT_ONE_PER_FILE before any byte is read.
  - `FILE_KEY` with `key`: each file has a header line whose first cell is the key and whose second cell is the value. Declare that
    line among the header rows. A file without exactly one such line holding a number is refused SLOW_KEY_UNRESOLVED.
  - `NONE`: the deposit has no slow knob. No curve then carries a slow value, so S8 would refuse TOO_FEW_CURVES and no layout can
    reach S10: S1 refuses SLOW_NONE_HAS_NO_PATH at lint, before any byte is read (plan 1160 A24). Declare the slow knob, or report the
    deposit as one with no slow knob.
- `LONG_TABLE`: one `file` holds every curve, and `[selection.slow]` is `COLUMN` with its `key`. `block` says where a curve begins:
  - `EXACT`: a curve is a run of consecutive rows with one slow value. A slow value in two runs that are not adjacent is refused
    CURVE_REPEATED.
  - `FAST_RESTART`: a curve ends where the fast knob turns back against its direction (`row_order`, or `direction` when the rows are
    stored in acquisition order). The curve's slow value is its first row's, and the census reports `distinct_slow_in_block max = N`,
    a count. Rows in acquisition order with direction `UNORDERED` give no direction, so S1 refuses BLOCK_RULE_HAS_NO_DIRECTION.

`[knobs.fast] control` says how the fast knob was driven: `SET` (it was set to each value of a grid; the template's line) or `MEASURED`
(it was read, not set: a ramp or a carried sweep). An instrument ramp's fast knob is MEASURED: a temperature or field swept at a rate
and read as it passed is never a grid, whatever its step looks like (plan 1160 A38). It decides what a point is, and so what a
repeated fast value means:

| control | `[replicate] identity` | a point is | a repeated fast value in a curve |
|---|---|---|---|
| SET | NONE, SEED, RUN, SAMPLE, FILE | one row, keyed by its fast value | refused FAST_VALUE_REPEATED at S5 |
| SET | SAME_FAST_VALUE | a run of consecutive rows with one fast value; the census reports readings per point (min, max) | consecutive: the readings of one point; revisited after the knob left it: refused FAST_VALUE_REPEATED |
| MEASURED | NONE | one row, keyed by its place in the curve | no repeat: every row is its own point |
| MEASURED | any other | (none) | refused at S1 MEASURED_KNOB_HAS_NO_POINTS, as is an `[interval] method` other than STATED or NONE |

FAST_VALUE_REPEATED's detail counts, over the refused curves, `consecutive runs`, `longest run`, `values revisited` and `monotone runs`
(counts only, never a value), and names the exit of each kind it found. The four kinds of repeat and their remedies:

- **K1** consecutive replicate runs (a set knob, a grid): `[replicate] identity = "SAME_FAST_VALUE"`.
- **K2** a value revisited after the knob left it (a measured knob dithering): `control = "MEASURED"`. A set knob that loops is two
  branches: split the rows (SPLIT_ROWS), one file per branch.
- **K3** a single consecutive duplicate: `SAME_FAST_VALUE`, as K1.
- **K4** a long flat run (a hold: a segment, not a replicate): `control = "MEASURED"`, or exclude the segment.

Not available: `[replicate] adjacency = "ANYWHERE"` (a point as every row with one fast value, wherever it lies); a revisit under SET
stays refused. A loop (up then down along the same fast knob) is two branches: a SET knob's loop is split into one file per branch by
conversion (SPLIT_ROWS) before it can be declared; a MEASURED knob's loop is admitted as rows: declare `control = "MEASURED"` (plan 1160
A25).

`root` is the directory that holds the files: the deposit's `.../raw`, or for a CONVERTED source the bank directory; the seal lists
that same directory. A deposit with no files.lst is declared from its raw directory listing. For a bank, `excluded` lists
`CONVERSION-MANIFEST.json` (plan 1160 A26).

`excluded` lists the files of the universe that are not curves, each with a `why`. The seal checks that the universe is exactly the
selected files, the excluded files and the truth side, each file in one part. Otherwise it refuses UNIVERSE_NOT_PARTITIONED, or
SELECTION_DUPLICATE when a name is given twice. After a conversion with SPLIT_ROWS CHANGE the bank holds one output per change, some
of them short or not curves: choose the curves for `[selection] files` from the convert summary (rows and columns per output), and list
every other output in `excluded` with its why (plan 1160 A38).

A family of files that varies in two parameters (a field and a pressure, say) is not one curve family. One parameter becomes the slow
knob; the other must be held fixed: by selection (select the files at one value of it and list the rest in `excluded`, with the why),
or, when the deposit itself holds it fixed, by stating that in transducer.toml's `[record] preparation`. Never let both vary across the
selected curves: two curves at one slow value are refused CURVE_REPEATED, and curves that differ in both would be chained as if only
the slow knob had changed (plan 1160 A38).

### A RESERVED data set: declare the blinded view (plan 1160 A41)

A deposit's file names can carry the slow value (`run_h0.5.csv`). The intake's Details, census and report name curve files, so on a
RESERVED data set the names alone would leak it. Make the blinded view first, then declare the view, never the deposit:

```
<host> 'cd ~/scratch/cc-intake && bin/cc intake blind <id> "<cc-datasets>/<name>/raw" "<file 1>" "<file 2>" ...'   # the curve files, in curve order
```

It makes `<cc-blind>/<id>/` with one hard link per file named by ordinal (`001.csv`, `002.csv` ...), writes the name-to-ordinal key to
`<cc-blind>/<id>.KEY.json`, beside the view and outside it, and prints the key's sha256. Leave the key unread until unblinding: no
intake stage reads it, and an in-process read of it is logged as a bypass, which S6 refuses. Then declare `[source] kind = "BLINDED"`,
`root = "<cc-blind>/<id>"`, `blinded_from` (the deposit's directory you named), `key_sha256` (the printed sha256, which the seal
records with the declaration), `universe = "*"`, and in `[selection]` the ordinals in the order you gave the files, `excluded = []`.
Every Detail, census line and report then names ordinals only. `<cc-blind>` must be on the deposit's device (a hard link cannot cross
devices: BLIND_NOT_ONE_DEVICE); a view is never replaced (BLIND_VIEW_EXISTS).

### transducer.toml for real data

Alongside intake.toml, `new intake` writes transducer.toml. For real data it must say `kind = "record"` with `[record]` (apparatus, preparation, observation, authors_projection, source) plus `[reduction]` (name, keeps, discards) and `[interval]` (role as printed, keeps, discards); lint refuses while any TODO remains.

The file `new intake` writes is the transducer template, `kind = "transducer"`, made for a simulation. For a deposit, delete its
`[transducer]` table and write `[record]` in its place. Each field is one line of words about the deposit, taken from its metadata,
never a value read from a data file:

- `apparatus`: the instrument and its settings, as the deposit states them.
- `preparation`: the sample, and how it was prepared and brought to each slow-knob value.
- `observation`: what one row of the file is.
- `authors_projection`: any step the authors applied before depositing (a background subtraction, a normalisation); "none stated" if
  the deposit states none.
- `source`: where the files come from (repository, DOI or accession, licence).

`[reduction]` says what the Compass keeps of each point and what it discards. `[interval]` says what the interval keeps and discards.
Its `role` is fixed: write it exactly as in the example below (S0 compares it with cc.toml). `[provenance_note]` is optional. One complete
file, for a hypothetical deposit (every line here is illustrative):

```toml
# declarations/<id>/transducer.toml - the record file of a deposited data set
schema = 1
kind = "record"
id = "<id>"

[record]
apparatus = "a SQUID magnetometer, field 10 mT, temperature swept at 1 K/min (as stated in the deposit's README)"
preparation = "one powder sample, zero-field cooled before each field value"
observation = "one row = one magnetization reading at one temperature"
authors_projection = "none stated: the deposit's README says the columns are the instrument output"
source = "the data repository record named in the README (licence CC BY 4.0)"

[reduction]
name = "none in the Compass: the file stores one value of the measured quantity per (slow, fast) point"
keeps = "the deposited value at each point"
discards = "nothing the file holds"

[interval]
role = "projection C: places the reading's sign cell against its declared margin; never an operator input"
keeps = "the uncertainty column as deposited"
discards = "how the authors computed it"
```

Then:

```
<host> 'cd ~/scratch/cc-intake && bin/cc intake lint <id>'
<host> 'cd ~/scratch/cc-intake && bin/cc intake seal <id> --author "<name>" --as human --unconfirmed'
<host> 'cd ~/scratch/cc-intake && bin/cc intake run <id> && cat declarations/<id>/intake-report.md'
```

S1 refusals appear at lint and at seal: a seal refused for an S1 reason makes no run and no intake-report.md, and the refusal is the
answer (plan 1160 A26): do not run unsealed to get past it, since an unsealed run is not a reportable result (plan 1160 S11.9 W1).
Sealing is recommended and not enforced. The seal lists the universe under the declared `[source] root`, the directory S3 reads; it takes
no `--universe`. If `seal` refuses, fix the declaration and seal again; do not run. Seal before the first run: `run` reads the data through the logged loader, and the report's
ordering note compares the seal time with the first logged read. A conversion reads the raw files before you seal; that is the designed
order, so the ordering note reports it as information and never as a refusal: when declarations/<id>/conversion-access.log holds reads of
raw files from before the seal, the note adds `CONVERSION_READ_BEFORE_SEAL (n files)`, and the seal claims ordering only for the intake's
own reads (plan 1160 A13).

The reports and seals stay in the clone on the host. Copy back only what you mean to keep, with the same `<host>` command.
