# HOWTO (ADVANCED)

For someone who has done the first hour in `README.md`. Every command output below was produced by the
command shown; `…` marks lines left out. `bin/cc help --advanced` lists every command:

```
$ bin/cc help --advanced
cc - Criticality Compass   (ADVANCED)

  bin/cc show <input>                                         every reading of an input, and each point's verdict
  bin/cc explain <input> <point>                              the whole chain for one point: data -> verdict
  bin/cc run <input> | --all [--tables SET] [--dry]           measure; --dry writes nothing
  bin/cc reverdict <input> --tables SET [--from SET]          re-verdict a stored result under another rulebook; measures nothing
  bin/cc freeze <run-id> | --all [--tables SET]               make a result and what it read read-only
  bin/cc tabulate [--diff A B]                                write SIGNATURE-TABLE.md + docs/verdict-table.html; --diff prints only
  bin/cc new case <id>                                        start a case file from the template
  bin/cc new input <id> [--like X ...]                        start an input from the template; --like also takes --points --data-dir --label-format --add-instrument
  bin/cc new instrument <id>                                  start an instrument (registry file + stub module) from the template
  bin/cc data add <input>                                     pin the sha256 of an input's data files
  bin/cc tables fork <from> <to>                              copy a rulebook so you can edit it
  bin/cc tables drop <set> [--with-results]                   delete an unfrozen rulebook
  bin/cc tables split <set> --column C --value V --verdict X  override one cell family
  bin/cc validate [--input ID --tables SET | --mvt]           check every file; each problem has a Next line
  bin/cc check [--fast | --baseline]                          validate + tests; run it before a commit (two tiers, see Tests)
  bin/cc test [-v] [<name> ...]                               run the named tests (default all)
  bin/cc mutate <relpath> (--sed E | --py E) -- <test> ...    run tests against a temporary mutation
  bin/cc help [--advanced]                                    this text
  bin/cc family <id> [--tables SET]                           the family verdict (bracket, f1, f2) of a stored result; measures nothing
  bin/cc new family <id>                                      start a family declaration from the template
```

Any command accepts `--advanced` to print the fuller view (the margins, how each point was obtained, per-size
cells, the verdict class, the rulebook line numbers, and the hashes of what a result read). The mode changes
what is printed, never what is computed.

## The weekly loop

Taxonomy changes (cases, joins) and rule changes (verdict rows) are data edits. The loop is:

1. **Add or change a case.** `bin/cc new case <id>`, fill the TODOs (a case file has an optional
   `breaker_verdict` for a pre-registered breaker; leave it empty otherwise), map points to it in
   `inputs/<input>/points.toml`, `bin/cc validate`. No result changes: no result names a case.
2. **Change verdict rows.** `bin/cc tables fork v01-rules <name>`, edit `tables/<name>/verdict.toml`,
   `bin/cc validate`. (`v01-rules` is the working rulebook, the one `bin/cc help` names under `rules in use`.)
3. **Re-verdict or re-run.** If your change touched only `verdict.toml` or `codes.toml`, the readings do not change:
   `bin/cc reverdict <input> --tables <name>` applies the new rules to the stored readings, in seconds, with no
   measurement (see "Re-verdicting without measuring" below). Otherwise `bin/cc run --all --tables <name>` measures
   again (about half a minute for the eleven inputs).
4. **Look.** `bin/cc show <input> --tables <name>`, `bin/cc explain …`, and
   `bin/cc tabulate --diff v01-rules <name>`.
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
- `--data-dir <dir>` and `--label-format '<pattern>'` retarget the data map of a `--like` input: the folder under the
  data root, and the file-name pattern, which may use only `{label}` (the point), `{size}` and `{start}`. Without them
  the like-input's folder and names are kept. A pattern with any other `{...}` is refused with the form to write.
- `--add-instrument <id>` adds one instrument to a copy of the like-input: its blocks are written with `TODO`
  values that `validate` refuses one by one, each with a Next line, so nothing runs half-declared.
- Without `--like`, CC writes `inputs/TEMPLATE.m.toml.in` with every field `"TODO"`.

A copy of `b7-at-line` that gains the `along` instrument:

```
$ bin/cc new input b7c --like b7-at-line --add-instrument along
wrote inputs/b7c/m.toml and points.toml (like b7-at-line)
  Next: fix every TODO, then bin/cc data add b7c and bin/cc validate
```

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
| along | `size` (a chain) and `control` (a declared relation over the points) | `observable`, `block_map` | the observable of both points of a pair, at every size |
| fluct | `size` (a chain) | `two_start` (its `unit_scale`) | the energy `E` at every size, from the main start |
| needle_chain | `chain` (template `matched-chain`: the pairs `[[243, 81], [81, 27]]`) and `size` | `observable`, `block_map`, and `[eps] drift` | the level stacks at three sizes: the needle's velocity at two size pairs, and how it decays |

Under `v04-rules` every input also needs `inputs/<id>/couplings.toml` (see "Probe completeness" below); `new input` does not
write it, and `validate` names a missing one.

To change a frozen input, do not edit it. Make `<id>-2` with `--like <id>`, run `data add`, and run it as a new
input; the old results stay readable.

## A new input over raw snapshots (a stack format, plan 0873)

Use this when the data are the raw configurations `s[N, L, L]` (N snapshots of an L x L lattice), not a stored observable. CC reduces the stack
itself: the declared `[block_map]` blocks each snapshot down to `[observable] final_size` and the observable (`g1`) is read at every level,
so `G` (one level) and `GL` (every level) are computed from the snapshots, never trusted from a file. The format is a name in `data.format`:

| `data.format` | the file | reader |
|---|---|---|
| `snapshots-v1` | `.npy`, or `.npz` with the stack under a key; integer spins `s[N, L, L]` | numpy |
| `image-stack-v1` | `.npy` or `.tif` / `.tiff`; `uint8` `[N, L, L]` | numpy; `tifffile` for TIFF (if it is not installed `validate` refuses with `pip install tifffile` and the `.npy` alternative; nothing is skipped) |

The schemas (dims, dtypes, which array kinds are reduced, which reader for which extension) are DATA in `cc.toml [formats.<name>]`.

1. Copy the working stack input: `bin/cc new input <id> --like x4s-stack` (add `--instruments needle,across` to keep fewer instruments;
   it drops the tables they do not need). That writes a complete `m.toml` (nothing to edit unless the data differ) and a `points.toml`
   whose `"0.46" = "TODO"` line you replace with a case id: `ising-field-decoy` (the like-input's).
2. In `m.toml` each `[[data.files]]` block names the stack: `arrays.GL = { key = "S" }` (every level) and `arrays.G = { key = "S", level = 2 }`
   (one level) are REDUCED from the stack under `key`; `arrays.E = { key = "O", level = 0 }` is an ordinary stored column read as before.
3. Declare the geometry: `[observable] final_size` and `[block_map] factor` must satisfy `L = final_size * factor^k` for every size, and
   `observable.levels` is the derived `k + 1` (validate refuses a disagreement, naming both numbers). `block_map.name` is `majority3`
   (3x3 majority of +-1 spins) or `mean3` (block mean of a real field).
4. `bin/cc data add <id>` pins the raw files. `new input` does NOT write `inputs/<id>/couplings.toml`: copy it from the like-input by hand and change `id`.
5. `bin/cc validate`, then `bin/cc run <id> --tables v07-rules`. Keep `needle` among the instruments: `stability` and the verdict
   read it (a stack input without `needle` reads `REFUSE-NEEDLE-UNMEASURED`, an honest refusal, not an error).

The first run, `--dry` included, reduces the stacks (about 8 s for the three files alone; a minute or more when the machine is busy) and keeps the result under `results/reduced/<id>/<sha>.npz`; the
name is the sha of the raw file, the code hash, the key, the map and the level count, so a changed file or changed code reduces again. It is a build
cache: git ignores it and deleting it changes nothing. A block map that is not a measured site per cell (`block_map.limited = "assigned"` or
`"resolution-limited"`) must also declare `[observable] level_floor = 1`: level 0 is then excluded, and validate refuses a limited input that keeps it.
There is no interpolation option, flagged or not: a value is either a measured site or a declared assignment of one.

## Changing the rules

`bin/cc tables fork v01-rules <name>` copies the rulebook: `codes.toml`, `verdict.toml`, and the two files the
v0.1 instruments read, `membership.toml` and `family.toml` (see below). Edit the copy:

- `verdicts` lists every verdict the rows may give; `refuse` lists the ones that count as refusals. A new class
  of verdict must also be added to `cc.toml [alphabets] class_truth`, or named in the table's `[class_of]`.
- Each `[[row]]` has `when.<column>` lists, a `verdict` and a `why`. A column a row omits matches every value.
- The rows must be a **partition**: no signature row in two rows, none in no row. `validate` expands every row
  and prints each uncovered or doubly covered pattern as a ready-made `when` block (see the Tutorial).

`bin/cc tables split <set> --column C --value V --verdict X` makes the common edit mechanically, "whenever C
reads V, the verdict is X", and keeps the partition:

```
$ bin/cc tables split mine --column two_start --value UNRES --verdict REFUSE-EQUIL
split touched 3 rows (22 rows now)
tables/mine/verdict.toml: clean
```

**When not to use it.** `split` sends every cell with that value to one verdict, including cells whose needle
or flow had already decided otherwise (here it also moves needle DIS and ORD cells from NOT to REFUSE-EQUIL).
It cannot say "this value, but only when the needle is MID". For a narrower change edit the rows by hand, as
Part 2 of the Tutorial does.

It rewrites `verdict.toml` in a canonical form: the header comment stays, comments between rows do not, so
put the meaning in each row's `why`. `drop` refuses the default rulebook, and a frozen one (it names the results that depend on it):

```
$ bin/cc tables drop v01-rules
REFUSED: tables/v01-rules is the default rulebook (cc.toml [defaults] tables).
  Next: change [defaults] tables in cc.toml first, or drop another set
exit 1
```

## Re-verdicting without measuring

A rule change that touches only `verdict.toml` or `codes.toml` cannot change a reading: the intervals and sign
cells come from the data, the rules only translate them. `reverdict` applies a rulebook to a stored result and
measures nothing:

```
$ bin/cc reverdict w2-potts --tables rv
reverdict w2-potts@v01-rules -> results/w2-potts@rv.json (no instrument was run)
w2-potts   rules: rv   result: results/w2-potts@rv.json (not frozen)
…
point 5   case potts-q5
  sink       BLANK (NOT-MEASURED: needle is not declared on this input)
  needle     BLANK (NOT-MEASURED: needle is not declared on this input)
  flow       BLANK (NOT-MEASURED: needle is not declared on this input)
  across     1.679 [1.417, 1.932] SIG+ -> RELEVANT
  stability  0.08076 [-0.3098, 0.5382] BLANK (UNRES: interval straddles 0 and a margin edge)
  two_start  BLANK (UNRES: interval straddles 0 and a margin edge)
  => verdict NOT
     why: honest null (not in verdict_x): the needle was not measured or not evaluated
```

(Here `tables/rv` is a fork of `v01-rules` in which the "needle not measured" row was changed to `NOT`; the
`…` hides the other points.) The result is written as `results/<input>@<set>.json` with a field `derived_from`
naming the result it came from. It has no `.npz` of its own: its resample vectors are the parent's, and
`freeze` handles that. Without `--from SET`, the readings come from the result under the default rulebook.

`reverdict` refuses when it cannot be sure the readings still hold, and says what to do instead:

- the stored result is missing: run the input first;
- the target result is frozen: pick another set;
- the new set differs from the old one in `membership.toml`. Membership decided which units of the input ran
  at all, so a different rule can mean units that were never measured:

```
$ bin/cc reverdict b7-at-line-2 --tables rv
REFUSED: tables/rv changes membership.toml, which decided which units of b7-at-line-2 ran.
  Next: re-measure with bin/cc run b7-at-line-2 --tables rv
exit 1
```

A reverdict under a set reproduces exactly what `run` would have written there (a test compares them), which
is why it is safe to use for the weekly loop and why it is not a way to avoid re-measuring when the instruments
change.

## Along, and membership as a door value

The `along` instrument reads a **pair** of points. For each edge of a declared control relation (`[relations.control]`
in `m.toml`, a chain over the points in their declared order) it takes the difference of the observable of the
two points at each lattice size, `Delta(L)`; it then takes `ln|Delta|`, A over the size chain, B accumulates the
step along the chain, and the result is divided by the log of the size span: `y_along`. That is the growth with
size of the difference between two neighbouring points. It is coded by its sign cell like any reading (the cuts
are `-0.25 0 +0.25`, `y`). If the sign of `Delta` is not the same at the estimate and at every resample, the logarithm
is not defined and the pair reads `NOT-EVALUATED`, with its reason.

Not every pair means something: along a line it should be taken between points that are **on the manifold**. A
point is on it when its needle reads MID, and that is a rule you can change, so it is a table-set file,
`tables/<set>/membership.toml`:

```
[along]
reads = "needle"        # the signature column whose per-point code decides membership
map = { DIS = "OFF", ORD = "OFF", MID = "ON", NOT-MEASURED = "UNCHECKED", NOT-EVALUATED = "NOT-EVALUATED" }
rank = ["OFF", "NOT-EVALUATED", "UNCHECKED", "ON"]
door = { OFF = "REFUSE-OFF-MANIFOLD", NOT-EVALUATED = "NOT-EVALUATED", UNCHECKED = "RUN-FLAG-U", ON = "RUN" }
```

A pair takes the **lowest-ranked** membership of its two points, and that membership is looked up in `door`. The
door values:

| membership of the pair | door value | what happens |
|---|---|---|
| OFF (a point reads DIS or ORD) | `REFUSE-OFF-MANIFOLD` | the pair is not computed; its reading is BLANK with that value |
| NOT-EVALUATED | `NOT-EVALUATED` | not computed; the needle of a point could not be evaluated |
| UNCHECKED (the needle was not measured) | `RUN-FLAG-U` | computed, and the pair carries flag U: membership unchecked |
| ON (both points read MID) | `RUN` | computed |

Which codes count as ON is a taxonomy decision, and changing it changes which units are measured, which is why a
reverdict across two different membership files is refused. A set without a membership file for an instrument that
needs one is refused by `validate`, with the way out:

```
$ bin/cc validate --input b7-at-line-2 --tables nomem
tables/nomem/membership.toml:along: along runs door:off_manifold on b7-at-line-2 but this set has no rule for it
  Next: copy tables/v01-rules/membership.toml into tables/nomem/, or fork from v01-rules (bin/cc tables fork v01-rules <new-name>)
validate: 1 findings
exit 1
```

`show` prints the pairs after the points, and `explain <input> <pair>` gives the pair trace: the membership
door, `Delta` per size, A then B, the interval against the margin, the cell, and the code the family gives it.
It reads the stored result; nothing is measured again. A pair that ran:

```
$ bin/cc explain b7-at-line-2 0.14->0.21
explain b7-at-line-2 0.14->0.21   rules: v01-rules
along   (pair 0.14->0.21)
  1 MEMBER    membership.toml [along] reads needle: 0.14 NOT-MEASURED -> UNCHECKED, 0.21 NOT-MEASURED -> UNCHECKED; lowest rank decides -> door RUN-FLAG-U   flags: truth point, membership unchecked (the upstream needle was not measured)
  2 DELTA     A over the control edge 0.14->0.21, row 0: 27 0.05402, 81 0.05431, 243 0.04232
  3 KERNEL    ln|Delta| [-2.918, -2.913, -3.162]; A over size [0.005433, -0.2495]; B at the top edge -0.244; over the log span 2.197: -0.1111
  4 READING   y_along -0.1111  interval [-0.2479, 0.005093]  (95 %, 400 block resamples)
  5 SIGN      cuts -0.25 0 +0.25 (eps y): bL 1, bU 2 -> ZERO!
  6 CODE      family.toml line 52 [f2.code]: ZERO! -> MARGINAL
```

and one the door refused (on `x7a-bc` the needle reads DIS at both points, so the pair is off the manifold):

```
$ bin/cc explain x7a-bc 1.0->1.5
explain x7a-bc 1.0->1.5   rules: v01-rules
along   (pair 1.0->1.5)
  1 MEMBER    membership.toml [along] reads needle: 1.0 DIS -> OFF, 1.5 DIS -> OFF; lowest rank decides -> door REFUSE-OFF-MANIFOLD   flags: navigated point
  2 READING   REFUSE-OFF-MANIFOLD
```

## Families

A **family** is several points of one input read together (the Tutorial's Part 3 reads one). It has two parts:

- `families/<id>.toml`, the declaration: the input, and the `interior` points in the order along the family. A
  family names no rulebook. `bin/cc new family <id>` starts one:

```
$ bin/cc new family b7-demo
wrote families/b7-demo.toml
  Next: replace every TODO (an input and its interior points), then bin/cc validate and bin/cc family b7-demo
```

  Fill every `TODO` (an input and at least two of its points); `validate` refuses any left. One input per family
  in v0.1, and control edges only if the input declares `along`.

- `tables/<set>/family.toml`, the rules: three columns (`bracket`, `f1`, `f2`), each with an alphabet that includes
  `UNRES`, `NOT-EVALUATED` and `NOT-MEASURED`; how each column is read (`[bracket]`, `[f1]`, `[f2]`); and `[[row]]`
  blocks that partition the product of the three alphabets into family verdicts, exactly as `verdict.toml` does for
  points. `validate` checks the partition is total and disjoint. How an `along` cell becomes an f2 code (ZERO! is
  MARGINAL, SLOW+ is WEAK, and so on) is the `code` map in `[f2]`; the f1 map is `[f1] code`; neither lives in `codes.toml`.

`bin/cc family <id> [--tables SET]` prints the family verdict from the stored result. It re-measures nothing, and
refuses with a Next line if the set has no `family.toml` or the input has no result under the set. A family
whose points the membership door refuses reads that, rather than a class:

```
$ bin/cc family x7a-bc-lambda
family x7a-bc-lambda   rules: v01-rules   input: x7a-bc   interior: 0.0 1.0 1.5 1.8 1.9 1.95
  bracket NON-MONOTONE
    edge 0.0->1.0 DESCENT
    edge 1.0->1.5 NO-DESCENT
    edge 1.5->1.8 NO-DESCENT
    edge 1.8->1.9 NO-DESCENT
    edge 1.9->1.95 DESCENT
  f1      NOT-MEASURED
  f2      REFUSE-OFF-MANIFOLD
    0.0->1.0 along REFUSE-OFF-MANIFOLD  -> REFUSE-OFF-MANIFOLD
    1.0->1.5 along REFUSE-OFF-MANIFOLD  -> REFUSE-OFF-MANIFOLD
    1.5->1.8 along REFUSE-OFF-MANIFOLD  -> REFUSE-OFF-MANIFOLD
    1.8->1.9 along REFUSE-OFF-MANIFOLD  -> REFUSE-OFF-MANIFOLD
    1.9->1.95 along REFUSE-OFF-MANIFOLD  -> REFUSE-OFF-MANIFOLD
  => family verdict REFUSE-OFF-MANIFOLD   class REFUSE, family.toml line 60
     why: X7a: a member point off the manifold at L 243 (it also explains a non-monotone bracket, so it is read first by partition)
```

(The Blume-Capel lambda sweep: the needle reads DIS at two points, so no pair is on the manifold and f2 is the
door value; the family verdict is a refusal, not LINE.)

## LINE-END families (v05-rules, plan 0871)

A line of fixed points can END: the XY low phase is a line up to T_KT, then the sweep meets a disordered sink. `v05-rules` reads
that from a family, with four additions to the three columns above (all in `tables/v05-rules/family.toml`; nothing in v01 to v04
changes):

- **The bracket is direction-agnostic.** `bracket` is `BRACKET-UP` (the needle steps from a lower to a higher sink along the chain),
  `BRACKET-DOWN`, `BRACKET-FLAT` (a MID chain with no step), `NON-MONOTONE` (an ascent AND a descent) or `NO-MID`. A T-ordered chain
  reads `BRACKET-DOWN` here where v01 to v04 refused it; the direction comes from the declared chain, never from an assumption.
- **`points`** is LINE only when every interior point reads per-point LINE (the geometry after the probe).
- **`lower` and `upper` are the two SIDES** of the declared interior: the points of `axes.point` before the first and after the last
  `interior` point. The side's **boundary** is the last point of the contiguous run of MID needles that reaches outward from the
  interior's edge point (positional, no threshold); the points past it are the **beyond** points. A side reads, from the boundary
  (needle MID, flow STOPPED, SLOW or UNRES) and the beyond points (every needle a sink, DIS or ORD):
  - the **end kind**, decided by the beyond points' ORDER axis and `two_start`: `END-BKT-CANDIDATE` (the starts agree, order OFF-WINDOW),
    `END-MULTICRITICAL` (the starts stay apart: the AT 4-Potts lookalike), `END-ORDER-UNMEASURED` (one start only);
  - `OPEN` (no points on that side), `NO-END` (a MID point re-appears after a sink), or `UNRES` / a null.
- **`end_point` and `end_bracket`.** The family names the boundary of each side that ENDS a line (`end_point`) and the pair
  (boundary, first beyond point) (`end_bracket`).

The verdict rows: interior LINE and a side `END-BKT-CANDIDATE` is `BKT-END`; interior LINE with only an `END-MULTICRITICAL` side, or with no
readable end (both sides OPEN or END-ORDER-UNMEASURED), is `LINE`, the sides reported beside it; an f2 that reads `REFUSE-OFF-MANIFOLD`
reads `REFUSE-OFF-MANIFOLD` whatever the points and sides say (plan 0871 G6: a member point off the manifold is a fact about the chain).
Every other cell reads what v04-rules read.

**End-bracket scoring.** The grid cannot place an end closer than its spacing, so an end is a BRACKET, not a point. `bin/cc tabulate`
adds a **Family ends** section for a family whose input joins a `BKT-END` truth point (the case `xy-tkt`): the truth point scores `agree`
when it lies inside the family's `end_bracket`, `disagree` when it does not (or the family reads LINE, or a non-BKT-END class), and
`refused` when the family refuses. A refusal is a miss, never an agreement.

**Two caveats the rule cannot remove.**

- *An off-manifold step reads the same as an end.* A sweep that leaves its manifold (a decoy) shows a MID run followed by a sink run just
  as a real end does; the family cannot tell. Only the declaration and a blind decoy can. The `why` of every BKT-END row says so.
- *BKT finite-size: xi is larger than L just above T_KT.* The BKT correlation length is xi ~ exp(b / sqrt(t)) with t = (T - T_KT) / T_KT; with
  b of order 1.5 it is already about 400 sites at T = 0.95, more than the largest size here (L = 243). A block-lattice needle can still read
  the sign of its velocity there (DIS, SIG-), but a family whose first beyond point lies a long way above T_KT reads an end bracket that
  is too high. An `end_bracket` that does not contain T_KT is a finite-size MISS and is recorded as one.

`families/x2b-xy.toml` reads the XY sweep X2b (nine T from 0.5 to 1.1, interior T <= 0.85). As it was read:

```
$ bin/cc family x2b-xy --tables v05-rules
family x2b-xy   rules: v05-rules   input: x2b-xy   interior: 0.5 0.6 0.7 0.8 0.85
  bracket BRACKET-DOWN
    edge 0.5->0.6 NO-DESCENT,NO-ASCENT
    edge 0.6->0.7 NO-DESCENT,NO-ASCENT
    edge 0.7->0.8 NO-DESCENT,NO-ASCENT
    edge 0.8->0.85 NO-DESCENT,NO-ASCENT
    edge 0.85->0.89294 NO-DESCENT,NO-ASCENT
    edge 0.89294->0.95 DESCENT,NO-ASCENT
    edge 0.95->1.0 NO-DESCENT,NO-ASCENT
    edge 1.0->1.1 NO-DESCENT,NO-ASCENT
  f1      UNRES
    0.5->0.6 y_last +0.130 [-0.042, +0.290] UNRES  -> UNRES
    0.5->0.7 y_last +0.024 [-0.146, +0.178] ZERO!  -> CONSTANT
    0.6->0.7 y_last -0.106 [-0.253, +0.041] UNRES  -> UNRES
    0.5->0.8 y_last +0.056 [-0.087, +0.221] ZERO!  -> CONSTANT
    0.6->0.8 y_last -0.074 [-0.201, +0.055] ZERO!  -> CONSTANT
    0.7->0.8 y_last +0.032 [-0.095, +0.160] ZERO!  -> CONSTANT
    0.5->0.85 y_last +0.113 [-0.058, +0.270] UNRES  -> UNRES
    0.6->0.85 y_last -0.017 [-0.158, +0.136] ZERO!  -> CONSTANT
    0.7->0.85 y_last +0.089 [-0.061, +0.226] ZERO!  -> CONSTANT
    0.8->0.85 y_last +0.057 [-0.076, +0.198] ZERO!  -> CONSTANT
  f2      WEAK
    0.5->0.6 along SLOW-  -> WEAK
    0.6->0.7 along SLOW-  -> WEAK
    0.7->0.8 along SLOW-  -> WEAK
    0.8->0.85 along ZERO!  -> MARGINAL
  points  NOT-LINE
    0.5 geometry LINE  -> LINE
    0.6 geometry WALKING  -> NOT-LINE
    0.7 geometry LINE  -> LINE
    0.8 geometry LINE  -> LINE
    0.85 geometry LINE  -> LINE
  lower   OPEN   boundary 0.5, beyond (none)
    reads boundary_needle MID, boundary_flow STOPPED, beyond_needles NONE, beyond_order NONE  -> family.toml side_row line 510
    why: no point lies on this side of the declared interior
  upper   END-BKT-CANDIDATE   boundary 0.89294, beyond 0.95 1.0 1.1
    reads boundary_needle MID, boundary_flow STOPPED, beyond_needles SINK, beyond_order INDEP  -> family.toml side_row line 560
    why: plan 0871 E2: the boundary is MID (flow stopped, slow or unresolved: at T_KT the flow is marginal-slow), every point beyond it is a sink (sink-agnostic: a clock's lower end exits to ORD) and the starts AGREE there (OFF-WINDOW, two_start INDEP): the end of a line, a BKT candidate. A sweep that steps off its manifold reads the same (review 3.2.2)
  end     0.89294 (bracket 0.89294 .. 0.95)
  => family verdict REFUSE-UNCLASSIFIED-v0   class REFUSE, family.toml line 448
     why: 0863: no positive row yet (0862 X7b/X2-X4 decide)
```

Read the lines in order. `f1` and `f2` combine their pair codes by a declared rank (`[f1] rank`, `[f2] rank` in `family.toml`): for f1 one resolved
VARIES pair is enough while CONSTANT needs every pair CONSTANT, so a single UNRES pair makes the column UNRES; f2 reads its weakest pair the same way.
The interior is NOT-LINE because T 0.6 reads WALKING (see Known limits). `lower OPEN` is a statement about the grid, not about the physics: no point
of the sweep lies below the interior (the printed boundary and reads on that line are just the interior's edge point). The upper side is
`END-BKT-CANDIDATE`: the boundary is 0.89294 (its needle still reads MID, flow STOPPED) and every point past it is a DIS sink (a sink is a needle that
left the window, DIS disordered or ORD ordered) whose two starts agree. The `end` line prints `end_point` first and `end_bracket` in brackets after it.
`end_bracket` is `[0.89294, 0.95]`. T_KT = 0.89294 is itself a grid point here, so "the bracket contains T_KT" is nearly true by construction: what
the test can still catch is an end that sits too early (boundary 0.85) or too late (first beyond 1.0 or higher, a finite-size miss). The verdict is
the refusal `REFUSE-UNCLASSIFIED-v0`, the family rulebook's default for a cell with no positive row (its printed `why`, "no positive row yet"):
BKT-END needs an interior that reads LINE, and this one does not.

## across_delta on the TRANSFORMED basis (v07-rules, plan 0874)

v07-rules = v06-rules + one thing, declared before it ran (`expected/v07-rules.toml`): `across_delta` reads the finite-size TRANSFORMED exponent on a pair whose two endpoints are both converging.

**The pair basis.** `tables/v07-rules/membership.toml [across_delta]` reads the signature column `drift_code` at both endpoints of a control pair; the lowest-ranked membership decides the pair's door
value. Both CONVERGING gives `delta_basis TRANSFORMED`: the pair reads `yD_inf = (yD2 - r yD1)/(1 - r)` (yD1, yD2 the Delta exponents of the two size steps, r the mean of the two endpoints' needle
`|v2|/|v1|`, taken per resample from `needle_chain`'s drift as `3^-(drift + 1)`). Any other pair (a null `drift_code` included) reads `delta_basis RAW`: the raw yD2, r = 0. `door:basis` refuses a
TRANSFORMED pair (NOT-EVALUATED, with a reason) where r >= 1 at the estimate or any resample. A set with no `[across_delta]` rule (v06-rules and earlier) reads every pair RAW: the instrument declares
`member_default = "RAW"`. `delta_basis` is shown (`show`, `--advanced`: `per pair: 0.5->0.6 ZERO! MARGINAL [delta_basis TRANSFORMED]`; the pair rows of a result) and read by no verdict row; the pair's step
exponents and r are reported (`y_steps`, `ratio`).

**The per-point rule.** `codes.toml [columns.helper.across_dlt] combine.prefer_door = "TRANSFORMED"`: a point combines ONLY the touching pairs read on the TRANSFORMED basis when it has at least one, else all of
its touching pairs (RAW), then the v06 rule applies (a resolved code counts only when every combined pair reads it). A converging point is thus read from its converging neighbours and never from a
pair that crosses into a non-converging region. `bin/cc explain <input> <point>` prints the rule beside the combine rank.

## Across by the difference estimator, the finite-size transform and the end note (v06-rules, plan 0872)

v06-rules = v05-rules + three things, each declared before it ran (`expected/v06-rules.toml`).

**`across_delta` (F2).** A pair instrument: for a control pair (a, b) of the declared chain, Delta(L) = mean g1(b) - mean g1(a) at final size 9, and the
exponent is `log3 |Delta(L)/Delta(L/3)|` at the top size step, with the same block bootstrap and the same eps (`y`) as `across`. It is `per_point`: a point reads the
cell of every control pair that touches it (`bin/cc explain <input> a->b` shows one), and `codes.toml [columns.helper.across_dlt]` combines them: a resolved code counts only when
EVERY touching pair reads it (`combine.agree`), else UNRES (`combine.disagree`). The signature column `across` is then ONE declared choice per input: the helper `across_dlt` when the
input declares `across_delta`, else the covariance helper `across_cov`; a declared `across_delta` that is NOT-EVALUATED reads UNRES, never the covariance. Admissible only when
`[relations.control] coupling = "<name>"` names a coupling that `couplings.toml` says `across` probes; `bin/cc validate` refuses anything else, each with a Next line. Declare it on a
T-ordered input by adding `across_delta` to `instruments` and the coupling line (see `inputs/x2b-xy-2`). Read the tight intervals with care: the Delta estimator resolves the exponent to about
+-0.01, so an interval that excludes 0 by a hair reads SLOW-/SLOW+ (WEAK), not ZERO! (MARGINAL).

**TRANSFORMED stability (F1).** `stability` is a total table over (`stability_raw`, `drift_code`): on a point whose needle drift is CONVERGING (a measured pre-asymptotic small pair), a raw STABLE
or CROSSING reads TRANSFORMED; OFF and UNRES stay; every other drift keeps today's reading, so a real walking (CROSSING off a CONVERGING point) is still WALKING. `geometry.toml` accepts
TRANSFORMED wherever a line accepted STABLE; a RELEVANT exponent on a TRANSFORMED point refuses (REFUSE-UNRES: not certified as a point, with its Next line). The declared transform
`y_inf = (y2 - r y1)/(1 - r)` (r = the needle's own v2/v1) is the `transform` instrument; its helper column `y_inf_code` is visible in `show` and read by no verdict row, and it is NOT-EVALUATED where the correction does not decay.

**The end note (F3).** A family names each end point (`ends`: point, side, END-kind). `bin/cc show` and `explain` of that point print `end of a LINE run (family <id>, END-<kind>)` beside its per-point
reading (read from the stored family; nothing for a dry run, a set without family sides, or a point that ends nothing). No verdict changes.

## A new instrument

`bin/cc new instrument <id>` writes `instruments/<id>.toml` and a stub module `cc/instruments/<id>.py`:

```
$ bin/cc new instrument foo
wrote instruments/foo.toml and cc/instruments/foo.py
  add this line to checks.toml [roles].maths: "cc/instruments/foo.py"
  Next: replace every TODO in instruments/foo.toml, write the stages and delete the TODO-STAGE marker, then bin/cc validate (bin/cc run refuses until it is clean)
```

Replace every `TODO` in the registry file, write the stages in the module (the marker `TODO-STAGE` goes when you
are done), add the module to `checks.toml [roles].maths` as the message says, and run `bin/cc validate`. While
`instruments/` has any finding, `bin/cc run` is refused: a half-made instrument cannot enter a result. A
maths module must pass `checks.py` (no branches, see `KERNEL-IN-CC.md`). A name that is not a module name (lower-case letters, digits, underscores) or that already exists is refused.

## Why v01-rules differs from verdict-x-rules

`v01-rules` is `verdict-x-rules` plus two data changes, both from one decision, and nothing else.

1. **c-prime (codes).** In `codes.toml`, a resolved reading inside the margin reads MID, not a side: the needle
   column's `NEG` and `POS` cells are `MID` (they were `DIS` and `ORD`), and the flow column's `NEG` and `POS`
   cells are `SLOW` (they were `FLOWING`).
2. **The SLOW split (verdict).** The row for a needle at MID with a SLOW flow used to refuse always
   (`REFUSE-SLOW`). Now `SLOW` with `across` MARGINAL and `stability` STABLE is `LINE`, and every other SLOW
   cell still refuses.

**Why.** X5, a pair of coupled Ising layers at a navigated critical point, read NOT at all three of its points
while the point is critical: a false negative. The cause was not the needle: at the critical coupling the
needle is unbiased (its mean velocity was -0.0004 and it read MID in four of four trials). The cause was in
the rules. At `g = 0` the needle velocity is -0.0118, interval [-0.02263, -0.003361]: wholly below zero but not
beyond the margin, cell `NEG`. That cell was read as a side of the window (`DIS`) and its flow as `FLOWING`, and the rulebook says that a flowing point
off the window is NOT. A sign-resolved reading inside the margin is not a flow: it is a reading that is small and
resolved, which is what `SLOW` says. So c-prime moves it to `MID` and `SLOW`.

The consequence was declared before any run, and the comparison confirms it:

```
$ bin/cc tabulate --diff verdict-x-rules v01-rules
6 cells change verdict between verdict-x-rules and v01-rules
REFUSE-SLOW -> LINE: 6 cells in 1 patterns
  when.needle = ["MID"]; when.flow = ["SLOW"]; when.across = ["MARGINAL"]; when.stability = ["STABLE"]; when.two_start = ["INDEP"]
2 fixture points change verdict
  x5-bilayer:0.0  NOT -> REFUSE-SLOW
  x5-bilayer:0.3  NOT -> REFUSE-SLOW
tabulate --diff: wrote nothing (bin/cc tabulate writes SIGNATURE-TABLE.md and docs/verdict-table.html)
```

The old row refused every SLOW cell: a critical line whose block flow is small but resolved was read as the end
of a BKT line, never as a line (the STAGE3 flaw of v0). With c-prime more readings reach SLOW, so the row is
split by `across` and `stability`: a marginal, stable exponent is a line, and every other SLOW cell still
refuses. Six cells of the rulebook change (SLOW to LINE) and, of the points both sets have a result for, the only ones that
move are X5's, from NOT to REFUSE-SLOW at two of its three points. Every other point keeps its verdict, and the
scoreboard locks them.
X5 does not reach POINT; it goes from three confident false negatives to two honest refusals and one NOT.

## Freezing

A result is written once by `bin/cc run`, under the id `<input>@<set>`. Freeze it when you accept it:
`bin/cc freeze <input>@<set>` or `bin/cc freeze --all --tables <set>`. Freezing makes read-only, each one
individually, the result's `.json` and `.npz` and exactly the files its `read` lists (its `m.toml`, its
instrument files, its data manifest), plus the rulebook directory it ran under. It records their hashes in
`FROZEN.json`.

What stays editable, by design: every `points.toml`, every `cases/*.toml`, `cc.toml`, the templates,
`expected/`, `tests/golden/`. Taxonomy is never frozen, so a new idea about what a point is never needs a fork.

**Freeze by dependency.** `bin/cc freeze --all --tables v01-rules` freezes each result under that rulebook with the
files it read, and the rulebook directory once (all of `tables/v01-rules`, so `membership.toml` and `family.toml`
with it). A **derived** result (from `reverdict`) freezes the parent's vectors too, since it has none of its own.
A family result is not stored: `bin/cc family` reads the results it names, so freezing those freezes the family.

A frozen id is never re-run; a different table set is a different id:

```
$ bin/cc run w2-potts --tables verdict-x-rules
REFUSED: results/w2-potts@verdict-x-rules.json is frozen (a frozen result never changes).
  Next: bin/cc tables fork verdict-x-rules <new-name>, edit tables/<new-name>/verdict.toml, then bin/cc run w2-potts --tables <new-name>
exit 1
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
tabulate: 19 results -> SIGNATURE-TABLE.md, docs/verdict-table.html
```

`SIGNATURE-TABLE.md` lists every result's points with their codes, verdict and (here, and only here) the
truth class from the case, so you can see where the rulebook and the taxonomy agree. `docs/verdict-table.html`
is one static page you can open in a browser: for each rulebook, its rows grouped by verdict class, each row
with its `why`, its line number, how many signature rows it covers, the fixture points that hit it, and the
rows no result ever hit. (`tabulate` writes both files; `tabulate --diff` writes nothing.)

`bin/cc tabulate --diff A B` compares two rulebooks on every signature row and on every fixture point that has a
result under both:

```
$ bin/cc tabulate --diff v01-rules scratch
1512 cells change verdict between v01-rules and scratch
REFUSE-EQUIL -> LINE: 12 cells in 1 patterns
  when.needle = ["MID"]; when.flow = ["STOPPED", "SLOW"]; when.across = ["MARGINAL"]; when.stability = ["STABLE"]; when.two_start = ["UNRES"]
REFUSE-EQUIL -> NOT: 252 cells in 1 patterns
  when.needle = ["MID"]; when.flow = ["FLOWING"]; when.two_start = ["UNRES"]
REFUSE-EQUIL -> POINT: 6 cells in 1 patterns
  when.needle = ["MID"]; when.flow = ["STOPPED"]; when.across = ["RELEVANT"]; when.stability = ["STABLE"]; when.two_start = ["UNRES"]
…
REFUSE-EQUIL -> WALKING: 12 cells in 1 patterns
  when.needle = ["MID"]; when.flow = ["STOPPED"]; when.across = ["RELEVANT", "MARGINAL"]; when.stability = ["CROSSING"]; when.two_start = ["UNRES"]
0 fixture points change verdict
tabulate --diff: wrote nothing (bin/cc tabulate writes SIGNATURE-TABLE.md and docs/verdict-table.html)
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
  FAIL  5 signature table enumerated over every in-table case, collisions listed :: 17 in-table case(s); collisions section present; missing ['ar1-null', 'bc-tricritical', 'potts-q6', 'potts-q7']
-- MVT FAIL
```

## Tests, mutations and the testing system

`bin/cc check` has two tiers; pick by what you are about to do:

| tier | command | when |
|---|---|---|
| fast | `bin/cc check --fast` | the pre-commit hook runs it (about 25 s, budget 30 s); it skips the tests listed in `cc.toml [check].slow` |
| full | `bin/cc check` | the end of every Generator phase, and the Auditor's gate: `validate`, EVERY test script and the scoreboard |

Nothing is dropped by a list. `detect.run` is content-keyed: a result stored under the same input and table set whose `read` hashes
and `measure_hash` equal this run's IS the result (nothing is measured or re-written); a measured result under another set whose key
differs only in its `tables/*` entries is re-verdicted (`derived_from` set), unless the sets' `membership.toml` differ; anything
else is measured. `measure_hash` is the sha over (path, content sha) of the import closure, within `cc/`, of `cc/door.py` and of the
modules of the instruments the input declares, parsed from the import statements (`declare.measure_hash`); an edit to a file in no
closure (view.py, score.py, ...) keeps the key, an edit to kernel.py or an instrument module moves it. A closure that cannot be read
statically (a dynamic import) is refused. `code_hash` (all of `cc/` and `bin/cc`) stays recorded as provenance and `freeze` still
demands it. A result with no `measure_hash` has no key: `bin/cc run <input>` writes it.
A green full check writes `tests/BASELINE.txt` (tree, HEAD, every test's name, status and seconds); `bin/cc check --baseline`
reads it back when the tree is unchanged.

`bin/cc test` runs every test, `bin/cc test <name> …` the named
ones, `-v` prints each test's lines. Tests are plain scripts, and a test that cannot find its data fails with
the path; none skips.

What each kind of test protects (the test files are in `tests/`):

| kind | what it protects | goes red when |
|---|---|---|
| unit (kernel, sign, resample, kernel_rs, budget, tables_cli, view, along, family) | the arithmetic and the commands | a named change to the code |
| regression (the fixture replays, detect_verdicts, verdict_equivalence, tabulate, reverdict, x5) | the first measurements CC was built to reproduce | a frozen number, cell or verdict moves |
| door breakers (test_declare, `tests/planted/`) | the file checks | a deliberately bad plugin file is accepted, or its message changes |
| rule breakers (`tests/breakers/*.toml`) | the verdict table's meaning | a synthetic reading gets the wrong verdict |
| scoreboard lock (`expected/<set>.toml`) | every point's verdict, and every family's | any point's or family's verdict changes |
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

**Mutation.** To see that a test can fail, mutate a copy (the rule breakers name the rulebook they test, here
`verdict-x-rules`):

```
bin/cc mutate tables/verdict-x-rules/codes.toml --sed 's/"SIG+" = "COEXIST"/"SIG+" = "INDEP"/' -- test_breakers
RED   test_breakers
      ok field-decoy-not-line
      ok off-critical-growth-change
      ok unres-across-not-positive
      ok unres-two-start-not-positive
      ok w1-point-estimate-crossing
      BROKEN coexistence-at-transition: expected code COEXIST, got INDEP; expected verdict FIRST-ORDER, got POINT
      BROKEN slow-kinetics-off-transition: expected code COEXIST, got INDEP
      test_breakers: 5 of 7 ok
```

It copies the repo to a temporary directory, applies the edit there (the frozen file too, in the copy only),
runs the named tests there, prints RED or GREEN for each test, and deletes the copy. Your tree is never changed.
For this edit it prints `RED   test_breakers`, with the two breakers it breaks named.

## Routine edits

| edit | files touched | what validates | code change | old results readable |
|---|---|---|---|---|
| new case, existing points | `cases/<id>.toml`; join lines in `inputs/*/points.toml` | case schema, join | none | yes: no result names a case |
| new model, existing layout | `new input --like --points`; `data add`; its `points.toml` | `m.toml` against the instrument contracts; hashes | none | yes: a new input id |
| change verdict rows / new class | `tables fork`; the copy's `verdict.toml` (`verdicts`, `refuse`, rows); a new class also in `cc.toml alphabets.class_truth` | partition; class derivation | none | yes: the old set is frozen and untouched |
| split a verdict | `tables split`, or by hand: one row becomes rows partitioning its cells | partition | none | yes |
| change what is "on the manifold" | the fork's `membership.toml` | keys equal the column's alphabet plus the nulls | none | yes; re-run, since `reverdict` refuses |
| change how a family is read | the fork's `family.toml` | partition of the three alphabets | none | yes; `family --tables <set>` |
| new family | `new family <id>`; fill the `TODO`s | input, points, the set's `family.toml` | none | yes: nothing names a family |
| remove or rename a case | the case file; the join lines; `pairs_with` lines (validate lists each) | full validate names every stale id | none | yes: `UNJOINED` until fixed |
| change a frozen input | `new input <id>-2 --like <id>`; `data add` | as for a new model | none | yes |
| new instrument | `new instrument <id>`; its registry file and module; `checks.toml` | registry file; `checks.py` | yes | yes: a new module name |

## Probe completeness, the size chain and POINT-MANIFOLD (v04-rules, plan 0870)

`v04-rules` is `v03-rules` forked, with three declared changes. Each is a table or a declaration, never a threshold chain in code.

**1. Probe completeness.** A per-point instrument probes one direction: `across` reads the response to the declared conjugate.
If the system has a second coupling that nothing probes, "relevant and stopped" on the probed direction is consistent with a
point and with a line alike (the AT line of E151 read POINT twice for this reason). `inputs/<id>/couplings.toml` declares the
sampler's couplings from the Hamiltonian, and which of them `across` probes:

```
schema = 1
kind = "couplings"
id = "x5n-bilayer-2"
names = ["K", "g"]
probes = ["K"]
```

`validate` checks `names` against the scalars the data files store (minus the size key `L`): a declaration cannot choose its own
verdict. The signature column `probe` reads COMPLETE (every coupling probed), INCOMPLETE (one is not), UNKNOWN (`names = "unknown"`,
admissible only when the data store no scalars) or NOT-MEASURED (the input declares no `across`). `tables/v04-rules/probe.toml`
projects the geometry through it: a positive geometry (POINT, LINE, WALKING) with probe INCOMPLETE reads REFUSE-PROBE-INCOMPLETE,
with probe UNKNOWN REFUSE-PROBE-UNKNOWN, and every other cell passes. `compose.toml` reads the projected geometry, so the verdict
moves only where the geometry did (b7-at-line-4 keeps its REFUSE-TWO-START-UNMEASURED; its GEOMETRY at 0.0 and 0.07 is the refusal).
A refusal says why and what to do:

```
$ bin/cc explain x5n-bilayer-2 0.0 --tables v04-rules
…
probe      INCOMPLETE
  declared in inputs/x5n-bilayer-2/couplings.toml: couplings ['K', 'g'], probed by across ['K']
…
8 VERDICT   verdict.toml line 131: when.needle = [MID]; when.two_start = [INDEP]; when.flow = [STOPPED]; when.across = [RELEVANT]; when.stability = [STABLE]; when.probe = [INCOMPLETE]
            => verdict BLANK (REFUSE-PROBE-INCOMPLETE)
               why: plan 0870: a second coupling exists and is not probed here (across probes one direction only): a positive per-point class is not certified; read the family over the unprobed coupling. Next: declare the second coupling's instrument, or read the family
9  GEOMETRY  geometry.toml line 56: when.needle = [MID]; when.flow = [STOPPED]; when.across = [RELEVANT]; when.stability = [STABLE]  => POINT
10 PROBE     probe.toml line 17: when.probe = [INCOMPLETE]; when.geometry = [POINT, LINE, WALKING]  => REFUSE-PROBE-INCOMPLETE
11 ORDER     order.toml line 72: when.needle = [MID]; when.two_start = [INDEP]; when.fluct = [VANISHES]  => CONTINUOUS
12 COMPOSE   compose.toml line 36: when.order = [EQUILIBRATED, CONTINUOUS, FIRST-ORDER-TUNNELLING, EQUILIBRATED-UNRES]  => REFUSE-PROBE-INCOMPLETE (the geometry)
```

**2. The size chain.** The flow was read from ONE size pair, so a finite-size correction that decays (the XY low phase) read SLOW and
refused. An input with two matched pairs declares `relations.chain` (template `matched-chain`, `pairs = [[243, 81], [81, 27]]`) and the
instrument `needle_chain`: it takes the needle's velocity at both pairs, `ln|v|` through `door:logcoord` (a velocity whose sign is not
constant is NOT-EVALUATED by construction), and reports `drift = omega_eff - 1`, where `omega_eff = -A(ln|v|) / ln(size ratio)` is how fast
the velocity decays down the chain. It is read against `[eps] drift = 0.5`, declared in the plan before any run. `drift_code` is
CONVERGING (omega_eff above 1: the correction dies), MARGINAL-DRIFT (within eps of 1), PERSISTENT (below 1: a genuine slow flow, log
corrections included) or UNRES. The derived `flow` is a total table over (flow of the top pair, drift_code): **a SLOW flow whose drift
CONVERGES reads STOPPED, and every other cell is the top pair's flow.** `drift_code` stays in every result and in `ignores` of
`verdict.toml`: it is the visible flag of Bruce's R2, read by no verdict row. An input with one size pair reads drift NOT-MEASURED, and
its flow is the top pair's, as under v03-rules.

```
$ bin/cc show x2-xy-line-3 --tables v04-rules
…
point 0.6   case xy-low-phase
…
  drift_code 0.8204 [0.3995, 1.332] POS -> CONVERGING
  flow       velocity 0.001239 [0.0007177, 0.001869] SLOW+ drift 0.8204 [0.3995, 1.332] POS -> STOPPED
  across     0.6956 [0.3908, 0.9802] SIG+ -> RELEVANT
  stability  0.9112 [0.4498, 1.363] SIG+ -> CROSSING
…
  => verdict WALKING
```

Read that block as a finding, not a success: T 0.6 of the XY low phase is a LINE point, the flow now reads STOPPED, and a 2.5 sigma
fluctuation of `across` that the old REFUSE-SLOW was hiding reaches the WALKING row. The rule is recorded as it is.
The same plan narrows `two_start`: COEXIST at the combined cell now requires the LARGEST size to read COEXIST
(`combine.top_only` in `codes.toml`); no stored two_start code on any existing input moved.

**3. POINT-MANIFOLD.** A family over a navigated chain of points can say what one point cannot. `family.toml` gains the row
{f1 CONSTANT, f2 IRRELEVANT} = POINT-MANIFOLD (class POINT), and names its two siblings {VARIES, IRRELEVANT} and {CONSTANT, MARGINAL}
as REFUSE-UNCLASSIFIED, each with a `why` that names a Next line. `families/x5n-g.toml` reads the coupled Ising layers over g
(`x5n-bilayer-3`: `x5n-bilayer-2` plus `along`, a control chain over g, and two matched pairs):

```
$ bin/cc family x5n-g --tables v04-rules
family x5n-g   rules: v04-rules   input: x5n-bilayer-3   interior: 0.0 0.1 0.3
  bracket BRACKET
    edge 0.0->0.1 NO-DESCENT
    edge 0.1->0.3 NO-DESCENT
  f1      CONSTANT
    0.0->0.1 y_last +0.030 [-0.050, +0.086] ZERO!  -> CONSTANT
    0.0->0.3 y_last +0.021 [-0.066, +0.091] ZERO!  -> CONSTANT
    0.1->0.3 y_last -0.009 [-0.067, +0.059] ZERO!  -> CONSTANT
  f2      IRRELEVANT
    0.0->0.1 along SIG-  -> IRRELEVANT
    0.1->0.3 along NEG  -> IRRELEVANT
  => family verdict POINT-MANIFOLD   class POINT, family.toml line 75
     why: plan 0870 P3: …
```

So the positive class of x5n is re-earned by the family over g: each per-point reading refuses (the K probe is incomplete), and the
three points together read as one point class. This is the first reading ever of the POINT-MANIFOLD row; a MARGINAL f2 here would have
been a finding that stopped the plan.

## Known limits of v0.1

Read these before you trust a verdict.

- **One real input reaches a positive class for a point: `x5n-bilayer`, POINT at all three points.** The twelve
  inputs hold 79 points under `v01-rules`: NOT (19 points), REFUSE-NEEDLE-UNMEASURED (41), REFUSE-SLOW (10),
  REFUSE-TWO-START-UNMEASURED (5), REFUSE-UNRES (1) and POINT (3, all `x5n-bilayer`; `bin/cc run --all` prints
  them). LINE, WALKING and FIRST-ORDER appear in no real per-point result; only the synthetic rule breakers
  exercise those rows. One positive **family** verdict exists, LINE for `b7-at-line-2`,
  and it rests on a boundary cell (the pair `0.14->0.21` reads inside the margin by 0.002; see Tutorial part 3).
  The other three families refuse (`x8-ising-compass` and `x7a-nnn-manifold` read `REFUSE-UNCLASSIFIED-v0`,
  `x7a-bc-lambda` reads `REFUSE-OFF-MANIFOLD`). Do not read "no positive" as "nothing is critical".
- **x5 is REFUSE-SLOW, not POINT.** The navigated critical point of the coupled layers now reads needle MID, flow
  SLOW and across RELEVANT at `g = 0` and `g = 0.3`. A SLOW flow with a RELEVANT across lands in the refusing SLOW
  row by ruling (only a MARGINAL across with a STABLE stability leaves it), so those two points refuse. `g = 0.1`
  reads NOT: its needle reads ORD. Navigation itself, which would stop on a confirmed reading, is not in v0.1.
- **The x2 and x3 lines are still refused.** Eight points of the XY and clock models, whose true class is LINE, read
  REFUSE-SLOW: their across and stability read UNRES (x2 0.6 reads RELEVANT and CROSSING), not the MARGINAL and
  STABLE the new LINE cell needs. The split opened the LINE cell; no real point reaches it yet.
- **x4's FIRST-ORDER-LINE is not reproduced.** In the study the first-order line came from a separate
  statistic, a table of where the response to the field h crosses, which CC has no instrument for. CC's own
  pipeline puts the needle at the ordered sink there and reads NOT.
- **The family code maps live in `family.toml`.** How an `along` cell becomes an f2 code is `[f2.code]`, and the
  f1 map is `[f1] code`, in the rulebook's `family.toml`, not in `codes.toml`: a change to either is a change to
  the family rulebook (and to nothing else).
- **`new input --like` cannot change the size axis or mix data directories.** `--data-dir` moves every file to one
  folder; a different set of sizes, or points drawn from two folders, is written by hand.
- **`bin/cc check --fast` takes about 25-34 s against its 30 s budget.** The hook runs it before every commit; it
  prints the slowest fast test and the line to move into `cc.toml [check].slow`, and that move is a maintainer's
  choice, so the budget is currently exceeded.
- **REFUSE-PROBE-UNKNOWN: a real-data input can never read POINT, LINE or WALKING per point (v04-rules).** `inputs/<id>/couplings.toml`
  declares the system's couplings and which of them `across` probes. With `names = "unknown"` (admissible only when the data store no
  scalar parameters) the probe column reads UNKNOWN, and `probe.toml` turns every positive geometry into REFUSE-PROBE-UNKNOWN. That
  is the honest reading of "a second direction may exist"; only a family over a navigated chain can say more. To lift it, declare the
  couplings from the Hamiltonian; if they are unknown this instrument reads the position only. An input with two couplings and one probed
  (b7: K and L4; x5n: K and g) reads REFUSE-PROBE-INCOMPLETE per point and is read through its family.
- **v04-rules: x2-xy-line-3 T 0.6 reads WALKING, and x3-clock6-3 T 0.5 reads flow STOPPED.** The XY low phase is a LINE; its drift CONVERGES, so
  its flow reads STOPPED, and a fluctuation of `across` (+0.696, a 2.5 sigma reading) with stability CROSSING reaches the WALKING row. The clock's
  ordered end (needle ORD, verdict NOT either way) is STOPPED by a converging drift, which the declared predictions said no clock point would be.
  Both are recorded in `expected/v04-rules.toml` as findings about the rule, not repaired.
- **v05-rules: x2b-xy reads a refusal, not BKT-END (plan 0871 P4, recorded and not repaired).** Three predictions declared before the run missed:
  T 0.6 reads WALKING (stability CROSSING, the same cell as x2-xy-line-3), T 0.89294 reads POINT (across RELEVANT +0.17, flow STOPPED), and f1 reads
  UNRES. What held: probe COMPLETE everywhere; drift CONVERGING and flow STOPPED at T <= 0.8; the upper side END-BKT-CANDIDATE with an
  end_bracket [0.89294, 0.95] that contains T_KT; f2 WEAK (not IRRELEVANT, so no POINT-MANIFOLD). `expected/v05-rules.toml` keeps the declaration and the
  after-run `[[change]]` that lists each miss. The end is therefore found by the family, but the BKT-END verdict is withheld because the interior is not LINE.
- **v04-rules: `needle_chain` needs the level stack at three sizes, and its drift is NOT-EVALUATED wherever the velocity changes sign** (b7, x5n,
  x9c q3-q8, the clock's T1 and the XY T_KT). A drift that cannot be formed refuses nothing: the flow is the top pair's.
- **v04-rules: `couplings.toml` sits beside `m.toml` rather than inside it,** because an `m.toml` that a stored result read cannot change
  (its hash is in the result); `[conjugate].hamiltonian_knowledge` therefore stays in `m.toml`, and `conjugate_to` is free text ("beta" for the
  one coupling `T`), so `probes` is checked against `names` and the stored scalars, not against `conjugate_to`.
- **v06-rules: the difference estimator does not read MARGINAL where it is tightest (plan 0872 P4, recorded and not repaired).** On x2b-xy-2 the stability reads TRANSFORMED at all
  five low-phase points and no point reads WALKING, but `across_delta` is MARGINAL only at T 0.5; the pairs 0.6->0.7 and 0.7->0.8 read SLOW- (WEAK), and a point whose two touching pairs
  disagree is UNRES, so geometry is LINE at 0.5 and REFUSE-UNRES / REFUSE-WEAK at 0.6-0.85. The family x2b-xy under v06-rules reads x2b-xy (covariance across plus F1) and is BKT-END with
  end_bracket [0.89294, 0.95]. `expected/v06-rules.toml` keeps the declaration and the after-run `[[change]]`.
- **v07-rules: the difference estimator reads MARGINAL on x2b-xy-2 once it is corrected (plan 0874).** The four converging pairs 0.5->0.6 ... 0.8->0.85 read yD_inf within +-0.02 of zero (all ZERO!), so across is MARGINAL
  and geometry / verdict LINE at all five low-phase points, and the family x2b-xy-2 is BKT-END with end_bracket [0.89294, 0.95]. All [0874] predictions held; `expected/v07-rules.toml` keeps the declaration and the
  after-run `[[change]]`. The instrument file `instruments/across_delta.toml` gained fields (requires, door_values, member_default, door_label), so `x2b-xy-2@v06-rules` was re-measured (every cell identical).
