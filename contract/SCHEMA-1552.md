# SCHEMA-1552 — the hold needle (stage 5a-N) and its map record

Frozen by plan 1552 before any implementation. It adds a needle, a reader, a scorer and an orchestrator next to the
files of plans 1525 to 1545. No existing file is edited (except `checks.toml`, if the pre-commit hook asks for an
entry). The wire is `compass-apparatus/1` of `SCHEMA-1545.md` **as amended by plan 1553** (`SCHEMA-1553.md`; owner
ruling 2026-11-16): a `nudge` or `scan` with `n_eq` below the declared `lag` is accepted, and the dial is a delay
line (§13). Nothing here relies on a wire floor for `n_eq`.

Words. The **needle** is the client that steers. A **drop** is one run of the needle from its first message to its
outcome. A **pair** is two readings, one `g` ticks below the needle's **centre** and one `g` ticks above it. A
**place** is one dial tick at which a reading was taken. **Truth** is anything the apparatus knows and does not
declare: the hidden parameter, its drift, the true crossing, the dial's actual value. **Settled** is the needle's own
word, from its own lag model (§4.2): the dial had arrived before the reading's first sampling sweep. **Mid-move** is
the opposite.

Outward wording, fixed: the kernel values of this stream are "declared under the Origin's ruling, pending kernel
revision". Never "relational reading" and never "kernel reading" without that clause.

## 1. Files (all NEW)

| file | holds |
|---|---|
| `navigator/holdtab.py` | the alphabet and the total tables. Pure. Imports only `navigator.steer` |
| `navigator/holdrep.py` | the record builders of the report and of the map. Pure |
| `navigator/hold.py` | the needle: settings parser, door, wire client, the three phases, `main` |
| `navigator/hold-settled.toml` | hold mode SETTLED, FEEDBACK ON (§2, §2.1) |
| `navigator/hold-mid.toml` | hold mode MID-MOVE, FEEDBACK ON (§2.1) |
| `navigator/hold-settled-off.toml`, `navigator/hold-mid-off.toml` | each mode with `ops = ["declare", "scan"]`: FEEDBACK OFF |
| `navigator/hold-mid-null.toml` | the mid-move null (§2.1) |
| `needlestream/read_hold.py` | the reader of a report and of a map. Pure and total |
| `environment/hold_score.py` | the scorer and the truth overlay. Pure |
| `environment/hold-score.toml` | the score settings (§9) |
| `environment/run_hold.py` | the orchestrator (§10) |

Entry points:

* `python -m navigator.hold --needle <settings toml> --port <P> --drop <name> --map <path>` — exactly these four
  arguments, in this order of declaration. Exit 0 = a stream with an outcome; 2 = `RefusedToStart` (one line on
  stderr, nothing on stdout, the map not created); 1 = the server was not there.
* `python -m environment.run_hold --env E.toml --at <apparatus toml> --needle <settings toml> --score <score toml>`.

## 2. The settings file (strict; no default anywhere)

Exactly these thirteen keys. A missing or unknown key refuses with the first such key in sorted order; otherwise the
first failing check in the order of this table refuses. Refusal: stderr `RefusedToStart field=<key> parse=B`, exit 2,
before the wire is touched. A bool is never an int; an int is never a float.

| key | domain | `hold-settled.toml` | meaning |
|---|---|---|---|
| `needle_structure` | `"hold-pair-v1"` | | |
| `ops` | `["declare","scan","nudge"]` or `["declare","scan"]` | ON | the ops the client holds. Without `nudge` it is FEEDBACK OFF |
| `g` | int ≥ 1 | 12 | half-width of the pair, in ticks; the unit of `sigma` |
| `step` | int ≥ 1 | 6 | ticks the centre moves on a `raise` or a `lower` |
| `sigma` | the int `0` | 0 | the setpoint offset in units of `g`; this needle serves 0 only |
| `n_eq` | int ≥ 0 | 450 | **the settle time of a hold probe: the needle's own choice** (§4.2) |
| `S` | int ≥ 40 | 500 | samples of a hold probe |
| `skip` | int ≥ 1 | 1 | |
| `z` | float > 0 | 2.0 | the class threshold (`navigator.steer.end_class`) |
| `ignite` | table, exactly `steps`, `S`, `margin`, `n_eq` | `{steps=[100,20], S=100, margin=1, n_eq=450}` | `steps`: non-empty list of even ints ≥ 2, each a proper divisor of the one before; `S` int ≥ 40; `margin` int ≥ 0; `n_eq` int ≥ 0 |
| `approach` | table, exactly `S`, `n_eq` | `{S=40, n_eq=48}` | `S` int ≥ 40; `n_eq` int ≥ 0 |
| `lost` | int ≥ 1 | 3 | consecutive `no-signal` hold steps before the needle ignites again |
| `M` | table, exactly the nine keys of §6, each a non-empty string | §6 | the kernel declaration |

The three `n_eq` values are three declared choices, one per phase. None of them has a floor from the wire or from
the needle: `0` is legal. The start record carries them verbatim, so a reader can say which phases read mid-move
(`read_hold.settle`, §8).

### 2.1 The five shipped files: two hold modes, NO DEFAULT

The needle has two hold modes, **SETTLED** and **MID-MOVE** (owner ruling 2026-11-16). Both are first-class settings
of the one needle; they differ in the hold probe's settle time and in nothing else. **Neither is the default**: there
is no `hold.toml`, the parser has no default for `n_eq`, and every caller names its file. Which one becomes the
default is decided later (stage 3), from fresh seeds.

`hold-settled.toml` holds the column above. The other four differ from it in exactly the keys shown.

| file | differs in | case |
|---|---|---|
| `hold-mid.toml` | `n_eq = 0` | MID-MOVE: each hold probe is read from the first sweep after the command |
| `hold-settled-off.toml` | `ops = ["declare","scan"]` | SETTLED, FEEDBACK OFF |
| `hold-mid-off.toml` | `n_eq = 0`, `ops = ["declare","scan"]` | MID-MOVE, FEEDBACK OFF |
| `hold-mid-null.toml` | `n_eq = 0`, `S = 40` | mid-move null: the whole window (40 sweeps) ends before the declared lag (48) is over |

`sigma` is 0 in all five: this needle serves the crossing itself. Setpoint offsets on the safe side are a later plan's
(before stage 3).

## 3. The door (parse A)

The needle sends `{"op":"declare"}` first. It refuses with stderr `RefusedToStart field=<f> parse=A`, exit 2, nothing
on stdout and no map, on the first of these, in this order:

| field | refuses when |
|---|---|
| `declared` | the reply is not an object with exactly the sixteen declared keys of `SCHEMA-1545.md` §4 and `op == "declared"` |
| `wire` | `wire != "compass-apparatus/1"` |
| `dials` | not exactly one dial and one position |
| `numbers` | a declared number the needle computes with is not of its type and domain: the dial is exactly `name` (str), `lo` < `hi` (numbers), `T` and `max_nudge` (ints ≥ 1); `pos[0]` (int, 0 … `T`); `index`, `lag`, `horizon`, `k` (ints ≥ 0); `tau` (number ≥ 0). A bool is never a number |
| `roles` | the roles are not a list of objects with string names, the names are not distinct, or not exactly one has `role == "crossing"` |
| `M` | the crossing role's `name` is not `M.observable` |
| `ordered_side` | (`ordered_side[dial]`, crossing `ordered_sign`) is not a pair of `+` / `-` |
| `g` | `2*g + step > max_nudge` or `2*g > T` |
| `ignite` | `T % ignite.steps[0] != 0` |

There is no settle door: a settle time is never refused.

## 4. What the needle does

### 4.1 Orientation

`view = ORIENT[(ordered_side[dial], ordered_sign)]`: the identity when the two signs agree, the flip
(`SIG-` ↔ `SIG+`) when they differ. Every table below reads classes through `view`, so "`SIG-`" means "the crossing
is above this tick" on every dial. The classes written in records are the classes as read (`steer.end_class(D,
D_err, z)`), never the viewed ones.

### 4.2 The lag model (the needle's own; from the DECLARED `lag` only)

The needle is told `lag` and is never told the dial's actual value. Its model is the needle rule of `SCHEMA-1553.md`
§6: a position commanded at index `c` is in force from index `c + lag` on. It keeps `(cmd, since)`: the tick last
commanded and the index at which it was commanded. At the start `cmd` = the declared position and
`since = index - lag` (the dial starts settled).

* Each reading of a call is commanded at the index where the reading before it ended (for the first reading of a
  call: the index before the call). `commanded(cmd, since, to, at) = (to, since if to == cmd else at)`: a command to
  the tick already commanded moves nothing.
* `settled(since, lag, first, skip) = since + lag <= first - skip`, where `first` is `window[0]` of the reading: the
  move had arrived before the first sampling sweep. Under `SCHEMA-1553.md` this is sufficient, not necessary: a
  reading marked settled was read at the commanded position, and a reading marked mid-move may or may not have been.

`settled` reads the LAST command only. That is the whole model: a delay line keeps order, so when the last command
has arrived every earlier one has.

Every reading carries its `settled` mark in the report and in the map. A mid-move reading still steers (its class
enters the tables like any other); what it never does is name a clean place (§7).

### 4.3 Phases

One **segment** = ignite, then approach (FEEDBACK ON only), then hold. Segments are numbered from 1.

**ignite.** Round `r` (from 1) scans the ticks `grid(lo, hi, steps[r-1], margin, T)`: every tick from
`lo - margin*width` to `hi + margin*width` in steps of `width`, kept when `0 ≤ t ≤ T`; round 1 has `lo, hi = 0, T`.
One `scan` with `ignite.n_eq`, `ignite.S`, `skip`. Bracket rule: set the `UNRES` readings aside; the viewed classes
of the rest must be one run of `SIG-` then one run of `SIG+`, both non-empty; the bracket is (last `SIG-` tick, first
`SIG+` tick). Kinds: `bracketed`; `no-bracket` (the rule fails: a new segment begins, at round 1); `range-low` /
`range-high` (the bracket's midpoint is not a legal centre, §4.4). After the last round the centre is
`(lo + hi) // 2`.

**approach** (ON only). `legs(delta, max_nudge)` with `delta = centre - g - pos`: `ceil(|delta| / max_nudge) - 1`
whole strides of `max_nudge` toward the low probe, each one `nudge` with `approach.n_eq`, `approach.S`, `skip`, kind
`moving`, reason `"stride"`, `ticks = d`. The last move (≤ `max_nudge`) is the first hold probe. `delta = 0` and
`|delta| ≤ max_nudge` both give no stride: a segment may have no approach step.

**hold.** Each hold step reads the pair at `centre - g` and `centre + g`, low probe first.
ON: two `nudge` calls (`d = centre - g - pos`, then `d = 2g`), each with `n_eq`, `S`, `skip`.
OFF: one `scan` of the two ticks with the same numbers. The kind is the table of §4.4.

### 4.4 The hold table (total: 9 cells)

Viewed classes (low, high) → the call:

| low \ high | `SIG-` | `UNRES` | `SIG+` |
|---|---|---|---|
| `SIG-` | `raise` | `raise` | `stay` |
| `UNRES` | `no-signal` | `no-signal` | `lower` |
| `SIG+` | `no-signal` | `no-signal` | `lower` |

The table reads the SIGN classes only. No size of `D`, no error bar and no kernel value enters it.

`DIRECTION = {stay: 0, raise: +1, lower: -1, no-signal: 0, range-low: 0, range-high: 0}`; `APPLIED = {ON: 1, OFF: 0}`. The new centre would be
`centre + APPLIED[mode] * DIRECTION[call] * step`. `placed(kind, c, g, T)` is `range-low` when `c < g`, `range-high`
when `c > T - g`, else `kind`. The step's kind is `placed(call, new centre, g, T)`; its `ticks` is
`APPLIED[mode] * DIRECTION[kind] * step`. So:

* FEEDBACK OFF never moves its centre and never sends `nudge`; its call still says `raise` or `lower`.
* There is no clamp and no shortened move. A move that would put a probe off the dial is a range kind, the last step.
* `streak` counts consecutive `no-signal` steps. ON: when `streak ≥ lost` a new segment begins. OFF never ignites
  again from a hold (it could not walk to a new centre). A `no-bracket` round begins a new segment in either mode
  (§4.3): it happens before any hold.

### 4.5 A reading that never arrives

A reply that is not a reading at exactly the ticks asked (a refusal, a closed socket, anything else) is a step with
`evaluated: false`, reason `"n/e"`, `ticks: null`. It is the last step. Its kind is
`unread(index, cost, horizon)`, from declared quantities alone: `cost(readings, n_eq, S, skip) =
readings * (n_eq + S*skip)` for the call that was not answered; `no-reading` when `index + cost > horizon` (the call
did not fit before the declared horizon, and the wire refuses it), `wire-lost` when it did fit and still did not come.
For an ON hold pair the call is one `nudge` (`readings = 1`); for an OFF hold pair and an ignite round it is one
`scan` of all its ticks.

Its payload is `{}`, with one exception: an ON hold pair whose low probe was served and whose high probe was not
keeps the low reading — the payload is the eight common keys of §5.2 for that one reading, and the map gets its
place.

### 4.6 The fold

Last kinds: `range-low`, `range-high` → outcome `OFF-DIAL`; `no-reading` → `HORIZON`; `wire-lost` → `WIRE-LOST`. No
other kind ends a stream.
The outcome's `reason` is the last step's kind. Every stream has at least one step.

## 5. The report (stdout; one JSON object per line, each flushed when known)

The envelope is `SCHEMA-1533.md` (`compass-report/2`).

### 5.1 start

`{"rec":"start","schema":"compass-report/2","needle":"hold-pair-v1","settings":<the settings table verbatim>,
"mode":{"ops":[...],"feedback":steer.mode_of(ops)},"sigma":{"offset":0,"unit":steer.SIGMA_UNIT,
"measured":"pair-half-width"},"dials":[name],"belief":report2.belief(fields),"declared_other":
report2.declared_other(fields)}` where `fields` is the declaration without `op`. Belief comes from the declaration
only.

### 5.2 step

`{"rec":"step","step":n,"phase":p,"index":<index after its last reading>,"evaluated":bool,"verdict":[{"kind","reason",
"dial","ticks"}],<payload key>:{...}}`. Payload key: `grid` (ignite), `leg` (approach), `pair` (hold). `reason` of an
evaluated ignite or hold step is the classes as read joined by `|`. `ticks` of an ignite verdict is `null`.

Common payload keys (eight): `segment`; `pos` (ticks, one per reading); `window` (`[first, last]` per reading, the
wire's); `values`, `errors` (per declared role, one number per reading, the wire's own); `settled` (one bool per
reading, §4.2); `classes` (as read); `kernel` (§6).
Plus: ignite `round`, `lo`, `hi` (the bracket, or `null`, `null`); approach `d`; hold `n` (hold step number in the
segment, from 1), `centre`, `setpoint` (= centre + sigma·g = centre), `bracket` (`[centre-g, centre+g]`), `streak`.

A hold step therefore reports the needle's belief (`centre`), its steering call (`verdict`) and its bracket, against
the wire's index: the trail (§8).

### 5.3 outcome

`{"rec":"outcome","kind":"OFF-DIAL"|"HORIZON"|"WIRE-LOST","reason":<last kind>,"bracket":null,"A_hull":null,"B_hull":null,
"agree":null,"steps":<count>}`.

## 6. M and the kernel values

`M` (in the settings, the start record and the map head), nine keys:

| key | value |
|---|---|
| `observable` | the name of the declared crossing role (`"D"`) |
| `node` | text: one reading of the observable at one dial tick, over the window and at the index the wire reports |
| `relation` | `"path"` (fixed) |
| `edge` | text: from each reading of a drop to the reading the wire served just before it |
| `direction` | text: the wire's index; the source is the later reading (current minus prior) |
| `provenance` | text; shipped: `"steering (declared under the Origin's ruling, pending kernel revision)"` |
| `transform` | `"none"` (fixed) |
| `rho_base`, `chi_0` | `"not-declared"` (fixed) |

These formulas are the A and B of `cc/kernel.py` over one path. The declaration is NOT admitted through
`cc.admit.declare` here: the needle side imports no `cc`, and the acceptance client compares the stream's values with
`cc/kernel.py`'s formulas afterwards (item K1). Admission proper waits for the kernel revision.

The nodes are ALL readings of the drop, in the order the wire served them, whatever their phase or settled mark. The
relations are one path: edge *i* runs from reading *i* to reading *i−1*. In the terms of `cc/kernel.py`:
`Relations(n, src = 1..n-1, tgt = 0..n-2)`, `A = x[src] − x[tgt]`, `B[e] = A[e] +` the A of the edge leaving
`tgt(e)`; the first edge is terminal. Per reading the report holds `kernel.A[j]`, `kernel.B[j]`: the values of the
edge that reading sources; the first reading of a drop has `"no-predecessor"` for both. `kernel.R` is
`"NOT EVALUATED"` (ρ_base and χ₀ are not declared). The needle computes these with `holdtab.kernel_next`; it imports
neither `cc` nor `numpy`. The values sit beside the verdicts and enter no table.

## 7. The map (`compass-map/1`; the file named by `--map`, opened for append)

One JSON object per line. The head is written and flushed before the start record is on stdout; the places of a step
are written and flushed before that step is on stdout.

**head** (twelve keys): `{"rec":"head","map":"compass-map/1","drop":<name>,"needle":"hold-pair-v1",
"dial":{"name","lo","hi","T"},"start":{"tick","index"},"clock":{"index_unit","index_kind","clock","lag","k","tau"},
"n_eq":{"ignite","approach","hold"},"skip":<int ≥ 1>,"roles":[the declared role names, sorted],
"sign_rule":{"observable","z","ordered_sign","ordered_side"},"M":{...}}`. `start` is the declared position and index
at the drop's first message. With `start`, `clock.lag` and `skip` the head carries all the lag model needs: a reader
recomputes every `settled` mark from the map alone.

**place** (fourteen keys), one per reading served, in the order served:

| key | holds |
|---|---|
| `rec`, `drop`, `seq` | `"place"`, the head's drop, 0, 1, 2 … within the drop |
| `dial`, `tick`, `value` | the dial's name, the tick, and `lo + tick*(hi-lo)/T` (the COMMANDED value) |
| `index`, `window` | the TIME axis: `window` is the wire's `[first, last]`; `index == window[1]` |
| `readings` | `{role: {"value", "error"}}` for every declared role |
| `class` | `steer.end_class` of the observable's reading under the head's `z` |
| `settled` | bool, §4.2 |
| `state` | `holdtab.state(class, ordered_sign, settled)` |
| `call` | `{"step", "phase", "kind"}` of the step that took the reading |
| `kernel` | `{"A", "B", "R"}`, §6 |

**The state list is OPEN across versions.** `compass-map/1` has the four states below. A later version will add
names (a `discontinuous` state for a first-order line is already expected). So the version string is the vocabulary:
a reader of `compass-map/1` answers `Unreadable` for a head whose `map` is any other string, with a reason that holds
the words `unknown map version` and that string; and `Unreadable` for a place whose `state` is not one of its four
names, with a reason that holds the words `unknown state` and that name. It never types a state it does not know as
one it does. Both refusals come before any other check of that record's content.

Within `compass-map/1`, `state` is a total function (3 classes × 2 signs × 2): a mid-move reading is `"in-transit"`; a settled one is
`"ordered-side"` when its class has the role's ordered sign, `"disordered-side"` when it has the other sign, and
`"critical-bracketed"` when it is `UNRES`. `"critical-bracketed"` says that the sign was unresolved at the head's `z`
in that reading, and nothing more: it is not a claim that the crossing is at that tick. The dial's `ordered_side` does not enter the state: it orients steering
and the truth overlay. `"unknown"` is never written: it is what `read_hold.state_at` answers for a tick with no
place.

The relation between successive places is the declared path of §6. No relation between NEIGHBOURING ticks is
declared here.

The map never holds truth: exactly the keys above, on synthetic and on real Systems alike.

## 8. The reader (`needlestream/read_hold.py`)

Pure and total. Imports only `json`, `dataclasses`, `navigator`, `needlestream`. Opens nothing, prints nothing.

* `read(text) -> Stream | Unreadable`. `Stream(start, steps, outcome, mode, dial, orient)`; `orient` is `"+"` when
  the dial's `ordered_side` and the crossing's `ordered_sign` agree and `"-"` when they differ (§4.1); `outcome` is
  `needlestream.read.PENDING` when the text has no outcome record yet. The reader walks the stream as the needle did
  and recomputes, from the numbers the stream reports, every tick, class, settled mark, kind, reason, move, centre,
  streak, segment, round, bracket and kernel value, and the kind of an unevaluated last step (§4.5). One that is not
  what the tables give → `Unreadable(reason)`.
* `read_map(text) -> Map | Unreadable`. `Map(drops)`, `Drop(head, places)`. Zero or more drops (the empty text is the
  empty map), each a head then its places; drop names unique; within a drop `seq` counts from 0 and windows move
  strictly forward from `start.index`; each place's `readings` has exactly the head's `roles`; each place's class,
  settled mark, state and kernel values follow from its own numbers, the places before it and the head.
* `places(stream, drop_name)` → the head and places a report implies; `check(stream, drop)` → `None` when the drop is
  exactly that, else a reason.
* `state_at(drop, tick)` → the state of the latest place at that tick, `"unknown"` when there is none.
* `trail(stream)` → one point per evaluated hold step: `step, index, segment, centre, bracket, kind, ticks`.
* `sigma(stream)` → `{"g", "ticks", "value", "ticks_per_g"}`: the setpoint offset in both units.
* `settle(stream)` → `{"lag", "floor", "n_eq": {phase: n}, "mid_move": {phase: n < lag}, "relaxed": {phase: n ≥
  floor}}` with `floor = lag + k*tau`. `mid_move` is the phase's SETTING against the declared lag: when it is true
  every reading of the phase that follows a move is mid-move. The per-reading truth of the matter is the `settled`
  mark (a probe at the tick already commanded is settled whatever the setting).

## 9. The scorer (`environment/hold_score.py`; never imported by the needle side)

`hold-score.toml`: exactly `offset_K` (float; where this lattice's crossing sits against `K_c`, in the dial's value),
`out_run` (int ≥ 0), `plan` (non-empty string). Shipped: `-0.0018`, `3`, `"1552"`. `parse_score(dict)` →
`ScoreCfg(offset_K, out_run, plan)` or `navigator.reader.Malformed` (field `score` for a wrong key set, else the first
key outside its domain).

* `truth_ticks(rows, dial, offset_K)`: window → the true crossing in ticks for that window, from the `points` of
  `truth.json`: the mean of the point's two `K_c` (the crossing at the window's two ends), plus `offset_K`, in ticks.
  That is the crossing at the middle of the window when the drift is linear within the window, and a declared
  approximation otherwise.
* `score(stream, rows, cfg)`: for each evaluated hold step, `truth_tick` = mean of the two probes' truths,
  `e = centre − truth_tick` (SIGNED: negative when the centre is on the low-tick side of the true crossing, whatever
  way the crossing is moving; no statistic here assumes a monotone drift), cell `IN` when `|e| ≤ g` else `OUT`, `true_kind` (`raise` when the truth is above the
  pair, `lower` when below, else `stay`), `settled` (both probes settled). Table keys: `plan, offset_K, out_run, g,
  feedback, outcome, lock, hold_steps, in_fraction, mean_e, rms_e, max_abs_e, rms_e_g, longest_out, mid_move_steps,
  segments, accuracy, verdict_table, steps`. A reading with no truth row raises `KeyError`. With no evaluated hold
  step the six per-step statistics (`in_fraction, mean_e, rms_e, max_abs_e, rms_e_g, accuracy`) are the token
  `"no-hold-steps"`, never a number and never `null`. `segments` is the number of segments in which the needle read
  something (an evaluated step). `verdict_table[true_kind][kind]` counts hold steps: the outer key is the truth, the
  inner key is the needle's call. Of a truth point only `window` and `K_c` are read; any other key (`pos`, and the
  `sampling` and `dial` of `SCHEMA-1553.md` §5) is ignored.
* `lock(outcome_kind, cells, out_run)`, a table over the three outcome kinds: `OFF-DIAL` → `LEFT-RANGE`; `WIRE-LOST`
  → `CUT-SHORT`; `HORIZON` → by the cells: none, or last cell `OUT` → `LOST`; else longest `OUT` run > `out_run` →
  `RECOVERED`; else `HELD`. Any other outcome kind raises `KeyError`.
* `overlay(drop, rows, offset_K)`: per place `truth_tick`, `true_state` (from the tick, the truth and the head's
  `ordered_side`) and `agree`: `resolved-true`, `resolved-false`, or `not-resolved` (states `critical-bracketed` and
  `in-transit`). Returned as its own table; synthetic Systems only.

## 10. The orchestrator (`environment/run_hold.py`)

Refuses before any server starts on a malformed env, world, needle or score file (exit 2, `refused.json`). The run
id is `environment.run_blind.run_id` over the world file, the env table, the needle file, the score file, `tau-v0.toml`
and the vendor table, as `run_blind` does; it does not depend on the port or on `run_dir_root`. The needle's `--drop`
is the run id. Then:
starts `environment.apparatus_server`, runs the needle as a separate process (stdout → `<run_dir>/report.jsonl`; the
map → a path in a fresh temporary directory OUTSIDE the run directory, so the needle is never handed the directory
the truth is written to), stops the server, moves the map to `<run_dir>/map.jsonl`, and only then reads `truth.json`
and writes `score.json` and `map-truth.json`. A second run into the same run directory REPLACES the map (one drop per
run directory); it never appends to it. Exit 0 whatever the outcome kind; 1 on an infrastructure failure. A report or map that does not
read, a map that is not its report's, or a reading with no truth row refuses the run (`needle_stdout`, `needle_map`,
`truth_join`). The run is a pure function of its config files: a second run writes byte-identical report and map.

## 11. Isolation

The needle's three modules import only the allowlist of `test_hold_needle.py` (h12); they call `open` exactly twice
(the settings file, the map); they name no truth word; they import nothing from `environment` or `cc`. Truth files
beside the map change nothing, byte for byte (h13).

## 12. Out of scope (named so nobody builds them here)

Persistence of a map across drops, a survey mode, any UI or Player, a relation between neighbouring ticks, a
setpoint other than 0, a second dial, a default hold mode, map states beyond the four of §7, and drift worlds other
than the shipped linear one (step, sine, ramp to failure and random walk are later worlds). These belong to the later mapping stage (after 5c) and to 5b. A map file may
already hold several drops (§8): each head carries what a later merge needs (dial, clock, lag, sign rule, M).

## 13. Dependency

`hold-mid.toml` and `hold-mid-null.toml` run only on an apparatus that accepts `n_eq < lag`: plan 1553
(`SCHEMA-1553.md`). What this contract takes from it:

* §2 there: the dial is a delay line. A position commanded at index `c` is in force from `c + lag` on, whatever the
  op, `n_eq`, `S`, `skip`, what is commanded next, or where a call ends; a pending move carries across points and
  calls. Each point commands at the index of its own first sweep. `d` and the reply's `pos` are the COMMANDED
  position. Nothing on the wire marks a reading mid-move: the mark is the needle's own (§4.2).
* §6 there: the needle rule that §4.2 here implements.
* §5 there: a truth point gains `sampling` and `dial`. The scorer here ignores them (§9).

Everything else in this contract runs on the unamended wire of plan 1545 as well: with every `n_eq ≥ lag` the two
wires are sweep for sweep the same. The contract tests use the scripted apparatus of `contract/holdwire.py`, which
accepts any `n_eq`; the one test on the real server (s08) uses settled readings only, so the Generator's branch is
green whether or not plan 1553 has landed.

## 14. Names the tests import (the test's use is the signature)
Where a section above names a function without its full signature, or a test reads a name this file does not spell
out, the way the three tests use it IS the contract. Read the tests' imports before writing each module. In particular:
`navigator.holdtab`: `hold_kind`, `bracket`, `ignite_kind`, `classes`, `commanded`, `settled`, `cost`, `unread`, and the
constants `OPS`, `LAST_KINDS`, `UNREAD`, `PLACE_STATES`, `STATES`, `IN_TRANSIT`, `UNVISITED`, `MAP`, `NEEDLE`;
the literal `M` strings of `contract/holdwire.py` `CFG["M"]`; `Stream.dial`, and the tuples `trail` and `drops` return;
the overlay's keys and `HS.LOCKS`, `HS.NO_STEPS`; `run_id` in `score.json` and `map-truth.json`; the body of
`refused.json`. A name a test imports and this file omits is a defect of this file, not a freedom: report it as a
`surprise:` line and build what the test uses.
