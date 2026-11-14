"""T0 (plan 1511 §2): wire + declare + refuse-to-start. Tests 1/2 end to end."""
import json
import subprocess
import sys

import pytest

from conftest import (ROOT, Wire, fake_server, free_port, honest_declared, honest_responder, make_configs, real_server)
from navigator import needle as N

DECL_FIELDS = ["knobs_K", "ordered_side", "L", "tau", "k", "index_unit", "index_kind", "observable"]


def run_needle(tmp_path, responder, **needle):
    with fake_server(responder) as fs:
        cfg = make_configs(tmp_path, needle=needle, port=fs.port)
        r = N.run(cfg["needle"])
        return r, fs


@pytest.mark.parametrize("field", DECL_FIELDS)
def test_needle_refuses_to_start_when_server_drops_a_field(tmp_path, field):
    r, fs = run_needle(tmp_path, honest_responder(declared=honest_declared(drop=[field])))
    assert r == N.RefusedToStart(field=field, parse="A")
    assert "where" not in fs.ops  # refused at the declaration; never asks the driver face


def test_needle_refuses_to_start_when_server_ill_types_a_field(tmp_path):
    r, _ = run_needle(tmp_path, honest_responder(declared=honest_declared(L="27")))
    assert r == N.RefusedToStart(field="L", parse="A")
    r, _ = run_needle(tmp_path, honest_responder(declared=honest_declared(tau=-3)))
    assert r == N.RefusedToStart(field="tau", parse="A")


def test_needle_refuses_to_start_on_eof_at_declare(tmp_path):
    r, _ = run_needle(tmp_path, lambda m, raw: "EOF")
    assert isinstance(r, N.RefusedToStart) and r.parse == "A"


def test_malformed_edge_is_refused_to_start_not_refuse(tmp_path):
    for edge in ({"op": "edge", "K_c": "x", "w": 0.02}, {"op": "edge", "K_c": 0.34888, "w": -1.0},
                 {"op": "edge", "K_c": 0.34888}, {"op": "nev"}):
        r, _ = run_needle(tmp_path, honest_responder(edge=edge))
        assert isinstance(r, N.RefusedToStart) and r.parse == "A", edge


def test_negative_u_is_refused_before_connecting(tmp_path):
    r, fs = run_needle(tmp_path, honest_responder(), u=-0.1)
    assert r == N.RefusedToStart(field="u", parse="B")
    assert fs.seen == []


def test_u_above_u_max_is_refused_after_where(tmp_path):
    r, fs = run_needle(tmp_path, honest_responder(), u=0.2)  # u_max = 0.50 - 0.34888
    assert r == N.RefusedToStart(field="u", parse="u_range")
    assert fs.ops[:2] == ["declare", "where"]


def test_honest_server_is_not_refused(tmp_path):
    r, fs = run_needle(tmp_path, honest_responder())
    assert not isinstance(r, N.RefusedToStart)
    assert fs.ops[:2] == ["declare", "where"]


def test_real_server_declares_and_serves_where(tmp_path):
    cfg = make_configs(tmp_path)
    with real_server(cfg):
        w = Wire(cfg["port"])
        try:
            d = w.call({"op": "declare"})
            assert d == honest_declared()  # no index, no w
            e = w.call({"op": "where"})
            assert e["op"] == "edge" and e["index"] == 0 and e["w"] == 0.02
            assert abs(e["K_c"] - 0.34888) < 5e-6
        finally:
            w.close()


def test_server_with_bad_at_toml_exits_2_naming_the_field(tmp_path):
    cfg = make_configs(tmp_path, at=dict(L4=-0.1))
    p = subprocess.run([sys.executable, "-m", "environment.server", "--env", str(cfg["env"]), "--at", str(cfg["at"]),
                        "--run-dir", str(tmp_path / "rd")], cwd=ROOT, capture_output=True, text=True, timeout=120)
    assert p.returncode == 2
    assert "L4" in p.stderr


def test_orchestrator_exit_2_and_refused_json_on_bad_needle_toml(tmp_path):
    cfg = make_configs(tmp_path, needle=dict(u=-0.1))
    p = subprocess.run([sys.executable, "-m", "environment.run", "--env", str(cfg["env"]), "--needle", str(cfg["needle"]),
                        "--at", str(cfg["at"])], cwd=ROOT, capture_output=True, text=True, timeout=120)
    assert p.returncode == 2, p.stderr
    assert "RefusedToStart" in p.stderr and "u" in p.stderr
    files = list(cfg["out"].glob("*/refused.json"))
    assert len(files) == 1
    assert json.loads(files[0].read_text()) == {"kind": "RefusedToStart", "field": "u", "parse": "B"}
    assert not list(cfg["out"].glob("*/verdict.json"))
