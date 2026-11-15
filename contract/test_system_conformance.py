"""Plan 1518 — TRACK-S acceptance (the System face). Launches the REAL environment server and drives it
over a raw socket. Stage-2 adds ONE op: `probe{Ks:[...],n}` → `obs{E2:[m floats],index}` — the Stage-1
set+step+sense machinery looped over m fixed points, in one wire call (contract/SCHEMA.md). Default needle
= the 2-point bracket. FROZEN: the Generator makes this green by building `probe`; it does not edit this file.

RED until `probe` exists: Stage-1 treats an unknown op as `nev`, so the batched replies come back `nev`
instead of a float-list `obs`.

Run from the repo root:  python -m pytest contract/test_system_conformance.py -x
"""
import json
import socket
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
KNOBS = (0.30, 0.60)
N = 4                 # small sweep count — structural test, keep it fast
K_LO, K_HI = 0.40, 0.50   # a 2-point bracket, both inside KNOBS
K_MID = 0.45
K_OUT = 0.70          # outside KNOBS (> hi) ⇒ set must reject ⇒ nev


def _free_port():
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    p = s.getsockname()[1]
    s.close()
    return p


def _write_cfgs(tmp, port):
    """environment.toml + at.toml (+ tau) for a TINY AT lattice. Real Stage-1 fields (no burn_mode/shape)."""
    at_dir = tmp / "plugins_at"
    at_dir.mkdir(parents=True, exist_ok=True)
    env_path = tmp / "environment.toml"
    at_path = at_dir / "at.toml"
    env_path.write_text(f'system = "at"\nport = {port}\nrun_dir_root = "{tmp / "run"}"\n')
    at_path.write_text(
        "L_blocks = 1\nL4 = 1.0\nburn = 4\nseed = 1\nk = 1\nnlev = 2\n"
        f"knobs_K = [{KNOBS[0]}, {KNOBS[1]}]\nw = 0.01\n"
        'index_unit = "sweep"\nindex_kind = "sweep"\n'
    )
    (at_dir / "tau-v0.toml").write_text("value = 1.0\n")
    return env_path, at_path


def _launch(env_path, at_path, run_dir, port):
    proc = subprocess.Popen(
        [sys.executable, "-m", "environment.server", "--env", str(env_path),
         "--at", str(at_path), "--run-dir", str(run_dir)],
        cwd=str(ROOT), stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
    )
    for _ in range(600):  # up to ~30 s; port binds only after init/burn, so a connect = ready
        if proc.poll() is not None:
            out, err = proc.communicate()
            raise AssertionError(f"server exited early rc={proc.returncode}\nstdout={out}\nstderr={err}")
        try:
            socket.create_connection(("127.0.0.1", port), timeout=0.2).close()
            return proc
        except OSError:
            time.sleep(0.05)
    proc.kill()
    raise AssertionError("server never bound the port")


class _Conn:
    def __init__(self, port):
        self.s = socket.create_connection(("127.0.0.1", port), timeout=5)
        self.rf = self.s.makefile("r", encoding="utf-8", newline="\n")

    def ask(self, msg):
        self.s.sendall((json.dumps(msg) + "\n").encode())
        line = self.rf.readline()
        assert line, "server closed unexpectedly"
        return json.loads(line)

    def close(self):
        try:
            self.s.close()
        except OSError:
            pass


def _float_list(v, n):
    assert isinstance(v, list) and len(v) == n, f"expected {n}-float list, got {v!r}"
    for x in v:
        assert isinstance(x, float) and not isinstance(x, bool), f"non-float element: {x!r}"


def test_probe_batches_the_bracket(tmp_path):
    """One `probe` call carries both bracket points and returns both E2 values; index advances by m*n."""
    port = _free_port()
    env_path, at_path = _write_cfgs(tmp_path, port)
    proc = _launch(env_path, at_path, tmp_path / "run", port)
    try:
        c = _Conn(port)
        d = c.ask({"op": "declare"})
        assert d["op"] == "declared", d
        assert list(d["knobs_K"]) == list(KNOBS)
        r = c.ask({"op": "probe", "Ks": [K_LO, K_HI], "n": N})   # ONE wire call, two points
        assert r["op"] == "obs", r
        _float_list(r["E2"], 2)
        assert r["index"] == 2 * N, r                            # each of the 2 points stepped n
        c.close()
    finally:
        proc.terminate()
        proc.wait(timeout=5)


def test_probe_m1_equals_stage1(tmp_path):
    """m=1 ≡ Stage-1: probe{Ks:[K],n}.E2[0] equals set+step+sense from the same burned state (same seed)."""
    # server A: Stage-1 path
    pA = _free_port(); envA, atA = _write_cfgs(tmp_path / "A", pA)
    procA = _launch(envA, atA, tmp_path / "A" / "run", pA)
    # server B: batched path (same seed=1 ⇒ identical burn)
    pB = _free_port(); envB, atB = _write_cfgs(tmp_path / "B", pB)
    procB = _launch(envB, atB, tmp_path / "B" / "run", pB)
    try:
        a = _Conn(pA); a.ask({"op": "declare"})
        assert a.ask({"op": "set", "K": K_MID})["op"] == "ok"
        assert a.ask({"op": "step", "n": N})["op"] == "ok"
        e_single = a.ask({"op": "sense"})["E2"]
        a.close()

        b = _Conn(pB); b.ask({"op": "declare"})
        rb = b.ask({"op": "probe", "Ks": [K_MID], "n": N})
        assert rb["op"] == "obs", rb
        _float_list(rb["E2"], 1)
        assert rb["E2"][0] == e_single, (rb["E2"][0], e_single)   # the batched single point == Stage-1
        b.close()
    finally:
        for p in (procA, procB):
            p.terminate(); p.wait(timeout=5)


def test_probe_out_of_bounds_is_nev_no_clamp(tmp_path):
    """A probe with any out-of-bounds K is nev, index unchanged, nothing stepped — no clamp."""
    port = _free_port()
    env_path, at_path = _write_cfgs(tmp_path, port)
    proc = _launch(env_path, at_path, tmp_path / "run", port)
    try:
        c = _Conn(port)
        c.ask({"op": "declare"})
        r1 = c.ask({"op": "probe", "Ks": [K_LO, K_HI], "n": N})  # valid: proves we're in probe mode
        assert r1["op"] == "obs" and r1["index"] == 2 * N, r1    # RED on Stage-1 (nev, index 0)
        r2 = c.ask({"op": "probe", "Ks": [K_LO, K_OUT], "n": N})  # one point out of bounds
        assert r2["op"] == "nev", r2
        assert r2["index"] == 2 * N, r2                          # unchanged: no point stepped, no clamp
        c.close()
    finally:
        proc.terminate()
        proc.wait(timeout=5)


if __name__ == "__main__":
    # The compass gate runs this as `python <file>`, so the assertions must run HERE too — a pytest file
    # with no runner would exit 0 without evaluating anything (a vacuous pass). This runner makes RED red
    # under the gate, so the probe op must be GREEN before the commit lands. (Also runnable via pytest.)
    import tempfile
    _tests = [test_probe_batches_the_bracket, test_probe_m1_equals_stage1, test_probe_out_of_bounds_is_nev_no_clamp]
    _fail = 0
    for _t in _tests:
        with tempfile.TemporaryDirectory() as _d:
            try:
                _t(Path(_d)); print(f"PASS {_t.__name__}")
            except Exception as _e:  # noqa: BLE001 — a conformance failure is a value, reported then counted
                _fail += 1; print(f"FAIL {_t.__name__}: {type(_e).__name__}: {_e}")
    print(f"{len(_tests) - _fail}/{len(_tests)} passed")
    sys.exit(1 if _fail else 0)
