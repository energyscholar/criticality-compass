"""intake_suspect - plan 1176 phase A: FORMAT v14's optional [plane] and [suspect], and the suspect polyline in grid cells (role intake_suspect
with its own cap, tests/test_budget.py SUSPECT_CAP, so CORE_CAP stays 1200).
The suspect is the DECLARER'S GUESS of a line, never data and never a checkpoint. Converting it acts on the guess, not on the data: a vertex
[slow, fast] lands on the curve whose slow value EQUALS its slow exactly as S5 holds it (the float FORMAT's reader parsed; no snapping to the
nearest curve, else SUSPECT_SLOW_NOT_A_CURVE); its fast value must lie within that curve's measured span [first, last sample] (else
SUSPECT_FAST_OUT_OF_SPAN); its cell is then (curve rank, the in-span nearest sample's rank), ties to the lower rank. Nothing between measured
points is ever formed: a cell is a rank pair, never a value. Curve rank and sample rank are intake_feature's (slow order; ascending fast, stable).
The plane: [plane] axes "slow-fast". A family whose curves carry more than one replicate key (intake_census.KEYED: a second knob varies) needs
[plane.slice] (else PLANE_NEEDS_A_SLICE); the slice names the declared [replicate.key] COLUMN (else PLANE_SLICE_NOT_THE_SECOND_KNOB) and keeps
the curves whose key is exactly its value (none: PLANE_SLICE_SELECTS_NO_CURVE).
Every refusal is a local typed value (Refused, its sentence in REFUSAL): STAGES.toml is untouched and the core is at its cap. Like the side
oracle, it reads only the Census object (the pinned bytes it carries) and the tables as values: it constructs no Path and opens nothing, and a
refusal's detail names vertex ordinals, the declared guess and curve ranks, never a measured value."""
from dataclasses import dataclass, field

import intake_census
from intake_blind import gate, look

REFUSAL = {   # code -> sentence; every code this module emits is a row (tests/test_suspect.py)
    "SUSPECT_ABSENT": "The declaration has no [suspect]: no line was declared, so there is nothing to follow (no default line exists).",
    "PLANE_ABSENT": "The declaration has a [suspect] but no [plane]: the suspect's vertices are in no declared plane.",
    "SUSPECT_NEEDS_TWO_VERTICES": "A suspect line needs at least two vertices.",
    "SUSPECT_VERTEX_NOT_A_PAIR": "Each vertex is [slow, fast]: exactly two numbers in the declared knobs' units.",
    "SUSPECT_SLOW_NOT_A_CURVE": "A vertex's slow value is not exactly the slow value of a curve of the plane; it is never snapped to a near curve.",
    "SUSPECT_FAST_OUT_OF_SPAN": "A vertex's fast value lies outside its curve's measured span; nothing beyond a measured sample is formed.",
    "PLANE_NEEDS_A_SLICE": "The curves carry more than one value of a second knob ([replicate.key]); [plane.slice] must fix one value.",
    "PLANE_SLICE_NOT_THE_SECOND_KNOB": "[plane.slice] column is not the declared [replicate.key] COLUMN, the only second knob a family declares.",
    "PLANE_SLICE_SELECTS_NO_CURVE": "No curve's [replicate.key] value is exactly the [plane.slice] value.",
}


@dataclass(frozen=True)
class Refused:
    """A typed refusal of the plane or the suspect. Invariant: `code` is a key of REFUSAL; `detail` names ordinals, ranks and the declared
    guess, never a measured value."""
    code: str
    detail: str

    def words(self):
        return f"{self.code}: {REFUSAL[self.code]} Detail: {self.detail}"


@dataclass(frozen=True)
class Plane:
    """The curves of the plane, in slow order (curve rank = index), each as (slow value, fast values in ascending order (sample rank = index));
    source: the census's curve objects in the same order (plan 1176 D, A-E6: the side oracle is built over exactly these)."""
    curves: tuple
    source: tuple = ()


@dataclass(frozen=True)
class Cells:
    """The suspect polyline in grid cells: (curve rank, sample rank) per vertex, in declared order, and the grid's extent (curves, n_max),
    the navigator's plane (0, 0) .. (curves - 1, n_max - 1). corridor is the declared corridor word. plane: the Plane they were converted on
    (plan 1176 D; not part of a Cells' identity)."""
    cells: tuple
    corridor: str
    curves: int
    n_max: int
    plane: Plane = field(default=None, compare=False)


KEY_COLUMN = {   # [replicate.key] kind -> (its row) -> the column a slice may name; total over FORMAT's kinds (only a COLUMN is a column)
    "NONE": lambda k: None, "FILE_NAME": lambda k: None, "COLUMN": lambda k: k["column"],
}


def _curves(t, d, census):
    """(curve, its replicate key) of the census, as S5 cut them (the same reads as intake_feature's oracle: the Pinned's bytes only)."""
    files = census.pinned.files
    cs = intake_census.CURVES[d["selection"]["layout"]](d, files, [intake_census.read(t, d, f) for f in files])
    key = intake_census.KEYED[d["replicate"]["identity"]](d["selection"]["layout"], d["replicate"]["key"]["kind"])
    return [(c, key(d, c)) for c in cs]


def _plane(keyed):
    """A Plane of (curve, key) pairs: slow order (stable), each curve's fast values ascending (stable, as intake_feature ranks samples)."""
    cs = [c for c, _ in sorted(keyed, key=lambda ck: ck[0].slow)]
    return Plane(tuple((c.slow, tuple(sorted(r[0] for r in c.rows))) for c in cs), tuple(cs))


def _sliced(d, keyed, sl):
    """The plane at [plane.slice]: the slice must name the declared key column, and keep at least one curve."""
    kept = [(c, k) for c, k in keyed if k == sl["value"]]
    return gate([(lambda: sl["column"] == KEY_COLUMN[d["replicate"]["key"]["kind"]](d["replicate"]["key"]), "PLANE_SLICE_NOT_THE_SECOND_KNOB",
                  lambda: f"slice column {sl['column']!r}; [replicate.key] kind {d['replicate']['key']['kind']}"),
                 (lambda: len(kept) > 0, "PLANE_SLICE_SELECTS_NO_CURVE", lambda: f"slice {sl['column']!r} = {sl['value']!r}; {len(keyed)} curves, none with that key")],
                lambda: _plane(kept), Refused)


SLICE = {   # (does a second knob vary: more than one replicate key, is a [plane.slice] declared) -> (declaration, keyed curves) -> Plane | Refused
    (False, False): lambda d, keyed: _plane(keyed),
    (True, False): lambda d, keyed: Refused("PLANE_NEEDS_A_SLICE", f"{len({k for _, k in keyed})} values of the second knob over {len(keyed)} curves"),
    (False, True): lambda d, keyed: _sliced(d, keyed, d["plane"]["slice"]),
    (True, True): lambda d, keyed: _sliced(d, keyed, d["plane"]["slice"]),
}


def plane(t, census):
    """The plane of a census (S5's evidence) under its declaration's [plane]: a Plane, or Refused."""
    d = census.pinned.declaration.data
    keyed = _curves(t, d, census)
    return SLICE[(len({k for _, k in keyed}) > 1, "slice" in look(d, "plane", {}))](d, keyed)


def pair(v):
    """A vertex is [slow, fast]: a list of exactly two numbers (bool is no number)."""
    return isinstance(v, list) and len(v) == 2 and all(isinstance(x, (int, float)) and not isinstance(x, bool) for x in v)


def nearest(fast, x):
    """The rank of the in-span sample nearest x (ascending fast values; ties to the lower rank): a sample's rank, never a value between two."""
    return min(range(len(fast)), key=lambda i: (abs(fast[i] - x), i))


def cell(p, i, v):
    """One vertex (its ordinal i) to (curve rank, sample rank), or the first refusal of its rows."""
    ranks = [k for k, (slow, _) in enumerate(p.curves) if pair(v) and slow == (float(v[0]),)]
    fast = lambda: p.curves[ranks[0]][1]
    return gate([(lambda: pair(v), "SUSPECT_VERTEX_NOT_A_PAIR", lambda: f"vertex {i}: {v!r}"),
                 (lambda: len(ranks) == 1, "SUSPECT_SLOW_NOT_A_CURVE", lambda: f"vertex {i}: slow {v[0]!r}; the plane holds {len(p.curves)} curves"),
                 (lambda: fast()[0] <= v[1] <= fast()[-1], "SUSPECT_FAST_OUT_OF_SPAN", lambda: f"vertex {i}: fast {v[1]!r} on curve rank {ranks[0]}")],
                lambda: (ranks[0], nearest(fast(), v[1])), Refused)


def _cells(p, s):
    """Every vertex in cells, or the first vertex's refusal."""
    each = [cell(p, i, v) for i, v in enumerate(s["vertices"])]
    bad = [c for c in each if isinstance(c, Refused)] + [None]
    return {True: lambda: Cells(tuple(each), s["corridor"], len(p.curves), max(len(f) for _, f in p.curves), p), False: lambda: bad[0]}[bad[0] is None]()


ON_PLANE = {Plane: lambda p, s: _cells(p, s), Refused: lambda p, s: p}   # the plane's outcome type -> (it, [suspect]) -> Cells | Refused


def suspect(t, census):
    """The suspect polyline of a census in grid cells: Cells, or Refused (SUSPECT_ABSENT, PLANE_ABSENT, SUSPECT_NEEDS_TWO_VERTICES, the plane's
    refusals, then the first refused vertex's). S0 has already typed [plane] and [suspect] (FORMAT v14)."""
    d = census.pinned.declaration.data
    s = look(d, "suspect", {})
    return gate([(lambda: "suspect" in d, "SUSPECT_ABSENT", lambda: f"declaration {census.pinned.declaration.id}"),
                 (lambda: "plane" in d, "PLANE_ABSENT", lambda: f"declaration {census.pinned.declaration.id}"),
                 (lambda: len(s["vertices"]) >= 2, "SUSPECT_NEEDS_TWO_VERTICES", lambda: f"{len(s['vertices'])} vertex")],
                lambda: (lambda p: ON_PLANE[type(p)](p, s))(plane(t, census)), Refused)
