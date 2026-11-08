"""test_wheel - plan 0985 phase 3: what a built wheel carries. The workspace copy holds what the installed tool NEEDS at run time and nothing else:
the code, the declared data (tables, inputs, cases, expected, families, fixtures, instruments), the stored results and the frozen record (a run refuses
when a frozen result or frozen test file is absent, seen below), the CC0 data under data/ (cc.toml [data] local), docs/ (tabulate writes docs/verdict-table.html),
benchmark/ (bench verify), and README, CLAIMS, LICENSE, NOTICE. Of tests/ it carries ONLY the files FROZEN.json names (the structure gate's C7); the other
tests are the clone's. No file of the wheel names a home directory, a user's tree or one of the author's machines.
Builds a wheel (python -m pip wheel --no-deps --no-build-isolation) into a scratch directory; needs setuptools."""
import json
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
W = "criticality_compass/workspace/"


from lib import bad, check  # noqa: E402


with tempfile.TemporaryDirectory() as t:
    src = Path(t) / "src"
    src.mkdir()
    names = [n for n in subprocess.run(["git", "-C", str(ROOT), "ls-files", "-z"], capture_output=True, check=True).stdout.decode().split("\0") if n]
    for n in names:   # the tracked files as they are in the working tree (a hook runs before the commit exists)
        if (ROOT / n).is_file():
            (src / n).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(ROOT / n, src / n)
    r = subprocess.run([sys.executable, "-m", "pip", "wheel", "--no-deps", "--no-build-isolation", "-q", "-w", str(Path(t) / "dist"), str(src)], capture_output=True, text=True)
    wheels = sorted((Path(t) / "dist").glob("*.whl"))
    check("a wheel builds", r.returncode == 0 and len(wheels) == 1, r.stderr[-300:])
    if wheels:
        z = zipfile.ZipFile(wheels[0])
        names = [n[len(W):] for n in z.namelist() if n.startswith(W)]
        have = set(names)
        frozen = json.loads((ROOT / "FROZEN.json").read_text())["files"]
        frozen_tests = {k for k in frozen if k.startswith("tests/")}
        check("the frozen record and every frozen file of it are in the wheel", "FROZEN.json" in have and all(k in have for k in frozen), str([k for k in frozen if k not in have][:3]))
        check("tests/ holds exactly the files FROZEN.json names", {n for n in have if n.startswith("tests/")} == frozen_tests, str(sorted(n for n in have if n.startswith("tests/") and n not in frozen_tests)[:3]))
        check("the CC0 data under data/ is in the wheel (cc.toml [data] local)", "data/l8/ATTRIBUTION.md" in have, "data/ missing")
        check("README, CLAIMS, LICENSE and NOTICE are in the wheel", all(f in have for f in ("README.md", "CLAIMS.md", "LICENSE", "NOTICE")), str([f for f in ("README.md", "CLAIMS.md", "LICENSE", "NOTICE") if f not in have]))
        check("the run-time trees are in the wheel", all(any(n.startswith(d + "/") for n in have) for d in ("bin", "cc", "tables", "inputs", "cases", "expected", "families", "fixtures", "instruments", "results", "docs", "benchmark")))
        check("no platform binary (cc/_ext/*.so) is in the wheel", not [n for n in have if n.endswith(".so")])
        pats = [re.compile(p) for p in ("/ho" + "me/", "/Us" + "ers/", "~/soft" + "ware", r"(?i)\bpen" + r"guin\b", r"(?i)\bji" + r"ll\b", r"(?i)\bporch" + r"light\b", "hal-" + "main", "has-anyone-" + "looked", "aura" + "sys", "structure-" + "checks",
                                                  r"\bRo" + r"bin\b", r"\bBr" + r"uce\b(?! Stephenson)")]
        # plan 0985 phase 4: the author's process vocabulary (roles, the review agent, review relays, private log entries) is not user-facing text. Data files keep plan numbers.
        vocab = [re.compile(p) for p in (r"(?i)\bar" + r"gus\b", r"\bAudi" + r"tor\b", r"\bGene" + r"rator\b", r"GPT" + r"-6", r"(?i)\brel" + r"ay \d", r"\bLOG " + r"E\d+", r"\bE\d{3}\b(?<!E731)")]
        hit = [n for n in names if not n.endswith((".npz", ".so")) for ln in z.read(W + n).decode("utf-8", "replace").splitlines() for p in pats if p.search(ln)]
        check("no file of the wheel names a home directory, one of the author's machines or trees, or a private person", not hit, str(sorted(set(hit))[:4]))
        user_facing = [n for n in names if n.endswith((".md", ".html", ".py")) or n in ("bin/cc", "cc.toml")]   # help text, docs, CLAIMS, code strings
        vhit = [n for n in user_facing for ln in z.read(W + n).decode("utf-8", "replace").splitlines() for p in vocab if p.search(ln)]
        check("no user-facing file of the wheel (help, docs, CLAIMS, code) uses the process vocabulary", not vhit, str(sorted(set(vhit))[:6]))
print("test_wheel: " + ("FAILED " + "; ".join(bad) if bad else "ok"))
sys.exit(1 if bad else 0)
