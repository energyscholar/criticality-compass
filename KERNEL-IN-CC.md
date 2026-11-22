# The kernel in CC

What the nine instruments of the verdict path compute, and the family fingerprints, in the kernel's terms, and where the code is built so that a wrong state
cannot be reached instead of being checked for afterwards. You do not need this to use CC (`README.md` is
enough). Read it when you want to know what a number means, or before you touch an instrument.

## Why CC uses relational math

A is the graph incidence operator (`cc/kernel.py:72`); B and R build on it; the maths is standard. What CC takes from the relational method (credited in `README.md`, "Acknowledgements") is a rule about what may reach them:

- Before A, only an added constant, `x + c` (`cc/intake_terminal.py:152`).
- Every relation is declared, with its provenance, before any data are touched (`cc/admit.py:28`).
- Input the door cannot admit is refused with a stated reason: a cycle, an undeclared provenance, a non-finite value, an endpoint outside the nodes (`cc/admit.py:33-58`). Past the door a refusal is a value that carries its reason (`cc/door.py:22`).

The method (structure, not control) is that invalid states cannot be reached, instead of being checked for afterwards. That is what makes the needle hard to fool: a cycle, an undeclared provenance, a non-finite value and an out-of-range endpoint never reach A, and a smoothed or interpolated series is not admitted before A. So `cc/kernel.py` holds no `if`: each value it receives was built by the door as a frozen type. The idioms are explained in `docs/READING-THE-CODE.md`; `docs/try-to-break-it.md` has commands that try to break the door.

If an input is wrong, extend the refusal in `cc/admit.py`. Do not add smoothing, interpolation, clamps or guards downstream.

## Kernel V8 on one page

- A **NodeField** is one scalar for each node of a declared set of nodes: the 27, 81 and 243 sizes with one
  number each, or the two starts with one number each.
- A **declared relation** is a set of nodes and directed edges, each edge with its provenance, declared before any
  data are touched; the kernel refuses a relation with a cycle. On the current inputs the one candidate is the
  `control` edge between two neighbouring points (`along`, `across_delta`, `stability_delta`), pending an external verifier (ruling R2).
- A **declared comparison** (an external verifier, 2026-10-06) is a set of ordered differences between values observed
  independently, each through its own M, that the analysis supplies: the blocking-map comparison of independent
  sizes (`size`, `matched`, `chain`: one blocking step relates L to L/3) and the two-start difference (`start`,
  pending an external verifier (ruling R1)). It is not a kernel relation and claims no provenance (not Coupling, not Continuation, not
  Persistence); it is admissible in a downstream projection C. `m.toml` declares both in its `[relations.*]`
  tables, from a closed set of templates; plan 1337 moved the comparisons into C (`project.Comparison`, built only by
  `door.comparison_for`, with no provenance and no src/tgt, so neither `admit.declare` nor `kernel.A`/`B` can take one).
  `door.STANDING` is the total table name -> standing: on a comparison `provenance` is optional and never read, on
  `control` it is required; every result records it as `standing`. In `explain`, step 3 prints each by its name as
  COMPARISON or RELATION (`cc.toml [step_labels]`), and `cc.toml [projections.<name>]` says what each comparison
  keeps and discards.
- An **EdgeField** is one scalar for each declared edge.
- **A** is the kernel's one operator that takes a NodeField to an EdgeField: for each declared edge,
  `A(x)[edge] = x[source] - x[target]`, the difference of the two node values. The size-direction differences are
  the same arithmetic computed as a C comparison, not a relational reading ("A over that size edge as the needle:
  NOT ADMISSIBLE"): plan 1337 moved them into C (`project.Comparison`, read by `project.compared`), and step 4 of
  `explain` prints `C` (or `C+KERNEL` where a control edge is also read) to say what the number is. Where CC wants a
  NodeField again it declares a projection and says what the projection keeps and discards.
- **B** (accumulation along continuation) and **R** (circulation) are unused as kernel operators on any current
  input. `along` (below) sums the steps of its size comparison to the top edge: `B(g)[e] = g[e]` plus the sum of
  `g[f]` over the edges that continue `e`, which over a comparison is the plain C sum it already is: since plan 1337 the code computes it inside C
  (`project.continued`) and calls `kernel.B` nowhere. `kernel.uses` lists `["A"]`, or `["A", "B"]` when `along` is
  declared: after plan 1337 a frozen `operators` field lists the operators the instrument's *design* names, and the
  comparisons now run inside C (only `control` reaches `kernel.A`). Plan 1337 is a measurement epoch: door, project and the instruments sit inside
  `schema.measure_hash`, so every stored result's reuse key moves (the frozen ones included) and each is re-measured
  before it is reused or frozen; what a result says does not change, but for the new `standing` field.
- **M** is what an input declares: its `m.toml`. It says which nodes, which comparisons and relations, which
  margins; CC refuses to run anything the M did not declare.

The data are never the nodes. A node holds a number reduced from data (a mean, a covariance); the reduction is
step 2 of `explain`, and it is applied identically to the original data (row 0) and to every resample.

The simulator enters M as a declared transducer, never as an observable of its own: `inputs/<id>/transducer.toml` names the
sampler (the frozen toolset file and its sha256), and says that one recorded configuration is one observation and that the
recorded sequence is not a process sequence. The per-locus mean is a declared bounded reduction before A, with what it keeps
(the typical value of the observable at the locus) and what it discards (the configuration-to-configuration variation and the
order of the configurations) stated in that file. The bootstrap interval is a projection C: it places the reading's sign cell
against its declared margin, and is never an operator input (an external verifier). The same holds for the Gamma-method interval: its window W and integrated autocorrelation time are statistics of the projection C and feed the sign cell only (gamma is declared but NOT yet used on real inputs; plan 0878 recorded a one-cell disagreement with the bootstrap twin, pending a numbered explanation).

## The comparisons and relations, in ASCII

An arrow points from an edge's source to its target. The difference is source value minus target value.

```
size comparison (chain)      27 <- 81 <- 243            edges: 81 -> 27, 243 -> 81
start comparison (pair)      random <- ordered          edge:  ordered -> random      (pending an external verifier (ruling R1))
matched comparison (big 243, small 81)

   big 243:    L0   L1   L2   L3
                    \    \    \
   small 81:      L0   L1   L2        edges: (243,L1)->(81,L0) (243,L2)->(81,L1) (243,L3)->(81,L2)
```

The matched comparison pairs a big and a small system at the same block-lattice size, one blocking step apart
(the blocking map). One relation is declared for `along` and the delta instruments (pending an external verifier (ruling R2)), and the
families take their differences inside C over index pairs of the same two shapes:

```
control relation over points 0.0 <- 0.07 <- 0.14 <- 0.21        edges: 0.07 -> 0.0, 0.14 -> 0.07, 0.21 -> 0.14
all-pairs (family f1, in C)  0.0, 0.07, 0.14, 0.21              pairs: every (j, i) with i before j (6 for 4 points)
```

An `along` unit is one edge of the control relation, restricted to its two points (edge `b -> a`).

## The nine instruments of the verdict path

CC has 11 instrument modules: the nine the verdict path reads (needle, across, stability, two_start, fluct, along, needle_chain, across_delta, stability_delta), needle_o (a start test: the needle's maths on the ordered start, so it needs no section), and transform — an independent conventional estimate, not a Compass reading (its own section below). The sections below follow the order the verdict path reads them.

### needle: does one more blocking step move the observable, and where does it sit?

- **Comparison:** `matched`. **Nodes:** the observable `g1` of the big system's four block levels and the small
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

- **Comparison:** `size` chain. **Nodes:** `ln(s * R)` at each size, where `R` is the covariance of the
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

- **Comparison:** the size chain, then a second chain over the *steps*: one node per step's exponent.
  **Operator:** A over the steps chain, at the last edge.
- **Reads:** `d`, the change of the exponent from the second to the last step: `y_last - y_prev`.
- **Means:** a walking or crossing fixed point makes the exponent drift with size; a stable line does not.
  `d` inside its margin: STABLE. Above it: CROSSING.
- **A number:** w2-potts at q = 5: the steps are `[1.598, 1.679]`, so `d = 1.679 - 1.598 = 0.08076`; its
  interval `[-0.3098, 0.5382]` straddles zero and a margin edge, so the cell is UNRES.

### two_start: do two ways of starting agree?

- **Comparison (pending R1):** `start`, a `pair` over the two starts, one edge per size. **Nodes:** the order parameter averaged from each
  start, divided by its declared unit scale. **Operator:** A over the pair, `D = ordered - random`.
- **Reads:** `D` at each size (the instrument is coded per size, then the sizes are combined by the codes
  table's `combine`).
- **Means:** at a continuous transition, the two starts reach the same value (`D` near zero). At a first-order
  transition, they can stay apart (`D` above the margin): coexistence. `D` below the margin (the ordered start
  lower) is not coexistence but a fluctuation, and is coded separately.
- **A number:** w2-potts at q = 5, size 27: the starts give `0.7659` (random) and `0.7629` (ordered), so
  `D = 0.7629 - 0.7659 = -0.00301`, interval `[-0.008733, 0.001665]`, inside the margin of 0.01: `ZERO!`, which
  the table codes INDEP.

### fluct: does the variance of the energy density persist with size?

- **Comparison:** the `size` chain. **Nodes:** `ln var(e)` at each size, `e = E / unit_scale`, the energy per bond (the
  `unit_scale` is declared in the input's `[two_start]` table). **Operator:** A over the size edges, divided by the log of
  the size ratio, like `across`; the door gives `ln` a positive argument by construction (variance is positive).
- **M keeps** the second cumulant of the density and **discards** its higher cumulants and the time order of the snapshots.
  Nothing but a declared unit scale acts before A.
- **Reads:** `y_last`, the exponent of `var(e)` with size. A continuous transition has `var(e) ~ L^(-d + alpha/nu)`, so `y`
  is negative (`VANISHES`); at a discontinuity `C ~ L^d` makes `var(e)` stay (`y` inside the margin: `PERSISTS`); above the
  margin is `GROWS`. Margin `eps.y = 0.25`, cut at zero: no new constant.
- **Means / trap:** a witness, read by `order.toml` only and only when the two starts agree (INDEP). Under COEXIST a run that
  does not tunnel has a within-phase variance that vanishes, so there it is never evidence (the q = 7 trap). At q = 5,
  L << xi, the variance falls as at a continuous point: the blind spot is structural, a resolution limit.
- **A number:** w2-potts-2 at q = 3: `y_last = -1.564`, interval `[-1.615, -1.513]`, `SIG-`, so `VANISHES`.

### along: how fast does the difference between two neighbouring points grow with size?

- **Relation (pending R2):** a pair unit, one edge of the declared `control` relation (a chain over the points,
  `a <- b`). **Comparison:** the `size` chain. **Nodes:** first the observable of the two points at each size (two nodes, one pair, per size),
  then `ln(s * Delta)` at each size, where `Delta` is the difference of the two points. **Operators:** A over
  the control edge gives `Delta(L)`; A over the size chain gives the step of `ln(s * Delta)`; B over the size chain
  accumulates the steps to the top edge; the sum is divided by the log of the size span.
- **Reads:** `y_along`, the growth exponent of `|Delta|` with system size. Before any of this, a **door** reads
  whether both points are on the manifold: the pair's membership (from the rulebook's `membership.toml`) decides
  whether the pair runs at all, and a refused pair is a door value (`REFUSE-OFF-MANIFOLD`), not an error.
- **Means:** the points are the same line when `Delta` does not grow or shrink with size beyond the margin:
  `y_along` inside it is `ZERO!`, marginal. Above the margin the points separate as the lattice grows (they sit on
  different fixed points); below, they come together.
- **A number:** b7-at-line-2, the pair `0.14->0.21` (`explain b7-at-line-2 0.14->0.21`): `Delta` is `0.05402`,
  `0.05431` and `0.04232` at sizes 27, 81 and 243, so `ln|Delta|` is `-2.918`, `-2.913`, `-3.162`; A over size
  gives `0.005433` and `-0.2495`; B accumulates them to `-0.244`; over the log span `2.197` that is `-0.1111`,
  interval `[-0.2479, 0.005093]`, inside the margin of 0.25: `ZERO!`.

### needle_chain: does the needle's velocity die away down the size chain?

- **Comparison:** `chain` (template `matched-chain`): the needle's matched comparison taken at two neighbouring size pairs,
  (243, 81) and (81, 27), laid end to end; then a chain over the two **steps**. **Nodes:** the level means of all three
  sizes (twelve nodes here). **Operator:** A over each matched pair gives that pair's velocity; `ln|v|` of the two
  velocities goes through `door:logcoord`; A over the steps chain, divided by the declared `ln(size ratio) = ln 3`.
- **Reads:** `drift = omega_eff - 1`, where `omega_eff = -A(ln|v|) / ln 3` is the rate at which the velocity decays per
  blocking step. Read against `[eps] drift = 0.5`. `velocity_prev` (the smaller pair's velocity) is reported, not coded.
- **Means:** a velocity that shrinks faster than the size grows (omega_eff above 1 by more than eps) is a finite-size
  correction dying away: `drift_code` CONVERGING. Within eps of 1: MARGINAL-DRIFT. Below: PERSISTENT, a genuine slow
  flow. The derived `flow` column is a total table over (flow of the top pair, drift_code): SLOW with CONVERGING reads
  STOPPED; every other cell is the top pair's flow. `drift_code` stays in every result and is read by no verdict row.
  Where the velocity changes sign at the estimate or any resample, `ln|v|` is not defined and the drift is
  NOT-EVALUATED with that reason; the flow is then the top pair's, as on an input with one size pair.
- **A number:** x2b-xy-2 at T 0.7: the top pair's velocity is `0.001459` (the needle's `v_all [0.07625, 0.01112,
  0.001459]`, last edge), the (81, 27) pair's velocity is `velocity_prev 0.011158` (report). `ln 0.011158 - ln 0.001459 =
  2.034`, over `ln 3 = 1.0986` gives `omega_eff = 1.852`, so `drift = 0.8515`, interval `[0.7556, 0.9427]`, cuts
  `-0.5 0 +0.5`: `SIG+` -> CONVERGING (codes.toml line 211). The velocity itself reads `SLOW+` (eps step 0.01) ->
  flow_top SLOW, and `flow = STOPPED (codes.toml line 226)`. At T 0.89294 the drift is
  `NOT-EVALUATED (sign of velocity not constant across the point estimate and every resample)`.

### across_delta: how the difference between two neighbouring points grows with size (the TRANSFORMED door is v07 only)

- **Relation (pending R2):** one edge `a -> b` of the declared `control` chain (here T increasing). **Comparison:** the `size` chain.
  **Nodes:** the mean observable of the two points at each size; then `ln(s Delta)` at each size, `Delta(L) =
  g1(b) - g1(a)`, with `s` the constant sign the door found. **Operator:** A over the control edge gives `Delta(L)`;
  `door:logcoord`; A over the size chain divided by `ln 3` gives the step exponents `yD1` (27 -> 81) and `yD2`
  (81 -> 243). This is `along`'s difference read as `across`'s exponent at the top step, with the same eps (`y`).
- **Door (the pair basis, v07):** `membership.toml [across_delta]` reads both endpoints' `drift_code`; both
  CONVERGING -> door value TRANSFORMED and `r` = the mean over the two endpoints of `3^-(drift + 1)` per resample
  (the needle's own |v_top|/|v_prev|); any other pair -> RAW, `r = 0`. `door:basis` refuses a TRANSFORMED pair where
  `r >= 1` anywhere (NOT-EVALUATED). A set with no `[across_delta]` rule reads every pair RAW (`member_default`).
- **Reads:** `y_last = (yD2 - r yD1) / (1 - r)` (so `yD2` on a RAW pair). It is `per_point`: a point reads the cells
  of every control pair touching it, combined by `codes.toml [columns.helper.across_dlt]`: only the TRANSFORMED pairs
  when it has one; a resolved code counts only when every combined pair reads it, else UNRES. The signature column
  `across` is then ONE declared choice per input: `across_dlt` when the input declares `across_delta`, else the
  covariance `across_cov`; a declared delta that is NOT-EVALUATED reads UNRES, never the covariance.
- **Means:** two points on the same line keep a difference that neither grows nor shrinks with size beyond eps:
  MARGINAL. Above: RELEVANT (they sit on different fixed points). On a pair read on the TRANSFORMED basis (v07), the reading is the transform's limit rather than the exponent at L 243: a transform-basis claim, not relationally admissible (an external verifier (ruling Q3), 2026-10-05; see Rulings below), superseded by the Delta-basis sets (v08).
- **A number:** pair `0.7->0.8`: `Delta` is `-0.02660, -0.02436, -0.02412` at 27, 81, 243 (sign constant, `s = -1`);
  `ln|Delta| = -3.627, -3.715, -3.725`; `yD1 = -0.0802`, `yD2 = -0.00913` (report `y_steps`). Both endpoints read
  CONVERGING (drift 0.8515 and 0.8781), so the door is TRANSFORMED and `r = (0.1308 + 0.1270) / 2 = 0.1289` (report
  `ratio`); `y_last = (-0.00913 + 0.1289 x 0.0802) / 0.8711 = 0.00139`, interval `[-0.008635, 0.01197]`, `ZERO!`
  -> MARGINAL (codes.toml line 277). Pair `0.85->0.89294`: 0.89294's drift is NOT-EVALUATED -> OTHER -> RAW, `r =
  0`, `y_last = yD2 = 0.04746 [0.02579, 0.06894]`, `SLOW+` -> WEAK. Point 0.7 combines `0.6->0.7` and `0.7->0.8`, both
  TRANSFORMED and MARGINAL -> MARGINAL; `across = MARGINAL (codes.toml line 297)`.
- **What `explain` prints:** `explain <input> a->b` prints one section per instrument that reads the pair, each from its own stored vectors (plan 0881 P2.1). Under `across_delta`: `Delta` per size, then the stored `y_steps` (`yD1`, `yD2`) and `ratio`, then the reading, the sign and the family code. For `0.85->0.89294` on x2b-xy-3: `y_steps [0.09186, 0.04746]; ratio 0`, `y_last 0.04746 [0.02579, 0.06894]`, `SLOW+`; the `along` section of the same pair keeps its own `ln|Delta|`, A, B trace (`y_along 0.06966`).
### stability_delta: does the difference estimator's exponent change between size steps?

- **Relation (pending R2):** one edge `a -> b` of the declared `control` chain; **Comparison:** the `size` chain, as `across_delta`. **Operator:** A over the control edge gives `Delta(L)`; `door:logcoord`; A over the size chain gives the step exponents `yD1`, `yD2`; `door:steps`, then A over the chain of those steps gives `d = yD2 - yD1`. It reads no drift and no transform, and needs no membership door: the column is the same under every rule (plan 0877, `v08-rules`).
- **Reads:** `d`, per control pair, against `eps y` (0.25), `per_point`: a point reads the cells of the pairs that touch it and every pair must agree to resolve. This is stability on the Delta basis: where v06/v07 reported a TRANSFORMED cell, v08's alphabet has none.
- **Means:** the exponent of the difference holds from one size step to the next (STABLE) or it changes, without any finite-size correction being assumed.
- **A number:** x2b-xy-3, pair `0.85->0.89294` (`bin/cc explain x2b-xy-3 '0.85->0.89294' --tables v08-rules`): `y_steps [0.09186, 0.04746]`, so `d = 0.04746 - 0.09186 = -0.0444`, interval `[-0.08474, -0.003254]`, cuts `-0.25 0 +0.25`: `SLOW-`. The sign cell is not a stable reading: plan 0889 records that a sign cell whose deciding endpoint lies inside its interval method's own resample noise is not a stable reading (6 of 11 bootstrap seeds read `ZERO!`); the Gamma-method interval (plan 0878) is the deterministic centre.

## Not an instrument of the verdict path: transform

### transform: an independent conventional estimate — not a Compass reading (reported, read by no row)

- **Comparison:** the `size` chain (for `R = cov(G, E)` at each size, as `across` and `stability`) and the
  `matched-chain` (for the needle's two velocities, as `needle_chain`). **Operator:** A over the size chain gives
  `y1`, `y2`, the growth exponents of `ln(s R)` over the two steps; A over the matched pairs gives the two velocities;
  `ln r = ln|v_top| - ln|v_prev|` (`door:logcoord` on both); `door:decays` refuses unless `ln r < 0` at the estimate
  and every resample.
- **Reads:** `y_inf = y2 + r (y2 - y1) / (1 - r) = (y2 - r y1) / (1 - r)`: the limit of an exponent whose correction
  decays by the factor `r` per blocking step. `r` is the ONE point's own ratio (across_delta uses the mean of two
  endpoints). Helper code `y_inf_code` (RELEVANT .. IRRELEVANT, eps `y`), flag H (uses the conjugate);
  NOT-EVALUATED where `R` or `v` changes sign or the correction does not decay.
- **Means:** an independent conventional estimate — not a Compass reading (an external verifier (ruling Q3), 2026-10-05: there is no observation at infinite size, and the shared-omega assumption is an undeclared prior). It is what a conventional finite-size extrapolation would give if the needle's correction were the whole finite-size effect. No verdict row in any set reads it, and none in any set after v07 may; plan 0877 keeps it report-only in v08.
  `stability` TRANSFORMED is the related, row-read fact:
  `d = y2 - y1` inside eps on a CONVERGING point.
- **A number:** T 0.7: `R = 0.1146, 0.107, 0.1026` at 27, 81, 243; `y_steps [-0.06243, -0.03832]` so `y1 = -0.06243`,
  `y2 = -0.03832` (the `across` trace); `r = 0.001459 / 0.011158 = 0.1308`; `y_inf = -0.03832 + 0.1308 x 0.02411 /
  0.8692 = -0.03469`, interval `[-0.1551, 0.0672]`, `ZERO!` -> `y_inf_code MARGINAL` (readings of
  `results/x2b-xy-2@v07-rules.json`: `transform.y_inf`). `d = y2 - y1 = 0.02411 [-0.09121, 0.121]` is `stability_raw`
  STABLE, so `stability = TRANSFORMED (codes.toml line 363)`. At T 0.89294: `NOT-EVALUATED (sign of R not constant across the point estimate and every resample)`. `show` and `explain` print the `y_inf` reading with the label above (`cc.toml [conventional]`: one declared string; plan 0881 P2.3).

## The family fingerprints

A family reads the points of one input together, from the stored result and its resample vectors; it never
measures again. Its columns are ordered differences of stored readings over the interior run (the paragraph "The
family layer is a projection C" below says where they are computed and what the verdict is):

- **bracket: ordered differences of ranked codes, inside C.** Each point's needle code is given a declared rank
  (DIS 0, MID 1, ORD 2), and the ranks, in the points' declared order, are differenced neighbour by neighbour
  (`rank(i+1) - rank(i)`; `fingerprint.code_steps` over `chain_pairs`). Each difference is placed among the cells for `eps = 0` (three cells), so a step down is
  `DESCENT` and anything else is `NO-DESCENT`; the bracket is `BRACKET` when no step descends and some point is MID.
- **f1: all-pairs differences, inside C.** The stored reading of each interior point, per resample, is differenced
  over every index pair (`y(j) - y(i)`; `fingerprint.pair_differences` over `all_pairs`; 6 pairs for 4 points), each
  with its own interval, coded by its sign cell.
- **f2: along over the chain.** The `along` cell of each consecutive pair of interior points, coded through
  `[f2.code]`.

Where a point reads a null (`NOT-MEASURED`, `NOT-EVALUATED`), the edges and pairs that touch it read that null: a
null is plumbing around the maths, and only ranked codes reach the differences. The family verdict is one lookup in a
partition of the three columns (`family.toml`), validated total and disjoint, with no priority chain.

**The family layer is a projection C (an external verifier (ruling Q19), 2026-10-06).** The bracket and f1 differences are computed inside C, as
ordered differences of the stored per-point readings over the interior run (`y(j) - y(i)` for the `across_delta.y_last`
vectors, `rank(i+1) - rank(i)` for the needle codes); they are not A over a declared relation, and the family layer is not a
second relational pass. This supersedes the former sentence "Its three columns are built with the same operators" and the
former headings "A over a chain of codes" and "A over the `all-pairs` relation" (both corrected above). Plan 0892 P2 made the
code say so: `cc/fingerprint.py` imports no kernel, admit or door, and computes the same arithmetic over index pairs in the
door's former edge order (every family transcript byte-identical). The family verdict (LINE, BKT-END, POINT-MANIFOLD,
REFUSE-*) is a **declared report**, a projection C over per-point sign cells, not a relational reading; the sign-cell rule
stands unchanged. `bin/cc family` prints `=> family report` and the label `cc.toml [report] family` under it.

**Under method `chains` (plan 0978).** The family layer reads an input of method `chains` through the same stored cells; only f1 reads a vector, and it reads the per-chain differences `d_k = y_k(j) - y_k(i)` of rows 1..m (row 0 is a copy of chain 0), whose order statistics `[d_(r), d_(m+1-r)]` are the interval of `median_k(d_k)`: an estimand that coincides with the difference of the two medians only when `d` is symmetric (declared, as T7-B). An end bracket localises to one grid interval; it carries no joint coverage over the cells it reads. Method `gamma` has no per-row difference vector, so f1 reads NOT-EVALUATED there (a row of the readout table, not an exception).

**The per-point verdict path is a projection C as well (an external verifier, 2026-10-06).** The per-point sign cells the family
reads are themselves sign cells of declared comparisons: the blocking-map comparison of independent sizes (the needle's
matched levels, the size chains) and the two-start difference (pending an external verifier (ruling R1)), each computed inside C, not A over a
kernel relation. The per-point verdict is a **declared report** too; `show` prints the label `cc.toml [report] verdict` once
under each result header, and `explain` labels steps 3 and 4 COMPARISON and C. Both labels are one table, `cc.toml [report]`;
the verdict words and the tables are unchanged. The code that computes the per-point differences calls `kernel.A`
no more: plan 1337 moved them into C (`project.Comparison`; a change that moves every measure key, the plan 1337 epoch); the labels say what the numbers are.

The declared interior rule `interior = "mid-run-open"` is a projection C over the needle sign cells: it keeps the MID run (less the end a sink lies beyond), discards every value and every other column, and reads nothing else.

## Geometry and order: one verdict as two axes

`v02-rules` reads the signature row twice and composes. The **geometry** axis (`geometry.toml`) is the verdict the rulebook
gives when the two starts are taken to agree: it reads needle, flow, across and stability and nothing else. The **order**
axis (`order.toml`) reads needle and two_start and nothing else: COEXIST-AT-WINDOW, NOT-EQUILIBRATED, EQUILIBRATED, and the
position rule and the honest nulls as values (OFF-WINDOW, NEEDLE-UNMEASURED, ORDER-UNMEASURED). `compose.toml` is a partition
of (geometry, order); `validate` proves that it gives `verdict.toml`'s verdict on every row of the signature domain, so the
factorisation is a refactor and nothing else: `bin/cc tabulate --diff v01-rules v02-rules` prints 0 cells and 0 points. What
it buys is that a coexisting point still has a geometry, and a non-coexisting point still has an order, without a side
table. No operator is involved: both axes are lookups in tables, so this section changes no kernel declaration.

## What the rulings bound (an external verifier, 2026-10-05)

These are rulings about what CC may claim and what it does not implement. The Q0 ruling is the transducer paragraph under "Kernel V8 on one page".

- **Q1 - reweighting.** Reweighting the configurations is outside the relational treatment. The navigator never acts on a reweighted quantity as a reading, and nothing in CC implements it.
- **Q3 - the transform.** There is no observation at infinite size; the shared-omega assumption of the finite-size transform is an undeclared prior. The `transform` output is an independent conventional estimate — not a Compass reading; no verdict row in any set after v07 may read it. The v06/v07 claims that rest on a TRANSFORMED basis (`x2b-xy-2@v06-rules` and `@v07-rules`: LINE, BKT-END) are transform basis — not relationally admissible; superseded by `x2b-xy-3@v08-rules`.
- **Q19 - the family layer (2026-10-06).** Not admissible as a second relational pass; admissible as a declared projection C over per-point sign cells. The family verdict is a declared report (above, "The family fingerprints").
- **The needle (2026-10-06).** The L and L/3 observations are each admissible through their own M; "L -> L/3 as a Kernel edge: NOT ADMISSIBLE"; "A over that size edge as the needle: NOT ADMISSIBLE"; the declared blocking-map comparison is admissible in a downstream projection C. The needle is restated as a C comparison; no provenance class is added and Coupling is not broadened. The per-point verdict is a declared report (above).
- **Q4 - the star.** A single edge is the Primary kernel, Delta to Sigma. A radial chain is A, then B, then R, with `rho_base` and `chi_0` declared (plan 0885).
- **Q5 - stacks.** Simulated stacks are Phase 1 only; real movies are Phase 2 eligible.
- **The principle.** Universal operators are not a universal model of systems. Every input's M is a complete Origin declaration: what was measured, by what, what a node keeps and discards. Plan 0884 is the first real one.

## Where structure replaces control

The rule for any code that computes: make a wrong state impossible to reach, rather than catch it after. It is
checked mechanically on every commit (`checks.py`: in the files that do the arithmetic, no `if`, no ternary,
no `while`, no `try`, no comparison, no `clip` or `max` or `abs` or default-valued `get`, and no numeric
literal besides 0 and 1 unless the line says where it was declared). In CC it shows in five places (the families read the same way: a lookup in a partition, nulls carried as values):

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
