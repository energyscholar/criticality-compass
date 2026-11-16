# SCHEMA-1553 — mid-move readings (an amendment to SCHEMA-1545, the emulated apparatus)

Frozen by plan 1553 before any implementation. **Owner ruling, 2026-11-16: "Allow mid-move readings."** It reverses
plan 1545's owner question OQ-A. A real apparatus can force a reading while a dial is still moving; this one now does
too. `SCHEMA-1545.md` stays byte-identical. This file replaces the parts of it listed in §8 and nothing else; where
the two differ, this file rules.

Words (as SCHEMA-1545, plus): the **commanded** position is the last position the needle asked for. The position **in
force** is where the dial really is. A move is **pending** from the index it is commanded until the index it arrives.
A reading is **mid-move** when the position in force changed, or was not yet the commanded one, under its samples.

## 1. Files

| file | change |
|---|---|
| `environment/dial.py` | NEW: the delay line (§2). Pure; imports only `dataclasses`. |
| `environment/apparatus_wire.py` | EDITED: the door rule (§3) |
| `system-instantiated/plugins/at/apparatus.py` | EDITED: the engine reads the dial from the delay line (§2, §4); the truth row (§5) |
| `contract/test_apparatus_wire.py` | EDITED by the Auditor (plan 1553 lists every edit); frozen again |
| `contract/test_apparatus_midmove.py`, `contract/SCHEMA-1553.md` | NEW, frozen |
| `checks.toml` | EDITED: one line declares the new test |

No other file changes. `environment/apparatus_server.py`, `environment/apparatus_config.py`, `environment/drift.py`,
the three shipped `.toml` files and every older face are byte-identical to main `61fb241` (test m11 pins them). The
world file has no new key: `lag` keeps its type and its set (int ≥ 0).

## 2. The dial is a delay line

**A position commanded at index `c` is in force from index `c + lag` on.** That is the whole rule. It does not depend
on `n_eq`, `S` or `skip`, on the op, on what is commanded next, or on where a call ends.

`environment.dial` (exactly these six public names; test d02 checks that there is no seventh):

| name | value |
|---|---|
| `Track` | a frozen dataclass `(lag, arrivals)`; `arrivals` is a tuple of `(arrival index, position)` in the order commanded; a position is a tuple of integer ticks |
| `start(lag, pos)` | the track of a dial that has been at `pos` since index 0: one arrival, `(0, pos)` |
| `command(track, index, pos)` | a NEW track: the old arrivals plus `(index + lag, pos)`. The old track is unchanged. |
| `commanded(track)` | the last position commanded, as a list (arrived or not) |
| `at(track, index)` | the position in force at `index`, as a list: that of the last arrival whose index is `<= index` |
| `runs(track, lo, hi)` | the dial over the sweeps `lo … hi − 1` as maximal runs (§5) |

**The sweep that moves the index from `I` to `I + 1` runs at the dial value of `at(track, I)`** and at the hidden
values `hidden_at(I)` (SCHEMA-1545 §3, unchanged). Settle sweeps, skipped sweeps and sampled sweeps are all the same
kind of sweep; none of them asks whether a move is pending.

What this makes true by construction:

* **Lag is a pure delay.** `at` returns a commanded position, so the dial is at one commanded tick or at another,
  never between (no interpolated value has a representation: a position is a tuple of ints).
* **Order is kept and nothing is shadowed.** Commands are issued at increasing indices (each accepted point costs at
  least 40 sweeps) and all wait the same `lag`, so they arrive in the order commanded, and every commanded position is
  in force for exactly the time until the next command, `lag` sweeps late.
* **A pending move carries across points and across calls.** The track is the only place the dial lives, and no dial
  operation removes, replaces or hastens an arrival: `Track` is two fields and no method, `arrivals` is a tuple. The
  engine calls `start` once, when it is built, and never constructs a `Track` itself; every later track comes from
  `command`. Under that use, "every call ends with the dial at its commanded position" has no way to be written.
* **A command to the position already commanded is no move.** It adds an arrival that changes nothing. So `read`,
  `nudge` with `d` all zero, and a `scan` point at the commanded position are the same sweeps, bit for bit (m09).

**A move that outlasts its call (the pending-lag rule).** Let a move be commanded at index `c` in a call that ends at
index `E`, with `c + lag > E`. The call's end does nothing to it. The dial stays at the old position for the sweeps
`E … c + lag − 1` of whatever comes next — a `read`, a `nudge`, a `scan`, one call or several — and is at the new
position from sweep `c + lag` on. Nothing completes a move at the end of a call or at the start of the next one, and
a later command neither cancels nor hastens it. A refused call runs no sweep and so does not move the clock toward
the arrival. Example (lag 48): `nudge` with `n_eq = 0, S = 40, skip = 1` at index 0 is read wholly at the old tick;
the next reading's sweeps 40–47 are at the old tick and its sweeps from 48 on at the new one.

Each point of an accepted call commands its position at the index of **its own first sweep**: for the j-th point
(j = 0, 1, …) of a call accepted at index `I0`, `c = I0 + j * (n_eq + S * skip)`. A `read` commands the current
commanded position (no move). The burn (SCHEMA-1545 §2) runs at the start position.

## 3. The wire (SCHEMA-1545 §4 with one rule changed)

`n_eq` is an int ≥ 0 for `read`, `nudge` **and `scan`**. The old rule `n_eq ≥ lag` for `nudge` and `scan` is gone.
Every other rule of SCHEMA-1545 §4 stands unchanged: the four ops, the exact key sets, `S ≥ 40`, `skip ≥ 1`, bools
are not ints, `max_nudge`, the grid, the horizon, totality (a refused call changes nothing: it runs no sweep, so it
neither advances nor disturbs a pending move).

* `d` is measured from the **commanded** position: `0 <= commanded[i] + d[i] <= T[i]`.
* The cost of a call is `m * (n_eq + S * skip)` as before. The lag costs nothing extra and is never added to it.
* `pos` in `declared` is the **commanded** position. `pos[j]` in `reading` is the commanded position of the j-th
  point — the position the needle asked that reading to be taken at. It is not a statement of where the dial was.
* The reply shapes and key sets are exactly those of SCHEMA-1545 §4. **A mid-move reading is told apart by nothing on
  the wire.** There is no flag, no count of early samples, no arrival index. The needle knows `lag` (declared), its
  own requests and every `index`; §6 says what it can compute from them.

**Never on the wire** (in addition to SCHEMA-1545 §4): the position in force, the dial's value, whether a move is
pending, when it arrives, `sampling`, the runs of §5.

## 4. What one reading is (replaces SCHEMA-1545 §5, items 1–3 and the paragraph under them)

For each point of an accepted call, in order:

1. command the point's position at the current index (§2);
2. `n_eq` sweeps;
3. `S` samples: `skip` sweeps, then one sample (`(e2, gs)` as SCHEMA-1545 §5).

Every sweep runs at `at(track, I)`. `a = (index before sampling) + skip`, `b = index after the last sample`, as before.
The formulas for `D`, `D_err`, `C`, `C_err` are unchanged.

With `first` the index of the point's first sweep and no older move pending, the sweeps `first … first + lag − 1` run
at the old tick and the rest at the new one. So:

| the call asks | where the switch falls |
|---|---|
| `n_eq ≥ lag` | in the settle, or exactly at its end. Every sample is at `pos[j]`. **These are the sweeps of plan 1545, and the reply is the same bits.** |
| `n_eq < lag < n_eq + S·skip` | under the samples: sweep `lag − n_eq` (counted from 0) of the sampling is the first at the new tick. It can fall inside a sample's `skip` group. |
| `lag ≥ n_eq + S·skip` | at the reading's end or after it. The whole reading is a `read` at the old tick, bit for bit (m05); the move arrives at the first sweep of the next point, or during a later point or call. |
| `n_eq = 0` | sampling starts at once; the first `lag` sampling sweeps are at the old tick |

**Identity with the blind face** (SCHEMA-1545 §5, last paragraph) stands unchanged: it is stated for `lag = 0`.

## 5. Truth artifacts (adds to SCHEMA-1545 §7)

`edge.json` and `perf.json` are unchanged. In `truth.json` the row keys are unchanged. Two meanings are made exact and
each entry of `points` gains two keys:

* row `pos` — the **commanded** position at the row's index;
* row `actual` — the dial values of the position **in force** at the row's index, `at(track, index)`: the position
  that rules the next sweep. An arrival exactly at the row's index is in force (m05). It can differ from the value of
  `pos` only while a move is pending at the end of the call;
* point `sampling` — int, the index before the point's first sampling sweep (`a − skip`);
* point `dial` — `runs(track, first, b)`: the dial over the point's own sweeps `first … b − 1` as maximal runs of one
  position, `[[index, position], …]`. The first entry is `[first, at(track, first)]`. Each later entry is an arrival
  with `first < index < b` whose position differs from the run before it. An arrival exactly at `b` is not in it (no
  sweep of this point ran there); it opens the next point's `dial`. Indices are absolute; positions are lists of
  integer ticks, never dial values.

A point's key set is exactly `{pos, window, K_c, sampling, dial}`.

A scorer reads a point as **clean** when `dial[-1][1] == pos and dial[-1][0] <= sampling`: every sampled sweep ran at
the commanded position. Anything else is a mid-move reading, and `dial` says at which sweep each switch fell.

## 6. What stage 5a-N may rely on (replaces the "Floor" item of SCHEMA-1545 §8; the other items stand)

* **Floor.** The wire enforces no floor. `n_eq ≥ lag + k·tau` is the needle's own rule for a settled reading, and
  whether to take a mid-move reading is a needle setting.
* **`settled`, computed by the needle from the wire alone.** Keep one number, `arrive`: whenever a point commands a
  position different from the one commanded before it, set `arrive = c + lag` with `c` the index of that point's first
  sweep (§2: the `index` before the call plus `j` times the per-point cost). A reading with window `[a, b]` taken with
  `skip` is **settled** when `arrive <= a − skip`. This is sufficient, not necessary: a settled reading is always
  clean in the truth (m10); a reading the rule calls unsettled may still be clean (a move away and straight back).
* **A mid-move reading is still a reading at `pos[j]` for bookkeeping**, and its errors are the same jackknife. The
  jackknife knows nothing of the move: `D_err` of a mid-move reading is not an error bar on the settled value.

## 7. Worked cases (lag 90, start tick 400, every call `n_eq = 0, S = 40, skip = 1` unless said; test m07)

| call | sweeps | commanded | arrives | `dial` of the point | row `actual` |
|---|---|---|---|---|---|
| `nudge +32` | 0–39 | 432 | 90 | `[[0,[400]]]` | value(400) |
| `read` | 40–79 | 432 | — | `[[40,[400]]]` | value(400) |
| `read` | 80–119 | 432 | — | `[[80,[400]],[90,[432]]]` | value(432) |
| `scan 1100,100,700` | 120–239 | 1100, 100, 700 | 210, 250, 290 | `[[120,[432]]]`, `[[160,[432]]]`, `[[200,[432]],[210,[1100]]]` | value(1100) |
| `read` (`n_eq 5, S 100`) | 240–344 | 700 | — | `[[240,[1100]],[250,[100]],[290,[700]]]` | value(700) |

## 8. What this file replaces in SCHEMA-1545 (the file itself is not edited)

| SCHEMA-1545 | replaced by |
|---|---|
| §4 "`n_eq` int ≥ `lag` for `nudge` and `scan`, int ≥ 0 for `read`" | §3: int ≥ 0 for all three |
| §4 "`0 <= pos[i] + d[i] <= T[i]`", "`pos[j]` is the position the j-th reading was taken at" | §3: `pos` is the commanded position |
| §4 the op table: `read` "no dial moves"; `nudge` "then one reading at the new position"; `scan` "the dial stays at the last" | §2: each op COMMANDS (a `read` commands no move). A move commanded earlier can arrive during any op, and a reading is at the new position only from `c + lag` on |
| §5 items 1–3 and "Because `n_eq ≥ lag` is a door rule, every sample of every reading is taken with the dial at `pos[j]`, and between calls the dial is at `pos`" | §2 and §4 |
| §6 "a function of … the dial value at `pos[j]`" | the dial values of `at(track, I)` for `I = a − skip … b − 1` |
| §7 the `truth.json` row: `"actual": [dial values at pos]`, the point keys | §5 |
| §8 "Floor … the wire enforces only `n_eq >= lag`" | §6 |

Everything else in SCHEMA-1545 stands as written.
