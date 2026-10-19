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
`root = "<cc-datasets>/<id>"`. On a machine without that directory, S3 refuses ROOT_UNRESOLVED. That refusal is honest: the data are not
there.

```
<host> 'cd ~/scratch/cc-intake && bin/cc new intake <id>'
```

The new declaration's TODO lines are the choices. It is intake format v3 (`schema = 3`); a v2 declaration is refused SCHEMA_UNSUPPORTED,
so restate it in v3 under a new id.

`[source]` says what the files are:

- `kind`: `DEPOSIT` (the files as deposited, read directly) or `CONVERTED` (a bank written by a declared conversion; it also carries
  `converted_from`, and its `root` is under `<cc-banks>/`). A CONVERTED source is refused CONVERSION_NOT_LIVE at S3 until the conversion
  has a body.
- `admissibility`: `RAW`, `DECLARABLE`, `FIGURE_LEVEL` or `PROCESSED_UNDECLARABLE`, read from the deposit's metadata. It is sealed with the
  declaration.

For a table, `[reader]` is `table-curve-v1`:

- `[reader.format]` sets `kind`: `COMMA`, `TAB`, `WHITESPACE`, or `XLSX` with a `sheet`.
- `[reader.header]` sets `kind`:
  - `SKIP` with `rows`;
  - `NAMES` with `rows` and the line of `names`;
  - `NAMES_UNITS` with `rows`, the line of `names` and the line of `units`.
- `comment` holds the line prefixes to drop, for example `["#"]`, or `[]` for none. An empty prefix `""` would drop every line, so it is
  refused COMMENT_PREFIX_EMPTY.

Columns are named in `[knobs.fast]`, `[measured]` and `[measured.uncertainty]` (COLUMN or NONE): by NAME (a string) or by 1-based POSITION
(an integer).

There are two layouts in `[selection]`:

- `PER_FILE`: one curve per file. `files` lists them, in curve order. `[selection.slow]` says where each curve's slow-knob value comes
  from:
  - `LISTED` with `values`: one number per file of `files`, in that order, each written as text (`["-0.15", "-0.10"]`). A count that
    differs from `files` is refused SLOW_VALUES_NOT_ONE_PER_FILE before any byte is read.
  - `FILE_KEY` with `key`: each file has a header line whose first cell is the key and whose second cell is the value. Declare that
    line among the header rows. A file without exactly one such line holding a number is refused SLOW_KEY_UNRESOLVED.
  - `NONE`: the deposit has no slow knob. The census forms the curves with no slow value (`curves_with_slow = 0`).
- `LONG_TABLE`: one `file` holds every curve, and `[selection.slow]` is `COLUMN` with its `key`.

When a deposit repeats a point (several readings at one fast value, one after another), declare `[replicate] identity =
"SAME_FAST_VALUE"`: consecutive rows of one curve with an equal fast value are then the readings of one point, and the census reports
readings per point (min, max). Under any other identity such rows are refused FAST_VALUE_REPEATED. A repeat that is not consecutive is
refused ROW_ORDER_DIFFERS (rows declared ASCENDING or DESCENDING).

`excluded` lists the files of the universe that are not curves, each with a `why`. The seal checks that the universe is exactly the
selected files, the excluded files and the truth side, each file in one part. Otherwise it refuses UNIVERSE_NOT_PARTITIONED, or
SELECTION_DUPLICATE when a name is given twice.

Then:

```
<host> 'cd ~/scratch/cc-intake && bin/cc intake lint <id>'
<host> 'cd ~/scratch/cc-intake && bin/cc intake seal <id> --universe ~/scratch/cc-datasets/<id> --author "<name>" --as human --unconfirmed'
<host> 'cd ~/scratch/cc-intake && bin/cc intake run <id> && cat declarations/<id>/intake-report.md'
```

Sealing is recommended and not enforced. Seal before the first run: `run` reads the data through the logged loader, and the report's
ordering note compares the seal time with the first logged read.

The reports and seals stay in the clone on the host. Copy back only what you mean to keep, with the same `<host>` command.
