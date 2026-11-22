"""admit.py - the DOOR (plumbing; may branch). Declared relations are built here and nowhere else.
Refuses, with a reason, what Kernel V8 declares inadmissible: a missing provenance, an endpoint outside the declared
nodes, and any CYCLE (section 4: a ring/torus makes a node its own relational predecessor).
This is where refusal lives: what passes here is built as a frozen kernel type, and what does not is refused with a reason that travels on as a value.
Code downstream of the door must not add guards, clamps or defaults for input the door should have refused; extend the refusal here instead.
See KERNEL-IN-CC.md ("Why CC uses relational math") and docs/READING-THE-CODE.md."""
import numpy as np
from kernel import Relations, Provenance, NodeField, M


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


def declare(n, edges, provenance):
    src = np.array([s for s, _ in edges], dtype=int).reshape(-1)
    tgt = np.array([t for _, t in edges], dtype=int).reshape(-1)
    prov = tuple(provenance)
    if len(prov) != len(src):
        raise ValueError("REFUSED: one provenance per declared edge")
    if not all(isinstance(p, Provenance) for p in prov):
        raise ValueError("REFUSED: every edge needs a declared provenance (Continuation/Coupling)")
    if not ((src >= 0) & (src < n) & (tgt >= 0) & (tgt < n)).all():
        raise ValueError("REFUSED: an edge endpoint lies outside the declared nodes")
    if not acyclic(n, src, tgt):
        raise ValueError("REFUSED: a cycle (ring/torus) is inadmissible: a node would be its own predecessor")
    return Relations(n, src, tgt, prov)


def nodefield(data):
    x = np.asarray(data, dtype=float)
    x = x.reshape(1, -1) if x.ndim == 1 else x
    if x.ndim != 2:
        raise ValueError("REFUSED: a NodeField is k components x n nodes")
    if not np.isfinite(x).all():
        raise ValueError("REFUSED: every value projected through M must be finite (in D)")
    return NodeField(x)


def m(rho_base, chi_0, pairs=(), cc=()):
    cc = np.asarray(cc, dtype=float).reshape(-1)
    if not (np.isfinite(rho_base) and np.isfinite(chi_0) and chi_0 > 0):
        raise ValueError("REFUSED (NOT EVALUATED): rho_base and chi_0 must be declared, finite, chi_0 > 0")
    if len(cc) != len(pairs) or not np.isfinite(cc).all():
        raise ValueError("REFUSED (NOT EVALUATED): one finite cc per declared component pair")
    return M(float(rho_base), float(chi_0), tuple(tuple(p) for p in pairs), cc)
