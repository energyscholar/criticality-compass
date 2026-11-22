"""manual.hold - `compass hold`: one hold run of a catalogue system through environment.run_hold, printed and saved (plan 1634).
It wraps the orchestrator as a subprocess and edits nothing of it. Entry: python -m manual.hold --help (bin/cc hold passes the invoking directory in COMPASS_CWD)."""
import argparse
import contextlib
import json
import os
import re
import secrets
import shutil
import signal
import socket
import subprocess
import sys
import tempfile
import time
import tomllib
from datetime import datetime, timezone
from pathlib import Path

from manual import record as REC

ROOT = Path(__file__).resolve().parent.parent
CAT = tomllib.loads((Path(__file__).resolve().parent / "catalogue.toml").read_text())
SYSTEMS = {k: v for k, v in CAT.items() if k != "pending"}
KEYS = {"world": ("kind", "L_blocks", "seed", "horizon", "dials", "drift"), "needle": ("needle_structure", "g", "step", "S", "n_eq")}
OUT = {"scored": ("outcome", "lock", "in_fraction", "rms_e_g", "mean_e", "hold_steps", "accuracy"), "refused": ("field", "parse", "detail")}
MEANING = {0: "scored", 2: "refused", 1: "infrastructure failure", 3: "wall clock reached"}
TERM_GRACE = 30   # seconds between SIGTERM and SIGKILL of the orchestrator


def parser():
    ap = argparse.ArgumentParser(prog="compass hold", description="Run one hold of a catalogue system and save the run as a record.")
    ap.add_argument("system", nargs="?")
    ap.add_argument("world", nargs="?", help="a catalogue world name, or the path of a world .toml file")
    ap.add_argument("--needle", help="hold mode: a catalogue needle name or a .toml path (required; no mode is the default)")
    ap.add_argument("--seed", type=int, help="the one override: write a copy of the world with this seed")
    ap.add_argument("--wall", type=float, default=1800.0, help="wall-clock limit in seconds (default 1800)")
    ap.add_argument("--out", help="where records go (default $COMPASS_RUNS, else ./compass-runs)")
    ap.add_argument("--dry", action="store_true", help="print the resolved input and write nothing")
    ap.add_argument("--list", action="store_true", help="print the catalogue")
    ap.add_argument("--verify", metavar="DIR", help="recompute the hashes of a record")
    return ap


def say(lines, text=""):
    lines.append(text)
    print(text, flush=True)


def refuse(lines, why, choices=()):
    say(lines, f"REFUSED: {why}")
    for c in choices:
        say(lines, f"  {c}")
    return 2, lines


def listing(lines):
    for name, s in SYSTEMS.items():
        for w, p in s["worlds"].items():
            say(lines, f"{name:6} {w:11} needles: {' '.join(s['needles'])}   ({p})")
    for name, p in CAT.get("pending", {}).items():
        say(lines, f"{name:6} pending     {p['reason']}")


def pick(token, table, base):
    """-> (label, record source, bytes) for a catalogue name or a file path; a name that is neither is a lookup miss (None)."""
    if token in table:
        return token, table[token], (ROOT / table[token]).read_bytes()
    p = (base / token) if token else None
    return ("path", "path", p.read_bytes()) if p is not None and p.is_file() else None


def free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def keyline(role, text, keys):
    d = tomllib.loads(text)
    return f"  {role} params: " + " ".join(f"{k}={d[k]}" for k in (keys or d) if k in d)


def run(a, base, lines):
    sysn = SYSTEMS.get(a.system)
    if sysn is None:
        return refuse(lines, f"unknown system '{a.system}' (choose one)", [f"{k}" for k in SYSTEMS] + [f"{k} (pending: {v['reason']})" for k, v in CAT.get("pending", {}).items()])
    if not a.needle:
        return refuse(lines, "no hold mode is the default (choose --needle ...)", [f"--needle {n}" for n in sysn["needles"]])
    world, needle = pick(a.world, sysn["worlds"], base), pick(a.needle, sysn["needles"], base)
    for kind, got, tab in (("world", world, sysn["worlds"]), ("needle", needle, sysn["needles"])):
        if got is None:
            return refuse(lines, f"no {kind} '{a.world if kind == 'world' else a.needle}' for {a.system} (a catalogue name or a .toml path)", list(tab))
    wtext = world[2].decode()
    wtext = re.sub(r"(?m)^seed\s*=.*$", f"seed = {a.seed}", wtext) if a.seed is not None and re.search(r"(?m)^seed\s*=", wtext) else (f"seed = {a.seed}\n" + wtext if a.seed is not None else wtext)
    files = {"env": (sysn["env"], (ROOT / sysn["env"]).read_text()), "world": (world[1], wtext), "needle": (needle[1], needle[2].decode()), "score": (sysn["score"], (ROOT / sysn["score"]).read_text())}
    tau = ROOT / sysn["plugin"] / "tau-v0.toml"
    vendor = ROOT / sysn["plugin"] / "vendor" / "VENDOR.toml"
    seed = tomllib.loads(wtext)["seed"]
    vs = REC.versions(ROOT)
    say(lines, "INPUT")
    say(lines, f"  system {a.system}  world {world[0]}  needle {needle[0]}  seed {seed} ({'overridden' if a.seed is not None else 'from the world file'})")
    for role, (src, text) in files.items():
        say(lines, f"  {role:6} {src}  sha256 {REC.hashlib.sha256(text.encode()).hexdigest()[:12]}")
        say(lines, keyline(role, text, KEYS.get(role)))
    say(lines, f"  code   compass {vs['compass']}  git {vs['git'] if isinstance(vs['git'], str) else vs['git']['head'][:12]}  digest {vs['code_digest'][:12]}")
    if a.dry:
        say(lines, "dry run: nothing written")
        return 0, lines
    return execute(a, base, lines, sysn, files, (world, needle), seed, vs, tau, vendor)


def execute(a, base, lines, sysn, files, picked, seed, vs, tau, vendor):
    out = Path(os.path.expanduser(a.out or os.environ.get("COMPASS_RUNS") or "compass-runs"))
    out = out if out.is_absolute() else base / out
    stage, port = Path(tempfile.mkdtemp(prefix="compass-hold-")), free_port()
    (stage / "input").mkdir()
    env_rec = re.sub(r'(?m)^run_dir_root\s*=.*$', 'run_dir_root = "run"', re.sub(r"(?m)^port\s*=.*$", f"port = {port}", files["env"][1]))
    names = {"env": "env.toml", "world": "world.toml", "needle": "needle.toml", "score": "score.toml"}
    for role, (_, text) in files.items():
        (stage / "input" / names[role]).write_text(env_rec if role == "env" else text)
    (stage / "input" / "tau-v0.toml").write_bytes(tau.read_bytes())
    (stage / "run-env.toml").write_text(re.sub(r'(?m)^run_dir_root\s*=.*$', f'run_dir_root = "{stage / "r"}"', env_rec))   # the orchestrator needs an absolute root; the record keeps "run"
    cmd = [sys.executable, "-m", "environment.run_hold", "--env", str(stage / "run-env.toml"), "--at", str(stage / "input" / "world.toml"),
           "--needle", str(stage / "input" / "needle.toml"), "--score", str(stage / "input" / "score.toml")]
    t0, started, seen, wall = time.monotonic(), datetime.now(timezone.utc), 0, False
    with open(stage / "stderr.txt", "wb") as err:
        proc = subprocess.Popen(cmd, cwd=ROOT, stdout=subprocess.DEVNULL, stderr=err, start_new_session=True)
        while proc.poll() is None:
            seen = progress(stage, seen, t0, lines)
            if time.monotonic() - t0 > a.wall and not wall:
                wall = True
                proc.send_signal(signal.SIGTERM)
                t_term = time.monotonic()
            if wall and time.monotonic() - t_term > TERM_GRACE:
                with contextlib.suppress(ProcessLookupError):
                    os.killpg(proc.pid, signal.SIGKILL)
            time.sleep(1)
        with contextlib.suppress(ProcessLookupError):
            os.killpg(proc.pid, signal.SIGKILL)   # nothing of a run may outlive it
    progress(stage, seen, t0, lines)
    done = sorted((stage / "r").glob("*")) if (stage / "r").is_dir() else []
    rid = done[0].name if done else "norunid"
    status = REC.status_of(proc.returncode, wall)
    stamp = started.strftime("%Y%m%dT%H%M%SZ")
    rec = out / f"{stamp}-{a.system}-{picked[0][0]}-{rid}-{secrets.token_hex(2)}"
    out.mkdir(parents=True, exist_ok=True)
    rec.mkdir()
    shutil.move(str(stage / "input"), rec / "input")
    shutil.move(str(done[0]), rec / "run") if done else (rec / "run").mkdir()
    err_text = (stage / "stderr.txt").read_text(errors="replace").strip()
    m = re.search(r"RefusedToStart field=\S+ parse=\S+ ?(.*)", err_text)   # the orchestrator's refusal line carries the detail; refused.json the field and parse
    shown = REC.summary_of(status, rec / "run", scrub((m.group(1) if m else "") or "none", stage)) if status in ("scored", "refused") else {"reason": scrub(err_text.splitlines()[-1] if err_text else status, stage)}
    say(lines, "OUTPUT")
    say(lines, "  " + " ".join(f"{k}={v}" for k, v in shown.items()) + (f"  run_id={rid}" if rid != "norunid" else ""))
    code = REC.EXIT[status]
    say(lines, f"record: {rec.name}")
    say(lines, f"exit {code}: {MEANING[code]}  (status {status})")
    (rec / "terminal.txt").write_text("\n".join(lines) + "\n")
    inputs = [{"role": r, "record_path": f"input/{names[r]}", "source": files[r][0], "sha256": REC.sha(rec / "input" / names[r])} for r in names]
    inputs += [{"role": "tau", "record_path": "input/tau-v0.toml", "source": tau.relative_to(ROOT).as_posix(), "sha256": REC.sha(rec / "input" / "tau-v0.toml")},
               {"role": "vendor", "record_path": "absent", "source": vendor.relative_to(ROOT).as_posix() if vendor.is_file() else "absent", "sha256": REC.sha(vendor) if vendor.is_file() else "absent"}]
    argv = ["hold", a.system, picked[0][0], "--needle", picked[1][0], "--wall", str(a.wall)] + (["--seed", str(a.seed)] if a.seed is not None else [])
    REC.write(rec, {"argv": argv, "started_utc": started.isoformat(timespec="seconds").replace("+00:00", "Z"),
                    "finished_utc": datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"), "wall_s": round(time.monotonic() - t0, 3),
                    "wall_limit_s": a.wall, "status": status, "exit": code, "orchestrator_exit": proc.returncode, "system": a.system, "world": picked[0][0],
                    "needle": picked[1][0], "seed": seed, "seed_overridden": a.seed is not None, "port": port, "inputs": inputs, "run_id": rid, "summary": shown, "versions": vs})
    shutil.rmtree(stage, ignore_errors=True)
    return code, lines


def scrub(text, stage):
    return text.replace(str(stage), "<tmp>").replace(str(ROOT), "<root>").replace(str(Path.home()), "<home>")


def progress(stage, seen, t0, lines):
    """one RUN line per new step record in the orchestrator's report.jsonl, read as it grows."""
    rep = next(iter(sorted((stage / "r").glob("*/report.jsonl"))), None) if (stage / "r").is_dir() else None
    rows = rep.read_text().splitlines() if rep is not None and rep.is_file() else []
    for ln in rows[seen:]:
        try:
            r = json.loads(ln)
        except ValueError:
            return seen   # a half-written line: read it next time
        seen += 1
        r.get("rec") == "step" and say(lines, f"RUN step {r['step']} phase {r['phase']} index {r['index']}  t={time.monotonic() - t0:.0f}s")
    return seen


def main(argv=None):
    a, lines = parser().parse_args(argv), []
    base = Path(os.environ.get("COMPASS_CWD") or os.getcwd())
    if a.verify:
        bad = REC.verify(base / a.verify)
        print("\n".join(bad) if bad else "verified: every file matches run.json")
        return 1 if bad else 0
    if a.list:
        listing(lines)
        return 0
    return run(a, base, lines)[0]


if __name__ == "__main__":
    sys.exit(main())
