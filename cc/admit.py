"""admit.py - the DOOR (plumbing; may branch), and the four kernel types it owns. A kernel type's constructor IS the door: there is no second way to build one.
Refuses, with a reason, what Kernel V8 declares inadmissible: a missing provenance, an endpoint outside the declared
nodes, and any CYCLE (section 4: a ring/torus makes a node its own relational predecessor); a non-finite value; an M without a declared finite chi_0 > 0.
This is where refusal lives: what passes here is built as a frozen kernel type with read-only arrays that it owns (a later write to the caller's array never reaches it),
and what does not is refused with a reason (a declaration raises; data returns an `Refused` value through `admitted`, see docs/READING-THE-CODE.md "Two kinds of refusal").
`cc/kernel.py` imports these types and holds the operators only. `admit.declare`, `admit.nodefield` and `admit.m` are the documented door functions: argument conversion, then the type's constructor.
Code downstream of the door must not add guards, clamps or defaults for input the door should have refused; extend the refusal here instead.
See KERNEL-IN-CC.md ("Why CC uses relational math") and docs/READING-THE-CODE.md."""
from dataclasses import dataclass
from enum import Enum

import numpy as np


class Provenance(Enum):
    CONTINUATION = "Continuation"   # within-family continuation, declared from observable/device geometry
    COUPLING = "Coupling"           # cross-family coupling, declared from a physical coupling mechanism
    STEERING = "Steering"           # Origin-declared steering relation, pending kernel revision; V8's operators.rs names no such provenance (CC's one provenance beyond it)


def _owned(a):
    """A copy that owns its memory and is read-only: a write into it raises, and no array the caller still holds shares it."""
    o = np.array(a)
    o.setflags(write=False)
    return o


def acyclic(n, src, tgt):
    """Kahn's algorithm: True iff the declared directed graph has no cycle."""
    indeg = np.bincount(tgt, minlength=n)
    out = [[] for _ in range(n)]
    for s, t in zip(src, tgt):
        out[s].append(t)
    frontier, seen = [i for i in range(n) if indeg[i] == 0], 0
    while frontier:
        i = frontier.pop()
        seen += 1
        for t in out[i]:
            indeg[t] -= 1
            if indeg[t] == 0:
                frontier.append(t)
    return seen == n


@dataclass(frozen=True)
class Relations:
    """Directed, acyclic (no ring/torus), every edge with a provenance; src and tgt are owned read-only int arrays. Refuses at construction."""
    n: int
    src: np.ndarray                 # int[E]
    tgt: np.ndarray                 # int[E]
    provenance: tuple               # Provenance[E]

    def __post_init__(self):
        src = np.asarray(self.src, dtype=int).reshape(-1)
        tgt = np.asarray(self.tgt, dtype=int).reshape(-1)
        prov = tuple(self.provenance)
        if len(src) != len(tgt):
            raise ValueError("REFUSED: every edge needs a source and a target")
        if len(prov) != len(src):
            raise ValueError("REFUSED: one provenance per declared edge")
        if not all(isinstance(p, Provenance) for p in prov):
            raise ValueError("REFUSED: every edge needs a declared provenance (Continuation/Coupling)")
        if not ((src >= 0) & (src < self.n) & (tgt >= 0) & (tgt < self.n)).all():
            raise ValueError("REFUSED: an edge endpoint lies outside the declared nodes")
        if not acyclic(self.n, src, tgt):
            raise ValueError("REFUSED: a cycle (ring/torus) is inadmissible: a node would be its own predecessor")
        object.__setattr__(self, "src", _owned(src))
        object.__setattr__(self, "tgt", _owned(tgt))
        object.__setattr__(self, "provenance", prov)


@dataclass(frozen=True)
class Refused:
    """A value refusal: what the door says about data it will not admit (data refuses by returning this; a declaration raises)."""
    sentence: str


def _shaped(data):
    x = np.asarray(data, dtype=float)
    return x.reshape(1, -1) if x.ndim == 1 else x


def _nodefield_refusal(x):
    """The one place a NodeField's refusal is written: None when `x` is admissible, else the Refused."""
    if x.ndim != 2:
        return Refused("REFUSED: a NodeField is k components x n nodes")
    if not np.isfinite(x).all():
        return Refused("REFUSED: every value projected through M must be finite (in D)")
    return None


@dataclass(frozen=True)
class NodeField:
    """k components x n nodes, every value finite (in D); data is an owned read-only float array. Refuses at construction."""
    data: np.ndarray                # float[k, n]

    def __post_init__(self):
        x = _shaped(self.data)
        r = _nodefield_refusal(x)
        if r is not None:
            raise ValueError(r.sentence)
        object.__setattr__(self, "data", _owned(x))


@dataclass(frozen=True)
class EdgeField:
    """What A makes: owned read-only arrays. No value refusal (operators.rs has no constructor); that it came from A over a declared relation is provenance, which Python cannot seal."""
    spatial: np.ndarray             # float[k, E]
    comp: np.ndarray                # float[P, n]

    def __post_init__(self):
        object.__setattr__(self, "spatial", _owned(self.spatial))
        object.__setattr__(self, "comp", _owned(self.comp))


@dataclass(frozen=True)
class M:
    """The M-supplied constants: rho_base, chi_0, component pairs, one cc per pair. Refuses at construction; cc is an owned read-only array.
    Inside E, A and R read the pairs from the SAME M, so they cannot disagree. A alone takes pairs directly (Case A uses A->B only and must not invent rho values to call A)."""
    rho_base: float
    chi_0: float
    pairs: tuple                    # ((a, b), ...) declared component pairs
    cc: np.ndarray                  # float[P], one per pair

    def __post_init__(self):
        cc = np.asarray(self.cc, dtype=float).reshape(-1)
        pairs = tuple(tuple(p) for p in self.pairs)
        if not (np.isfinite(self.rho_base) and np.isfinite(self.chi_0) and self.chi_0 > 0):
            raise ValueError("REFUSED (NOT EVALUATED): rho_base and chi_0 must be declared, finite, chi_0 > 0")
        if len(cc) != len(pairs) or not np.isfinite(cc).all():
            raise ValueError("REFUSED (NOT EVALUATED): one finite cc per declared component pair")
        object.__setattr__(self, "rho_base", float(self.rho_base))
        object.__setattr__(self, "chi_0", float(self.chi_0))
        object.__setattr__(self, "pairs", pairs)
        object.__setattr__(self, "cc", _owned(cc))


def declare(n, edges, provenance):
    src = np.array([s for s, _ in edges], dtype=int).reshape(-1)
    tgt = np.array([t for _, t in edges], dtype=int).reshape(-1)
    return Relations(n, src, tgt, tuple(provenance))


def nodefield(data):
    """A NodeField, or a raise (a declaration: the run must not start). Data that may be non-finite goes through `admitted`."""
    return NodeField(data)


def admitted(data):
    """The value door for DATA: a NodeField, or a Refused value (the run continues and the reason travels). Same test as the constructor, written once (`_nodefield_refusal`)."""
    x = _shaped(data)
    r = _nodefield_refusal(x)
    return r if r is not None else NodeField(x)


def m(rho_base, chi_0, pairs=(), cc=()):
    return M(rho_base, chi_0, pairs, cc)
