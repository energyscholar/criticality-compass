"""oracle_measured.py - plan 1282 P5: the finite-L side of the Oracle. The SCAN terminal (the bracket is the flanking RESOLVED nodes around a band of UNRES nodes; navigate.walk
cannot bracket across a band), MeasuredStart (the non-uniform 7-label grid) and the loaders that turn chain files into the (a, b) the frozen navigate.needle reads. STRUCTURE, NOT CONTROL:
scan is a total fold over the moves (no threshold of its own); a missing or ambiguous file is an empty read, which navigate.needle REFUSEs as a value. Imports navigate, sampler only: never oracle,
detect or door, so it is outside the measure_hash closure."""
import hashlib
from dataclasses import dataclass
from pathlib import Path

import numpy as np

import navigate
import sampler

BIG = 243
PARTNER = {BIG: 81}   # declared (A2.1): the matched pair, big L -> partner L
GRID = tuple(sampler.LABELS)   # the 7 labels, K/K_c: where production data exists (non-uniform)
FAMILY = "poc"
OUTCOME = {**{(a, b, c): "REFUSE" for a in (True, False) for b in (True, False) for c in (True, False)}, (True, True, False): "BRACKET"}   # (a down node, an up node above it, an up node below a down) -> the walk's outcome; total over the 8
STEM = "{family}_{label}_L{L}_{start}_c{chain}.npz"   # production chain file: <data_root>/1282/<run>/<STEM>
LABEL_RUN = {}   # label -> its one run dir; OWED to the P2f production run. The glob-count == 1 rule below is what enforces it.


@dataclass(frozen=True)
class MeasuredStart:
    labels: tuple   # the labels of the nodes, in K order
    target: float   # K_c: read by the SCORER alone, never by a reading

    def n(self):
        return len(self.labels)

    def k(self, j):
        return sampler.LABELS[self.labels[j]]

    def start_id(self):
        return f"measured:{self.labels[0]}-{self.labels[-1]}-{len(self.labels)}"


def scan(read, n):
    """Read every node once; the bracket is [last lo, first hi above it]. BRACKET only for (a lo exists, a hi above it exists, no hi below the last lo), else REFUSE: total, branch-free."""
    readings = [read(j) for j in range(n)]
    moves = [r.move for r in readings]
    los = [j for j in range(n) if moves[j] == "lo"]
    his = [j for j in range(n) if moves[j] == "hi"]
    last_lo = max(los, default=-1)
    his_above = [j for j in his if j > last_lo]
    first_hi = min(his_above, default=n)
    disordered = any(j < last_lo for j in his)   # an ORD node below a DIS node already falsifies faithfulness: refused, never bracketed
    outcome = OUTCOME[(bool(los), bool(his_above), disordered)]
    lo = last_lo if outcome == "BRACKET" else 0
    hi = {True: first_hi, False: n - 1}[outcome == "BRACKET"]
    return navigate.Walk(outcome, lo, hi, tuple(enumerate(readings)))


def label_of(K):
    return f"{round(K / sampler.KC, 2):.2f}"   # exact on the grid: K = float(label) * K_c


def paths(root, K, big=BIG):
    """{L: [the run-dir matches of each random-start chain c0..c9]}: every run dir is searched, none is preferred."""
    return {L: [sorted((Path(root) / "1282").glob("*/" + STEM.format(family=FAMILY, label=label_of(K), L=L, start="random", chain=c))) for c in sampler.CHAINS]
            for L in (big, PARTNER[big])}


def g1(path, L):
    with np.load(path) as z:
        return z["G"][:, sampler.SIZES[L] - 1]   # the final-level g1 series (N,): the quantity navigate._read expects


def load_rehearsal(root, K, big=BIG):
    """(a, b) python lists of the final-level g1 of each chain at L big / its partner. 0 matches: the chain is absent (under-replication, the needle REFUSEs); >= 2 matches: AMBIGUOUS, ([], [])."""
    found = paths(root, K, big)
    clear = not any(len(m) > 1 for ms in found.values() for m in ms)
    pick = lambda L: [g1(m[0], L) for m in found[L] if len(m) == 1]   # noqa: E731
    return {True: lambda: (pick(big), pick(PARTNER[big])), False: lambda: ([], [])}[clear]()


def file_shas(root, K, big=BIG):
    """sha256 over the raw BYTES of every file load_rehearsal could open (sorted; every match, ambiguous ones included; none found -> the empty digest): what was read (T23), no array pass."""
    h = hashlib.sha256()
    [h.update(p.read_bytes()) for p in sorted(p for ms in paths(root, K, big).values() for m in ms for p in m)]
    return h.hexdigest()


def load_sample(tools, K, L, start, seed, run):
    """The off-grid probe: one chain from the pinned sampler (sampler.load(toolset) -> tools), h = 0. The costed path (tau(K) rule); P5 does not call it."""
    return sampler.sample(tools, K, 0.0, L, start, seed, run)[0].G[:, sampler.SIZES[L] - 1]
