"""fingerprint.py - the family fingerprints as maths: consecutive and all-pairs differences by A (maths)."""
import sign
from kernel import A


def code_steps(x, rel):
    """The sign cell of each consecutive difference of one component, A over the declared chain, eps = 0: three cells."""
    d = A(x, rel).spatial[0]
    return [s.value for s in sign.sign(d, d, 0)]


def pair_differences(x, rel):
    """y(j) - y(i) per resample row for every edge (j -> i) of the declared all-pairs relation: [rows, edges]."""
    return A(x, rel).spatial
