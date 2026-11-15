"""The whole page from a list of Run | Unreadable. Pure: no clock, no randomness, no file.

Draws only what the needle was told and what it decided. The truth appears only through Run.overlay.
"""
import html
import math

from needleview.report import Budget, Evaluated, Floor, Located, Run, Unreadable
from needleview.scale import scale

DASH = "—"
X0, SPAN = 40.0, 240.0
PLOT_C, PLOT_D, PLOT_G = (10.0, 90.0), (115.0, 70.0), (200.0, 70.0)

CSS = """
:root{--bg:#fbfbf8;--fg:#1d1f21;--mute:#6a6f76;--line:#c9ccd1;--a:#b3470f;--b:#14628a;--g0:#3a7d44;--g1:#7a4aa0;--next:#f2d37a;--zero:#8a8f96;--truth:#c0182f;--panel:#ffffff}
@media (prefers-color-scheme: dark){:root:not([data-theme="light"]){--bg:#15171a;--fg:#e6e7e9;--mute:#9aa0a8;--line:#3a3f46;--a:#f09a62;--b:#6cb8e6;--g0:#7fcf8a;--g1:#c39be6;--next:#6b5a1d;--zero:#7d838b;--truth:#ff6b7d;--panel:#1d2024}}
:root[data-theme="dark"]{--bg:#15171a;--fg:#e6e7e9;--mute:#9aa0a8;--line:#3a3f46;--a:#f09a62;--b:#6cb8e6;--g0:#7fcf8a;--g1:#c39be6;--next:#6b5a1d;--zero:#7d838b;--truth:#ff6b7d;--panel:#1d2024}
*{box-sizing:border-box}
body{margin:0;padding:16px;background:var(--bg);color:var(--fg);font:15px/1.45 system-ui,sans-serif}
h1{font-size:1.3rem;margin:0 0 .4rem}h2{font-size:1.1rem;margin:0 0 .3rem;overflow-wrap:anywhere}
.mute,.meta,figcaption{color:var(--mute);font-size:.85rem}
.tablewrap{overflow-x:auto}
table{border-collapse:collapse;font-size:.85rem}th,td{border:1px solid var(--line);padding:2px 8px;text-align:right}
th:first-child,td:first-child{text-align:left}
section.run{margin:1.4rem 0;padding-top:.6rem;border-top:1px solid var(--line)}
.rounds{display:flex;flex-wrap:wrap;gap:12px}
figure{margin:0;flex:1 1 280px;max-width:420px}
svg.round{width:100%;height:auto;background:var(--panel);border:1px solid var(--line)}
svg.widths{width:100%;max-width:420px;height:auto;background:var(--panel);border:1px solid var(--line)}
polyline.width-path{fill:none;stroke:var(--b);stroke-width:1.5;opacity:.8}
svg text{fill:var(--mute);font-size:9px}
.frame{fill:none;stroke:var(--line)}
line.tick{stroke:var(--mute);stroke-width:1}
line.zero{stroke:var(--zero);stroke-dasharray:3 2}
rect.next{fill:var(--next);opacity:.45}
line.c-err,line.d-err{stroke:var(--mute);stroke-width:1}
circle.c,circle.d{stroke-width:1.5;fill:none}
circle.c{stroke:var(--a)}circle.c.in-A{fill:var(--a);stroke-width:3}
circle.d{stroke:var(--b)}circle.d.in-B{fill:var(--b);stroke-width:3}
circle.g{stroke-width:1.2}
circle.g.l0{fill:var(--g0);stroke:var(--g0)}circle.g.l1{fill:none;stroke:var(--g1)}circle.g.l2{fill:var(--mute);stroke:var(--mute)}
.key{display:inline-block;width:.8em;height:.8em;border-radius:50%;border:2px solid var(--mute);vertical-align:-1px;margin:0 2px 0 8px}
.kA{border-color:var(--a);background:var(--a)}.kA0{border-color:var(--a)}.kB{border-color:var(--b);background:var(--b)}.kB0{border-color:var(--b)}
"""
CSS_OVERLAY = """
line.truth{stroke:var(--truth);stroke-width:1.5}
polygon.truth-off{fill:var(--truth)}
span.cell{font-weight:600;padding:0 6px;border:1px solid var(--truth);border-radius:3px;color:var(--truth)}
"""


def _px(v):
    return format(v, ".2f")


def _e(s):
    return html.escape(s, quote=True)


def _x(k, x0, x1):
    return X0 + (k - x0) / (x1 - x0) * SPAN


def _n(v):
    return format(v, ".6g")


def _yn(v):
    return "yes" if v else "no"


def _sig(r, i):
    return math.sqrt(r.Gs_err[i][1] ** 2 + r.Gs_err[i][0] ** 2)


def _bool(v):
    return "true" if v else "false"


def _ticks(r):
    x0, x1 = r.grid[0], r.grid[-1]
    out = []
    for k in r.grid:
        x = _px(_x(k, x0, x1))
        out.append(f'<line class="tick" data-k="{k!r}" x1="{x}" x2="{x}" y1="272.00" y2="278.00" />')
    out.append(f'<text x="40.00" y="290.00">{_n(x0)}</text>')
    out.append(f'<text x="280.00" y="290.00" text-anchor="end">{_n(x1)}</text>')
    return out


def _plot_labels(name, dom, top, height):
    lo, hi = dom
    return [f'<rect class="frame" x="40.00" y="{_px(top)}" width="240.00" height="{_px(height)}" />',
            f'<text x="2.00" y="{_px(top + 8)}">{name}</text>',
            f'<text x="38.00" y="{_px(top + 8)}" text-anchor="end">{_n(hi)}</text>',
            f'<text x="38.00" y="{_px(top + height)}" text-anchor="end">{_n(lo)}</text>']


def _overlay_mark(r, ov):
    x0, x1, k = r.grid[0], r.grid[-1], ov.truth_K_c
    if x0 <= k <= x1:
        x = _px(_x(k, x0, x1))
        return (f'<line class="truth" data-k="{k!r}" x1="{x}" x2="{x}" y1="4.00" y2="276.00">'
                f'<title>truth_K_c = {k!r}</title></line>')
    if k < x0:
        return ('<polygon class="truth-off" data-side="lo" points="28.00,60.00 38.00,54.00 38.00,66.00">'
                f'<title>truth_K_c = {k!r} is below this grid</title></polygon>')
    return ('<polygon class="truth-off" data-side="hi" points="292.00,60.00 282.00,54.00 282.00,66.00">'
            f'<title>truth_K_c = {k!r} is above this grid</title></polygon>')


def _round_svg(r, ov):
    ev = isinstance(r, Evaluated)
    x0, x1 = r.grid[0], r.grid[-1]
    out = [f'<svg class="round" viewBox="0 0 300 295" data-round="{r.round}" data-evaluated="{_bool(ev)}" '
           f'data-x0="{x0!r}" data-x1="{x1!r}" data-lo="{r.lo!r}" data-hi="{r.hi!r}">']
    if not ev:
        out += _ticks(r)
        out.append('<text class="not-evaluated" x="160.00" y="140.00" text-anchor="middle">not evaluated</text>')
    else:
        m, nlev = len(r.grid), len(r.Gs[0])
        sigs = [_sig(r, i) for i in range(m)]
        dc = (min(r.C[i] - r.C_err[i] for i in range(m)), max(r.C[i] + r.C_err[i] for i in range(m)))
        dd = (min([0.0] + [r.D[i] - sigs[i] for i in range(m)]), max([0.0] + [r.D[i] + sigs[i] for i in range(m)]))
        flat = [v for row in r.Gs for v in row]
        dg = (min(flat), max(flat))
        sc, sd, sg = scale(*dc, *PLOT_C), scale(*dd, *PLOT_D), scale(*dg, *PLOT_G)
        nx, nw = _x(r.lo, x0, x1), _x(r.hi, x0, x1) - _x(r.lo, x0, x1)
        out.append(f'<rect class="next" data-lo="{r.lo!r}" data-hi="{r.hi!r}" x="{_px(nx)}" y="4.00" width="{_px(nw)}" height="270.00">'
                   f'<title>next grid: lo {r.lo!r}, hi {r.hi!r}</title></rect>')
        out += _plot_labels("C", dc, *PLOT_C) + _plot_labels("D", dd, *PLOT_D) + _plot_labels("Gs", dg, *PLOT_G)
        out += _ticks(r)
        yz = _px(sd.y(0.0))
        out.append(f'<line class="zero" x1="40.00" x2="280.00" y1="{yz}" y2="{yz}" />')
        for i, k in enumerate(r.grid):
            x = _px(_x(k, x0, x1))
            top, bot = _px(sc.y(r.C[i] + r.C_err[i])), _px(sc.y(r.C[i] - r.C_err[i]))
            out.append(f'<line class="c-err" data-i="{i}" x1="{x}" x2="{x}" y1="{top}" y2="{bot}" />')
            cls = "c in-A" if i in r.A else "c"
            note = " (in A)" if i in r.A else ""
            out.append(f'<circle class="{cls}" data-i="{i}" data-k="{k!r}" data-v="{r.C[i]!r}" data-err="{r.C_err[i]!r}" '
                       f'cx="{x}" cy="{_px(sc.y(r.C[i]))}" r="3.00">'
                       f'<title>C = {r.C[i]!r} +- C_err {r.C_err[i]!r} at K = {k!r}{note}</title></circle>')
            top, bot = _px(sd.y(r.D[i] + sigs[i])), _px(sd.y(r.D[i] - sigs[i]))
            out.append(f'<line class="d-err" data-i="{i}" x1="{x}" x2="{x}" y1="{top}" y2="{bot}" />')
            cls = "d in-B" if i in r.B else "d"
            note = " (in B)" if i in r.B else ""
            out.append(f'<circle class="{cls}" data-i="{i}" data-k="{k!r}" data-v="{r.D[i]!r}" data-sig="{sigs[i]!r}" '
                       f'cx="{x}" cy="{_px(sd.y(r.D[i]))}" r="3.00">'
                       f'<title>D = {r.D[i]!r} +- sig {sigs[i]!r} at K = {k!r}{note}</title></circle>')
            for lev in range(nlev):
                out.append(f'<circle class="g l{min(lev, 2)}" data-level="{lev}" data-i="{i}" data-k="{k!r}" data-v="{r.Gs[i][lev]!r}" '
                           f'data-err="{r.Gs_err[i][lev]!r}" cx="{x}" cy="{_px(sg.y(r.Gs[i][lev]))}" r="2.50">'
                           f'<title>Gs level {lev} = {r.Gs[i][lev]!r} +- {r.Gs_err[i][lev]!r} at K = {k!r}</title></circle>')
    if ov is not None:
        out.append(_overlay_mark(r, ov))
    out.append("</svg>")
    return "".join(out)


def _rounds_of(rep):
    return () if isinstance(rep, Floor) else rep.rounds


def _widths(rep):
    rs = _rounds_of(rep)
    return [rs[0].grid[-1] - rs[0].grid[0]] + [r.hi - r.lo for r in rs]


def _overview_svg(items):
    paths = [(i, it) for i, it in enumerate(items) if isinstance(it, Run) and _rounds_of(it.report)]
    out = ['<svg class="widths" viewBox="0 0 300 120">']
    if paths:
        logs = [[math.log10(w) for w in _widths(it.report)] for _, it in paths]
        flat = [v for row in logs for v in row]
        sy = scale(min(flat), max(flat), 10.0, 90.0)
        steps = max(len(row) for row in logs) - 1
        out.append('<rect class="frame" x="40.00" y="10.00" width="240.00" height="90.00" />')
        out.append('<text x="2.00" y="18.00">width</text>')
        out.append(f'<text x="38.00" y="18.00" text-anchor="end">{_n(10 ** max(flat))}</text>')
        out.append(f'<text x="38.00" y="100.00" text-anchor="end">{_n(10 ** min(flat))}</text>')
        out.append(f'<text x="40.00" y="114.00">start</text><text x="280.00" y="114.00" text-anchor="end">round {steps}</text>')
        for (i, it), row in zip(paths, logs):
            pts = " ".join(f"{_px(X0 + j / steps * SPAN)},{_px(sy.y(v))}" for j, v in enumerate(row))
            ws = ",".join(repr(w) for w in _widths(it.report))
            out.append(f'<polyline class="width-path" data-run="{i}" data-widths="{ws}" points="{pts}">'
                       f'<title>{_e(it.label)}: width of the bracket by round (log scale)</title></polyline>')
    out.append("</svg>")
    return "".join(out)


def _cells(it):
    """label, kind, reason, lo, hi, width, agree as text."""
    if isinstance(it, Unreadable):
        return [it.label, "Unreadable", DASH, DASH, DASH, DASH, DASH]
    rep = it.report
    if isinstance(rep, Floor):
        return [it.label, "REFUSE", "floor", DASH, DASH, DASH, DASH]
    if isinstance(rep, Budget):
        return [it.label, "REFUSE", "budget", DASH, DASH, DASH, DASH]
    last = rep.rounds[-1]
    return [it.label, "Located", DASH, repr(last.lo), repr(last.hi), repr(last.hi - last.lo), _yn(rep.agree)]


def _table(items, any_overlay):
    cols = ["label", "kind", "reason", "lo", "hi", "width", "agree"]
    extra = ("truth_K_c", "a", "contains", "cell")
    head = "".join(f'<th data-col="{c}">{c}</th>' for c in cols)
    if any_overlay:
        head += "".join(f'<th class="overlay" data-col="{c}">{c}</th>' for c in extra)
    out = [f'<div class="tablewrap"><table class="runs"><thead><tr>{head}</tr></thead><tbody>']
    for i, it in enumerate(items):
        row = "".join(f'<td data-col="{c}">{_e(v)}</td>' for c, v in zip(cols, _cells(it)))
        if any_overlay:
            ov = it.overlay if isinstance(it, Run) else None
            if ov is None:
                vals = [DASH] * 4
            else:
                vals = [repr(ov.truth_K_c), repr(ov.a), DASH if ov.contains is None else _yn(ov.contains), ov.cell]
            row += "".join(f'<td data-col="{c}">{_e(v)}</td>' for c, v in zip(extra, vals))
        out.append(f'<tr data-run="{i}">{row}</tr>')
    out.append("</tbody></table></div>")
    return "".join(out)


def _section(i, it):
    if isinstance(it, Unreadable):
        kind, reason = "Unreadable", ""
    elif isinstance(it.report, Located):
        kind, reason = "Located", ""
    elif isinstance(it.report, Floor):
        kind, reason = "REFUSE", "floor"
    else:
        kind, reason = "REFUSE", "budget"
    out = [f'<section class="run" data-run="{i}" data-label="{_e(it.label)}" data-kind="{kind}" data-reason="{reason}">',
           f"<h2>{_e(it.label)}</h2>"]
    if isinstance(it, Unreadable):
        out.append(f'<p class="why">{_e(it.why)}</p></section>')
        return "".join(out)
    rep, ov = it.report, it.overlay
    if isinstance(rep, Located):
        last = rep.rounds[-1]
        out.append(f'<p class="meta">Located: bracket [{last.lo!r}, {last.hi!r}], width {last.hi - last.lo!r}, '
                   f'agree {_yn(rep.agree)}, {len(rep.rounds)} rounds</p>')
    else:
        out.append(f'<p class="refuse" data-reason="{reason}">REFUSE ({reason}): the needle gave no bracket.</p>')
    if ov is not None:
        out.append(f'<p class="meta">scored: <span class="cell" data-cell="{_e(ov.cell)}">{_e(ov.cell)}</span> '
                   f'truth_K_c {ov.truth_K_c!r}, a {ov.a!r}</p>')
    out.append('<div class="rounds">')
    for r in _rounds_of(rep):
        state = "" if isinstance(r, Evaluated) else ", not evaluated"
        out.append(f"<figure><figcaption>round {r.round} (index {r.index}{state}); grid {r.grid[0]!r} to {r.grid[-1]!r}</figcaption>"
                   f"{_round_svg(r, ov)}</figure>")
    out.append("</div></section>")
    return "".join(out)


def render(items):
    items = list(items)
    any_overlay = any(isinstance(it, Run) and it.overlay is not None for it in items)
    css = CSS + (CSS_OVERLAY if any_overlay else "")
    legend = ('<p class="mute">Each round is drawn on its own K axis (first and last grid point at the ends). Top plot: C with C_err; '
              '<span class="key kA"></span>in A <span class="key kA0"></span>not in A. Middle plot: D with sig, the dashed line is 0; '
              'sig = sqrt(Gs_err[1]^2 + Gs_err[0]^2), computed here from the reported Gs_err; '
              '<span class="key kB"></span>in B <span class="key kB0"></span>not in B. Bottom plot: Gs, one mark per level. '
              "The shaded band is the next round's grid (lo to hi).</p>")
    parts = ["<!doctype html>", '<html lang="en"><head><meta charset="utf-8">',
             '<meta name="viewport" content="width=device-width, initial-scale=1">',
             "<title>Needle view</title>", f"<style>{css}</style></head><body>",
             "<h1>Needle view</h1>", legend, _overview_svg(items), _table(items, any_overlay)]
    parts += [_section(i, it) for i, it in enumerate(items)]
    parts.append("</body></html>\n")
    return "".join(parts)
