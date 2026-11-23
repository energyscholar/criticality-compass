# SCHEMA-1569 — Compass stage 4: the 2-D Ising System on the same blind face

FROZEN with `contract/test_ising_port.py`. Where plan 1569 and this file differ, this file rules. It amends nothing in
SCHEMA-1545, -1546, -1552 or -1553. It adds one face, the **Engine face**, which states as data what the apparatus host
used to hard-code for AT. Section numbers are cited by the tests.

## 1. What stage 4 proves

A second System runs under the hold needle of plan 1552 **with no edit under `navigator/` or `needlestream/`** (p02, a tree
digest pinned at the base). The System reaches the needle only through its declaration on the `compass-apparatus/1` wire:
the role names, the ordered side, the dials and the dynamics label. The needle's settings name the observable through
`[M] observable`. The AT settings run on Ising therefore refuse to start (`field=M parse=A`, p12). That refusal is the null
of "built in, not declared".

The wire stays `compass-apparatus/1`: one dial, one lag. The 5b break (`/2`, `clock` renamed to `dynamics`) is not this stage.

## 2. The Engine face (every `plugins/<name>/apparatus.py`)

| name | type | AT value | Ising value |
|---|---|---|---|
| `PARAMS` | tuple of str | `("K",)` | `("K",)` |
| `HIDDEN` | {name: (lo exclusive, hi inclusive)} | `{"L4": (0, ln3/4)}` | `{"dK": (-0.1, 0.1)}` |
| `ORDERED_SIDE` | {dial: "+" or "-"} | `{"K": "+"}` | `{"K": "+"}` |
| `ROLES` | list of {name, role, ordered_sign?} | D crossing +, C peak | **dU4 crossing +, chi peak** |
| `DYNAMICS` | str, the wire's `clock` value | `"algorithmic (Swendsen-Wang)"` | the same string |
| `S_MIN` | int, the fewest samples a reading may take | 40 | 40 |
| `EXTRA_KEYS` | tuple of str, the plugin's own world keys | `()` | `("kind", "h_ticks")` |
| `parse_extra(d)` | d restricted to EXTRA_KEYS → dict or `Malformed` | `{}` | section 4 |
| `transition(world)` | → `"continuous"` or `"none"` | always `"continuous"` | by kind |
| `Engine(world)` | the engine | | |

`Engine` has `S_MIN` (= the module's), `pos`, `index`, `K_c(index) -> float | None`, `run(positions, n_eq, S, skip) ->
(points, spans)` and `truth_row(call, op, points, spans)`. A point is `{"pos", "window", "values": {role: float},
"errors": {role: float}}`, keyed by **every** declared role name. The truth-row keys are SCHEMA-1553 section 5's.

The host serves exactly the plugin directories that hold an `apparatus.py` (`apparatus_config.systems()`, p01).

## 3. The host (five files, System-neutral)

- `apparatus_wire.py` (p03 reads its source; p06 drives it with a stub engine whose `S_MIN` is 20 (so S = 19 is `nev` and S = 20 is a reading), whose roles are its own
  and whose dynamics is `"stub time"`):
  - `reading(pub, points, index)` builds one list per role, in `pub.roles` order.
  - The `S` floor is `engine.S_MIN`.
  - `clock` is `pub.dynamics`, and `Public` gains `dynamics`.
  - `time_label(dynamics)` returns `f"lag and drift are in {dynamics} time"`.
  - `CLOCK` and `TIME_LABEL` are gone.
- `apparatus_server.py`: the label comes from `time_label(plug.DYNAMICS)`. edge.json keeps exactly its six keys (a07);
  `K_c` may be `null`.
- `apparatus_config.py`:
  - `World` gains `extra`.
  - `parse_world` takes the plugin's `EXTRA_KEYS` and `parse_extra`.
  - `parse_env(d)` checks `system` against `systems()` itself, then calls `config.parse_env_cfg` on `d` with `system`
    replaced by `config.SYSTEMS[0]`, and rebuilds the `EnvConfig` with the real system. It never assigns to `config.SYSTEMS`
    and re-implements no rule. Every other rule is config.py's, and config.py stays sha-frozen (p10).
  - `load_apparatus_cfgs` uses `parse_env` (p09 drives it with `system = "ising"`).
- `run_hold.py`: it uses `AC.parse_env` and passes `plug.transition(world)` to `finish`.
- `hold_score.py`: adds `SCORER`, `score_none`, `overlay_none` and `NO_TRANSITION` (section 6).

None of the five holds a role name, an update-rule name, `CLOCK`/`TIME_LABEL`, or (in the wire) the literal 40 (p03).

**AT stays byte-identical**: a fixed sequence of eight calls gives the same reply bytes, truth.json, edge.json and perf.json
(timings excluded) as at the base (p04, pinned): exact bytes, except the one K_c token within ULP_BOUND (amendment I). All of plan 1545's and 1553's tests stay green, except one declared edit
(section 8).

## 4. The Ising engine (`plugins/ising/apparatus.py`)

- **Lattice.** One L × L lattice, L = 3·L_blocks, and one RNG stream: `plugin.init(L, lattice_K(0), h, burn, seed, nlev,
  (-inf, inf))`.
- **Sweeps.** Every sweep sets `state.K = lattice_K(index)`, then calls the frozen `plugin.step(state, 1)`, where
  `lattice_K(i) = tick_value(dial in force at i) + dK(i)` and `dK(i) = hidden dK + drift offset(i)` (environment/drift.py).
  (`lattice_K` is a name for this section only. The truth-row key `actual` keeps SCHEMA-1553's meaning: the dial values in
  force, without dK.)
  The dial in force follows the delay line of environment/dial.py.
- **Field.** `h = h_ticks / blind.H_PER_UNIT` on a field world and 0 on a critical one. The field never appears on the wire.
- **World kinds** (`parse_extra`):

  | kind | key set | transition |
  |---|---|---|
  | `critical` | `{kind}` | `"continuous"` |
  | `field` | `{kind, h_ticks}`, with h_ticks an `int` ≥ 1 (not a `bool`, not a float such as `2.0`) | `"none"` |

  Any other kind, a missing kind, or a key outside the kind's set is `Malformed` (p09).
- **Critical value.** `K_c(index) = plugin.critical_K() - dK(index)` on a continuous world and `None` otherwise (p08). A
  truth row's `K_c` is taken at the row's index; a point's `K_c` is `[K_c(window[0]), K_c(window[1])]` (p08 checks both
  ends). *Structure note, reviewed by the plan's reviewer and not tested:* the choice is a table keyed on the transition (`_K_C`),
  not an `if`.
- **Reading.** One reading at a position samples `S` configurations: `n_eq` sweeps first, then `skip` sweeps before each
  sample. On each sample it computes `_, msum, a, q = plugin.observe(s, nlev)`, with `m = msum / L²`.
  - `u_l(idx) = 1 - mean(q_l) / (3 mean(a_l)^2)`. Levels are finest first, and the last is the whole lattice.
  - `dU4 = u_{nlev-1} - u_{nlev-2}`, i.e. the whole lattice minus the next finer level. It is positive on the ordered side.
  - `chi = L² (mean(m²) - mean(|m|)²)`.
  - Both errors are `common.jackknife.jackknife(S, f)`, applied to the whole statistic (not combined from parts).
- **Identity with plan 1546.** Static, lagless, with dK = 0, a reading is **bit-identical** to the frozen blind face's
  `measure_moments` at the same K and seed (dU4 = U4[1] − U4[0]; chi and chi_err exactly). With a dK it is the blind face
  at K + dK. Under a linear drift and under a step drift the values **and both errors** equal a direct loop within rel 1e-9
(p07). That is the declared tolerance:
  it is the only place where an implementer's float order may differ.

## 5. One jackknife

`common/jackknife.py` holds `BLOCKS = 20` and `jackknife(S, f, blocks=BLOCKS)`. It equals both plugins' frozen
`_jackknife` exactly (p14). The Ising engine imports it and defines no jackknife of its own. AT's `apparatus.py` keeps
calling `blind._jackknife`: its float order is unchanged, which is what makes p04 a byte gate. The frozen blind modules
are not edited.

## 6. Scoring by transition

`hold_score.SCORER = {"continuous": (score, overlay), "none": (score_none, overlay_none)}`. It is a total table on
`transition(world)`; run_hold indexes it after the needle has exited.

`score_none(stream, rows, cfg)` returns exactly these keys, and run_hold adds `run_id` as it does for the continuous score
(p11 checks the whole set):
- `plan`, `transition` (`"none"`), `feedback`, `outcome` (the stream's outcome kind), `lock` (`NO_TRANSITION =
  "no-transition"`);
- `hold_steps`: the number of hold steps with `evaluated` true;
- `calls`: over those hold steps, `verdict[0].kind` → count;
- `segments`: the number of distinct `segment` ids over every evaluated step, read from the phase's payload (`grid`, `leg`,
  `pair`);
- `ignite_steps`: the number of ignite steps, evaluated or not.

It has no tracking error, no IN/OUT cells and no accuracy. `overlay_none` returns
`{"drop", "places": [], "counts": {"no-transition": n}}`, where n is the number of places in the drop (p11). The continuous score is plan 1552's, unchanged.

**Decoy reading (plan 1569 acceptance).** On a field world the hold needle must not lock. Its measured quantity is
`hold_steps` (0 = it never found a crossing to hold), and it counts only on a live run: the outcome is `HORIZON` or
`OFF-DIAL`, at least one ignite step ran, and `hold_steps` equals the count in the run's own `report.jsonl`. The map of a
field run must hold no place in a `critical-bracketed` state.

## 7. The Ising needle settings (`needle-settings/ising/`, outside `navigator/`)

There are three files: `hold-settled.toml`, `hold-mid.toml` and `hold-settled-off.toml`. Each equals its `navigator/` twin
except for exactly these keys (p13):

| key | AT twin | Ising |
|---|---|---|
| `[M] observable` | `"D"` | `"dU4"` |
| `S` | 500 | 1500 |
| `[ignite] S` | 100 | 400 |

The S values are set from recon seeds 500–509. The dU4 slope at L = 81 is shallow below K_c (recon r1): S 500 gives
|z| ≈ 1 at ±g, and S 1500 gives |z| > 2. The other keys, the M declaration included, are the AT twin's. The files live
outside `navigator/` because h19 pins that directory's glob and because stage 4 edits nothing there.

## 8. Declared edits of frozen files

1. `contract/test_apparatus_midmove.py`: delete the two lines of `PINS` for `environment/apparatus_config.py` and
   `environment/apparatus_server.py` (m11). This file's p03/p04 hold them now. Nothing else in that file changes.

No other frozen file is edited. config.py, the blind modules, at/plugin.py, the worlds of 1545 and every navigator file
stay byte-identical (a12, the 1546 conformance FROZEN list, p02).

**The life of p02 and p04 after the merge (cold audit M2; coordinator ruling 2026-11-17).** Phase 3 registers
`test_ising_port.py` in `checks.toml`, so p02 (`TREE_PINS`, the digest of `navigator/` and `needlestream/`) and p04
(`AT_BYTES`, AT's wire bytes) run in every `bin/cc check --fast` from then on. Plan 1568 adds files under `navigator/`
and `needlestream/`, so whichever of 1568 and 1569 merges **second** re-takes both constants at its own rebase, on the
first plan's merged tree, and commits that as a **declared test edit**: the two constants' values change and nothing
else in the file does. It is named in that plan's rebase section and in its report. Every later plan that edits
`navigator/`, `needlestream/` or AT's wire does the same, by name, in its own plan; a silent re-pin is a drift finding.
Within a build, C2 (`git diff <base>..tip -- navigator needlestream` empty) and B-AT hold the same facts at acceptance.

## 9. The shipped Ising worlds (p15)

All six have L_blocks 27, nlev 2, lag 48, horizon 200000, `hidden = {dK = 0.0}`, `fixed = {}` and max_nudge 32.

| file | kind | dial lo, hi, T, start | drift of dK | K_c tick |
|---|---|---|---|---|
| ising-apparatus | critical | 0.42, 0.545, 500, 0 | linear −1.3e-7 per sweep (K_c rises 0.026: the crossing moves ≈ 2 ticks per SETTLED hold step, as on AT) | 82.7 → 186.7 at the horizon |
| ising-apparatus-static | critical | same | none | 82.7 |
| ising-apparatus-static-r2 | critical | 0.40, 0.50, 400, 400 | none | 162.7 |
| ising-apparatus-static-r3 | critical | 0.425, 0.475, 200, 100 | none | 62.7 |
| ising-apparatus-field | field, h_ticks 1000 | as R1 | none | none |
| ising-apparatus-field-hard | field, h_ticks 90 | as R1 | none | none |

The one-lattice crossing of dU4 at L = 81 sits ≈ 0.005 below K_c (recon r1), so the needle holds near tick
K_c − 20 on R1. `environment/hold-score-ising.toml` holds exactly `offset_K = -0.0050`, `out_run = 3`,
`plan = "1569"` (p15), the way hold-score.toml does for AT. The acceptance client does not read it: it writes its own
copy of these three values and scores every Ising run with that copy.

**Registry (plan 1569).** Seeds 500–599 are 1569's. Recon 500–519; Part A acceptance 520–544 (never used before the
acceptance); the plan author's wiring run of the acceptance client 570–594 (burned as recon, cold audit M3); free for Part B
recon 545–569 and 595–599. Part B's scored and retry seeds lie outside this block and are requested from the
registry owner (plan 1569 Phase 4). Ports: the block **10400–10499** (the acceptance client uses 10400–10463),
disjoint from 1568's 9900–9908, 9960–9983, 10100–10144, 10200–10219 and 10300–10309 (SCHEMA-1568 §9). The shipped
`environment-apparatus-ising.toml` says 8790, the port 1568's registry gives 1569 for interactive use.
