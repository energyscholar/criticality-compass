"""test_wheel_hold - plan 1634 T8: the wheel runs a hold outside the clone. Builds a wheel as tests/test_wheel.py does (from `git ls-files` of the working tree: every new
file must be `git add`ed first), installs it with --no-deps into a fresh venv made by this interpreter, reaches numpy through one .pth file naming the directory that
holds this interpreter's numpy, then from an empty directory runs `compass hold --list` and a short scored run, and checks that nothing was written inside site-packages,
that the man page is installed, and that tests/test_wheel.py fails on no name its baseline did not already fail (plan 1634 ruling A7: its two baseline failures are
host paths in results/ and process words in cc/*.py; the only new hits the added trees may bring are the two `~/soft` + `ware` lines of environment/environment*.toml)."""
import os
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from lib import bad, check, guarded  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
W = "criticality_compass/workspace/"
BASELINE_FAILS = {"no file of the wheel names a home directory, one of the author's machines or trees, or a private person",
                  "no user-facing file of the wheel (help, docs, CLAIMS, code) uses the process vocabulary"}
ADDED = ("environment/", "navigator/", "needlestream/", "common/", "system-instantiated/", "needle-settings/", "manual/", "needleview/")
EXPECTED_NEW = {"environment/environment.toml", "environment/environment-blind.toml"}
HOST = [re.compile(p) for p in ("/ho" + "me/", "/Us" + "ers/", "~/soft" + "ware", r"(?i)\bpen" + r"guin\b", r"(?i)\bji" + r"ll\b", r"(?i)\bporch" + r"light\b", "has-anyone-" + "looked", "aura" + "sys")]
VOCAB = [re.compile(p) for p in (r"(?i)\bar" + r"gus\b", r"\bAudi" + r"tor\b", r"(?<!random\.)\bGene" + r"rator\b", r"(?i)\brel" + r"ay \d", r"\bLOG " + r"E\d+")]
LOAD = os.getloadavg()[0]
T = Path(tempfile.mkdtemp(prefix="t-wheel-hold-"))


def run(cmd, cwd, timeout=900, **kw):
    r = subprocess.run([str(c) for c in cmd], capture_output=True, text=True, cwd=cwd, timeout=timeout, **kw)
    return r.returncode, r.stdout + r.stderr


def snapshot(sp):
    return {p.relative_to(sp).as_posix() for p in sp.rglob("*") if "__pycache__" not in p.parts}


def t8():
    src = T / "src"
    names = [n for n in subprocess.run(["git", "-C", str(ROOT), "ls-files", "-z"], capture_output=True, check=True).stdout.decode().split("\0") if n]
    for n in names:
        if (ROOT / n).is_file():
            (src / n).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(ROOT / n, src / n)
    rc, out = run([sys.executable, "-m", "pip", "wheel", "--no-deps", "--no-build-isolation", "-q", "-w", T / "dist", src], T)
    wheels = sorted((T / "dist").glob("*.whl"))
    check("T8 a wheel builds", rc == 0 and len(wheels) == 1, out[-300:])
    if not wheels:
        return
    z = zipfile.ZipFile(wheels[0])
    have = {n[len(W):] for n in z.namelist() if n.startswith(W)}
    check("T8 the wheel carries manual/, the stage-4 trees and the man page", all(any(n.startswith(d) for n in have) for d in ADDED) and any(n.endswith("compass.1") for n in z.namelist()),
          str([d for d in ADDED if not any(n.startswith(d) for n in have)]))
    new_hits = sorted({n for n in have if n.startswith(ADDED) and n.endswith((".toml", ".py", ".md")) for ln in z.read(W + n).decode("utf-8", "replace").splitlines() for p in HOST if p.search(ln)})
    check("T8 the added trees bring no host path but the two expected ones (ruling A7)", set(new_hits) <= EXPECTED_NEW, str(new_hits))
    vhits = sorted({n for n in have if n.startswith(ADDED) and n.endswith((".md", ".py", ".html")) for ln in z.read(W + n).decode("utf-8", "replace").splitlines() for p in VOCAB if p.search(ln)})
    check("T8 the added trees use no process vocabulary", not vhits, str(vhits[:4]))
    venv = T / "venv"
    rc, out = run([sys.executable, "-m", "venv", venv], T)
    check("T8 a fresh venv", rc == 0, out[-200:])
    py = venv / "bin" / "python"
    import numpy
    sp = Path(run([py, "-c", "import sysconfig;print(sysconfig.get_paths()['purelib'])"], T)[1].strip())
    (sp / "numpy-here.pth").write_text(str(Path(numpy.__file__).resolve().parent.parent) + "\n")
    rc, out = run([py, "-m", "pip", "install", "--no-deps", "--no-index", "-q", wheels[0]], T)
    check("T8 the wheel installs with --no-deps", rc == 0, out[-300:])
    rc, out = run([py, "-c", "import criticality_compass as c;print(c.__file__)"], T)
    check("T8 compass resolves inside the fresh venv", rc == 0 and str(venv) in out, out[-200:])
    cwd = T / "empty"
    cwd.mkdir()
    before = snapshot(sp)
    compass = venv / "bin" / "compass"
    env = {k: v for k, v in os.environ.items() if k not in ("PYTHONPATH", "COMPASS_RUNS", "CC_DATA_ROOT")}
    rc, out = run([compass, "hold", "--list"], cwd, env=env)
    check("T8 `compass hold --list` runs outside the clone", rc == 0 and "ising" in out and "fhn" in out, f"rc={rc} {out[-300:]}")
    world = T / "world.toml"
    world.write_text(re.sub(r"(?m)^horizon\s*=.*$", "horizon = 1", (ROOT / "system-instantiated/plugins/ising/ising-apparatus-static.toml").read_text()))
    rc, out = run([compass, "hold", "ising", world, "--needle", "settled"], cwd, env=env)
    recs = [p for p in (cwd / "compass-runs").glob("*") if p.is_dir()] if (cwd / "compass-runs").is_dir() else []
    check("T8 a short scored run from the wheel: exit 0, one record under ./compass-runs/", rc == 0 and len(recs) == 1, f"rc={rc} {out[-400:]}")
    rc, out = run([compass, "hold", "--verify", recs[0]], cwd, env=env) if recs else (1, "no record")
    check("T8 the record verifies", rc == 0, out[-200:])
    check("T8 nothing was written inside site-packages", snapshot(sp) == before, str(sorted(snapshot(sp) - before)[:4]))
    check("T8 the man page is installed at <venv>/share/man/man1/compass.1", (venv / "share" / "man" / "man1" / "compass.1").is_file())
    rc, out = run([sys.executable, str(ROOT / "tests" / "test_wheel.py")], ROOT)
    fails = {ln[5:].split(":")[0].strip() for ln in out.splitlines() if ln.startswith("FAIL ")}
    check("T8 tests/test_wheel.py fails on no name outside its baseline (ruling A7)", fails <= BASELINE_FAILS, str(sorted(fails - BASELINE_FAILS)))


guarded("T8", t8)
shutil.rmtree(T, ignore_errors=True)
print("test_wheel_hold: " + ("FAILED " + "; ".join(bad) if bad else "ok"))
sys.exit(1 if bad else 0)
