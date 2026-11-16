"""The fragments of the needle player: one HTML fragment per event. Pure: no clock, no randomness, no file.

Every element is written through `_tag` or `_shape`, which take its source as a required argument, so an element
without a source cannot be written. What came from `Known` or `Scored` is written only in system elements.
"""
import html

from needleview.draw import PLOT_C, PLOT_D, PLOT_G, _n, _px, _sig, _x
from needleview.player.stream import Known, Outcome, RoundEv, RunStart, Scored, UNKNOWN
from needleview.report import Evaluated
from needleview.scale import scale

NAV, SYS = "navigator", "system"
DASH = "—"
LATER = "not reported (stage 2)"
VIEWBOX = "0 0 300 320"
TRAIL_Y, TRAIL_H = "298.00", "14.00"


def _e(s):
    return html.escape(s, quote=True)


def _attrs(attrs):
    return " ".join(k if v is None else f'{k}="{_e(v)}"' for k, v in attrs)


def _tag(name, src, attrs, inner):
    return f'<{name} {_attrs(attrs)} data-source="{src}">{inner}</{name}>'


def _shape(name, src, attrs):
    return f'<{name} {_attrs(attrs)} data-source="{src}" />'


def _yn(v):
    return "yes" if v else "no"


def _bool(v):
    return "true" if v else "false"


def _pair(p):
    return f"{p[0]!r}, {p[1]!r}"


# ---------- slots and zones ----------
def _slot(src, name, state, text):
    attrs = [("class", "slot"), ("data-slot", name), ("data-state", state)]
    if state == "value":
        attrs.append(("data-v", text))
    return _tag("span", src, attrs, _e(text))


def _row(src, name, state, text):
    return _tag("div", src, [("class", "row")], _tag("span", src, [("class", "cap")], _e(name)) + _slot(src, name, state, text))


def _value(src, name, text):
    return _row(src, name, "value", text)


def _absent(src, name):
    return _row(src, name, "absent", DASH)


def _unknown(src, name):
    return _row(src, name, "unknown", UNKNOWN)


def _maybe(name, v, fmt):
    return _absent(NAV, name) if v is None else _value(NAV, name, fmt(v))


def _zone(src, rows):
    return _tag("div", src, [("class", "zone")], _tag("span", src, [("class", "zone-name")], src.upper()) + "".join(rows))


def _system_rows(names, values):
    if values is None:
        return [_unknown(SYS, n) for n in names]
    return [_absent(SYS, n) if v is None else _value(SYS, n, v) for n, v in zip(names, values)]


# ---------- the frame ----------
def _tick_marks(r, x0, x1):
    out = []
    for i, k in enumerate(r.grid):
        x = _px(_x(k, x0, x1))
        out.append(_shape("line", NAV, [("class", "tick"), ("data-key", f"tick-{i}"), ("data-k", repr(k)),
                                        ("x1", x), ("x2", x), ("y1", "272.00"), ("y2", "278.00")]))
    out.append(_tag("text", NAV, [("x", "40.00"), ("y", "290.00")], _n(x0)))
    out.append(_tag("text", NAV, [("x", "280.00"), ("y", "290.00"), ("text-anchor", "end")], _n(x1)))
    return out


def _plot_labels(name, dom, top, height):
    lo, hi = dom
    return [_shape("rect", NAV, [("class", "box"), ("x", "40.00"), ("y", _px(top)), ("width", "240.00"), ("height", _px(height))]),
            _tag("text", NAV, [("class", "plot-name"), ("x", "284.00"), ("y", _px(top + 8))], name),
            _tag("text", NAV, [("x", "38.00"), ("y", _px(top + 8)), ("text-anchor", "end")], _n(hi)),
            _tag("text", NAV, [("x", "38.00"), ("y", _px(top + height)), ("text-anchor", "end")], _n(lo))]


def _moments(r, x0, x1):
    m, nlev = len(r.grid), len(r.Gs[0])
    sigs = [_sig(r, i) for i in range(m)]
    dc = (min(r.C[i] - r.C_err[i] for i in range(m)), max(r.C[i] + r.C_err[i] for i in range(m)))
    dd = (min([0.0] + [r.D[i] - sigs[i] for i in range(m)]), max([0.0] + [r.D[i] + sigs[i] for i in range(m)]))
    flat = [v for row in r.Gs for v in row]
    dg = (min(flat), max(flat))
    sc, sd, sg = scale(*dc, *PLOT_C), scale(*dd, *PLOT_D), scale(*dg, *PLOT_G)
    nx, nw = _x(r.lo, x0, x1), _x(r.hi, x0, x1) - _x(r.lo, x0, x1)
    out = [_shape("rect", NAV, [("class", "next"), ("data-key", "next"), ("data-lo", repr(r.lo)), ("data-hi", repr(r.hi)),
                                ("x", _px(nx)), ("y", "4.00"), ("width", _px(nw)), ("height", "270.00")])]
    out += _plot_labels("C", dc, *PLOT_C) + _plot_labels("D", dd, *PLOT_D) + _plot_labels("Gs", dg, *PLOT_G)
    out += _tick_marks(r, x0, x1)
    yz = _px(sd.y(0.0))
    out.append(_shape("line", NAV, [("class", "zero"), ("data-key", "zero"), ("x1", "40.00"), ("x2", "280.00"), ("y1", yz), ("y2", yz)]))
    for i, k in enumerate(r.grid):
        x = _px(_x(k, x0, x1))
        out.append(_shape("line", NAV, [("class", "c-err"), ("data-key", f"cerr-{i}"), ("data-i", str(i)), ("x1", x), ("x2", x),
                                        ("y1", _px(sc.y(r.C[i] + r.C_err[i]))), ("y2", _px(sc.y(r.C[i] - r.C_err[i])))]))
        out.append(_shape("circle", NAV, [("class", "c in-A" if i in r.A else "c"), ("data-key", f"c-{i}"), ("data-i", str(i)),
                                          ("data-k", repr(k)), ("data-v", repr(r.C[i])), ("data-err", repr(r.C_err[i])),
                                          ("cx", x), ("cy", _px(sc.y(r.C[i]))), ("r", "3.00")]))
        out.append(_shape("line", NAV, [("class", "d-err"), ("data-key", f"derr-{i}"), ("data-i", str(i)), ("x1", x), ("x2", x),
                                        ("y1", _px(sd.y(r.D[i] + sigs[i]))), ("y2", _px(sd.y(r.D[i] - sigs[i])))]))
        out.append(_shape("circle", NAV, [("class", "d in-B" if i in r.B else "d"), ("data-key", f"d-{i}"), ("data-i", str(i)),
                                          ("data-k", repr(k)), ("data-v", repr(r.D[i])), ("data-sig", repr(sigs[i])),
                                          ("cx", x), ("cy", _px(sd.y(r.D[i]))), ("r", "3.00")]))
        for lev in range(nlev):
            out.append(_shape("circle", NAV, [("class", f"g l{min(lev, 2)}"), ("data-key", f"g-{lev}-{i}"), ("data-level", str(lev)),
                                              ("data-i", str(i)), ("data-k", repr(k)), ("data-v", repr(r.Gs[i][lev])),
                                              ("data-err", repr(r.Gs_err[i][lev])), ("cx", x), ("cy", _px(sg.y(r.Gs[i][lev]))),
                                              ("r", "2.50")]))
    return out


def _trail(spans, now, g0, g1):
    out = []
    for j, (lo, hi) in enumerate(spans):
        xa, xb = _x(lo, g0, g1), _x(hi, g0, g1)
        out.append(_shape("rect", NAV, [("class", "trail now" if j == now else "trail"), ("data-j", str(j)), ("data-key", f"trail-{j}"),
                                        ("data-lo", repr(lo)), ("data-hi", repr(hi)), ("x", _px(xa)), ("y", TRAIL_Y),
                                        ("width", _px(xb - xa)), ("height", TRAIL_H)]))
    return out


def _system_mark(system, x0, x1):
    if not isinstance(system, Known):
        return _tag("text", SYS, [("class", "sys-unknown"), ("x", "282.00"), ("y", "8.00"), ("text-anchor", "end")], f"K_c {UNKNOWN}")
    k = system.truth_K_c
    if x0 <= k <= x1:
        x = _px(_x(k, x0, x1))
        return _shape("line", SYS, [("class", "truth"), ("data-key", "truth"), ("data-k", repr(k)),
                                    ("x1", x), ("x2", x), ("y1", "4.00"), ("y2", "276.00")])
    if k < x0:
        return _shape("polygon", SYS, [("class", "truth-off"), ("data-side", "lo"), ("points", "28.00,60.00 38.00,54.00 38.00,66.00")])
    return _shape("polygon", SYS, [("class", "truth-off"), ("data-side", "hi"), ("points", "292.00,60.00 282.00,54.00 282.00,66.00")])


def _frame(r, system, g0, g1, spans):
    ev = isinstance(r, Evaluated)
    x0, x1 = r.grid[0], r.grid[-1]
    if ev:
        marks = _moments(r, x0, x1)
    else:
        marks = _tick_marks(r, x0, x1)
        marks.append(_tag("text", NAV, [("class", "not-evaluated"), ("x", "160.00"), ("y", "140.00"), ("text-anchor", "middle")],
                          "not evaluated"))
    marks += _trail(spans, r.round, g0, g1)
    layers = (_tag("g", NAV, [("class", "layer")], "".join(marks)) +
              _tag("g", SYS, [("class", "layer")], _system_mark(system, x0, x1)))
    return _tag("svg", NAV, [("class", "frame"), ("viewBox", VIEWBOX), ("data-round", str(r.round)), ("data-evaluated", _bool(ev)),
                             ("data-x0", repr(x0)), ("data-x1", repr(x1)), ("data-lo", repr(r.lo)), ("data-hi", repr(r.hi))], layers)


# ---------- one fragment per event ----------
def _head(e):
    s = e.system
    known = isinstance(s, Known)
    nav = _zone(NAV, [_row(NAV, "belief", "not-reported", LATER)])
    system = _zone(SYS, _system_rows(("truth_K_c", "a", "w_max"), (repr(s.truth_K_c), repr(s.a), repr(s.w_max)) if known else None))
    return _tag("div", NAV, [("class", "head"), ("data-ev", "run"), ("data-run", str(e.run))], nav + system)


def _round(e, earlier):
    r = e.rnd
    rounds = [x.rnd for x in earlier if isinstance(x, RoundEv)] + [r]
    g0, g1 = rounds[0].grid[0], rounds[0].grid[-1]
    spans = [(g0, g1)] + [(x.lo, x.hi) for x in rounds]
    system = earlier[0].system
    button = _tag("button", NAV, [("class", "rnd"), ("type", "button"), ("data-round", str(r.round))], str(r.round))
    body = _tag("div", NAV, [("class", "body"), ("hidden", None)],
                _frame(r, system, g0, g1, spans) + _row(NAV, "verdict", "not-reported", LATER))
    return _tag("div", NAV, [("class", "round"), ("data-ev", "round"), ("data-run", str(e.run)), ("data-round", str(r.round)),
                             ("data-evaluated", _bool(isinstance(r, Evaluated)))], button + body)


def _outcome(e):
    nav = [_value(NAV, "kind", e.kind), _maybe("reason", e.reason, str)]
    nav += [_maybe("lo", e.bracket, lambda b: repr(b[0])), _maybe("hi", e.bracket, lambda b: repr(b[1])),
            _maybe("width", e.bracket, lambda b: repr(b[1] - b[0])), _maybe("agree", e.agree, _yn),
            _maybe("A_hull", e.A_hull, _pair), _maybe("B_hull", e.B_hull, _pair)]
    sc = e.score
    scored = isinstance(sc, Scored)
    system = _system_rows(("cell", "contains"), (sc.cell, None if sc.contains is None else _yn(sc.contains)) if scored else None)
    return _tag("div", NAV, [("class", "outcome"), ("data-ev", "outcome"), ("data-run", str(e.run)), ("data-kind", e.kind),
                             ("data-reason", e.reason or "")], _zone(NAV, nav) + _zone(SYS, system))


def _refused(e):
    return _tag("div", NAV, [("class", "unreadable"), ("data-ev", "unreadable"), ("data-run", str(e.run))],
                _tag("p", NAV, [("class", "why")], _e(e.why)))


def fragments(stream):
    """one fragment per event; a fragment is a function of the event and the earlier events of its own run."""
    by_run, out = {}, []
    for e in stream:
        earlier = by_run.get(e.run, ())
        if isinstance(e, RunStart):
            out.append(_head(e))
        elif isinstance(e, RoundEv):
            out.append(_round(e, earlier))
        elif isinstance(e, Outcome):
            out.append(_outcome(e))
        else:
            out.append(_refused(e))
        by_run[e.run] = earlier + (e,)
    return tuple(out)
