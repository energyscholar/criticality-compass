# Stage-2 wire contract — the batched point probe (plan 1518)

**Base:** Stage-1 point protocol (plan 1511, `8cdadc5`), which this EXTENDS by one op. Nothing in Stage-1
is removed or changed. One JSON object per line over the loopback TCP socket.

## Stage-1 ops (unchanged — read `environment/wire.py`, `navigator/reader.py`)
`declare`→`declared{knobs_K,ordered_side,L,tau,k,index_unit,index_kind,observable}` · `where`→`edge{K_c,w,index}`
· `set{K}`→`ok{index}` · `step{n}`→`ok{index}` · `sense`→`obs{E2:float,index}`. Unknown/malformed ⇒
`nev{index}` (a value). `index` = sweeps so far; the needle accepts a reply only if op AND index match
(`reader.judge`).

## The ONE new op — `probe` (the whole of Stage-2)
A needle that touches the manifold at m points (the default is the **2-point bracket** K_c−u, K_c+u) paid
Stage-1 `3·m` round-trips (set+step+sense per point). `probe` does all m in ONE call:
```json
→ {"op":"probe", "Ks":[K_1, …, K_m], "n":64}
← {"op":"obs",   "E2":[e_1, …, e_m], "index":I}
```
- `Ks`: a non-empty list of m reals (m=1 is exactly Stage-1). `n`: int ≥1.
- The world does, for each i in order: `set(K_i)`, `step(n)`, `sense` → e_i. It is the Stage-1 machinery
  looped — **a stub over the same fixed system**, no per-point physics variation. `E2` is **exactly m
  floats**, parallel to `Ks`. `index` += `m·n` (every point steps n).
- **m = 1 ≡ Stage-1:** `probe{Ks:[K],n}` ⇒ `E2:[e]` equals Stage-1 `set{K}+step{n}+sense` from the same
  burned state. This is the acceptance equivalence.
- **Totality, no clamp:** if ANY `K_i` is rejected by `set` (outside `knobs_K`), the whole call is
  `nev{index}` with the index UNCHANGED and NO point stepped (structure-not-control: out-of-bounds is
  NotEvaluated, never clipped). Malformed `Ks`/`n` ⇒ `nev` likewise.
- The reply op stays `obs`; `E2` being a list is how a batched reply is told from a single `sense`. The
  needle's batched reader is SEPARATE from the scalar `parse_obs` (unchanged for the Stage-1 path) and is
  **total**: it requires `len(E2) == m` (the count of `Ks` sent) and every element a float, else NotEvaluated.
  That length parity is the completeness guard — fewer answers than questions cannot pass. Ordering/no-drop is
  the index: the needle accepts a reply only if `index == exp + m·n`. Together they are the "ack + checksum",
  carried by the SHAPE of the reply, not an extra handshake (a digest would mask an off-by-one computed
  identically at both ends).

## What the slice-1 needle does — `margin-batched-v0` (a NEW structure)
Because `where` hands the needle K_c (oracle-ON), a 2-point bracket would not change the verdict — nothing to
localize that `where` does not already give. So slice 1 makes the SAME Stage-1 reading over FEWER calls, no
new verdict: declare, `where` (get K_c, w), then ONE `probe{Ks:[K_c+u], n}` (m = 1) per round instead of
set+step+sense (3 round-trips → 1). Verdict is Stage-1's: **LINE iff |K−K_c| ≤ w**. Stage-1's
`margin-constant-v0`, its 185 tests, and its golden are UNTOUCHED — `margin-batched-v0` is a new declared
version (structure-not-control). The wire carries m ≥ 2 for the deferred bracket needle; slice 1 uses m = 1.

## The live spec
The two `contract/test_*_conformance.py` files + this SCHEMA are the live spec. (An earlier
`advance`/`shape`/`burn_mode` design and its `golden/` + `scripted_server.py` doubles were fiction and have
been removed.)
