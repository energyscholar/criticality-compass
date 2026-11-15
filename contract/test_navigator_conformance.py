"""Plan 1518 — TRACK-N acceptance (the Navigator face). Launches the REAL server (probe-capable) and runs
the REAL needle end to end with the NEW opt-in structure `margin-batched-v0`: it makes the SAME Stage-1
reading (one point K_c+u, verdict LINE iff |K−K_c|≤w) but over ONE `probe` call per round instead of
set+step+sense (3→1 round-trips). Stage-1's `margin-constant-v0` and its golden stay frozen and untouched.
We assert the verdict is `kind='LINE'` — the needle returns LINE only when all N rounds genuinely evaluated
(any unevaluated round ⇒ a budget-REFUSE, returned before LINE) AND |K−K_c|≤w — so LINE proves the batched
probe read real values end to end, index arithmetic included. (rc==0 and the probe count alone would NOT:
every Verdict, REFUSE included, exits 0 with N probes logged — a wrong index would pass vacuously.) We also
read the server's perf.json to prove the MECHANISM was `probe`, one per round. FROZEN: the Generator makes
this green by adding the `margin-batched-v0` structure; it does not edit this file.

RED until the structure exists: `reader.parse_needle_cfg` rejects any structure but `margin-constant-v0`,
so the needle RefusedToStart (exit 2) and never issues a `probe`.

Run from the repo root:  python -m pytest contract/test_navigator_conformance.py -x
"""
import json
import socket
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
# L4=0.15 ⇒ K_c≈0.343 (lattice_at.self_dual_K), inside KNOBS with room for ±u ⇒ the probe lands in-bounds
# and evaluates (NOT a degenerate out-of-bounds fixture that would REFUSE "budget" without exercising obs).
KNOBS = (0.20, 0.50)
L4 = 0.15
U = 0.02            # K_c+u ≈ 0.363 ∈ KNOBS; |probe−K_c| = u = 0.02 ≤ w ⇒ LINE
W = 0.05
N_ROUNDS = 3
N_SWEEPS = 4


def _free_port():
    s = socket.socket(); s.bind(("127.0.0.1", 0)); p = s.getsockname()[1]; s.close(); return p


def _write_cfgs(tmp, port):
    at_dir = tmp / "plugins_at"; at_dir.mkdir(parents=True, exist_ok=True)
    env_path = tmp / "environment.toml"; at_path = at_dir / "at.toml"
    env_path.write_text(f'system = "at"\nport = {port}\nrun_dir_root = "{tmp / "run"}"\n')
    at_path.write_text(
        f"L_blocks = 1\nL4 = {L4}\nburn = 4\nseed = 1\nk = 1\nnlev = 2\n"
        f"knobs_K = [{KNOBS[0]}, {KNOBS[1]}]\nw = {W}\n"
        'index_unit = "sweep"\nindex_kind = "sweep"\n'
    )
    (at_dir / "tau-v0.toml").write_text("value = 1.0\n")
    return env_path, at_path


def _launch_server(env_path, at_path, run_dir, port):
    proc = subprocess.Popen(
        [sys.executable, "-m", "environment.server", "--env", str(env_path),
         "--at", str(at_path), "--run-dir", str(run_dir)],
        cwd=str(ROOT), stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
    )
    for _ in range(600):
        if proc.poll() is not None:
            out, err = proc.communicate()
            raise AssertionError(f"server exited early rc={proc.returncode}\nstderr={err}")
        try:
            socket.create_connection(("127.0.0.1", port), timeout=0.2).close()
            return proc
        except OSError:
            time.sleep(0.05)
    proc.kill(); raise AssertionError("server never bound the port")


def test_needle_probes_the_bracket(tmp_path):
    port = _free_port()
    env_path, at_path = _write_cfgs(tmp_path, port)
    run_dir = tmp_path / "run"
    server = _launch_server(env_path, at_path, run_dir, port)
    try:
        needle_toml = tmp_path / "needle.toml"
        needle_toml.write_text(
            f'host = "127.0.0.1"\nport = {port}\nneedle_structure = "margin-batched-v0"\n'
            f"u = {U}\ndu = 0.02\nN = {N_ROUNDS}\nn = {N_SWEEPS}\n"
        )
        res = subprocess.run(
            [sys.executable, "-m", "navigator.needle", "--needle", str(needle_toml)],
            cwd=str(ROOT), stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=120,
        )
        assert res.returncode == 0, f"needle did not return a Verdict (rc={res.returncode}) err={res.stderr}"
        # ⚠ THE SHARP EDGE. Every Verdict (LINE/ABSENT/REFUSE) exits 0 and prints 3 probes, so rc==0 and the
        # probe count below are NOT enough: a wrong `judge` index rejects every reply ⇒ all rounds
        # evaluated=False ⇒ Verdict("REFUSE","budget") ⇒ still rc 0, still 3 probes — a vacuous pass. The
        # needle returns LINE *only* when all N rounds are genuinely evaluated (needle.py: any unevaluated
        # round ⇒ budget-REFUSE, returned before LINE) AND |K−K_c|≤w. With this in-bounds fixture a correct
        # batched probe MUST read LINE, so asserting LINE proves the probe evaluated end to end — index and all.
        assert "kind='LINE'" in res.stdout, (
            f"verdict was not LINE — a wrong parse_obs/judge index reads as REFUSE/budget here; stdout={res.stdout!r}")
    finally:
        server.terminate()
        server.wait(timeout=5)

    perf = json.loads((run_dir / "perf.json").read_text())
    ops = [e["op"] for e in perf]
    assert "probe" in ops, f"needle never issued a batched probe; ops seen: {sorted(set(ops))}"
    # one batched probe per round replaces per-point set/step/sense — proves the MECHANISM was probe, not set/step/sense
    assert ops.count("probe") == N_ROUNDS, f"expected {N_ROUNDS} probes (one per round), got {ops.count('probe')}"


if __name__ == "__main__":
    # The compass gate runs this as `python <file>`, so the assertion must run HERE too — a pytest file with
    # no runner would exit 0 without launching anything (a vacuous pass, the exact degenerate-pass trap this
    # test guards against). This runner makes RED red under the gate. (Also runnable via pytest.)
    import tempfile
    with tempfile.TemporaryDirectory() as _d:
        try:
            test_needle_probes_the_bracket(Path(_d)); print("PASS test_needle_probes_the_bracket"); sys.exit(0)
        except Exception as _e:  # noqa: BLE001
            print(f"FAIL test_needle_probes_the_bracket: {type(_e).__name__}: {_e}"); sys.exit(1)
