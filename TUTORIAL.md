# Tutorial: one point, then one rule change

Three parts. Part 1 follows one point of one input from data files to verdict. Part 2 changes a rule in a
scratch rulebook and asks CC what moved. Part 3 reads a family: several points that together say something
no single point can. Every output below was produced by the command above it; `…` marks lines left out.
Read `README.md` first for the words.

## Part 1: the Potts q = 5 point, end to end

```
$ bin/cc show w2-potts
w2-potts   rules: v01-rules   result: results/w2-potts@v01-rules.json (frozen)
```

(Here the head of the `show` report, from its first line to the point 5 rows is the same text that HOWTO prints, once: see [Re-verdicting without measuring](HOWTO.md#re-verdicting-without-measuring).)

```
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
  3 COMPARISON size: chain, Coupling   27 <- 81 <- 243
  4 C         operator A over size; row 0: y_steps [1.598, 1.679]; y_last [1.679]
```

The comparison says which numbers are compared: 243 with 81 and 81 with 27, one blocking step apart (a declared
comparison, inside a projection C; an external verifier, 2026-10-06). The step takes the
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

The code is the sign cell translated through `tables/v01-rules/codes.toml`; the line number is printed
so you can open it. `SIG+` for the growth exponent is `RELEVANT`. `stability` asks whether that exponent
changes from one size step to the next; its interval runs from -0.31 to +0.54, which straddles both zero and a
margin, so the data cannot say: UNRES, shown as BLANK. `two_start` compares two ways of starting the
simulation at each size (an ordered start and a random one): INDEP at 27 and 243, UNRES at 81. The code table
declares how the three sizes combine: the code that comes first in the `combine.rank` list wins, so one
unresolved size makes the point UNRES. (The text above is the BASIC view; `--advanced` also prints the cell
names, the margins and which instrument asked.)

### The verdict row and its why

```
8 VERDICT   verdict.toml line 153: when.needle = [NOT-MEASURED, NOT-EVALUATED]
            => verdict BLANK (REFUSE-NEEDLE-UNMEASURED)
               why: honest null (not in verdict_x): the needle was not measured or not evaluated
```

`verdict.toml` is a list of rows. Each row says "when the signature row has these codes, the verdict is
this, and here is why". `bin/cc validate` checks that the rows cover every possible signature
row exactly once, so exactly one row matches. For this point it is the row at line 153: whenever the needle
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

Fork from the working rulebook, `v01-rules` (the one in `rules in use:` of `bin/cc help`), so that your copy
carries everything the working rules have, including its `membership.toml` and `family.toml`:

```
$ bin/cc tables fork v01-rules scratch
forked tables/v01-rules to tables/scratch
  Next: edit tables/scratch/verdict.toml, then bin/cc validate, then bin/cc run --all --tables scratch
```

### Make the edit, half way

Open `tables/scratch/verdict.toml` in Geany. The change takes 17 edits: the row that sends
`when.two_start = ["FLUCT", "UNRES"]` to `REFUSE-EQUIL` must lose its `"UNRES"` (edit 1), and the 16 rows that
read `when.two_start = ["INDEP"]` must each gain `"UNRES"` (edits 2 to 17). Do only the first one, then
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

Add `"UNRES"` to the other 16 rows, so each reads `when.two_start = ["INDEP", "UNRES"]`, and validate again:

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

This measures again (the time grows with the inputs on disk: time it, do not assume) and writes the
results under the id `<input>@scratch`. The `…@v01-rules` results are untouched. It prints every point of every
input as it goes; the lines that matter are the tables below.

### Compare

```
```

(Here the head of the `tabulate --diff` listing is the same text that HOWTO prints, once: see [Reading the whole rulebook, and comparing two](HOWTO.md#reading-the-whole-rulebook-and-comparing-two).)

```
  when.needle = ["MID"]; when.flow = ["STOPPED"]; when.across = ["RELEVANT", "MARGINAL"]; when.stability = ["CROSSING"]; when.two_start = ["UNRES"]
0 fixture points change verdict
tabulate --diff: wrote nothing (bin/cc tabulate writes SIGNATURE-TABLE.md and docs/verdict-table.html)
```

1 512 cells of the rulebook (signature rows) change verdict, sorted by the old and new verdict: some become
LINE, POINT or WALKING, most become other refusals, because the rest of the rulebook still has its say. And
no fixture point changes verdict. Why: a point is only affected if it reads the needle at the window (MID)
and the two-start comparison UNRES together. Of the 79 points CC holds under v01-rules, the x2, x3, x5 and x5n points read MID, but
their two-start comparison is INDEP (x5n then reads POINT, which no such rule touches); the one point whose two-start comparison is UNRES with the needle
measured (x4, K = 0.46) has the needle ORD, which is NOT either way; Potts q = 5 has an UNRES two-start but no
needle at all; and the inputs that never measured the two starts (x7a, x8) read NOT-MEASURED, which is not
UNRES. A rule can matter a lot to the rulebook and not at all to today's data. (`tabulate --diff` writes
nothing; plain `bin/cc tabulate` writes `SIGNATURE-TABLE.md` and `docs/verdict-table.html`, which show every
rulebook as tables you can open.) The cell count does not need any results; the "fixture points" line
compares real results, so run the `run --all` step first, as above, or it has nothing to compare.

### The one-line alternative, and what it hides

The same verdicts for every point can be had with one line in `tables/scratch/codes.toml`: in the
`[columns.signature.two_start.map]` table, change `"UNRES" = "UNRES"` to `"UNRES" = "INDEP"`. The rulebook
then needs no row changes. But the signature row would now say INDEP where the data said UNRES, in `show`,
in `explain` and in every table: the doubt disappears from the output. The 17-edit version keeps the code
honest and puts the decision in the rulebook, where `tabulate --diff` can show it. Prefer the long way when
the choice is a scientific one.

### Clean up

```
$ bin/cc tables drop scratch --with-results
dropped tables/scratch and 22 result files
```

`drop` never deletes a frozen rulebook or the default one; `--with-results` also deletes the unfrozen results
that were run under it (a `.json` and a `.npz` for each input).

## Part 3: a family

A point is read alone: its needle, its exponent, its stability. Some claims need several points together. The
B7 line is the example. On the exact self-dual line of the Ashkin-Teller model no single point measures the
needle, so every point on its own is refused (`bin/cc show b7-at-line-2` says `REFUSE-NEEDLE-UNMEASURED` five
times). Yet the five points together say something: the exponent of the response changes from point to point
along the line, and the growth of the difference between neighbouring points does not. That is a **family**.

A family is declared in `families/b7-at-line-2.toml`: the input, and the **interior** points, in the order
along the line (`0.0 0.07 0.14 0.21`; the endpoint `0.2747` is the four-state Potts point, a different class,
and is left out by declaration). The rulebook decides what the readings mean: `tables/v01-rules/family.toml`.
Ask for it:

```
$ bin/cc family b7-at-line-2
family b7-at-line-2   rules: v01-rules   input: b7-at-line-2   interior: 0.0 0.07 0.14 0.21
  bracket NOT-MEASURED
    edge 0.0->0.07 NOT-MEASURED
    edge 0.07->0.14 NOT-MEASURED
    edge 0.14->0.21 NOT-MEASURED
    edge 0.21->0.2747 NOT-MEASURED
  f1      VARIES
    0.0->0.07 y_last +0.064 [+0.019, +0.109] SLOW+  -> CONSTANT
    0.0->0.14 y_last +0.166 [+0.112, +0.224] SLOW+  -> CONSTANT
    0.07->0.14 y_last +0.102 [+0.054, +0.165] SLOW+  -> CONSTANT
    0.0->0.21 y_last +0.322 [+0.233, +0.394] POS  -> VARIES
    0.07->0.21 y_last +0.258 [+0.183, +0.325] POS  -> VARIES
    0.14->0.21 y_last +0.156 [+0.074, +0.233] SLOW+  -> CONSTANT
  f2      MARGINAL
    0.0->0.07 along ZERO!  -> MARGINAL
    0.07->0.14 along ZERO!  -> MARGINAL
    0.14->0.21 along ZERO!  -> MARGINAL
  => family report LINE   class LINE, family.toml line 55
     report: declared report — a projection C over per-point sign cells, not a relational reading (an external verifier (ruling Q19), 2026-10-06)
     why: B7 (SYNTHESIS-3): fingerprints 1 and 2 both resolved; X7a: POINT manifolds do not reach f2 MARGINAL
```

Read it section by section.

**The bracket.** The bracket asks whether the needle, read along the whole input, only ever moves up through
the window: each needle code is given a rank (DIS 0, MID 1, ORD 2), A takes the difference between neighbouring
points, and the bracket is `BRACKET` when no step goes down and some point sits at MID. This input never measured the needle, so every edge and the bracket
itself read `NOT-MEASURED`. That is a value, not an error, and the family rule allows it: the LINE row accepts
a bracket that was not measured, which is how a line is read when only its exponents are known.

**f1, the exponent varies.** Fingerprint 1 asks whether the `across` exponent differs between
points. It takes the difference of the exponent over **every pair** of interior points (6 pairs), each with
its own interval from the stored resamples, and codes each pair like any other reading: a pair whose interval
is wholly beyond the margin (`POS`) is `VARIES`, one inside the margin (`SLOW+`) is `CONSTANT`. One resolved
pair is enough to say the exponent varies, so f1 is `VARIES`, because `0.0->0.21` and `0.07->0.21` are
resolved. A family never invents a number: each of these is a stored resample difference, and nothing is
measured again.

**f2, the growth along the line is marginal.** Fingerprint 2 is the `along` instrument:
for each **consecutive** pair of interior points it reads how the difference of the two points grows with the
lattice size. The pair is read only if both of its points are on the manifold (the membership door; part of
`HOWTO.md`). All three pairs read `ZERO!` (inside the margin), which the rulebook codes `MARGINAL`.
Marginal growth needs every pair, not one.

**The row** (the last two lines). The three columns are looked up in the family rulebook's partition, exactly as
a point's signature row is looked up in `verdict.toml`: bracket not measured, f1 `VARIES`, f2 `MARGINAL` is
the row at `family.toml` line 55, `LINE`. Its `why` cites the reasoning: both fingerprints resolved, and the
POINT manifolds of X7a do not reach f2 `MARGINAL`.

**Why LINE, and how close it is.** Look at the boundary pair, `0.14->0.21`, with the pair trace of `explain`:

```
```

(Here the `explain` pair trace, steps 1 to 3 is the same text that HOWTO prints, once: see [Along, and membership as a door value](HOWTO.md#along-and-membership-as-a-door-value).)

```
  4 READING   y_along -0.1111  interval [-0.2479, 0.005093]  (95 %, 400 block resamples)
  5 SIGN      cuts -0.25 0 +0.25 (eps y): bL 1, bU 2 -> ZERO!
  6 CODE      family.toml line 52 [f2.code]: ZERO! -> MARGINAL
```

The membership door (step 1) is `RUN-FLAG-U`: the pair ran, and carries the flag U (membership unchecked)
because the needle was not measured. Steps 2 and 3 are the statistic: the difference of the two points at each
size, then the logarithm of its size, then A over the size chain and B accumulated along it, divided by the log
of the size span. The interval is `[-0.2479, +0.005]` against the margin `-0.25`: the lower end is **0.002
inside** the margin, so the cell is `ZERO!` (step 5) and the code `MARGINAL` (step 6). Had the lower end fallen
below `-0.25`, the cell would be `UNRES`, f2 would be `UNRES`, and the family would read
`REFUSE-UNCLASSIFIED-v0` instead of LINE. The family verdict is therefore real and resolved, and also close: that is exactly what the pair trace
is for.

## Part 4: a point that refuses and a family that does not (v04-rules)

`bin/cc explain x5n-bilayer-2 0.0 --tables v04-rules` ends with the verdict `REFUSE-PROBE-INCOMPLETE`. Read it from the bottom:
step 12 (COMPOSE) takes the geometry as the probe left it, step 10 (PROBE) is the row that replaced the geometry POINT of step 9,
and the `probe INCOMPLETE` line says why: `inputs/x5n-bilayer-2/couplings.toml` declares the couplings K and g, and `across` probes only K.
One probed direction cannot tell a point from a line, so the point refuses and the `why` sends you to the family.

`bin/cc family x5n-g --tables v04-rules` reads the same system over its three g values: f1 CONSTANT (the exponent does not change),
f2 IRRELEVANT (the difference between neighbouring g shrinks relative to the size), so the verdict is POINT-MANIFOLD, class POINT.
The point class is earned by the family, never by one probed direction. HOWTO has the full transcripts and the rules.

## Part 5: where a line ends (v05-rules)

A line of fixed points has an end. `bin/cc family x2b-xy --tables v05-rules` reads the XY temperature sweep X2b: five low-phase temperatures
(the **interior**, T <= 0.85) and then T_KT = 0.89294, 0.95, 1.0 and 1.1. Read it from the top.

1. `bracket BRACKET-DOWN`: along the chain the needle goes from MID to DIS once (edge `0.89294->0.95`). v05 reads either direction; v01 to v04
   would have called a T-ordered chain NON-MONOTONE.
2. `f1 UNRES`, `f2 WEAK`: three of the ten f1 pairs are unresolved, so f1 is unresolved; and three of the four neighbour pairs shrink slowly
   with size (SLOW-), so f2 reads WEAK, not MARGINAL. Neither fingerprint gives the LINE signature (f1 VARIES with f2 MARGINAL) here, and f2 is
   not IRRELEVANT either, so the POINT-MANIFOLD row does not fire.
3. `points NOT-LINE`: LINE needs every interior point to read LINE, and the list below it shows T 0.6 reading WALKING.
4. `lower OPEN`, `upper END-BKT-CANDIDATE`: the upper side's boundary is 0.89294 (MID, flow STOPPED) and what lies beyond it (0.95, 1.0, 1.1) is
   disordered, with the two starts agreeing. A line ended in a disordered phase.
5. `end 0.89294 (bracket 0.89294 .. 0.95)`: the end is a bracket, the boundary and the first point beyond. T_KT lies inside it.
6. The verdict is a refusal, `REFUSE-UNCLASSIFIED-v0` (its printed `why`, "no positive row yet", is the default of a cell the rulebook has no
   positive row for): BKT-END needs the interior to read LINE, and it does not. The family found the end and declined to name it.
   T_KT is a grid point of this sweep (0.89294), so "the bracket contains T_KT" is nearly automatic; the check that still bites is an end that
   sits too early or too late.

Two cautions travel with every BKT-END. A sweep that merely leaves its manifold reads the same as a real end. And just above T_KT the correlation
length exceeds the largest size, so an end bracket can sit too high; a bracket that does not contain T_KT is a finite-size miss. HOWTO has the rows.
