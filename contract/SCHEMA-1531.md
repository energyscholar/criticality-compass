# The needle player — stream, fragment and page contract (plan 1531)

**Base:** the needle view (`9901fae`, `contract/SCHEMA-1529.md`). Its five modules are FROZEN byte for byte, and
`test_b5` here pins their sha256. `needleview/player/` is a NEW package below it: a command-line tool that turns
reports of `contract/SCHEMA-1525.md` into ONE HTML page that shows ONE round of ONE run at a time, with selectors and
an animated step between rounds. It draws the Navigator View only (`data-view="navigator"`); other views get no
element here.

Three things are declared here that the needle view did not have:
1. **The stream.** The page is drawn from an append-only list of events, never from a report as a whole.
2. **The source.** Every drawn element says whether it shows what the needle measured and decided (`navigator`) or
   what only the System knows (`system`). An unknown System reads `UNKNOWN`: a declared value, never an empty cell.
3. **A script.** It shows, hides and interpolates elements that Python wrote. It computes no position.

## Modules and signatures
| module | holds |
|---|---|
| `needleview/player/__init__.py` | empty |
| `needleview/player/stream.py` | the seven types; `events(run, world, label, text, truth)`, `refused(run, world, label, why)`, `encode(stream)`. Pure |
| `needleview/player/frame.py` | `fragments(stream) -> tuple[str, ...]`: one HTML fragment per event. Pure |
| `needleview/player/assets.py` | two string constants: the style sheet and the script. No function |
| `needleview/player/page.py` | `render(stream) -> str`: the whole page. Pure |
| `needleview/player/__main__.py` | `load(run, world, label, path, truth)` and `main(argv=None) -> int`. The ONLY module that opens a file |

Exactly these six files. They import only from `argparse, json, math, sys, html, dataclasses, typing, needleview`
(so `needleview.report`, `needleview.scale`, `needleview.draw` and `needleview.player.*` are allowed).

## The stream
A **stream** is a tuple of events. A **run** is an int: the position of the input, from 0.

```
Unknown  ()                                                    # the System did not say
Known    (truth_K_c: float, a: float, w_max: float)            # what the System declares about itself
Scored   (cell: str, contains: bool | None)                    # what the score says about the outcome
RunStart (run, world: str, label: str, system: Known | Unknown)
RoundEv  (run, rnd: Evaluated | NotEvaluated)                  # the needle view's two round types, unchanged
Outcome  (run, kind, reason, bracket, A_hull, B_hull, agree, score: Scored | Unknown)
Refused  (run, why: str)                                       # the input could not be read as a report
```
Frozen dataclasses, fields in this order. `bracket`, `A_hull`, `B_hull` are a tuple of two floats or `None`.
`UNKNOWN = "UNKNOWN"` is a module constant of `stream.py`.

**`events(run, world, label, text, truth)`** returns the events of ONE input, as a tuple. It never raises. With
`item = needleview.report.parse(label, text, truth)`:
- `item` is `Unreadable` ⇒ `refused(run, world, label, item.why)`, which is
  `(RunStart(run, world, label, Unknown()), Refused(run, why))`.
- otherwise ⇒ `RunStart`, then one `RoundEv` per round in order (none for a floor refusal), then one `Outcome` whose
  six report fields are the report's own `kind, reason, bracket, A_hull, B_hull, agree`.
- **The System's part comes only from `item.overlay`.** `overlay is None` ⇒ `system = Unknown()` and
  `score = Unknown()`. Otherwise `system = Known(truth_K_c, a, w_max)` and `score = Scored(cell, contains)`.
  So with `truth` false every run is an unknown System; with `truth` true a bare report still is; and a malformed
  truth is a `Refused` whose `why` contains `truth` (the reader's rule, unchanged).
- `world` and `label` are carried as given. Nothing is inferred from them or from a path.

**`encode(stream)`** returns a list of JSON objects, one per event, with exactly these keys:
```
{"ev": "run",        "run": i, "world": w, "label": l, "system": "UNKNOWN" | {"truth_K_c", "a", "w_max"}}
{"ev": "round",      "run": i, "nav": {the 13 ROUND keys of SCHEMA-1529, values as in the report}}
{"ev": "outcome",    "run": i, "nav": {"kind", "reason", "bracket", "A_hull", "B_hull", "agree"}, "score": "UNKNOWN" | {"cell", "contains"}}
{"ev": "unreadable", "run": i, "why": why}
```
The outcome's `nav` keys are in the order written. An unevaluated round's seven moment keys are `null`.
**Round trip:** for every readable run, `dict(outcome["nav"], rounds=[each round's "nav"])` equals the report's seven
REPORT keys exactly. `nav` never holds a VERDICT key.

**The live seam (declared, not built).** A later live source appends events of these four kinds to a stream that is
still growing, possibly with several runs interleaved. Two properties, both tested here, are what make that possible
without changing `fragments`:
- **append-only:** `fragments(s[:k]) == fragments(s)[:k]` for every k. A later event never changes an earlier fragment.
- **per-run:** a fragment depends only on the earlier events of its own run.
Nothing else is built for it: no socket, no decoder, no insertion by the script. A live stage will have to reopen this
contract in three named places: the script gains an inlet (the text rules below forbid every one today), `render` gains
a way to add a section and its options for a new run, and a System that becomes known after its `RunStart` needs a new
event (under append-only, `RunStart.system` cannot change).

**The domain.** Per run, a stream holds a prefix of `RunStart, RoundEv*, (Outcome | Refused)`, in that order. That is
what `events` and `refused` produce and what a live source will send. `fragments` is defined on such streams only; any
other stream is outside this contract and no behaviour is promised for it.

## The fragments — `fragments(stream)`
One string per event, each ONE element whose root carries `data-ev`, `data-run` and `data-source="navigator"`.
Text is escaped with `html.escape(s, quote=True)`. Numbers in `data-*` attributes and slots are `repr(float)`. Pixel
coordinates are `format(x, ".2f")`. Every element is closed.

### The two sources
- **Every element of a fragment, the root included, carries `data-source="navigator"` or `data-source="system"`.**
  No element outside a fragment carries `data-source`.
- `data-ev` is on a fragment's root and on no other element.
- These class names mean one source wherever they appear in a fragment. Navigator: `tick c c-err d d-err zero g next
  trail not-evaluated rnd body frame why`. System: `truth truth-off sys-unknown`. Use other names for anything else.
- A `navigator` element is never inside a `system` element. Whatever comes from `Known` or `Scored` is written only
  in `system` elements. So removing the `system` elements from a page drawn with the truth and from the same page
  drawn without it leaves the same elements, attribute for attribute (tested).
- A **zone** is `<div class="zone" data-source="S">` holding one `class="zone-name"` element whose text is exactly
  `NAVIGATOR` or `SYSTEM`.
- A **slot** is `<span class="slot" data-source="S" data-slot="NAME" data-state="STATE">TEXT</span>`. Its text (after
  `strip()`) is the value and nothing else; a caption goes in a sibling element.

| state | text | `data-v` |
|---|---|---|
| `value` | the value | the same text |
| `absent` | `—` (U+2014): the report holds `null` here | none |
| `unknown` | `UNKNOWN` | none |
| `not-reported` | `not reported (stage 2)` | none |

### `RunStart` → `<div class="head" data-ev="run" data-run="i">`
Two zones. NAVIGATOR: slot `belief`, state `not-reported` (what the needle believes it runs on; the 1525 report does
not say). SYSTEM: slots `truth_K_c`, `a`, `w_max`: `value` with `repr` under `Known`, else `unknown`.

### `RoundEv` → `<div class="round" data-ev="round" data-run="i" data-round="r" data-evaluated="true|false">`
- one `<button class="rnd" type="button" data-round="r">` whose text is `r`, NOT inside the body;
- one `<div class="body" hidden>` holding one `<svg class="frame" viewBox="0 0 300 320" data-round data-evaluated
  data-x0 data-x1 data-lo data-hi>` and one slot `verdict`, state `not-reported` (the needle's steering verdict).

**The frame** has exactly two `<g class="layer">` children, one per source, and every other element of the frame is
inside the layer of its own source.

*Navigator layer.* Every mark of SCHEMA-1529 "A round", with the same classes, the same `data-*` attributes and the
same geometry (x mapping `40 + (K − x0)/(x1 − x0) · 240`, the three plots, `Affine | Flat`): `line.tick`, `circle.c`
(+ `in-A`), `line.c-err`, `circle.d` (+ `in-B`), `line.d-err`, `line.zero`, `circle.g`, `rect.next`; an unevaluated
round has the ticks and one `text.not-evaluated`. The test compares them with `needleview.draw.render`, mark for mark.
No other `circle` is drawn in a frame.

*The trail*, also in the navigator layer: with `g0, g1` the first and last grid point of the run's ROUND 1, frame r
holds r + 1 `<rect class="trail" data-j data-lo data-hi x y width height>`, j = 0 … r:
- j = 0 is the first grid: `lo, hi = g0, g1`. j ≥ 1 is the bracket after round j: that round's `lo, hi`.
- `x = xg(lo)`, `width = xg(hi) − xg(lo)`, with `xg(K) = 40 + (K − g0)/(g1 − g0) · 240`; `y = 298.00`, `height = 14.00`.
- the class `now` is on j = r and on no other.
A bracket outside the first grid is drawn where `xg` puts it; nothing is moved into range.

*Keys.* Every mark that can move carries a `data-key`, unique inside its frame: `tick-i`, `c-i`, `cerr-i`, `d-i`,
`derr-i`, `g-level-i`, `zero`, `next`, `trail-j`, `truth` (i = `data-i`, or the grid position for a tick). No other
element of a frame carries `data-key`.

*System layer.* Exactly one mark:
- under `Known`: `<line class="truth" data-key="truth" data-k x1 x2>` with `x1 = x2 = x(truth_K_c)` when
  x0 ≤ truth_K_c ≤ x1, else `<polygon class="truth-off" data-side="lo|hi">` (as SCHEMA-1529 "Overlay");
- under `Unknown`: `<text class="sys-unknown">` whose text contains `UNKNOWN`.

### `Outcome` → `<div class="outcome" data-ev="outcome" data-run="i" data-kind="Located|REFUSE" data-reason="floor|budget|">`
Two zones. NAVIGATOR slots, `value` or `absent`:

| slot | text when present |
|---|---|
| `kind` | `Located` / `REFUSE` |
| `reason` | `floor` / `budget` |
| `lo`, `hi` | `repr` of `bracket[0]`, `bracket[1]` |
| `width` | `repr(bracket[1] − bracket[0])` |
| `agree` | `yes` / `no` |
| `A_hull`, `B_hull` | `repr(x)`, a comma, a space, `repr(y)` |

SYSTEM slots `cell` and `contains` (`yes` / `no`): `unknown` under `Unknown`; under `Scored`, `value`, and `contains`
is `absent` when it is `null`.

### `Refused` → `<div class="unreadable" data-ev="unreadable" data-run="i">`
One `<p class="why">` whose text is the `why`. No slot.

## The page — `render(stream)`
A function of the stream alone: no clock, no randomness, no environment.

**Whole page.** Starts with `<!doctype html>`. `<title>Needle player</title>`. One `<style>`. One `<noscript>`.
Exactly two `<script>` elements, in this order: `<script type="application/json" id="stream">` and one with NO
attribute. Contains none of these substrings, in any letter case: `http:`, `https:`, `<link`, `<img`, `<iframe`,
`<object`, `<embed`, `@import`, `url(`, `<path`, `src=`, `srcdoc`, `xlink`.
With the truth off the page also holds none of `HIT`, `MISS`, `REFUSED` (case-sensitive, anywhere: style, script and
comments included).

**The data block** is `json.dumps(encode(stream))` with every `<` written as the six characters `\u003c`: the block holds no `<`, and
`json.loads` of its text equals `encode(stream)`.

**Layout.** `<div id="player" data-view="navigator" data-step-ms="…" data-play-ms="…">` (two positive integers, the
length of one step and the pause between steps when playing) holds, outside the stage:
- `<select id="pick-world" aria-label="world">`: one `<option value="W">W</option>` per distinct `world`, in order of
  first appearance. No other world is ever written.
- per world, in the same order, `<select class="pick-run" data-world="W" aria-label="run" hidden>`: one
  `<option value="i">label</option>` per run of that world, in stream order.
- `<button id="prev" aria-label="previous round">`, `<button id="play" aria-label="play">`,
  `<button id="next" aria-label="next round">`, `<input id="scrub" type="range" min="1" step="1" aria-label="round">`,
  `<output id="pos">`.
and ONE `<div id="stage">` holding, per `RunStart` in stream order,
`<section class="run" data-run="i" data-world="W" data-label="L" hidden>` whose content is exactly that run's
fragments, in stream order, and nothing else.

**One screen, as written.** Every `section.run` and every `div.body` carries `hidden`, and the style sheet holds
`[hidden]{display:none !important}`: nothing of any run shows until the script chooses one section and one body. The
only `svg` elements are the frames. Outside the stage, only `option` elements grow with the number of runs.

**Look (not tested, required).** Colours are CSS custom properties on `:root`, redefined for dark under
`@media (prefers-color-scheme: dark)` guarded by `:root:not([data-theme="light"])` and again under
`:root[data-theme="dark"]` (these three selectors and a `prefers-reduced-motion` rule ARE tested for presence);
`body` has an explicit background. The two zones look different without colour (a solid and a dashed border, and
their names). A and B are told apart by fill as well as colour. At 390 px wide nothing scrolls sideways. With one run
and one round chosen, the whole player fits two screens at most. No model name appears; the worlds' names are the
operator's labels.

## The script
It may: read `data-*` attributes and the two selectors; set or remove `hidden`; add or remove a class; clone a frame
Python wrote, and on the CLONE set a numeric attribute to a value between that mark's value in the frame on show and
its value in the next frame (marks paired by `data-key`); remove the clone. It reads the length of a step from
`data-step-ms` and `data-play-ms`. Under `prefers-reduced-motion: reduce` it steps at once.

Tested on its text:
- every number written in it is `0`, `1`, `2` or `3`, and no number is written in another base;
- it contains none of: `Math.`, `getBBox`, `getBoundingClientRect`, `getCTM`, `getScreenCTM`, `createElement`,
  `innerHTML`, `outerHTML`, `insertAdjacentHTML`, `document.write`, `eval(`, `Function(`, `fetch(`, `XMLHttpRequest`,
  `WebSocket`, `EventSource`, `import(`, `localStorage`, `sessionStorage`, `viewBox`, `offsetWidth`, `clientWidth`,
  `Date`, `random`, `JSON.parse`, `dataset`, `data-v`, `data-lo`, `data-hi`, `data-x0`, `data-x1`, `data-k"`, `data-k'`;
- it contains `data-key`, `prefers-reduced-motion`, `data-step-ms`, `data-play-ms`, `requestAnimationFrame`,
  `cloneNode`, `addEventListener`, `hidden`.

**Behaviour** (required; no JavaScript runs in the tests, the reviewer checks it in a browser at acceptance):
- On load: the first world is chosen, its run selector is the only one shown, its first run's section is the only one
  shown, and round 1's body is the only body shown. A run with no round (a floor refusal, an unreadable input) shows its
  section with no body; the scrubber is disabled and `#pos` says so.
- Changing the world shows that world's run selector and its selected run. Changing the run shows that run at round 1.
  Either stops play.
- `#prev`, `#next`, a `button.rnd` and `#scrub` go to a round of the run on show; out of range does nothing. After a
  step exactly one body of that run is shown, `#scrub` holds its number, `#pos` reads e.g. `round 2 of 5`, and the
  `button.rnd` of the round on show carries the class `on`.
- `#play` steps forward every `data-play-ms` and stops at the last round; pressed at the last round it starts again
  from round 1. Its text and `aria-pressed` say which state it is in.
- After any sequence of actions, `#stage` differs from the bytes Python wrote only in `hidden` attributes and classes:
  every clone is removed, and no coordinate of a frame Python wrote is ever changed.

Required, not tested (no JavaScript runs in the tests): the script keeps no list of runs, rounds or frames; at each
action it asks the document. It never changes an element Python wrote except `hidden`, a class, and the text and
state of the five controls.

## The CLI
`python -m needleview.player --out OUT [--truth] ITEM [ITEM …]`
- An ITEM is `WORLD/RUN=PATH`: split at the FIRST `=`, then the left part at its FIRST `/`. WORLD, RUN and PATH must
  each be non-empty, and no `WORLD/RUN` may be given twice. RUN is the run's label.
- It writes `render(stream)`, UTF-8, to OUT and exits 0, where `stream` is the concatenation of
  `load(i, world, label, path, truth)` over the ITEMs, i from 0. `load` reads `path` as UTF-8 and returns
  `events(i, world, label, text, truth)`; a path that cannot be read (missing, a directory, not UTF-8) gives
  `refused(i, world, label, why)`. No exception leaves `load`.
- Exit 2, with a message on stderr and nothing written: a usage error (no ITEM, no `--out`, an ITEM of another form,
  a repeated `WORLD/RUN`), or OUT cannot be written. There is no exit 1.

## Blindness
- The six modules import only from the list above. No relative import. No `__import__`, `exec`, `eval`. The name
  `open` is called only in `needleview/player/__main__.py`.
- No string constant equals `where`, and none contains (case-sensitive; docstrings, the style sheet and the script
  included): `self_dual`, `lattice`, `system-instantiated`, `plugins`, `at-blind`, `edge.json`, `config.json`,
  `perf.json`, `L4`, `Ashkin`, `Potts`, `Ising`, `W1`, `W2`, `W3`.
- `stream.py` takes the outcome's six fields from the report by name, in ONE expression over the six names of `nav`,
  and reads no other key of the parsed JSON. (`json.loads` holds the nine VERDICT values for a moment; `test_s4` and
  `test_b2` hold that none of them gets out.)
- A malformed truth read under `--truth` makes the whole input a `Refused`, rounds included (the reader's rule since
  plan 1529). "The navigator's part does not move" is a statement about inputs that parse under both truth values.
- The truth reaches a fragment only through `RunStart.system` and `Outcome.score`, which only
  `parse(…, truth=True)` on a scored file can fill.
- With the truth off, a file with all nine VERDICT values changed, and the same file with none of them, give the
  same bytes. With the truth on they do not: the check can fail.
