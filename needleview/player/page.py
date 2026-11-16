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
    pick = "".join(f'<select class="pick-run" data-world="{_e(w)}" aria-label="run" hidden>' +
                   "".join(f'<option value="{r.run}">{_e(r.label)}</option>' for r in runs[w]) + "</select>" for w in worlds)
    return f'<select id="pick-world" aria-label="world">{world}</select>{pick}'


def _sections(stream):
    out, order = {}, []
    for e, frag in zip(stream, fragments(stream)):
        if isinstance(e, RunStart):
            out[e.run] = [f'<section class="run" data-run="{e.run}" data-world="{_e(e.world)}" data-label="{_e(e.label)}" hidden>']
            order.append(e.run)
        out[e.run].append(frag)
    return "".join("".join(out[i]) + "</section>" for i in order)


def render(stream):
    controls = ('<button id="prev" type="button" aria-label="previous round">&#9664;</button>'
                '<button id="play" type="button" aria-label="play" aria-pressed="false">play</button>'
                '<button id="next" type="button" aria-label="next round">&#9654;</button>'
                '<input id="scrub" type="range" min="1" step="1" aria-label="round" />'
                '<output id="pos">no rounds</output>'
                '<span>slow</span>'
                '<input id="speed" type="range" min="0.25" max="4" step="0.25" value="1" aria-label="speed" />'
                '<span>fast</span>'
                '<label><input id="loop" type="checkbox" aria-label="loop" />loop</label>'
                '<label><input id="all" type="checkbox" aria-label="play all" />play all</label>'
                '<button id="full" type="button" aria-label="full screen" aria-pressed="false"><span class="ico"></span></button>')
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
