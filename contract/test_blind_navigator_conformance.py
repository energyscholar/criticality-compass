"""Plan 1525 — TRACK-N acceptance (the closed-loop needle, blind). Runs the REAL orchestrator `environment.run_blind`,
which launches the REAL blind server and the needle `navigator.recover` as a subprocess (contract/SCHEMA-1525.md).
FROZEN: the Generator makes this green; it does not edit this file.

What it pins:
  1. the loop runs all N rounds, ONE `measure` per round, and NOTHING else on the wire (no `where`, no Stage-1/2 op);
  2. every round is evaluated and the report is `Located` — a wrong index/shape would read as REFUSE(budget), so
     Located proves the moments parse and index arithmetic end to end;
  3. the needle STEERS ON ITS OWN READINGS: each round's grid is the declared m-point grid of the current bracket, and
     each round's (A, B, lo, hi) equals `narrow` recomputed from that round's REPORTED moments — a needle that ignored or
     swapped its readings fails here, not later in the scored run;
  4. scoring is outside the needle and total: the same deterministic run is HIT under a generous score file and MISS
     under an impossible one; `contains`/`width`/`narrow_enough` are reported separately;
  5. the needle cannot reach the truth: an import allowlist (no os/pathlib/glob/subprocess/importlib/environment) and no
     string constant naming the truth file, the plugin tree or `where`;
  6. the declared refusals are values with the declared exit codes (strict configs, bracket, nlev, floor, unreachable).
This is a STRUCTURAL test on a tiny lattice. The physics acceptance is the declared L=81 run in the plan, not here.

RED until environment/run_blind.py, environment/blind_server.py, navigator/recover.py, navigator/estimate.py exist.
Run from the repo root:  python contract/test_blind_navigator_conformance.py   (or pytest)
"""
import ast
import json
import socket
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
M, N_ROUNDS, N_EQ, S, SKIP, Z = 5, 3, 3, 40, 1, 2.0
BRACKET = (0.25, 0.45)
AT_GOOD = {"L_blocks": "3", "L4": "0.14", "burn": "5", "seed": "11", "k": "1", "nlev": "2", "knobs_K": "[0.20, 0.50]",
           "K_start": "0.20", "index_unit": '"sweep"', "index_kind": '"sample_counter"'}
NEEDLE_GOOD = {"needle_structure": '"recover-adaptive-v0"', "bracket": f"[{BRACKET[0]}, {BRACKET[1]}]", "m": str(M),
               "N": str(N_ROUNDS), "n_eq": str(N_EQ), "S": str(S), "skip": str(SKIP), "z": str(Z)}
ALLOWED_IMPORTS = {"argparse", "json", "math", "socket", "sys", "tomllib", "dataclasses", "typing", "collections", "navigator"}


def _free_port():
    s = socket.socket(); s.bind(("127.0.0.1", 0)); p = s.getsockname()[1]; s.close(); return p


def _toml(d):
    return "".join(f"{k} = {v}\n" for k, v in d.items())


def _write(tmp, a="1.0", w_max="1.0", at=None, needle=None):
    port = _free_port()
    at_dir = tmp / "plugins_at"; at_dir.mkdir(parents=True, exist_ok=True)
    env_path, at_path = tmp / "environment.toml", at_dir / "at-blind.toml"
    env_path.write_text(f'system = "at"\nport = {port}\nrun_dir_root = "{tmp / "runs"}"\n')
    at_path.write_text(_toml(AT_GOOD if at is None else at))
    (at_dir / "tau-v0.toml").write_text("value = 1.0\n")
    needle_path = tmp / "recover.toml"
    needle_path.write_text(_toml(NEEDLE_GOOD if needle is None else needle))
    score = tmp / "score-1525.toml"
    score.write_text(f"a = {a}\nw_max = {w_max}\n")
    return env_path, at_path, needle_path, score


def _orchestrate(tmp, **kw):
    env_path, at_path, needle, score = _write(tmp, **kw)
    res = subprocess.run([sys.executable, "-m", "environment.run_blind", "--env", str(env_path), "--at", str(at_path),
                          "--needle", str(needle), "--score", str(score)],
                         cwd=str(ROOT), stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=600)
    dirs = sorted(p for p in (tmp / "runs").glob("*") if p.is_dir()) if (tmp / "runs").exists() else []
    return res, dirs


def _run(tmp, **kw):
    res, dirs = _orchestrate(tmp, **kw)
    assert res.returncode == 0, f"run_blind rc={res.returncode} stderr={res.stderr}"
    assert len(dirs) == 1 and (dirs[0] / "verdict.json").is_file(), f"expected one run dir with verdict.json: {dirs}"
    return json.loads((dirs[0] / "verdict.json").read_text()), json.loads((dirs[0] / "perf.json").read_text())


def _refused(tmp, **kw):
    res, dirs = _orchestrate(tmp, **kw)
    assert res.returncode == 2, f"expected exit 2 (RefusedToStart), got {res.returncode} stderr={res.stderr}"
    assert len(dirs) == 1 and (dirs[0] / "refused.json").is_file(), f"expected one run dir with refused.json: {dirs}"
    assert not (dirs[0] / "verdict.json").exists(), "a refused run must not be scored"
    r = json.loads((dirs[0] / "refused.json").read_text())
    assert r["kind"] == "RefusedToStart" and isinstance(r["field"], str), r
    return r


def _close(a, b):
    return abs(a - b) <= 1e-12


def test_closed_loop_runs_blind_and_steers_on_its_own_readings(tmp_path):
    from navigator.estimate import narrow
    v, perf = _run(tmp_path)
    ops = [e["op"] for e in perf]
    assert ops == ["declare"] + ["measure"] * N_ROUNDS, f"wire ops must be declare + {N_ROUNDS}×measure only: {ops}"
    assert v["kind"] == "Located", f"expected Located (all rounds evaluated); got {v['kind']} {v.get('reason')}"
    rounds = v["rounds"]
    assert len(rounds) == N_ROUNDS and all(r["evaluated"] for r in rounds), rounds
    lo, hi = BRACKET
    per = M * (N_EQ + S * SKIP)
    for k, r in enumerate(rounds, start=1):
        want = [lo] + [lo + i * (hi - lo) / (M - 1) for i in range(1, M - 1)] + [hi]
        assert len(r["grid"]) == M and all(_close(g, x) for g, x in zip(r["grid"], want)), (k, r["grid"], want)
        assert r["grid"][0] == lo and r["grid"][-1] == hi, ("grid endpoints must be exact", k, r["grid"], lo, hi)
        assert r["index"] == k * per, (k, r["index"], k * per)
        n = narrow(r["grid"], r["C"], r["C_err"], r["Gs"], r["Gs_err"], Z)
        assert list(r["A"]) == list(n.A) and list(r["B"]) == list(n.B), ("A/B must be narrow() of the reported moments", k, r, n)
        assert r["lo"] == n.lo and r["hi"] == n.hi, ("the bracket must be narrow() of the reported moments", k, r["lo"], r["hi"], n)
        assert all(_close(d, g[1] - g[0]) for d, g in zip(r["D"], r["Gs"])), ("D", k)
        assert lo <= r["lo"] < r["hi"] <= hi, f"round {k} bracket {r['lo'], r['hi']} not nested in {lo, hi}"
        lo, hi = r["lo"], r["hi"]
    assert v["bracket"] == [lo, hi], (v["bracket"], lo, hi)
    assert v["cell"] == "HIT" and v["contains"] is True and v["narrow_enough"] is True, v   # a = w_max = 1.0
    assert _close(v["width"], hi - lo), v
    assert v["plan"] == "1525" and isinstance(v["truth_K_c"], float), v


def test_scoring_is_outside_the_needle_and_total(tmp_path):
    v, _ = _run(tmp_path, a="0.0", w_max="1e-9")             # nothing can be this narrow ⇒ MISS (by width)
    assert v["kind"] == "Located", v["kind"]
    assert v["cell"] == "MISS" and v["narrow_enough"] is False, v


def test_floor_is_a_scored_refusal(tmp_path):
    v, perf = _run(tmp_path, at=dict(AT_GOOD, k="5"))         # n_eq = 3 < k*tau = 5*1.0
    assert v["kind"] == "REFUSE" and v["reason"] == "floor" and v["rounds"] == [] and v["cell"] == "REFUSED", v
    assert v["bracket"] is None and v["contains"] is None, v
    assert [e["op"] for e in perf] == ["declare"], perf


def test_strict_configs_refuse_to_start(tmp_path):
    cases = {
        "at_missing_K_start": dict(at={k: v for k, v in AT_GOOD.items() if k != "K_start"}),
        "at_K_start_outside_knobs": dict(at=dict(AT_GOOD, K_start="0.60")),
        "at_unknown_key": dict(at=dict(AT_GOOD, w="0.02")),
        "at_nlev_1": dict(at=dict(AT_GOOD, nlev="1")),
        "needle_m_4": dict(needle=dict(NEEDLE_GOOD, m="4")),
        "needle_unknown_key": dict(needle=dict(NEEDLE_GOOD, port="8788")),
        "needle_bracket_outside_knobs": dict(needle=dict(NEEDLE_GOOD, bracket="[0.10, 0.45]")),
        "score_negative_a": dict(a="-0.1"),
    }
    for name, kw in cases.items():
        sub = tmp_path / name; sub.mkdir()
        try:
            _refused(sub, **kw)
        except AssertionError as e:
            raise AssertionError(f"{name}: {e}") from None


def test_needle_alone_is_unreachable_with_no_server(tmp_path):
    needle = tmp_path / "recover.toml"; needle.write_text(_toml(NEEDLE_GOOD))
    res = subprocess.run([sys.executable, "-m", "navigator.recover", "--needle", str(needle), "--port", str(_free_port())],
                         cwd=str(ROOT), stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=60)
    assert res.returncode == 1 and res.stdout == "", (res.returncode, res.stdout, res.stderr)
    assert res.stderr.startswith("Unreachable") and "Traceback" not in res.stderr, res.stderr   # exit 1 alone is also "no module"


def test_needle_cannot_reach_the_truth():
    banned_strings = ("where", "edge", "edge.json", "vendor", "plugins", "system-instantiated", "at-blind", "lattice_at")
    for rel in ("navigator/recover.py", "navigator/estimate.py"):
        tree = ast.parse((ROOT / rel).read_text())
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for a in node.names:
                    assert a.name.split(".")[0] in ALLOWED_IMPORTS, (rel, a.name)
            if isinstance(node, ast.ImportFrom):
                assert node.level == 0 and (node.module or "").split(".")[0] in ALLOWED_IMPORTS, (rel, node.module)
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                assert not any(b == node.value or (b != "where" and b in node.value) for b in banned_strings), (rel, node.value)
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                assert node.func.id not in ("__import__", "exec", "eval"), (rel, node.func.id)


if __name__ == "__main__":
    import tempfile
    _tests = [test_closed_loop_runs_blind_and_steers_on_its_own_readings, test_scoring_is_outside_the_needle_and_total,
              test_floor_is_a_scored_refusal, test_strict_configs_refuse_to_start, test_needle_alone_is_unreachable_with_no_server,
              test_needle_cannot_reach_the_truth]
    _fail = 0
    for _t in _tests:
        with tempfile.TemporaryDirectory() as _d:
            try:
                (_t(Path(_d)) if _t.__code__.co_argcount else _t()); print(f"PASS {_t.__name__}")
            except Exception as _e:  # noqa: BLE001
                _fail += 1; print(f"FAIL {_t.__name__}: {type(_e).__name__}: {_e}")
    print(f"{len(_tests) - _fail}/{len(_tests)} passed")
    sys.exit(1 if _fail else 0)
