# CHANGELOG-TABLES - the lineage of the rulebooks, verdict-x-rules .. v08-rules

Written 2026-10-05 (plan 0881 P2) against CC main `e8924b0`+. Sources: HOWTO sections, `expected/<set>.toml [[change]]` blocks (the
declared-before-run locks and the after-run records), `git log`, `tables/<set>/*` headers. Every
set is a fork of its predecessor; `validate` proves each partition. A set's results are frozen only where the freeze rule allows (see the last section).
Each entry: what changed (data, never code paths in a rulebook) / declared effect / what the record says happened.

**verdict-x-rules** - 2026-10-01, plan 0863 (commits 20ab7bd, 6290964, c673ee5; frozen 888dcc4). `codes.toml`
+ `verdict.toml` only: a transcription of the toolset's `verdict_x` (STAGE1 off-window, STAGE2 coexistence,
STAGE3 slow flow, CAND_GS point/line/walking) as a partition with a `why` per row. First locks: the four v0 fixtures
(x8, b7, w2, c2) and x2/x3/x4 from the toolset's frozen result files. Recorded, not repaired: REFUSE-SLOW at six
LINE-truth points (a known rule flaw); NOT at x4's first-order-line decoy; x5-bilayer NOT x3 (known false negative).

**v01-rules** - 2026-10-02, plan 0864 (1c6e32b, 4ad79a8; along/families 3b4e90f, 7994150; frozen 68e5342). The
working default (`cc.toml [defaults]`). Two data changes from one decision: c' (`codes.toml`: needle NEG/POS read
MID not a side; flow NEG/POS read SLOW not FLOWING) and the SLOW split (`verdict.toml`: SLOW + across MARGINAL +
stability STABLE = LINE; every other SLOW cell still refuses). Declared diff: 6 cells, 0 of 60 v0 points move; x5
g 0 and g 0.3 NOT -> REFUSE-SLOW once an input (held). Adds `membership.toml` (along's door) and `family.toml`
(bracket/f1/f2 partition, 240 cells); first family verdict LINE for b7-at-line-2 on a boundary cell (0.002 inside eps).

**v02-rules** - 2026-10-02, plan 0866 P-A/P-B (0166553, 47ba5d5). `verdict.toml` byte-identical; adds
`geometry.toml`, `order.toml`, `compose.toml` and `validate` proves compose(geometry, order) = verdict on all 45 360
rows: `tabulate --diff v01-rules v02-rules` = 0 cells, 0 points. The `fluct` witness (A over ln var(e)) splits
EQUILIBRATED into CONTINUOUS / FIRST-ORDER-TUNNELLING / EQUILIBRATED-UNRES, read only with the starts INDEP.
Rung X9 (w1/w3-potts): one MISS, w1 q4 two_start UNRES (predicted INDEP). Finding: x4-ising-field-3 two_start
FLUCT (a signed order parameter's sign is set by which start is called ordered). Headers still say `v01-rules`.

**v03-rules** - 2026-10-02, plan 0867 P1 (b1ecb47, c7f2de7). + signature column `needle_pair` (the needle of each
start: `needle_o` reads the ordered start's own level stack; a total 3x3 pair table). One new cell: needle at a sink,
PINNED-BETWEEN-PHASES, two_start COEXIST -> FIRST-ORDER (order COEXIST-AT-WINDOW). Predicted effect on existing
inputs: none (no input had `needle_o`); held. x9c-potts: q6/q8/q10 FIRST-ORDER as declared; q3/q4 REFUSE-FLOW seen,
not predicted; q5 two_start UNRES, the allowed marginal-cell difference. `test_run_all` replays this set.

**v04-rules** - 2026-10-03, plan 0870 (f59a8cb .. 9489253). Three declared changes. (1) `probe.toml` + per-input
`couplings.toml`: a positive geometry with an unprobed second coupling reads REFUSE-PROBE-INCOMPLETE (or -UNKNOWN):
x5n-bilayer/-2 lose POINT x6 by declaration, b7-at-line-4's geometry at 0.0/0.07 likewise (verdict unchanged). (2)
`needle_chain` on two matched pairs: `drift_code` (eps drift 0.5, declared in the plan) and the derived `flow`
(SLOW x CONVERGING = STOPPED); two_start `top_only` COEXIST (no stored code moved). (3) POINT-MANIFOLD family row
and its two named siblings; x5n-g reads POINT-MANIFOLD (f2 IRRELEVANT). Recorded findings: x2-xy-line-3 T 0.6
WALKING (a LINE point; the predicted-possible BAD), x3-clock6-3 T 0.5 STOPPED via CONVERGING (verdict NOT anyway).

**v05-rules** - 2026-10-03/04, plan 0871 (1e31da0 .. 8c47857). `family.toml` only. Direction-agnostic bracket
(BRACKET-UP/-DOWN/-FLAT, NO-MID, NON-MONOTONE; FLAT added as a recorded plan gap), new columns `points`, `lower`,
`upper`, the side table (boundary = end of the MID run, G3), end kinds END-BKT-CANDIDATE / -MULTICRITICAL /
-ORDER-UNMEASURED, `end_point`/`end_bracket`, BKT-END rows, LINE with no readable end (G4), an off-manifold f2 read
first (G6); 98 860-cell proof that no v04 family moved. x2b-xy (nine T): three declared predictions MISSED and the
locks widened after the run, marked MISS (T 0.6 WALKING, T 0.89294 POINT, f1 UNRES); end_bracket [0.89294, 0.95]
held; family REFUSE-UNCLASSIFIED-v0. Headers of `verdict.toml`/`codes.toml` still say `v04-rules`.

**v06-rules** - 2026-10-04, plan 0872 (db6145f .. 06d0715). F2 `across_delta` (the difference estimator over the
control chain; the signature `across` reads it when declared, a NOT-EVALUATED delta reads UNRES, never the
covariance; coupling admissibility checked by validate). F1 TRANSFORMED stability: `stability` = total table over
(stability_raw, drift_code); geometry/verdict accept TRANSFORMED where STABLE was accepted; RELEVANT + TRANSFORMED
-> REFUSE-UNRES; the `transform` instrument reports `y_inf` (helper `y_inf_code`, read by no row; an independent conventional estimate — not a Compass reading, see the classification below). F3 end notes in
`show`/`explain`. Declared movers: x2b-xy 0.6 WALKING -> LINE, x2-xy-line-3 0.6 WALKING -> REFUSE-UNRES (held).
x2b-xy-2 (= x2b-xy + across_delta + transform): MISS at 4 of 5 low-phase points (pairs read SLOW- -> WEAK, so
UNRES/WEAK, not MARGINAL); x2b-xy family BKT-END, bracket [0.89294, 0.95]. 16 MISS-marked widenings in this file. **Transform basis:** the TRANSFORMED stability behind x2b-xy-2's LINE at 0.6-0.85 is a transform-basis claim (classification below).

**v07-rules** - 2026-10-04, plan 0874 (a7275b0 .. 1f02463). The frontier. One thing: a control pair whose BOTH
endpoints read drift_code CONVERGING is read on the TRANSFORMED basis, yD_inf = (yD2 - r yD1)/(1 - r), r from the
endpoints' `needle_chain` drift (`membership.toml [across_delta]`, `door:basis`); any other pair RAW; a point
combines only its TRANSFORMED touching pairs when it has one (`codes.toml combine.prefer_door`). Every other table
byte-identical to v06 (the `verdict.toml` header therefore still says `v06-rules`). Every [0874] prediction held
ON THE TRANSFORM BASIS: x2b-xy-2 LINE at 0.5-0.85; family x2b-xy-2 BKT-END, end 0.89294, bracket [0.89294, 0.95] (DEVELOPMENT data, not a
blind score). The only cells that moved v06 -> v07 on 31 inputs: x2b-xy-2 across/geometry/verdict at 0.6-0.85. These LINE and BKT-END
readings are transform-basis claims, not evidence (classification below); `x2b-xy-3@v08-rules` supersedes them.

**v08-rules** - 2026-10-05, plan 0877 P2 (b51b121). The frontier. Declared before any run
(`expected/v08-rules.toml`, from the toolset's 0877-P0 table): a `stability_delta` instrument (stability on the Delta basis, `d = yD2 - yD1` per control pair,
no transform, no TRANSFORMED cell in the alphabet); Bruce's ruling A (the across helpers read SLOW- and SLOW+ MARGINAL, not WEAK); D2 (a covariance
across that is a null no longer blocks a live Delta reading); `family.toml` f1 reads `across_delta.y_last` per consecutive interior pair (the f1 plumbing branch,
test seen RED). The F1 row (RELEVANT + TRANSFORMED = REFUSE-UNRES) is gone: its cells return to the POINT row. v08 applies only to inputs that declare
`stability_delta` (every other input's stability reads NOT-MEASURED under v08 by construction; no scoreboard is claimed for them). What the record says:
`x2b-xy-3@v08-rules` (600k) reads LINE at 0.5, 0.6, 0.7, 0.8, 0.85, REFUSE-UNRES at 0.89294, NOT at 0.95, 1.0, 1.1 (9 of 9 as locked); its family reads
BKT-END, end 0.89294, bracket [0.89294, 0.95] (`bin/cc family x2b-xy-3 --tables v08-rules`). `transform` stays report-only. Plan 0878 added `x2b-xy-4@v08-rules`
(the Gamma-method interval): recorded MISSes, never adjusted, at `stability_delta.d` 0.85->0.89294 (ZERO! vs the bootstrap's SLOW-) and in the window W (18..28).
The cell is not a stable reading: plan 0889 records that a sign cell whose deciding endpoint lies inside its interval method's own resample noise is not a stable
reading (x2b-xy-3@v08, stability_delta.d 0.85->0.89294: 6 of 11 bootstrap seeds read ZERO!); Gamma is the deterministic centre. No stored result changes.

## Classification of the transform-basis claims (Robin Q3, 2026-10-05; plan 0881 P2.4)

Robin's ruling: the transform has no observation at infinite size, and the shared-omega assumption is an undeclared prior. So, in the record:

- `x2b-xy-2@v06-rules` and `x2b-xy-2@v07-rules`: LINE (per point, on TRANSFORMED stability) and BKT-END (the family, via `across_delta` TRANSFORMED pairs) are
  **transform basis — not relationally admissible (Robin Q3, 2026-10-05); superseded by `x2b-xy-3@v08-rules`.**
- What stands: what was run and recorded. The result files, `expected/v06-rules.toml`, `expected/v07-rules.toml` and the v06/v07 table directories are unchanged
  (hash-pinned: the record must show what was). The classification lives here and in `results/README.md`, never in a result or a table.
- The `transform` instrument's `y_inf` is an **independent conventional estimate — not a Compass reading**. It stays printed (with that label), and no verdict row in
  any set reads it; none in any set after v07 may.
- A superseded set is still frozen where it can be (see below).

## The family layer is a projection C (Robin Q19, 2026-10-06; plan 0892)

Every `tables/*/family.toml` header says "the differences are maths (cc/fingerprint.py, by A)". That sentence is superseded by Robin Q19
(2026-10-06): since plan 0892 the bracket and f1 differences are computed inside C (a declared projection over per-point sign cells), not by A
over a declared relation, and the family verdict is a declared report. The tables are unchanged (hash-pinned by every stored result); the
verdict words are unchanged. Plan 0892 P2 (2026-10-08) landed: `cc/fingerprint.py` computes the same differences over index pairs and
imports no kernel, admit or door; every family transcript is byte-identical, and `bin/cc family` prints `=> family report` with the label
`cc.toml [report] family`.

## The per-point verdict path is a projection C (Robin, 2026-10-06, LOG E382; plan 0893 P1, 2026-10-08)

Every table header (`codes.toml`, `verdict.toml`, `family.toml`) that calls a size chain, the matched levels or the two-start pair a "relation",
or its difference "A", is superseded by Robin's ruling of 2026-10-06 (LOG E382): the L and L/3 observations are independent, each through its
own M; the blocking-map comparison between them is admissible in a downstream projection C, and "A over that size edge as the needle" is not.
These are declared **comparisons**; the per-point verdict is a **declared report** (`cc.toml [report] verdict`, printed once under every
`show` header and in each `## Rules:` section of SIGNATURE-TABLE.md). The tables are unchanged (hash-pinned), the verdict words are
unchanged, and no number moves; the code still computes these differences with `kernel.A` until plan 0893 P2. The start comparison is pending
Robin R1 and the control edge (a relation) pending R2.

## Cross-cutting notes

- `cc.toml [defaults] tables = "v01-rules"`: `show`/`run`/`help` without `--tables` read the oldest set.
- A "MISS" is a comment in `expected/*.toml` beside a widened lock, not a field; v06 carries 16 such lines and v07 11.
- Stale headers: v02 (says v01), v05 (says v04), v07 `verdict.toml` (says v06; its `codes.toml` is correct). They are the first comment line of table files whose sha256 every
  result records in its `read`; editing one would make that set's results read as stale, so they are REPORTED here and not edited.
- Results stored per set (`ls results/*@<set>.json`): verdict-x 9, v01 12, v02 21, v03 24, v04 29, v05 30, v06 31, v07 31, v08 2.
- `FROZEN.json` lists 8 verdict-x-rules results, 11 v01-rules results and (plan 0881 P2.7) the 24 v03-rules results, with the table dirs of those three sets. The v02 and v04..v07 results
  record no `measure_hash` (they predate plan 0876), so `freeze` (which compares it with the committed tree's, plan 0881 P1.3) refuses them: freezing needs a re-measurement,
  which would move a stored result. They stay unfrozen; `show`/`explain` still re-hash what each read.
