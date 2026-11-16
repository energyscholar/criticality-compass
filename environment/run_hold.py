"""Plan 1552: the orchestrator of the hold stage (contract/SCHEMA-1552.md section 10). Owns the apparatus server subprocess and runs the
needle as a SEPARATE PROCESS handed four arguments; the needle's map is written in a fresh temporary directory OUTSIDE the run directory
and moved in only after the server has exited and written the truth. Scoring happens here, after the needle has exited.
Entry: python -m environment.run_hold --env E.toml --at at-apparatus.toml --needle hold-settled.toml --score hold-score.toml
Exit: 0 = score.json written (any outcome kind); 2 = RefusedToStart (refused.json); 1 = infrastructure failure."""
import argparse
import json
import os
import shutil
import signal
import subprocess
import sys
import tempfile
from pathlib import Path

from environment import apparatus_config as AC
from environment import config as C
from environment import hold_score as HS
from environment.run import ROOT, reap, refuse, wait_ready
from environment.run_blind import REFUSED_LINE, _raw, run_id
from navigator import hold as HD
from navigator import reader as R
from needlestream import read as NS
from needlestream import read_hold as RH

OUTPUTS = ("report.jsonl", "map.jsonl", "truth.json", "score.json", "map-truth.json")


def _doc(rid, doc):
    return json.dumps({**doc, "run_id": rid}, sort_keys=True) + "\n"


def main(argv=None):
    ap = argparse.ArgumentParser()
    for k in ("env", "at", "needle", "score"):
        ap.add_argument(f"--{k}", required=True)
    a = ap.parse_args(argv)

    envd = C.load_toml(a.env)
    env = C.parse_env_cfg(envd) if isinstance(envd, dict) else envd
    if isinstance(env, R.Malformed):
        print(f"RefusedToStart field={env.field} parse=B {env.detail}", file=sys.stderr)
        return 2  # no run dir can be named without the env file's run_dir_root
    at_path = Path(a.at)
    vendor = _raw(C.plugin_dir(env.system) / "vendor" / "VENDOR.toml")
    needle_raw, score_raw = _raw(a.needle), _raw(a.score)
    rid, canon = run_id(_raw(at_path), envd, needle_raw, score_raw, _raw(at_path.parent / "tau-v0.toml"), vendor)
    run_dir = Path(os.path.expanduser(env.run_dir_root)) / rid

    srv = AC.load_apparatus_cfgs(a.env, at_path)
    if isinstance(srv, R.Malformed):
        return refuse(run_dir, srv.field, "B", srv.detail)
    bad = HD.refusal_b(needle_raw) if needle_raw else "needle"
    if bad:
        return refuse(run_dir, bad, "B")
    scfg = HS.parse_score(score_raw)
    if isinstance(scfg, R.Malformed):
        return refuse(run_dir, scfg.field, "B", scfg.detail)
    env = srv[0]
    run_dir.mkdir(parents=True, exist_ok=True)
    for name in OUTPUTS:
        (run_dir / name).unlink(missing_ok=True)       # one drop per run directory: nothing of an earlier run is read
    (run_dir / "config.json").write_text(canon)
    signal.signal(signal.SIGTERM, lambda *_: sys.exit(143))  # the finally below reaps the server on the way out
    proc = down = res = None
    with tempfile.TemporaryDirectory(prefix="hold-map-") as tmp:
        tmp_map = Path(tmp) / "map.jsonl"
        try:
            with open(run_dir / "server.log", "wb") as log:
                proc = subprocess.Popen([sys.executable, "-m", "environment.apparatus_server", "--env", str(a.env), "--at", str(at_path),
                                         "--run-dir", str(run_dir)], cwd=ROOT, stdout=subprocess.DEVNULL, stderr=log)
                down = wait_ready(proc, env.port)
                if down is None:
                    with open(run_dir / "report.jsonl", "wb") as out:
                        res = subprocess.run([sys.executable, "-m", "navigator.hold", "--needle", str(a.needle), "--port", str(env.port),
                                              "--drop", rid, "--map", str(tmp_map)], cwd=ROOT, stdout=out, stderr=subprocess.PIPE, text=True)
                reap(proc)  # the server writes truth.json as it exits; reap BEFORE reading or writing outputs
        finally:
            if proc is not None:
                reap(proc)
        if down is not None or res.returncode not in (0, 2):  # the run did not happen: an honest third status
            print(f"InfrastructureFailure {down or res.stderr.strip()}", file=sys.stderr)
            return 1
        if res.returncode == 2:
            (run_dir / "report.jsonl").unlink(missing_ok=True)
            m = REFUSED_LINE.search(res.stderr)
            return refuse(run_dir, m.group(1) if m else "needle_stderr", m.group(2) if m else "B")
        maptext = tmp_map.read_text() if tmp_map.exists() else ""
        if tmp_map.exists():
            shutil.copyfile(tmp_map, run_dir / "map.jsonl")
    return finish(run_dir, rid, (run_dir / "report.jsonl").read_text(), maptext, scfg)


def finish(run_dir, rid, report, maptext, scfg):
    st, mp = RH.read(report), RH.read_map(maptext)
    if isinstance(st, NS.Unreadable) or st.outcome is NS.PENDING:
        return refuse(run_dir, "needle_stdout", "B")
    if isinstance(mp, NS.Unreadable) or len(mp.drops) != 1 or RH.check(st, mp.drops[0]) is not None:
        return refuse(run_dir, "needle_map", "B")
    rows = json.loads((run_dir / "truth.json").read_text())["rows"]
    try:
        score, over = HS.score(st, rows, scfg), HS.overlay(mp.drops[0], rows, scfg.offset_K)
    except KeyError:
        return refuse(run_dir, "truth_join", "B")
    (run_dir / "score.json").write_text(_doc(rid, score))
    (run_dir / "map-truth.json").write_text(_doc(rid, over))
    return 0


if __name__ == "__main__":
    sys.exit(main())
