# SCHEMA-1558 — the hold setpoint sigma (stage 5a-σ)

FROZEN with `contract/test_hold_setpoint.py`. It amends SCHEMA-1552 by ADDING a second needle shape; every rule of
SCHEMA-1552 holds for `hold-pair-v1` unchanged, byte for byte (test t14 pins nine outputs). Section numbers below that say
"1552 §n" are SCHEMA-1552's.

**What sigma is (owner rulings, verbatim in substance).** sigma is a declared USER setting: an UNSIGNED safe-side offset in units
of the pair half-width `g`. The danger side is the System's declared `ordered_side` of the dial, never assumed and never read off
the readings. sigma is defined on MEASURED quantities: the pair and its half-width (the needle's own), and `dead_band`, the needle's
measured error against the EDGE. The edge is truth, so the band is CALIBRATED ON TRUTH (owner ruling, 2026-11-16): it is
measured by plan 1561 across its drift laws, both directions, and read from its table `contract/drift-band.json` (shape
`compass-drift-band/1`, plan 1561's, read as written, with its top-level `locks`, one 1552 lock per run
`{law}--{rung}--{needle}--s{seed}`): `dead_band.ticks = ceil(max p95 over the runs of the DOMAIN cells: rows with sigma > 0 and law ramp,
ramp-reversed, sine or walk whose every seed is HELD)` (rev 6, m4: a surviving seed of a broken cell never sets the band) (step drift is outside the band's laws: its rows are reported, never bound), computed, never typed.
**The band's domain is a total table over each run's lock** (cold audit B1), declared before the band run:

| lock | class | the run contributes |
|---|---|---|
| HELD | band | its p95 (a HELD run without a finite p95 is a gap) |
| RECOVERED, LOST, LEFT-RANGE | out | nothing: a named REPORT row, "out of the setpoint needle's domain"; the declared domain narrows by that (law, rung, sigma) |
| CUT-SHORT, REFUSED, FAILED, MISSING, MISMATCH | gap | no evidence: the table is incomplete and nothing is accepted |

**The band's domain has a STATE coordinate** (rev 7, owner ruling 2026-11-17, OQ-11 b). Each row of the table carries `state =
{target, lo, hi}`: the drift target's value (L4 today) over the readings its p95s were taken at (σ > 0: the park readings; σ = 0:
the hold steps), computed by plan 1561's `band` from the rung's DECLARED world for each seed, never typed. The band covers the
hull of `state` over the DOMAIN cells, the cells that set `dead_band.ticks` (on 1561's full table: [0.08, 0.1557976]). A reading
whose state lies outside that interval is OUT of the band's domain by construction: it is never band evidence and never held to
the band (acceptance B1 classes every park reading by it; a HELD seed with no reading inside fails). The interval lives in the
table, bound to the band row by `about.provenance` (the table's sha), and NEVER in the needle's settings: the needle never sees
the hidden state, and no hidden-state word may reach a report or map (acceptance M2).

A domain that does not hold forward ramp's first rung at every measured sigma is a finding for the owner, never a silent pass
(t16, acceptance D1). **An inadmissible sigma is unrepresentable** (owner ruling 2026-11-17, replacing OQ-8's list-then-refuse):
the setpoint is not a free number but a MEMBER of a type, `dead_band.admissible`, generated from this table by the band writer
(§4.5) at one needle geometry (§2.2): `ADMISSIBLE = {sigma : sigma band-measured, sigma·g whole and > dead_band.ticks}`. A sigma
at or inside the band cannot be written down: the only place to write it is the type, and a band row whose type holds it is
refused whole (§2). The band run measures exactly the members of the type, read from the shipped band row, never a typed list.
sigma = 0 is plan 1552.

## 1. Files

Edited (plan 1552's own files; none is in 1552's FROZEN list): `navigator/holdtab.py` (tables ADDED at the end, nothing
existing changed), `navigator/hold.py`, `navigator/holdrep.py`, `needlestream/read_hold.py`, `environment/hold_score.py`,
`environment/run_hold.py`. NEW: `navigator/setpoint-settled.toml`, `navigator/setpoint-settled-2.toml` (and no other
`navigator/setpoint*.toml`). Contract (NEW, frozen): this file,
`contract/test_hold_setpoint.py` and `contract/drift-band.json` (the band's input, plan 1561's `compass-drift-band/1`; at build
time it holds plan 1558's own recon rows, and the reviewer replaces it with plan 1561's accepted table, §2.1). ⛔ No new module under `navigator/`: 1552's frozen h12 allows the needle's three modules to
import only `hold, holdtab, holdrep, reader, report2, steer` from navigator. ⛔ No file named `navigator/hold*.toml` (h19).

## 2. Shapes: one settings table per shape, a sum type

`needle_structure` names the shape and selects the check table. Two shapes:

| shape | keys | sigma | parks |
|---|---|---|---|
| `hold-pair-v1` (1552) | 1552 §2's 13 keys | int 0 exactly | never |
| `hold-setpoint-v1` | the 15 keys below | a number > 0 | after every hold pair |

A `needle_structure` that names no shape is read with `hold-pair-v1`'s table (so 1552's refusals are unchanged; a setpoint table
with an unknown name is refused at its first key 1552 does not know, `dead_band`).

`hold-setpoint-v1` keys, IN THIS ORDER (the refusal order: a missing or unknown key first, sorted; then the first key outside its
domain in this order; parse B, `RefusedToStart field=<key> parse=B`, before the wire):

| key | domain |
|---|---|
| needle_structure | `"hold-setpoint-v1"` |
| ops, g, step, n_eq, S, skip, z | as 1552 §2 |
| dead_band | THE BAND ROW of this geometry (§2.2): a table of exactly {ticks: int ≥ 0 (never a bool), admissible, about, S, n_eq, z, g, step, park}; `admissible` = THE TYPE of the setpoint: a non-empty, strictly increasing list, every member a finite number > 0 (never a bool) with `sigma_ticks(member, g)` whole and `> ticks` (closed: equal is refused); a list holding any other member is not the type and the row is refused (no member is dropped or moved); `about` = the type's description (§2.3), exactly its seven fields (`HT.ABOUT`); `ticks` is the needle's MEASURED error against the EDGE (p95 of \|park − edge\| in ticks, both drift directions, plan 1558 "Declared numbers") AND the hold geometry it was measured at. Each geometry key must EQUAL the table's own key, same value and same type all the way down (`_same`: the park's cells too, 500.0 is not 500) (`HT.BAND_GEOMETRY`); a band measured at another S, n_eq, z, g, step or park is refused, never reused (the park's length sets the lag the band is made of: audit 2 N2) |
| sigma | a MEMBER of `dead_band.admissible`: int or float (never a bool), finite, > 0, equal to a member as `sigma_ticks` pairs by cross-multiplying (`n·b == a·d`: 2 and 2.0 are one member). Nothing else is checked here: whole, positive and outside the band are properties of the type, established once, at `dead_band`. A free sigma that is not a member is refused however good a number it is |
| ignite, approach | as 1552 §2 |
| park | table of exactly {S: int ≥ 40, n_eq: int ≥ 0}: the settle and window of the park reading |
| lost, M | as 1552 §2 |

`dead_band` and `sigma` are the only checks that read other keys (dead_band: the six geometry keys, and g for its type; sigma: g, dead_band). All but
`park` are checked before them, so neither sees a value outside its domain except the park, which `dead_band` only COMPARES
(`_same` is total over any value: it returns False, never raises); a park outside its domain whose band carries the same park is
refused at `park`, and one whose band differs is refused at `dead_band`, the first in the table's order. `sigma_ticks(sigma, g)` is sigma·g EXACTLY as an integer pair
(numerator, denominator): sigma is read as the decimal its shortest `repr` writes, so 0.57 at g 100 is 5700/100 = 57 ticks (the
float product is 56.99999999999999). Integer arithmetic only: plan 1552's h12 allows `holdtab` no new import. There is no clamp anywhere: a refused sigma is never moved to the nearest legal value.

**Why a member of an enumeration, not `offset_ticks = DEAD_BAND + m`** (the owner's two candidates). The kernel declaration and
the start record carry sigma in unit `g` (§5.1 `{"unit": "g", "measured": "pair-half-width"}`), and the parse already reads it
exactly in g (`sigma_ticks`); `DEAD_BAND + m` (m ≥ 1) changes the declared unit to ticks AND makes every m representable, so an
unmeasured setpoint is writable again: it forbids the band but not the unmeasured. The enumeration forbids both: its members are
the band run's own measured sigmas, so the band run and the type are one list. What the parse itself can see is the type's shape
(whole, outside the band); that each member was MEASURED is held by the writer generating the list, and by t16 and accept.py
holding the shipped list equal to the table's (the needle opens only its settings and map, §11, never the table).

### 2.1 The two shipped files
`setpoint-settled.toml` = `hold-settled.toml`'s numbers + {needle_structure `hold-setpoint-v1`, sigma SIGMA_LO (1.5 today), park
{S 500, n_eq 450}, and the `[dead_band]` band row of the table's geometry: ticks DEAD_BAND (13 on plan 1561's full table), S 500, n_eq 450, z 2.0, g 12,
step 6, park {S 500, n_eq 450}, admissible ADMISSIBLE ([1.5, 2] today), about (§2.3)} (13 = ceil(max p95) over the domain cells' σ > 0 runs of
`drift-band.json` whose law is ramp, ramp-reversed, sine or walk, COMPUTED by the test as `DEAD_BAND`; step drift is report-only).
`setpoint-settled-2.toml` is the same with sigma SIGMA_HI (2 today). SIGMA_LO and SIGMA_HI are the band run's CANDIDATES: the
least multiple of g/2 whose sigma·g is strictly outside the band, and the next; both must be members (t16). If a new band moves
them, the band row is regenerated and band-run is repeated on its members before the files are written (plan order step 3b).
The files write a whole sigma as an integer. Every test case that depends on the band is computed from `DEAD_BAND`, so a new table
needs the two files and a re-pin, never a new test. Test t16 holds each to the dict it builds (`setpoint_cfg`). There is no
mid-move setpoint file: the door refuses one (§3).

### 2.2 The band is keyed by geometry (declared for later: per-use-case precision)
A band is measured at ONE needle geometry (`HT.BAND_GEOMETRY`: S, n_eq, z, g, step, park): longer readings would give a narrower
band, a closer sigma and more lag. `drift-band.json` names its geometry (`geometry`, the six cells); a band row is the writer's
output for one table, and carries that geometry as its own cells; the admissible set is a function of (geometry, the band measured
at it). ONE geometry ships today. A precision setting added later is a NEW MEASURED BAND ROW (a new table at the new geometry, its
own row), never a schema break: the row's shape is this one. An unmeasured geometry has no row, so it is unrepresentable the same
way an inadmissible sigma is: a settings table whose geometry differs from its band row's is refused at `dead_band`. Each row
carries its cost (§2.3 `cost`, the cycle row of §4.4 per member) so that a later chooser can show the precision-lag trade.
Nothing beyond this keying is built in this plan.

### 2.3 The type self-documents (owner ruling 2026-11-17)
`dead_band.about` is the type's description, as DATA, written by the band writer (§4.5) from the same table its members come
from: ONE source. Exactly these fields (`HT.ABOUT`), every one non-empty:

| field | content |
|---|---|
| meaning | what the parameter is: an UNSIGNED offset from the critical crossing, parked on the dial's declared SAFE side |
| units | "sigma, in pair half-widths g" |
| conversion | {ticks: "sigma * g", g_ticks: this geometry's g (= the row's `g`), knob_per_tick: "(hi - lo) / T" of the System's declared dial (the System's, read at run time: §8 `sigma().value`)} |
| band | {ticks (= the row's `ticks`), p95_max (max p95 over the domain cells' runs), laws (the band's four), bound_to (`HT.BAND_GEOMETRY`: the row's own cells), promise (the p95 statement)}: why the set is what it is |
| cost | {unit "sweeps per cycle, an upper bound (§4.4)", max_nudge (the apparatus's it is computed at, 32), skip, approach}: the precision-lag trade |
| provenance | {sha256 of `contract/drift-band.json`}: the sha ONLY. The needle echoes its settings into its map, and the file's name carries a word the no-truth gate (`accept.py` M2) forbids there; the sha names the table without it |
| members | one per admissible member, in its order: {sigma, ticks (= sigma·g, exactly), cycle {plus, minus} (§4.4's row on a "+" and a "−" dial), domain, out, label} |
| members[].domain / out | rev 6 (cold audit M4): the member's cells `law/direction/rung`, in the table's row order. `domain` = HELD on every seed; `out` = any seed RECOVERED, LOST or LEFT-RANGE. Generated from the table's `locks` by the function that computes the band; t16 and `accept.py` hold them equal to the table. Finding D is therefore in every tooltip |

Every member's `label` is DERIVED from those fields, never written: `sigma {sigma} g = {ticks} ticks from the crossing, on the safe
side; band {band.ticks} ticks; cycle <= {cycle.plus} sweeps on a + dial, {cycle.minus} on a - dial; held on {len(domain)}
cells, out of its domain on: {out, comma-joined, or "none"}`. The parse requires the seven
fields and no other (`dead_band`); t16 and accept.py hold every number to the members and the table. The needle never reads it.

**The UI contract (declared; no UI is built in this plan).** Any settings surface (the needle's settings, the future
remote-control Player, the web artifact display and control surface) offers ONLY the measured (geometry, sigma) pairs: the
members of a band row's `admissible`, from the shipped band row (`navigator/setpoint-settled*.toml` `[dead_band]`, or the band
writer's output it is generated from), and never a free sigma field, a free geometry field, or a list of its own. Its tooltip and
each option's text are rendered from `about` and nothing else (the member's `label`, and `meaning`, `units`, `conversion`, `band`,
`cost`, `provenance` for the detail); no surface writes its own copy of any of them.

FEEDBACK OFF arms are not shipped files; the acceptance writes them (ops = ["declare","scan"]).

## 3. The door (parse A)
1552 §3 in its order, then three more rows. **Every lag rule goes through `holdtab.settled`** (and the lag model through
`holdtab.commanded`): rows 2 and 3 are `not settled(0, lag, n_eq, skip)` (a reading whose window opens `n_eq` after the
command, `0 + lag <= n_eq - skip`), never an inline `lag + skip`, so a per-dial lag (stage 5b) changes those two functions,
not the call sites (cross-plan review 2026-11-17, finding 4).
1. `sigma` when `sum(reach(g, off, side)) > T`, where `off = offset(sigma, g)`, `side` is the declared `ordered_side[dial]`, and
   `reach` is §4.1's. For `hold-pair-v1` the row never fires (reach = (g, g), already ruled by the `g` row). This row is NOT the
   band's refusal (that is unreachable: the type holds no sigma at or inside the band, §2). It guards a different input path, the
   SYSTEM'S DECLARATION: the dial's `T` arrives on the wire at `declare`, after the settings parse, so a member that fits one
   System's dial may not fit another's. It stays.
2. `n_eq` when `PAIR_SETTLED[shape]` and `n_eq < lag + skip` (`lag` the System's declared lag). A setpoint needle reads its hold
   pair SETTLED: the walk and park between pairs mean a mid-move pair is read at a dial still travelling from the park, and its
   centre is dragged (seed 160: the mid static twin ended 7.7 ticks off a crossing it started 1.7 from). The lag is declared by the
   System, so this is a door row (parse A), never a settings check. For `hold-pair-v1` it never fires (`hold-mid.toml` is
   unchanged).
3. `park` when any parking phase `p` in `PARKS[shape]` has `cfg[p].n_eq < lag + skip`: the park reading is scored against the
   edge, so it too is read settled. Never fires for `hold-pair-v1` (`PARKS` is empty).

## 4. What the needle does (holdtab names; all pure, all total over their domains, KeyError outside)

### 4.1 Tables added to `navigator/holdtab.py`
```
SETPOINT = "hold-setpoint-v1";  SHAPES = (NEEDLE, SETPOINT)
SAFE = {"+": -1, "-": 1}                      # ordered_side -> tick direction of the SAFE side (away from the ordered side)
PHASE_PAYLOAD = {**PAYLOAD, "walk": "leg", "park": "park"}   # a CONTRACT name (the reader and the scorer key on it)
PHASES = {NEEDLE: tuple(PAYLOAD), SETPOINT: tuple(PHASE_PAYLOAD)}
SETTLE = {"ignite": c.ignite, "approach": c.approach, "hold": c, "walk": c.approach, "park": c.park}   # the settings a phase reads at
PARKS  = {NEEDLE: (), SETPOINT: ("park",)}
PAIR_SETTLED = {NEEDLE: False, SETPOINT: True}  # the shape must read its hold pair settled (§3 row 2)
BAND_GEOMETRY = ("S", "n_eq", "z", "g", "step", "park")  # what a declared dead band is bound to (§2); one tuple: a new binding is one cell
sigma_ticks(sigma, g) = (n, d)  # sigma*g exactly: repr(sigma)'s decimal digits * g over 10^k (finite sigma only)
offset(sigma, g) = n // d       # whole by parse B (n % d == 0)
setpoint(centre, off, side) = centre + SAFE[side] * off
reach(g, off, side) = (max(g, off), g) for "+", (g, max(g, off)) for "-"     # ticks the hold needs below / above its centre
placed_at(kind, c, below, above, T) = ("range-low", kind, "range-high")[1 + (c > T - above) - (c < below)]
hold_kind_at(cls, view, mode, centre, step, below, above, T)   # hold_kind with placed_at
ignite_kind_at(br, below, above, T)                              # ignite_kind with placed_at
```
With below = above = g each `_at` function IS its 1552 namesake (t15 checks every cell). `PAYLOAD` is unchanged.

### 4.2 The needle (`navigator/hold.py`)
The drop keeps `off = offset(sigma, g)` and `(below, above) = reach(g, off, side)` (side = declared `ordered_side[dial]`), and
uses `ignite_kind_at` / `hold_kind_at` with them in place of `ignite_kind` / `hold_kind`. Every hold step's payload `setpoint` is
`setpoint(centre, off, side)` (1552 §5.2's key; for v1 it is the centre, as before).

**The park cycle** (setpoint shape only; `PARKS[shape]` is empty for v1, so v1 runs none of it):
1. Before each hold pair: **walk** to the low probe `centre - g`.
2. After each hold pair that is not a range kind and not `lost`, with the centre already moved by the step's ticks: **walk** to
   `s = setpoint(centre, off, side)`, then **park**: one reading AT s, with `park.n_eq`, `park.S` — a `nudge` to s (ON) or a
   one-tick `scan` of [s] (OFF).

**walk(to)**: ON only (OFF: no step at all). `legs(to - pos, max_nudge)` whole strides, each a nudge with the APPROACH
settle/window, each a step `phase "walk"`, verdict `moving`, reason `stride`, ticks = the stride, payload key `leg` =
common + {d}. The last move (≤ max_nudge) is left to the reading at `to`. Under 1552's door (2g + step ≤ max_nudge) the walk to
the low probe from the high probe of the previous pair is always empty, which is why v1 is unchanged.

**park step**: `phase "park"`, verdict kind `park`, reason = the class of its reading (`SIG-`, `UNRES`, `SIG+` as read), ticks
null, payload key `park` = common (1552 §5.2's eight) + {n (the hold pair's n), centre (after the move), setpoint (= s)}.
**The park reading enters no table**: it never moves the centre, never counts toward `lost`, never decides anything. A park
or walk call the wire does not answer ends the stream as 1552 §4.5 (an unevaluated step of that phase, the kind from
`unread`).

### 4.3 The fold
Unchanged: the outcome is the fold of the last step's kind (1552 §4.6). `park` and `moving` are never last kinds.

### 4.4 The cycle row (plan 1561's per-shape `cycle` table; this plan's Phase 4, on 1561's merged tip)
Plan 1561 Phase 4 makes `drift_score.cycle` a table keyed on the start record's `needle` (a shape with no row is a KeyError,
never the pair formula). The setpoint row needs the dial's `max_nudge` and declared side, which are in the START RECORD and not
in the settings, so this plan's Phase 4 widens the signature: `cycle(start) = CYCLE[start["needle"]](start)` (1561's caller
`s["step"] / cycle(start["needle"], s)` becomes `s["step"] / cycle(start)`; 1561's pair row reads `start["settings"]` and is
unchanged in value). With `cfg = start["settings"]`, `r(x) = x.n_eq + x.S · skip` the sweeps of one reading at settings `x`,
`off = offset(sigma, g)`, `M = start["declared_other"]["dials"][0]["max_nudge"]` (dials is not a slot),
`side = start["belief"]["ordered_side"]["declared"][dial]` (a slot), `n(δ) = len(legs(δ, M))`:
```
CYCLE["hold-setpoint-v1"](start) = 2·r(cfg) + r(cfg.park) + max over m in (−step, 0, +step) of W(m) · r(cfg.approach)
W(m) = n(m + SAFE[side]·off − g) + n(SAFE[side]·off + g)        # walk to the park (from the high probe, after the centre moved m),
                                                                 # then park → low probe; each walk's last move is the next reading's
```
This is the cycle's UPPER bound (the centre's move is at most one step). At g 12, step 6, M 32, approach {n_eq 48, S 40}: on a
"+" dial (the shipped fixture) W = 1 at σ 1.5 (|−6 − 18 − 12| = 36 ticks: one stride) and at σ 2 (|0 − 24 − 12| = 36), so the
row is 2·950 + 950 + 88 = 2938 sweeps against the pair's 1900; on a "−" dial W = 0 at σ 1.5 (2850) and W = 1 at σ 2
(the walk back from the park, 24 + 12 = 36 ticks: 2938). At σ 4 it is 3114 ("+") and 3026 ("−"): the side matters. For `hold-pair-v1` the row is 1561's `2 · r(cfg)` unchanged. Until Phase 4, 1561's score of a setpoint run is a
KeyError, by design.

### 4.5 The band writer (`environment/drift_band.py`, NEW in this plan's Phase 4; plan 1561's `band` subcommand calls it)
`band(table, cost_at) -> {"geometry", "ticks", "admissible", "about", "domain", "out", "gaps"}`, pure: ONE band row (§2.2) per table
(`cost_at` = {approach, skip, max_nudge}, the settings and apparatus the description's `cost` is computed at: today plan 1552's
approach {S 40, n_eq 48}, skip 1, and the fixture's max_nudge 32), reading
`table["geometry"]`, `table["rows"]` and `table["locks"]` by the lock table at the top of this schema: `geometry` = the table's,
`ticks` = ceil(max p95 over the band-class runs of the four laws with sigma > 0), `admissible` = the sorted sigmas of those rows
whose sigma·g is whole and > ticks (the type, §2), `about` = §2.3's description of it (its numbers computed, its sha the table's),
`domain` = the (law, direction, rung, sigma) cells all of whose runs are band-class, `out` = the out-class runs (law, rung, sigma,
seed), `gaps` = the gap-class runs. A table with any gap, or no band-class run, is a `ValueError` naming them, never a band.
`accept.py` (B3) and t16 apply the same rule; `contract/test_drift_score.py` s11 is replaced at this merge by the line in the plan
("Files", Phase 4), which asserts the setpoint row's value at the shipped files.

## 5. The report
### 5.1 start
`needle` = the shape (`settings["needle_structure"]`). `sigma`:
- v1: `{"offset": 0, "unit": "g", "measured": "pair-half-width"}` (1552 §5.1, unchanged)
- setpoint: `{"offset": sigma, "unit": "g", "measured": "pair-half-width", "ticks": offset(sigma, g), "dead_band": dead_band}`
### 5.2 step
`step(n, phase, …)` keys the payload with `PHASE_PAYLOAD[phase]` (`walk` → `leg`, `park` → `park`).

## 6. M and the kernel values
Unchanged: every reading, walk and park included, is a node of the declared path (1552 §6).

## 7. The map
`compass-map/1`, unchanged states. Head `needle` = the shape; head `n_eq` is TOTAL over `PHASES[shape]`,
`{p: SETTLE[p](cfg).n_eq for p in PHASES[shape]}` (v1: ignite, approach, hold, in that order, unchanged; setpoint: + walk (the
approach's), park), so plan 1565's clock, which dates a reading by its phase's settle, has a cell for every phase. The reader
checks the keys against `PHASES[head.needle]`. A place's `call.phase` must be in `PHASES[head.needle]` (a v1 map naming `park` is unreadable).

## 8. The reader (`needlestream/read_hold.py`)
The replay (1552 §8) replays both shapes; `_head` accepts `needle in SHAPES`; payload lookups use `PHASE_PAYLOAD`. Added or
extended, pure:
- `sigma(stream)` → {g: sigma, ticks: offset(sigma, g), value: ticks*(hi-lo)/T, ticks_per_g: g}
- `settle(stream)` → n_eq gains `park` for the setpoint shape (mid_move, relaxed over the same keys)
- `deadband(stream)` → **the needle's MEASURED band**, from its own evaluated hold pairs only: per pair,
  `z * sqrt((e_lo² + e_hi²)/2) / (|D_hi - D_lo| / (2g))` ticks for the declared observable; a flat pair (equal values) has no
  finite band and is COUNTED in `n` and `flat`, never dropped. → {n, flat, median, p95} (sorted finite bands, index
  `min(len-1, int(q*len))`; None when there are none).

## 9. The scorer (`environment/hold_score.py`)
`score()` unchanged in keys and meaning (hold steps only); its `segments` reads `PHASE_PAYLOAD` so walk and park steps count.
Added `setpoint_score(stream, rows, cfg)`, pure, KeyError on a reading with no truth row:
- side = `start.belief.ordered_side.declared[dial]`; off = offset(sigma, g); band = dead_band.ticks (`NO_STEPS` for hold-pair-v1)
- `actual_ticks(rows)`: window → the tick the dial ACTUALLY held over it: the truth row point's `dial` runs (SCHEMA-1553 §5),
  each run weighted by the samples of the window it covers. One dial.
- per evaluated park step: truth_tick at its window; `actual` at its window; `margin = SAFE[side] * (actual - truth_tick)`
  (never the commanded setpoint; see the note below): positive on the safe side; `cell` = "SAFE" if margin > 0 else "UNSAFE";
  row keys {step, index, centre, setpoint, actual, truth_tick, margin, cell}
- `safe_fraction`, `mean_margin_g` (mean margin / g), `min_margin_g`, `rms_set_e_g` (rms of margin − off, / g),
  `ordered_share` (share of ALL readings of evaluated hold, walk and park steps whose ACTUAL tick is on the TRUE ordered side:
  `SAFE[side] * (actual - truth) < 0`), `ordered_depth_max` and `ordered_depth_p95` (over the same readings, ticks past the true
  crossing on the ordered side, `max(0, -SAFE[side]*(actual - truth))`; 0 on the safe side; p95 as §8: the probe's exposure,
  REPORTED, never barred — owner ruling OQ-3), `edge_error_p95` (p95 of \|margin − off\| in ticks: the needle's error against the
  edge, the statistic the band declares), `band_holds` (`edge_error_p95 <= band`); each `NO_STEPS` when there is no park step
- keys: {plan, offset_K, needle, sigma, sigma_ticks, g, dead_band_ticks, ordered_side, feedback, outcome, park_steps,
  safe_fraction, mean_margin_g, min_margin_g, rms_set_e_g, ordered_share, ordered_depth_max, ordered_depth_p95, edge_error_p95,
  band_holds, parks}

Note on the sign: `SAFE[side] * (actual - truth)` is the dial's displacement from the true crossing measured in the safe
direction; positive = the dial sat on the safe side of the truth.

## 10. The orchestrator (`environment/run_hold.py`)
`SETPOINT = {"hold-pair-v1": (), "hold-setpoint-v1": ("setpoint.json",)}`. For a setpoint run it also writes `setpoint.json` =
`{**setpoint_score(st, rows, scfg), "noise_band": deadband(st), "run_id": rid}` (`noise_band` is the reader's per-reading band, 1552) (sorted keys, as score.json), computed inside
the same truth-join `try` as score.json. A v1 run writes no `setpoint.json`. Refusals as 1552 §10 (a dead-band sigma: exit 2,
`refused.json` only, no server; a mid-move setpoint pair: exit 2, `refused.json` field `n_eq` parse A, no report, map or score; likewise a mid-move park, field `park`).

## 11. Isolation
As 1552 §11: the three needle modules keep 1552's import allowlist and open only the settings and the map; the scorer is
never imported by the needle side.

## 12. Out of scope
A mid-move setpoint needle (refused at the door; a later plan may read the pair mid-move only after a settled
walk); a setpoint measured at run time (the dead band is declared from recon; QC B2a); a one-sided hold that never crosses (the pair
still straddles the crossing; `ordered_share` reports the exposure); a setpoint on more than one dial; a default sigma; σ for
the recover needles; any change to the apparatus or to plan 1552's contract files.
