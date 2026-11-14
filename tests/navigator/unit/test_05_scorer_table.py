"""Test 5, unit half (plan 1511 §3, §11.10): score(truth, verdict) -> Cell is a TOTAL table over Truth x Verdict."""
from itertools import product

import pytest

from environment import score as S

EXPECT = {
    ("present", "LINE"): "TRUE_LINE", ("present", "POINT"): "UNREACHED", ("present", "ABSENT"): "FALSE_ABSENT",
    ("present", "REFUSE"): "REFUSED",
    ("absent", "LINE"): "FALSE_LINE", ("absent", "POINT"): "UNREACHED", ("absent", "ABSENT"): "TRUE_ABSENT",
    ("absent", "REFUSE"): "REFUSED",
    ("decoy", "LINE"): "UNREACHED", ("decoy", "POINT"): "UNREACHED", ("decoy", "ABSENT"): "UNREACHED",
    ("decoy", "REFUSE"): "UNREACHED",
}


def test_axes_and_cell_names_are_exactly_the_declared_ones():
    assert [t.value for t in S.Truth] == ["present", "absent", "decoy"]
    assert [v.value for v in S.Verdict] == ["LINE", "POINT", "ABSENT", "REFUSE"]
    assert {c.name for c in S.Cell} == {"TRUE_LINE", "FALSE_LINE", "TRUE_ABSENT", "FALSE_ABSENT", "REFUSED", "UNREACHED"}


def test_table_covers_the_whole_product_with_no_gap_and_no_extra():
    assert set(S.TABLE) == set(product(S.Truth, S.Verdict))
    assert len(S.TABLE) == 12


@pytest.mark.parametrize("truth,verdict", list(EXPECT))
def test_all_twelve_cells_are_pinned(truth, verdict):
    assert S.score(truth, verdict).name == EXPECT[(truth, verdict)]


def test_the_four_reachable_reds_are_table_lookups():
    assert S.score("present", "LINE") == S.Cell.TRUE_LINE
    assert S.score("absent", "ABSENT") == S.Cell.TRUE_ABSENT
    assert S.score("absent", "LINE") == S.Cell.FALSE_LINE
    assert S.score("present", "REFUSE") == S.Cell.REFUSED


def test_score_takes_exactly_truth_and_verdict():
    import inspect
    assert list(inspect.signature(S.score).parameters) == ["truth", "verdict"]  # no ordered_side: the scorer never sees it
