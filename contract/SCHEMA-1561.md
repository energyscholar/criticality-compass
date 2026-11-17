# SCHEMA-1561 — the drift worlds (where a hold breaks)

Frozen by plan 1561 before any implementation. It adds two drift laws to plan 1545's apparatus, a declared set of
drift-world ladders, a pure scorer of a moving crossing, a pure breakpoint table, and a reader that writes one report
over finished runs. Nothing here runs the apparatus or the needle: runs are made by plan 1552's own orchestrator
(`python -m environment.run_hold`), one per rung, and read afterwards. **Making the runs is out of scope**: no runner is
shipped; the Auditor's acceptance makes them (materialise, write the world beside a copy of the plugin directory, one
`run_hold` per rung), and the report checks each run's own `config.json` against the name it was filed under (§5).

Words: a **world** is one apparatus world table (SCHEMA-1545 §2). A **rung** is the base world with a few keys
replaced. A **ladder** is an ordered list of rungs whose **severity** rises strictly. A **mode** is one of the three
needle files a run is made with: `SET` = `navigator/hold-settled.toml`, `MID` = `navigator/hold-mid.toml`, `OFF` =
`navigator/hold-settled-off.toml` (plan 1552's shipped FEEDBACK OFF file: `ops = ["declare", "scan"]`). The **break** of a ladder is where its rungs stop
holding.

**Phase 4 (amended 2026-11-17, the cross-plan review's findings 1 and 6).** Three changes, each marked *Phase 4* below: `cycle`
is a table keyed on the needle shape (§4); the shape is part of "made as named" (§5); each read rung carries its run's time
(§5). They change only `drift_score.py` and `ladder_report.py`, the readers of finished runs; nothing a run executes.

## 1. Files

| file | NEW / EDITED | holds |
|---|---|---|
| `environment/drift.py` | EDITED (plan 1545's) | two more laws, `ramp-then-rest` and `walk` (§2). The four older laws are unchanged |
| `contract/test_apparatus_drift.py` | EDITED by the Auditor (line 45 only) | the law tuple now has six names |
| `contract/test_apparatus_midmove.py` | EDITED by the Auditor (lines 110–111 only) | the new sha of the drift test; `drift.py` is no longer pinned |
| `environment/drift_worlds.py` | NEW | `parse_worlds`, `materialise`, `to_toml`, `ladder` (§3) |
| `system-instantiated/plugins/at/drift-worlds.toml` | NEW | the declared ladders (§3.3) |
| `environment/drift_score.py` | NEW | `cycle`, `motion`, `rung_class`, `breakpoint`, `Break` (§4) |
| `environment/ladder_report.py` | NEW | the report over finished runs (§5) |

No other file changes, except one `checks.toml` line per contract test. In particular `navigator/*`, `needlestream/*`,
`environment/hold_score.py`, `environment/run_hold.py`, `environment/apparatus_*.py` and every plugin file stay
byte-identical (plan 1558 edits several of them at the same time).

## 2. The two new laws

`environment.drift.LAWS == ("none", "linear", "sine", "step", "ramp-then-rest", "walk")`, in that order. The rows of
SCHEMA-1545 §3 stand unchanged; these two are added. `I` is the apparatus index, an int ≥ 0; `h` the horizon.

| law | keys, in this order | `offset(I)` |
|---|---|---|
| `ramp-then-rest` | `at` int ≥ 0, `rate` float, `span` int ≥ 1 | `rate * min(max(0, I - at), span)` |
| `walk` | `at` int ≥ 0, `seed` int ≥ 0, `every` int ≥ 1, `stride` float > 0, `knots` int ≥ 1 | `0.0` when `I < at`, else `W(I - at)` |

`ramp-then-rest` is still until `at`, moves at `rate` per sweep for `span` sweeps, then rests at `rate * span` for
ever. Its bounds over `[0, h]` are `(min(0.0, rate * m), max(0.0, rate * m))` with `m = min(max(0, h - at), span)`.

`walk` is a telegraph walk: it is piecewise linear, continuous, with `knots` segments of `every` sweeps each, and then
it rests. Segment `j` (`0 ≤ j < knots`) moves by `stride * s_j`, where the sign is

    s_j = walk_sign(seed, j) = 1 - 2 * (sha256(f"compass-walk/1 {seed} {j}".encode("utf-8")).digest()[0] & 1)

which is +1 or −1. Let `P[0] = 0` and `P[n+1] = P[n] + s_n`, and let `s_knots = 0` (the rest). With
`n = min(J // every, knots)`:

    W(J) = stride * (P[n] + s_n * (J - n * every) / every)

so `W(n * every) = stride * P[n]` exactly at every knot, and `W(J) = stride * P[knots]` for every `J ≥ knots * every`.
`environment.drift.walk_sign(seed, j)` is a public function with exactly that value. The bounds of `walk` over `[0, h]`
are the min and the max of `W` over the knots `n * every` for `0 ≤ n ≤ min(H // every, knots)` and the end point `W(H)`,
where `H = max(0, h - at)`; because `W` is linear between knots, they are attained and they contain the law. A `walk`
value carries its derived tables (`vel`, `prefix`) in `Drift.values` next to its five keys; nothing outside `drift.py`
reads them.

Both laws are pure functions of `I`: no memory, no state, no call order. `parse_drift` checks them exactly as
SCHEMA-1545 §3 says (the table, `target`, `law`, an unknown key, then the law's keys in the order above), with the
`navigator.reader` field rules: a bool is never an int, an int is never a float, a float must be finite. The field
reported is the key's own name. A world whose drift leaves the domain of its target within its horizon is refused
`field=drift` by `apparatus_config.parse_world`, exactly as before: **the law is never clamped and the drift is never
cut short**. The string `"ramp"` is still not a law (the frozen test uses it as the example of an unknown law).

## 3. The drift worlds

### 3.1 The worlds file (strict; `parse_worlds(table) -> Worlds | Malformed`)

Exactly two top-level keys: `base` (a file name — letters, digits, `-`, `_`, `.`, never `--` — ending in `.toml`, a sibling of the
worlds file) and `ladder` (a non-empty list). Otherwise `field=worlds` (wrong key set or not a table), `field=base`, or
`field=ladder`.

A ladder is a table with exactly `name` (a name as above; a **name** never contains `--`, the run-name separator) and `rungs` (a non-empty list): otherwise
`field=ladder[<i>]`, `field=ladder[<i>].name`, `field=ladder[<i>].rungs`. Names are distinct over the file
(`field=ladder.name`).

A rung is a table with the required keys `label` (a name), `severity` (a finite float > 0), `horizon`, `drift`, and the
optional keys `hidden`, `dials`; any other key is refused by its own name. Field names: `<ladder>[<j>]` (not a table),
`<ladder>[<j>].<key>` (a missing required key, the first in the order `label, severity, horizon, drift`; an unknown
key, the first in sorted order; a bad `label` or `severity`). Within a ladder, labels are distinct
(`<ladder>.label`) and severities rise strictly in the order given (`<ladder>.severity`). The rung's `horizon`,
`drift`, `hidden` and `dials` are NOT checked here: they are world keys, and `apparatus_config.parse_world` judges the
whole world.

Order of checks: the file's key set; `base`; `ladder` is a non-empty list; each ladder in order (key set, `name`,
`rungs`, each rung in order, distinct labels, rising severity); distinct ladder names. The first failure is returned.

`Worlds(base, ladders)`, `Ladder(name, rungs)`, `Rung(label, severity, table)` are frozen dataclasses; `ladders` and
`rungs` are tuples in the file's order; `table` holds the rung's override keys (`horizon`, `drift`, and `hidden` /
`dials` when given), as given. `ladder(worlds, name)` returns the named ladder (KeyError when there is none).

### 3.2 A rung as a world

`materialise(base, rung, seed) == {**base, **rung.table, "seed": seed}`: the base world's keys in their order, each
replaced by the rung's where it has one, and the world's `seed` the run seed. **The drift table is the rung's as
declared — a walk's own `seed` is NOT the run seed**: the run seed moves the thermal noise, never the path, so every
run seed meets the same walk. `materialise` checks nothing, mutates neither argument, and returns a deep copy: no
table in the world is shared with the rung or the base.

`to_toml(world)` writes one `key = value` line per top-level key in the table's order (TOML inline tables and arrays
below the top level); `tomllib.loads(to_toml(w)) == w` for every materialised rung, **exactly**: every float to its
last bit (`repr`), a float stays a float (`1.0`, not `1`), and a string with quotes or backslashes reads back as written.

### 3.3 The declared ladders (`system-instantiated/plugins/at/drift-worlds.toml`, `base = "at-apparatus.toml"`)

Every rung of every ladder, materialised with any run seed, is a world `parse_world` accepts. The table below IS the
file's content; the Generator writes it, and `test_drift_worlds.py` w05 compares every rung with an independent
statement of this table (the file's bytes are not pinned). In L4 units; ticks are the dial's (0.00025 in K); `dK_c/dL4` is about −0.60 to −0.66 over L4 0.06–0.14, so 0.004
in L4 is about 10 ticks. All ladders stay inside L4 0.06–0.14 (the range `offset_K` was set in, plan 1552 F6) except
the walk, which reaches 0.156.

| ladder | hidden L4 | law | rungs (label: the rung's own keys) | horizon | severity |
|---|---|---|---|---|---|
| `ramp` | 0.14 | `ramp-then-rest`, at 20000, `rate = -4e-7 * m`, `span = 150000 // m` (0.06 in L4, ≈ 150 ticks UP the dial) | `x1 x2 x3 x4 x6 x8 x12` (m) | `60000 + span` | m |
| `ramp-reversed` | 0.08 | the same with `rate = +4e-7 * m` (≈ 150 ticks DOWN the dial) | the same | the same | m |
| `ramp-edge` | 0.14 | `ramp` x1, with the dial `{K, lo 0.20, hi 0.375, T 700, max_nudge 32, start 0}` (same tick) | `x1` | 210000 | 1.0 |
| `sine` | 0.10 | `sine`, amp 0.04 (≈ ±100 ticks), period P | `P800000 P400000 P200000 P100000 P50000` | 150000 | 800000 / P |
| `step` | 0.10 | `step` at 40000, `size = -J/1000` (UP the dial) | `J4 J8 J12 J16 J24 J40` | 100000 | J / 4 |
| `step-reversed` | 0.10 | `step` at 40000, `size = +J/1000` (DOWN the dial) | `J8 J12 J16 J24` | 100000 | J / 4 |
| `walk` | 0.10 | `walk` at 20000, seed 1561, stride 0.008 (≈ 20 ticks), knots 10, `every` E | `e20000 e10000 e6000 e4000 e2500 e1500` | `50000 + 10 * E` | 20000 / E |

The shipped `at-apparatus.toml` drift (linear, −4e-7) is rung `x1`'s speed. Walk seed 1561 is the plan number, not a
choice made from data; its signs are `+ − + + + + + + + −` (prefix `0 1 0 1 2 3 4 5 6 7 6`).

## 4. The score of a moving crossing (`environment/drift_score.py`, pure)

It opens nothing and prints nothing; the needle side never imports it. Its inputs are plan 1552's `score.json` (as a
dict) and the first line of the run's `report.jsonl` (the start record, as a dict).

- *Phase 4.* `cycle(shape, settings) == CYCLE[shape](settings)` — the needle's sweeps per hold pair, from a table keyed on the
  needle SHAPE. `CYCLE` has exactly one row, `"hold-pair-v1"` (plan 1552): `2 * (settings["n_eq"] + settings["S"] *
  settings["skip"])`. A shape with no row raises `KeyError`; it is never given the pair formula. Plan 1558 adds the
  `"hold-setpoint-v1"` row at its merge (its walk and park reading, SCHEMA-1558 §4.2), and with it the line of s11 that
  pins its numbers.
- `motion(score, start)` returns a dict with exactly these keys:
  - `lock`, `outcome` — copied from the score; `hold_steps` — `len(score["steps"])`;
  - `top_speed = settings["step"] / cycle(start["needle"], settings)` — the most ticks per sweep the needle can move (the
    start record's `needle` is the shape; a start record with no `needle` raises `KeyError`);
  - `out_runs` — the maximal runs of `cell == "OUT"` in step order, each `{"first": <the first OUT step's "step">,
    "steps": <its length>, "sweeps": <index of the next IN step − index of the first OUT step, or "never">}`;
  - `recovery_max` — the largest `sweeps` of a run that ended; `"never"` when there are runs and none ended; the token
    `"no-out-runs"` when there are steps and no run; `"no-hold-steps"` when there are no steps;
  - `unrecovered` — true when the last run never ended; `"no-hold-steps"` when there are no steps;
  - `ordered_share` — the share of steps whose `e` has the sign of the ordered side (`start["belief"]["ordered_side"]
    ["declared"][<the dial>]`, `+` ⇒ `e > 0`, `−` ⇒ `e < 0`; `e == 0` is on neither side);
  - `travel` — the last step's `truth_tick` minus the first's;
  - over the **moving pairs** (consecutive steps whose `truth_tick` differs; `d` = the difference, `di` = the
    difference of `index`, `e` = the later step's error): `slew_max` and `slew_mean` = max and mean of
    `|d| / di / top_speed`; `jump_max_g` = `max |d| / g`; `trail_along` = mean of `-e * sign(d)` (positive = the centre
    is BEHIND the crossing's own motion, whichever way it moves); `trail_along_g = trail_along / g`.
  - No steps ⇒ `ordered_share, travel, slew_max, slew_mean, jump_max_g, trail_along, trail_along_g` are all the token
    `"no-hold-steps"`. Steps but no moving pair ⇒ the last five are the token `"no-moving-steps"`. A token is never a
    number and a number is never a token.
- `rung_class(lock)` is the total table `HELD → held; RECOVERED, LOST, LEFT-RANGE → broken; CUT-SHORT, REFUSED, FAILED,
  MISSING, MISMATCH → no-evidence`. Any other value raises `KeyError`. LEFT-RANGE is `broken` for the breakpoint (the
  hold did not hold); whether a world that is MEANT to leave the dial did so is judged on its lock, not on its break.
- `breakpoint(rungs)` takes `[(label, class), …]` in the ladder's order and returns `Break(kind, below, above, detail)`:

| the class sequence | `kind` | `below` | `above` | `detail` |
|---|---|---|---|---|
| any `no-evidence` | `INCOMPLETE` | `""` | `""` | the labels with no evidence |
| else a `held` after the first `broken` | `NOT-MONOTONE` | `""` | `""` | the labels of those held rungs |
| else all `held` | `HOLDS-THROUGH` | the last label | `""` | `()` |
| else the first is `broken` | `BROKEN-FROM-FIRST` | `""` | the first label | `()` |
| else | `BREAKS-BETWEEN` | the last held label | the first broken label | `()` |

It chooses nothing: a non-monotone ladder is reported as such, never smoothed into a bracket.

## 5. The report (`environment/ladder_report.py`)

`python -m environment.ladder_report --worlds <drift-worlds.toml> --root <dir> --out <file.json>`. Exit 0 = the file is
written; exit 2 = the worlds file cannot be read or is refused (one line on stderr beginning `refused:`; nothing is
written). A `--root` that is not a directory also exits 2 (`refused: root: …`).

A run directory is `<root>/<ladder>--<label>--<mode>--s<seed>` (`run_name(ladder, label, mode, seed)`; `mode` one of
`MODES = ("SET", "MID", "OFF")`), holding `runs/<run id>/` as `run_hold` writes it. `parse_name` is its inverse
(`None` for any other name). `read_run(dir, mode, rung, seed) -> (lock, motion | None, scorer | None)`: no such directory ⇒
`MISSING`; not exactly one `runs/*/` directory, or `refused.json` in it ⇒ `REFUSED` (when any has `refused.json`) else
`FAILED`; `config.json`, `score.json` or the first line of `report.jsonl` missing or unreadable ⇒ `FAILED`; the run's own
`config.json` says it was not made as named ⇒ **`MISMATCH`**; a score `lock` outside `rung_class`'s table, or (*Phase 4*) a
start record whose `needle` is not a row of `CYCLE`, ⇒ `FAILED`;
else the score's `lock`, `motion(score, start)` and `scorer = {"out_run", "offset_K"}` copied from `config.json`'s
`score`. "Made as named" (`made_as(config, mode, rung, seed)`) is (*Phase 4*): the needle's `(needle_structure, "nudge" in ops,
n_eq > 0)` equals `NEEDLE[mode]` with `NEEDLE = {"SET": ("hold-pair-v1", True, True), "MID": ("hold-pair-v1", True, False),
"OFF": ("hold-pair-v1", False, True)}` (a needle with no `needle_structure` key is not made as any mode, so a setpoint-shape
run filed under a ladder root is `MISMATCH`, never `SET`); `config["at"]["seed"] ==
seed`; and every key of `rung.table` equals `config["at"]`'s. The name of a directory is a claim; the run's own config
is the evidence.

The output (sorted keys) is `{"schema": "compass-drift-ladders/1", "base", "cells", "strays"}`. `strays` lists, sorted,
every directory under the root whose name is not a run of a declared ladder and rung. There is one cell for every
`(ladder, mode, seed)` that has at least one run directory, sorted by those three; a cell lists **every rung of its
ladder** in the declared order — a rung with no directory is `MISSING`, so a missing rung can never shorten a ladder
into a clean bracket — each as `{label, severity, lock, class, motion, scorer, perf}`, and the cell's `break` as `{kind, below,
above, detail}`.

*Phase 4, the time report.* `perf` is `null` exactly when `motion` is (`MISSING`, `REFUSED`, `FAILED`, `MISMATCH`); else it is
read from the run's own `perf.json` (`{"calls": [{"op": <str>, "seconds": <number>}, …]}`, as plan 1552's orchestrator
writes it): `{"seconds": <fsum of every call's seconds>, "calls": <the number of calls>, "by_op": {<op>: {"calls", "seconds"}}}`
with one `by_op` entry per op that occurs. No `perf.json` ⇒ the token `"no-perf"`; a file that is not that shape (not JSON,
no `calls`, a call without a string `op` or a numeric `seconds`) ⇒ the token `"unreadable-perf"`. Time is report-only: it
never changes a lock, a class or a break.

## 6. What stays as it was

The needle, its tables, the reader, plan 1552's scorer and orchestrator, the apparatus server and wire: byte-identical.
The four old laws give the same offset at every index and the same bounds at every horizon. `"ramp"` is not a law.
There is no default hold mode: a run is always made with a named needle file, and every report cell names its mode.
