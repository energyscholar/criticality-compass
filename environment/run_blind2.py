"""Plan 1533: the orchestrator of report schema 2. As environment.run_blind (plan 1525), which it imports from and does not edit:
it owns the blind server subprocess and runs the needle `navigator.recover2` as a SEPARATE PROCESS handed a port and nothing
else. The needle's stdout goes straight into <run_dir>/report.jsonl, line by line as the needle writes it. After the needle
exits, the stream is read with needlestream.read and scored against the truth in <run_dir>/edge.json. Three files are written:
report.jsonl (the stream), score.json (the score), verdict.json (the schema-1 shape: the fold plus the nine score keys), so the
viewers of plans 1529 and 1531 read a Located or REFUSE run unchanged. The plan stamp is a declared field of the score file.
Entry: python -m environment.run_blind2 --env E.toml --at at-blind.toml --needle recover2.toml --score score-1533.toml
Exit: 0 = verdict.json written (any outcome kind); 2 = RefusedToStart (refused.json); 1 = infrastructure failure."""
import argparse
import json
import os
import signal
import subprocess
import sys
from pathlib import Path

from environment import blind_config as BC
from environment import config as C
from environment.run import ROOT, reap, refuse, wait_ready
from environment.run_blind import REFUSED_LINE, _raw, run_id
from navigator import reader as R
from navigator import recover2 as RC2
from navigator import steer as ST
from needlestream import read as NS

SIDES = ("below-range", "inside", "above-range")
SCORE_KEYS = ("a", "w_max", "plan")


def truth_side(K_c, searched):
    """where the true crossing lies against the two ends of the searched range, ends included in `inside`."""
    return SIDES[(K_c >= searched[0]) + (K_c > searched[1])]


def _located(bracket, side, K_c, sc):
    contains, width = bracket[0] - sc.a <= K_c <= bracket[1] + sc.a, bracket[1] - bracket[0]
    narrow_enough = width <= sc.w_max
    return contains, width, narrow_enough, "HIT" if contains and narrow_enough else "MISS"


def _no_bracket(cells):
    """a kind with no bracket: a total cell per side of the truth, and no contains, width or narrow_enough."""
    return lambda bracket, side, K_c, sc: (None, None, None, cells[side])


_PAST = ("LEAN-TRUE", "LEAN-FALSE")
SCORE = {
    ST.OUTCOME_KINDS[0]: _located,
    ST.OUTCOME_KINDS[1]: _no_bracket(dict(zip(SIDES, (_PAST[0], _PAST[1], _PAST[1])))),
    ST.OUTCOME_KINDS[2]: _no_bracket(dict(zip(SIDES, (_PAST[1], _PAST[1], _PAST[0])))),
    ST.OUTCOME_KINDS[3]: _no_bracket(dict.fromkeys(SIDES, "NO-CALL")),
    ST.OUTCOME_KINDS[4]: _no_bracket(dict.fromkeys(SIDES, "REFUSED")),
}


def score2(kind, bracket, side, K_c, sc):
    """-> (contains, width, narrow_enough, cell). Total over the five outcome kinds; KeyError for any other."""
    return SCORE[kind](bracket, side, K_c, sc)


def parse_score2(d):
    """a parsed toml table -> (ScoreConfig, plan) | Malformed. Strict: exactly a, w_max, plan."""
    if not isinstance(d, dict):
        return R.Malformed("score", "table required")
    extra = sorted(set(d) - set(SCORE_KEYS))
    if extra:
        return R.Malformed(extra[0], "unknown key")
    sc, plan = BC.parse_score_cfg({k: v for k, v in d.items() if k != "plan"}), R._str(d, "plan")
    bad = R._first_bad([sc, plan])
    return bad if bad else (sc, plan)


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
    ncfg = RC2.load_cfg(a.needle)
    if isinstance(ncfg, R.Malformed):
        return refuse(run_dir, ncfg.field, "B", ncfg.detail)
    sd = C.load_toml(a.score)
    scored = sd if isinstance(sd, R.Malformed) else parse_score2(sd)
    if isinstance(scored, R.Malformed):
        return refuse(run_dir, scored.field, "B", scored.detail)
    scfg, plan = scored
    env = srv[0]
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "config.json").write_text(canon)
    report = run_dir / "report.jsonl"
    signal.signal(signal.SIGTERM, lambda *_: sys.exit(143))  # the finally below reaps the server on the way out
    proc = down = res = None
    try:
        with open(run_dir / "server.log", "wb") as log:
            proc = subprocess.Popen([sys.executable, "-m", "environment.blind_server", "--env", str(a.env), "--at", str(at_path),
                                     "--run-dir", str(run_dir)], cwd=ROOT, stdout=subprocess.DEVNULL, stderr=log)
            down = wait_ready(proc, env.port)
            if down is None:
                with open(report, "wb") as out:  # the needle writes the stream straight into the file, line by line
                    res = subprocess.run([sys.executable, "-m", "navigator.recover2", "--needle", str(a.needle), "--port",
                                          str(env.port)], cwd=ROOT, stdout=out, stderr=subprocess.PIPE, text=True)
            reap(proc)  # the server writes perf.json as it exits; reap BEFORE reading or writing outputs
    finally:
        if proc is not None:
            reap(proc)
    if down is not None or res.returncode not in (0, 2):  # the run did not happen: an honest third status
        print(f"InfrastructureFailure {down or res.stderr.strip()}", file=sys.stderr)
        return 1
    if res.returncode == 2:
        report.unlink(missing_ok=True)
        m = REFUSED_LINE.search(res.stderr)
        return refuse(run_dir, m.group(1) if m else "needle_stderr", m.group(2) if m else "B")
    stream = NS.read(report.read_text())
    if not (isinstance(stream, NS.Stream) and stream.schema == 2 and stream.outcome is not NS.PENDING):
        report.unlink(missing_ok=True)
        return refuse(run_dir, "needle_stdout", "B")
    return write_scores(run_dir, rid, stream, scfg, plan)


def write_scores(run_dir, rid, stream, sc, plan):
    K_c = json.loads((run_dir / "edge.json").read_text())["K_c"]
    searched = stream.start.settings["bracket"]
    side = truth_side(K_c, searched)
    o = stream.outcome
    contains, width, narrow_enough, cell = score2(o.kind, o.bracket, side, K_c, sc)
    nine = {"truth_K_c": K_c, "a": sc.a, "w_max": sc.w_max, "contains": contains, "width": width,
            "narrow_enough": narrow_enough, "cell": cell, "run_id": rid, "plan": plan}
    (run_dir / "score.json").write_text(json.dumps({**nine, "searched": searched, "truth_side": side}, sort_keys=True) + "\n")
    (run_dir / "verdict.json").write_text(json.dumps({**NS.fold_v1(stream), **nine}, sort_keys=True) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
