"""The whole page of the needle player, a function of the stream alone. Pure: no clock, no randomness, no file."""
import html
import json

from needleview.player.assets import SCRIPT, STYLE
from needleview.player.frame import fragments
from needleview.player.stream import RunStart, encode

STEP_MS, PLAY_MS = "600", "1600"
LEGEND = ("One round is on show. The NAVIGATOR zone and the solid-bordered marks are what the needle measured and decided; "
          "the SYSTEM zone and the dashed border are what only the System knows, and read UNKNOWN when nothing is known. "
          "The strip under the plots is how the bracket narrowed, round by round.")


TIPS = {
    "world": "Choose which test world to look at.\nEach world is one kind of system the needle was pointed at. Changing it lists that world's runs, and shows the first run's first round.",
    "run": "Choose which run of this world to look at.\nA run is one attempt by the needle, from its first guess to its last. Different runs of the same world can narrow in on the answer by different paths.",
    "prev": "Go back one round.\nA round is one sweep of the needle across a range of dial settings. Going back shows what the needle knew before it narrowed its search.",
    "play": "Play or pause the animation of the rounds.\nWhile playing, the page moves from round to round by itself and shows the needle's search closing in. Press again to pause on the round you are watching.",
    "next": "Go forward one round.\nA round is one sweep of the needle across a range of dial settings. Going forward shows the narrower range it chose to search next.",
    "scrub": "Drag to any round of this run.\nEach round is one sweep of the needle across the dial. The far left is the first, widest sweep, and the far right is the last, narrowest one.",
    "speed": "How fast the animation runs.\nLeft is slow and right is fast. It changes both the length of the move between rounds and the pause on each round, so you can follow the needle at your own pace.",
    "loop": "Start again from round 1 after the last round.\nWith this off, playing stops at the final round, where the needle has finished narrowing. With it on, the run replays until you pause it.",
    "all": "Play every run, then every world.\nWith this on, playing carries on from one run to the next, and from one world to the next, so you can compare how the needle did on each without clicking.",
    "full": "Fill the screen with the player. Press Esc to leave.\nThe plots grow to use the whole window, which makes the dots and numbers easier to read.",
}


def _e(s):
    return html.escape(s, quote=True)


def _data(stream):
    return json.dumps(encode(stream)).replace("<", "\\u003c")


def _selectors(stream):
    worlds, runs = [], {}
    for e in stream:
        if isinstance(e, RunStart):
            if e.world not in runs:
                worlds.append(e.world)
                runs[e.world] = []
            runs[e.world].append(e)
    world = "".join(f'<option value="{_e(w)}">{_e(w)}</option>' for w in worlds)
    pick = "".join(f'<select class="pick-run" data-world="{_e(w)}" aria-label="run" title="' + _e(TIPS["run"]) + '" hidden>' +
                   "".join(f'<option value="{r.run}">{_e(r.label)}</option>' for r in runs[w]) + "</select>" for w in worlds)
    return f'<select id="pick-world" aria-label="world" title="{_e(TIPS["world"])}">{world}</select>{pick}'


def _sections(stream):
    out, order = {}, []
    for e, frag in zip(stream, fragments(stream)):
        if isinstance(e, RunStart):
            out[e.run] = [f'<section class="run" data-run="{e.run}" data-world="{_e(e.world)}" data-label="{_e(e.label)}" hidden>']
            order.append(e.run)
        out[e.run].append(frag)
    return "".join("".join(out[i]) + "</section>" for i in order)


def render(stream):
    t = {k: _e(v) for k, v in TIPS.items()}
    controls = ('<button id="prev" type="button" aria-label="previous round" title="' + t["prev"] + '">&#9664;</button>'
                '<button id="play" type="button" aria-label="play" aria-pressed="false" title="' + t["play"] + '">play</button>'
                '<button id="next" type="button" aria-label="next round" title="' + t["next"] + '">&#9654;</button>'
                '<input id="scrub" type="range" min="1" step="1" aria-label="round" title="' + t["scrub"] + '" />'
                '<output id="pos">no rounds</output>'
                '<span>slow</span>'
                '<input id="speed" type="range" min="0.25" max="4" step="0.25" value="1" aria-label="speed" title="' + t["speed"] + '" />'
                '<span>fast</span>'
                '<label title="' + t["loop"] + '"><input id="loop" type="checkbox" aria-label="loop" title="' + t["loop"] + '" />loop</label>'
                '<label title="' + t["all"] + '"><input id="all" type="checkbox" aria-label="play all" title="' + t["all"] + '" />play all</label>'
                '<button id="full" type="button" aria-label="full screen" aria-pressed="false" title="' + t["full"] + '"><span class="ico"></span></button>')
    return "".join([
        "<!doctype html>\n",
        '<html lang="en"><head><meta charset="utf-8">',
        '<meta name="viewport" content="width=device-width, initial-scale=1">',
        f"<title>Needle player</title><style>{STYLE}</style></head><body>",
        f'<h1>Needle player</h1><p class="mute">{_e(LEGEND)}</p>',
        "<noscript>This page needs scripts on to show one round at a time.</noscript>",
        f'<div id="player" data-view="navigator" data-step-ms="{STEP_MS}" data-play-ms="{PLAY_MS}">',
        f'<div class="bar">{_selectors(stream)}</div>',
        f'<div class="controls">{controls}</div>',
        f'<div id="stage">{_sections(stream)}</div></div>',
        f'<script type="application/json" id="stream">{_data(stream)}</script>',
        f"<script>{SCRIPT}</script>",
        "</body></html>\n",
    ])
