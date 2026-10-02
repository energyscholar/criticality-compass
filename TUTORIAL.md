# Tutorial: one point, then one rule change

Two parts. Part 1 follows one point of one input from data files to verdict. Part 2 changes a rule in a
scratch rulebook and asks CC what moved. Every output below was produced by the command above it; `…`
marks lines left out. Read `README.md` first for the words.

## Part 1: the Potts q = 5 point, end to end

```
$ bin/cc show w2-potts
w2-potts   rules: verdict-x-rules   result: results/w2-potts@verdict-x-rules.json (frozen)
point 2   case ising-2d
…
point 5   case potts-q5
  sink       BLANK (NOT-MEASURED: needle is not declared on this input)
  needle     BLANK (NOT-MEASURED: needle is not declared on this input)
  flow       BLANK (NOT-MEASURED: needle is not declared on this input)
  across     1.679 [1.417, 1.932] SIG+ -> RELEVANT
  stability  0.08076 [-0.3098, 0.5382] BLANK (UNRES: interval straddles 0 and a margin edge)
  two_start  BLANK (UNRES: interval straddles 0 and a margin edge)
  => verdict BLANK (REFUSE-NEEDLE-UNMEASURED)
     why: honest null (not in verdict_x): the needle was not measured or not evaluated
```

Point 5 is the 2D five-state Potts model at its exact critical coupling. Its case, `potts-q5`, says the true
class is WALKING: the flow lingers near a pair of fixed points that have just disappeared. The question is what
CC can say about it. Now the whole chain:

```
$ bin/cc explain w2-potts 5
```

### The data

```
across
  1 DATA      w2/q5-L27-random.npz [G key G, E key E] ... 3 blocks; sha256 matches fixtures/data/w2-potts.toml
  2 REDUCE    row 0: 27 14.42, 81 83.45, 243 527.7
```

Step 1 names the files that were read: one block of snapshots per lattice size (27, 81, 243), with the keys
used inside each file. `sha256 matches` says the file is exactly the one pinned in `fixtures/data`; if it were
not, CC would refuse and say so. Step 2 reduces each block to one number for the original data (row 0):
here, the covariance of the observable with the energy, which grows as a power of the size.

### The size chain

```
  3 RELATION  size: chain, Coupling   27 <- 81 <- 243
  4 KERNEL    operator A over size; row 0: y_steps [1.598, 1.679]; y_last [1.679]
```

The relation says which numbers are neighbours: 243 is connected to 81 and 81 to 27. Operator A takes the
difference along each connection (a difference of logarithms, divided by the log of the size ratio), giving
one growth exponent per step: 1.598 from 27 to 81 and 1.679 from 81 to 243. `across` reports the last one,
1.679.

### The interval against the margins

```
  5 READING   y_last 1.679  interval [1.417, 1.932]  (95 %, 400 block resamples, b 400)
  6 SIGN      cuts -0.25 0 +0.25 (eps y): bL 3, bU 3 -> SIG+
```

The same data were resampled 400 times in blocks, and the 95 % interval of the exponent is [1.417, 1.932].
Step 6 places that interval among the declared cuts at -0.25, 0 and +0.25 (the margins, `eps y`):
`bL 3, bU 3` says that the lower end and the upper end both have all three cuts below them, so the whole
interval lies above +0.25. An interval wholly beyond the margin is the strongest resolved reading, `SIG+`; one that straddles zero and a margin edge cannot be placed, and is `UNRES`. No comparison chain decides this; the cell is a position among the cuts.

### The code, the second instrument, the combine over sizes

```
  7 CODE      across: codes.toml line 107: SIG+ -> RELEVANT
stability
  …
  5 READING   d 0.08076  interval [-0.3098, 0.5382]  (95 %, 400 block resamples, b 400)
  6 SIGN      cuts -0.25 0 +0.25 (eps y): bL 0, bU 3 -> BLANK (UNRES: interval straddles 0 and a margin edge)
  7 CODE      stability: codes.toml line 122: UNRES -> BLANK (UNRES: interval straddles 0 and a margin edge)
two_start
  …
  7 CODE      L27 two_start: codes.toml line 136: ZERO! -> INDEP
  7 CODE      L81 two_start: codes.toml line 140: UNRES -> BLANK (UNRES: interval straddles 0 and a margin edge)
  7 CODE      L243 two_start: codes.toml line 136: ZERO! -> INDEP
  7 CODE      combine.rank NOT-MEASURED > NOT-EVALUATED > COEXIST > FLUCT > UNRES > INDEP (first wins) -> BLANK (UNRES: interval straddles 0 and a margin edge)
```

The code is the sign cell translated through `tables/verdict-x-rules/codes.toml`; the line number is printed
so you can open it. `SIG+` for the growth exponent is `RELEVANT`. `stability` asks whether that exponent
changes from one size step to the next; its interval runs from -0.31 to +0.54, which straddles both zero and a
margin, so the data cannot say: UNRES, shown as BLANK. `two_start` compares two ways of starting the
simulation at each size (an ordered start and a random one): INDEP at 27 and 243, UNRES at 81. The code table
declares how the three sizes combine: the code that comes first in the `combine.rank` list wins, so one
unresolved size makes the point UNRES. (The text above is the BASIC view; `--advanced` also prints the cell
names, the margins and which instrument asked.)

### The verdict row and its why

```
8 VERDICT   verdict.toml line 133: when.needle = [NOT-MEASURED, NOT-EVALUATED]
            => verdict BLANK (REFUSE-NEEDLE-UNMEASURED)
               why: honest null (not in verdict_x): the needle was not measured or not evaluated
```

`verdict.toml` is a list of rows. Each row says "when the signature row has these codes, the verdict is
this, and here is why". `bin/cc validate` checks that the rows cover every possible signature
row exactly once, so exactly one row matches. For this point it is the row at line 133: whenever the needle
is NOT-MEASURED or NOT-EVALUATED, the verdict is a refusal.

Why the refusal? The needle is the instrument that asks whether the observable still moves under one more
blocking step and whether it sits at one of the two trivial fixed points. The Potts data were collected without it. The rulebook does not let a class be named without a needle reading, so CC
names none; the reasonable-looking `RELEVANT` growth exponent does not change that. This is a deliberate
refusal and not a failure: the alternative would be a guess.

## Part 2: change a rule and see what moves

The rulebook decides what an unresolved two-start comparison means. The working rules say that when the needle
sits at the window and the two-start difference is UNRES, the point is refused (`REFUSE-EQUIL`: an unresolved
difference cannot certify equilibrium). Suppose you would rather let it pass as INDEP. How far does that reach?

### Fork a scratch rulebook

```
$ bin/cc tables fork verdict-x-rules scratch
forked tables/verdict-x-rules to tables/scratch
  Next: edit tables/scratch/verdict.toml, then bin/cc validate, then bin/cc run --all --tables scratch
```

### Make the edit, half way

Open `tables/scratch/verdict.toml` in Geany. The change takes 15 edits: the row that sends
`when.two_start = ["FLUCT", "UNRES"]` to `REFUSE-EQUIL` must lose its `"UNRES"` (edit 1), and the 14 rows that
read `when.two_start = ["INDEP"]` must each gain `"UNRES"` (edits 2 to 15). Do only the first one, then
validate:

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

A half-done edit is caught. The rulebook is a partition, so removing UNRES from one row left every signature
row with the needle at MID and the two-start at UNRES (1 512 of them) with no verdict at all. CC prints the
missing pattern as a ready-made `when` block.

### Finish it

Add `"UNRES"` to the other 14 rows, so each reads `when.two_start = ["INDEP", "UNRES"]`, and validate again:

```
$ bin/cc validate

validate: clean
```

### Run it under the scratch rules

```
$ bin/cc run --all --tables scratch
run b7-at-line@scratch -> results/b7-at-line@scratch.json
…
x8-ising-needle: ran
```

This measures again (about ten seconds in all) and writes seven results under the id `<input>@scratch`. The
frozen `…@verdict-x-rules` results are untouched. It prints every point of every input as it goes; the lines
that matter are the tables below.

### Compare

```
$ bin/cc tabulate --diff verdict-x-rules scratch
1512 cells change verdict between verdict-x-rules and scratch
REFUSE-EQUIL -> LINE: 6 cells in 1 patterns
  when.needle = ["MID"]; when.flow = ["STOPPED"]; when.across = ["MARGINAL"]; when.stability = ["STABLE"]; when.two_start = ["UNRES"]
REFUSE-EQUIL -> NOT: 252 cells in 1 patterns
  when.needle = ["MID"]; when.flow = ["FLOWING"]; when.two_start = ["UNRES"]
…
REFUSE-EQUIL -> WALKING: 12 cells in 1 patterns
  when.needle = ["MID"]; when.flow = ["STOPPED"]; when.across = ["RELEVANT", "MARGINAL"]; when.stability = ["CROSSING"]; when.two_start = ["UNRES"]
0 fixture points change verdict
…
```

1 512 cells of the rulebook (signature rows) change verdict, sorted by the old and new verdict: some become
LINE, POINT or WALKING, most become other refusals, because the rest of the rulebook still has its say. And
no fixture point changes verdict. Why: a point is only affected if it reads the needle at the window (MID)
and the two-start comparison UNRES together. Of the 60 points CC holds, the x2 and x3 points read MID, but
their two-start comparison is INDEP; the one point whose two-start comparison is UNRES with the needle
measured (x4, K = 0.46) has the needle ORD, which is NOT either way; and Potts q = 5 has an UNRES two-start
but no needle at all. A rule can matter a lot to the rulebook and not at all to today's data. `tabulate` also
rewrites `SIGNATURE-TABLE.md` and `docs/verdict-table.html`, which show the same diff as tables you can open.
(Run the `run --all` step first, as above, or the "fixture points" line has no scratch results to compare;
the cell count does not need them.)

### The one-line alternative, and what it hides

The same verdicts for every point can be had with one line in `tables/scratch/codes.toml`: in the
`[columns.signature.two_start.map]` table, change `"UNRES" = "UNRES"` to `"UNRES" = "INDEP"`. The rulebook
then needs no row changes. But the signature row would now say INDEP where the data said UNRES, in `show`,
in `explain` and in every table: the doubt disappears from the output. The 15-row edit keeps the code honest
and puts the decision in the rulebook, where `tabulate --diff` can show it. Prefer the long way when the
choice is a scientific one.

### Clean up

```
$ bin/cc tables drop scratch --with-results
dropped tables/scratch and 14 result files
```

`drop` never deletes a frozen rulebook or the default one; `--with-results` also deletes the unfrozen results
that were run under it (a `.json` and a `.npz` for each of seven inputs).
