"""test_code_hash - a result records the content hash of the code that made it (provenance); `freeze` refuses a result whose measure_hash (plan 0881 P1.3; was code_hash)
hash is not the committed tree's (plan 0869 P2). Planted (plan 0876 B: an edit to a module in every closure, project.py; one in no closure keeps the reuse key, so a re-run would reuse): run, commit a code edit, freeze -> RED; run again -> green."""
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
bad = []


def check(name, ok, why=""):
    print(("ok   " if ok else "FAIL ") + name + ("" if ok else f": {why}"))
    if not ok:
        bad.append(name)


with tempfile.TemporaryDirectory() as t:
    repo = Path(t) / "repo"
    shutil.copytree(ROOT, repo, ignore=shutil.ignore_patterns(".git", "__pycache__"))
    for q in [repo, *repo.rglob("*")]:
        q.chmod(q.stat().st_mode | 0o200)

    def cc(*args):
        r = subprocess.run([sys.executable, str(repo / "bin" / "cc"), *args], capture_output=True, text=True, cwd=repo)
        return r.returncode, r.stdout + r.stderr

    def git(*args):
        subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@t", *args], cwd=repo, capture_output=True, check=True)
    git("init", "-q")
    git("add", "-A")
    git("commit", "-q", "-m", "copy")
    cc("tables", "fork", "verdict-x-rules", "t3")
    rid = "b7-at-line@t3"
    rc, out = cc("run", "b7-at-line", "--tables", "t3")
    check("run succeeds in the committed copy", rc == 0, out[:300])
    (repo / "cc" / "project.py").write_text((repo / "cc" / "project.py").read_text() + "\n# planted: code the result did not run\n")
    git("commit", "-q", "-a", "-m", "plant")
    rc, out = cc("freeze", rid)
    check("freeze refuses a result made by other code than the committed tree's (RED)",
          rc == 1 and "REFUSED" in out and "measure_hash" in out and "Next:" in out, out)
    rc, out = cc("run", "b7-at-line", "--tables", "t3")
    rc, out = cc("freeze", rid)
    check("freeze accepts the result once it is re-run at the committed code", rc == 0 and out.startswith("froze "), out)
print("test_code_hash: " + ("FAILED" if bad else "all passed"))
sys.exit(1 if bad else 0)
