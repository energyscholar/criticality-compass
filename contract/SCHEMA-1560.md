# SCHEMA-1560 — the random Boolean network System on the frozen stage-3a blind wire

FROZEN by plan 1560 Phase 0. The Generator builds to this; it does not edit it. The tests that hold it are
`contract/test_rbn_core.py` (k01–k08) and `contract/test_rbn_blind_conformance.py` (b01–b08).

## 1. Scope
One System, `rbn`, served by the existing System-neutral server `environment/blind_server2.py` (unchanged) through
`system-instantiated/plugins/rbn/blind.py`. The wire is the frozen SCHEMA-1525 stage-3a face: `declare` and
`measure`; everything else is `nev`. Only K is a dial on this wire. The bias p is a DECLARED FIXED value (§6), never
a dial here. A result on this wire is a result on the K section at that p. It is never a unicritical result for the
System. The two-dial (K, p) face is a later wire (plan 1545's lane; §9).

## 2. The model (the core, `plugin.py`)
A quenched network of N nodes, coupled across both dials. It is drawn once from one generator `rng = default_rng(seed)`,
in this order:
1. `v = rng.random(N)`: the in-degree offsets.
2. For each node i in order, `rng.choice(N, KMAX, replace=False)`: its KMAX inputs, distinct, read in order. A node may
   read itself.
3. `w = rng.random((N, 2**KMAX))`: the table weights.

`KMAX = ceil(hi)`, where hi is the high knob.
- **In-degree.** At dial K, node i reads its first `k_i(K) = floor(K + v_i)` inputs. This is monotone in K for every
  node, and its mean over the ensemble is exactly K.
- **Table.** With bias p, node i outputs `w[i, r] < p` on row `r = sum_{m < k_i} x[inputs[i, m]] * 2**m`. Every row is
  1 with probability p and is monotone in p.
- **One synchronous update.** `outputs(net, x, K, p)` returns a NEW bool array.
- **Annealed line.** With distinct inputs and independent rows, E[λ] = 2p(1−p)·K exactly, where λ is the one-step
  Derrida damage (§3). The annealed critical set is the LINE 2p(1−p)K = 1.

Constants:
- `UPDATE = "uniform-probe"`
- `ORDERED_SIDE = "-K"`: the frozen side, 2p(1−p)K < 1, is the low-K side.
- `DIALS = ("K", "p")`
- `critical_K(p) = 1 / (2p(1−p))`

## 3. The measurement (one Derrida probe)
`probe(net, K, p, eta, rng)` makes its draws in this order:
1. `x = rng.random(N) < 0.5`: a fresh uniform state.
2. `j = rng.integers(N)`.
3. `ua = rng.random(N)` and `ba = rng.random(N) < 0.5`.
4. `ub = rng.random(N)` and `bb = rng.random(N) < 0.5`.

Then `y` is x with bit j flipped. Each replica updates once:
- `fx = where(ua < eta, ba, outputs(x))`
- `fy = where(ub < eta, bb, outputs(y))`

The damage is `h1 = sum(fx != fy)`, an int.

There is one code path for every eta. At eta = 0 the noise draws are still made. Exactly:
- λ_net(K, p) = (1/N) Σ_i Σ_{m<k_i} 2^(−k_i) Σ_r [T_i(r) ≠ T_i(r ⊕ 2^m)]
- E[h1] = (1−η)² λ_net + N(η − η²/2)

Replica noise is the field conjugate to damage: there is no absorbing healed state, so a noise world has NO transition.

## 4. State, dials, index
- `init(N, K, p, eta, seed, knobs_K)` draws the network (§2) and keeps the same rng for probes. The index starts at 0.
- `set(state, K, p)` returns the state, or `None` when K is outside the knobs (inclusive) or p is not in the open
  interval (0, 1). There is no clamp: a refused set leaves the state untouched, and set never draws. Both dials are
  real: after `set`, every probe runs at the new K AND the new p (k05 checks the probe stream at a moved p).
- `step(state, n)` draws n probes and discards them; the index increases by n.
- `sample(state)` draws one probe and returns its h1; the index increases by 1.
- The index counts probes. Probes are independent, so tau is 1 probe by construction.

## 5. The world (`blind.py`), a total parser
- A world's `kind` decides its key set, and no default is ever filled.
  - `critical`: `kind, N, p_ticks, seed, k, knobs_K, K_start, index_unit, index_kind`.
  - `noise`: the same keys plus `eta_ticks`.
  - A critical world has NO noise key, so a zero noise cannot be written.
- Value rules:
  - `N`: an int ≥ 9 and a multiple of 3. The declared L is N.
  - `p_ticks`: an int, 1 ≤ p_ticks ≤ 999; p = p_ticks/1000. So p = 0 and p = 1 cannot be written.
  - `eta_ticks`: an int, 1 ≤ eta_ticks ≤ 10^6; eta = eta_ticks/10^6.
  - `seed` is an int ≥ 0; `k` is an int ≥ 1.
  - `knobs_K` is two finite floats with 0 ≤ lo < hi ≤ 8, and `K_start` is a finite float inside them.
  - `index_unit` and `index_kind` are non-empty strings.
- `nlev` is NOT a world key. It is the constant 2.
- The tau comes from the sibling `tau-v0.toml`: `value` is a finite number > 0. Other keys are ignored.
- `parse_world(d, taud)` and `load_world(path)` never raise. Every fault is `Refused(field, detail)`, naming its field.
  An unreadable file is named by its file name. Keys are checked in this order: the kind first, then unknown keys,
  then the kind's keys in order, then the knob range, then K_start, then tau.
- `World` is a frozen dataclass with fields `(eta_ticks, N, p_ticks, seed, k, knobs_K, K_start, index_unit,
  index_kind, tau)`. `eta_ticks` is 0 for a critical world. Its properties `p` and `eta` are floats.
- Why `World` has no `kind` field: in the probe η = 0 is a physical value (no noise), not a sentinel; it runs the same
  code path as every η. The TOML is where "a noise world with zero noise" must be unwritable, and it is (`eta_ticks`
  ≥ 1 in a noise world, absent in a critical one). After parsing, `eta_ticks ≥ 1` and `kind = "noise"` are the same
  predicate, so the truth table keyed on it is total over the type.

## 6. The declaration (constant per world; a noise world declares exactly what its critical world does)
```
{"op":"declared","knobs_K":[lo,hi],"ordered_side":"-K","L":N,"tau":tau,"k":k,"index_unit":..,"index_kind":..,
 "observable":"moments","nlev":2,"roles":[{"name":"heal","role":"crossing","ordered_sign":"+"}],
 "update":"uniform-probe","fixed":{"p":p}}
```
- **13 keys:** the ten 3a keys, plus `roles`, `update` and `fixed`. `fixed` names the value at which the other dial is
  held, in the shape of SCHEMA-1545's apparatus `fixed`.
- **DECLARED DEVIATION from SCHEMA-1545's role shape:** `roles` holds ONE entry, a `crossing`. There is no `peak`,
  because no one-step quantity of this probe peaks: h1 is Poisson-like with every moment a function of λ, monotone
  in K (plan 1560 recon). The frozen narrowing rule needs a peak, so this System cannot be narrowed by it; only the
  frozen step table reads it.
- `ordered_sign` is "+": D = heal[1] − heal[0] = 1 − λ̂ is POSITIVE on the ordered (low-K) side. That is what the frozen
  step table needs under `-K`: a grid that brackets the line reads raw `SIG+|SIG-`, and the step table rules it `narrow`.
- **DECLARED DEVIATION from the roadmap's wording:** the roadmap names the crossing quantity `log λ`. This wire serves
  1 − λ̂: the same zero, on a linear scale whose jackknife error is defined at λ̂ = 0 too.
- `L` carries N, a NODE COUNT. An RBN has no length; the frozen 3a key is reused for the system size.
- `DIALS` is not on this wire. A 3a wire moves one dial, and declaring p a dial there would claim a move the wire
  cannot make. `fixed` says p is held, and §9 is the two-dial truth a later wire declares.

## 7. `measure_moments(state, Ks, n_eq, S, skip)` (behind the frozen blind_wire validation)
- If any K is outside the knobs it returns `None`, before anything moves.
- Otherwise, for each K in order:
  1. `set(state, K, state.p)`, then `step(state, n_eq)`.
  2. For each of S samples: `step(state, skip − 1)`, then `H[i] = sample(state)`.
  3. `f(idx) = 1 − mean(H[idx])`.
  4. `heal += [[0.0, f(all)]]` and `heal_err += [[0.0, jk(f)]]`.
- Level 0 is time 0, where the damage is exactly 1, so heal is exactly 0 with error 0. Level 1 is time 1.
- `jk` is the 20-block leave-one-block-out jackknife on `np.array_split(arange(S), 20)`:
  err = sqrt((B−1)/B · Σ_b (loo_b − mean(loo))²).
- It returns `{"heal": [...], "heal_err": [...]}`. The index advances by n_eq + S·skip per K.

## 8. The truth (in `<run_dir>/edge.json` only), a total table on the kind
- critical: `{"transition":"line","critical_set":{"form":"2p(1-p)K=1","approx":"annealed"},"held":{"p":p},
  "section":{"dial":"K","K_c":1/(2p(1-p))}}`
- noise: `{"transition":"none","critical_set":null,"held":{"p":p,"eta":eta},"section":null}`

The line is a new truth kind. It is never a scalar K_c reinterpreted: `K_c` exists only inside `section`, which is the
line cut at the held p.

`held` lists every parameter the world holds constant: the dial p and, for a noise world, η, which is not a dial. A
reader tells them apart by `section.dial` and by §9 (the dials are K and p); `held` is not a dial list.

The decoys fail BY STRUCTURE. With replica noise the expected healing is D(K) = 1 − N(η − η²/2) − (1 − η)²λ_net(K):
a noiseless world's data with the section moved down by the floor ηN. At ONE N a noise world whose floor leaves an
in-range zero is indistinguishable from a shifted critical world. So every shipped decoy has its floor large enough
that E[D] < 0 on the WHOLE knob range of its own network (b08 checks this exactly). A needle can then only find "no
crossing in the knobs", at any sampling budget.

## 9. Declared for later (nothing is built): the two-dial truth table
- **K section at p.** Exists for every p in (0, 1), at K_c = 1/(2p(1−p)) ≥ 2.
- **p section at K.** Exists only for K ≥ 2, at p± = (1 ± √(1 − 2/K))/2. At K = 2 the line is tangent to the p axis at
  p = ½. For K < 2 there is no crossing on the p axis. A p range that contains ½ holds two crossings when K > 2, so a
  p-only world must lie on one side of ½. Its ordered side in p is AWAY from ½.
- **K+p.** A path through the plane crosses the line where 2p(1−p)K = 1. That is a new wire (plan 1545's lane).

## 10. Purity
- `plugin.py` imports only math, dataclasses and numpy. It holds no wire face and names no file, wire or truth.
- `blind.py` imports only importlib, math, tomllib, dataclasses, pathlib, typing and numpy, and path-loads its sibling
  `plugin.py`.
- The server, the navigator and every other System's files are unchanged (sha256-pinned in b08).
