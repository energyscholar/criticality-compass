# SCHEMA-1545 — the emulated apparatus (stage 5a-S, the one-dial System wire)

Frozen by plan 1545 before any implementation. This file adds a THIRD server face next to the Stage-2 face
(`SCHEMA.md`) and the blind face (`SCHEMA-1525.md`). Both older faces, their op tables and their files stay
byte-identical. Later stages (5a-N the hold needle, 5b two dials) add through new schema files only.

Words: the **needle** is the client that steers. The **apparatus** is this server. A **dial** is a control the needle
may turn; its position is an integer **tick**. The **index** is the apparatus clock. **Drift** is a hidden motion of
the transition that the needle is never told about.

## 1. Files (all NEW; no existing file is edited except `checks.toml`)

| file | holds |
|---|---|
| `environment/drift.py` | the drift laws: pure functions of the index |
| `environment/apparatus_config.py` | the strict parser of an apparatus world; `tick_value` |
| `environment/apparatus_wire.py` | the total op → reply map; `OPS`, `WIRE`, `CLOCK`, `TIME_LABEL` |
| `environment/apparatus_server.py` | the entry point |
| `system-instantiated/plugins/at/apparatus.py` | the Ashkin–Teller plugin's apparatus side (sibling of `blind.py`) |
| `system-instantiated/plugins/at/at-apparatus.toml`, `at-apparatus-static.toml` | the two declared production worlds (plan 1545 "Declared numbers") |
| `environment/environment-apparatus.toml` | host config (same three keys as `environment-blind.toml`) |

Entry point: `python -m environment.apparatus_server --env <environment toml> --at <apparatus toml> --run-dir <dir>`.
`tau-v0.toml` is read from the directory of the `--at` file, exactly as the blind server does.

## 2. The world file (strict)

Every key below is required. A missing key, an unknown key, a wrong type (a bool is never an int; an int is never a
float) or a value outside its set makes the server print one line to stderr,
`RefusedToStart field=<key> parse=B detail=<text>`, and exit with code 2 **before** it creates the run directory or
binds the port. There are no defaults.

| key | type | set | meaning |
|---|---|---|---|
| `L_blocks` | int | ≥ 1 | lattice side is `L = 3 * L_blocks` |
| `burn` | int | ≥ 0 | sweeps before index 0, at the start position and at the index-0 hidden values |
| `seed` | int | any | the one RNG stream |
| `k` | int | ≥ 1 | declared to the needle (its own floor multiplier) |
| `nlev` | int | ≥ 2 | levels handed to the vendored observable; this wire uses levels 0 and 1 only |
| `index_unit`, `index_kind` | str | any | declared to the needle unchanged |
| `lag` | int | ≥ 0 | sweeps a commanded dial change takes to arrive (§5) |
| `horizon` | int | ≥ 1 | the last index this world may reach (§4) |
| `dials` | list of tables | length 0 or 1 | each `{name, lo, hi, T, max_nudge, start}` (below) |
| `fixed` | table | keys = plugin `PARAMS` minus the dial names, exactly | each a finite float: the parameters that are not dials |
| `hidden` | table | keys = plugin `HIDDEN`, exactly | each a float inside the plugin's domain: the value at index 0 |
| `drift` | table | `{target, law, <law keys>}` exactly | §3 |

A dial table has exactly six keys: `name` (str, one of the plugin `PARAMS`), `lo` and `hi` (finite floats, `lo < hi`),
`T` (int ≥ 1, the number of tick intervals), `max_nudge` (int, `1..T`), `start` (int, `0..T`).
More than one dial ⇒ `field=dials` (two dials are stage 5b). Field names on refusal: the offending key itself
(`lag`, `T`, `name`, `max_nudge`, `start`, `law`, `rate`, …); a wrong `hi ≤ lo` is `field=hi`; anything wrong with
`dials` as a whole (not a list, too many, a repeated name), or anything wrong inside `fixed` or `hidden` (a wrong key
set, a value that is not a float, a hidden value outside its domain) is `field=dials|fixed|hidden`; a drift that leaves the target's domain is `field=drift`.

Order of checks (the first failure is the one reported): an unknown top-level key (the first in sorted order); the
scalar keys in the order of the table; `dials` (its shape, then inside a dial: an unknown key, `name`, `lo`, `hi`, `T`,
`lo < hi`, `max_nudge`, `start`); `fixed`; `hidden`; the `drift` table (section 3); last, the drift bounds.

For the AT plugin: `PARAMS = ("K",)`, `HIDDEN = {"L4": (0.0, ln(3)/4)}` with the domain `0 < L4 ≤ ln(3)/4`,
`ORDERED_SIDE = {"K": "+"}`.

**The dial value** of tick `t` is exactly `lo + t * (hi - lo) / T` (this expression, this order; IEEE doubles).
`environment.apparatus_config.tick_value(lo, hi, T, t)` returns it. No other dial value exists on this apparatus.

## 3. Drift (hidden, a pure function of the index)

`drift.target` names one hidden parameter. `drift.law` is one of `environment.drift.LAWS = ("none", "linear", "sine",
"step")`. The offset at index `I` is exactly:

| law | extra keys | `offset(I)` | bounds over `[0, horizon]` |
|---|---|---|---|
| `none` | — | `0.0` | `(0.0, 0.0)` |
| `linear` | `rate` float | `rate * I` | `(min(0.0, rate*horizon), max(0.0, rate*horizon))` |
| `sine` | `amp` float > 0, `period` int ≥ 2 | `amp * math.sin(2.0 * math.pi * I / period)` | `(-amp, amp)` |
| `step` | `at` int ≥ 0, `size` float | `size` when `I >= at`, else `0.0` | `(min(0.0, size), max(0.0, size))` |

`hidden_at(I)[target] = hidden[target] + offset(I)`; the other hidden values are constant. Nothing accumulates: the
value at index `I` is computed from `I`, never from the value at `I - 1`.

`environment.drift`: `parse_drift(table, targets)` returns a drift value or a `navigator.reader.Malformed`;
`offset(drift, I)` and `bounds(drift, horizon)` are the two columns above. `parse_drift` checks in this order and reports
the first failure as `Malformed.field`: the table itself (`drift`), `target`, `law`, any key the law does not have (that
key), then the law's keys in the order of the table (that key). The world is refused (`field=drift`) unless
`lo_domain < hidden[target] + bounds[0]` and `hidden[target] + bounds[1] <= hi_domain`: a drift can never carry the
hidden parameter out of the model's domain, so no sweep ever needs a guard.

**The sweep that moves the index from `I` to `I + 1`** runs at the hidden values `hidden_at(I)` and at the dial value
in force for that sweep (§5). It is one call of the frozen `plugin.step(state, 1)` after setting `state.current_K` and
`state.L4`. Drift acts on every sweep of every op: settle sweeps, lag sweeps, skipped sweeps and sampled sweeps.

The truth at index `I` is `K_c(I) = self_dual_K(hidden_at(I)["L4"])` from the vendored `lattice_at`.

## 4. The wire

One JSON object per line each way, UTF-8, `\n`. `WIRE = "compass-apparatus/1"`.
`OPS = ("declare", "read", "nudge", "scan")`. Everything else — the Stage-2 ops, the blind `measure`, `where`, an
unknown op, an `op` that is not a string, a non-object line, a line that is not JSON or not UTF-8, a missing or an
extra key, a wrong type — is answered
`{"op": "nev", "index": I}` with the current index, and **nothing changes**: no dial moves, no sweep runs, the RNG is
untouched, no truth row is written.

### requests (exact key sets)

| op | keys | effect when accepted |
|---|---|---|
| `declare` | `op` | none |
| `read` | `op, n_eq, S, skip` | one reading at the current position; no dial moves |
| `nudge` | `op, d, n_eq, S, skip` | move by `d` ticks, then one reading at the new position |
| `scan` | `op, ticks, n_eq, S, skip` | visit each listed position in order, one reading at each; the dial stays at the last |

`S` int ≥ 40, `skip` int ≥ 1, `n_eq` int ≥ `lag` for `nudge` and `scan`, int ≥ 0 for `read`. Bools are not ints.
`d` is a list of exactly `len(dials)` ints with `|d[i]| <= max_nudge[i]` and `0 <= pos[i] + d[i] <= T[i]`.
`ticks` is a non-empty list of positions; a position is a list of exactly `len(dials)` ints with `0 <= t[i] <= T[i]`.
A `scan` is **not** bound by `max_nudge`. With `m` positions (`m = 1` for `read` and `nudge`) the call costs
`m * (n_eq + S * skip)` sweeps; a call with `index + cost > horizon` is refused.

**Totality.** Every rule above is checked on the whole request before anything mutates. One illegal entry anywhere
refuses the whole call with `nev`. There is no clamp, no rounding, no partial move and no partial scan.

### replies

`declare` ⇒ exactly these keys:

```
{"op":"declared","wire":"compass-apparatus/1",
 "dials":[{"name":"K","lo":0.2,"hi":0.5,"T":1200,"max_nudge":32}],   # five keys each; [] when there is no dial
 "pos":[400],            # the current position, one tick per dial
 "fixed":{},             # parameter name -> value, for every parameter that is not a dial
 "ordered_side":{"K":"+"},   # for EVERY parameter: "+" = larger value is the ordered side, "-" = smaller
 "roles":[{"name":"D","role":"crossing","ordered_sign":"+"},{"name":"C","role":"peak"}],
 "index":I,"horizon":H,"lag":lag,"tau":tau,"k":k,"L":L,
 "index_unit":"sweep","index_kind":"sample_counter",
 "clock":"algorithmic (Swendsen-Wang)"}
```

`read`, `nudge`, `scan` ⇒ one reply shape, `m` points:

```
{"op":"reading","pos":[[t],…],"window":[[a,b],…],"values":{"D":[…],"C":[…]},"errors":{"D":[…],"C":[…]},"index":I}
```

`tau` is the number in `tau-v0.toml` as written there (the shipped one is the int 67; a needle must accept an int or a
float). `pos[j]` is the position the j-th reading was taken at; `window[j] = [a, b]` are the indices of its first and last
sample; `values[name][j]` and `errors[name][j]` are floats; `index` is the index after the call. The keys of `values`
and `errors` are exactly the role names.

**Never on the wire**, in any reply: the truth (`K_c`), any hidden parameter or its name, the drift law or its
parameters, the dial's "actual" value, the run directory, the time label of §7. A world with drift and the same world
with `law = "none"` answer `declare` with byte-identical lines.

## 5. Lag, and what one reading is

For each point of an accepted call, with `prev` the position before the point and `cur` the commanded position:

1. `L_lag` sweeps at the dial value of `prev`, where `L_lag = lag` for `nudge` and `scan`, and `0` for `read`;
2. `n_eq - L_lag` sweeps at the dial value of `cur`;
3. `S` samples: `skip` sweeps at `cur`, then one sample — `(e2, gs)` of the current configuration from the vendored
   `observables_at.observables(s[None], t[None], nlev)`.

Lag is a pure delay: the dial is either at the old tick or at the new one, never between. Because `n_eq ≥ lag` is a
door rule, **every sample of every reading is taken with the dial at `pos[j]`**, and between calls the dial is at
`pos`. `a = (index before sampling) + skip`, `b = index after the last sample`.

From the `S` samples (`N = L * L`, `G0`, `G1` the level-0 and level-1 columns of `gs`, `E2` the `e2` column), with the
frozen 20-block delete-one jackknife of `SCHEMA-1525.md` (`blind._jackknife`):

* `D = mean(G1) - mean(G0)`, `D_err = sqrt(jk(mean G1)**2 + jk(mean G0)**2)` — the crossing quantity. It is the same
  number as `Gs[1] - Gs[0]` and the `s` of the `SCHEMA-1533.md` reading class on the blind wire.
* `C = var(E2) / N`, `C_err = jk(var(E2) / N)` — the peak quantity, identical to the blind `C`, `C_err`.

**Identity with the blind face.** With no drift, `lag = 0`, and `start` at the tick whose value equals the blind
world's `K_start`, `scan{ticks:[[t1],[t2],…]}` returns bit-for-bit the `C`, `C_err`, `Gs[1]-Gs[0]`, `index` that the
blind `measure{Ks:[value(t1), value(t2), …]}` returns for the same seed, burn and sizes.

## 6. The reading stream (what `index` means; for the kernel M declaration of stage 5a-N)

One lattice, held for the life of the server, and one RNG stream. `index` is the total number of sweeps since the
burn; it is an integer and all arithmetic on it is exact. It advances by exactly the cost of each accepted call and by
nothing else. Windows of successive readings are disjoint and increasing. A reading with window `[a, b]` is a function
of the configuration at index `a - skip`, the dial value at `pos[j]`, the hidden values at indices `a - skip … b - 1`
and the RNG — so `index` orders the readings in the apparatus's own (algorithmic) time, and equal index differences
are equal amounts of that time. The index is the only clock; there is no wall-clock quantity on the wire.

## 7. Truth artifacts (the needle is never told the run directory)

Constant, ASCII: `TIME_LABEL = "lag and drift are in algorithmic (Swendsen-Wang) time"`. It is the value of the key
`time` in all three files and never appears on the wire.

* `<run-dir>/edge.json`, written **before** the port binds:
  `{"time", "wire", "index": 0, "K_c": K_c(0), "drift": <the drift table as given>, "hidden": <the hidden table>}`.
* `<run-dir>/truth.json`, written on exit: `{"time", "wire", "rows": [...]}`, one row per **accepted** `read`,
  `nudge` or `scan`, in order:
  `{"call": n (1-based), "op", "index": I after the call, "K_c": K_c(I), "pos": [...], "actual": [dial values at pos],
  "points": [{"pos", "window": [a, b], "K_c": [K_c(a), K_c(b)]}, …]}`.
  Refused calls and `declare` write no row.
* `<run-dir>/perf.json`, written on exit: `{"time", "calls": [{"op": <str>, "seconds": <float>}, …]}`, one entry per
  line received.

The server exits 0 on SIGTERM and writes `truth.json` and `perf.json` on the way out.

## 8. What stage 5a-N may rely on (frozen here, used there)

* **Floor.** The needle's own rule becomes `n_eq >= lag + k * tau`; the wire enforces only `n_eq >= lag`.
* **sigma.** The safe-side offset is an unsigned whole number of ticks, expressed through positions: a hold at centre
  `p` with half-gap `g` reads positions `p - g` and `p + g`, and `ordered_side` says which of them is the ordered one.
  A position outside `0..T` cannot be written (it is `nev`), so an out-of-range sigma has no representation.
  Alternating `p - g` and `p + g` by `nudge` needs `max_nudge >= 2 * g`.
* **Roles.** `roles` has exactly one `crossing` entry (with `ordered_sign`: the sign the quantity takes on the ordered
  side) and one `peak` entry. A needle that reads only `roles` needs no system name.
* **Lists.** `dials`, `pos`, `d`, a scan position and `actual` are lists with one entry per dial, so two dials change
  lengths, not shapes.
