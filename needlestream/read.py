"""Plan 1533: the reader of a needle report, schema 1 and schema 2 (contract/SCHEMA-1533.md).

Pure: it opens nothing and prints nothing, and `read` never raises. Every input is a Stream or an Unreadable. A schema-1
report is validated by the one schema-1 reader (needleview.report) and lifted into the same shape. A schema-2 stream is
held to the needle's own tables: a verdict that is not the table's verdict for that step's numbers makes it Unreadable.
"""
import json
from dataclasses import dataclass
from typing import Union

from navigator import report2 as P
from navigator import steer as T
from needleview import report as V1

START_KEYS = frozenset(("rec", "schema", "needle", "settings", "mode", "sigma", "dials", "belief", "declared_other"))
SETTINGS_KEYS = frozenset(("bracket", "m", "N", "n_eq", "S", "skip", "z", "detectors"))
STEP_KEYS = frozenset(("rec", "step", "phase", "index", "evaluated", "verdict", "scan"))
VERDICT_KEYS = frozenset(("kind", "reason", "dial", "ticks"))
OUTCOME_KEYS = frozenset(("rec", "kind", "reason", "bracket", "A_hull", "B_hull", "agree", "steps"))
FOUR = ("bracket", "A_hull", "B_hull", "agree")


class _Name:
    def __init__(self, name):
        self._name = name

    def __repr__(self):
        return self._name


NOT_REPORTED = _Name("NOT_REPORTED")
PENDING = _Name("PENDING")


@dataclass(frozen=True)
class Verdict:
    kind: str
    reason: str
    dial: Union[str, None]
    ticks: Union[int, None]


@dataclass(frozen=True)
class Step:
    step: int
    phase: str
    index: int
    evaluated: bool
    verdict: object
    scan: dict


@dataclass(frozen=True)
class Start:
    needle: str
    settings: dict
    mode: dict
    sigma: dict
    dials: tuple
    belief: dict
    declared_other: dict


@dataclass(frozen=True)
class Outcome:
    kind: str
    reason: Union[str, None]
    bracket: object
    A_hull: object
    B_hull: object
    agree: object
    steps: int


@dataclass(frozen=True)
class Stream:
    schema: int
    start: object
    steps: tuple
    outcome: object


@dataclass(frozen=True)
class Unreadable:
    why: str


class _Refused(Exception):
    """internal: a text that cannot be read; read turns it into an Unreadable value."""


def _no(why):
    raise _Refused(why)


def _is_int(v):
    return type(v) is int


def _is_float(v):
    return type(v) is float and v == v and v not in (float("inf"), float("-inf"))


def _keys(obj, keys, name):
    if type(obj) is not dict or set(obj) != keys:
        _no(f"{name} does not hold exactly its keys")
    return obj


def _strings(v, name):
    if type(v) is not list or not all(type(x) is str for x in v) or len(set(v)) != len(v):
        _no(f"{name} is not a list of distinct strings")
    return tuple(v)


def _settings(s):
    _keys(s, SETTINGS_KEYS, "settings")
    br = s["bracket"]
    if type(br) is not list or len(br) != 2 or not all(_is_float(x) for x in br) or not br[0] < br[1]:
        _no("settings.bracket is not [lo, hi] floats with lo < hi")
    if not all(_is_int(s[k]) and s[k] >= 1 for k in ("m", "N", "n_eq", "S", "skip")):
        _no("settings m, N, n_eq, S, skip are not ints >= 1")
    if not (_is_float(s["z"]) and s["z"] > 0):
        _no("settings.z is not a float > 0")
    if s["detectors"] != P.detectors():
        _no("settings.detectors are not this needle's detectors")
    return s


def _start(o):
    _keys(o, START_KEYS, "the start record")
    if o["rec"] != "start" or o["schema"] != P.SCHEMA:
        _no(f"the start record is not schema {P.SCHEMA}")
    if o["needle"] != T.NEEDLE_V1:
        _no(f"needle {o['needle']!r} is not read by this reader")
    settings = _settings(o["settings"])
    mode = _keys(o["mode"], frozenset(("ops", "feedback")), "mode")
    ops = _strings(mode["ops"], "mode.ops")
    if mode["feedback"] != T.mode_of(ops):
        _no("mode.feedback is not the mode of the ops held")
    sigma = _keys(o["sigma"], frozenset(("offset", "unit", "measured")), "sigma")
    if not (_is_int(sigma["offset"]) and sigma["offset"] >= 0):
        _no("sigma.offset is not an int >= 0")
    if sigma["unit"] != T.SIGMA_UNIT or sigma["measured"] != T.SIGMA_MEASURED:
        _no("sigma is not an offset in units of g with no measured definition")
    dials = _strings(o["dials"], "dials")
    belief = _keys(o["belief"], frozenset(T.SLOTS), "belief")
    for slot, v in belief.items():
        if v != T.UNKNOWN and (type(v) is not dict or set(v) != {"declared"}):
            _no(f"belief.{slot} is neither unknown nor a declared value")
    side = belief["ordered_side"]
    if not (type(side) is dict and side.get("declared") in T.ORDERED_SIDES):
        _no("belief.ordered_side is not a declared side this reader knows")
    other = o["declared_other"]
    if type(other) is not dict or any(k in T.SLOTS or k == "op" for k in other):
        _no("declared_other is not a table of keys that are not slots")
    return Start(o["needle"], settings, mode, sigma, dials, belief, other)


def _verdict_record(rec, i):
    v = rec["verdict"]
    if type(v) is not list or len(v) != 1:
        _no(f"step {i}: a bracketing step holds exactly one verdict")
    _keys(v[0], VERDICT_KEYS, f"step {i} verdict")
    if v[0]["dial"] is not None or v[0]["ticks"] is not None:
        _no(f"step {i}: a bracketing verdict holds no dial and no ticks")
    return v[0]


def _step(rec, i):
    _keys(rec, STEP_KEYS, f"step record {i}")
    if rec["rec"] != "step" or not _is_int(rec["step"]) or rec["step"] != i:
        _no(f"step record {i} is numbered {rec['step']!r}")
    if rec["phase"] not in T.PHASES:
        _no(f"step {i}: phase {rec['phase']!r} is not read by this reader")
    scan = rec["scan"]
    if type(scan) is not dict:
        _no(f"step {i}: scan is not an object")
    if rec["index"] != scan.get("index") or rec["evaluated"] != scan.get("evaluated"):
        _no(f"step {i}: index or evaluated is not its scan's")
    return _verdict_record(rec, i)


def _candidate(scans):
    """a schema-1 report holding these rounds, so the schema-1 reader validates them. None when there is no round."""
    done = bool(scans) and all(s.get("evaluated") is True for s in scans)
    if done:
        lo, hi = scans[-1].get("lo"), scans[-1].get("hi")
        return {"kind": T.LOCATED, "reason": None, "bracket": [lo, hi], "A_hull": [lo, hi], "B_hull": None, "agree": False,
                "rounds": scans}
    return {"kind": T.REFUSE, "reason": T.REFUSE_REASONS[1], "bracket": None, "A_hull": None, "B_hull": None, "agree": None,
            "rounds": scans}


def _rounds_valid(scans):
    run = V1.parse("", json.dumps(_candidate(scans)), False) if scans else None
    if isinstance(run, V1.Unreadable):
        _no(run.why)


def _chain(start, scans):
    """the first grid is the declared bracket; each grid is the bracket the step before it left."""
    ends = [tuple(start.settings["bracket"])] + [(s["lo"], s["hi"]) for s in scans[:-1]]
    for i, (s, want) in enumerate(zip(scans, ends), 1):
        if (s["grid"][0], s["grid"][-1]) != want:
            _no(f"step {i}: the grid does not start where the bracket before it ended")


def _verdicts(start, scans, records):
    z, side = start.settings["z"], start.belief["ordered_side"]["declared"]
    out = []
    for i, (scan, v) in enumerate(zip(scans, records), 1):
        want = T.scan_verdict(*T.end_classes(scan["D"], scan["Gs_err"], z), side) if scan["evaluated"] else T.not_evaluated()
        if (v["kind"], v["reason"]) != want:
            _no(f"step {i}: the verdict {(v['kind'], v['reason'])!r} is not the table's verdict {want!r} for its numbers")
        out.append(Verdict(v["kind"], v["reason"], None, None))
    return out


def _outcome(o, steps, kinds, scans):
    _keys(o, OUTCOME_KEYS, "the outcome record")
    kind, reason = T.outcome(kinds)
    if o["rec"] != "outcome" or (o["kind"], o["reason"]) != (kind, reason):
        _no(f"the outcome {(o['kind'], o['reason'])!r} is not the fold {(kind, reason)!r} of the step kinds")
    if not _is_int(o["steps"]) or o["steps"] != steps:
        _no("the outcome does not count its steps")
    if kind != T.LOCATED and any(o[k] is not None for k in FOUR):
        _no(f"a {kind} outcome carries a bracket, hull or agree")
    if kind in (T.LOCATED, T.REFUSE):
        run = V1.parse("", json.dumps({**{k: o[k] for k in ("kind", "reason") + FOUR}, "rounds": scans}), False)
        if isinstance(run, V1.Unreadable):
            _no(run.why)
    return Outcome(o["kind"], o["reason"], o["bracket"], o["A_hull"], o["B_hull"], o["agree"], o["steps"])


def _lines(text):
    if not text.endswith("\n"):
        _no("the last line has no line end")
    out = []
    for n, line in enumerate(text.split("\n")[:-1], 1):
        obj = json.loads(line)
        if type(obj) is not dict:
            _no(f"line {n} is not a JSON object")
        out.append(obj)
    return out


def _read2(text):
    recs = _lines(text)
    if recs[0].get("rec") != "start":
        _no("the first record is not a start record")
    start = _start(recs[0])
    body = recs[1:]
    stepped = 0
    while stepped < len(body) and body[stepped].get("rec") == "step":
        stepped += 1
    tail = body[stepped:]
    if len(tail) > 1 or (tail and tail[0].get("rec") != "outcome"):
        _no("records follow the steps that are not one outcome record")
    verdict_records = [_step(rec, i) for i, rec in enumerate(body[:stepped], 1)]
    scans = [rec["scan"] for rec in body[:stepped]]
    if len(scans) > start.settings["N"]:
        _no("more steps than settings.N")
    if any(s.get("evaluated") is not True for s in scans[:-1]):
        _no("a step follows a step that was not evaluated")
    _rounds_valid(scans)
    _chain(start, scans)
    verdicts = _verdicts(start, scans, verdict_records)
    steps = tuple(Step(rec["step"], rec["phase"], rec["index"], rec["evaluated"], (v,), rec["scan"])
                  for rec, v in zip(body[:stepped], verdicts))
    outcome = _outcome(tail[0], len(steps), [v.kind for v in verdicts], scans) if tail else PENDING
    return Stream(2, start, steps, outcome)


def _lift(obj, text):
    run = V1.parse("", text, False)
    if isinstance(run, V1.Unreadable):
        _no(run.why)
    steps = tuple(Step(r["round"], T.PHASES[0], r["index"], r["evaluated"], NOT_REPORTED, r) for r in obj["rounds"])
    out = Outcome(obj["kind"], obj["reason"], obj["bracket"], obj["A_hull"], obj["B_hull"], obj["agree"], len(steps))
    return Stream(1, NOT_REPORTED, steps, out)


def _whole(text):
    try:
        return json.loads(text)
    except (ValueError, RecursionError):
        return None


def _read(text):
    if type(text) is not str:
        _no("the input is not text")
    whole = _whole(text)
    if type(whole) is dict and "rec" not in whole:
        return _lift(whole, text)
    return _read2(text)


def read(text):
    """text -> Stream | Unreadable. Never raises, opens nothing."""
    try:
        return _read(text)
    except _Refused as e:
        return Unreadable(str(e))
    except (ValueError, RecursionError, TypeError, KeyError, AttributeError, IndexError) as e:
        return Unreadable(f"not readable ({type(e).__name__})")


def fold_v1(stream):
    """the seven keys of a schema-1 report, or PENDING while the stream has no outcome."""
    o = stream.outcome
    if o is PENDING:
        return PENDING
    return {"kind": o.kind, "reason": o.reason, "bracket": o.bracket, "A_hull": o.A_hull, "B_hull": o.B_hull,
            "agree": o.agree, "rounds": [s.scan for s in stream.steps]}
