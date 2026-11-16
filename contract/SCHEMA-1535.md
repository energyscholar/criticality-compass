# The needle player v2 — pace, loop, play-all, full screen, plot names (plan 1535)

**Base:** the needle player (`d812e80`, `contract/SCHEMA-1531.md`). SCHEMA-1531 and its three tests are FROZEN and are
not edited: all 23 of its tests stay green. This file ADDS four controls and one label rule, and supersedes the five
sentences of SCHEMA-1531 named under "What this supersedes". Everything else in SCHEMA-1531 holds as written: the six
modules and their imports, the stream, the fragments, the two sources, the page rules, the script's text rules, the
CLI and blindness. No file is added: the change lives in `needleview/player/{assets,page,frame}.py`.

## The four new controls
Written by `render`, inside `#player`, outside `#stage`, each exactly once. None carries `data-source`. None is a
`select`, an `option` or an `svg` (SCHEMA-1531 counts those).

| control | bytes |
|---|---|
| pace | `<input id="speed" type="range" min="0.25" max="4" step="0.25" value="1" aria-label="speed" />` with the visible words `slow` before it and `fast` after it |
| loop | `<input id="loop" type="checkbox" aria-label="loop" />` inside a `<label>` whose text is `loop`. Not `checked` |
| play all | `<input id="all" type="checkbox" aria-label="play all" />` inside a `<label>` whose text is `play all`. Not `checked` |
| full screen | `<button id="full" type="button" aria-label="full screen" aria-pressed="false">` holding ONE empty `<span class="ico"></span>` and no text. The icon (four corner brackets) is drawn in the style sheet |

`data-step-ms` and `data-play-ms` keep their 1531 values and meaning: they are the lengths at pace 1.

**As written, the page behaves as plan 1531's**: pace 1, loop off, play-all off, not full screen.

## The plot names
In an evaluated frame, the three plot names are `<text class="plot-name" x="284.00" y="Y" data-source="navigator">`
with the texts `C`, `D`, `Gs` in this order and `Y` = `18.00`, `123.00`, `208.00` (the plot's top + 8). No
`text-anchor`. They sit right of the plot boxes, which end at x = 280, so they cannot touch the y-axis numbers, which
are end-anchored at x = 38. A frame holds no start-anchored `text` with x < 40. An unevaluated frame holds no
`plot-name`. Nothing else in a frame moves: every mark, number and key is as SCHEMA-1531 says.
(The needle view of plan 1529 keeps its own labels; its files are frozen and `test_b5` pins them.)

## The script — text
Every text rule of SCHEMA-1531 "The script" still holds (numbers `0 1 2 3` only; the forbidden list; the required
list). In addition:
- it contains `requestFullscreen`, `exitFullscreen`, `fullscreenElement`, `fullscreenchange`, `keydown`, `Escape`,
  `fs-on`, and a `getElementById` call for each of `speed`, `loop`, `all`, `full`;
- it contains none of `.style`, `setTimeout`, `setInterval`, `selected=`, `scrollTo`, `scrollIntoView`.
So the pace is read from `#speed` (a value Python wrote the range of), never written as a number in the script; full
screen is a class, never a style the script sets; and time still comes only from `requestAnimationFrame`.

The style sheet contains `#player.fs-on` with `position:fixed`, and `:root.fs-on`.

## The script — behaviour (required; checked by the Auditor in a browser, no JavaScript runs in the tests)
Everything in SCHEMA-1531 "Behaviour" holds when the four new controls are untouched. With them:

- **Pace.** With `s` = the value of `#speed`: a step lasts `data-step-ms / s` and play waits `data-play-ms / s`
  between steps. A change takes effect at once, also while playing, and does not stop play. Under
  `prefers-reduced-motion: reduce` a step is still immediate; the wait between steps still follows the pace.
- **Loop** (`#loop` checked, `#all` not): play does not stop at the last round. One wait after reaching it, play
  goes to round 1 of the same run and continues.
- **Play all** (`#all` checked): one wait after reaching a run's last round, play shows the NEXT run at its round 1:
  the next option of the run selector on show; after the last run of a world, the first run of the next world (the
  next option of `#pick-world`). Both selectors show the run on show. A run with no round is shown for one wait,
  then play moves on. After the last run of the last world: with `#loop` checked, the first run of the first world;
  otherwise play stops there. On a run with no round `#play` is enabled exactly when `#all` is checked.
- **A selector changed by hand stops play**, as in 1531. Checking or unchecking `#loop` or `#all`, moving `#speed`
  and pressing `#full` do not.
- **Full screen.** `#full` pressed: `#player` and the root element get the class `fs-on`, `aria-pressed` becomes
  `true`, and the script asks for `#player.requestFullscreen()`. A refusal or a missing API is ignored: the class
  alone makes `#player` a fixed overlay that fills the window. `#full` pressed again, the `Escape` key, or the
  browser leaving full screen (`fullscreenchange` with no `fullscreenElement`) removes the class from both, sets
  `aria-pressed="false"` and leaves the browser's full screen if it is on. While `fs-on`, with one run and one round
  on show at 1280×800, `#player` fills the window and does not scroll, and the frame is at least 200 px high.
- After any sequence of actions `#stage` still differs from the bytes Python wrote only in `hidden` attributes and
  classes.

## What this supersedes in SCHEMA-1531
1. "The page — Layout": the list of controls gains the four above.
2. "The script", first paragraph: the script may also set the selected option of `#pick-world` and of a
   `select.pick-run` (play-all only), add or remove the class `fs-on` on `#player` and on the root element, and call
   the Fullscreen API.
3. "Behaviour": "`#play` … stops at the last round" holds only when `#loop` and `#all` are both unchecked.
4. "Behaviour": "Changing the world … Either stops play" means a change made by the reader, not one made by play-all.
5. "Required, not tested": "the five controls" becomes the nine controls and the two selectors.
SCHEMA-1531 "Look": the plot names follow "The plot names" above.
