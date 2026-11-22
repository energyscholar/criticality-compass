"""kernel.py - T0: a Python REFERENCE of the ABR kernel (V8, pinned rev 5c7941e0), vectorised over declared relations.

Pure maths: types + operators, NO validation here. Every value that reaches an operator was built by the DOOR
(`admit.py`), which refuses inadmissible input with a reason. So this file holds no branch at all.
  Provenance   spatial provenances only (Continuation, Coupling). Persistence is not a member: it cannot enter the
               spatial edge list, because there is no value to put there.
  Relations    directed, acyclic (no ring/torus), every edge with a provenance      - built only by admit.declare
  NodeField    k components x n nodes, every value finite (in D)                     - built only by admit.nodefield
  M            the M-supplied constants: rho_base, chi_0, component pairs, one cc per pair - built only by admit.m
               Inside E, A and R read the pairs from the SAME M, so they cannot disagree. A alone takes pairs
               directly (Case A uses A->B only and must not invent rho values to call A).
Operators (formulas exactly as operators.rs at the pinned rev):
  A(x)[e] = x[s] - x[t];  comp pair (a,b): x[a][i] - x[b][i]           NodeField -> EdgeField (the ONLY such step)
  B(g)[e] = g[e] + sum over succ(e) = out[tgt(e)]   IMMEDIATE successors only; terminal edges add nothing
  rho[i]  = rho_base * chi[i] / (chi_0 + chi[i]),  chi[i] = max |A| over edges incident to i and comp[.][i]
  R(g)[e] = g[e] + rho[src(e)] * (sum_succ g - sum_pred g)  (+ cc cross-topology term per declared pair)
  E(x)    = R(B(A(x)), rho(A(x)))

Why this file is shaped this way (read before editing). A is the graph incidence operator, and B and R build on it; the maths is standard. This file
relies on a rule about what reaches it: only `x + c` before A, every relation declared with its provenance, inadmissible input refused with a reason
at the door. Each value arrives built by the door as a frozen type, so this file holds no `if`: a cycle, an undeclared provenance, a non-finite value and an out-of-range endpoint cannot reach it. Do not add smoothing,
interpolation, clamps or guards here, and do not accept an undeclared relation; if an input is wrong, extend the door's refusal in `admit.py`.
The reasons and the idioms are in KERNEL-IN-CC.md ("Why CC uses relational math") and docs/READING-THE-CODE.md.
"""
from dataclasses import dataclass
from enum import Enum
import numpy as np


class Provenance(Enum):
    CONTINUATION = "Continuation"   # within-family continuation, declared from observable/device geometry
    COUPLING = "Coupling"           # cross-family coupling, declared from a physical coupling mechanism


@dataclass(frozen=True)
class Relations:
    n: int
    src: np.ndarray                 # int[E]
    tgt: np.ndarray                 # int[E]
    provenance: tuple               # Provenance[E]


@dataclass(frozen=True)
class NodeField:
    data: np.ndarray                # float[k, n]


@dataclass(frozen=True)
class EdgeField:
    spatial: np.ndarray             # float[k, E]
    comp: np.ndarray                # float[P, n]


@dataclass(frozen=True)
class M:
    rho_base: float
    chi_0: float
    pairs: tuple                    # ((a, b), ...) declared component pairs
    cc: np.ndarray                  # float[P], one per pair


def _out_sum(rel, v):
    """per node i: sum of v[e] over the edges e leaving i."""
    return np.bincount(rel.src, weights=v, minlength=rel.n)


def _in_sum(rel, v):
    """per node i: sum of v[e] over the edges e entering i."""
    return np.bincount(rel.tgt, weights=v, minlength=rel.n)


def A(x: NodeField, rel: Relations, pairs=()) -> EdgeField:
    spatial = x.data[:, rel.src] - x.data[:, rel.tgt]
    comp = np.array([x.data[a] - x.data[b] for a, b in pairs]).reshape(len(pairs), rel.n)
    return EdgeField(spatial, comp)


def B(g: EdgeField, rel: Relations) -> EdgeField:
    spatial = np.array([s + _out_sum(rel, s)[rel.tgt] for s in g.spatial]).reshape(g.spatial.shape)
    comp = np.array([c + _out_sum(rel, c[rel.tgt]) for c in g.comp]).reshape(g.comp.shape)
    return EdgeField(spatial, comp)


def rho(a: EdgeField, rel: Relations, m: M) -> np.ndarray:
    mag = np.abs(a.spatial).max(axis=0, initial=0.0)                  # form: chi is a max selection of |A| (V8 rho)
    chi = np.zeros(rel.n)
    np.maximum.at(chi, rel.src, mag)
    np.maximum.at(chi, rel.tgt, mag)
    chi = np.maximum(chi, np.abs(a.comp).max(axis=0, initial=0.0))   # form: chi is a max selection of |A| (V8 rho)
    return m.rho_base * chi / (m.chi_0 + chi)


def R(bg: EdgeField, rel: Relations, rho_n: np.ndarray, m: M) -> EdgeField:
    rho_e = rho_n[rel.src]
    spatial = np.array([s + rho_e * (_out_sum(rel, s)[rel.tgt] - _in_sum(rel, s)[rel.src])
                        for s in bg.spatial]).reshape(bg.spatial.shape)
    for p, (a, b) in enumerate(m.pairs):
        asym = bg.comp[p][rel.tgt] - bg.comp[p][rel.src]
        spatial[a] += rho_e * m.cc[p] * asym
        spatial[b] -= rho_e * m.cc[p] * asym
    comp = bg.comp.copy()
    for p, (a, b) in enumerate(m.pairs):
        comp[p] += rho_n * (_out_sum(rel, bg.spatial[a]) - _out_sum(rel, bg.spatial[b]))
    return EdgeField(spatial, comp)


def E(x: NodeField, rel: Relations, m: M) -> EdgeField:
    a = A(x, rel, m.pairs)                    # A and R read the pairs from the SAME M
    return R(B(a, rel), rel, rho(a, rel, m), m)
