# HOWTO (ADVANCED)

For someone who has done the first hour in `README.md`. Every command output below was produced by the
command shown; `…` marks lines left out. `bin/cc help --advanced` lists every command:

```
$ bin/cc help --advanced
cc - Criticality Compass   (ADVANCED)

  bin/cc show <input>                                         every reading of an input, and each point's verdict
  bin/cc explain <input> <point>                              the whole chain for one point: data -> verdict
  bin/cc run <input> | --all [--tables SET] [--dry]           measure; --dry writes nothing
  bin/cc freeze <run-id> | --all [--tables SET]               make a result and what it read read-only
  bin/cc tabulate [--diff A B]                                SIGNATURE-TABLE.md and docs/verdict-table.html
  bin/cc new case <id>                                        start a case file from the template
  bin/cc new input <id> [--like X ...]                        start an input from the template
  bin/cc data add <input>                                     pin the sha256 of an input's data files
  bin/cc tables fork <from> <to>                              copy a rulebook so you can edit it
  bin/cc tables drop <set> [--with-results]                   delete an unfrozen rulebook
  bin/cc tables split <set> --column C --value V --verdict X  override one cell family
  bin/cc validate [--input ID --tables SET | --mvt]           check every file; each problem has a Next line
  bin/cc check [--fast]                                       validate + tests; run it before a commit
  bin/cc test [-v] [<name> ...]                               run the named tests (default all)
  bin/cc mutate <relpath> (--sed E | --py E) -- <test> ...    run tests against a temporary mutation
  bin/cc help [--advanced]                                    this text
  bin/cc (v0.1) family                                        not in v0
```

Any command accepts `--advanced` to print the fuller view (the margins, how each point was obtained, per-size
cells, the verdict class, the rulebook line numbers, and the hashes of what a result read). The mode changes
what is printed, never what is computed.

## The weekly loop

Taxonomy changes (cases, joins) and rule changes (verdict rows) are data edits. The loop is:

1. **Add or change a case.** `bin/cc new case <id>`, fill the TODOs, map points to it in
   `inputs/<input>/points.toml`, `bin/cc validate`. No result changes: no result names a case.
2. **Change verdict rows.** `bin/cc tables fork verdict-x-rules <name>`, edit `tables/<name>/verdict.toml`,
   `bin/cc validate`.
3. **Re-run.** `bin/cc run --all --tables <name>` (about ten seconds for the seven inputs).
4. **Look.** `bin/cc show <input> --tables <name>`, `bin/cc explain …`, and
   `bin/cc tabulate --diff verdict-x-rules <name>`.
5. **Freeze what you keep.** `bin/cc freeze --all --tables <name>`. Drop what you do not:
   `bin/cc tables drop <name> --with-results`.
6. **Before you commit,** `bin/cc check`.

A case, shown from the start (the template is filled in by hand, then validated):

```
$ bin/cc new case potts-q4
wrote cases/potts-q4.toml
  Next: fill every TODO in cases/potts-q4.toml, map points to it in inputs/<input>/points.toml, then bin/cc validate
```

## A new input

Use this when you have new data (a new model, or the same model at new points). The easy start is a copy of an
existing input:

```
$ bin/cc new input w2b --like w2-potts --points 6,7
wrote inputs/w2b/m.toml and points.toml (like w2-potts)
  Next: fix every TODO, then bin/cc data add w2b and bin/cc validate
```

What the options do:

- `--like <input>` copies that input's `m.toml` as the starting point.
- `--points 6,7` writes the data-file blocks for these new points by renaming the file paths of the like-input's
  points, with `obtained` lines left as `TODO`; `points.toml` gets one `"TODO"` line per point. The new paths are
  guesses. `validate` names every file that does not exist, one finding per file.
- `--pattern-point P` says which point of the like-input to use as the naming pattern, when the file names
  contain the point label more than once. A path that still could not be worked out is written as `"TODO"` with
  the old path in a comment.
- `--instruments across,stability` keeps only those instruments, and drops the tables no kept instrument needs
  (see the table at the end of this section).
- Without `--like`, CC writes `inputs/TEMPLATE.m.toml.in` with every field `"TODO"`.

Then:

1. Fix every `TODO` in `inputs/<id>/m.toml` and `inputs/<id>/points.toml`. `obtained` says how each point was
   obtained: `truth` (the exact critical point), `navigated` (found by a procedure) or `observed`.
2. Put the data files where `m.toml` says, under the data root named in `cc.toml [data]`. CC never copies or
   writes data; it reads them in place.
3. `bin/cc data add <id>` writes `fixtures/data/<id>.toml`, the sha256 of every file the input reads. From then on
   `validate` refuses a mismatch. `data add` refuses to overwrite an existing manifest:

```
$ bin/cc data add w2-potts
fixtures/data/w2-potts.toml already exists.
  Next: delete it first if it is unfrozen and you mean to re-pin
```

4. `bin/cc validate`, then `bin/cc run <id>` and `bin/cc show <id>`.

**Which tables each instrument needs.** `m.toml` must contain exactly the tables its declared instruments need:
a missing one is refused and so is an unused one.

| instrument | relation | other tables | what it reads per point |
|---|---|---|---|
| needle | `matched` (big and small size) | `sinks`, `observable`, `block_map` | the level stack of the observable at the two sizes |
| across | `size` (a chain) | `conjugate`, `observable`, `block_map` | the observable and its conjugate at every size |
| stability | `size` (a chain) | `conjugate`, `observable`, `block_map` | as across |
| two_start | `start` (a pair) | `two_start` | one order parameter for each of the two starts, per size |

To change a frozen input, do not edit it. Make `<id>-2` with `--like <id>`, run `data add`, and run it as a new
input; the old results stay readable.

## Changing the rules

`bin/cc tables fork verdict-x-rules <name>` copies `codes.toml` and `verdict.toml`. Edit the copy:

- `verdicts` lists every verdict the rows may give; `refuse` lists the ones that count as refusals. A new class
  of verdict must also be added to `cc.toml [alphabets] class_truth`, or named in the table's `[class_of]`.
- Each `[[row]]` has `when.<column>` lists, a `verdict` and a `why`. A column a row omits matches every value.
- The rows must be a **partition**: no signature row in two rows, none in no row. `validate` expands every row
  and prints each uncovered or doubly covered pattern as a ready-made `when` block (see the Tutorial).

`bin/cc tables split <set> --column C --value V --verdict X` makes the common edit mechanically, "whenever C
reads V, the verdict is X", and keeps the partition:

```
$ bin/cc tables split mine --column two_start --value UNRES --verdict REFUSE-EQUIL
split touched 3 rows (20 rows now)
tables/mine/verdict.toml: clean
```

**When not to use it.** `split` sends every cell with that value to one verdict, including cells whose needle
or flow had already decided otherwise (here it also moves needle DIS and ORD cells from NOT to REFUSE-EQUIL).
It cannot say "this value, but only when the needle is MID". For a narrower change edit the rows by hand, as
Part 2 of the Tutorial does.

It rewrites `verdict.toml` in a canonical form: the header comment stays, comments between rows do not, so
put the meaning in each row's `why`. `drop` refuses the default rulebook, and a frozen one (it names the results that depend on it):

```
$ bin/cc tables drop verdict-x-rules
REFUSED: tables/verdict-x-rules is the default rulebook (cc.toml [defaults] tables).
  Next: change [defaults] tables in cc.toml first, or drop another set
```

## Freezing

A result is written once by `bin/cc run`, under the id `<input>@<set>`. Freeze it when you accept it:
`bin/cc freeze <input>@<set>` or `bin/cc freeze --all --tables <set>`. Freezing makes read-only, each one
individually, the result's `.json` and `.npz` and exactly the files its `read` lists (its `m.toml`, its
instrument files, its data manifest), plus the rulebook directory it ran under. It records their hashes in
`FROZEN.json`.

What stays editable, by design: every `points.toml`, every `cases/*.toml`, `cc.toml`, the templates,
`expected/`, `tests/golden/`. Taxonomy is never frozen, so a new idea about what a point is never needs a fork.

A frozen id is never re-run; a different table set is a different id:

```
$ bin/cc run w2-potts
REFUSED: results/w2-potts@verdict-x-rules.json is frozen (a frozen result never changes).
  Next: bin/cc tables fork verdict-x-rules <new-name>, edit tables/<new-name>/verdict.toml, then bin/cc run w2-potts --tables <new-name>
```

`--dry` is always allowed. `freeze` on something already frozen is harmless:

```
$ bin/cc freeze w2-potts@verdict-x-rules
froze 0 files, 0 dir for w2-potts@verdict-x-rules
```

If a frozen file's hash no longer matches (you edited it), `run` and `freeze` refuse with the file's name and
`Next: git checkout -- <file>`. `show`, `explain` and `tabulate` re-hash everything a result read, so an old
result stays readable exactly as long as what it read is unchanged. `bin/cc check` refuses a frozen file whose
hash has changed.

## Reading the whole rulebook, and comparing two

```
$ bin/cc tabulate
tabulate: 7 results -> SIGNATURE-TABLE.md, docs/verdict-table.html
```

`SIGNATURE-TABLE.md` lists every result's points with their codes, verdict and (here, and only here) the
truth class from the case, so you can see where the rulebook and the taxonomy agree. `docs/verdict-table.html`
is one static page you can open in a browser: for each rulebook, its rows grouped by verdict class, each row
with its `why`, its line number, how many signature rows it covers, the fixture points that hit it, and the
rows no result ever hit.

`bin/cc tabulate --diff A B` compares two rulebooks on every signature row and on every fixture point that has a
result under both:

```
$ bin/cc tabulate --diff verdict-x-rules scratch
1512 cells change verdict between verdict-x-rules and scratch
REFUSE-EQUIL -> LINE: 6 cells in 1 patterns
  when.needle = ["MID"]; when.flow = ["STOPPED"]; when.across = ["MARGINAL"]; when.stability = ["STABLE"]; when.two_start = ["UNRES"]
…
0 fixture points change verdict
tabulate: 7 results -> SIGNATURE-TABLE.md, docs/verdict-table.html
```

(Here `scratch` is the forked rulebook of the Tutorial, with no run yet; after `run --all --tables scratch` the
fixture-point line compares real results.) A point-level difference prints as `input:point  OLD -> NEW`.
A result whose rulebook file changed after it was run is refused with the `run` command to repeat.

## What validate says

```
$ bin/cc validate
tables/scratch/verdict.toml: 1512 uncovered cells in 1 patterns
  [[row]]
  when.needle = ["MID"]
  when.two_start = ["UNRES"]
  Next: add a [[row]] with one of these when-lines, or widen a neighbouring row
validate: 1 findings
exit 1
```

Each finding is `<file>:<key>: <what is wrong>` followed by `Next: <what to do>`. The common ones:

| finding | what to do |
|---|---|
| `…: still TODO` | replace the placeholder with the real value |
| `inputs/<id>/points.toml:points."4": unknown case 'potts-4'` | create the case (`bin/cc new case potts-4`) or map the point to an existing case or `"none"` |
| `<file> does not exist under the data root` | fix the path in `m.toml`, or put the file there |
| `N uncovered cells` / `N doubly covered cells` | add or widen a row, using the printed `when` block |
| `… changed since it was pinned` | the data file changed since `data add`; investigate before you re-pin |
| `… changed after it was frozen` | `git checkout -- <file>`, then fork instead of editing |

`bin/cc validate --input <id> --tables <set>` checks one input under one rulebook. `bin/cc validate --mvt`
reports, and changes nothing, on whether the cases and rulebook are enough to make a minimum viable test:

```
$ bin/cc validate --mvt
validate: clean
-- MVT gate (report only; no status is changed)
  PASS  1 POINT: >= 2 in-table cases with different mechanisms :: 4 case(s) ['bc-lambda-line', 'ising-2d', 'nnn-ising-manifold', 'potts-q3'], 4 distinct mechanism(s)
…
  FAIL  5 signature table enumerated over every in-table case, collisions listed :: 17 in-table case(s); collisions section present; missing ['ar1-null', 'bc-tricritical', 'nnn-ising-manifold', 'potts-q6', 'potts-q7']
-- MVT FAIL
```

## Tests, mutations and the testing system

`bin/cc check` runs `validate`, every test and the scoreboard (about a minute); `bin/cc check --fast`, which the
pre-commit hook runs, skips the slow tests. `bin/cc test` runs every test, `bin/cc test <name> …` the named
ones, `-v` prints each test's lines. Tests are plain scripts, and a test that cannot find its data fails with
the path; none skips.

What each kind of test protects (the test files are in `tests/`):

| kind | what it protects | goes red when |
|---|---|---|
| unit (kernel, sign, resample, kernel_rs, budget, tables_cli, view) | the arithmetic and the commands | a named change to the code |
| regression (the four fixture replays, detect_verdicts, verdict_equivalence, tabulate) | the first measurements CC was built to reproduce | a frozen number, cell or verdict moves |
| door breakers (test_declare, `tests/planted/`) | the file checks | a deliberately bad plugin file is accepted, or its message changes |
| rule breakers (`tests/breakers/*.toml`) | the verdict table's meaning | a synthetic reading gets the wrong verdict |
| scoreboard lock (`expected/<set>.toml`) | every point's verdict | any point's verdict changes |
| golden transcripts (`tests/golden/`) | the exact text of each command | any byte of a command's output changes |

**Adding a rule breaker is a data file.** Copy any file in `tests/breakers/`: it states a synthetic reading (a
vector of numbers, or a set of cells), the cell, code and verdict it must give, and a `[mutation]` (a
one-line edit to a rulebook file that should make it fail, which `test_breakers_red` actually applies).

**Changing an expected verdict is a reviewed edit.** The scoreboard holds the verdict CC gives, not the truth.
When a point's verdict has to change, change its line in `expected/<set>.toml` and append a `[[change]]` with the
date, the points and a `why`. A verdict you edit without a `why` is refused by a test.

**Regolden.** When a command's output changes on purpose, `bin/cc test --regolden test_golden` rewrites the
differing transcripts under `tests/golden/` and lists every file it wrote. Read each one (`git diff tests/golden/`)
before you commit; `bin/cc check` never regoldens. A transcript that changes by a time, a date or a path is a
bug in the command, not a reason to regolden.

**Mutation.** To see that a test can fail, mutate a copy:

```
bin/cc mutate tables/verdict-x-rules/codes.toml --sed 's/"SIG+" = "COEXIST"/"SIG+" = "INDEP"/' -- test_breakers
```

It copies the repo to a temporary directory, applies the edit there (the frozen file too, in the copy only),
runs the named tests there, prints RED or GREEN for each test, and deletes the copy. Your tree is never changed.
For this edit it prints `RED   test_breakers`, with two breakers named as broken.

## Routine edits

| edit | files touched | what validates | code change | old results readable |
|---|---|---|---|---|
| new case, existing points | `cases/<id>.toml`; join lines in `inputs/*/points.toml` | case schema, join | none | yes: no result names a case |
| new model, existing layout | `new input --like --points`; `data add`; its `points.toml` | `m.toml` against the instrument contracts; hashes | none | yes: a new input id |
| change verdict rows / new class | `tables fork`; the copy's `verdict.toml` (`verdicts`, `refuse`, rows); a new class also in `cc.toml alphabets.class_truth` | partition; class derivation | none | yes: the old set is frozen and untouched |
| split a verdict | `tables split`, or by hand: one row becomes rows partitioning its cells | partition | none | yes |
| remove or rename a case | the case file; the join lines; `pairs_with` lines (validate lists each) | full validate names every stale id | none | yes: `UNJOINED` until fixed |
| change a frozen input | `new input <id>-2 --like <id>`; `data add` | as for a new model | none | yes |

A new instrument, or a new kind of sidecar table, is a code change. That is v0.1.

## Known limits of v0

Read these before you trust a verdict.

- **No real input has yet reached a positive class.** The seven inputs hold 60 points; their verdicts are NOT (14 points),
  REFUSE-NEEDLE-UNMEASURED (36), REFUSE-SLOW (8), REFUSE-TWO-START-UNMEASURED (1) and REFUSE-UNRES (1).
  POINT, LINE, WALKING and FIRST-ORDER appear in no real result. Only the synthetic rule breakers exercise
  those rows of the rulebook, so the rows are tested but have never been seen on data. Do not read "no
  positive" as "nothing is critical".
- **REFUSE-SLOW on x2 and x3 is a flaw in the rulebook, locked as today's behaviour.** On the XY and clock
  models, the points whose true class is LINE read a needle at the window and a flow that is resolved but
  smaller than the margin (`SLOW`). The rulebook's STAGE3 row sends that to REFUSE-SLOW: a critical line whose
  block flow is small but resolved is refused and never called LINE. That is a line read as if it were the end
  of a BKT line. `expected/verdict-x-rules.toml` records it with a `why`; the repair is a forked rulebook in
  v0.1, not an edit of the lock.
- **x4's FIRST-ORDER-LINE is not reproduced.** In the study, the X4 first-order line came from a separate
  statistic, a table of where the response to the field h crosses, which CC has no instrument for. CC's own
  pipeline puts the needle at the ordered sink there and reads NOT.
- **The weekly-loop gaps** found by using `new input` and `new case` for the first real inputs:
  - `new input --like` cannot retarget the data folder or the file-label format (ninety file blocks were
    written by script), and cannot add an instrument: the needle, the matched relation, the sinks and the
    margins are written by hand;
  - the `new case` template has no `breaker_verdict` field;
  - `obtained` and `points` are written as `TODO` and must be filled by hand;
  - one message was unhelpful: an observable-levels finding whose real cause was in the code (the check now
    applies to the two observable kinds that need it).
- **Along-the-line measurement, and re-verdicting without re-measuring, are v0.1.** Every point is read alone,
  and a new rulebook is applied by running again (seconds, but a new result id each time).
