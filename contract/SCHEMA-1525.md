# Stage-3a wire contract — the BLIND face + `measure` (plan 1525)

**Base:** Stage-2 (`f0cad1a`). Stage-1/2 (`environment/server.py`, `environment/wire.py`, `environment/run.py`,
`navigator/needle.py`, `navigator/reader.py`, `system-instantiated/plugins/at/plugin.py`, `contract/SCHEMA.md`, their
tests and golden) are FROZEN and untouched. Everything below is a NEW declared version. One JSON object per line over
loopback TCP, as Stage-1. Revised after the Fable flaw audit (2026-11-15); the numbered findings are cited as [F#].

## Why a second server (structure, not discipline)
The Stage-1/2 server answers `where` with the true K_c, and it burns the lattice AT K_c before the port binds. Both
are correct for oracle-ON and both leak in a blind stage. The blind server is a separate entry point
(`python -m environment.blind_server --env E --at A --run-dir D`) whose op table has exactly TWO ops:

| op | reply |
|---|---|
| `declare` | `declared{knobs_K, ordered_side, L, tau, k, index_unit, index_kind, observable, nlev}` — no K_c, no w; `observable = "moments"` |
| `measure{Ks, n_eq, S, skip}` | `moments{C, C_err, Gs, Gs_err, index}` |
| anything else — `where`, `set`, `step`, `sense`, `probe`, unknown, malformed | `nev{index}` (index unchanged) |

The declared fields other than `nlev`/`observable` are exactly Stage-1's `declared_msg` (`environment/server.py:18-20`),
so the frozen `navigator.reader.parse_declared` parses it (it ignores extra keys; the needle checks `nlev` itself).

The truth is written ONLY to `<run_dir>/edge.json` = `{"K_c": float}` (no `w` — nothing in 3a scores against w [F21]),
before the port binds, exactly as Stage-1 (R4-1). The needle is never given the run dir. On exit (including SIGTERM)
the blind server writes `<run_dir>/perf.json` = a list with one object per line received, in order, each holding at
least `"op"` (`str(op)`, `"None"` when absent) and `"seconds"` (float), as Stage-1 (`environment/server.py:23-35`).

## Blind world config `at-blind.toml` (STRICT) and the blind start
Keys, exactly — a missing key, an unknown key or a wrong type ⇒ a refusal value [F15]:
`L_blocks` int ≥ 1 (L = 3·L_blocks), `L4` float, `burn` int ≥ 0, `seed` int, `k` int ≥ 1, `nlev` int ≥ 2 [F12],
`knobs_K` [float lo, float hi] with lo < hi, `K_start` float with lo ≤ K_start ≤ hi, `index_unit` str, `index_kind` str.
(No `w`.) Ints are TOML ints (bool rejected); floats are TOML floats. Its tau is the sibling `tau-v0.toml`, read with
the frozen Stage-1 tau parser (that file is NOT strict: it carries `source`/`stamp`). The parsed type is a NEW frozen
dataclass `BlindAtConfig` in `environment/blind_config.py`; the frozen `navigator.reader.AtConfig` is not used.

The blind start lives in the NEW file `system-instantiated/plugins/at/blind.py` [F14]. It path-loads the sibling
`plugin.py` (the same `importlib.util.spec_from_file_location` method as `environment/config.py:load_plugin`) to reuse
`plugin.State`, `plugin.set`, `plugin.step` and the vendored modules unchanged, and defines:
- `init_blind(cfg) -> plugin.State`: `rng = np.random.default_rng(seed)`;
  `S,T = lattice_at.at_sw(L, K_start, L4, 1, 0, burn, rng)`; `State(S[0], T[0], rng, K_start, 0, L4, nlev, L, knobs_K, None)`.
- `truth(state) -> {"K_c": float(lattice_at.self_dual_K(state.L4))}`.
- `measure_moments(state, Ks, n_eq, S, skip) -> dict` — the computation below (AT-specific, so it lives with the plugin).
`plugin.init` (burns at K_c) is never called by the blind server. `environment/blind_server.py` path-loads `blind.py`.

## `measure` — moments, not raw samples
```
→ {"op":"measure", "Ks":[K_1..K_m], "n_eq":450, "S":2000, "skip":1}
← {"op":"moments", "C":[m], "C_err":[m], "Gs":[[nlev]×m], "Gs_err":[[nlev]×m], "index":I}
```
- Validation, ALL before any mutation (in `environment/blind_wire.py`): `Ks` a non-empty list, every element a float
  (not bool/int) inside the declared `knobs_K` (inclusive); `n_eq` int ≥ 1; `S` int ≥ 40; `skip` int ≥ 1 (bool rejected
  everywhere); no missing key. Any failure ⇒ `nev`, index unchanged, nothing stepped. No clamp.
  (`S ≥ 40` = 2·B so every jackknife block holds at least two samples [F21].)
- For each K_i in order, on the ONE held state: `plugin.set(K_i)`; `plugin.step(n_eq)`; then S times
  { `plugin.step(skip)`; `E2, _, Gs, _ = observables_at.observables(s[None], t[None], nlev)`; record `E2[0]`, `Gs[0]` } [F7].
- `index += m·(n_eq + S·skip)` (this is just what `plugin.step` accumulates).
- Per K_i, with `E2` an (S,) float array, `G` an (S, nlev) array, `N = L·L`, `B = 20`,
  `blocks = np.array_split(np.arange(S), B)`, and for a statistic f the B leave-one-block-out values
  `loo_b = f(np.setdiff1d(np.arange(S), blocks[b]))`:
  - `C = E2.var() / N` (numpy default ddof=0); `C_err = sqrt((B−1)/B · Σ_b (loo_b − mean(loo))²)` with f = var/N.
  - `Gs[l] = G[:,l].mean()`; `Gs_err[l]` = the same jackknife with f = mean of column l.
- Every element of every field is a Python float. `C`, `C_err` have length m; `Gs`, `Gs_err` are m lists of nlev.

## The needle — `recover-adaptive-v0`
`python -m navigator.recover --needle recover.toml --port P`. A separate module; `navigator/needle.py` is untouched.
The port comes ONLY from `--port` (the orchestrator passes the env port: one source, no mismatch to police [F21]);
the host is always `127.0.0.1`. `navigator/recover.py` and `navigator/estimate.py` may import only: `argparse, json,
math, socket, sys, tomllib, dataclasses, typing, collections` and `navigator.*` (an AST test enforces this allowlist
[F18]). The needle sends nothing but `declare` and `measure`, opens no file except the `--needle` path, writes nothing,
and prints ONE JSON line on stdout. No clock, no timeout, no `signal` (the frozen
`tests/navigator/unit/test_04_no_clock.py` globs `navigator/*.py`) [F17].

`recover.toml` (STRICT — missing/unknown/wrong-type key ⇒ RefusedToStart): `needle_structure = "recover-adaptive-v0"`,
`bracket = [lo, hi]` floats, `m` int ≥ 5, `N` int ≥ 1, `n_eq` int ≥ 1, `S` int ≥ 40, `skip` int ≥ 1, `z` float > 0.
(m ≥ 5 so that a hull of one or two grid points plus the one-Δ pad is strictly narrower than the bracket.)
Its parser `parse_recover_cfg(raw: dict) -> RecoverConfig | navigator.reader.Malformed` lives in `navigator/recover.py`;
`environment/run_blind.py` imports it from there (environment may import navigator; never the reverse) [F2].

**Order and outcomes [F13]** (Stage-1's three statuses, `navigator/needle.py`):
1. parse `recover.toml` — fault ⇒ **RefusedToStart** (exit 2, one line `RefusedToStart field=<f> parse=B` on stderr).
2. connect `127.0.0.1:P` — failure ⇒ **Unreachable** (exit 1, one stderr line).
3. `declare` — not a valid declaration (frozen `parse_declared`), or `nlev` not an int ≥ 2 ⇒ RefusedToStart (parse=A).
4. bracket check: `knobs_lo ≤ lo < hi ≤ knobs_hi`, else RefusedToStart(field `bracket`, parse=A).
5. floor: `n_eq < k·tau` ⇒ a **REFUSE report, reason `floor`, `rounds: []`** (exit 0) — the loop is never entered.
6. rounds r = 1..N, all N, no early stop. Then: any round not Evaluated ⇒ REFUSE report reason `budget` (exit 0);
   else a **Located** report (exit 0).

**Round r.** `grid = [lo] + [lo + i·(hi−lo)/(m−1) for i in 1..m−2] + [hi]` (endpoints exact [F9]); `exp += m·(n_eq+S·skip)`
(always, evaluated or not); ONE `measure{Ks: grid, n_eq, S, skip}`. Evaluated iff the reply's op is `moments`,
`index == exp`, and `C`, `C_err` are m floats and `Gs`, `Gs_err` are m lists of `nlev` floats. If Evaluated:
`(A, B, lo', hi') = narrow(grid, C, C_err, Gs, Gs_err, z)` and the next bracket is `[lo', hi']`. If NOT Evaluated: the
bracket is unchanged and the round's moment fields, `D`, `A`, `B` are `null` [F11].

**`navigator.estimate.narrow(grid, C, C_err, Gs, Gs_err, z) -> Narrowed`** (pure; `lo0 = grid[0]`, `hi0 = grid[-1]` [F8]):
- **A (fluctuation peak):** `j = argmax(C)` (first index on ties). `A = { i : C[i] ≥ C[j] − z·sqrt(C_err[i]² + C_err[j]²) }`.
- **B (block-ratio crossing, levels 0 and 1):** `D[i] = Gs[i][1] − Gs[i][0]`, `σ[i] = sqrt(Gs_err[i][1]² + Gs_err[i][0]²)`.
  `B = { i : |D[i]| ≤ z·σ[i] } ∪ { i, i+1 : D[i]·D[i+1] < 0 }`.
- `U = A ∪ B`, `Δ = (hi0−lo0)/(m−1)`. `lo' = max(lo0, grid[min U] − Δ)`, `hi' = min(hi0, grid[max U] + Δ)`.
  U is never empty (A always holds j), so `lo0 ≤ lo' < hi' ≤ hi0`: the bracket is nested by construction.
- Returns `Narrowed(A: tuple[int], B: tuple[int], lo: float, hi: float)` (a NamedTuple), A and B sorted ascending, plain
  Python `int`/`float` (no numpy scalars).

**Report (stdout, one JSON line):**
`{"kind": "Located"|"REFUSE", "reason": null|"floor"|"budget", "bracket": [lo,hi]|null, "A_hull": [g,g]|null,
"B_hull": [g,g]|null, "agree": bool|null, "rounds": [ROUND…]}` where ROUND =
`{"round", "grid", "C", "C_err", "Gs", "Gs_err", "D", "A", "B", "lo", "hi", "index", "evaluated"}` (`lo`/`hi` = the bracket
AFTER the round; `index` = exp after the round; `D` the m-list Gs[i][1]−Gs[i][0]) [F4].
For Located: `bracket` = the final `[lo, hi]`; `A_hull`/`B_hull` = `[grid[min], grid[max]]` of the final round's A/B
(`B_hull = null` when B is empty); `agree` = the two closed hulls intersect (touching counts) — `false` when B is empty.
For REFUSE: `bracket`, `A_hull`, `B_hull`, `agree` are `null`.

## Orchestrator `python -m environment.run_blind --env E --at A --needle R --score F`
- Parse the env file with the frozen `environment.config` env parser (it supplies `system`, `port`, `run_dir_root`).
  Unparseable ⇒ exit 2, nothing written (no run dir is nameable).
- `run_id` = Stage-1's recipe (`environment/run.py:run_id`: sha256 over the canonical JSON, same truncation) applied to
  {at-blind raw, env raw minus `run_dir_root`/`port`, needle raw, score raw, tau raw, vendor raw}; the `score` entry is the
  only addition. `run_dir = expanduser(run_dir_root)/run_id`.
- Parse at-blind (strict), tau, recover.toml (`parse_recover_cfg`) and score (below). Any fault ⇒
  `<run_dir>/refused.json` = `{"kind":"RefusedToStart","field":<str>,"parse":"B"}`, exit 2, and no server is started.
- Write `config.json`; launch `environment.blind_server` (stderr → `server.log`); wait for the port with Stage-1's
  `wait_ready`; run the needle as a SUBPROCESS: `python -m navigator.recover --needle R --port <env port>` (cwd repo root,
  no run-dir argument, no environment variable naming it); SIGTERM/reap the server (it writes perf.json on exit).
- Needle exit 1, or the server never bound ⇒ exit 1 (InfrastructureFailure, stderr), nothing scored.
  Needle exit 2 ⇒ `refused.json` `{"kind":"RefusedToStart","field":<from the needle's stderr line>,"parse":<A|B>}`, exit 2.
  Needle exit 0 but stdout is not one JSON object with a valid `kind` ⇒ `refused.json` field `needle_stdout`, exit 2.
  Otherwise score, write `verdict.json`, exit 0.

## Scoring (inside `run_blind` — the needle never sees this)
`score-1525.toml` (STRICT, declared before data): `a` float ≥ 0 (finite-size allowance, K-units), `w_max` float > 0 [F19].
Truth `K_c` from `<run_dir>/edge.json`. With `[lo, hi]` = the report's bracket:
`contains = (lo − a ≤ K_c ≤ hi + a)`, `width = hi − lo`, `narrow_enough = (width ≤ w_max)` [F6]. Total cell map:
- `HIT` iff kind = Located and contains and narrow_enough;
- `MISS` iff kind = Located and not HIT;
- `REFUSED` iff kind = REFUSE.
`verdict.json` = the needle report + `truth_K_c`, `a`, `w_max`, `contains`, `width`, `narrow_enough` (all three `null`
for REFUSE), `cell`, `run_id`, `plan: "1525"`.
