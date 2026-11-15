# The needle view — reader and page contract (plan 1529)

**Base:** Stage 3a (`5b519d5`). Every Stage-1/2/3a file is FROZEN and untouched, and this package imports none of
them. `needleview/` is a NEW top-level package: a command-line tool that turns reports of `contract/SCHEMA-1525.md`
into ONE static HTML page. It draws only what the needle was told and what it decided. It never draws the System's
model. The truth may appear only as an overlay, only on request, and only from a scored verdict file.

## Modules and signatures
| module | holds |
|---|---|
| `needleview/__init__.py` | empty |
| `needleview/report.py` | the eight types; `parse(label, text, truth) -> Run \| Unreadable` (pure: no file is opened here) |
| `needleview/scale.py` | `Affine \| Flat`, the two scale forms |
| `needleview/draw.py` | `render(items) -> str` (pure): the whole page from a list of `Run \| Unreadable` |
| `needleview/__main__.py` | `load(label, path, truth) -> Run \| Unreadable` and `main(argv=None) -> int`. The ONLY module that opens a file |

`load(label, path, truth)` reads `path` as UTF-8 text and returns `parse(label, text, truth)`. A path that cannot be
read (missing, a directory, bytes that are not UTF-8) gives `Unreadable(label, why)`. No exception leaves `load` or `parse`.

## The types (frozen dataclasses, fields in this order; every list arrives as a tuple)
```
Run          (label: str, report: Located | Floor | Budget, overlay: Overlay | None)
Unreadable   (label: str, why: str)                      # why is never empty
Located      (rounds: tuple[Evaluated, ...], agree: bool)             # >= 1 round, all Evaluated
Floor        ()                                                       # REFUSE, reason floor: the loop was never entered
Budget       (rounds: tuple[Evaluated | NotEvaluated, ...])           # REFUSE, reason budget: >= 1 NotEvaluated
Evaluated    (round, grid, C, C_err, Gs, Gs_err, D, A, B, lo, hi, index)
NotEvaluated (round, grid, lo, hi, index)
Overlay      (truth_K_c: float, a: float, w_max: float, contains: bool | None, cell: str)
```
A **float** below is a Python `float` that is finite. A JSON integer is NOT a float, and a bool is never a number.
An **int** is a Python `int` that is not a bool. `Gs`, `Gs_err` are tuples of tuples.

## `parse` — a report is read into a type or refused (parse, don't validate)
REPORT keys (7): `kind, reason, bracket, A_hull, B_hull, agree, rounds`.
VERDICT keys (9): `truth_K_c, a, w_max, contains, width, narrow_enough, cell, run_id, plan`.
ROUND keys (13): `round, grid, C, C_err, Gs, Gs_err, D, A, B, lo, hi, index, evaluated`.

`parse` returns `Unreadable(label, why)` unless ALL of the following hold:
1. `text` is JSON and its value is an object.
2. All seven REPORT keys are present, and every other key is a VERDICT key. Any other key ⇒ `why` contains
   `unknown key` and the key's name.
3. `kind` is `"Located"` or `"REFUSE"`. Any other kind ⇒ `why` contains the kind's name (a later schema's report is
   refused by name, never mis-drawn).
4. `rounds` is a list, and each element is an object with exactly the 13 ROUND keys, where:
   - `round` is the int position in the list, counted from 1; `index` is an int ≥ 0; `evaluated` is a bool;
   - `grid` is a list of m ≥ 2 floats, strictly increasing;
   - `lo`, `hi` are floats with `grid[0] ≤ lo < hi ≤ grid[-1]`;
   - if `evaluated`: `C`, `C_err`, `D` are lists of m floats; `Gs`, `Gs_err` are lists of m lists of nlev floats, one
     nlev ≥ 2 for the whole round; every `C_err` and `Gs_err` value is ≥ 0; `A` and `B` are lists of ints, strictly
     increasing, inside 0..m−1; `A` is not empty;
   - if not `evaluated`: `C, C_err, Gs, Gs_err, D, A, B` are all `null`.
5. For `Located`: `reason` is `null`; there is at least one round and every round is evaluated; `bracket` is a list
   of two floats equal to the last round's `[lo, hi]`; `A_hull` is a list of two floats `[x, y]` with x ≤ y; `B_hull`
   is `null` or such a list; `agree` is a bool.
6. For `REFUSE`: `bracket`, `A_hull`, `B_hull`, `agree` are all `null`, and either `reason` is `"floor"` with
   `rounds == []` (⇒ `Floor()`), or `reason` is `"budget"` with at least one round, at least one of them not
   evaluated (⇒ `Budget(rounds)`).
7. The overlay rule below does not refuse.

**The overlay.** With `truth` false the VERDICT values are never read (only the key names, rule 2), and `overlay`
is `None`. With `truth` true:
- no VERDICT key present ⇒ `overlay` is `None` (a bare report: the truth is absent, not zero);
- otherwise all nine must be present and well-formed: `truth_K_c` float; `a` float ≥ 0; `w_max` float > 0; `cell` one
  of `HIT`, `MISS`, `REFUSED`; `run_id` and `plan` strings; `cell == "REFUSED"` exactly when the report is a
  `REFUSE`, and then `contains`, `width`, `narrow_enough` are `null`; otherwise `contains` and `narrow_enough` are
  bools and `width` a float. Then `overlay = Overlay(truth_K_c, a, w_max, contains, cell)`.
- anything else ⇒ `Unreadable` whose `why` contains `truth`. A malformed truth is shown as a refusal; it never
  silently becomes `None`.

`parse` holds a tuple of readers with one entry (this one). A later report schema adds a reader in a new file.

## The page — `render(items)`
The page is a function of `items` alone: no clock, no randomness, no environment. Text is escaped with
`html.escape(s, quote=True)` wherever a label or a `why` is written. Every number in a `data-*` attribute and in a
table cell is `repr(float)`. Every pixel coordinate is `format(x, ".2f")`. Every element is closed
(`<circle … />` or an end tag).

**Whole page.** Starts with `<!doctype html>`. `<title>Needle view</title>`. Contains none of these substrings, in
any letter case: `<script`, `http:`, `https:`, `<link`, `<img`, `<iframe`, `@import`, `url(`, `<path`.
(Draw with `line`, `polyline`, `polygon`, `circle`, `rect`, `text`. No SVG path data is written anywhere.)

**Order.** First the overview (`svg.widths`, then `table.runs`), then one section per item, in the order given.

**Sections.** For item i (from 0): `<section class="run" data-run="i" data-label="…" data-kind="K" data-reason="R">`
with K, R = `Located`, `` (empty) · `REFUSE`, `floor` · `REFUSE`, `budget` · `Unreadable`, `` (empty).
The number of sections ALWAYS equals the number of items.
- `Unreadable`: one `<p class="why">` whose text is the `why`; no `svg.round`.
- `Floor`, `Budget`: one `<p class="refuse" data-reason="floor|budget">`. `Floor` has no `svg.round`.

**A round.** One `<svg class="round" data-round data-evaluated="true|false" data-x0 data-x1 data-lo data-hi>` per
round, inside its section, with x0 = `grid[0]`, x1 = `grid[-1]`, and lo, hi the bracket after the round.
Coordinates are in a 300 × 295 user space. Each round has its own x scale:

    x(K) = 40 + (K − x0) / (x1 − x0) · 240

and three plots, each with a top T and a height H, on the y scale

    y(v) = T + H − (v − v_lo) / (v_hi − v_lo) · H        when v_hi > v_lo   (Affine)
    y(v) = T + H / 2                                     when v_hi = v_lo   (Flat)

| plot | T | H | v_lo | v_hi |
|---|---|---|---|---|
| C | 10 | 90 | min over i of `C[i] − C_err[i]` | max over i of `C[i] + C_err[i]` |
| D | 115 | 70 | min(0, min over i of `D[i] − sig[i]`) | max(0, max over i of `D[i] + sig[i]`) |
| Gs | 200 | 70 | min over i, l of `Gs[i][l]` | max over i, l of `Gs[i][l]` |

with `sig[i] = sqrt(Gs_err[i][1]² + Gs_err[i][0]²)`, computed by the viewer from reported fields; the page says so in
words. Nothing is added to a zero span and no value is moved into range: `Flat` is the second form of the scale.

Elements of EVERY round:
- m × `<line class="tick" data-k x1 x2>` with `x1 = x2 = x(grid[i])`.

Elements of an EVALUATED round (m = grid length, nlev = levels):
- m × `<circle class="c" data-i data-k data-v data-err cx cy>`: `cx = x(grid[i])`, `cy = y_C(C[i])`; the class
  `in-A` is added exactly when i ∈ A.
- m × `<line class="c-err" data-i x1 x2 y1 y2>`: `x1 = x2 = x(grid[i])`, `y1 = y_C(C[i] + C_err[i])`, `y2 = y_C(C[i] − C_err[i])`.
- m × `<circle class="d" data-i data-k data-v data-sig cx cy>`: `cy = y_D(D[i])`; the class `in-B` exactly when i ∈ B.
- m × `<line class="d-err" data-i x1 x2 y1 y2>`: `y1 = y_D(D[i] + sig[i])`, `y2 = y_D(D[i] − sig[i])`.
- 1 × `<line class="zero" x1 x2 y1 y2>`: `x1 = 40.00`, `x2 = 280.00`, `y1 = y2 = y_D(0)`.
- m·nlev × `<circle class="g" data-level data-i data-k data-v data-err cx cy>`: `cy = y_Gs(Gs[i][level])`.
- 1 × `<rect class="next" data-lo data-hi x width>`: `x = x(lo)`, `width = x(hi) − x(lo)`.

An UNEVALUATED round has the ticks, no circle, and one `<text class="not-evaluated">`.

**Overlay** (only for a `Run` whose `overlay` is not `None`):
- in each of its `svg.round`, exactly one of `<line class="truth" data-k x1 x2>` with `x1 = x2 = x(truth_K_c)`, when
  x0 ≤ truth_K_c ≤ x1; or `<polygon class="truth-off" data-side="lo|hi">`, `lo` when truth_K_c < x0, else `hi`;
- in its section, one `<span class="cell" data-cell="HIT|MISS|REFUSED">`.
When no item has an overlay, none of the classes `truth`, `truth-off`, `cell`, `overlay` appears on any element.

**Overview.**
- `<svg class="widths">` with one `<polyline class="width-path" data-run="i" data-widths="…">` per `Located` or
  `Budget` item; `data-widths` is the comma-joined `repr` of `[grid[-1] − grid[0] of round 1]` followed by
  `hi − lo` of each round. Its geometry is free (a log scale is total here: every width is > 0 by the types).
- `<table class="runs">`: header cells `<th data-col="…">`, and in `<tbody>` one `<tr data-run="i">` per item with one
  `<td data-col="…">` per column. Columns, in order: `label, kind, reason, lo, hi, width, agree`. Cell text
  (compared after `strip()`); an absent value is the single character `—` (U+2014):

| item | label | kind | reason | lo, hi | width | agree |
|---|---|---|---|---|---|---|
| `Located` | the label | `Located` | `—` | `repr` of the last round's lo, hi | `repr(hi − lo)` | `yes` / `no` |
| `Floor` | the label | `REFUSE` | `floor` | `—` | `—` | `—` |
| `Budget` | the label | `REFUSE` | `budget` | `—` | `—` | `—` |
| `Unreadable` | the label | `Unreadable` | `—` | `—` | `—` | `—` |

  If at least one item has an overlay, four more columns follow, their header cells carrying the class `overlay`:
  `truth_K_c` (`repr`), `a` (`repr`), `contains` (`yes` / `no` / `—` when `null`), `cell`. A row with no overlay has
  `—` in all four. (`a` is shown so that a HIT that contains the truth only through the allowance is explained.)

**Look (not tested, required).** Colours are CSS custom properties on `:root`, redefined for dark under
`@media (prefers-color-scheme: dark)` guarded by `:root:not([data-theme="light"])` and again under
`:root[data-theme="dark"]`; `body` has an explicit background; the layout works at phone width with no sideways page
scroll. A and B are told apart by shape or fill as well as colour. Each mark has a `<title>` child with its numbers.
Axis labels are the numbers themselves and the report's own field names. No model name appears.

## The CLI
`python -m needleview --out OUT [--truth] ITEM [ITEM …]`
- An ITEM with no `=` is a PATH, and its label is the PATH as typed. An ITEM with `=` is `LABEL=PATH`, split at the
  FIRST `=`; so a path that contains `=` must be given with a label. An empty LABEL or PATH is a usage error.
- It writes `render([load(label, path, truth) for each ITEM])`, encoded as UTF-8, to OUT, and exits 0. Unreadable
  inputs are drawn on the page; they are not errors.
- Exit 2, with a message on stderr and nothing written: a usage error (no ITEM, no `--out`, an empty LABEL or PATH),
  or OUT cannot be written. There is no exit 1.

## Blindness, by construction
- Every `needleview/*.py` imports only from: `argparse, json, math, sys, html, dataclasses, typing, needleview`.
  No relative import. No `__import__`, `exec`, `eval`.
- The name `open` is called only in `needleview/__main__.py`.
- No string constant equals `where`, and none contains (case-sensitive substring; docstrings and f-string pieces
  included): `self_dual`, `lattice`, `system-instantiated`, `plugins`, `at-blind`, `edge.json`, `config.json`,
  `perf.json`, `L4`, `Ashkin`, `Potts`, `Ising`. Write such words in `#` comments only.
- The truth reaches `render` only through `Run.overlay`, which only `parse(…, truth=True)` can fill.
