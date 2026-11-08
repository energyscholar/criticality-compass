"""test_code_hash - a result records the content hash of the code that made it (provenance); `freeze` refuses a result whose measure_hash (plan 0881 P1.3; was code_hash)
hash is not the committed tree's (plan 0869 P2). Planted (plan 0876 B: an edit to a module in every closure, project.py; one in no closure keeps the reuse key, so a re-run would reuse): run, commit a code edit, freeze -> RED; run again -> green."""
from functools import partial
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
import frozen  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
# plan 0881 P2.7: an input with NO frozen result under any set (b7-at-line has a frozen v03 parent, so a re-verdict stood on it and the plant could not be refused)
INPUT = "b7-at-line-5"


from lib import bad, cc as run_cc, check  # noqa: E402


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
    cc("tables", "fork", "v01-rules", "t3")
    rid = f"{INPUT}@t3"
    rc, out = cc("run", INPUT, "--tables", "t3")
    check("run succeeds in the committed copy", rc == 0, out[:300])
    (repo / "cc" / "project.py").write_text((repo / "cc" / "project.py").read_text() + "\n# planted: code the result did not run\n")
    git("commit", "-q", "-a", "-m", "plant")
    rc, out = cc("freeze", rid)
    check("freeze refuses a result made by other code than the committed tree's (RED)",
          rc == 1 and "REFUSED" in out and "measure_hash" in out and "Next:" in out, out)
    rc, out = cc("run", INPUT, "--tables", "t3")
    rc, out = cc("freeze", rid)
    check("freeze accepts the result once it is re-run at the committed code", rc == 0 and out.startswith("froze "), out)
print("test_code_hash: " + ("FAILED" if bad else "all passed"))
sys.exit(1 if bad else 0)
