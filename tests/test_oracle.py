"""test_oracle - plan 1282 P3: the total Oracle sum type and `cc navigate --oracle declared`. Data-free (0 core-h): the exact 2-D Ising field is a walk-identity check.
Breakers, each seen RED: B1 (ZERO-pinned interior; RED on navigate.MOVE which stops, GREEN on MOVE_LIVE which is UNRESOLVED), B2 (inverted field; RED on a lo/hi-swapped table),
B3 (literal-uniform ZERO; REFUSE). Also E-LOG (append-before-use record), dispatch totality, MOVE_LIVE totality, cc/navigate.py byte-unchanged against main 8d0551f."""
import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
from lib import check  # noqa: E402
sys.path[:0] = [str(ROOT / "cc")]
import navigate  # noqa: E402
import oracle  # noqa: E402
from sign import Sign  # noqa: E402

S = Sign
ST = oracle.StartDecl(0.35, 0.60, 0.01, oracle.KC)
N = ST.n()


def walk_of(field, table):
    return navigate.walk(lambda j: oracle.reading(field, ST.k(j), table), N)


def b1(K):   # honest ends, ZERO at every interior probe
    return {K < 0.36: S.SIG_MINUS, K > 0.59: S.SIG_PLUS}.get(True, S.ZERO)


with tempfile.TemporaryDirectory() as t:
    for lo, hi in ((0.35, 0.60), (0.40, 0.48)):
        lines, status = oracle.cli(Path(t), ["declared", "--start", str(lo), str(hi), "--dk", "0.01"])
        check(f"M-PoC start [{lo}, {hi}]: BRACKET [0.44, 0.45], status 0, lines returned not printed", status == 0 and lines[-1] == "navigate declared: BRACKET [0.44, 0.45]", lines[-1])
    log = [json.loads(ln) for ln in (Path(t) / "results" / "navigate" / "declared.access.jsonl").read_text().splitlines()]
    want = {"path": "declared:exact", "size": 0, "route": "declared"}
    check("E-LOG: one record per probe, route declared, fields as specified", len(log) > 0 and all(r[k] == v for r in log for k, v in want.items()) and all(r["partition"].startswith("declared:") and r["sha256"] and "pid" in r and "argv" in r and "git_head" in r for r in log), str(log[:1]))
    lines, status = oracle.cli(Path(t), ["declared", "--start", "0.35"])
    check("usage refusal is a value (status 2), not an exception", status == 2 and lines[0].startswith("REFUSED"), str(lines))

w = walk_of(oracle.EXACT, oracle.MOVE_LIVE)
check("exact field walk: BRACKET one node wide, straddling K_c", w.outcome == "BRACKET" and w.hi - w.lo == 1 and ST.k(w.lo) < oracle.KC < ST.k(w.hi), str((w.outcome, w.lo, w.hi)))

w1 = walk_of(b1, oracle.MOVE_LIVE)
w1_red = walk_of(b1, navigate.MOVE)
check("B1 GREEN: ZERO-pinned interior ends UNRESOLVED under MOVE_LIVE", w1.outcome == "UNRESOLVED", w1.outcome)
check("B1 seen RED: the same reader on navigate.MOVE stops (a false location)", w1_red.outcome == "STOP", w1_red.outcome)

inverted = lambda K: {True: S.SIG_PLUS, False: S.SIG_MINUS}[K < oracle.KC]  # noqa: E731
swap = {k: {"lo": "hi", "hi": "lo"}.get(v, v) for k, v in oracle.MOVE_LIVE.items()}
check("B2: inverted field REFUSEs under MOVE_LIVE", walk_of(inverted, oracle.MOVE_LIVE).outcome == "REFUSE")
check("B2 seen RED: the lo/hi-swapped table bisects to a false BRACKET", walk_of(inverted, swap).outcome == "BRACKET", walk_of(inverted, swap).outcome)
check("B3: literal-uniform ZERO REFUSEs", walk_of(lambda K: S.ZERO, oracle.MOVE_LIVE).outcome == "REFUSE")

check("MOVE_LIVE total over Sign + {None}", set(oracle.MOVE_LIVE) == set(Sign) | {None})
check("MOVE_LIVE maps MID to unresolved where navigate.MOVE stops", oracle.MOVE_LIVE[S.ZERO] == "unresolved" and navigate.MOVE[S.ZERO] == "stop")
ne = oracle.reading(lambda K: None, 0.4, oracle.MOVE_LIVE)
check("not established -> the _refuse-shaped Reading, move refuse", ne == navigate.Reading("REFUSE", None, None, None, 0, None, navigate.NE, "refuse"), str(ne))
live = oracle.LiveDetector(None, None, None, None)
check("Oracle dispatch total: both constructors read, LiveDetector is a total REFUSE stub", set(oracle.READERS) == {oracle.Declared, oracle.LiveDetector} and oracle.read_of(live)(3).move == "refuse")
r = subprocess.run(["git", "diff", "8d0551f", "--", "cc/navigate.py"], cwd=ROOT, capture_output=True, text=True)
check("cc/navigate.py byte-unchanged against main 8d0551f", r.returncode == 0 and r.stdout == "", r.stderr or r.stdout[:200])
sys.exit(int(bool(__import__("lib").bad)))
