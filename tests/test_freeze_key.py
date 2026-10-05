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


def scenario(rel):
    """Make a result in a committed scratch copy, commit an edit to `rel`, then try to freeze: (rc, output)."""
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
        cc("tables", "fork", "verdict-x-rules", "t4")
        rc, out = cc("run", "b7-at-line", "--tables", "t4")
        check(f"run succeeds ({rel})", rc == 0, out[:300])
        (repo / rel).write_text((repo / rel).read_text() + "\n# planted\n")
        git("commit", "-q", "-a", "-m", f"plant {rel}")
        return cc("freeze", "b7-at-line@t4")


rc, out = scenario("cc/view.py")
check("a commit outside the measurement closure leaves a result freezable (code_hash differs, measure_hash does not)",
      rc == 0 and out.startswith("froze "), out)
rc, out = scenario("cc/project.py")
check("a commit inside the closure refuses the freeze (RED)", rc == 1 and "REFUSED" in out and "measure_hash" in out and "Next:" in out, out)
print("test_freeze_key: " + ("FAILED" if bad else "all passed"))
sys.exit(1 if bad else 0)
