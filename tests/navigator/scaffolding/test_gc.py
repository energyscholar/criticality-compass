"""Plan 1511 §4: structural garbage collection. start -> run -> stop leaves no live process, no bound port, no stray dir
(beyond the intended run dir) — at L=27, then 81, then 243. The larger-L checks test TEARDOWN, not physics (burn=1,N=1,n=1)."""
import os
import signal
import subprocess
import sys
import time

import pytest

from conftest import ROOT, free_port, make_configs, port_bound


def procs_with(token):
    """pids (other than ours) whose command line contains token — a /proc scan, not pgrep (pgrep self-matches)."""
    me, out = os.getpid(), []
    for d in os.listdir("/proc"):
        if d.isdigit() and int(d) != me:
            try:
                cmd = open(f"/proc/{d}/cmdline", "rb").read().replace(b"\0", b" ").decode(errors="replace")
            except OSError:
                continue
            if token in cmd:
                out.append(int(d))
    return out


def trivial(tmp_path, L_blocks):
    # k=1, tau=1 => floor 1, so n=1 passes it and a real round (set, step, sense) runs
    return make_configs(tmp_path, at=dict(L_blocks=L_blocks, burn=1, k=1), tau=dict(value=1), needle=dict(N=1, n=1, u=0.0))


def run_orch(cfg):
    return subprocess.run([sys.executable, "-m", "environment.run", "--env", str(cfg["env"]), "--needle", str(cfg["needle"]),
                           "--at", str(cfg["at"])], cwd=ROOT, capture_output=True, text=True, timeout=120)


@pytest.mark.parametrize("L_blocks", [9, 27, 81])  # L = 27, 81, 243 — small first
def test_start_run_stop_leaves_nothing_behind(tmp_path, L_blocks):
    cfg = trivial(tmp_path, L_blocks)
    p = run_orch(cfg)
    assert p.returncode == 0, p.stderr
    token = str(cfg["tmp"])  # every spawned process names this unique tmp dir in its arguments
    assert procs_with(token) == [], "orphaned process"
    assert not port_bound(cfg["port"]), "bound port left behind"
    kids = sorted(os.listdir(cfg["out"]))
    assert len(kids) == 1 and len(kids[0]) == 16, kids  # exactly the intended run dir
    assert (cfg["out"] / kids[0] / "verdict.json").exists()
    # nothing else was written under the tmp tree except what make_configs put there and the one run dir
    assert sorted(os.listdir(cfg["tmp"])) == ["environment.toml", "needle.toml", "out", "plugin"]


def test_refused_run_also_leaves_nothing_behind(tmp_path):
    cfg = make_configs(tmp_path, needle=dict(u=-1.0))
    assert run_orch(cfg).returncode == 2
    assert procs_with(str(cfg["tmp"])) == [] and not port_bound(cfg["port"])
    assert len(os.listdir(cfg["out"])) == 1


def test_orchestrator_killed_by_SIGTERM_mid_run_reaps_its_server(tmp_path):
    cfg = make_configs(tmp_path, at=dict(L_blocks=27, burn=1, k=1), tau=dict(value=1), needle=dict(N=50, n=200, u=0.0))
    p = subprocess.Popen([sys.executable, "-m", "environment.run", "--env", str(cfg["env"]), "--needle", str(cfg["needle"]),
                          "--at", str(cfg["at"])], cwd=ROOT, stderr=subprocess.DEVNULL)
    try:
        t0 = time.time()
        while not port_bound(cfg["port"]):
            assert p.poll() is None and time.time() - t0 < 120
            time.sleep(0.05)
        p.send_signal(signal.SIGTERM)
        p.wait(30)
    finally:
        if p.poll() is None:
            p.kill()
            p.wait()
    deadline = time.time() + 20
    while (procs_with(str(cfg["tmp"])) or port_bound(cfg["port"])) and time.time() < deadline:
        time.sleep(0.1)
    leaked = procs_with(str(cfg["tmp"]))
    for pid in leaked:  # the fixture reaps even on failure: a leaked server must not outlive the test
        os.kill(pid, signal.SIGKILL)
    assert leaked == [] and not port_bound(cfg["port"])


def test_set_accumulates_no_state_and_snapshot_is_bounded():
    """the live sim's snapshot state is bounded by construction: many set/step calls change no array shape or attribute set."""
    from environment import config as C
    from navigator import reader as R
    plugin = C.load_plugin("at")
    st = plugin.init(R.parse_at_cfg(dict(L_blocks=3, L4=0.14, burn=2, seed=1, k=1, nlev=1, knobs_K=[0.2, 0.5], w=0.02,
                                         index_unit="sweep", index_kind="sample_counter")))
    shape = (st.s.shape, st.t.shape, st.s.nbytes + st.t.nbytes)
    attrs = sorted(vars(st))
    for i in range(300):
        plugin.set(st, 0.3 + 0.0001 * i)
        plugin.step(st, 1)
    assert (st.s.shape, st.t.shape, st.s.nbytes + st.t.nbytes) == shape and sorted(vars(st)) == attrs and st.index == 300
