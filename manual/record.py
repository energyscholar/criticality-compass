"""manual.record - the saved-run record of `compass hold` (plan 1634, format compass-manual-run/1): the manifest, the status table, the sha256s,
the code digest and the verifier. A record holds no hostname, user name or absolute path: every path in it is relative to the record directory."""
import hashlib
import json
import platform
import subprocess
from pathlib import Path

SCHEMA = "compass-manual-run/1"
STATUS = {0: "scored", 2: "refused", 1: "infrastructure-failure", "wall": "wall-clock"}   # keyed by the orchestrator's exit code; "wall" is the driver's kill
UNKNOWN = "unknown-exit"
EXIT = {"scored": 0, "refused": 2, "infrastructure-failure": 1, "wall-clock": 3, UNKNOWN: 1}   # the wrapper's exit codes
DIGEST_TREES = ("bin", "cc", "environment", "navigator", "needlestream", "common", "system-instantiated", "needle-settings", "manual")
SCORE_FIELDS = ("outcome", "lock", "in_fraction", "rms_e_g", "mean_e", "hold_steps", "accuracy")


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def status_of(orch_exit, wall_killed):
    return STATUS.get({True: "wall", False: orch_exit}[wall_killed], UNKNOWN)


def code_digest(root):
    files = sorted(p for t in DIGEST_TREES if (root / t).is_dir() for p in (root / t).rglob("*")
                   if p.is_file() and "__pycache__" not in p.parts and p.suffix != ".pyc")
    return hashlib.sha256("".join(f"{p.relative_to(root).as_posix()} {sha(p)}\n" for p in files).encode()).hexdigest()


def _git(root, *a):
    return subprocess.run(["git", "-C", str(root), *a], capture_output=True, text=True).stdout.strip()


def versions(root):
    try:
        from importlib import metadata
        dist = metadata.version("criticality-compass")
    except Exception:  # noqa: BLE001 - a clone that was never installed reads its own pyproject
        import tomllib
        pp = root / "pyproject.toml"
        dist = tomllib.loads(pp.read_text())["project"]["version"] if pp.is_file() else "not-installed"
    clone = (root / ".git").exists()
    git = {"head": _git(root, "rev-parse", "HEAD"), "dirty": bool(_git(root, "status", "--porcelain"))} if clone else "not-a-clone"
    import numpy
    return {"compass": dist, "git": git, "code_digest": code_digest(root), "python": platform.python_version(), "numpy": numpy.__version__,
            "platform": platform.system() + " " + platform.machine()}


def outputs_of(rec):
    return [{"path": p.relative_to(rec).as_posix(), "sha256": sha(p), "bytes": p.stat().st_size}
            for p in sorted(rec.rglob("*")) if p.is_file() and p.name not in ("run.json", "run.json.sha256")]


def summary_of(status, run, detail="none"):
    if status == "scored":
        sc = json.loads((run / "score.json").read_text())
        return {k: sc[k] for k in SCORE_FIELDS}
    if status == "refused":
        rf = json.loads((run / "refused.json").read_text())
        return {"field": rf["field"], "parse": rf["parse"], "detail": detail}
    return {"reason": status}


def write(rec, manifest):
    """Write run.json (sorted keys) and its digest line; `outputs` is computed here, from the directory as it is."""
    manifest = {**manifest, "schema": SCHEMA, "record": rec.name, "outputs": outputs_of(rec)}
    (rec / "run.json").write_text(json.dumps(manifest, sort_keys=True, indent=2) + "\n")
    (rec / "run.json.sha256").write_text(f"{sha(rec / 'run.json')}  run.json\n")


def verify(rec):
    """-> the list of problems (each names a file); empty means the record is as it was written."""
    rec = Path(rec)
    if not (rec / "run.json").is_file() or not (rec / "run.json.sha256").is_file():
        return ["run.json: missing"]
    bad = [] if (rec / "run.json.sha256").read_text().split()[0] == sha(rec / "run.json") else ["run.json: sha256 does not match run.json.sha256"]
    man = json.loads((rec / "run.json").read_text())
    for o in man["outputs"]:
        p = rec / o["path"]
        bad += [f"{o['path']}: missing"] if not p.is_file() else [f"{o['path']}: sha256 differs"] if sha(p) != o["sha256"] else []
    return bad

