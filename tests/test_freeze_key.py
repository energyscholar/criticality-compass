"""test_freeze_key - `freeze` compares the result's measure_hash (what MEASURES) with the committed tree's, not code_hash (plan 0881 P1.3).
In a committed scratch copy: a result made, then a commit that edits a module in NO measurement closure (view.py) -> freeze ACCEPTS
(the old code_hash compare refused it: the reuse/freeze deadlock); a commit that edits one in every closure (project.py) -> freeze REFUSES."""
from functools import partial
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
import frozen  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
# plan 0881 P2.7: an input with NO frozen result under any set. A re-verdict stands on its frozen parent (it measured nothing), so once the v03 results were
# frozen the old input (b7-at-line, which has a v03 result) was judged by its parent and the closure plant could no longer be refused: the test must start from an unfrozen input.
INPUT = "b7-at-line-5"


from lib import bad, cc as run_cc, check  # noqa: E402


def scenario(rel):
    """Make a result in a committed scratch copy, commit an edit to `rel`, then try to freeze: (rc, output)."""
    with tempfile.TemporaryDirectory() as t:
        repo = Path(t) / "repo"
        shutil.copytree(ROOT, repo, ignore=shutil.ignore_patterns(".git", "__pycache__"))
        frozen.thaw(repo)   # the copy only; the live tree is frozen

        cc = partial(run_cc, repo)

        def git(*args):
            subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@t", *args], cwd=repo, capture_output=True, check=True)
        git("init", "-q")
        git("add", "-A")
        git("commit", "-q", "-m", "copy")
        cc("tables", "fork", "v01-rules", "t4")
        rc, out = cc("run", INPUT, "--tables", "t4")
        check(f"run succeeds ({rel})", rc == 0, out[:300])
        (repo / rel).write_text((repo / rel).read_text() + "\n# planted\n")
        git("commit", "-q", "-a", "-m", f"plant {rel}")
        return cc("freeze", f"{INPUT}@t4")


rc, out = scenario("cc/view.py")
check("a commit outside the measurement closure leaves a result freezable (code_hash differs, measure_hash does not)",
      rc == 0 and out.startswith("froze "), out)
rc, out = scenario("cc/project.py")
check("a commit inside the closure refuses the freeze (RED)", rc == 1 and "REFUSED" in out and "measure_hash" in out and "Next:" in out, out)
print("test_freeze_key: " + ("FAILED" if bad else "all passed"))
sys.exit(1 if bad else 0)
