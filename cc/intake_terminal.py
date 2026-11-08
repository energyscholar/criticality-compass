"""intake_terminal - S10 KERNEL_HANDOFF and the terminal of the intake (plan 1160 P6; role intake_terminal with its own cap,
tests/test_budget.py TERMINAL_CAP, so INTAKE_CAP is not raised). The terminal is plan 1118's REDUCE expressed as A over a declared chain:
per PRIMARY bridge, the projection gives one number r_k per curve (MAX_MEASURED: the curve's largest measured reading; ARGMAX_FAST: the fast
value at it, ties to the first row in stored order), [shift] c is added here and only here (x + c), the curves in slow order are the nodes of
CC's chain relation (door.TEMPLATES["chain"], admit.declare), the door admits the values (door.nodefield: a non-finite value is a Null), and
kernel.A gives the edges e_k = r_{k+1} - r_k. Nothing between measured points is ever formed: every result names curves by rank.
Invariant: every dispatch is a dict total over its alphabet (tests/test_intake.py); a refusal's detail carries names, words and counts, never a
value; RESULT.json (declarations/<id>/RESULT.json) holds the span's slow values, and the report never does."""
import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np

import admit
import door
import intake_census
import intake_feasible
import intake_seal
import kernel
import schema
from intake_blind import Mark, Pass, Refuse, detail, gate
from intake_evidence import Feasibility, IntervalPlan, KernelInput, Lineage
import registry

ROUTE = {"CHAIN_SLOW": "chain", "PAIR_NEAREST_FAST": "pair-nearest-fast"}   # POLICY bridge -> its door template name; total (test). Only "chain" is in door.TEMPLATES
VALUE = {"MAX_MEASURED": lambda c, i: c.rows[i][1], "ARGMAX_FAST": lambda c, i: c.rows[i][0]}   # POLICY projection -> (curve, its max row) -> r_k; total
LOCATE = {   # POLICY projection -> (the edges e, r) -> the interior candidate nodes (plan 1118: REDUCE takes the global maximum, PAIR the local maxima); total
    "MAX_MEASURED": lambda e, r: [int(np.argmax(r))],   # ties -> the lowest rank
    "ARGMAX_FAST": lambda e, r: [int(k) for k in (np.flatnonzero((e[:-1] > 0) & (e[1:] < 0)) + 1)[np.argsort(-r[np.flatnonzero((e[:-1] > 0) & (e[1:] < 0)) + 1], kind="stable")]],
}
SD = {True: lambda xs: float(np.std(xs, ddof=1)), False: lambda xs: float("nan")}   # n >= 2 readings -> their sample SD; one reading has none: a NaN the door refuses
SIGMA = {   # (projection, S7 tiering) -> (curves, their max rows) -> (sigma per curve at its maximum,) or () (UNTIERED); total over POLICY's projections x tierings
    ("MAX_MEASURED", "STATED"): lambda cs, top: (np.array([c.rows[i][2] for c, i in zip(cs, top)]),),   # the uncertainty column (S1 METHOD_NEEDS_UNCERTAINTY_COLUMN)
    ("MAX_MEASURED", "REPLICATES"): lambda cs, top: (np.array([(lambda xs: SD[len(xs) >= 2](xs))([r[1] for r in c.rows if r[0] == c.rows[i][0]]) for c, i in zip(cs, top)]),),
    ("MAX_MEASURED", "NONE"): lambda cs, top: (),   # REPLICATES: the readings at the maximum's fast value (one run of it: S5 FAST_VALUE_REPEATED)
    **{("ARGMAX_FAST", k): (lambda cs, top: ()) for k in ("STATED", "REPLICATES", "NONE")},   # a stated sigma is the measured value's, not a location's: no tier
}
TIER = {True: "RESOLVED", False: "EXPLORATORY"}
HONEST = {   # S8 max_bracket -> why the tier is what it may claim (plan 1160 E8); total over FORMAT's bracket values
    "CANDIDATE_BRACKET": "No frozen coverage evidence exists for the PRIMARY lane (S8: at most CANDIDATE_BRACKET), so no tier here is a coverage claim. "
                         "RESOLVED says only that both edges flanking the maximum exceed Z sigma on this bank; read every bracket as EXPLORATORY until coverage evidence is frozen.",
    "VALIDATED_BRACKET": "Frozen coverage evidence exists for the PRIMARY lane (S8: VALIDATED_BRACKET); the tier is read against it.",
}


@dataclass(frozen=True)
class Tiered:
    """sigma per curve and Z: the tier from the flanking edges (sigma of an edge = hypot of its curves' sigmas, as plan 1118), the tied set
    from |r_k - r_m| <= Z hypot(sigma_k, sigma_m) (the sigma of the difference)."""
    z: float
    s: np.ndarray

    def tier(self, e, m):
        se = np.hypot(self.s[:-1], self.s[1:])
        return TIER[bool(e[m - 1] > self.z * se[m - 1] and -e[m] > self.z * se[m])]

    def tied(self, r, m):
        return tuple(int(k) for k in np.flatnonzero(np.abs(r - r[m]) <= self.z * np.hypot(self.s, self.s[m])))

    def count(self, tied):
        return len(tied)


@dataclass(frozen=True)
class Untiered:
    """tiering NONE, or a location projection: no tier, no tied count; the span is the two flanking ranks."""
    def tier(self, e, m):
        return "UNTIERED"

    def tied(self, r, m):
        return (m,)

    def count(self, tied):
        return "NOT_EVALUATED"


@dataclass(frozen=True)
class MaxLocated:
    """An interior maximum at rank m; the span [lo_rank, hi_rank] is the chain neighbourhood of the tied curves (ranks are 0-based slow order)."""
    m: int
    lo_rank: int
    hi_rank: int
    tier: str
    n_tied: object

    def words(self):
        return f"MaxLocated, span ranks {self.lo_rank}..{self.hi_rank} (maximum at rank {self.m}), tier {self.tier}, n_tied {self.n_tied}"

    def record(self, slows, wheres):
        return {"type": "MaxLocated", "m": self.m, "lo_rank": self.lo_rank, "hi_rank": self.hi_rank, "tier": self.tier, "n_tied": self.n_tied,
                "span_slow": [list(slows[self.lo_rank]), list(slows[self.hi_rank])], "span_curves": [wheres[self.lo_rank], wheres[self.hi_rank]]}


@dataclass(frozen=True)
class MaxAtPathEnd:
    """The maximum is the first or last curve of the chain: no edge flanks it on one side, so no bracket exists."""
    end: int

    def words(self):
        return f"MaxAtPathEnd at rank {self.end}"

    def record(self, slows, wheres):
        return {"type": "MaxAtPathEnd", "end": self.end, "end_slow": list(slows[self.end]), "end_curve": wheres[self.end]}


@dataclass(frozen=True)
class NoInteriorMaximum:
    """(ARGMAX_FAST lane) no interior node has a rising edge in and a falling edge out."""
    def words(self):
        return "NoInteriorMaximum"

    def record(self, slows, wheres):
        return {"type": "NoInteriorMaximum"}


KINDS = (MaxLocated, MaxAtPathEnd, NoInteriorMaximum)   # every result kind of result() (plan 1160 A15; tests/test_intake_loop2.py T15.1)
READING = {   # result kind -> RESULT.json's `reading`: what the result is and is not evidence of (plan 1160 A15, A38); total over KINDS (test)
    MaxLocated: "A located maximum is not, by itself, evidence of a transition: `tiering` and `primary_verdict` say how far it was tested.",
    MaxAtPathEnd: "The maximum is at an end of the chain, so no bracket exists: the slow range may not reach a peak.",
    NoInteriorMaximum: "No curve between the ends has a rising edge in and a falling edge out: there is no interior maximum to locate.",
}


@dataclass(frozen=True)
class Handoff:
    """One PRIMARY bridge's kernel input and result. Invariant: `slows` and `wheres` are the curves' slow values and names in slow order
    (RESULT.json reads them; words() never does)."""
    bridge: dict
    bias: str
    result: object
    slows: tuple
    wheres: tuple

    def words(self):
        return f"PRIMARY {self.bridge['template']} on '{self.bridge['on']}' ({self.bias}): {self.result.words()} of {len(self.slows)} curves"

    def record(self):
        return {"bridge": self.bridge["template"], "on": self.bridge["on"], "projection": self.bias, "n_curves": len(self.slows), **self.result.record(self.slows, self.wheres)}


def result(e, r, cands, tiers, rel):
    """The result of one chain: the first interior candidate's MaxLocated, else MaxAtPathEnd (a REDUCE maximum at an end) or NoInteriorMaximum."""
    n = len(r)
    inner = [m for m in cands if 0 < m < n - 1]
    near = lambda tied: sorted(set(tied) | {int(a) for a, b in zip(rel.src, rel.tgt) if b in tied} | {int(b) for a, b in zip(rel.src, rel.tgt) if a in tied})
    loc = lambda m, tied: MaxLocated(m, near(tied)[0], near(tied)[-1], tiers.tier(e, m), tiers.count(tied))
    return {True: lambda: loc(inner[0], tiers.tied(r, inner[0])), False: lambda: {True: lambda: MaxAtPathEnd(cands[0]), False: NoInteriorMaximum}[len(cands) > 0]()}[len(inner) > 0]()


def values(cs, bias, tiering, c):
    """The kernel input of one PRIMARY bridge before the door: (r + c,) and, when the tiering gives one, (sigma,). x + c is applied here only."""
    top = [max(range(len(k.rows)), key=lambda i: k.rows[i][1]) for k in cs]   # each curve's largest measured value, ties to the first row
    return (np.array([VALUE[bias](k, i) for k, i in zip(cs, top)]) + c,) + SIGMA[(bias, tiering)](cs, top)


def chain(n):
    """CC's chain relation over n curves in slow order (door.TEMPLATES["chain"]), declared through admit.declare: acyclic over distinct
    ranks, endpoints in range, each edge a CONTINUATION, so the door cannot refuse it."""
    n, edges = door.TEMPLATES["chain"][1]({"axes": {"slow": list(range(n))}}, {"axis": "slow"})
    return admit.declare(n, edges, [kernel.Provenance.CONTINUATION] * len(edges))


def reduce(xs, bias, z, rel):
    """Plan 1118's REDUCE as A over the chain: xs are the admitted NodeFields (r + c, and sigma when tiered); the edges are A's."""
    tiers = {True: lambda: Untiered(), False: lambda: Tiered(z, xs[-1].data[0])}[len(xs) == 1]()
    e, r = kernel.A(xs[0], rel).spatial[0], xs[0].data[0]
    return result(e, r, LOCATE[bias](e, r), tiers, rel)


def handoff(lineage, plan, feasibility, t):
    """S10: NO_KERNEL_ROUTE (no PRIMARY bridge, or one whose template has no door template in CC) | PROJECTION_EMPTY_ON_CURVE (plan 1160
    A39.1: the PRIMARY projection's DOMAIN, intake_feasible's, is empty on a curve) | DOOR_REFUSED (the door refuses a value: door.nodefield's
    Null on a non-finite r_k or sigma), in that order; else the KernelInput of every PRIMARY bridge."""
    census = lineage.census
    d, files = census.pinned.declaration.data, census.pinned.files
    cs = sorted(intake_census.CURVES[d["selection"]["layout"]](d, files, [intake_census.read(t, d, f) for f in files]), key=lambda c: c.slow)
    primary = [b for b in d["bridge"] if b["lane"] == "PRIMARY"]
    unrouted = [b for b in primary if ROUTE[b["template"]] not in door.TEMPLATES]
    bias = lambda b: [p["bias"] for p in d["projection"] if p["lane"] == "PRIMARY" and p["to"] == b["on"]][0]   # CHAIN_SLOW takes a projection's `to` (S1)
    vals = lambda b: values(cs, bias(b), plan.tiering, d["shift"]["c"])
    empty = lambda: [(bias(b), intake_feasible.DOMAIN[bias(b)](cs)) for b in primary if intake_feasible.DOMAIN[bias(b)](cs)]
    return gate([(lambda: primary and not unrouted, "NO_KERNEL_ROUTE", lambda: detail(words=[f"PRIMARY bridge {b['template']} on '{b['on']}': no door template in CC" for b in unrouted][:3] or ["no PRIMARY bridge"],
                                                                                      counts={"PRIMARY bridges": len(primary)})),
                 (lambda: not empty(), "PROJECTION_EMPTY_ON_CURVE", lambda: detail(words=[f"PRIMARY projection {empty()[0][0]}"] + empty()[0][1][:3], counts={"curves": len(empty()[0][1]), "of": len(cs)}))],
                lambda: admitted(lineage, plan, feasibility, t, cs, primary, bias, vals))


def admitted(lineage, plan, feasibility, t, cs, primary, bias, vals):
    """The door step: every PRIMARY bridge's values through door.nodefield (a NodeField or a Null), then A over the chain."""
    rel = chain(len(cs))
    fields = [[door.nodefield(v, None) for v in vals(b)] for b in primary]
    nulls = [(b, x) for b, xs in zip(primary, fields) for x in xs if isinstance(x, door.Null)]
    one = lambda b, xs: Handoff(b, bias(b), reduce(xs, bias(b), t["policy"]["policy"]["tier_z"], rel), tuple(c.slow for c in cs), tuple(c.where for c in cs))
    return gate([(lambda: not nulls, "DOOR_REFUSED", lambda: detail(words=[f"PRIMARY bridge {b['template']} on '{b['on']}': {x.value} ({x.reason})" for b, x in nulls][:3], counts={"kernel-input arrays refused": len(nulls)}))],
                lambda: Pass(KernelInput(lineage, tuple(one(b, xs) for b, xs in zip(primary, fields)), feasibility.identifiability)))


def bodies(t, d):
    """The registered body of S10, closed over the tables. It has exactly its SIGNATURE row (tests/test_intake.py)."""
    def s10(lineage: Lineage, plan: IntervalPlan, feasibility: Feasibility) -> Pass | Refuse:
        return handoff(lineage, plan, feasibility, t)
    return {"S10": s10}


SEALED_FIELDS = ("declaration_sha256", "sealed_at_utc", "author_kind", "confirmed_by")
IDENTITY = {   # the seal status -> RESULT.json's seal fields; total over SealStatus. UNSEALED has no SEAL.json (intake_seal.record is {}), so its
    intake_seal.SealStatus.UNSEALED: lambda rec: {f: "" for f in SEALED_FIELDS},   # fields are empty by the status, never by a lookup default
    intake_seal.SealStatus.SEALED: lambda rec: {f: rec[f] for f in SEALED_FIELDS},
    intake_seal.SealStatus.SEALED_THEN_EDITED: lambda rec: {f: rec[f] for f in SEALED_FIELDS},
}


def identity(seal):
    """RESULT.json's seal_identity of S2's SealState: the status and the record's fields, looked up in IDENTITY by the status."""
    return {"status": seal.status.name, **IDENTITY[seal.status](seal.record)}


def _record(root, t, d, out, primary):
    """RESULT.json of a run whose S10 passed. It leads with what to read (plan 1160 A15): `tiering`, `primary_verdict`, then `reading`
    (READING's sentence of each distinct result kind, in result order); then every PRIMARY bridge's result, the identifiability, the bracket and why its tier
    claims no coverage, the confirmation, and the code and seal identity. Its only numbers are ranks, counts, Z and the span's slow values."""
    k, seal = out["S10"].result.evidence, out[t["stages"]["seal_stage"]].result.evidence
    rec = {"tiering": out["S7"].result.evidence.tiering, "primary_verdict": primary, "reading": " ".join(dict.fromkeys(READING[type(h.result)] for h in k.columns)),
           "schema": 1, "kind": "intake-result", "id": Path(d).name, "results": [h.record() for h in k.columns],
           "ranks": "0-based positions of the curves in slow order: the nodes of the declared chain (CHAIN_SLOW)",
           "tier_z": t["policy"]["policy"]["tier_z"], "identifiability": k.identifiability,
           "max_bracket": out["S8"].result.evidence.max_bracket, "why_this_tier": HONEST[out["S8"].result.evidence.max_bracket],
           "confirmation": {True: "CONFIRMED", False: "UNCONFIRMED"}[out[t["stages"]["seal_stage"]].confirmed()],
           "code_identity": {"commit": schema.git_head(root), "code_hash": schema.code_hash(root),
                             "terminal_sha256": registry.sha256_of(Path(__file__))},
           "seal_identity": identity(seal)}
    (Path(d) / "RESULT.json").write_text(json.dumps(rec, indent=1) + "\n")


WRITE = {**{m: lambda root, t, d, out, primary: (Path(d) / "RESULT.json").unlink(missing_ok=True) for m in Mark}, Mark.PASSED: _record}   # S10's mark -> write or remove a stale one; total


def write(root, t, d, out, primary):
    """declarations/<id>/RESULT.json after a run: written when S10 passed (PRIMARY_READY or PRIMARY_INCOMPLETE[confirmation]), else removed."""
    return WRITE[out["S10"].mark](root, t, d, out, primary)
