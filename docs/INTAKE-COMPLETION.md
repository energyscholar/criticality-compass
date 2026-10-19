# The intake's terminal: what a completed run says

Plan 1160 P6. Stage S10 KERNEL_HANDOFF is the terminal of the intake. It runs after S0 to S8 have passed; S9 ALTERNATIVE_INTAKE (the second lane) runs after it (plan 1160 A9). It turns the census into one
result per PRIMARY bridge and writes `declarations/<id>/RESULT.json`. The code is `cc/intake_terminal.py`.

## What the terminal computes

The terminal is plan 1118's REDUCE, written as the kernel operator A over a declared chain.

1. **One number per curve.** The PRIMARY projection gives one number r_k for each curve k:
   - `MAX_MEASURED` gives the curve's largest measured reading.
   - `ARGMAX_FAST` gives the fast value at that reading.
   - If two rows tie for the largest reading, the first row in stored order wins.
2. **The shift.** `[shift] c` is added here, as r_k + c. This is the only place it is applied.
3. **The chain.** The curves, in slow order, are the nodes of CC's chain relation (`door.TEMPLATES["chain"]`, declared through
   `admit.declare`). Each curve is joined to the next one.
4. **The door.** The door admits the numbers (`door.nodefield`). A value that is not finite is a Null, and S10 refuses with DOOR_REFUSED.
5. **The edges.** `kernel.A` gives the edges e_k = r_{k+1} − r_k.

Nothing between two measured curves is ever formed. There is no interpolation, no fit and no centroid. Every result names curves by
**rank**, meaning their 0-based position in slow order.

## The three results

| Result | When | What it says |
|---|---|---|
| `Located(m, lo_rank, hi_rank, tier, n_tied)` | The maximum is at an interior node m. For ARGMAX_FAST, the first interior local maximum, taking the largest r first. | The peak lies between the curves at ranks `lo_rank` and `hi_rank`. That span is the chain neighbourhood of the tied curves. RESULT.json gives their slow values (`span_slow`). |
| `MaxAtPathEnd(end)` | The largest r is the first or last curve. | No bracket exists, because only one side of the maximum has a curve. The scan may not reach the peak, so extend the slow range. |
| `NoInteriorMaximum` | Only the `ARGMAX_FAST` lane can give this: no interior node has a rising edge in and a falling edge out. | Along this projection there is no interior maximum to bracket. |

## Tier and n_tied

The tier boundary Z is declared in `intake/POLICY.toml` as `[policy] tier_z = 2.0`. It is the only constant in the terminal.

The σ of a curve depends on the S7 tiering:

| S7 tiering | σ of a curve |
|---|---|
| `STATED` | The declared uncertainty column at the curve's maximum. |
| `REPLICATES` | The sample standard deviation of the readings at the maximum's fast value. A single reading has none, which gives a non-finite σ, and the door refuses it. |
| `NONE` | No σ. |

The σ of an edge is the hypot of the σ of its two curves, as in plan 1118.

**Tiers:**
- **RESOLVED**: e_{m−1} > Z·σ_{m−1} and −e_m > Z·σ_m. The rising edge into the maximum and the falling edge out of it both exceed Z σ.
- **EXPLORATORY**: there is a σ, but one of those two edges does not exceed Z σ.
- **UNTIERED**: no σ applies. This happens with tiering `NONE`, and also with the `ARGMAX_FAST` projection: a stated σ belongs to the
  measured value, not to a location, so it gives no tier. An UNTIERED result is a **candidate with no resolution claim**. Its `n_tied` is
  `NOT_EVALUATED` and its span is the two flanking ranks, m − 1 and m + 1.

**n_tied** (tiered results only) counts the curves k with |r_k − r_m| ≤ Z·hypot(σ_k, σ_m), which is the σ of their difference. The span
covers the chain neighbourhood of all of them. A plateau of three equal maxima gives n_tied = 3 and a span two curves wider than a single
peak.

### Why the tier is not a coverage claim

S8 states the largest bracket the evidence permits (`max_bracket`). Without frozen coverage evidence for the PRIMARY lane, that is
`CANDIDATE_BRACKET`. In that case RESULT.json's `why_this_tier` says so: RESOLVED means only that both flanking edges exceed Z σ on this
bank. Read every such bracket as EXPLORATORY until coverage evidence is frozen.

## A single observable cannot tell a crossover from a transition

S8's identifiability value, `TRANSITION_TOPOLOGY_NOT_IDENTIFIABLE_FROM_AVAILABLE_OBSERVABLES`, appears in the report and in RESULT.json.

A maximum of one observable along one slow knob looks the same whether a phase transition causes it or a smooth crossover does. **A Located result is not a transition.** A Located
result says *where* the observable peaks among the measured curves. It does not say *what kind* of change happens there. That needs a
second, independent observable (a second lane), finite-size evidence, or both.

## The refusals of S10

- **NO_KERNEL_ROUTE**: there is no value route to the kernel. Either the PRIMARY lane has no bridge, or a PRIMARY bridge's template has no
  door template in CC. `PAIR_NEAREST_FAST` (plan 1118's PAIR) is not yet a door template.
- **DOOR_REFUSED**: the door refused a value. Either a curve's r_k + c or its σ is not finite. The chain relation itself cannot be refused,
  because it is acyclic by construction.

## The verdicts

S10 counts toward PRIMARY, which the run reports as one of three verdicts:

| Verdict | When |
|---|---|
| **PRIMARY_READY** | S10 executed, and the seal is confirmed (`bin/cc intake seal <id> ... --as human --confirmed-by NAME`). |
| **PRIMARY_INCOMPLETE[confirmation]** | S10 executed, but the seal is not confirmed. RESULT.json is still written, with `confirmation = UNCONFIRMED`. |
| **PRIMARY_REFUSED_AT S10** | S10 refused. No RESULT.json is written, and a stale one is removed. |

S9 ALTERNATIVE_INTAKE runs after S10 (plan 1160 A9). A refused second lane does not withhold the result: S10 still runs, the PRIMARY
verdict is what S0 to S8 and S10 make it, RESULT.json is written when S10 passed, and the ROBUSTNESS verdict is ROBUSTNESS_REFUSED at S9
with S9's code (SECOND_LANE_INFEASIBLE). Fix the second lane and run again to examine robustness.

## Choosing a second lane

A real data set (`[source] origin = "EXPERIMENT"`) needs two lanes, PRIMARY and ALTERNATIVE. A second lane must differ from the first; ARGMAX_FAST needs each curve's maximum to be interior; PAIR_NEAREST_FAST is declared `on` the measured quantity, not a derived one.

Each step of a lane takes one input, and S1 refuses OPERATION_NOT_PERMITTED when the input is in the wrong link of the chain. Its Detail
names the link the step is permitted on. A name is RAW when it is `[measured] name`, and DERIVED_OBSERVABLE when it is the `to` of a
projection of the same lane.

| Step | Declare it on | What the data must hold | Refused when they do not |
|---|---|---|---|
| projection `MAX_MEASURED` | `from` = the measured quantity (RAW) | nothing beyond the census | - |
| projection `ARGMAX_FAST` | `from` = the measured quantity (RAW) | each curve's largest reading is interior: not at the first or last fast point of its curve | S9 SECOND_LANE_INFEASIBLE |
| bridge `CHAIN_SLOW` | `on` = the `to` of a projection of the same lane (DERIVED_OBSERVABLE) | three or more curves (S8) | S8 TOO_FEW_CURVES |
| bridge `PAIR_NEAREST_FAST` | `on` = the measured quantity (RAW), not a projection's `to` | each curve's anchor inside a slow neighbour's fast span | S9 SECOND_LANE_INFEASIBLE |

`PAIR_NEAREST_FAST` has no door template in CC, so declare it in the ALTERNATIVE lane only: as the PRIMARY bridge, S10 refuses
NO_KERNEL_ROUTE. The two lanes differ when their projections or their bridges differ (else S1 refuses LANES_IDENTICAL). Two pairs that
differ, for example:

- PRIMARY: `MAX_MEASURED` from the measured quantity to `X_max`, then `CHAIN_SLOW` on `X_max`.
- ALTERNATIVE: a bridge `PAIR_NEAREST_FAST` on the measured quantity itself (no projection); or a projection `ARGMAX_FAST` from the
  measured quantity to `X_star`, then `CHAIN_SLOW` on `X_star`, when every curve's maximum is interior.

`peek` and the census cannot tell you whether a maximum is interior (that is a value). If S9 refuses, the result of S10 stands; the
second lane is what was refused. When you cannot know the maxima are interior, declare `PAIR_NEAREST_FAST` as the ALTERNATIVE bridge
(plan 1160 A23).

## RESULT.json

`declarations/<id>/RESULT.json` is written on every run where S10 passed. It holds:

- `results`: one entry per PRIMARY bridge, with the bridge, its `on`, the projection, the result `type`, `m`, `lo_rank`, `hi_rank`, `tier`
  and `n_tied` (or `end`), `span_slow` or `end_slow` (the slow values of the span's curves), `span_curves` (their file names) and
  `n_curves`.
- `ranks`: says what a rank is.
- `tiering` and `tier_z`.
- `identifiability`.
- `max_bracket` and `why_this_tier`.
- `confirmation` and `primary_verdict`.
- `code_identity`: the commit, the code hash and the terminal file's sha256.
- `seal_identity`: the seal status, the declaration sha256, when it was sealed, the author kind and who confirmed it.

Only these fields hold numbers: the ranks and counts, `tier_z`, and the slow values of the span. `tests/test_intake_leak.py` K7 checks this.

**The report** (`intake-report.md`) prints the result type, ranks, tier, n_tied, the number of curves and the identifiability. It **never**
prints a slow or measured value. The slow values are only in RESULT.json.

## From INCOMPLETE to READY

```
bin/cc intake run demo1                      # PRIMARY_INCOMPLETE, missing confirmation; RESULT.json confirmation UNCONFIRMED
rm declarations/demo1/SEAL.json declarations/demo1/seal.log
bin/cc intake seal demo1 --author "<name>" --as human --confirmed-by "<name>"
bin/cc intake run demo1                      # PRIMARY_READY; RESULT.json confirmation CONFIRMED
```

Confirmation is a human act: you confirm that you, a human, read the declaration and stand by it. `tests/test_intake_cli.py` runs these
four lines.
