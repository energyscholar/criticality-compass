"""oracle_reweight.py - plan 1456 WIDTH: the dense zero-crossing navigator. Binless Ferrenberg-Swendsen multi-histogram reweighting of the SAME matched-pair poc chains
P5's needle reads (plus their stored energy array O) to a dense grid, so P5's scan terminal brackets the finite-L crossing at the dense flank resolution DK_DENSE.
STRUCTURE, NOT CONTROL: the only margin is the frozen navigate.EPS; the FS reweight is a POST-A transform declared through REWEIGHT_DECL (a declared report / conventional
estimate, never a relational or kernel reading). The one honest null is the per-label energy-coverage predicate (membership in a SAMPLED label's support, B1), not the global
hull and not a tuned overlap threshold; FS non-convergence and under-replication are REFUSE values (None), never clamps. Imports navigate, sign, sampler, oracle_measured only:
NEVER oracle, detect or door, so it stays outside the measure_hash closure (grep-asserted in tests/test_oracle.py). r = readout.rank(10, 22/1024) = 2 is the P5 rank rule, passed in by the caller."""
import hashlib
from dataclasses import dataclass

import numpy as np

import navigate
import oracle_measured
import sampler
import sign

GRID = oracle_measured.GRID                 # the 7 sampled labels, K/K_c order
NL = len(GRID)                              # 7
KI = np.array([sampler.LABELS[l] for l in GRID])   # the 7 sampled couplings K_i, in label order
DK_DENSE = 0.002                            # plan 1456 (confirmed, section 7.1): the dense FLANK resolution; it does NOT set the UNRES band (section 1e)
FS_TOL = 1e-10                              # the FS f_i fixed-point residual (max |delta f|)
FS_MAXIT = 1000                             # non-convergence within this -> the read is a typed Refusal (a REFUSE value, B-FS-CONVERGE), never a clamp
REWEIGHT_DECL = (
    "reweight v1 (plan 1456): binless Ferrenberg-Swendsen multi-histogram estimate -- a DECLARED REPORT / conventional estimate, NOT a relational or kernel reading. "
    "KEEP: the reweighted typical g1 of each system at the target coupling K. "
    "DISCARD: configuration order; the sampling coupling of each configuration (absorbed into the FS free energies f_i). "
    "PRIOR (named): FS reweightability -- the density of states is coupling-independent, so a histogram sampled at K_i reweights to K; its admissibility DOMAIN is the "
    "per-label energy-coverage predicate (the reweighted mean conjugate lies in >=1 sampled label's range), outside which the estimate is a REFUSE value, not a number. "
    "CONJUGATE: X = the energy array O level 0, used with the declared Boltzmann sign (weight ~ exp(+K*X)) at its stored normalization; the input's transducer MUST confirm "
    "that sign and that normalization (extensive vs per-spin) before any real-data read -- absent, the read refuses rather than guess."
)


def _lse(a, axis):
    """log-sum-exp along `axis`, overflow-safe."""
    m = np.max(a, axis=axis, keepdims=True)
    return np.squeeze(m + np.log(np.sum(np.exp(a - m), axis=axis, keepdims=True)), axis=axis)


def fs_solve(X, Ki, Ni):
    """The binless FS free energies f_i (gauge f_0 := 0): exp(f_i) = sum_a exp(K_i X_a - D_a), D_a = log sum_j N_j exp(K_j X_a - f_j), by bounded fixed point.
    None when the residual does not reach FS_TOL within FS_MAXIT (a REFUSE value, not a clamp; B-FS-CONVERGE)."""
    logN = np.log(Ni)
    f = np.zeros(len(Ki))
    for _ in range(FS_MAXIT):
        D = _lse(logN[None, :] + Ki[None, :] * X[:, None] - f[None, :], 1)      # D_a over labels j, log-sum-exp
        nf = _lse(Ki[:, None] * X[None, :] - D[None, :], 1)                     # f_i over samples a, log-sum-exp
        nf = nf - nf[0]                                                         # gauge f_0 := 0 (the estimators are gauge-invariant)
        done = np.max(np.abs(nf - f)) < FS_TOL
        f = nf
        if done:
            return f
    return None


def _logdenom(X, Ki, Ni, f):
    return _lse(np.log(Ni)[None, :] + Ki[None, :] * X[:, None] - f[None, :], 1)   # D_a with the converged f


def weights(X, Ki, Ni, K, f):
    """w_a(K) = exp(K X_a - D_a) / sum_b exp(K X_b - D_b), by log-sum-exp (normalized at K)."""
    lw = K * X - _logdenom(X, Ki, Ni, f)
    return np.exp(lw - _lse(lw, 0))


def reweighted(X, g, Ki, Ni, K):
    """(<g>_K, <X>_K) by the binless FS reweight of one pooled sample set to K; None when the FS solve does not converge (the REFUSE value propagates)."""
    f = fs_solve(X, Ki, Ni)
    return None if f is None else (lambda w: (float((g * w).sum()), float((X * w).sum())))(weights(X, Ki, Ni, K, f))


@dataclass(frozen=True)
class DenseStart:
    """The dense uniform grid over the label span [lo, hi] at dk; carries its OWN `labels` tuple (the 7 sampled GRID labels it reweights FROM, named in the report)."""
    lo: float
    hi: float
    dk: float
    labels: tuple            # the 7 sampled labels reweighted from (B6)
    target: float            # K_c: read by the SCORER alone, never by a reading

    def n(self):
        return round((self.hi - self.lo) / self.dk) + 1

    def k(self, j):
        return self.lo + j * self.dk

    def start_id(self):
        return f"reweight:{self.lo:.6f}-{self.hi:.6f}-{self.dk}"


def dense_start(target):
    """The canonical dense grid over the 7-label span [LABELS[GRID[0]], LABELS[GRID[-1]]] at DK_DENSE; `target` (K_c) is carried for the SCORER alone."""
    return DenseStart(sampler.LABELS[GRID[0]], sampler.LABELS[GRID[-1]], DK_DENSE, GRID, target)


def _open(path, L):
    with np.load(path) as z:
        return z["O"][:, 0], z["G"][:, sampler.SIZES[L] - 1]   # E = O[:, 0] (the per-configuration energy), g1 = final-level block g1; paired per configuration


def pair_read(root, big):
    """{L: {(label_index, chain): (X, g1)}} over ALL 7 labels for big and its partner, uniquely-resolved chain files only (the P5 glob-count == 1 rule). K-independent: built once."""
    small = oracle_measured.PARTNER[big]
    found = {l: oracle_measured.paths(root, sampler.LABELS[l], big) for l in GRID}   # {label: {L: [per-chain match lists]}}
    return {L: {(li, c): _open(found[l][L][c][0], L)
                for li, l in enumerate(GRID) for c in sampler.CHAINS if len(found[l][L][c]) == 1}
            for L in (big, small)}


def _digest(root, big):
    """A CONSTANT read_digest (M2): sha256(REWEIGHT_DECL + the file_shas over all 7 labels), computed once (load and bytes are K-independent)."""
    shas = "".join(oracle_measured.file_shas(root, sampler.LABELS[l], big) for l in GRID)
    return hashlib.sha256(REWEIGHT_DECL.encode() + shas.encode()).hexdigest()


def _pool(cells, c):
    """chain c's samples pooled across the 7 labels: (X, g1, N_i per label)."""
    cols = [cells[(li, c)] for li in range(NL)]
    return np.concatenate([x for x, _ in cols]), np.concatenate([g for _, g in cols]), np.array([len(x) for x, _ in cols])


def _ranges(cells, good):
    """per-label (min, max) of the conjugate over the matched chains -- the SAMPLED support (B1), not the global hull."""
    return [(lambda a: (float(a.min()), float(a.max())))(np.concatenate([cells[(li, c)][0] for c in good])) for li in range(NL)]


def _system(cells, good, K):
    """(g per matched chain, Xbar reweighted mean conjugate, covered) for one system, or None when any chain's FS solve does not converge (B-FS-CONVERGE)."""
    rw = [reweighted(X, g, KI, Ni, K) for X, g, Ni in (_pool(cells, c) for c in good)]
    ranges = _ranges(cells, good)
    return (lambda g, xbar: (g, xbar, any(lo <= xbar <= hi for lo, hi in ranges)))(
        np.array([v[0] for v in rw]), float(np.mean([v[1] for v in rw]))) if all(v is not None for v in rw) else None


@dataclass(frozen=True)
class Refusal:
    """A typed REFUSE value (plan 1458): WHY the read is not established -- under_replication | fs_nonconverge | coverage; a value of the output type, never an exception."""
    reason: str


@dataclass(frozen=True)
class Reweight:
    """The dense reweighted matched-pair order field, BESIDE oracle.Measured: K -> Sign | Refusal. Carries NO K_c. `load`/`digest` are K-independent, injected once (M2).
    The matched-pair difference Delta_c(K) = <g1_big,c>_K - <g1_small,c>_K over the m matched chains places the sign cell through the frozen navigate.interval + sign.sign."""
    big: int
    small: int
    m: int
    r: int
    load: object             # {L: {(label_index, chain): (X, g1)}} -- K-independent, built once
    digest: str              # the constant read_digest
    name = "reweight"

    def __call__(self, K):
        cb, cs = self.load[self.big], self.load[self.small]
        good = [c for c in sampler.CHAINS if all((li, c) in cb and (li, c) in cs for li in range(NL))]   # a chain MATCHED (complete in both) is a pool (M4)
        b = _system(cb, good, K) if len(good) >= self.m else None                                        # fewer than m matched pools -> None (under-replication)
        s = _system(cs, good, K) if len(good) >= self.m else None
        ok = b is not None and s is not None                                                              # both systems solved (FS converged)
        key = (len(good) >= self.m, ok, bool(ok and b[2] and s[2]))                                       # (replicated, FS converged, covered): the honest nulls (B1)
        return {(False, False, False): lambda: Refusal("under_replication"), (True, False, False): lambda: Refusal("fs_nonconverge"),
                (True, True, False): lambda: Refusal("coverage"), (True, True, True): lambda: self._cell(b[0], s[0])}[key]()   # a total table over the live rows; the other keys cannot occur

    def _cell(self, gb, gs):
        lo, hi = navigate.interval(gb[:self.m] - gs[:self.m], self.m, self.r)
        return sign.sign(lo, hi, navigate.EPS)[0]

    def read_digest(self, K):
        return self.digest


def make_reweight(root, big, m, r):
    """The Reweight order field for the big member at the data root (partner fixed by oracle_measured.PARTNER); load + constant digest built once."""
    return Reweight(big, oracle_measured.PARTNER[big], m, r, pair_read(root, big), _digest(root, big))


def report_dense(st, big, w, bracket):
    """The dense report (the `reweight` header); a DECLARED REPORT, not a relational reading (C2)."""
    trace = [f"  node {j} K={st.k(j):.4f} side={r.side} move={r.move} {r.status}" for j, r in w.trace]
    head = f"navigate reweight (L {big} vs {oracle_measured.PARTNER[big]}, m 10; labels {st.labels[0]}..{st.labels[-1]}; a declared report, not a relational reading)"
    return [head] + trace + [f"navigate reweight: {w.outcome} [{bracket[0]:.4f}, {bracket[1]:.4f}]"], 0
