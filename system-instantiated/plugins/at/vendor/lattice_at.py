"""lattice_at.py - T5 (plumbing): Ashkin-Teller snapshots. H = -sum_<ij> [K s_i s_j + K t_i t_j + L s_i s_j t_i t_j].
Embedded Swendsen-Wang: update s with t fixed (bond coupling J_ij = K + L t_i t_j), then t with s fixed. Signed couplings
are handled generally: a bond may form between spins with s_i s_j sign(J_ij) > 0, with probability 1 - exp(-2|J_ij|).
Self-dual critical line (Wiseman & Domany 1993, image-verified; = sinh 2K = exp(-2L)): Z = 1 - 2X, Z = e^{-4K},
X = e^{-2(K+L)}; Ising end L = 0, K = ln(1+sqrt2)/2; 4-state Potts end K = L = ln(3)/4.
Periodic SIMULATED system; the analysis declares no ring."""
import numpy as np
from scipy.sparse import coo_matrix
from scipy.sparse.csgraph import connected_components


def _sw_signed(s, J_right, J_down, rng):
    """one SW update of s (L x L, +-1) with bond couplings J_right[i,j] (to (i,j+1)) and J_down[i,j] (to (i+1,j))."""
    L = s.shape[0]
    idx = np.arange(L * L).reshape(L, L)
    rows, cols = [], []
    for nb, J in ((np.roll(idx, -1, 1), J_right), (np.roll(idx, -1, 0), J_down)):
        sj = s.ravel()[nb.ravel()]
        ok = s.ravel() * sj * np.sign(J.ravel()) > 0
        bond = ok & (rng.random(L * L) < 1.0 - np.exp(-2.0 * np.abs(J.ravel())))
        rows.append(idx.ravel()[bond]); cols.append(nb.ravel()[bond])
    r, c = np.concatenate(rows), np.concatenate(cols)
    n, lab = connected_components(coo_matrix((np.ones(len(r)), (r, c)), shape=(L * L, L * L)), directed=False)
    return np.where((rng.random(n) < 0.5)[lab].reshape(L, L), -s, s)


def _step(s, t, K, Lc, rng):
    s = _sw_signed(s, K + Lc * t * np.roll(t, -1, 1), K + Lc * t * np.roll(t, -1, 0), rng)
    t = _sw_signed(t, K + Lc * s * np.roll(s, -1, 1), K + Lc * s * np.roll(s, -1, 0), rng)
    return s, t


def at_sw(L, K, Lc, n_samples, skip, burn, rng):
    """(sigma, tau) snapshots, each (n_samples, L, L) int8."""
    s = rng.choice(np.array([-1, 1]), size=(L, L))
    t = rng.choice(np.array([-1, 1]), size=(L, L))
    S = np.empty((n_samples, L, L), dtype=np.int8)
    T = np.empty((n_samples, L, L), dtype=np.int8)
    for _ in range(burn):
        s, t = _step(s, t, K, Lc, rng)
    for i in range(n_samples):
        for _ in range(skip):
            s, t = _step(s, t, K, Lc, rng)
        S[i], T[i] = s, t
    return S, T


def self_dual_K(Lc):
    """K on the self-dual line for four-spin coupling Lc: sinh 2K = exp(-2 Lc)."""
    return np.arcsinh(np.exp(-2.0 * Lc)) / 2.0
