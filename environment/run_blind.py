"""Plan 1525: the orchestrator of the blind stage. Owns the blind server subprocess (and its port) and runs the needle as a
SEPARATE PROCESS that is handed a port and nothing else: no run dir, no environment variable naming one. Scoring happens here,
after the needle has exited, against the truth in <run_dir>/edge.json. The server is reaped in `finally`, on every path.
Entry: python -m environment.run_blind --env environment-blind.toml --at at-blind.toml --needle recover.toml --score score-1525.toml
Exit: 0 = verdict.json written (any REFUSE included); 2 = RefusedToStart (refused.json); 1 = infrastructure failure."""
import argparse
import hashlib
import json
import os
import re
import signal
import subprocess
import sys
from pathlib import Path

from environment import blind_config as BC
from environment import config as C
from environment.run import ROOT, reap, refuse, wait_ready
from navigator import reader as R
from navigator import recover as RC

REFUSED_LINE = re.compile(r"RefusedToStart field=(\S+) parse=([AB])")


def run_id(at, env, needle, score, tau, vendor):
    """Stage-1's recipe (sorted keys, compact separators, sha256, first 16 hex) over the six raw configs plus the score."""
    env = {k: v for k, v in env.items() if k not in ("run_dir_root", "port")}
    needle = {k: v for k, v in needle.items() if k not in ("host", "port")}
    canon = json.dumps({"at": at, "environment": env, "needle": needle, "score": score, "tau_v0": tau, "vendor": vendor},
                       sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canon.encode()).hexdigest()[:16], canon


def _raw(path):
    d = C.load_toml(path)
    return {} if isinstance(d, R.Malformed) else d


def valid_report(rep):
    """a needle's stdout value is a report iff it is an object of a declared kind with a numeric bracket where Located."""
    if not isinstance(rep, dict) or rep.get("kind") not in ("Located", "REFUSE"):
        return False
    if rep["kind"] == "REFUSE":
        return True
    br = rep.get("bracket")
    return isinstance(br, list) and len(br) == 2 and all(isinstance(x, (int, float)) and not isinstance(x, bool) for x in br)


def score_cell(rep, K_c, sc):
    """the total cell map: HIT / MISS for a Located report, REFUSED for a REFUSE. -> (contains, width, narrow_enough, cell)."""
    if rep["kind"] == "REFUSE":
        return None, None, None, "REFUSED"
    lo, hi = rep["bracket"]
    contains, width = lo - sc.a <= K_c <= hi + sc.a, hi - lo
    narrow_enough = width <= sc.w_max
    return contains, width, narrow_enough, "HIT" if contains and narrow_enough else "MISS"


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--env", required=True)
    ap.add_argument("--at", required=True)
    ap.add_argument("--needle", required=True)
    ap.add_argument("--score", required=True)
    a = ap.parse_args(argv)

    envd = C.load_toml(a.env)
    env = C.parse_env_cfg(envd) if isinstance(envd, dict) else envd
    if isinstance(env, R.Malformed):
        print(f"RefusedToStart field={env.field} parse=B {env.detail}", file=sys.stderr)
        return 2  # no run dir can be named without the env file's run_dir_root
    at_path = Path(a.at)
    vendor = _raw(C.plugin_dir(env.system) / "vendor" / "VENDOR.toml")
    rid, canon = run_id(_raw(at_path), envd, _raw(a.needle), _raw(a.score), _raw(at_path.parent / "tau-v0.toml"), vendor)
    run_dir = Path(os.path.expanduser(env.run_dir_root)) / rid

    srv = BC.load_blind_cfgs(a.env, at_path)
    if isinstance(srv, R.Malformed):
        return refuse(run_dir, srv.field, "B", srv.detail)
    ncfg = RC.load_cfg(a.needle)
    if isinstance(ncfg, R.Malformed):
        return refuse(run_dir, ncfg.field, "B", ncfg.detail)
    scfg = BC.parse_score_cfg(C.load_toml(a.score))
    if isinstance(scfg, R.Malformed):
        return refuse(run_dir, scfg.field, "B", scfg.detail)
    env = srv[0]
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "config.json").write_text(canon)
    signal.signal(signal.SIGTERM, lambda *_: sys.exit(143))  # the finally below reaps the server on the way out
    proc = down = res = None
    try:
        with open(run_dir / "server.log", "wb") as log:
            proc = subprocess.Popen([sys.executable, "-m", "environment.blind_server", "--env", str(a.env), "--at", str(at_path),
                                     "--run-dir", str(run_dir)], cwd=ROOT, stdout=subprocess.DEVNULL, stderr=log)
            down = wait_ready(proc, env.port)
            if down is None:
                res = subprocess.run([sys.executable, "-m", "navigator.recover", "--needle", str(a.needle), "--port", str(env.port)],
                                     cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            reap(proc)  # the server writes perf.json as it exits; reap BEFORE reading or writing outputs
    finally:
        if proc is not None:
            reap(proc)
    if down is not None or res.returncode not in (0, 2):  # the run did not happen: an honest third status
        print(f"InfrastructureFailure {down or res.stderr.strip()}", file=sys.stderr)
        return 1
    if res.returncode == 2:
        m = REFUSED_LINE.search(res.stderr)
        return refuse(run_dir, m.group(1) if m else "needle_stderr", m.group(2) if m else "B")
    try:
        rep = json.loads(res.stdout)
    except ValueError:
        rep = None
    if not valid_report(rep):
        return refuse(run_dir, "needle_stdout", "B")
    return write_verdict(run_dir, rid, rep, scfg)


def write_verdict(run_dir, rid, rep, sc):
    K_c = json.loads((run_dir / "edge.json").read_text())["K_c"]
    contains, width, narrow_enough, cell = score_cell(rep, K_c, sc)
    doc = {**rep, "truth_K_c": K_c, "a": sc.a, "w_max": sc.w_max, "contains": contains, "width": width,
           "narrow_enough": narrow_enough, "cell": cell, "run_id": rid, "plan": "1525"}
    (run_dir / "verdict.json").write_text(json.dumps(doc, sort_keys=True) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
