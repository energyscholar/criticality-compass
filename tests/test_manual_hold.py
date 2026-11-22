"""test_manual_hold - plan 1634 T1-T7b: `compass hold` (bin/cc hold): the catalogue, a dry run that writes nothing, no default hold mode, a refusal that is
recorded, two identical runs that leave two records, a scored short run, a verifier that can fail, and a wall clock that kills the run.
Short runs use a TEST WORLD: ising-apparatus-static.toml with horizon = TEST_HORIZON (plan 1634 phase 0 M1: the smallest horizon that still writes score.json,
horizon 1, 1 to 2 s at 1-minute load 16). The wall-clock test uses WALL_HORIZON (horizon 20000 ran 34 s at load 16)."""
import json
import os
import re
import shutil
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from lib import bad, check, guarded  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
TEST_HORIZON = 1
WALL_HORIZON = 20000
CAT_WORLDS = {"ising": ["production", "static", "static-r2", "static-r3", "field", "field-hard"], "at": ["production", "static"]}
SCORE7 = ("outcome", "lock", "in_fraction", "rms_e_g", "mean_e", "hold_steps", "accuracy")
LOAD = os.getloadavg()[0]


def hold(*args, cwd=None, env=None):
    r = subprocess.run([sys.executable, str(ROOT / "bin" / "cc"), "hold", *map(str, args)], capture_output=True, text=True, cwd=cwd or ROOT, timeout=600,
                       env={**os.environ, **(env or {})})
    return r.returncode, r.stdout + r.stderr


def world_file(d, horizon):
    src = (ROOT / "system-instantiated/plugins/ising/ising-apparatus-static.toml").read_text()
    p = Path(d) / f"world-h{horizon}.toml"
    p.write_text(re.sub(r"(?m)^horizon\s*=.*$", f"horizon = {horizon}", src))
    return p


def records(out):
    return sorted(p for p in Path(out).iterdir() if p.is_dir()) if Path(out).is_dir() else []


def whole_record_text(rec):
    return b"\0".join(p.read_bytes() for p in sorted(rec.rglob("*")) if p.is_file())


def no_absolute(rec, out):
    """A3: no absolute --out path, no home directory anywhere in a record."""
    blob = whole_record_text(rec)
    return [n for n in (str(Path(out).resolve()), str(Path(out)), str(Path.home())) if n.encode() in blob]


def j(rec):
    return json.loads((rec / "run.json").read_text())


T = Path(tempfile.mkdtemp(prefix="t-manual-hold-"))
W = world_file(T, TEST_HORIZON)


def t1():
    rc, out = hold("--list")
    lines = out.splitlines()
    miss = [f"{s} {w}" for s, ws in CAT_WORLDS.items() for w in ws if not any(l.split()[:2] == [s, w] for l in lines)]
    check("T1 list: exit 0", rc == 0, f"rc={rc} {out[:200]}")
    check("T1 list: one line per catalogue world of ising and at", not miss, str(miss))
    check("T1 list: a pending line for fhn", any(l.split()[:2] == ["fhn", "pending"] for l in lines), out[:300])


def t2():
    o = T / "dry-out"
    o.mkdir()
    t0 = time.time()
    rc, out = hold("--dry", "ising", "static", "--needle", "settled", "--out", o)
    dt = time.time() - t0
    check("T2 dry: exit 0 and an INPUT block", rc == 0 and "INPUT" in out, f"rc={rc} {out[:200]}")
    import hashlib
    paths = {"world": "system-instantiated/plugins/ising/ising-apparatus-static.toml",
             "needle": "needle-settings/ising/hold-settled.toml", "score": "environment/hold-score-ising.toml"}
    wrong = [r for r, p in paths.items() if hashlib.sha256((ROOT / p).read_bytes()).hexdigest()[:12] not in out]
    check("T2 dry: the three sha256[:12] (world, needle, score) equal the files' own", not wrong, str(wrong))
    check("T2 dry: no env line (A13: the env file is rewritten for the record)", not re.search(r"(?m)^  env", out), out[:300])
    check("T2 dry: --out is still empty", not list(o.iterdir()), str(list(o.iterdir())))
    if LOAD <= 8:
        check("T2 dry: returns in under 5 s", dt < 5, f"{dt:.1f} s at load {LOAD:.1f}")
    else:
        print(f"note T2 dry: {dt:.1f} s, budget not judged (load {LOAD:.1f})")


def t3():
    o = T / "nomode-out"
    rc, out = hold("ising", "static", "--out", o)
    check("T3 no default mode: exit 2", rc == 2, f"rc={rc}")
    check("T3 no default mode: every Ising needle is named", all(n in out for n in ("settled", "mid", "settled-off")) and "no hold mode is the default" in out, out[:300])
    check("T3 no default mode: nothing written", not o.exists() or not list(o.iterdir()))


def refused_run(out):
    return hold("ising", W, "--needle", ROOT / "navigator" / "hold-settled.toml", "--out", out)


def t4():
    o = T / "refused-out"
    rc, out = refused_run(o)
    recs = records(o)
    check("T4 refusal: exit 2", rc == 2, f"rc={rc} {out[-300:]}")
    check("T4 refusal: OUTPUT shows field=M parse=A", re.search(r"field=M parse=A", out) is not None, out[-300:])
    check("T4 refusal: one record", len(recs) == 1, str(recs))
    if recs:
        r = recs[0]
        check("T4 refusal: status refused, run/refused.json present", j(r)["status"] == "refused" and (r / "run" / "refused.json").is_file(), str(j(r)["status"]))
        check("T4 refusal: needle recorded as path", j(r)["needle"] == "path")
        rc2, o2 = hold("--verify", r)
        check("T4 refusal: --verify exit 0", rc2 == 0, o2)
        check("T4 refusal: no absolute --out path or home directory in the record (A3)", not no_absolute(r, o), str(no_absolute(r, o)))


def t5():
    o = T / "twice-out"
    refused_run(o)
    first = records(o)[0]
    before = (first / "run" / "refused.json").read_bytes()
    refused_run(o)
    recs = records(o)
    check("T5 two identical runs: two records", len(recs) == 2, str([p.name for p in recs]))
    check("T5 two identical runs: both verify", all(hold("--verify", r)[0] == 0 for r in recs))
    check("T5 two identical runs: the first's run/refused.json is unchanged", (first / "run" / "refused.json").read_bytes() == before)


def t6():
    o = T / "scored-out"
    rc, out = hold("ising", W, "--needle", "settled", "--out", o)
    recs = records(o)
    check("T6 scored: exit 0", rc == 0, f"rc={rc} {out[-400:]}")
    check("T6 scored: at least one RUN line was printed", re.search(r"(?m)^RUN step \d+ phase \S+ index \d+", out) is not None, out[:300])
    check("T6 scored: one record", len(recs) == 1)
    if not recs:
        return
    r = recs[0]
    m, sc = j(r), json.loads((r / "run" / "score.json").read_text())
    check("T6 scored: status scored", m["status"] == "scored", m["status"])
    check("T6 scored: summary equals the seven fields of run/score.json", m["summary"] == {k: sc[k] for k in SCORE7})
    check("T6 scored: every listed output exists and matches", hold("--verify", r)[0] == 0 and any(x["path"] == "run/score.json" for x in m["outputs"]))
    head = subprocess.run(["git", "-C", str(ROOT), "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
    check("T6 scored: versions.git.head equals git rev-parse HEAD", m["versions"]["git"]["head"] == head, str(m["versions"]["git"]))
    check("T6 scored: code_digest is 64 hex", re.fullmatch(r"[0-9a-f]{64}", m["versions"]["code_digest"]) is not None)
    text = (r / "run.json").read_text()
    host = socket.gethostname().split(".")[0]
    check("T6 scored: run.json has no home directory or hostname", not any(s in text for s in ("/Us" + "ers/", "/ho" + "me/", host)), host)
    check("T6 scored: terminal.txt is what was printed", (r / "terminal.txt").read_text().rstrip() == out.rstrip(), "terminal.txt differs from stdout")
    check("T6 scored: no absolute --out path or home directory in the record (A3)", not no_absolute(r, o), str(no_absolute(r, o)))
    return r


def t7(src):
    for what, edit in (("run/score.json", lambda c: (c / "run" / "score.json").write_bytes(bytes([(c / "run" / "score.json").read_bytes()[0] ^ 1]) + (c / "run" / "score.json").read_bytes()[1:])),
                       ("run/map.jsonl", lambda c: (c / "run" / "map.jsonl").unlink()),
                       ("run.json", lambda c: (c / "run.json").write_text((c / "run.json").read_text().replace('"scored"', '"refused"', 1)))):
        c = T / ("copy-" + what.replace("/", "_"))
        shutil.copytree(src, c)
        edit(c)
        rc, out = hold("--verify", c)
        check(f"T7 verify can fail: {what} named, exit 1", rc == 1 and what in out, f"rc={rc} {out[:200]}")


def t7b():
    o = T / "wall-out"
    wf = world_file(T, WALL_HORIZON)
    rc, out = hold("ising", wf, "--needle", "settled", "--wall", 5, "--out", o)
    recs = records(o)
    check("T7b wall clock: exit 3", rc == 3, f"rc={rc} {out[-300:]}")
    if recs:
        m = j(recs[0])
        check("T7b wall clock: status wall-clock", m["status"] == "wall-clock", m["status"])
        with socket.socket() as s:
            check("T7b wall clock: nothing listens on the record's port", s.connect_ex(("127.0.0.1", m["port"])) != 0, str(m["port"]))
        check("T7b wall clock: the record verifies", hold("--verify", recs[0])[0] == 0)
    else:
        check("T7b wall clock: a record exists", False, "no record")


def refused_with(args, why, what, cwd=None, env=None):
    rc, out = hold(*args, cwd=cwd, env=env)
    check(f"{what}: exit 2", rc == 2, f"rc={rc} {out[-200:]}")
    check(f"{what}: a REFUSED line that names the reason, no traceback", "REFUSED:" in out and why in out and "Traceback" not in out, out[-300:])


def t12(rec):
    """A13: terminal.txt and run.json agree on every printed sha."""
    shas = dict(re.findall(r"(?m)^  (world|needle|score) +\S+ +sha256 ([0-9a-f]{12})$", (rec / "terminal.txt").read_text()))
    by = {i["role"]: i["sha256"] for i in j(rec)["inputs"]}
    check("T12 terminal.txt prints sha256 for world, needle and score", set(shas) == {"world", "needle", "score"}, str(shas))
    check("T12 terminal.txt and run.json agree on every printed sha", all(by[r].startswith(v) for r, v in shas.items()), f"{shas} vs {by}")
    check("T12 terminal.txt prints no env line", "  env " not in (rec / "terminal.txt").read_text())


def t13():
    d = T / "a14"
    d.mkdir()
    noseed = d / "noseed.toml"
    noseed.write_text(re.sub(r"(?m)^seed\s*=.*\n", "", W.read_text()))
    refused_with(["ising", noseed, "--needle", "settled", "--out", d / "o1"], "no top-level seed", "T13 world with no seed (A14)")
    check("T13 world with no seed: nothing written", not (d / "o1").exists() or not list((d / "o1").iterdir()))
    rc, out = hold("ising", noseed, "--needle", "settled", "--seed", 7, "--dry")
    check("T13 world with no seed but --seed given: the dry run resolves seed 7", rc == 0 and "seed 7 (overridden)" in out, out[:200])
    tbl = d / "table-seed.toml"
    tbl.write_text("seed = 5\n[other]\nseed = 3\n")
    import hashlib
    rc, out = hold("ising", tbl, "--needle", "settled", "--seed", 7, "--dry")
    want = hashlib.sha256(b"seed = 7\n[other]\nseed = 3\n").hexdigest()[:12]
    check("T13 --seed rewrites only the top-level seed (A15)", rc == 0 and want in out, out[:300])
    ok = d / "ok-record"
    shutil.copytree(good[0], ok)
    m = json.loads((ok / "run.json").read_text())
    del m["outputs"]
    (ok / "run.json").write_text(json.dumps(m))
    import hashlib as h
    (ok / "run.json.sha256").write_text(f"{h.sha256((ok / 'run.json').read_bytes()).hexdigest()}  run.json\n")
    refused_with(["--verify", ok], "outputs", "T13 --verify of a run.json with no outputs (A14)")
    extra = d / "extra-record"
    shutil.copytree(good[0], extra)
    (extra / "run" / "stray.txt").write_text("x")
    rc, out = hold("--verify", extra)
    check("T13 --verify names a file that is in the record but not in run.json (A15)", rc == 1 and "run/stray.txt" in out, f"rc={rc} {out[:200]}")
    # a tree with no tau-v0.toml beside the catalogue's plugin directory
    tree = d / "tree"
    shutil.copytree(ROOT / "manual", tree / "manual", ignore=shutil.ignore_patterns("__pycache__"))
    for f in ("environment/environment-apparatus-ising.toml", "environment/hold-score-ising.toml"):
        (tree / f).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / f, tree / f)
    (tree / "system-instantiated" / "plugins" / "ising").mkdir(parents=True)
    r = subprocess.run([sys.executable, "-m", "manual.hold", "ising", str(W), "--needle", str(ROOT / "needle-settings/ising/hold-settled.toml"), "--out", str(d / "o3")], capture_output=True, text=True, cwd=tree)
    check("T13 a system with no tau file (A14): REFUSED, exit 2, no traceback", r.returncode == 2 and "REFUSED:" in r.stdout and "tau-v0.toml" in r.stdout and "Traceback" not in r.stdout + r.stderr, f"rc={r.returncode} {(r.stdout + r.stderr)[-300:]}")


def t14():
    rc, out = hold()
    check("T14 no arguments: usage, exit 2", rc == 2 and "usage:" in out and "unknown system" not in out, f"rc={rc} {out[:200]}")
    rc, out = hold("--bogus")
    check("T14 an unknown option: usage error, exit 64", rc == 64, f"rc={rc} {out[-200:]}")
    for w in ("0", "-5"):
        rc, out = hold("ising", "static", "--needle", "settled", "--wall", w, "--dry")
        check(f"T14 --wall {w}: usage error, exit 64", rc == 64 and "greater than 0" in out, f"rc={rc} {out[-200:]}")


def t15():
    """A15: argv in run.json is the argv as given (relative to where the run was started)."""
    rc, out = hold("ising", W.name, "--needle", "settled", "--out", "rel-out", cwd=T)
    recs = records(T / "rel-out")
    check("T15 a run from a working directory with relative arguments: exit 0, one record", rc == 0 and len(recs) == 1, f"rc={rc} {out[-200:]}")
    if recs:
        check("T15 argv in run.json is the real argv", j(recs[0])["argv"] == ["hold", "ising", W.name, "--needle", "settled", "--out", "rel-out"], str(j(recs[0])["argv"]))


guarded("T1", t1)
guarded("T2", t2)
guarded("T3", t3)
guarded("T4", t4)
guarded("T5", t5)
good = []
guarded("T6", lambda: good.append(t6()))
guarded("T7", lambda: t7(good[0]) if good and good[0] else check("T7 verify can fail: needs T6's record", False, "no T6 record"))
guarded("T7b", t7b)
guarded("T12", lambda: t12(good[0]) if good and good[0] else check("T12 needs T6's record", False, "no T6 record"))
guarded("T13", lambda: t13() if good and good[0] else check("T13 needs T6's record", False, "no T6 record"))
guarded("T14", t14)
guarded("T15", t15)
shutil.rmtree(T, ignore_errors=True)
print("test_manual_hold: " + ("FAILED " + "; ".join(bad) if bad else "ok"))
sys.exit(1 if bad else 0)
