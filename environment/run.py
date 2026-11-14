"""Plan 1511: the orchestrator. Owns the server subprocess (and its port), calls the needle in-process, then writes the run
artifacts (§11.8). The needle writes nothing. The server is reaped in `finally`, on every path including failure.
Entry: python -m environment.run --env environment.toml --needle needle.toml [--at at.toml]
Exit: 0 = verdict.json written (any REFUSE included); 2 = RefusedToStart (refused.json); 1 = infrastructure failure (the server
never bound / exited early: the run did not happen)."""
import argparse
import hashlib
import json
import os
import signal
import socket
import subprocess
import sys
import time
from pathlib import Path

from environment import config as C
from environment import score as S
from navigator import needle as N
from navigator import reader as R

ROOT = C.ROOT
READY_WAIT = 120  # orchestrator-side (not the needle): poll-connect until the server's port accepts


def run_id(at, env, needle, tau, vendor):
    """sha256 of the sorted-key canonical JSON of the five configs, minus host/runtime fields (§11.8, R4-2)."""
    env = {k: v for k, v in env.items() if k not in ("run_dir_root", "port")}
    needle = {k: v for k, v in needle.items() if k not in ("host", "port")}
    canon = json.dumps({"at": at, "environment": env, "needle": needle, "tau_v0": tau, "vendor": vendor},
                       sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canon.encode()).hexdigest()[:16], canon


def _raw(path):
    d = C.load_toml(path)
    return {} if isinstance(d, R.Malformed) else d


def refuse(run_dir, field, parse, detail=""):
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "refused.json").write_text(json.dumps({"kind": "RefusedToStart", "field": field, "parse": parse}, sort_keys=True))
    print(f"RefusedToStart field={field} parse={parse} {detail}".rstrip(), file=sys.stderr)
    return 2


def wait_ready(proc, port):
    """-> None when the port accepts, else a str naming why the run cannot happen (infrastructure failure, exit 1)."""
    t0 = time.time()
    while True:
        with socket.socket() as s:
            if s.connect_ex(("127.0.0.1", port)) == 0:
                return None
        if proc.poll() is not None:
            return f"server exited early (code {proc.returncode})"
        if time.time() - t0 > READY_WAIT:
            return "server never bound its port"
        time.sleep(0.05)


def reap(proc):
    if proc.poll() is None:
        proc.send_signal(signal.SIGTERM)
        try:
            proc.wait(15)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait()


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--env", required=True)
    ap.add_argument("--needle", required=True)
    ap.add_argument("--at", default=None)
    a = ap.parse_args(argv)

    envd = C.load_toml(a.env)
    env = C.parse_env_cfg(envd) if isinstance(envd, dict) else envd
    if isinstance(env, R.Malformed):
        print(f"RefusedToStart field={env.field} parse=B {env.detail}", file=sys.stderr)
        return 2  # no run dir can be named without environment.toml's run_dir_root
    at_path = Path(a.at) if a.at else C.plugin_dir(env.system) / "at.toml"
    vendor = _raw(C.plugin_dir(env.system) / "vendor" / "VENDOR.toml")
    rid, canon = run_id(_raw(at_path), envd, _raw(a.needle), _raw(at_path.parent / "tau-v0.toml"), vendor)
    run_dir = Path(os.path.expanduser(env.run_dir_root)) / rid

    srv = C.load_server_cfgs(a.env, at_path)
    if isinstance(srv, R.Malformed):
        return refuse(run_dir, srv.field, "B", srv.detail)
    ncfg = N.load_needle_cfg(a.needle)
    if isinstance(ncfg, R.Malformed):
        return refuse(run_dir, ncfg.field, "B", ncfg.detail)
    env, at, tau = srv
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "config.json").write_text(canon)
    signal.signal(signal.SIGTERM, lambda *_: sys.exit(143))  # the finally below reaps the server on the way out
    proc = down = result = None
    try:
        with open(run_dir / "server.log", "wb") as log:
            proc = subprocess.Popen([sys.executable, "-m", "environment.server", "--env", str(a.env), "--at", str(at_path),
                                     "--run-dir", str(run_dir)], cwd=ROOT, stdout=subprocess.DEVNULL, stderr=log)
            down = wait_ready(proc, env.port)
            result = N.run(a.needle) if down is None else None
            reap(proc)  # the server writes perf.json as it exits; reap BEFORE reading/writing outputs
    finally:
        if proc is not None:
            reap(proc)
    if down is not None or isinstance(result, N.Unreachable):  # the run did not happen: exit 1, an honest third status (R4-5)
        print(f"InfrastructureFailure {down or result}", file=sys.stderr)
        return 1
    if isinstance(result, N.RefusedToStart):
        return refuse(run_dir, result.field, result.parse)
    return write_verdict(run_dir, rid, at, ncfg, result)


def write_verdict(run_dir, rid, at, ncfg, v):
    """truth = present iff |K - K_c| <= w, with K_c, w read from the server's <run_dir>/edge.json — on EVERY path, normal and
    REFUSE(floor) alike (R4-1). The orchestrator imports no plugin internal and names no system."""
    edge = json.loads((run_dir / "edge.json").read_text())
    K_c, w = edge["K_c"], edge["w"]
    K = K_c + ncfg.u
    truth = S.Truth.present if abs(K - K_c) <= w else S.Truth.absent
    cell = S.score(truth, S.Verdict(v.kind))
    doc = {"plan": "1511", "run_id": rid, "env_seed": at.seed, "declaration": v.declaration.raw, "truth": truth.value,
           "verdict": {"kind": v.kind, "reason": v.reason}, "cell": cell.name, "rounds": v.rounds}
    (run_dir / "verdict.json").write_text(json.dumps(doc, sort_keys=True) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
