"""Plan 1511 §11.10: the pure, total grader. score(truth, verdict) -> Cell over Truth x Verdict (12 cells, none missing).
The needle never imports this. The POINT column and the decoy row are UNREACHED at Stage 1 (declared, not omitted)."""
from enum import Enum
from itertools import product


class Truth(str, Enum):
    present = "present"
    absent = "absent"
    decoy = "decoy"


class Verdict(str, Enum):
    LINE = "LINE"
    POINT = "POINT"
    ABSENT = "ABSENT"
    REFUSE = "REFUSE"


class Cell(Enum):
    TRUE_LINE = "TRUE_LINE"
    FALSE_LINE = "FALSE_LINE"
    TRUE_ABSENT = "TRUE_ABSENT"
    FALSE_ABSENT = "FALSE_ABSENT"
    REFUSED = "REFUSED"
    UNREACHED = "UNREACHED"


_ROWS = {
    Truth.present: (Cell.TRUE_LINE, Cell.UNREACHED, Cell.FALSE_ABSENT, Cell.REFUSED),
    Truth.absent: (Cell.FALSE_LINE, Cell.UNREACHED, Cell.TRUE_ABSENT, Cell.REFUSED),
    Truth.decoy: (Cell.UNREACHED,) * 4,
}
TABLE = {(t, v): c for t, row in _ROWS.items() for v, c in zip(Verdict, row)}
assert set(TABLE) == set(product(Truth, Verdict))  # total by construction: no gap, no extra


def score(truth, verdict):
    return TABLE[(Truth(truth), Verdict(verdict))]
