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

The new declaration's TODO lines are the choices. For a table, `[reader]` is `table-curve-v1`:

- `[reader.format]` sets `kind`: `COMMA`, `TAB`, `WHITESPACE`, or `XLSX` with a `sheet`.
- `[reader.header]` sets `kind`:
  - `SKIP` with `rows`;
  - `NAMES` with `rows` and the line of `names`;
  - `NAMES_UNITS` with `rows`, the line of `names` and the line of `units`.
- `comment` holds the line prefixes to drop, for example `["#"]`.

Columns are named in `[knobs.fast]`, `[measured]` and `[measured.uncertainty]` (COLUMN or NONE): by NAME (a string) or by 1-based POSITION
(an integer).

There are two layouts in `[selection]`:

- `PER_FILE`: one curve per file.
- `LONG_TABLE`: one `file` holds every curve, and `[selection.slow]` is `COLUMN` with its `key`.

Then:

```
<host> 'cd ~/scratch/cc-intake && bin/cc intake lint <id>'
<host> 'cd ~/scratch/cc-intake && bin/cc intake seal <id> --universe ~/scratch/cc-datasets/<id> --author "<name>" --as human --unconfirmed'
<host> 'cd ~/scratch/cc-intake && bin/cc intake run <id> && cat declarations/<id>/intake-report.md'
```

Sealing is recommended and not enforced. Seal before the first run: `run` reads the data through the logged loader, and the report's
ordering note compares the seal time with the first logged read.

The reports and seals stay in the clone on the host. Copy back only what you mean to keep, with the same `<host>` command.
