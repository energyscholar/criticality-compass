"""Plan 1533 — the tables of report schema 2 (contract/SCHEMA-1533.md), pure. No process, no socket, no file but the
schema text. FROZEN: the Generator makes this green; it does not edit this file.

What it pins:
  1. ONE alphabet: the table in SCHEMA-1533.md and the tuples in navigator/steer.py name the same tokens, no token
     twice (case ignored), and no shipped name with another meaning is reused;
  2. the reading class is the position of an interval against 0, and its UNRES is exactly narrow()'s near-zero rule;
  3. the scan table is total over the 9 cells and both ordered sides, equals an oracle written from what each resolved
     end says, reaches four kinds (a constant verdict fails), and mirrors when the declared order mirrors;
  4. the outcome is a fold of the SET of step kinds: unanimity or UNDECIDED; no step = floor; a missing reading = budget;
  5. the belief is the declaration as received: declared values verbatim, `unknown` for every slot not declared,
     nothing invented, the input untouched;
  6. mode and sigma: OFF = no `nudge` held (it may scan); sigma is an unsigned offset in units of g, 0 here;
  7. the record builders write exactly the declared keys.

RED until navigator/steer.py and navigator/report2.py exist.
Run from the repo root:  python contract/test_report2_table.py   (or pytest)
"""
import ast
import copy
import itertools
import math
import re
import sys
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

READING = ("SIG-", "UNRES", "SIG+")
STEP_KINDS = ("narrow", "lean-lo", "lean-hi", "unresolved", "not-evaluated")
OUTCOME_KINDS = ("Located", "PAST-LO", "PAST-HI", "UNDECIDED", "REFUSE")
SLOTS = ("knobs_K", "ordered_side", "L", "tau", "k", "index_unit", "index_kind", "observable", "nlev", "system", "roles")
FAMILIES = {
    "reading": READING + ("n/e",),
    "step kind": STEP_KINDS,
    "outcome kind": OUTCOME_KINDS,
    "refuse reason": ("floor", "budget"),
    "phase": ("bracketing",),
    "mode": ("OFF", "ON"),
    "wire op": ("declare", "measure", "nudge"),
    "belief": ("unknown",),
    "sigma": ("g", "not-defined"),
    "score cell": ("HIT", "LEAN-TRUE", "LEAN-FALSE", "MISS", "NO-CALL", "REFUSED"),
    "truth side": ("below-range", "inside", "above-range"),
    "ordered side": ("+K", "-K"),
}
SHIPPED_WITH_ANOTHER_MEANING = ("absent", "line", "point", "edge", "edge lo", "edge hi")
DECLARED_3A = {"op": "declared", "knobs_K": [0.2, 0.5], "ordered_side": "+K", "L": 81, "tau": 67.0, "k": 6,
               "index_unit": "sweep", "index_kind": "sample_counter", "observable": "moments", "nlev": 2}
FLIP = {"SIG-": "SIG+", "UNRES": "UNRES", "SIG+": "SIG-"}


def _steer():
    from navigator import steer
    return steer


def _records():
    from navigator import report2
    return report2


def _schema_alphabet():
    text = (ROOT / "contract" / "SCHEMA-1533.md").read_text()
    block = text.split("<!-- alphabet:begin -->")[1].split("<!-- alphabet:end -->")[0]
    rows = re.findall(r"^\| `([^`]+)` \| ([a-z ]+) \|", block, flags=re.M)
    assert rows, "the alphabet table has no rows"
    return rows


def _oracle_class(d, s, z):
    return "UNRES" if abs(d) <= z * s else ("SIG+" if d > 0 else "SIG-")


def _oracle_scan(lo, hi, side):
    if side == "-K":
        lo, hi = FLIP[lo], FLIP[hi]
    below_lo, above_lo, above_hi, below_hi = lo == "SIG+", lo == "SIG-", hi == "SIG-", hi == "SIG+"
    if below_lo and above_hi:
        return "unresolved"
    if below_lo:
        return "lean-lo"
    if above_hi:
        return "lean-hi"
    return "narrow" if above_lo and below_hi else "unresolved"


def _oracle_outcome(kinds):
    if not kinds:
        return "REFUSE", "floor"
    if "not-evaluated" in kinds:
        return "REFUSE", "budget"
    said = [k for k in STEP_KINDS if k in kinds]
    one = {"narrow": ("Located", None), "lean-lo": ("PAST-LO", "lean-lo"), "lean-hi": ("PAST-HI", "lean-hi")}
    return one[said[0]] if len(said) == 1 and said[0] in one else ("UNDECIDED", "+".join(said))


def test_t01_one_alphabet_no_token_twice():
    rows = _schema_alphabet()
    tokens = [t for t, _ in rows]
    folded = [t.lower() for t in tokens]
    twice = sorted({t for t in folded if folded.count(t) > 1})
    assert not twice, f"a token is named twice in the alphabet table (case ignored): {twice}"
    reused = sorted(set(folded) & set(SHIPPED_WITH_ANOTHER_MEANING))
    assert not reused, f"a shipped name with another meaning is reused: {reused}"
    by_family = {}
    for token, family in rows:
        by_family.setdefault(family.strip(), []).append(token)
    assert {f: tuple(v) for f, v in by_family.items()} == FAMILIES, by_family


def test_t02_the_module_names_the_same_alphabet():
    S = _steer()
    assert S.READING == READING and S.NOT_EVALUATED == "n/e"
    assert S.STEP_KINDS == STEP_KINDS and S.OUTCOME_KINDS == OUTCOME_KINDS
    assert S.REFUSE_REASONS == ("floor", "budget") and S.PHASES == ("bracketing",) and S.MODES == ("OFF", "ON")
    assert S.NUDGE == "nudge" and S.ORDERED_SIDES == ("+K", "-K")
    assert S.SLOTS == SLOTS and S.UNKNOWN == "unknown" and S.SIGMA_UNIT == "g" and S.SIGMA_MEASURED == "not-defined"


def test_t03_reading_class_is_an_interval_position():
    S = _steer()
    for z, d, s in itertools.product((2.0, 0.5, 3.0), (-3.0, -2.0, -1.0, -0.0, 0.0, 1e-300, 1.0, 2.0, 3.0, 250.0), (0.0, 0.5, 1.0, 1.5)):
        assert S.end_class(d, s, z) == _oracle_class(d, s, z), (d, s, z)
    assert S.end_class(1.0, 1.0, 0.5) == "SIG+" and S.end_class(1.0, 1.0, 3.0) == "UNRES", "z is the declared one, not a constant"
    assert S.end_classes([-1.0, 0.0, 1.0], [[0.6, 0.8], [0.0, 0.0], [0.6, 0.8]], 0.5) == ("SIG-", "SIG+")
    assert S.end_classes([-1.0, 0.0, 1.0], [[0.6, 0.8], [0.0, 0.0], [0.6, 0.8]], 3.0) == ("UNRES", "UNRES")
    assert S.end_class(2.0, 1.0, 2.0) == "UNRES" and S.end_class(-2.0, 1.0, 2.0) == "UNRES", "the boundary is unresolved"
    assert S.end_class(0.0, 0.0, 2.0) == "UNRES"
    cases = (([-0.4, 0.0, 0.3], [[0.03, 0.04], [9.0, 9.0], [0.03, 0.04]]), ([-0.1, 0.0, 0.1], [[0.03, 0.04], [0.0, 0.0], [0.3, 0.4]]),
             ([-0.1, 0.5, 0.1], [[0.3, 0.4], [0.0, 0.0], [0.03, 0.039]]), ([0.2, -0.5, -0.2], [[0.0, 0.01], [0.0, 0.0], [0.01, 0.0]]))
    for D, err in cases:
        want = tuple(_oracle_class(D[i], math.sqrt(err[i][1] ** 2 + err[i][0] ** 2), 2.0) for i in (0, -1))
        assert S.end_classes(D, err, 2.0) == want, (D, err, want)
    assert S.end_classes(*cases[0], 2.0) == ("SIG-", "SIG+") and S.end_classes(*cases[3], 2.0) == ("SIG+", "SIG-")
    assert S.end_classes(*cases[2], 2.0) == ("UNRES", "SIG+"), "only the two ends are read"


def test_t04_the_scan_table_is_total_and_not_constant():
    S = _steer()
    seen = {}
    for side in ("+K", "-K"):
        for lo, hi in itertools.product(READING, READING):
            kind, reason = S.scan_verdict(lo, hi, side)
            assert kind == _oracle_scan(lo, hi, side), (side, lo, hi, kind)
            assert reason == f"{lo}|{hi}", (side, lo, hi, reason)
            seen.setdefault(side, set()).add(kind)
    for side, kinds in seen.items():
        assert kinds == {"narrow", "lean-lo", "lean-hi", "unresolved"}, (side, kinds)
    assert S.scan_verdict("SIG-", "SIG+", "+K")[0] == "narrow" and S.scan_verdict("SIG+", "SIG-", "-K")[0] == "narrow"
    assert S.scan_verdict("SIG-", "SIG-", "+K")[0] == "lean-hi" and S.scan_verdict("SIG+", "SIG+", "+K")[0] == "lean-lo"
    assert S.not_evaluated() == ("not-evaluated", "n/e")


def test_t05_the_table_mirrors_with_the_declared_order():
    S = _steer()
    turn = {"narrow": "narrow", "unresolved": "unresolved", "lean-lo": "lean-hi", "lean-hi": "lean-lo"}
    for lo, hi in itertools.product(READING, READING):
        # the same physical line read with K reversed: the ends swap and the ordered side flips
        assert S.scan_verdict(hi, lo, "-K")[0] == turn[S.scan_verdict(lo, hi, "+K")[0]], (lo, hi)
        assert S.scan_verdict(FLIP[lo], FLIP[hi], "-K")[0] == S.scan_verdict(lo, hi, "+K")[0], (lo, hi)
    for bad in ("K+", "", None, "+k"):
        try:
            S.scan_verdict("SIG-", "SIG+", bad)
        except KeyError:
            continue
        raise AssertionError(f"ordered side {bad!r} has a cell; the table must have none")


def test_t06_the_outcome_is_a_fold_of_the_set_of_kinds():
    S = _steer()
    for n in range(0, 4):
        for kinds in itertools.product(STEP_KINDS, repeat=n):
            assert S.outcome(list(kinds)) == _oracle_outcome(kinds), kinds
    assert S.outcome(["narrow"] * 5) == ("Located", None)
    assert S.outcome(["lean-hi"] * 5) == ("PAST-HI", "lean-hi") and S.outcome(["lean-lo"]) == ("PAST-LO", "lean-lo")
    assert S.outcome(["lean-hi", "narrow", "lean-hi"]) == ("UNDECIDED", "narrow+lean-hi")
    assert S.outcome(["unresolved"] * 3) == ("UNDECIDED", "unresolved")
    assert S.outcome([]) == ("REFUSE", "floor") and S.outcome(["narrow", "not-evaluated"]) == ("REFUSE", "budget")
    assert {S.outcome(list(k))[0] for k in itertools.product(STEP_KINDS, repeat=2)} == set(OUTCOME_KINDS)


def test_t07_the_belief_is_the_declaration_as_received():
    P = _records()
    got = P.belief(DECLARED_3A)
    assert tuple(got) == SLOTS, tuple(got)
    for slot in SLOTS[:9]:
        assert got[slot] == {"declared": DECLARED_3A[slot]}, (slot, got[slot])
    assert got["system"] == "unknown" and got["roles"] == "unknown", "the 3a wire declares neither; nothing is invented"
    assert P.declared_other(DECLARED_3A) == {}
    assert P.belief({}) == {s: "unknown" for s in SLOTS} and P.declared_other({}) == {}


def test_t08_every_undeclared_slot_is_unknown_and_nothing_is_filled():
    P = _records()
    for slot in SLOTS[:9]:
        fields = {k: v for k, v in DECLARED_3A.items() if k != slot}
        got = P.belief(fields)
        assert got[slot] == "unknown", f"{slot} was not declared and reads {got[slot]!r}"
        assert all(got[s] == {"declared": fields[s]} for s in SLOTS[:9] if s != slot), slot
    odd = {"nlev": None, "tau": "unknown", "k": False, "L": 0, "system": {"name": ["x", 1]}, "roles": [],
           "zz_extra": [1, "a", None], "op": "declared", "index": 0}
    before = copy.deepcopy(odd)
    got = P.belief(odd)
    assert got["nlev"] == {"declared": None} and got["tau"] == {"declared": "unknown"}, "a declared value is never the bare token"
    assert got["k"] == {"declared": False} and got["L"] == {"declared": 0} and got["roles"] == {"declared": []}
    assert got["system"] == {"declared": {"name": ["x", 1]}} and got["knobs_K"] == "unknown"
    assert P.declared_other(odd) == {"zz_extra": [1, "a", None], "index": 0}, "undeclared-slot keys are kept verbatim; op is the envelope"
    assert odd == before, "the declaration was changed"


def test_t09_mode_is_the_ops_held_and_off_may_scan():
    S = _steer()
    assert S.mode_of(("declare", "measure")) == "OFF", "a client with no nudge is OFF even though it places the knob"
    assert S.mode_of(("declare", "read")) == "OFF" and S.mode_of(()) == "OFF"
    assert S.mode_of(("declare", "read", "nudge")) == "ON" and S.mode_of(["nudge"]) == "ON"


def test_t10_the_records_hold_exactly_their_keys():
    P = _records()
    cfg = SimpleNamespace(bracket=(0.2, 0.5), m=9, N=5, n_eq=450, S=2000, skip=1, z=2.0)
    start = P.start("recover-adaptive-v1", cfg, ("declare", "measure"), (), dict(DECLARED_3A, zz=1))
    assert tuple(start) == ("rec", "schema", "needle", "settings", "mode", "sigma", "dials", "belief", "declared_other"), tuple(start)
    assert start["dials"] == [] and P.start("x", cfg, ("declare", "nudge"), ("K", "p"), {})["dials"] == ["K", "p"]
    assert start["rec"] == "start" and start["schema"] == "compass-report/2" and start["needle"] == "recover-adaptive-v1"
    assert start["settings"] == {"bracket": [0.2, 0.5], "m": 9, "N": 5, "n_eq": 450, "S": 2000, "skip": 1, "z": 2.0,
                                 "detectors": [{"name": "A", "role": "peak", "reads": "C"},
                                               {"name": "B", "role": "crossing", "reads": "Gs"}]}, start["settings"]
    assert start["mode"] == {"ops": ["declare", "measure"], "feedback": "OFF"}, start["mode"]
    assert start["sigma"] == {"offset": 0, "unit": "g", "measured": "not-defined"}, start["sigma"]
    assert type(start["sigma"]["offset"]) is int
    assert start["belief"] == P.belief(DECLARED_3A) and start["declared_other"] == {"zz": 1}
    scan = {"round": 3, "grid": [0.2, 0.5], "C": None, "C_err": None, "Gs": None, "Gs_err": None, "D": None, "A": None,
            "B": None, "lo": 0.2, "hi": 0.5, "index": 77, "evaluated": False}
    step = P.step(scan, ("not-evaluated", "n/e"))
    assert step == {"rec": "step", "step": 3, "phase": "bracketing", "index": 77, "evaluated": False,
                    "verdict": [{"kind": "not-evaluated", "reason": "n/e", "dial": None, "ticks": None}], "scan": scan}, step
    assert tuple(step) == ("rec", "step", "phase", "index", "evaluated", "verdict", "scan")
    v1 = {"kind": "Located", "reason": None, "bracket": [0.3, 0.4], "A_hull": [0.31, 0.32], "B_hull": None, "agree": False,
          "rounds": []}
    out = P.outcome("Located", None, v1, 5)
    assert out == {"rec": "outcome", "kind": "Located", "reason": None, "bracket": [0.3, 0.4], "A_hull": [0.31, 0.32],
                   "B_hull": None, "agree": False, "steps": 5}, out
    assert tuple(out) == ("rec", "kind", "reason", "bracket", "A_hull", "B_hull", "agree", "steps")
    away = P.outcome("PAST-HI", "lean-hi", {}, 5)
    assert away == {"rec": "outcome", "kind": "PAST-HI", "reason": "lean-hi", "bracket": None, "A_hull": None,
                    "B_hull": None, "agree": None, "steps": 5}, away


def test_t11_the_tables_are_pure():
    allowed = {"navigator/steer.py": {"math"}, "navigator/report2.py": {"navigator"}}
    for rel, ok in allowed.items():
        tree = ast.parse((ROOT / rel).read_text())
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                assert all(a.name.split(".")[0] in ok for a in node.names), (rel, [a.name for a in node.names])
            if isinstance(node, ast.ImportFrom):
                assert node.level == 0 and (node.module or "").split(".")[0] in ok, (rel, node.module)
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                assert node.func.id not in ("open", "print", "input", "__import__", "exec", "eval"), (rel, node.func.id)
    assert math.isfinite(1.0)


if __name__ == "__main__":
    _tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    _fail = 0
    for _t in _tests:
        try:
            _t(); print(f"PASS {_t.__name__}")
        except Exception as _e:  # noqa: BLE001
            _fail += 1; print(f"FAIL {_t.__name__}: {type(_e).__name__}: {str(_e)[:300]}")
    print(f"{len(_tests) - _fail}/{len(_tests)} passed")
    sys.exit(1 if _fail else 0)
