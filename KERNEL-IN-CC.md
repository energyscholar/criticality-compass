# The kernel in CC

What the four instruments compute, in the kernel's terms, and where the code is built so that a wrong state
cannot be reached instead of being checked for afterwards. You do not need this to use CC (`README.md` is
enough). Read it when you want to know what a number means, or before you touch an instrument.

## Kernel V8 on one page

- A **NodeField** is one scalar for each node of a declared set of nodes: the 27, 81 and 243 sizes with one
  number each, or the two starts with one number each.
- A **declared relation** is a set of nodes and directed edges, each edge with its provenance (here `Coupling`),
  declared before any data are touched. CC builds every relation from a closed set of three templates, in
  `m.toml`, and the kernel refuses a relation with a cycle. In `explain`, a relation prints as step 3.
- An **EdgeField** is one scalar for each declared edge.
- **A** is the one operator that takes a NodeField to an EdgeField: for each declared edge,
  `A(x)[edge] = x[source] - x[target]`, the difference of the two node values. There is no other way to get an
  EdgeField, and no implicit way back; where CC wants a NodeField again it declares a projection and says what the
  projection keeps and discards.
- **B** (accumulation along continuation) and **R** (circulation) are not used in v0. `kernel.uses = ["A"]` on
  every input.
- **M** is what an input declares: its `m.toml`. It says which nodes, which edges, which margins; CC refuses to
  run anything the M did not declare.

The data are never the nodes. A node holds a number reduced from data (a mean, a covariance); the reduction is
step 2 of `explain`, and it is applied identically to the original data (row 0) and to every resample.

## The relations, in ASCII

An arrow points from an edge's source to its target. `A` is source value minus target value.

```
chain over size              27 <- 81 <- 243            edges: 81 -> 27, 243 -> 81
pair over starts             random <- ordered          edge:  ordered -> random
matched (big 243, small 81)

   big 243:    L0   L1   L2   L3
                    \    \    \
   small 81:      L0   L1   L2        edges: (243,L1)->(81,L0) (243,L2)->(81,L1) (243,L3)->(81,L2)
```

The matched relation pairs a big and a small system at the same block-lattice size, one blocking step apart.

## The four instruments

### needle: does one more blocking step move the observable, and where does it sit?

- **Relation:** `matched`. **Nodes:** the observable `g1` of the big system's four block levels and the small
  system's three, as one seven-node field. **Operator:** A over the matched edges.
- **Reads:** the matched edge at the coarsest equal size is the **velocity**: `g1(big, level 3) - g1(small, level 2)`.
  Two more numbers locate the point against the two trivial fixed points: `d_ord` (the ordered value minus
  `g1`) and `d_dis` (`g1` minus the disordered value).
- **Means:** a velocity of zero (inside its margin) says one more blocking step does not move the observable: a
  fixed point at this size. A velocity above the margin says it is still flowing toward order, below says
  toward disorder. `d_ord` or `d_dis` near zero says the point is at the ordered or the disordered sink
  (trivial fixed points), where the velocity says nothing.
- **A number:** x8-ising-needle at K/K_c = 1.10 (`explain x8-ising-needle 1.10`): `v_all` is
  `[0.104, 0.04434, 0.002561]`, the three matched differences from fine to coarse; the velocity is the last,
  `0.002561`, interval `[0.001996, 0.003151]`, inside the margin of 0.01 and above zero: `SLOW+`. And `d_ord`
  is `3.472e-05`: the point sits on the ordered sink.

### across: how the linear response grows with size

- **Relation:** `size` chain. **Nodes:** `ln(s * R)` at each size, where `R` is the covariance of the
  observable with the energy. **Operator:** A over the size edges, divided by the log of the size ratio of the
  edge.
- **Reads:** `y_last`, the growth exponent of the last step. It carries the flag H in every table: it uses
  Hamiltonian knowledge (the conjugate field), unlike the needle.
- **Means:** the exponent of the response function with system size. Above its margin, the perturbation grows:
  relevant. Inside the margin, marginal. Below, irrelevant.
- **A number:** b7-at-line at 0.07: `R` is 17.93, 59.97 and 195 at sizes 27, 81 and 243. `ln(59.97/17.93) / ln 3
  = 1.099` and `ln(195/59.97) / ln 3 = 1.073`; `y_last` is `1.073`, interval `[1.04, 1.106]`: `SIG+`,
  relevant.

### stability: does that exponent change between size steps?

- **Relation:** the size chain, then a second chain over the *steps*: one node per step's exponent.
  **Operator:** A over the steps chain, at the last edge.
- **Reads:** `d`, the change of the exponent from the second to the last step: `y_last - y_prev`.
- **Means:** a walking or crossing fixed point makes the exponent drift with size; a stable line does not.
  `d` inside its margin: STABLE. Above it: CROSSING.
- **A number:** w2-potts at q = 5: the steps are `[1.598, 1.679]`, so `d = 1.679 - 1.598 = 0.08076`; its
  interval `[-0.3098, 0.5382]` straddles zero and a margin edge, so the cell is UNRES.

### two_start: do two ways of starting agree?

- **Relation:** `pair` over the two starts, one edge per size. **Nodes:** the order parameter averaged from each
  start, divided by its declared unit scale. **Operator:** A over the pair, `D = ordered - random`.
- **Reads:** `D` at each size (the instrument is coded per size, then the sizes are combined by the codes
  table's `combine`).
- **Means:** at a continuous transition, the two starts reach the same value (`D` near zero). At a first-order
  transition, they can stay apart (`D` above the margin): coexistence. `D` below the margin (the ordered start
  lower) is not coexistence but a fluctuation, and is coded separately.
- **A number:** w2-potts at q = 5, size 27: the starts give `0.7659` (random) and `0.7629` (ordered), so
  `D = 0.7629 - 0.7659 = -0.00301`, interval `[-0.008733, 0.001665]`, inside the margin of 0.01: `ZERO!`, which
  the table codes INDEP.

## Where structure replaces control

The rule for any code that computes: make a wrong state impossible to reach, rather than catch it after. It is
checked mechanically on every commit (`checks.py`: in the files that do the arithmetic, no `if`, no ternary,
no `while`, no `try`, no comparison, no `clip` or `max` or `abs` or default-valued `get`, and no numeric
literal besides 0 and 1 unless the line says where it was declared). In CC it shows in five places:

1. **The sign cell is a position among declared cuts.** A reading's cell is `sign(lo, hi, eps)`: the position
   of each interval end among the sorted cuts `-eps, 0, +eps`, counted, then looked up in a table. There is no
   comparison chain ("if lo > eps and ...") and no case that falls through; every position has a name.
2. **A door returns a value, never raises.** Everything that could go wrong with the data (a non-finite value,
   a covariance that changes sign across resamples) is checked by the door, in plumbing code between the
   stages, and comes out as a value of the output type: `NOT-EVALUATED` with its reason. The maths never sees
   it. It prints as `BLANK (NOT-EVALUATED: R = 0)`; a missing instrument prints as
   `BLANK (NOT-MEASURED: ...)`. A null is an answer, not an exception, and it reaches the verdict.
3. **The per-resample `d` of stability is A over the steps chain.** The steps are re-declared as a NodeField
   over a chain of steps, so `d` is the same operator as every other number, applied per resample. No
   broadcasting of one resample's exponent against another's, and no `abs` to hide a sign.
4. **`ln(s * R)` with `s` declared constant by the door.** The logarithm needs a positive argument. The door
   reads the sign `s` of `R` at the original data and at every resample; if it is the same sign everywhere and
   not zero, the coordinate is `ln(s * R)`, so the argument is positive by construction; if not, the door
   returns the null above. There is no `abs`, no clipping, no `log(max(R, tiny))`.
5. **The verdict is a partition lookup, never a priority chain.** `verdict.toml` is a set of rows that
   `validate` proves disjoint and complete. Exactly one row matches, whatever the order of the file. The
   alternative (test the conditions in a priority order and take the first that fires) is a control program: its
   behaviour depends on the order, and adding a verdict means reading all of it. Here a new rule is a new row,
   and `validate` tells you at once where it overlaps or what it leaves uncovered.

What is allowed to branch is plumbing: the door, the command line and the file checks. It is kept out of the
maths files, and `checks.py` fails the commit if a branch appears in one.
