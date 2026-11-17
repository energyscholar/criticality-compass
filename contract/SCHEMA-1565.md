# SCHEMA-1565 — the free-running apparatus: the world clock and the time ledger

Amends SCHEMA-1545 (sections 2, 4, 6, 7) and SCHEMA-1552 (the needle's two clock rules and section 10). Everything not named
here is unchanged. **A world with no `world_clock` key is the apparatus of plans 1545/1553, byte for byte.**

## 1. Why

Under SCHEMA-1545 §6 the index advances only by the cost of accepted calls: the needle's deliberation costs no world time, and a
needle that does nothing keeps the crossing for ever. Owner ruling (2026-11-16): the clock is a world option.

## 2. The world file: `world_clock`

**The name.** `clock` already means two other things: the wire's `declared.clock` (the dynamics label, SCHEMA-1545) and the map
head's `clock` table (SCHEMA-1552). This key is `world_clock`, everywhere it appears (world file, `World` field, `turns.json`,
module `environment/world_clock.py`), and `world_clock` is reserved as the wire name if the world clock is ever declared to a
needle. Nothing new is called `clock`.

One optional key, `world_clock`, an inline table. **Absent ≡ `{kind = "paused"}`** — the one declared default (owner ruling; it amends
SCHEMA-1545 §2 "no defaults" for this key alone). The kinds are a total table:

| kind | keys (in check order) | owed(turns n, needle seconds s) |
|---|---|---|
| `paused`  | — | 0 |
| `charged` | `per_turn`: int ≥ 0 (bool is not an int) | `per_turn · n` |
| `wall`    | `sweeps_per_second`: finite float > 0 (an int is not a float) | `floor(sweeps_per_second · s)` |

Refusals (`RefusedToStart field=<f> parse=B`, exit 2, before the port binds, no run directory):
`world_clock` not a table → `world_clock`; `kind` absent, not a str, or not a row → `kind`; a key that is neither `kind` nor one of the
kind's keys → that key (first in sorted order); then the kind's keys in table order. **The world clock is checked after every older
key** (after the drift bounds), so every refusal SCHEMA-1545 names is still refused on the same field. `TOP_KEYS` gains `world_clock`.

## 3. Turns and needle time

A **turn** is one line received on the needle's connection — any line: `declare`, an accepted call, a refused call, a line that is
not JSON. Turns are counted per server process (the ledger starts at `START` when the server starts and runs across every
connection it accepts, the harness's probe connection included); `turn` numbers continue across connections. The **needle time** of a turn (`gap_s`) is `time.monotonic()` from the moment the server finished sending its previous
reply on that connection (or accepted the connection) to the moment this line arrived. It is the one definition: the `wall` kind
bills it, and the ledger (§6) reports it. `charged` bills turns, not seconds: a needle's thinking is priced by the number of
lines it needs, which the host's load cannot change.

On each turn, BEFORE the line is parsed: `free = min(owed(n, Σgap) − ran, horizon − index)`; the world runs `free` sweeps through
`Engine.sweep()` (the dial in force by the delay line, the hidden values by the drift law at each index; no sample, no truth row),
`ran += free`. Then the line is handled exactly as SCHEMA-1545/1553 say. **The world saturates at the horizon**: the free run
never carries the index past it. Nothing new goes on the wire: replies differ from a paused world only through `index` and the
lattice the call finds.

Identity: `charged` with `per_turn = c` equals a paused world in which every line is preceded by a `read` costing exactly `c`
sweeps, the inserted replies and truth rows dropped (contract c03). `charged` with `per_turn = 0` is paused, byte for byte (c02).

## 4. The needle's two clock rules (amends SCHEMA-1552)

1. **A command is dated by its reading's window**: the point whose window opens at `a` began, and was commanded, at
   `a − skip − n_eq`. The last reply's index is NOT the command's index once the world runs between lines.
2. **A refusal is judged at the index it reports**: on a reply that is not a reading, the needle's index becomes the `nev`'s
   `index` when it has one (a lost wire reports nothing and the known index stands); `unread`'s kind is then
   `UNREAD[index + cost > horizon]`.

In a paused world both rules give the old numbers bit for bit (contract n01 pins plan 1552's needle bytes).

## 5. The needle's stopwatch: `environment/needle_timer.py`

`python -m environment.needle_timer --out F -- <navigator.hold's four arguments>` runs `navigator.hold` inside the stopwatch's own
process (an import, not a subprocess) with one socket shim. Per turn: `think_wall_s`, `think_cpu_s` (previous receipt, or connect, → this send) and `wait_wall_s`, `wait_cpu_s`
(this send → this receipt); wall is `perf_counter`, CPU is `process_time`. One JSON line per turn, then a tail line with
`turn = null` (last receipt → exit). It changes no byte the needle sends, receives or writes (n04).

## 6. The server's ledger `turns.json` and the run's `ledger.json`

`turns.json` (run directory, written in the server's `finally` with the other truth files):
`{"time": TIME_LABEL, "wire": WIRE, "world_clock": <the table as given, ABSENT when absent>, "turns": [row…]}`, one row per turn:
`{turn, op, gap_s, free, free_s, sweeps, wall_s, cpu_s, index}` — `op` as perf.json writes it; `free_s` the free run's wall
seconds; `sweeps` the call's own advance; `wall_s`/`cpu_s` the handler's perf_counter / process_time; `index` after the turn.
Invariant: `Σ(free + sweeps) = final index`. `perf.json` is unchanged (SCHEMA-1545 §7 keys).

`ledger.json` (written by run_hold AFTER score.json and map-truth.json; a pure function of the run directory plus the
orchestrator's stage times): `{summary, hold, orchestrator}`.
- World time is tiled: every sweep of `[0, final index)` has exactly one category from the total table
  `idle | lag-wait | relax | scan | approach | read-lo | read-hi | walk | park` (free sweep; settle sweep before / after the
  point's position is in force; sampling sweep of an ignite grid / approach leg / hold pair lower / upper probe / a setpoint
  needle's walk leg / park reading). The sampling category is indexed by the step's phase through the needle's own phase table
  (`navigator/holdtab.py`: `PAYLOAD` under plan 1552, `PHASE_PAYLOAD` once plan 1558 is in): a phase with no category has no row
  and the ledger refuses to import (KeyError); a served window that no step record claims is a KeyError too. No default row.
  `in_transit` (sampling sweeps before arrival) is an overlay, not a category. The categories sum to the final index exactly.
- `hold`: one row per hold step: `{step, index, sweeps{category}, in_transit, ticks, moved, kind, age[lo, hi], server_wall_s,
  needle_think_s}` where `age[k] = step index − window[k][0]`.
- `summary`: `{index, sweeps, share, in_transit, per_hold_cycle, hold_steps, hold_moves, mean_age, server{free_s, call_wall_s,
  call_cpu_s, gap_s}, needle{think_wall_s, think_cpu_s, wait_wall_s, wait_cpu_s} | null, slowest[≤5]}`.
- `orchestrator`: `{ready_s, needle_s, reap_s, finish_s, ledger_s}` (perf_counter seconds of run_hold's stages).

No ledger byte reaches the needle, and nothing the ledger measures changes a reading, a decision or a random stream.
