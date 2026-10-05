"""test_freeze_key - `freeze` compares the result's measure_hash (what MEASURES) with the committed tree's, not code_hash (plan 0881 P1.3).
In a committed scratch copy: a result made, then a commit that edits a module in NO measurement closure (view.py) -> freeze ACCEPTS
(the old code_hash compare refused it: the reuse/freeze deadlock); a commit that edits one in every closure (project.py) -> freeze REFUSES."""
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

    def plant(rel):
        (repo / rel).write_text((repo / rel).read_text() + "\n# planted\n")
        git("commit", "-q", "-a", "-m", f"plant {rel}")
    git("init", "-q")
    git("add", "-A")
    git("commit", "-q", "-m", "copy")
    cc("tables", "fork", "verdict-x-rules", "t4")
    cc("tables", "fork", "verdict-x-rules", "t5")
    rc, out = cc("run", "b7-at-line", "--tables", "t4")
    check("run succeeds", rc == 0, out[:300])
    cc("run", "b7-at-line", "--tables", "t5")
    plant("cc/view.py")
    rc, out = cc("freeze", "b7-at-line@t4")
    check("a commit outside the measurement closure leaves a result freezable (code_hash differs, measure_hash does not)",
          rc == 0 and out.startswith("froze "), out)
    plant("cc/project.py")
    rc, out = cc("freeze", "b7-at-line@t5")
    check("a commit inside the closure refuses the freeze (RED)", rc == 1 and "REFUSED" in out and "measure_hash" in out and "Next:" in out, out)
print("test_freeze_key: " + ("FAILED" if bad else "all passed"))
sys.exit(1 if bad else 0)
