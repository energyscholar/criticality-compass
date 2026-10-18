"""test_navigate - plan 1114: `cc navigate` (stored-map mode, UNTESTED) - one golden transcript, its T23 access log, the typed refusal, and two seen-reds:
(a) the golden map with one node removed must change the transcript (never pass silently); (b) nav.py's UNRES->MID move, put back in place of the
shipped move table, turns an UNRESOLVED walk into a STOP (the defect this verb must not ship is visible to this test).
Data-dependent: reads the b7 chain files under CC_DATA_ROOT (cc.toml [check] needs_data). CC_REGOLDEN=1 rewrites the golden (REGOLDENED line)."""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import tomllib
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path[:0] = [str(ROOT / "cc")]
import navigate  # noqa: E402

MAP = "b7-at-line-ch"
GOLD = ROOT / "tests" / "navigate" / f"{MAP}.txt"
bad = []


def check(name, ok, why=""):
    print(("ok   " if ok else "FAIL ") + name + ("" if ok else f": {why}"))
    if not ok:
        bad.append(name)


def cc(root, *args):
    r = subprocess.run([sys.executable, str(Path(root) / "bin" / "cc"), *args], capture_output=True, text=True, cwd=root)
    return r.returncode, r.stdout + r.stderr


with tempfile.TemporaryDirectory() as t:
    log = Path(t) / f"{MAP}.access.jsonl"
    rc, out = cc(ROOT, "navigate", MAP, "--access-log", str(log))
    if os.environ.get("CC_REGOLDEN") == "1" and (not GOLD.is_file() or GOLD.read_text() != out):
        GOLD.parent.mkdir(parents=True, exist_ok=True)
        GOLD.write_text(out)
        print(f"REGOLDENED {GOLD.relative_to(ROOT)}")
    gold = GOLD.read_text() if GOLD.is_file() else ""
    check(f"golden: navigate {MAP} equals tests/navigate/{MAP}.txt byte for byte", out == gold,
          "\n" + "\n".join(f"  got  {a}\n  want {b}" for a, b in zip(out.splitlines(), gold.splitlines()) if a != b)[:1500] or out[-600:])
    check("golden: exit status 0 (every walk outcome is a value)", rc == 0, str(rc))
    check("golden: line 1 is the UNTESTED warning", out.startswith("UNTESTED: cc navigate"), out[:120])
    recs = [json.loads(ln) for ln in log.read_text().splitlines()] if log.is_file() else []
    pins = tomllib.loads((ROOT / "fixtures" / "data" / f"{MAP}.toml").read_text())["files"]
    check("T23: one access-log line per chain file read, each route 'loader', partition stored-map:" + MAP,
          bool(recs) and all(r["route"] == "loader" and r["partition"] == f"stored-map:{MAP}" for r in recs), str(recs[:1]))
    check("T23: every logged path is named under <data-root>/ and its sha256 equals the input's pinned manifest",
          bool(recs) and all(r["path"].startswith("<data-root>/") and pins.get(r["path"][len("<data-root>/"):]) == r["sha256"] for r in recs),
          str([r["path"] for r in recs if pins.get(r["path"][len("<data-root>/"):]) != r["sha256"]][:3]))
    check("T23: the transcript states the count the log holds", f"({len(recs)} reads appended;" in out, str(len(recs)))

# ---- the typed refusal: a value with a Next line, UNTESTED first, exit status 1
for arg, why in (("b7-at-line", "method \"block\""), ("no-such-input", "no input 'no-such-input'")):
    rc, out = cc(ROOT, "navigate", arg)
    check(f"refusal: navigate {arg} is REFUSED NOT_A_STORED_MAP ({why}), UNTESTED first, a Next line, exit 1",
          rc == 1 and out.startswith("UNTESTED: ") and "REFUSED NOT_A_STORED_MAP" in out and why in out and "  Next: " in out, f"{rc} {out[-400:]}")

# ---- seen red (a): one node removed from the map must not pass silently
with tempfile.TemporaryDirectory() as t:
    for d in ("bin", "cc", "instruments"):
        shutil.copytree(ROOT / d, Path(t) / d, ignore=shutil.ignore_patterns("__pycache__"))
    for f in ("cc.toml", "checks.toml"):
        shutil.copy2(ROOT / f, Path(t) / f)
    shutil.copytree(ROOT / "inputs" / MAP, Path(t) / "inputs" / MAP)
    m = (Path(t) / "inputs" / MAP / "m.toml")
    text = m.read_text()
    blocks = text.split("\n[[data.files]]\n")
    kept = [b for b in blocks[1:] if 'point = "0.2747"' not in b]
    head = blocks[0].replace('"0.2747" = "truth"\n', "").replace(', "0.2747"]', "]")
    m.write_text("\n[[data.files]]\n".join([head, *kept]))
    rc, out = cc(t, "navigate", MAP, "--access-log", str(Path(t) / "x.jsonl"))
    check("seen red (a): the removal took (the 30 chain blocks of 0.2747 gone, and 0.2747 gone from axes.point)",
          len(kept) == len(blocks) - 1 - 30 and "0.2747" not in tomllib.loads(m.read_text())["axes"]["point"], f"{len(blocks) - 1} -> {len(kept)}")
    check("seen red (a): the corrupted map's transcript differs from the golden", out != gold, out[-300:])
    check("seen red (a): its node list no longer shows 0.2747", "0.2747 [" not in out and "nodes (chain files declared per size)" in out, out[-500:])

# ---- seen red (b): nav.py's move (UNRES -> MID -> stop) would locate an unreadable node; the shipped table does not
rng = np.random.default_rng(1114)


def node(j):
    """a synthetic map: DIS below node 3, ORD above, and an interval at node 3 that straddles 0 and both margin edges (cell UNRES)."""
    b = rng.normal(0.5, 1e-4, (10, 40))
    a = b + [-0.1, -0.1, -0.1, 0.0, 0.1, 0.1, 0.1][j] + np.linspace(-0.02, 0.02, 10)[:, None] * (j == 3)
    return navigate.needle(list(a), list(b), 10, 2)


w = navigate.walk(node, 7)
check("UNRES: the shipped walk ends UNRESOLVED at the node whose cell is UNRES (no location claimed)",
      w.outcome == "UNRESOLVED" and w.trace[-1][1].cell == navigate.Sign.UNRES and w.trace[-1][0] == 3, f"{w.outcome} {[(j, r.cell) for j, r in w.trace]}")
shipped = dict(navigate.MOVE)
navigate.MOVE.update({c: {"DIS": "lo", "ORD": "hi", "MID": "stop"}[navigate.SIDE[c]] for c in navigate.SIDE})   # nav.py lines 15, 18: MOVE[SIDE[cell]]
w_old = navigate.walk(node, 7)
navigate.MOVE.clear()
navigate.MOVE.update(shipped)
check("seen red (b): with nav.py's MOVE[SIDE[cell]] the same map STOPS at the UNRES node (the T1 defect), so the check above can fail",
      w_old.outcome == "STOP" and w_old.trace[-1][0] == 3, w_old.outcome)
check("MOVE is total over the eight sign cells and the NOT_ESTABLISHED reading", set(navigate.MOVE) == set(navigate.Sign) | {None}, str(set(navigate.MOVE)))

print("".join(f"FAILED {b}\n" for b in bad) + "test_navigate: " + ("FAILED" if bad else "all passed"))
sys.exit(1 if bad else 0)
