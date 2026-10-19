"""intake_choices - stage S1 CHOICES of the intake (plan 1160 P4: every row; the rows of P1 and P2 moved here from intake_blind, under role
`intake_choices` with its own line cap, tests/test_budget.py CHOICES_CAP, so INTAKE_CAP is not raised).
Invariant (blindness, as intake_blind): it receives the parsed Declaration and the POLICY table as plain values and can open nothing; its
imports are dataclasses, intake_blind and intake_names (tests/test_intake.py checks them, and its calls, over the AST). Every check is a
lookup in a table total over its alphabet (tests/test_intake.py asserts each), the rows run in the order of STAGES.toml's live S1 rows, and a
refusal's detail carries declared names, words and counts, never a data value (it has none: S1 reads no byte)."""
from dataclasses import dataclass

from intake_blind import RESTARTS, SWEEP, Declaration, Evidence, Pass, gate, look
from intake_names import detail

ONE_PER_FILE = {   # [selection.slow] source -> does the declaration give one slow value per selected file; total over FORMAT's sources (test)
    "LISTED": lambda sel: len(sel["slow"]["values"]) == len(sel["files"]),
    "FILE_KEY": lambda sel: True,   # each file states its own value in a header line (S5 reads it there, or refuses SLOW_KEY_UNRESOLVED)
    "NONE": lambda sel: True,       # no slow knob: no value is declared, so none is missing or extra
    "COLUMN": lambda sel: True,     # LONG_TABLE: the slow knob is a column of the one file
}
DIRECTED = {   # [selection] layout -> does the curve rule of the declaration have the direction it needs; total over FORMAT's layouts (test)
    "PER_FILE": lambda d: True,   # a file is a curve
    "LONG_TABLE": lambda d: {"EXACT": True, "FAST_RESTART": SWEEP[d["acquisition"]["row_order"]](d["acquisition"]) in RESTARTS}[d["selection"]["block"]],
}
SLOW_PATH = {   # (plan 1160 A24) [selection.slow] source -> can a curve carry a slow value (S8 counts curves_with_slow); total over FORMAT's sources (test)
    "LISTED": True, "FILE_KEY": True, "COLUMN": True, "NONE": False,   # NONE: curves_with_slow = 0 under every layout, so S8 refuses TOO_FEW_CURVES
}
SELECTED = {   # [selection] layout -> how many files the declaration selects; total over FORMAT's layouts (test). Amendment A1 of plan 1160
    "PER_FILE": lambda sel: len(sel["files"]), "LONG_TABLE": lambda sel: 1,   # LONG_TABLE names its one `file`
}
SLOW_IDS = {   # [selection.slow] source -> the declaration -> what names the slow knob (its name, and the key or column it is read from); total
    "LISTED": lambda d: {d["knobs"]["slow"]["name"]},
    "FILE_KEY": lambda d: {d["knobs"]["slow"]["name"], str(d["selection"]["slow"]["key"])},
    "COLUMN": lambda d: {d["knobs"]["slow"]["name"], str(d["selection"]["slow"]["key"])},
    "NONE": lambda d: set(),   # no slow knob: nothing it could share with the fast knob or the measured number
}
SCALAR = {"SCALAR_PER_LOCUS": True, "SERIES_PER_LOCUS": False, "PICTURE": False, "POSITIONS": False}   # [measured] shape -> one number per locus; total
PERMITTED = {   # (a step's op, the link of the chain its input is in) -> may it take that input (plan 1136 A1: Raw -> Projection ->
    # DerivedObservable -> Bridge -> KernelInput); total over ({PROJECTION} | POLICY's bridges) x the links (test). NO_LINK: a name the chain does not hold
    ("PROJECTION", "RAW"): True, ("PROJECTION", "DERIVED_OBSERVABLE"): False, ("PROJECTION", "NO_LINK"): False,
    ("CHAIN_SLOW", "RAW"): False, ("CHAIN_SLOW", "DERIVED_OBSERVABLE"): True, ("CHAIN_SLOW", "NO_LINK"): False,   # chains one number per curve
    ("PAIR_NEAREST_FAST", "RAW"): True, ("PAIR_NEAREST_FAST", "DERIVED_OBSERVABLE"): False, ("PAIR_NEAREST_FAST", "NO_LINK"): False,   # joins locus values
}
LINK_WORDS = {"RAW": "RAW (the measured name)", "DERIVED_OBSERVABLE": "DERIVED_OBSERVABLE (the `to` of a projection of the same lane)", "NO_LINK": "NO_LINK"}   # total
WANTS = lambda op: " or ".join(LINK_WORDS[k] for (o, k), ok in PERMITTED.items() if o == op and ok)   # (plan 1160 A9) the link(s) PERMITTED lets an op take
LANES = {"PLANTED": lambda policy: 1, "EXPERIMENT": lambda policy: policy["policy"]["real_data_lanes"]}   # [source] origin -> lanes required; total
NEIGHBOUR = {   # [replicate] identity -> the declaration -> does the replicate key name the fast knob (a neighbouring point of one sweep); total
    "NONE": lambda d: False, "SAME_FAST_VALUE": lambda d: False,   # 1160 P2: readings at one fast value are one point, never neighbours
    **{k: (lambda d: d["replicate"]["key"] in {d["knobs"]["fast"]["name"], str(d["knobs"]["fast"]["key"])}) for k in ("SEED", "RUN", "SAMPLE", "FILE")},
}
ROUTE = {"RAW": True, "DECLARABLE": True, "FIGURE_LEVEL": False, "PROCESSED_UNDECLARABLE": False}   # [source] admissibility -> has a kernel route; total
NEEDS_COLUMN = {   # the intake's interval method (cc.toml alphabets.interval_method | STATED | NONE) -> does it need an uncertainty column; total (test)
    "block": False, "iid": False, "gamma": False, "chains": False, "STATED": True, "NONE": False,
}
HAS_COLUMN = {"COLUMN": True, "NONE": False}   # [measured.uncertainty] kind -> does the declaration name an uncertainty column; total
POINTED = {   # (plan 1160 A17) [knobs.fast] control -> (identity, interval method) -> do the declared points exist; total over FORMAT's controls (test)
    "SET": lambda identity, method: True,   # a grid: the identity names a point's readings, any method may draw on them
    "MEASURED": lambda identity, method: identity == "NONE" and method in ("STATED", "NONE"),   # every row a point: no readings to group or resample
}


@dataclass(frozen=True)
class Chosen(Evidence):
    """S1 CHOICES' PASS evidence. Invariant: built only from a Declaration for which every row in `checked` held; `checked` is exactly the
    S1 rows with live = true, in STAGES.toml order (tests/test_intake.py)."""
    declaration: Declaration
    checked: tuple

    def summary(self):
        return f"Checked: {', '.join(self.checked)}. The S1 rows that are not live are listed under the reasons no body can return yet"


def chain(d):
    """Every declared step as (what it is, its lane, op, input name, link): a projection takes `from`, a bridge takes `on`; a name's link is
    RAW when it is the measured name, DERIVED_OBSERVABLE when it is the `to` of a projection of the same lane, else NO_LINK."""
    link = lambda lane, name: look({**{p["to"]: "DERIVED_OBSERVABLE" for p in d["projection"] if p["lane"] == lane}, d["measured"]["name"]: "RAW"}, name, "NO_LINK")
    return ([("projection", p["lane"], "PROJECTION", p["from"], link(p["lane"], p["from"])) for p in d["projection"]]
            + [("bridge", b["lane"], b["template"], b["on"], link(b["lane"], b["on"])) for b in d["bridge"]])


def choices(declaration, policy):
    """S1 CHOICES (reads no byte): the declared choices against each other and against POLICY (`policy`, intake/POLICY.toml as values)."""
    d, sel = declaration.data, declaration.data["selection"]
    slow, fast = SLOW_IDS[sel["slow"]["source"]](d), {d["knobs"]["fast"]["name"], str(d["knobs"]["fast"]["key"])}
    measured = {d["measured"]["name"], str(d["measured"]["key"])}
    steps = chain(d)
    lanes = sorted({b["lane"] for b in d["bridge"]})
    estimands = lambda to: sorted({policy["projection"][p["bias"]]["estimand"] for p in d["projection"] if p["to"] == to})
    mixed = sorted({p["to"] for p in d["projection"] if len(estimands(p["to"])) > 1})
    form = lambda lane: (tuple(sorted(p["bias"] for p in d["projection"] if p["lane"] == lane)), tuple(sorted(b["template"] for b in d["bridge"] if b["lane"] == lane)))
    raw_bridges = [s for s in steps if s[0] == "bridge" and s[4] == "RAW"]
    barred = [s for s in steps if not PERMITTED[(s[2], s[4])]]
    method, kind = d["interval"]["method"], d["measured"]["uncertainty"]["kind"]
    rows = [(lambda: not slow & fast, "KNOBS_SAME_QUANTITY", lambda: detail(words=[f"slow '{n}' is also the fast knob" for n in sorted(slow & fast)])),
            (lambda: not measured & (slow | fast), "MEASURED_IS_A_KNOB", lambda: detail(words=[f"measured '{n}' is also a knob" for n in sorted(measured & (slow | fast))])),
            (lambda: SELECTED[sel["layout"]](sel) > 0, "SELECTION_EMPTY", lambda: detail(words=[f"layout {sel['layout']}"], counts={"files selected": 0})),   # A1: S4 reads files[0]
            (lambda: ONE_PER_FILE[sel["slow"]["source"]](sel), "SLOW_VALUES_NOT_ONE_PER_FILE",
             lambda: detail(counts={"files": len(sel["files"]), "slow values": len(sel["slow"]["values"])})),
            (lambda: SLOW_PATH[sel["slow"]["source"]], "SLOW_NONE_HAS_NO_PATH", lambda: detail(words=[f"layout {sel['layout']}", "slow source NONE"])),   # A24
            (lambda: DIRECTED[sel["layout"]](d), "BLOCK_RULE_HAS_NO_DIRECTION",   # plan 1160 P2: FAST_RESTART needs a direction
             lambda: detail(words=["block FAST_RESTART", "row_order ACQUISITION", f"direction {d['acquisition']['direction']}"])),
            (lambda: SCALAR[d["measured"]["shape"]] or not raw_bridges, "PROJECTION_REQUIRED",
             lambda: detail(words=[f"shape {d['measured']['shape']}"] + [f"{s[1]} bridge {s[2]} on '{s[3]}' (the raw observation)" for s in raw_bridges])),
            (lambda: not mixed, "PROJECTION_ESTIMAND_MIXED", lambda: detail(words=[f"to '{to}': {' | '.join(estimands(to))}" for to in mixed])),
            (lambda: len(lanes) >= LANES[d["source"]["origin"]](policy), "SECOND_LANE_MISSING",
             lambda: detail(words=[f"origin {d['source']['origin']}"] + lanes, counts={"lanes with a bridge": len(lanes), "lanes required": LANES[d["source"]["origin"]](policy)})),
            (lambda: len({form(lane) for lane in lanes}) == len(lanes), "LANES_IDENTICAL",
             lambda: detail(words=[f"{lane}: projection {', '.join(form(lane)[0]) or 'none'}; bridge {', '.join(form(lane)[1])}" for lane in lanes])),
            (lambda: not NEIGHBOUR[d["replicate"]["identity"]](d), "REPLICATE_IS_SWEEP_NEIGHBOUR",
             lambda: detail(words=[f"identity {d['replicate']['identity']}", f"key '{d['replicate']['key']}' is the fast knob {d['knobs']['fast']['name']}"])),
            (lambda: POINTED[d["knobs"]["fast"]["control"]](d["replicate"]["identity"], method), "MEASURED_KNOB_HAS_NO_POINTS",   # plan 1160 A17
             lambda: detail(words=[f"control {d['knobs']['fast']['control']}", f"identity {d['replicate']['identity']}", f"interval method {method}"])),
            (lambda: not barred, "OPERATION_NOT_PERMITTED", lambda: detail(words=[f"{s[1]} {s[0]} {s[2]} on '{s[3]}' ({s[4]}; it is permitted on {WANTS(s[2])})" for s in barred][:3], counts={"steps not permitted": len(barred)})),
            (lambda: ROUTE[d["source"]["admissibility"]], "PROVENANCE_HAS_NO_KERNEL_ROUTE", lambda: detail(words=[f"admissibility {d['source']['admissibility']}"])),
            (lambda: not NEEDS_COLUMN[method] or HAS_COLUMN[kind], "METHOD_NEEDS_UNCERTAINTY_COLUMN", lambda: detail(words=[f"interval method {method}", f"uncertainty {kind}"]))]
    return gate(rows, lambda: Pass(Chosen(declaration, tuple(r[1] for r in rows))))
