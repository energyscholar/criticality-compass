"""intake_feasible - S7 INTERVAL_FEASIBILITY, S8 RESOLUTION_AND_IDENTIFIABILITY and S9 ALTERNATIVE_INTAKE (plan 1160 P5; role intake_feasible
with its own cap, tests/test_budget.py FEASIBLE_CAP, so INTAKE_CAP stays 1200). Invariant: each body takes the S5 Census only (its SIGNATURE row)
and returns the Pass of its evidence type or the Refuse of its first failing row, in STAGES.toml order; every dispatch is a dict total over
its alphabet (tests/test_intake.py). The interval floors are CC's own (cc/declare.py block_floor, gamma_floor, chain_cells), never restated
here. S7 and S8 read no data byte (the census counts); S9 reads the bytes S3 pinned, through the declaration's reader (no file is opened).
A Detail holds counts, words and curve names (plan 1160 P0), never a value."""
from pathlib import Path

import declare
import intake_census
from intake_blind import Pass, Refuse, detail, gate
from intake_evidence import Census, Feasibility, IntervalPlan, SecondLane

ROOT = Path(__file__).resolve().parent.parent
AT = "intake.toml [interval]"   # where CC's floor findings are located
# method -> are its intervals drawn from the readings of a point; total
REPLICATED = {"block": True, "iid": True, "gamma": True, "chains": True, "STATED": False, "NONE": False}
# method -> the terminal's tiering; total
TIERING = {"block": "REPLICATES", "iid": "REPLICATES", "gamma": "REPLICATES", "chains": "REPLICATES", "STATED": "STATED", "NONE": "NONE"}
# iid: k* undefined (plans 1134, 1117); STATED, NONE need none; total
HAS_FLOOR = {"block": True, "iid": False, "gamma": True, "chains": True, "STATED": True, "NONE": True}
FLOOR = {   # method -> (its [interval] table, the points as (curve, ordinal, readings), the tables) -> CC's floor findings on the readings per point; total
    "block": lambda iv, pts, t: declare.block_floor(AT, iv, pts),   # n // b >= min_blocks per point (min_blocks is REQUIRED at S0 since plan 1160 A4, so the "not declared" case is unreachable here)
    "gamma": lambda iv, pts, t: declare.gamma_floor(AT, iv, pts, t["interval_fields"]["gamma"]["k_gamma"]),   # n >= k_gamma * tau_declared per point
    "chains": lambda iv, pts, t: declare.chain_cells(AT, iv, {(w, k, 0) for w, k, _ in pts}, {(w, k, 0, c) for w, k, n in pts for c in range(n)}),   # reading c is chain c
    "iid": lambda iv, pts, t: [],   # no floor: METHOD_HAS_NO_FLOOR, the row after
    "STATED": lambda iv, pts, t: [],   # the uncertainty column is each point's interval (S1 METHOD_NEEDS_UNCERTAINTY_COLUMN guarantees the column)
    "NONE": lambda iv, pts, t: [],   # no interval: the terminal's result is UNTIERED
}
ROUTES = 'Next: more readings per point; [interval] method = "STATED" (the uncertainty column is each point\'s interval); [interval] method = "NONE" (UNTIERED)'


def interval(census, t):
    """S7: ONE_READING_PER_POINT (a method that draws on a point's readings, and every point holds one) | BELOW_METHOD_FLOOR (CC's floor of
    the method finds a point short; the detail's Next names the three routes) | METHOD_HAS_NO_FLOOR (iid), in that order."""
    iv = census.pinned.declaration.data["interval"]
    m = iv["method"]
    pts = tuple((w, k, n) for (w, _), ns in zip(census.curves, census.readings) for k, n in enumerate(ns, 1))
    found = lambda: FLOOR[m](iv, pts, t)
    return gate([(lambda: not (REPLICATED[m] and census.label.readings[1] == 1), "ONE_READING_PER_POINT",
                  lambda: detail(words=[f"method {m}", ROUTES], counts={"points": len(pts), "readings per point max": census.label.readings[1]})),
                 (lambda: not found(), "BELOW_METHOD_FLOOR", lambda: detail(words=[f"method {m}", found()[0].msg, ROUTES], counts={"floor findings": len(found())})),
                 (lambda: HAS_FLOOR[m], "METHOD_HAS_NO_FLOOR", lambda: detail(words=[f"method {m}: its k* is undefined (plans 1134, 1117)", ROUTES]))],
                lambda: Pass(IntervalPlan(census, m, TIERING[m], pts)))


IDENTIFIABILITY = "TRANSITION_TOPOLOGY_NOT_IDENTIFIABLE_FROM_AVAILABLE_OBSERVABLES"   # A1.8, D7: FORMAT.toml holds ONE [measured] table, so every declaration has one observable
COVERAGE = ROOT / "intake" / "coverage" / "PRIMARY"   # frozen planted coverage evidence of the PRIMARY lane (the bracket's lane); none exists yet
COVERED = {"CANDIDATE_BRACKET": lambda: True, "VALIDATED_BRACKET": lambda: any(COVERAGE.glob("*"))}   # [bracket] required -> is it met; total over FORMAT's values
MAX_BRACKET = {True: "VALIDATED_BRACKET", False: "CANDIDATE_BRACKET"}   # is there frozen coverage evidence -> the most bracket the census permits


def resolution(census):
    """S8: TOO_FEW_CURVES (fewer than 3 curves carry a slow value) | TOO_FEW_POINTS_IN_CURVE (a curve of fewer than 3 points) |
    NO_COVERAGE_EVIDENCE (VALIDATED_BRACKET required and no file under intake/coverage/PRIMARY/: none exists, so today it always refuses)."""
    x, req = census.label, census.pinned.declaration.data["bracket"]["required"]
    few = [w for w, n in census.curves if n < 3]
    return gate([(lambda: x.with_slow >= 3, "TOO_FEW_CURVES", lambda: detail(counts={"curves with a slow value": x.with_slow, "needed": 3})),
                 (lambda: not few, "TOO_FEW_POINTS_IN_CURVE", lambda: detail(words=few[:3], counts={"curves with fewer than 3 points": len(few)})),
                 (COVERED[req], "NO_COVERAGE_EVIDENCE", lambda: detail(words=[f"[bracket] required {req}", "no frozen coverage file under intake/coverage/PRIMARY/"]))],
                lambda: Pass(Feasibility(census, MAX_BRACKET[any(COVERAGE.glob("*"))], IDENTIFIABILITY)))


def peak(c):
    """(the fast value at a curve's largest measured value, ties to the first row; the curve's fast span (lo, hi)). Rows are in role order."""
    top = max(range(len(c.rows)), key=lambda i: c.rows[i][1])
    return c.rows[top][0], (min(r[0] for r in c.rows), max(r[0] for r in c.rows))


DOMAIN = {   # (plan 1160 A39.1: was ENDS) a POLICY projection -> (the curves in slow order) -> the curves on which it is empty; total over POLICY's
    "ARGMAX_FAST": lambda cs: [c.where for c in cs if peak(c)[0] in peak(c)[1]],   # projections. The maximum sits at a fast end: no interior location
    "MAX_MEASURED": lambda cs: [],   # a height exists on every curve
}   # consulted by S9 for every ALTERNATIVE step and by S10 (cc/intake_terminal.py) for the PRIMARY projection
ANCHOR = {   # an ALTERNATIVE bridge's template -> the projection its anchor is (its domain is that projection's); total over POLICY's bridges
    "CHAIN_SLOW": "MAX_MEASURED",   # chains every curve in slow order: no anchor, never empty
    "PAIR_NEAREST_FAST": "ARGMAX_FAST",   # the anchor is the fast value at each curve's maximum
}
PAIRS = {   # an ALTERNATIVE bridge's template -> (the curves in slow order) -> the curves whose anchor lies outside a slow neighbour's fast span,
    "CHAIN_SLOW": lambda cs: [],   # distinct, in slow order (plan 1160 A39.3: the curve p whose anchor is outside); total over POLICY's bridges
    "PAIR_NEAREST_FAST": lambda cs: [c.where for c in cs if c.where in {p.where for a, b in zip(cs, cs[1:]) for p, q in ((a, b), (b, a)) if not peak(q)[1][0] <= peak(p)[0] <= peak(q)[1][1]}],
}
NEXT = {   # S9's refusal -> its Next (plan 1160 A39.2); total over S9's rows
    "NO_INTERIOR_FAST_MAXIMUM": "Next: robustness is unavailable, not mis-chosen: no location-anchored second lane exists on a family with no interior fast maximum; it needs a second observable",
    "ANCHOR_OUTSIDE_NEIGHBOUR_SPAN": "Next: the anchors are interior but a slow neighbour's fast span does not reach them (ragged or shifted grids): select curves on a common fast span, or bridge CHAIN_SLOW",
}


def second(census, t):
    """S9 (plan 1160 A39.2: was SECOND_LANE_INFEASIBLE): NO_INTERIOR_FAST_MAXIMUM when an ALTERNATIVE step's DOMAIN is empty on a curve (a
    projection's own; a bridge's anchor projection, ANCHOR) | ANCHOR_OUTSIDE_NEIGHBOUR_SPAN when an ALTERNATIVE bridge PAIR_NEAREST_FAST
    finds a curve's interior anchor outside a slow neighbour's fast span: structural emptiness, no tolerance. With no ALTERNATIVE lane
    (origin PLANTED needs one lane, S1), nothing is checked and it passes, with that said. A Detail: the step, <= 3 curves, {curves, of}, Next."""
    d = census.pinned.declaration.data
    files = census.pinned.files
    cs = sorted(intake_census.CURVES[d["selection"]["layout"]](d, files, [intake_census.read(t, d, f) for f in files]), key=lambda c: c.slow)
    steps = [(f"projection {p['bias']}", p["bias"], lambda cs: []) for p in d["projection"] if p["lane"] == "ALTERNATIVE"] + [
        (f"bridge {b['template']}", ANCHOR[b["template"]], PAIRS[b["template"]]) for b in d["bridge"] if b["lane"] == "ALTERNATIVE"]
    found = lambda rule: [(what, rule(dom, pair)) for what, dom, pair in steps if rule(dom, pair)]
    said = lambda code, got: lambda: detail(words=[got[0][0]] + got[0][1][:3] + [NEXT[code]], counts={"curves": len(got[0][1]), "of": len(cs)})
    empty, outside = found(lambda dom, pair: DOMAIN[dom](cs)), found(lambda dom, pair: pair(cs))
    return gate([(lambda: not empty, "NO_INTERIOR_FAST_MAXIMUM", said("NO_INTERIOR_FAST_MAXIMUM", empty)),
                 (lambda: not outside, "ANCHOR_OUTSIDE_NEIGHBOUR_SPAN", said("ANCHOR_OUTSIDE_NEIGHBOUR_SPAN", outside))],
                lambda: Pass(SecondLane(census, tuple(what for what, _, _ in steps), len({b["lane"] for b in d["bridge"]}))))


def bodies(t, d):
    """The registered bodies of S7, S8 and S9, closed over the tables. Each has exactly its SIGNATURE row (tests/test_intake.py)."""
    def s7(census: Census) -> Pass | Refuse:
        return interval(census, t)

    def s8(census: Census) -> Pass | Refuse:
        return resolution(census)

    def s9(census: Census) -> Pass | Refuse:
        return second(census, t)
    return {"S7": s7, "S8": s8, "S9": s9}
