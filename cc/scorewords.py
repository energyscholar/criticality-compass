"""scorewords - plan 1201 AMENDMENT 1 (GATE-E findings F-4, F-5), built in plan 1205 P2 (ruling R4): the words of `bin/cc navigate score`.
Two facts, two typed fields, no shared vocabulary, and one verbose sentence assembled from them:
- navigator_verdict: the navigator's own verdict (linenav's), copied verbatim; score never recomputes it.
- checkpoint_reach: per checkpoint one Reach atom; checkpoints_summary: the count per atom.
- traced_slow_range and suspect_slow_range in the slow knob's physical unit (the traced ends' enclosing measured curves named).
- the census names its curves (F-5): per Feature kind, the curve ranks and their slow values (no measured value).
- the sentence names where each direction stopped: the nearest curve and the first curve beyond it, with their kinds.
The sentence's lead word is a lookup in LEAD, total over linenav.Verdict: only FOLLOWED_IN_CORRIDOR leads with the word FOLLOWED. Score cannot
certify a class of line (a crossover ridge traced within w_c scores the same: the E412 trap), so a score line names the declared line "the
suspect line" and never claims a class. Role plumbing; called by cc/navfamily.py's score (the walk is unchanged)."""
import enum

import numpy as np

import linenav


class Reach(enum.Enum):
    """One checkpoint against the traced line. ATOMS: REACHED_WITHIN_WC | REACHED_BEYOND_WC | NOT_REACHED. Axiom (a partition): NOT_REACHED
    when no line was traced or the checkpoint's slow value lies outside the slow range the trace covered (READ_RANGE: from the least to the
    greatest slow value of the measured curves the traced points read); else, with d its distance to the traced polyline in span units,
    REACHED_WITHIN_WC when d <= w_c and REACHED_BEYOND_WC when d > w_c."""
    REACHED_WITHIN_WC = "REACHED_WITHIN_WC"; REACHED_BEYOND_WC = "REACHED_BEYOND_WC"; NOT_REACHED = "NOT_REACHED"


REACH = {(False, False): Reach.NOT_REACHED, (False, True): Reach.NOT_REACHED,   # (reached, d <= w_c) -> Reach; total
         (True, True): Reach.REACHED_WITHIN_WC, (True, False): Reach.REACHED_BEYOND_WC}
LEAD = {   # the navigator's verdict -> the sentence's lead words; total over linenav.Verdict (only FOLLOWED_IN_CORRIDOR says FOLLOWED)
    linenav.Verdict.FOLLOWED_IN_CORRIDOR: "FOLLOWED trace", linenav.Verdict.PARTIAL_IN_CORRIDOR: "PARTIAL trace",
    linenav.Verdict.FOUND_DEVIATES: "DEVIATING trace", linenav.Verdict.ABSENT_IN_CORRIDOR: "ABSENT: no line in the corridor",
    linenav.Verdict.INDETERMINATE: "INDETERMINATE: no line acquired",
}
TIERING = {"NONE": "Untiered: no uncertainty column.", "COLUMN": "Tiered: the declared sigma column."}   # [measured.uncertainty] kind -> clause
DIRS = {-1: "backward", 1: "forward"}
READ_RANGE = ("the slow range a trace covered is that of the measured curves its points READ: each traced point reads its nearest curve (the "
              "oracle's own rule, Oracle.curve), so the range runs from the least to the greatest slow value of those curves; nothing is extended")


def read_range(o, path):
    """(least, greatest) curve rank the traced points read (READ_RANGE), or None when no line was traced."""
    ks = [o.curve(u) for u in path]
    return {True: lambda: (min(ks), max(ks)), False: lambda: None}[len(ks) > 0]()


def reach(o, path, u, wc):
    """The Reach of one checkpoint u (span units) against the traced polyline `path` (a list of points; empty when none was traced)."""
    have = len(path) > 0
    rr = read_range(o, path)
    reached = have and bool(o.span.u((o.slows[rr[0]], 0))[0] <= u[0] <= o.span.u((o.slows[rr[1]], 0))[0])
    d = {True: lambda: float(linenav.seg_dist(np.asarray(u, float), path)), False: lambda: None}[have]()
    return REACH[(reached, reached and d <= wc)], d


def summary(atoms):
    return ", ".join(f"{a.name} {sum(x is a for x in atoms)}" for a in Reach)


def census_named(o):
    """Per Feature kind, the curve ranks and their slow values (F-5)."""
    by = {k: [f"{r} ({o.slows[r]:g})" for r, f in enumerate(o.features) if type(f).__name__ == k] for k in ("Located", "Broad", "AtSpanEnd", "Absent")}
    return "; ".join(f"{k} {len(v)}: " + (", ".join(v) or "none") for k, v in by.items())


def stop_text(o, rec, path, sgn, unit):
    """Where direction sgn stopped: its end point's slow, terminal, the nearest curve (the last it read) and the next curve in that direction."""
    u = path[{-1: 0, 1: -1}[sgn]]
    k = o.ranks(u)[0]
    sl = o.span.x(u)[0]
    beyond = [r for r in (k + sgn,) if 0 <= r < len(o.slows)]   # the first curve past the nearest one in this direction: a curve it did not read
    nxt = {True: lambda: f"next curve rank {beyond[0]} ({type(o.features[beyond[0]]).__name__}, {o.slows[beyond[0]]:g} {unit})",
           False: lambda: "no curve beyond (the family's end)"}[len(beyond) > 0]()
    return f"{DIRS[sgn]} stopped at {sl:.4g} {unit} (terminal {rec['dirs'][sgn]['term'].name}; nearest curve rank {k}, {type(o.features[k]).__name__}, {o.slows[k]:g} {unit}; {nxt})"


def lines(ident, verdict, o, rec, path, cps, suspect, wc, unit, tiering, untested):
    """The score's output lines: the typed fields, then the sentence. `verdict` is the navigator's (rec["verdict"]), passed through."""
    each = [reach(o, path, u, wc) for u in cps]
    atoms = [a for a, _ in each]
    s = np.asarray(path, float).reshape(-1, 2)[:, 0]
    sus = sorted(o.span.x(v)[0] for v in suspect)
    traced = {True: lambda: (o.span.x((s.min(), 0))[0], o.span.x((s.max(), 0))[0]), False: lambda: None}[len(path) > 0]()
    rr = read_range(o, path)
    encl = {True: lambda: (f"; the curves read: ranks {rr[0]} .. {rr[1]}, {o.slows[rr[0]]:g} -> {o.slows[rr[1]]:g} {unit} (the checkpoints' reach range); "
                           f"enclosing measured curves of the traced ends {o.measured((s.min(), 0.5))[0][0]:g}|{o.measured((s.min(), 0.5))[0][1]:g} and "
                           f"{o.measured((s.max(), 0.5))[0][0]:g}|{o.measured((s.max(), 0.5))[0][1]:g} {unit}"), False: lambda: ""}[traced is not None]()
    tr = {True: lambda: f"{traced[0]:.4g} -> {traced[1]:.4g} {unit}", False: lambda: "none (no line traced)"}[traced is not None]()
    n_in, n_be, n_nr = (sum(a is x for a in atoms) for x in Reach)
    stops = "; ".join(stop_text(o, rec, path, k, unit) for k in sorted(rec["dirs"])) if len(path) else "no direction was traced"
    sentence = (f"{LEAD[verdict]} (navigator verdict {verdict.name}): traced {tr} of the suspect line's {sus[0]:g} -> {sus[-1]:g} {unit}; "
                f"{n_in + n_be} of {len(cps)} checkpoints reached, {n_in} within w_c and {n_be} beyond w_c ({wc} of each span), {n_nr} not reached "
                f"(outside the slow range of the curves the trace read); {stops}. {TIERING[tiering]}")
    rows = [f"  checkpoint {i}: slow {o.span.x(u)[0]:g} {unit}, distance {('none' if d is None else f'{d:.4f}')} span units -> {a.name}"
            for i, (u, (a, d)) in enumerate(zip(cps, each))]
    return [untested, f"score {ident}: navigator_verdict {verdict.name} (the navigator's, copied); {len(cps)} checkpoints converted by the suspect's rules",
            *rows, f"checkpoints_summary: {summary(atoms)}",
            f"traced_slow_range: {tr}{encl}", f"suspect_slow_range: {sus[0]:g} -> {sus[-1]:g} {unit} (the declared vertices)",
            f"census: {census_named(o)} (curve rank (slow) per Feature kind)",
            f"score: {n_in} of {len(cps)} checkpoints within w_c {wc} span units and reached (REACHED_WITHIN_WC)",
            f"sentence: {sentence}"]
