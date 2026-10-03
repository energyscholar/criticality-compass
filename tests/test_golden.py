"""test_golden - recorded `bin/cc` transcripts (both modes) of tests/golden/golden.toml, byte for byte.
CC_REGOLDEN=1 (bin/cc test --regolden) rewrites the differing or missing ones and lists them; it never deletes."""
import difflib
import os
import shutil
import stat
import subprocess
import sys
import tempfile
import time
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
GOLD = ROOT / "tests" / "golden"
REGOLDEN = os.environ.get("CC_REGOLDEN") == "1"
VERBOSE = os.environ.get("CC_VERBOSE") == "1"


def transcript(case, mode):
    """Run one case in a fresh writable copy of the repo: `before`, the plants, then the command."""
    with tempfile.TemporaryDirectory() as t:
        repo = Path(t) / "repo"
        shutil.copytree(ROOT, repo, ignore=shutil.ignore_patterns(".git", "__pycache__"))
        for p in [repo, *repo.rglob("*")]:
            p.chmod(p.stat().st_mode | stat.S_IWUSR)

        def cc(args):
            return subprocess.run([sys.executable, str(repo / "bin" / "cc"), *args], capture_output=True, text=True, cwd=repo)
        for b in case.get("before", []):
            cc(b)
        for src, dst in case.get("plant", {}).items():
            shutil.copyfile(ROOT / "tests" / "planted" / "golden" / src, repo / dst)
        argv = case["argv"] + (["--advanced"] if mode == "advanced" else [])
        r = cc(argv)
        return f"$ bin/cc {' '.join(argv)}\n{r.stdout}{r.stderr}exit {r.returncode}\n"


bad, written = [], []
for case in tomllib.loads((GOLD / "golden.toml").read_text())["case"]:
    for mode in ("basic", "advanced"):
        t0 = time.time()
        f, got = GOLD / f"{case['id']}.{mode}.txt", transcript(case, mode)
        if VERBOSE:
            print(f"seconds {time.time() - t0:7.1f}  {f.name}")
        want = f.read_text() if f.is_file() else None
        if got == want:
            print(f"ok   {f.name}")
        elif REGOLDEN:
            f.write_text(got)
            written.append(f.name)
            print(f"REGOLDENED tests/golden/{f.name}")
        else:
            diff = list(difflib.unified_diff((want or "").splitlines(), got.splitlines(), f.name, "now", lineterm=""))
            bad.append(f.name)
            print(f"FAIL {f.name}" + ("" if want is not None else " (no transcript yet)"))
            print("\n".join(diff[:40]))
            print("Next: if the change is intended, bin/cc test --regolden test_golden, read the new files, and list them in your report")
print(f"test_golden: {'FAILED ' + str(len(bad)) if bad else 'all passed'}" + (f" (regoldened {len(written)})" if written else ""))
sys.exit(1 if bad else 0)
