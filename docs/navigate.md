# `cc navigate` — stored-map mode (UNTESTED)

Plan 1114 step 0: the design and the predictions, committed before any navigate code exists and before the golden map is read by it.

**Status: UNTESTED.** `cc navigate` ships so that its capacity starts being tested. No transcript it prints has been scored
against a known transition; none is evidence of a located transition. Every output (trace, terminal and refusal) carries that
warning in its first line.

## Input: a declared stored map (no new format)

A stored map is an existing CC input whose `[interval] method = "chains"` (cc.toml `alphabets.interval_method`; plan 0937): every
`[[data.files]]` block names its `chain`, and each (point, size, start) cell holds `m` independent chains. Nothing new is declared.

- **nodes** = `[axes] point`, in the declared order (the walk's index order).
- **the size pair** = big 81, small 27: the pair navigator v2 declares (toolset `studies/NAV-AT/nav2.py` lines 48 and 99: `LIDX = {27: 0, 81: 1}`,
  `pin = {81: pinned(a), 27: pinned(b)}`).
- **the recorded series** of one chain = the input's declared `arrays.G` key at that block's declared `level`. On the AT inputs this is the final
  9 x 9 block level of each size, the level nav2 reads (`g1(levels(s, NLEV[L])[-1])`, nav2 line 141).
- **the start** = `[axes] main_start` (nav2 reads one start per map).
- **m, alpha** = the input's `[interval] m` and `alpha`; **r** = `readout.rank(m, alpha)` (CC's existing port of nav2's `rank`, nav2 lines 61-63).
  The declared `[interval] r` is printed beside it.

A input whose method is `block`, `iid` or `gamma` has one chain per cell: it is not a stored map. `cc navigate` refuses it with a typed
refusal `NOT_A_STORED_MAP` (a value printed under the UNTESTED line, exit status 1). An input id that is not a directory under `inputs/` is the
same refusal.

**Changed in step 1 (built after this section was first committed).** The step-0 text said the deciding table was keyed on the interval method
alone. Running the reader over every `chains` input showed that is not enough: some `chains` inputs carry no `arrays.G` on every file (they
declare `GL` or `Q` only), and one is `npy-v1` or `snapshots-v1`, not `npz-v1`. So the declared shape of a stored map is the triple
(`[interval] method`, `[data] format`, `arrays.G` on every file) = (`chains`, `npz-v1`, yes). The table maps that one triple to the reader;
every other triple is the refusal, and the refusal prints the input's own triple beside the declared one. An `arrays.G` with no `level`
names a one-level series (column 0).

A declared chain file that is not on disk is not read: the node simply holds fewer chains. Navigator v2's own eligibility rule then
reads that node `NOT_ESTABLISHED (INSUFFICIENT_REPLICATES)` (nav2 lines 18, 104-110) — a value, never an exception.

## The reading at one node: navigator v2, unchanged

Ported from nav2.py lines 81-110 with no new number: `d_k = mean(a_k) - mean(b_k)` over chains k < m (a = L 81, b = L 27); interval
`[d_(r), d_(m+1-r)]` (order statistics); sign cell = `sign.sign(lo, hi, EPS)` with EPS 0.01 (nav.py line 19, `[NAV-AT-N0]` needle); pinned
channel per size = NONE / MIXED / PINNED (a chain is pinned iff every recorded sample equals BOUND 1.0; nav2 lines 88-91); side = ORD when the
L 81 channel is PINNED, else the frozen `[P2] side_table` of the cell (nav2 line 100). Fewer than m chains at either size: NOT_ESTABLISHED.

## The walk: nav.py's N0 bisection, with the UNRES defect removed

The walk is the N0 rule of `studies/NAV-AT/nav.py acquire` (lines 38-52): read the two end nodes; unless the first reads DIS and the last
reads ORD the walk REFUSES (the map does not span a crossing in its declared order); otherwise bisect on node indices until a node stops
the walk or the bracket is one step wide (BRACKET).

**The defect (REGISTRY T1, "nav.py still maps UNRES->MID").** nav.py moves on the SIDE (`MOVE = {"DIS": "lo", "ORD": "hi", "MID": "stop"}`,
line 18), and its side comes from the `[P2] side_table`, which sends the cell UNRES to MID (`SIDE`, line 15; table in the toolset m.toml
`[P2] side_table`, "UNRES MID"). So a node whose interval straddles 0 and a margin edge — a node the needle cannot read — STOPS the walk at
lines 49-50 and is returned as `STOP ... mid_j`, i.e. as a located crossing. nav2 keeps the same side table (line 100, `SIDE[s]`); what nav2
adds is that its Reading carries the cell itself (line 73, "UNRES is a value"). nav2 has no walk.

**Here the walk moves on the cell, not on the side.** `MOVE` is a total table over the eight sign cells plus the NOT_ESTABLISHED reading:

| cell | move | outcome |
|---|---|---|
| SIG-, NEG | lo (the node is the new low end) | continue |
| POS, SIG+ | hi (the node is the new high end) | continue |
| SLOW-, ZERO!, SLOW+ | stop | STOP at the node (resolved inside the margin: nav.py's MID stop) |
| UNRES | unresolved | UNRESOLVED at the node: no location is claimed |
| (NOT_ESTABLISHED) | refuse | NOT_ESTABLISHED at the node |

and the L 81 sink overrides the cell exactly as nav2's side does: PINNED at L 81 moves hi. For every cell except UNRES this is nav.py's
`MOVE[SIDE[cell]]`; the one change is UNRES, which nav.py turned into a STOP. UNRESOLVED names the stage: the stored map holds m chains and the
next stage of the T6-B ladder (m 40) is not stored, so the walk cannot escalate; it ends and says so. Nothing here is a guard: every
terminal is a row of the table, the outcome alphabet is BRACKET | STOP | UNRESOLVED | NOT_ESTABLISHED | REFUSE, and each is printed as
a value.

## The output

Plain text, the UNTESTED warning on line 1. Then: the map (id, observable, size pair, m, r, alpha, EPS, start); every declared node with the
number of chain files present at each size (the whole stored map, read or not — so a node removed from the map changes the transcript even
when the walk never visits it); one line per node read, in read order (node, index, side, cell, median d, interval, pinned L 81 / L 27, move);
the outcome line (outcome, bracket or node); and the T23 line.

## The T23 access log

Every chain file the walk reads goes through one loader that appends a JSON line to an append-only access log (O_APPEND) BEFORE the bytes are
used: `{t_ns, partition, path, sha256, size, argv, pid, git_head, route: "loader"}` (the record of the toolset's `studies/TAX-B1b/t23.py`
R2). `path` is written relative to the declared data root (`<data-root>/...`), never as a location on this machine; `argv` omits the
program path. Default log: `results/navigate/<input>.access.jsonl` (git-ignored), or `--access-log PATH`. The transcript names the log, the
number of reads appended, and the nodes read. As in T23, reads outside the loader (a shell, another process, another copy of the bytes) are
not logged; the transcript says so.

## The golden map and the predictions

**Map: `b7-at-line-ch`** — the AT self-dual line set the Detector already ships (5 nodes L4 = 0.0, 0.07, 0.14, 0.21, 0.2747 on the exact
self-dual line; chains method, m 10, alpha 0.021484375; sizes 27/81/243; random start; G = g1 of p = sigma tau). Every node of this map is ON
the critical line; the map does not cross the line. The observable is p = sigma tau, not the sigma spins nav2 was built on; disclosed, not
changed (the input's declaration is what the map reader reads).

Predictions (written before `cc navigate` exists; nothing about these chains was read for them):

1. Line 1 is the UNTESTED warning.
2. The map line reads m 10, r 2 (rank(10, 0.021484375) = 2 = the declared r), pair L 81 / L 27, EPS 0.01.
3. The node list shows all 5 nodes with 10 chains at L 81 and 10 at L 27.
4. The walk reads exactly the two end nodes, 0.0 and 0.2747 (20 + 20 = 40 chain files appended to the access log).
5. Neither end reads DIS at 0.0 and ORD at 0.2747: on a critical line the matched difference at final size 9 is small. Predicted cells: one of
   ZERO! / SLOW- / SLOW+ / UNRES at both ends (side MID). Pinned channels NONE at both sizes at both ends.
6. Outcome: **REFUSE** (the ends are not DIS ... ORD). This is the robust prediction: any end pair other than (DIS at 0.0, ORD at 0.2747)
   refuses, whatever the cells are; prediction 5's cells are the risky part (a resolved finite-size drift beyond 0.01 would read NEG/POS or SIG±
   at an end and still REFUSE).

Seen-red (step 2): the same map with one node removed (node 0.2747 dropped from `axes.point`, `obtained` and its `[[data.files]]`) must not pass
silently: its node list loses a node and its walk reads 0.21 as the last end, so the transcript differs from the golden.

## Family mode (plan 1176 phase D): `bin/cc navigate family <id>` and `bin/cc navigate score <id> <checkpoints.toml>`

**The navigator is vendored, frozen.** `cc/linenav.py` is a byte-for-byte copy of the toolset's `tools/linenav.py`, frozen at v2.1-T
(toolset `studies/LINENAV/LINENAV-FROZEN.md`, plan 1113): cc/linenav.py sha256 `560e2712b83e0966e2c95113ff872f82999b35303a0d87197cc40c5f905e0ab2`.
It is never edited here; `tests/test_navfamily.py` D2 checks the sha. Family mode (`cc/navfamily.py`) is an adapter over it.

**What it walks.** A family is an intake declaration `declarations/<id>/intake.toml` that declares `[plane]` and `[suspect]` (FORMAT v14) and
whose intake run refuses at no stage. Its plane is grid cells, curve rank x sample rank (`cc/intake_suspect.py`); the navigator's plane is
(0, 0) .. (curves - 1, n_max - 1) in grid mode, with linenav's grid PARAMS untouched (w_c 5 cells, budget 400). The side oracle is the R1
feature projection (`cc/intake_feature.py`, POLICY `[feature_projection.FEATURE_ARGMAX_FAST]`), built over the SAME plane as the suspect
(the sliced curves when `[plane.slice]` is declared), answering in `linenav.Side`, its evidence `linenav.FiniteStored("<id>:<seal hash>")`.
stdout is value-free: the verdict, the terminals and the traced polyline in cells. `results/navigate/<id>.toml` holds the same polyline and,
per point, the measured slow and fast values of its neighbouring cells (a bracket of measured values, never a value between them).

**Refusals** are typed values, `REFUSED <code>: ...`, exit status 1: NO_DECLARATION, INTAKE_REFUSED_AT (the first refused stage), the suspect's
(SUSPECT_ABSENT: no default line exists, ...), PROJECTION_UNDECLARED, and for score CHECKPOINTS_INSIDE_DECLARATIONS, CHECKPOINTS_UNREADABLE.

**Score and the hold-out.** `score` reads a checkpoints file `points = [[slow, fast], ...]` that must live outside `declarations/`; each point is
converted by the suspect's rules (exact slow, in-span nearest sample) and scored by its distance in cells to the traced polyline; FOLLOWED needs
every checkpoint within w_c (5 cells). `family` takes no checkpoints argument and has no code path to them. Every file each command opens is
appended to its own access log (an audit hook on `open`): `results/navigate/<id>.access.jsonl` (family) and
`results/navigate/<id>.score.access.jsonl` (score). The family log never names the checkpoints (D5).
