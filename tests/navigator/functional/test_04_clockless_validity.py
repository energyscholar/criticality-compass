"""Test 4, functional half (plan 1511 §3, §1b): the needle's rounds over a socket with injected latency / stale / substituted
replies. Faults are SUBSTITUTED (nev / garbage / wrong index / EOF), never withheld. Verdict invariant under latency;
a runtime assert the needle's socket has no timeout."""
import json
import socket

from conftest import fake_server, honest_responder, latency_proxy, make_configs
from navigator import needle as N

ROUNDS = 8
# reply numbering through the proxy: 1=declared 2=edge, then round r (1-based) = replies 3r, 3r+1, 3r+2 = set, step, sense


def reply_no(r, which):  # which in 0,1,2 = set,step,sense
    return 3 * r + which


def run_via_proxy(tmp_path, transform=None, delay=0.0, **needle):
    with fake_server(honest_responder()) as fs, latency_proxy(fs.port, delay, transform) as px:
        cfg = make_configs(tmp_path, needle=needle, port=px.port)
        return N.run(cfg["needle"]), fs


def test_clean_run_evaluates_every_round_and_tracks_the_index(tmp_path):
    v, fs = run_via_proxy(tmp_path)
    assert isinstance(v, N.Verdict) and v.kind == "LINE" and v.reason is None
    assert [r["round"] for r in v.rounds] == list(range(1, ROUNDS + 1))
    assert all(r["evaluated"] for r in v.rounds)
    assert [r["index"] for r in v.rounds] == [450 * r for r in range(1, ROUNDS + 1)]  # post-step cumulative sweeps
    assert all(abs(r["K"] - (0.34888 + 0.0)) < 1e-12 for r in v.rounds)
    assert v.declaration.L == 27 and v.edge.w == 0.02
    assert fs.ops[:2] == ["declare", "where"]
    assert fs.ops[2:5] == ["set", "step", "sense"]


def test_verdict_is_invariant_under_per_call_latency(tmp_path):
    fast, _ = run_via_proxy(tmp_path / "a")
    slow, _ = run_via_proxy(tmp_path / "b", delay=0.04)
    assert slow == fast


def test_index_matched_slow_reply_is_used(tmp_path):
    # one reply arrives very late (a test-side sleep); the needle has no clock, so it just waits and uses it
    import time

    def tr(n, sent, rep):
        if n == reply_no(3, 2):
            time.sleep(0.4)
        return rep
    v, _ = run_via_proxy(tmp_path, tr)
    assert v.kind == "LINE" and all(r["evaluated"] for r in v.rounds)


def _inject(tmp_path, n_target, mutate):
    def tr(n, sent, rep):
        return mutate(rep) if n == n_target else rep
    return run_via_proxy(tmp_path, tr)


def _only_round_unevaluated(v, rnd):
    assert [r["round"] for r in v.rounds] == list(range(1, ROUNDS + 1)), "the needle runs all N rounds, never aborts early"
    assert [r["evaluated"] for r in v.rounds] == [r != rnd for r in range(1, ROUNDS + 1)]
    assert v.kind == "REFUSE" and v.reason == "budget"
    assert v.rounds[rnd - 1]["E2"] is None


def test_nev_with_matching_index_is_not_evaluated_and_later_rounds_stay_in_sync(tmp_path):
    for which in (0, 1, 2):
        v, _ = _inject(tmp_path / str(which), reply_no(2, which),
                       lambda rep: json.dumps({"op": "nev", "index": json.loads(rep)["index"]}))
        _only_round_unevaluated(v, 2)


def test_garbage_line_is_not_evaluated(tmp_path):
    v, _ = _inject(tmp_path, reply_no(4, 1), lambda rep: "}{ not json")
    _only_round_unevaluated(v, 4)


def test_wrong_index_is_not_evaluated(tmp_path):
    for delta in (-450, 1, 450):
        v, _ = _inject(tmp_path / str(delta), reply_no(3, 2),
                       lambda rep, d=delta: json.dumps({**json.loads(rep), "index": json.loads(rep)["index"] + d}))
        _only_round_unevaluated(v, 3)


def test_wrong_op_with_matching_index_is_not_evaluated(tmp_path):
    v, _ = _inject(tmp_path, reply_no(5, 0), lambda rep: json.dumps({"op": "obs", "E2": 0.0, "index": json.loads(rep)["index"]}))
    _only_round_unevaluated(v, 5)


def test_obs_without_a_float_E2_is_not_evaluated(tmp_path):
    v, _ = _inject(tmp_path, reply_no(2, 2), lambda rep: json.dumps({"op": "obs", "E2": "x", "index": json.loads(rep)["index"]}))
    _only_round_unevaluated(v, 2)


def test_eof_mid_run_is_absence_for_every_remaining_round(tmp_path):
    v, _ = _inject(tmp_path, reply_no(3, 1), lambda rep: "EOF")
    assert [r["round"] for r in v.rounds] == list(range(1, ROUNDS + 1))
    assert [r["evaluated"] for r in v.rounds] == [True, True] + [False] * 6
    assert v.kind == "REFUSE" and v.reason == "budget"


def test_eof_replaces_the_whole_connection_without_raising(tmp_path):
    # the server just closes at the first `set`
    state = {"n": 0}

    def resp(msg, raw):
        if msg and msg.get("op") == "set":
            return "EOF"
        return honest_responder()(msg, raw)
    with fake_server(resp) as fs:
        cfg = make_configs(tmp_path, port=fs.port)
        v = N.run(cfg["needle"])
    assert isinstance(v, N.Verdict) and v.kind == "REFUSE" and v.reason == "budget"
    assert not any(r["evaluated"] for r in v.rounds) and len(v.rounds) == ROUNDS


def test_needle_socket_has_no_timeout_at_runtime(tmp_path, monkeypatch):
    seen = []
    orig_init, orig_close = N._Wire.__init__, N._Wire.close

    def init(self, *a, **k):
        orig_init(self, *a, **k)
        seen.append(("open", self.sock.gettimeout()))

    def close(self):
        seen.append(("close", self.sock.gettimeout()))
        orig_close(self)
    monkeypatch.setattr(N._Wire, "__init__", init)
    monkeypatch.setattr(N._Wire, "close", close)
    assert socket.getdefaulttimeout() is None
    with fake_server(honest_responder()) as fs:
        N.run(make_configs(tmp_path, port=fs.port)["needle"])
    assert seen == [("open", None), ("close", None)]


def test_verdict_kind_is_by_the_band(tmp_path):
    out = {}
    for name, u in (("line", 0.015), ("off", 0.05)):  # |K-K_c| = u: inside / outside w=0.02
        with fake_server(honest_responder()) as fs:
            out[name] = N.run(make_configs(tmp_path / name, port=fs.port, needle=dict(u=u))["needle"])
    assert (out["line"].kind, out["line"].reason) == ("LINE", None)
    assert (out["off"].kind, out["off"].reason) == ("ABSENT", None)
