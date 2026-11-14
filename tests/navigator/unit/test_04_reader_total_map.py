"""Test 4 (plan 1511 §3, §1b, §11.1): the reader is a total map  line -> Reply | Malformed | EOF  and
judge(parsed, expected_op, expected_i) -> Evaluated | NotEvaluated. Validity = (op == expected_op AND index == expected_i)."""
import json

import pytest

from navigator import reader as R


def line(**d):
    return json.dumps(d) + "\n"


def test_matching_op_and_index_is_evaluated():
    j = R.judge(R.parse_line(line(op="ok", index=450)), "ok", 450)
    assert isinstance(j, R.Evaluated) and j.reply.op == "ok" and j.reply.index == 450


def test_slow_reply_with_matching_index_is_used():
    # latency is not a signal: nothing in the map sees time; the same line is the same judgement however late it arrives
    assert isinstance(R.judge(R.parse_line(line(op="obs", E2=-3.0, index=900)), "obs", 900), R.Evaluated)


def test_nev_carrying_the_matching_index_is_not_evaluated():
    assert R.judge(R.parse_line(line(op="nev", index=450)), "ok", 450) == R.NotEvaluated()


@pytest.mark.parametrize("idx", [0, 449, 451, 10**9, -1])
def test_index_mismatch_is_not_evaluated(idx):
    assert R.judge(R.parse_line(line(op="ok", index=idx)), "ok", 450) == R.NotEvaluated()


def test_wrong_op_with_matching_index_is_not_evaluated():
    assert R.judge(R.parse_line(line(op="obs", index=450, E2=1.0)), "ok", 450) == R.NotEvaluated()


@pytest.mark.parametrize("bad", ["garbage\n", "{\n", "[1,2]\n", "3\n", "null\n", '"ok"\n', "\n"])
def test_malformed_lines_are_not_evaluated(bad):
    p = R.parse_line(bad)
    assert isinstance(p, R.Malformed)
    assert R.judge(p, "ok", 0) == R.NotEvaluated()


@pytest.mark.parametrize("eof", ["", None])
def test_eof_is_not_evaluated(eof):
    p = R.parse_line(eof)
    assert p == R.EOF
    assert R.judge(p, "ok", 0) == R.NotEvaluated()


@pytest.mark.parametrize("idx", ["450", 450.0, True, None, [450]])
def test_non_int_index_is_not_evaluated(idx):
    assert R.judge(R.parse_line(json.dumps({"op": "ok", "index": idx}) + "\n"), "ok", 450) == R.NotEvaluated()


def test_missing_index_or_op_is_not_evaluated():
    assert R.judge(R.parse_line(line(op="ok")), "ok", 0) == R.NotEvaluated()
    assert R.judge(R.parse_line(line(index=0)), "ok", 0) == R.NotEvaluated()


def test_map_is_total_over_arbitrary_input():
    for s in ["", "\n", "{}", "{}\n", "\x00", "{\"op\": 7, \"index\": 0}\n", "é\n", "{\"op\":\"ok\",\"index\":1e999}\n"]:
        assert isinstance(R.judge(R.parse_line(s), "ok", 0), (R.Evaluated, R.NotEvaluated))
