"""test_check_fast_outcomes - `bin/cc check --fast` (the pre-commit hook) has three outcomes, each with its own exit code and first line (plan 1273, T4):
clean (0), `check: FAILED: content` (1), `check: NOT EVALUABLE HERE: <resources>` (3). NOT EVALUABLE HERE refuses only a commit whose staged diff
touches cc.toml [check] validate_domain; otherwise the check prints `validate: not evaluated (...)` and runs the tests. A scratch git copy of the
repository, its data root unset (the clone's data/ holds only the local data, so data_root and toolset are absent), its test list cut to one
trivial test, is driven through a real index: (a) a staged change outside the domain -> the tests run, exit 0; (b) a staged change inside it -> exit 3,
the Next line names the missing resource; (c) a staged content defect -> exit 1; (d) a staged git mv out of the domain -> exit 3 (plan 1273 A3). Seen RED on 272c843 (every outcome was `FAILED: validate`, exit 1)."""
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


from lib import bad, check  # noqa: E402


ENV = {k: v for k, v in os.environ.items() if k != "CC_DATA_ROOT" and not k.startswith("GIT_")}   # under the real hook GIT_INDEX_FILE names the REAL index


def git(repo, *a):
    return subprocess.run(["git", "-C", str(repo), "-c", "user.name=t", "-c", "user.email=t@t", *a], capture_output=True, text=True, check=True, env=ENV).stdout


def fast(repo):
    r = subprocess.run([sys.executable, str(repo / "bin" / "cc"), "check", "--fast"], capture_output=True, text=True, cwd=repo, env=ENV)
    return r.returncode, r.stdout + r.stderr


tmp = Path(tempfile.mkdtemp(prefix="cc-outcomes-"))
try:
    repo = tmp / "cc"
    shutil.copytree(ROOT, repo, ignore=shutil.ignore_patterns(".git", "__pycache__", "*.pyc"))
    (repo / "tests" / "test_noop.py").write_text('print("test_noop: all passed")\n')
    ct = repo / "checks.toml"
    ct.write_text(re.sub(r"(?s)\ntests = \[.*?\n\]\n", '\ntests = ["tests/test_noop.py"]\n', ct.read_text(), count=1))
    cc = repo / "cc.toml"   # validate names every slow/exclusive/needs_data/needs_rust test: the scratch lists only the one test it runs
    cc.write_text(re.sub(r"(?m)^(slow|exclusive|needs_data|needs_rust) = \[.*?\]", r"\1 = []", cc.read_text()))
    git(repo, "init", "-q")
    git(repo, "add", "-A")
    git(repo, "commit", "-qm", "base")   # the scratch's own base commit (no hook is installed in it)
    mt = repo / "inputs" / "w2-potts" / "m.toml"
    base = mt.read_text()

    (repo / "README.md").write_text((repo / "README.md").read_text() + "\none more line\n")
    git(repo, "add", "README.md")
    rc, out = fast(repo)
    check("(a) a staged change outside the validate domain, no data root: exit 0", rc == 0, out[-900:])
    check("(a) ... prints the not-evaluated line, naming the absent resources", "validate: not evaluated (data_root, toolset absent; this commit touches no file in the validate domain)" in out, out[:600])
    check("(a) ... and the tests ran", "check: 1 tests passed, 0 failed" in out, out[-600:])
    git(repo, "reset", "-q", "--hard", "HEAD")

    mt.write_text(base + "# a comment: a change inside the validate domain\n")
    git(repo, "add", "inputs/w2-potts/m.toml")
    rc, out = fast(repo)
    lines = out.splitlines()
    check("(b) a staged change inside the validate domain, no data root: exit 3", rc == 3, out[-900:])
    check("(b) ... first line: check: NOT EVALUABLE HERE: data_root, toolset", lines[:1] == ["check: NOT EVALUABLE HERE: data_root, toolset"], str(lines[:3]))
    check("(b) ... the Next line names the resource: commit from a host with data_root", any(ln.startswith("  Next: commit from a host with data_root") for ln in lines), out[-600:])
    check("(b) ... it names the staged path that touches the domain", "inputs/w2-potts/m.toml" in out, out[-600:])
    check("(b) ... no test ran, and it is not a content failure", "tests passed" not in out and "FAILED: content" not in out, out[-600:])
    git(repo, "reset", "-q", "--hard", "HEAD")

    mt.write_text(base.replace('instruments = ["', 'instruments = ["no-such-instrument", "', 1))
    git(repo, "add", "inputs/w2-potts/m.toml")
    rc, out = fast(repo)
    lines = out.splitlines()
    check("(c) a staged content defect, no data root: exit 1", rc == 1, out[-900:])
    check("(c) ... first line: check: FAILED: content", lines[:1] == ["check: FAILED: content"], str(lines[:3]))
    check("(c) ... the content finding is printed", "'no-such-instrument' is not in the instrument registry" in out, out[:900])
    check("(c) ... the absent resources are still said (one line each)", "  data_root: " in out and "checks not evaluated here" in out, out[-600:])
    git(repo, "reset", "-q", "--hard", "HEAD")

    spare = repo / "fixtures" / "data" / "spare.txt"   # in the domain, read by no check: its move leaves no content finding (a moved m.toml would)
    spare.write_text("spare\n")
    git(repo, "add", "fixtures/data/spare.txt")
    git(repo, "commit", "-qm", "spare")
    (repo / "docs").mkdir(exist_ok=True)   # plan 1273 A3: a move OUT of the domain is a change to the domain's file (rename detection folds it to the new path alone)
    git(repo, "mv", "fixtures/data/spare.txt", "docs/spare.txt")
    rc, out = fast(repo)
    lines = out.splitlines()
    check("(d) a staged git mv of an in-domain file out of the domain, no data root: exit 3", rc == 3, out[-900:])
    check("(d) ... first line: check: NOT EVALUABLE HERE: data_root, toolset", lines[:1] == ["check: NOT EVALUABLE HERE: data_root, toolset"], str(lines[:3]))
    check("(d) ... it names the OLD in-domain path", "fixtures/data/spare.txt" in out, out[-600:])
finally:
    shutil.rmtree(tmp, ignore_errors=True)
print("test_check_fast_outcomes: " + ("FAILED" if bad else "all passed"))
sys.exit(1 if bad else 0)
