"""Plan 1535 - the needle player v2 (contract/SCHEMA-1535.md): four new controls, the plot names, the script's text.
FROZEN: the Generator makes this green; it does not edit it. The 23 tests of plan 1531 stay green beside it, unedited.
No JavaScript runs here: what the controls DO is the Auditor's browser check.

Run:  python contract/test_needleplayer_v2.py   (or pytest)
"""
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import test_needleplayer_page as P   # noqa: E402 - the page helpers of plan 1531, reused as they are


def _page(truth=False):
    return P._els(P._render(P._stream(P._mixed_specs(), truth)))


def test_v1_four_new_controls_as_written():
    for truth in (False, True):
        els = _page(truth)
        player, stage = P._by_id(els, "player"), P._by_id(els, "stage")
        for ident in ("speed", "loop", "all", "full"):
            e = P._by_id(els, ident)
            assert P._in(e, player) and not P._in(e, stage) and "data-source" not in e["a"], ident
        a = P._by_id(els, "speed")["a"]
        assert P._by_id(els, "speed")["tag"] == "input", "the pace is a range, not a select (plan 1531 counts selects)"
        assert {k: a.get(k) for k in ("type", "min", "max", "step", "value", "aria-label")} == {
            "type": "range", "min": "0.25", "max": "4", "step": "0.25", "value": "1", "aria-label": "speed"}, a
        order = [e["a"].get("id") or e["own"].strip() for e in els if P._in(e, player) and not P._in(e, stage)
                 and (e["a"].get("id") == "speed" or e["own"].strip() in ("slow", "fast"))]
        assert order == ["slow", "speed", "fast"], ("the two ends of the pace are named, slow first", order)
        for ident, name in (("loop", "loop"), ("all", "play all")):
            e = P._by_id(els, ident)
            assert e["tag"] == "input" and e["a"].get("type") == "checkbox" and e["a"].get("aria-label") == name, e["a"]
            assert "checked" not in e["a"], (ident, "off as written: the page starts as plan 1531's")
            labels = [x for x in e["anc"] if x["tag"] == "label"]
            assert len(labels) == 1 and labels[0]["text"].strip() == name, (ident, [x["text"] for x in labels])
        full = P._by_id(els, "full")
        assert full["tag"] == "button" and full["a"].get("type") == "button", full["a"]
        assert full["a"].get("aria-label") == "full screen" and full["a"].get("aria-pressed") == "false", full["a"]
        inside = [e for e in els if P._in(e, full)]
        assert [(e["tag"], sorted(e["cls"]), e["text"]) for e in inside] == [("span", ["ico"], "")] and full["text"] == "", \
            "the icon is one empty span drawn by the style sheet"
        assert player["a"].get("data-step-ms") and player["a"].get("data-play-ms")
        want = {"prev", "play", "next", "scrub", "pos", "speed", "loop", "all", "full", "pick-world", "player", "stage", "stream"}
        got = [e["a"]["id"] for e in els if "id" in e["a"]]
        assert sorted(got) == sorted(want), ("exactly these ids, each once", sorted(got))


def test_v2_the_script_text():
    els = _page()
    js = P._sel(els, "script")[1]["text"]
    for need in ("requestFullscreen", "exitFullscreen", "fullscreenElement", "fullscreenchange", "keydown", "Escape", "fs-on"):
        assert need in js, need
    for ident in ("speed", "loop", "all", "full"):
        assert re.search(r"getElementById\(\s*['\"]" + ident + r"['\"]\s*\)", js), (ident, "the script reads this control")
    for bad in (".style", "setTimeout", "setInterval", "selected=", "scrollTo", "scrollIntoView"):
        assert bad not in js, (bad, "full screen is a class; time comes from requestAnimationFrame")
    style = re.sub(r"\s+", "", P._one(els, "style")["text"])
    assert ":root.fs-on" in style, "the page under the overlay does not scroll"
    rules = re.findall(r"#player\.fs-on\{([^}]*)\}", style)
    assert any("position:fixed" in r for r in rules), "the fallback overlay: #player.fs-on{position:fixed ...}"
    P.test_p10_the_script_moves_marks_and_measures_nothing()


def test_v3_plot_names_clear_of_the_axis_numbers():
    seen = 0
    for truth in (False, True):
        els = _page(truth)
        for svg in P._sel(els, "svg", "frame"):
            texts = P._sel(els, "text", None, svg)
            names = [t for t in texts if "plot-name" in t["cls"]]
            if svg["a"]["data-evaluated"] == "true":
                assert [(t["text"], t["a"].get("x"), t["a"].get("y")) for t in names] == [
                    ("C", "284.00", "18.00"), ("D", "284.00", "123.00"), ("Gs", "284.00", "208.00")], [t["a"] for t in names]
                seen += 1
            else:
                assert not names, "an unevaluated round draws no plot"
            for t in names:
                assert "text-anchor" not in t["a"] and t["a"].get("data-source") == "navigator", t["a"]
            for t in texts:
                if t["text"].strip() in ("C", "D", "Gs"):
                    assert "plot-name" in t["cls"], ("a plot name without its class", t["a"])
                if t["a"].get("text-anchor") is None and "x" in t["a"]:
                    assert float(t["a"]["x"]) >= 40.0, ("a start-anchored text over the y-axis numbers", t["a"], t["text"])
    assert seen > 0


TESTS = [(n, f) for n, f in sorted(globals().items()) if n.startswith("test_v") and callable(f)]

if __name__ == "__main__":
    P._main(TESTS)
