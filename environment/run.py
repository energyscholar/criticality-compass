"""Plan 1511: the orchestrator. Owns the server subprocess (and its port), calls the needle in-process, then writes the run
artifacts (§11.8). The needle writes nothing. The server is reaped in `finally`, on every path including failure.
Entry: python -m environment.run --env environment.toml --needle needle.toml [--at at.toml]
Exit: 0 = verdict.json written (any REFUSE included); 2 = RefusedToStart (refused.json)."""
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
from navigator import needle as N
from navigator import reader as R

ROOT = C.ROOT
READY_WAIT = 120  # orchestrator-side (not the needle): poll-connect until the server's port accepts


def run_id(at, env, needle, tau, vendor):
    """sha256 of the sorted-key canonical JSON of the five configs, minus host/runtime fields (§11.8)."""
    env = {k: v for k, v in env.items() if k not in ("run_dir_root", "port")}
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
    t0 = time.time()
    while True:
        with socket.socket() as s:
            if s.connect_ex(("127.0.0.1", port)) == 0:
                return
        if proc.poll() is not None:
            raise RuntimeError(f"server exited early (code {proc.returncode})")
        if time.time() - t0 > READY_WAIT:
            raise RuntimeError("server never bound its port")
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
    raise NotImplementedError("T2: spawn server, run needle, score, write verdict.json")


if __name__ == "__main__":
    sys.exit(main())
