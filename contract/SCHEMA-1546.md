# The 2-D Ising System plugin on the stage-3a blind wire (plan 1546)

**Base:** `61fb241` (plan 1545 merged). Everything that exists at the base is FROZEN and untouched: the stage-3a wire
(`contract/SCHEMA-1525.md`, `environment/blind_wire.py`, `environment/blind_server.py`, `environment/blind_config.py`,
`environment/config.py`), the AT plugin, every file under `navigator/`, and plan 1545's apparatus files. This document
adds NEW files only. The shape of `roles` (§7) is the one frozen in `contract/SCHEMA-1545.md`.
The tests are `contract/test_ising_core.py` (k01-k08) and `contract/test_ising_blind_conformance.py` (b01-b08).

## §1 What this is
A second System behind the SAME blind wire: the square-lattice Ising model. It exists so that later stages can ask
whether a needle that has never seen this System still locates its critical point (stage 4), and whether it stays
silent on a world with no transition (the field world, a crossover decoy). This plan builds the System and proves its
physics. It scores no needle.

The needle's side of the wire does not change: two ops, `declare` and `measure`; everything else is `nev`.
What changes is the content of two replies: the declaration names the observables and their ROLES, and the `moments`
reply carries those names. The exact critical coupling goes to the truth artifact and nowhere else.

## §2 The model and the coupling convention
Spins s = ±1 on an L × L torus. The reduced Hamiltonian, every nearest-neighbour bond counted ONCE:

    −H/kT = K · Σ_<ij> s_i s_j + h · Σ_i s_i        K ≥ 0, h ≥ 0

`K` is the dial (K = J/kT). In THIS plan `h` is a fixed property of a world: not a dial of the stage-3a wire, and never
on that wire. It is held as a whole number of ticks (§5), which is the form a later (K, h) two-dial wire would move (§11).
The ordered side is `"+K"`. For h = 0 the critical coupling is exact: sinh(2 K_c) = 1,
K_c = ln(1 + √2)/2 = 0.44068679350977147. For h > 0 there is no transition at any K.

## §3 The update: Swendsen–Wang with a ghost spin (the draw order is the contract)
`plugin.sweep(s, K, h, rng) -> s'` is ONE Swendsen–Wang update. Sites are numbered x = i·L + j (row i, column j);
`right(x)` = (i, (j+1) mod L), `down(x)` = ((i+1) mod L, j). With N = L·L and node N the ghost:

1. `u_r = rng.random(N)`; `u_d = rng.random(N)`; `u_g = rng.random(N)` — in this order.
2. `p = 1 − exp(−2K)`; `p_g = 1 − exp(−2h)`.
3. Bonds: x—right(x) iff `s[x] == s[right(x)] and u_r[x] < p`; x—down(x) iff `s[x] == s[down(x)] and u_d[x] < p`;
   x—ghost iff `s[x] == +1 and u_g[x] < p_g`.
4. Clusters = connected components of the N+1 nodes under those bonds, numbered 0, 1, … in order of their SMALLEST
   node index (this is what `scipy.sparse.csgraph.connected_components` returns for an undirected graph).
5. `u_c = rng.random(number of clusters)`. Cluster c flips iff `u_c[c] < 0.5` and c is not the ghost's cluster.
   The ghost's cluster never flips.

There is one code path. At h = 0, `p_g` is exactly 0, so no ghost bond forms and the ghost is a cluster of its own;
its draw is still made. The update label is `plugin.UPDATE = "swendsen-wang"`, and it is declared on the wire (§7):
lag and drift measured on this System are in ALGORITHMIC time, and a cluster update has a far smaller dynamic exponent
than a local one. k01 checks the update bit for bit against a second implementation (a union-find written out in the
test), so a local update under this label fails, and so does any other convention for K or h.
k02 checks the sampled distribution against exact enumeration on a 3 × 3 torus, with and without a field.

## §4 The core: `system-instantiated/plugins/ising/plugin.py`
Imports: `math`, `dataclasses`, `numpy`, `scipy` only. It knows no wire, no file and no truth artifact.

| name | meaning |
|---|---|
| `UPDATE = "swendsen-wang"`, `ORDERED_SIDE = "+K"`, `DIALS = ("K",)` | constants |
| `State` (dataclass) | `s` (L×L int array of ±1), `rng`, `K`, `h`, `index`, `L`, `nlev`, `knobs_K` (tuple) |
| `critical_K() -> float` | `math.log(1.0 + math.sqrt(2.0)) / 2.0` |
| `sweep(s, K, h, rng) -> array` | §3; returns a NEW array and leaves `s` as it was |
| `init(L, K, h, burn, seed, nlev, knobs_K) -> State` | `rng = np.random.default_rng(seed)`; `s = rng.choice(np.array([-1, 1]), size=(L, L))`; `burn` sweeps at (K, h); index 0 |
| `set(state, K) -> State or None` | `None` when K is outside `knobs_K` (inclusive bounds), state untouched; no clamp. Does not step. Otherwise it changes `state` in place and returns that same object. (`None` is the frozen AT plugin's shape for the same call; on the wire the frozen validation runs first, so it is never reached there.) |
| `step(state, n) -> State` | n sweeps at the state's K and h; `index += n`; in place, returns the same object |
| `observe(s, nlev) -> (bonds, msum, a, q)` | below |

`observe`: `bonds` = Σ over sites of s[x]·(s[right(x)] + s[down(x)]), a Python int; `msum` = Σ s, a Python int;
`a` and `q` are lists of `nlev` Python floats. Levels run FINEST FIRST, as the stage-3a levels do. For level l, with g = 3^(nlev−1−l), cut the lattice into g × g
boxes of side b = L/g; with m_box = (box spin sum)/b², `a[l]` = mean over boxes of m_box², `q[l]` = mean over boxes of
m_box⁴. The LAST level (l = nlev−1) is the whole lattice; level 0 has the smallest boxes.

## §5 The world config (STRICT) and its refusals: `system-instantiated/plugins/ising/blind.py`
`blind.py` path-loads its sibling `plugin.py` (`importlib.util.spec_from_file_location`, exposed as `blind.plugin`)
and uses it unchanged. Imports: `importlib`, `math`, `tomllib`, `dataclasses`, `pathlib`, `typing`, `numpy` only.

A world has a KIND, and the kind decides its key set:

    WORLD_KEYS = {"critical": ("kind", "L", "burn", "seed", "k", "nlev", "knobs_K", "K_start", "index_unit", "index_kind"),
                  "field":    ("kind", "h_ticks", "L", "burn", "seed", "k", "nlev", "knobs_K", "K_start", "index_unit", "index_kind")}

A `critical` world has NO field key: `h_ticks` (or `h`) in it is an unknown key and is refused. A `field` world has
`h_ticks`, a whole number of ticks ≥ 1, and its field is h = `h_ticks / H_PER_UNIT` with `blind.H_PER_UNIT = 100000`
(one tick is 1e-5). So a zero field, a negative field, a signed zero and a field too small to tell from zero cannot be
written: there is no float to compare with 0 anywhere between the file and the truth table.

| key | required | why |
|---|---|---|
| `kind` | `"critical"` or `"field"` | read first; it names the key set |
| `h_ticks` (`field` only) | int ≥ 1 | the field in ticks of 1e-5 |
| `L` | odd int ≥ 3, and a multiple of 3^(nlev−1) | an odd box holds an odd number of spins, so its magnetisation is never 0 and the cumulant of §7 has a positive denominator by construction. An even L is refused. |
| `burn` | int ≥ 0 | sweeps at `K_start` before the port listens |
| `seed` | int ≥ 0 | |
| `k` | int ≥ 1 | the stage-3a floor multiplier (n ≥ k·tau) |
| `nlev` | int ≥ 2 | |
| `knobs_K` | [float lo, float hi], 0 ≤ lo < hi | |
| `K_start` | float, lo ≤ K_start ≤ hi | where the lattice is burned; never K_c by rule of the shipped worlds |
| `index_unit`, `index_kind` | non-empty str | |

Ints are TOML ints and floats are TOML floats; a bool is neither; nan and inf are refused.
The tau is the sibling file `tau-v0.toml`: its `value` must be a finite number > 0 (int or float, not bool); its other
keys (`source`, `stamp`) are not read.

- `Refused(field, detail)` — a `NamedTuple` of two strings. `World` — a frozen dataclass with the fields `h_ticks`
  (an int: 0 for a `critical` world, the file's value for a `field` world), `L`, `burn`, `seed`, `k`, `nlev`,
  `knobs_K` (a tuple), `K_start`, `index_unit`, `index_kind`, `tau`, and the read-only property
  `h = h_ticks / H_PER_UNIT` (a float; exactly `0.0` for a critical world). It has no `kind` field: the kind IS
  `h_ticks > 0`, so the two cannot disagree.
- `parse_world(d, taud) -> World | Refused`. Total: it never raises and never fills a default. `field` is: `"kind"`
  when the kind is missing or is not one of the two strings; the first unknown key in sorted order (keys compared as
  `str`; `field` is `str(key)`); the missing or ill-typed key; `"L"` when L is not a multiple of 3^(nlev−1);
  `"knobs_K"` when lo < 0; `"K_start"` when it is outside the knobs; `"value"` for a bad tau; any name when `d` or
  `taud` is not a table. Order: the kind, then unknown keys (against that kind's key set), then that kind's keys in
  `WORLD_KEYS` order, then the cross-field rules in the order just given, then tau.
- `load_world(path) -> World | Refused`. A file that is missing, is not UTF-8 or is not TOML is
  `Refused(<that file's name>, …)`; that holds for the world file and for `tau-v0.toml`.

## §6 The truth: a total table on the world kind
`blind.truth(world)`:

| kind | value |
|---|---|
| `critical` (`h_ticks == 0`) | `{"transition": "continuous", "K_c": plugin.critical_K(), "held": {"h": 0.0}}` |
| `field` (`h_ticks ≥ 1`) | `{"transition": "none", "K_c": None, "held": {"h": h_ticks / 100000}}` |

`held` records the parameter the world holds fixed. It is in the truth artifact only.

Every admitted world is in exactly one row, and the row is read from an integer, not from a float. There is no
threshold: one tick is the second row. The truth does not depend on the knob range. A field world is NEVER reported
as critical.

## §7 The wire replies
`blind.declared(world)` — exactly these twelve keys:

    {"op":"declared", "knobs_K":[lo,hi], "ordered_side":"+K", "L":L, "tau":tau, "k":k, "index_unit":…, "index_kind":…,
     "observable":"moments", "nlev":nlev,
     "roles":[{"name":"U4","role":"crossing","ordered_sign":"+"},{"name":"chi","role":"peak"}],
     "update":"swendsen-wang"}

The first ten are the stage-3a keys, so the frozen `navigator.reader.parse_declared` parses the reply (it ignores extra
keys; it requires `L % 3 == 0`, which §5 guarantees). `roles` has the shape frozen in SCHEMA-1545 ("Roles"): a list
with exactly one `crossing` entry, which carries `ordered_sign` (the sign the quantity takes on the ordered side), and
exactly one `peak` entry (a quantity whose maximum marks the transition), in that order. The dial is not a role: it is
`knobs_K`, as in stage 3a. ONE thing differs from the apparatus wire, because this is the stage-3a wire: a `crossing`
quantity here is PER LEVEL (a list of `nlev` floats per coupling, as the stage-3a `Gs` is), and `ordered_sign` is the
sign of the stage-3a difference, level 1 minus level 0. The declaration names ONE dial. It says nothing of any
parameter the world holds fixed, and it is the same for every world kind and every field (§9). Every key of the
`moments` reply other than `op` and `index` is a name of `roles` or that name plus `_err`. `blind.ROLES` holds the
two entries (a tuple of dicts; `declared` sends copies); `blind.OBSERVABLE = "moments"`.

`blind.init_blind(world)` = `plugin.init(L, K_start, h, burn, seed, nlev, knobs_K)`.

`blind.measure_moments(state, Ks, n_eq, S, skip) -> {"chi", "chi_err", "U4", "U4_err"} | None`. It is `None`, and the
state is untouched, when any K of the list is outside the state's `knobs_K` (inclusive bounds): the whole list is
decided before anything moves, so there is no partial measure and no measure at a coupling other than the one asked.
(The frozen wire validates the same thing first and adds `op` and `index`, so the wire never sees the `None`.)
Otherwise, for each K in order, on the one held state: `plugin.set(state, K)`;
`plugin.step(state, n_eq)`; then S times { `plugin.step(state, skip)`; `_, msum, a, q = plugin.observe(state.s, nlev)` }.
With M = msum/N per sample (N = L²), and A, Q the (S, nlev) arrays of `a`, `q`:

- `chi = N · (mean(M²) − mean(|M|)²)` — the susceptibility (role `peak`).
- `U4[l] = 1 − mean(Q[:,l]) / (3 · mean(A[:,l])²)` — the Binder cumulant of the level-l boxes (role `crossing`).
  `U4[nlev−1]` is the cumulant of the whole lattice. With d = `U4[1] − U4[0]` (the coarser level minus the finer, the
  stage-3a difference), d is negative on the disordered side and positive on the ordered side: d RISES through 0 as K
  rises, which is what `ordered_side = "+K"` means in SCHEMA-1533 and what `ordered_sign = "+"` says. Deep on the
  disordered side both cumulants go to 0, so d goes to 0 from below: far from the transition d is NOT resolved from
  zero at a finite number of samples (§10 places the shipped knob range accordingly). The zero of d is NOT K_c at finite L: a sub-box and
  the torus have different fixed-point cumulants, so the zero sits at K_c − c/L with c ≈ 0.4 to 0.5 in the recon
  (a scaling-function offset, not a correction to scaling).
- Errors: B = 20 blocks, `blocks = np.array_split(np.arange(S), B)`; for a statistic f, the leave-one-block-out values
  `loo_b = f(np.setdiff1d(np.arange(S), blocks[b]))` and `err = sqrt((B−1)/B · Σ_b (loo_b − mean(loo))²)` — the stage-3a
  jackknife, applied to the whole statistic.
- Shapes: `chi`, `chi_err` are lists of m floats; `U4`, `U4_err` are m lists of `nlev` floats. Python floats only.

## §8 The server: `environment/blind_server2.py`
    python -m environment.blind_server2 --system NAME --world WORLD.toml --port P --run-dir DIR

A blind server for a System that owns its world config. It names no System and no physics. It loads
`system-instantiated/plugins/NAME/blind.py`, which must hold the whole face
`("Refused", "load_world", "init_blind", "declared", "truth", "measure_moments")`, and serves the FROZEN op table by
calling the frozen `environment.blind_server.serve_connection` (which uses `environment.blind_wire.handle`).
One connection at a time, as stage 3a.

Start, in this order: parse the port (taken as a string and parsed by hand); resolve the System; `load_world`; bind
127.0.0.1:P without listening; `init_blind` (the burn); write `<run_dir>/edge.json` =
`json.dumps(truth(world), sort_keys=True)`; listen. So a connection succeeds only after the truth artifact exists.
(This differs from the frozen stage-3a server, which binds and listens in one step after the burn: here the port is
BOUND before the burn, so that a busy port is refused before anything is written, and LISTENS after the truth.)
On exit, SIGTERM included, write `<run_dir>/perf.json`: a JSON list with one `{"op", "seconds"}` object per line
received, as stage 3a. A server that started writes nothing to stdout, and nothing to stderr except the frozen
loop's own `malformed: …` line for each `nev` reply.

Every start fault is a refusal: exit code 2, ONE stderr line `RefusedToStart field=<f> parse=B detail=<d>`, nothing on
stdout, the run directory not created, the port never listened on.

| fault | `field` |
|---|---|
| port not a decimal integer in 1..65535 | `port` |
| NAME does not match `[a-z][a-z0-9_]*`, or has no `blind.py`, or its `blind.py` lacks part of the face (so `at` is refused) | `system` |
| the world or its tau refused | the `Refused.field` of §5 |
| 127.0.0.1:P cannot be bound (in use) | `bind` |

The server's source holds no op name: it imports `environment.blind_server` and calls its `serve_connection`.

## §9 What the wire may not tell
- No truth: no `K_c`, no transition kind, no float within 1e-6 of K_c in any reply to the test's requests.
- No field and no kind: the declaration of a field world equals the declaration of the critical world with the same other keys.
  The decoy is indistinguishable by declaration; only the measured moments differ.
- No System name on the wire. A needle learns what it measures from `roles`, not from a name.
- No name the stage-2/3a needle contains: `chi`, `chi_err`, `U4`, `U4_err` appear in no file under `navigator/`, and
  none is an AT observable name. So the frozen needle reads the declaration and then finds no observable it knows:
  its first step is not evaluated and its stream ends in `REFUSE` (b07). The same frozen narrowing rule and the
  frozen step table (`navigator.steer`) read the reply correctly once they are given the two names from `roles`: a
  grid that brackets the transition is `narrow` under the declared `"+K"` (b07). Naming is the gap stage 4 closes.

## §10 Shipped worlds and the declared tau
`ising-blind.toml`: kind "critical", L 81, burn 400, seed 190, k 6, nlev 2, knobs_K [0.42, 0.55], K_start 0.42,
index_unit "sweep", index_kind "sample_counter". `ising-field-blind.toml` (the EASY decoy): kind "field", h_ticks 1000
(h = 0.01), and the same nine other keys. `ising-field-hard-blind.toml` (the HARD decoy): kind "field", h_ticks 90,
and the same nine other keys. Its truth is the second row of §6, exactly as the easy decoy's: a weak field is not a
transition, however critical the world looks at L = 81.
The knob range starts at 0.42, not deeper in the disordered phase, for a measured reason (plan 1546, recon): at L = 81
with boxes of 27 the level difference d of §7 is not resolved from zero at K = 0.30 with the stage-3a needle's 2000
samples, in the critical world itself, so a range that starts there gives the frozen step table an unresolved low end
in every world. At 0.42 the critical world's d is below zero by several standard errors.
`tau-v0.toml`: `value = 11` with `source` and `stamp` strings. The rule, declared before the pilot ran:
tau = ceil(2 · max τ_int) over energy, |M| and M² at K_c for L = 27, 45, 81 (measured max 5.43). With k = 6 the
stage-3a floor is n_eq ≥ 66; the stage-3a needle's n_eq = 450 clears it.

## §11 Room left for what comes next (nothing here depends on it)
- **A dial wire (5a-S, plan 1545).** `plugin.py` is wire-free and exposes `DIALS`, `set`, `step`, `observe`. A dial
  adapter is a NEW sibling module beside `blind.py` that path-loads `plugin.py`; no file of this plan is edited.
- **Ising with two dials, (K, h).** The owner has ruled that Ising is later solved with K and h both dials. Nothing
  here blocks it: `plugin.sweep` takes h per call and `State.h` is a plain field, so a dial adapter may move it; a
  world's field is already a whole number of ticks on a declared lattice (`H_PER_UNIT`), which is the form a dial
  moves; and `kind = "critical"` is a statement about a world that HOLDS h at zero, so a world whose h is a dial is a
  new kind with a new truth row (a critical POINT in the (K, h) plane), not an edit of these two.
- **A System with two dials (the RBN: K and p).** The server's face is System-neutral: a second System is a new
  directory with its own `blind.py`. The truth has a `transition` kind, so a critical LINE is a new kind, not a
  reinterpretation of `K_c`. The role alphabet is open (`knob` may label more than one name). The stage-3a
  `declared` keys (`knobs_K`, `ordered_side`, `L % 3 == 0`) are one-dial shapes; a two-dial System needs a new declared
  version of the declaration and of `measure`, not an edit of this one.
