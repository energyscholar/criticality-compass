# ARCHITECTURE - how a Criticality Compass result is made

Written 2026-10-05 (plan 0881 P2) against CC main `e8924b0`+ (the commit before the P2.4 docs; line and file counts are of that tree). Every number in
the verdict-path walkthrough is from `bin/cc explain x2b-xy-2 0.7 --tables v07-rules` unless a file is named; a stored result is read, never
re-measured, so those numbers do not move. `v08-rules` (the frontier) is described by `docs/CHANGELOG-TABLES.md`; `docs/VERDICTS.md` lists its words.

## In one paragraph

CC is a batch instrument. You give it finite snapshots of a system at declared points in parameter space and at
three lattice sizes, plus a declaration (`inputs/<id>/m.toml`, the kernel's M) of exactly what was measured and
how. It reduces the snapshots to a few numbers per point, takes **directed differences** of those numbers over
**declared comparisons** (size chains, matched block levels, a start pair: independent observations related through the
declared blocking map, inside a projection C) and one declared relation (neighbouring points, pending an external verifier (ruling R2)), reads each difference
with a resampled interval against a declared margin, turns the interval's position into a word, and looks the words
up in a rulebook that is plain TOML data. Per point the answer is POINT, LINE, WALKING, FIRST-ORDER, NOT or a named
refusal; a family of points can also read BKT-END or POINT-MANIFOLD. "Not measured" and "not evaluated" are values
that travel all the way to the verdict (printed as `BLANK (<value>: <reason>)`); a refusal is an answer, printed with
its reason and the rulebook line that gave it.

## Repository map

| path | holds | notes |
|---|---|---|
| `inputs/<id>/m.toml`, `couplings.toml`, `points.toml` | M: files, sizes, relations, margins, resampling; the couplings `across` probes; point -> case join | 34 inputs; `points.toml` is taxonomy, never frozen |
| `instruments/<name>.toml` + `cc/instruments/<name>.py` | one measurement: pipeline of `stage:`/`door:` steps, arrays, relations, columns -> eps key | 11 instrument modules: the nine the verdict path reads (needle, across, stability, two_start, fluct, along, needle_chain, across_delta, stability_delta), needle_o (a start test), and transform — an independent conventional estimate, not a Compass reading (10 `.py` files: `needle_o` reuses `needle.py`) |
| `tables/<set>/` | the rulebook: `codes`, `verdict`, `geometry`, `probe`, `order`, `compose`, `membership`, `family` | 9 sets, `verdict-x-rules`, `v01-rules` .. `v08-rules`; VERDICTS.md lists every word of `v08-rules` |
| `cases/`, `families/` | taxonomy: a case's true class (read only by `score.py`); a family = one input + interior points | 21 cases, 8 families |
| `results/<input>@<set>.json/.npz` | one run: readings, cells, codes, verdicts, reports, resample vectors, hashes of what was read | 189 results |
| `expected/<set>.toml` | the scoreboard lock (CC's expected verdict per point, NOT truth) + `[[change]]` history | CHANGELOG-TABLES.md |
| `FROZEN.json`, `fixtures/data/` | frozen files and their hashes; sha256 pins of the data files | data root: `cc.toml [data]`; frozen: verdict-x-rules (8 results), v01-rules (11), v03-rules (24) and their table dirs |
| `tests/` (53 scripts, 106 goldens, 7 breakers), `checks.toml`, `cc.toml` | tests; maths-vs-plumbing roles; defaults, alphabets, the labels (`[conventional]`), the check budget | `[defaults] tables = "v01-rules"`; v08 is the frontier |

## Module map (`checks.toml [roles]`)

**Maths** - no `if`, `try`, comparison, or literal but 0 and 1 (`checks.py` enforces it):
`kernel.py` 103 (A, B; R/E/rho present, reached by no instrument), `sign.py` 65 (interval position -> cell),
`resample.py` 14 (moving-block bootstrap), `readout.py` 16 (estimate + central interval + cell), `project.py` 45
(level means, cov, ln(s R), density variance), `reduce.py` 60 (3x3 block maps for raw stacks), `fingerprint.py` 14
(family differences by A), `gamma.py` 45 (the Gamma-method interval: window W and tau_int), `cc/instruments/*.py` 305 lines in 10 modules.

**Plumbing** - may branch: `bin/cc` 597 (CLI, check, freeze, mutate), `admit.py` 56 (builds declared relations;
refuses a cycle or a missing provenance), `schema.py` 164 (the declared partitions, the hashes), `declare.py` 1105 (schemas, `validate`,
partition checker, factorisation proof), `door.py` 308 (context, resample plan, the doors), `detect.py` 505 (measure -> codes -> verdict;
`run` and the reuse key), `reverdict.py` 96, `view.py` 385 (`show`, `explain`), `score.py` 247 (the only reader of
class truth; tabulate, diff), `family.py` 233, `formats.py` 116 (raw-stack formats), `transducer.py` 57 (the declared
transducer file), `resources.py` 36, `author.py` 363 (authoring).

## The verdict path (the numbers `explain` prints)

1. **DATA** - `door.load_blocks` reads the files `m.toml [[data.files]]` name (array files, or raw stacks reduced by
   `reduce.py` through the declared block map); `detect.read_hashes` records the sha256 of every file read and
   refuses a data file that differs from its pin. Here `x2b/T0.70000-L81-random.npz`, 2 blocks, sha256 matches.
2. **REDUCE** - the instrument's `reduce(arrays, ctx)` turns one resample row into node numbers; row 0 is the data,
   rows 1..400 are moving-block resamples (`b 400`, one generator). Here the needle's seven
   level means: `0.8006, 0.8769, 0.8883, 0.892 | 0.8007, 0.8772, 0.8905`.
3. **COMPARISON / RELATION** (the label is `cc.toml [step_labels]`, by relation name) - `door.relations_for` -> `admit.declare`:
   nodes and directed edges from one of four templates (`chain`, `matched`, `pair`, `matched-chain`), declared before data;
   `m.toml` still writes provenance `Coupling`, which a comparison does not claim (an external verifier, 2026-10-06). Here
   `matched: (243,L1)->(81,L0) (243,L2)->(81,L1) (243,L3)->(81,L2)`.
4. **C** (or **C+KERNEL** where a control edge is read) - `kernel.A`: `A(x)[e] = x[source] - x[target]` on every declared edge
   (`B` only for `along`); over a comparison it is the same arithmetic computed as a C comparison, until plan 0893 P2 moves it out of
   `kernel`. Between
   stages the doors run: `nodefield` (non-finite -> NOT-EVALUATED), `logcoord` (ln(s q) only when q keeps one sign at
   the estimate and every resample), `basis`, `decays`, `off_manifold`; a `door.Null` becomes a reading whose cell is
   the null, reason kept (`detect.after`). Here `velocity [0.001459]`, `d_ord [0.108]`.
5. **READING** - `readout.reading`: estimate = row 0; central 95 % interval of rows 1..400. `0.001459 [0.001324, 0.001605]`.
   Under interval method `chains` (Detector v10; plan 0937) rows 1..m are the m chain readings and `readout.chains` takes the interval from their
   order statistics `[v_(r), v_(m+1-r)]`. Two numbers then carry the name `estimate`, and they are different statistics: `readings[].estimate` is the
   **median** of the m chain readings (the sealed estimand); `reports[].estimate` is **row 0 = chain 0's reading** (a reported scalar, read by no sign cell).
   This is declared here, not changed: the v10 code and its stored records are frozen, and the next Detector version is where `reports[].estimate`
   is to be made the median (plan 0937 amendment 7, F8; Fable #9 finding F8).
6. **SIGN** - `sign.sign(lo, hi, eps)`: the position of both interval ends among the cuts `-eps, 0, +eps` is one of 8
   cells SIG-, NEG, SLOW-, ZERO!, SLOW+, POS, SIG+, UNRES (UNRES = straddles 0 and a margin edge); eps from
   `m.toml [eps]` via the instrument's `[columns]`. Here `eps step 0.01: bL 2, bU 2 -> SLOW+`.
7. **CODE** - `detect.codes_of`: `codes.toml` maps per column, helpers first, then the signature columns; nulls pass
   through every map; a point-size or pair column is combined by its declared `combine` (rank, `agree`, `top_only`,
   `prefer_door`); `probe` comes from `couplings.toml`, never from data. Here `flow_top SLOW` and
   `drift_code CONVERGING` -> `flow = STOPPED (codes.toml line 226)`; `across_cov MARGINAL` and `across_dlt MARGINAL`
   -> `across = MARGINAL (line 297)`; `stability_raw STABLE` x CONVERGING -> `TRANSFORMED (line 363)` (a v07 transform-basis reading: an external verifier (ruling Q3), 2026-10-05, ruled it not relationally admissible; `v08-rules` reads stability on the Delta basis with no TRANSFORMED cell); `two_start`
   INDEP at L27/81/243 -> INDEP; `probe COMPLETE`.
8. **VERDICT** - `detect.verdict_of`: exactly one `[[row]]` of `verdict.toml` contains the signature row (`validate`
   proves the rows disjoint and total, so file order is irrelevant). Here `verdict.toml line 161 => LINE`, why
   "verdict_x CAND_GS: marginal and stable".
9. -12. **GEOMETRY, PROBE, ORDER, COMPOSE** - the same codes read by four smaller partitions (`detect.axes_of`);
   `validate` proves compose(geometry, order) equals the verdict on every row. Here geometry line 73 LINE, probe
   line 12 (stands), order line 72 CONTINUOUS (witness: fluct VANISHES), compose line 36 -> LINE.
13. **FAMILY** - `family.py` reads the stored result, never re-measures: `bracket` (A over
    needle-rank codes along the points), `f1` (all-pairs A over `across.y_last` per resample; per chain, rows 1..m, under method `chains`, plan 0978), `f2` (`along` cells),
    `points`, `lower`/`upper` (the side table) -> one lookup in `family.toml`. `bin/cc family x2b-xy-2 --tables v07-rules`.

A pair instrument (`along`, `across_delta`, `stability_delta`) runs after the point instruments: its membership door (where the set
declares one) reads the two endpoints' codes (`membership.toml`); the pair runs or reads the door value. `explain <input> 'a->b'` prints
one section per instrument that reads the pair, each from its own stored vectors (plan 0881 P2.1).

The `transform` instrument is an **independent conventional estimate — not a Compass reading** (an external verifier (ruling Q3), 2026-10-05: there is no observation
at infinite size; the shared-omega assumption is an undeclared prior). Its `y_inf` is stored and printed with that label (`cc.toml [conventional]`),
and no verdict row in any set reads it; none in any set after v07 may.

## Provenance, reuse, freezing

A result records `read` (sha256 of every file read), `code_hash` (all of `cc/` + `bin/cc`, provenance only) and
`measure_hash` (the AST import closure of `cc/detect.py`, `cc/door.py` and the declared instrument modules: the
reuse key, plan 0876 B). `detect.run`: same `read` + same `measure_hash` under the same set -> the stored result IS
the result; a difference only in `tables/*` -> a re-verdict with `derived_from`; otherwise measure. `reuse=False`
always measures (the replay tests). `freeze` makes a result and what it read read-only and lists them in
`FROZEN.json`; it compares the result's `measure_hash` with the committed tree's (plan 0881 P1.3), so a result that records none cannot be
frozen. `show`/`explain`/`tabulate` re-hash and refuse a stale result.

Which results have a `measure_hash` at this commit: the 24 `v03-rules` results (refreshed by plan 0878 P2.2), `v08-rules` and later.
The `verdict-x-rules`, `v01-rules`, `v02-rules`, `v04-rules` .. `v07-rules` results were written before 0876 and record none, so
`bin/cc freeze --all --tables v02-rules` (and v04..v07) is refused: freezing them needs a re-measurement. Frozen at this commit: verdict-x-rules,
v01-rules and v03-rules.
