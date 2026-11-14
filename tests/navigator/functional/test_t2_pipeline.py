"""T2 (plan 1511 §2): verdict + floor + table + golden, end to end through the orchestrator (server subprocess, needle in-process).
Tests 3 (floor, e2e), 5 (functional half), 7 (reproducibility / golden), plus the perf baseline (§11.4)."""
import json
import os
import subprocess
import sys
from pathlib import Path

from conftest import GOLDEN_AT, PLUGIN_DIR, ROOT, Wire, make_configs, port_bound, real_server, toml_dumps

sys.path.insert(0, str(PLUGIN_DIR / "vendor"))
import lattice_at  # noqa: E402

GOLDEN_DIR = Path(__file__).resolve().parents[1] / "golden"
K_C = float(lattice_at.self_dual_K(GOLDEN_AT["L4"]))


def orch(cfg):
    p = subprocess.run([sys.executable, "-m", "environment.run", "--env", str(cfg["env"]), "--needle", str(cfg["needle"]),
                        "--at", str(cfg["at"])], cwd=ROOT, capture_output=True, text=True, timeout=120)
    return p


def only_run_dir(cfg):
    kids = [d for d in cfg["out"].iterdir() if d.is_dir()]
    assert len(kids) == 1, kids
    return kids[0]


def verdict_of(cfg):
    p = orch(cfg)
    assert p.returncode == 0, p.stderr
    rd = only_run_dir(cfg)
    return json.loads((rd / "verdict.json").read_text()), rd


def test_golden_config_is_present_LINE_TRUE_LINE(tmp_path):
    v, rd = verdict_of(make_configs(tmp_path))
    assert v["truth"] == "present" and v["verdict"] == {"kind": "LINE", "reason": None} and v["cell"] == "TRUE_LINE"
    assert set(v) == {"plan", "run_id", "env_seed", "declaration", "truth", "verdict", "cell", "rounds"}
    assert v["plan"] == "1511" and v["env_seed"] == 22 and v["run_id"] == rd.name and len(v["run_id"]) == 16
    assert v["declaration"] == {"op": "declared", "knobs_K": [0.2, 0.5], "ordered_side": "+K", "L": 27, "tau": 67, "k": 6,
                                "index_unit": "sweep", "index_kind": "sample_counter", "observable": "E2"}
    assert [r["round"] for r in v["rounds"]] == list(range(1, 9))
    assert [r["index"] for r in v["rounds"]] == [450 * i for i in range(1, 9)]
    assert all(r["evaluated"] and isinstance(r["E2"], float) and r["K"] == K_C + 0.0 for r in v["rounds"])
    assert set(os.listdir(rd)) >= {"verdict.json", "perf.json", "config.json"}


def test_off_band_u_is_absent_TRUE_ABSENT(tmp_path):
    v, _ = verdict_of(make_configs(tmp_path, needle=dict(u=0.05)))
    assert v["truth"] == "absent" and v["verdict"]["kind"] == "ABSENT" and v["cell"] == "TRUE_ABSENT"
    assert v["rounds"][0]["K"] == K_C + 0.05  # the orchestrator's K = K_c(edge) + u agrees with the scorer's config-side K_c


def test_below_floor_is_REFUSE_floor_cell_REFUSED_with_no_rounds(tmp_path):
    v, rd = verdict_of(make_configs(tmp_path, needle=dict(n=50)))
    assert v["verdict"] == {"kind": "REFUSE", "reason": "floor"} and v["cell"] == "REFUSED"
    assert v["rounds"] == [] and v["truth"] == "present" and v["declaration"]["k"] == 6


def test_refuse_floor_in_off_band_config_is_still_REFUSED_truth_absent(tmp_path):
    v, _ = verdict_of(make_configs(tmp_path, needle=dict(n=50, u=0.05)))
    assert v["truth"] == "absent" and v["cell"] == "REFUSED"


def test_u_out_of_range_exits_2_with_refused_json(tmp_path):
    cfg = make_configs(tmp_path, needle=dict(u=0.2))
    p = orch(cfg)
    assert p.returncode == 2 and "RefusedToStart" in p.stderr
    assert json.loads((only_run_dir(cfg) / "refused.json").read_text()) == {"kind": "RefusedToStart", "field": "u",
                                                                           "parse": "u_range"}
    assert not (only_run_dir(cfg) / "verdict.json").exists()


def test_perf_baseline_rows_are_measured_and_never_on_the_wire(tmp_path):
    v, rd = verdict_of(make_configs(tmp_path))
    rows = json.loads((rd / "perf.json").read_text())
    assert [r["op"] for r in rows] == ["declare", "where"] + ["set", "step", "sense"] * 8
    assert all(set(r) == {"op", "n", "seconds"} and isinstance(r["seconds"], float) and r["seconds"] >= 0 for r in rows)
    assert [r["n"] for r in rows if r["op"] == "step"] == [450] * 8 and all(r["n"] is None for r in rows if r["op"] != "step")
    # never sent over the wire: no reply carries a timing field
    cfg = make_configs(tmp_path / "w")
    with real_server(cfg):
        w = Wire(cfg["port"])
        try:
            for msg in ({"op": "declare"}, {"op": "where"}, {"op": "set", "K": 0.3}, {"op": "step", "n": 2}, {"op": "sense"}):
                assert not {"seconds", "perf", "time"} & set(w.call(msg))
        finally:
            w.close()


def test_7_golden_run_is_byte_identical_and_matches_the_cut_golden(tmp_path):
    """The pinned golden config (repo needle.toml + at.toml, port 8787): same configs => byte-identical verdict.json.
    The golden is cut ONCE (NAVIGATOR_CUT_GOLDEN=1) and thereafter re-asserted byte-identical."""
    assert not port_bound(8787), "port 8787 (the golden config's port) is busy"
    envp = tmp_path / "environment.toml"
    runs = []
    for i in (1, 2):
        out = tmp_path / f"out{i}"
        envp.write_text(toml_dumps(dict(system="at", port=8787, run_dir_root=str(out))))
        p = subprocess.run([sys.executable, "-m", "environment.run", "--env", str(envp), "--needle",
                            str(ROOT / "navigator" / "needle.toml"), "--at", str(PLUGIN_DIR / "at.toml")],
                           cwd=ROOT, capture_output=True, text=True, timeout=120)
        assert p.returncode == 0, p.stderr
        rd = next(out.iterdir())
        runs.append((rd.name, (rd / "verdict.json").read_bytes()))
    assert runs[0] == runs[1]
    rid, blob = runs[0]
    golden = GOLDEN_DIR / f"verdict-{rid}.json"
    if os.environ.get("NAVIGATOR_CUT_GOLDEN") == "1" and not golden.exists():
        golden.write_bytes(blob)
    assert golden.exists(), f"no golden cut for run_id {rid}"
    assert golden.read_bytes() == blob
