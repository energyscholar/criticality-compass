"""test_pin_history - a transducer pin is a CONTENT hash, so it is checked against the toolset's git HISTORY, not its working tree (plan 0929, D-0929-5).
A scratch git toolset: a sampler file committed twice and then edited again in the working tree. (1) a pin whose blob exists in an OLD commit passes, the bytes
read are that commit's (not the working tree's), and the supplying commit is recorded; (2) a pin whose sha is in NO commit is still REFUSED, naming the newest committed sha to write,
and so is a pin that matches only the uncommitted working-tree file (in a git toolset only commits are sources)."""
import hashlib
import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path[:0] = [str(ROOT / "cc"), str(ROOT / "cc" / "instruments")]
import declare  # noqa: E402
import transducer  # noqa: E402

bad = []


def check(name, ok, why=""):
    print(("ok   " if ok else "FAIL ") + name + ("" if ok else f": {why}"))
    if not ok:
        bad.append(name)


def git(t, *a):   # GIT_* stripped: under the pre-commit hook GIT_DIR points at the REAL repo, and the scratch commits would land on the branch
    return subprocess.run(["git", "-C", str(t), "-c", "user.name=t", "-c", "user.email=t@t", *a], capture_output=True, text=True, check=True, env={k: v for k, v in os.environ.items() if not k.startswith("GIT_")}).stdout.strip()


def h(b):
    return hashlib.sha256(b).hexdigest()


V1, V2, V3 = b"pub fn a() {}\n", b"mod x;\npub fn a() {}\n", b"mod x;\nmod y;\npub fn a() {}\n"
with tempfile.TemporaryDirectory() as d:
    t = Path(d) / "toolset"
    t.mkdir()
    git(t, "init", "-q")
    f = t / "lib.rs"
    f.write_bytes(V1)
    git(t, "add", "lib.rs")
    git(t, "commit", "-qm", "v1")
    c1 = git(t, "rev-parse", "HEAD")
    f.write_bytes(V2)
    git(t, "commit", "-qam", "v2")
    f.write_bytes(V3)   # the working tree moves on, uncommitted: another project's edit
    p = Path("inputs/x/transducer.toml")
    old = [declare.fmt(x) for x in transducer.update_findings(p, [f"lib.rs sha256 {h(V1)}"], t)]
    check("an OLD commit's blob passes although the working tree differs", old == [], str(old))
    got = transducer.retrieve(t, "lib.rs", h(V1))
    check("the bytes read are the old commit's, not the working tree's", got is not None and got[1] == V1 and got[1] != f.read_bytes(), str(got))
    check("the supplying commit is recorded", got is not None and got[0] == c1, str(got))
    check("supplied() names that commit", transducer.supplied([f"lib.rs sha256 {h(V1)}"], t) == {"lib.rs": {"sha256": h(V1), "commit": c1}})
    plant = [declare.fmt(x) for x in transducer.update_findings(p, ["lib.rs sha256 " + "0" * 64], t)]
    check("PLANT: a sha in NO commit is REFUSED, with a Next line", len(plant) == 1 and "differs from the toolset file's " + h(V2) in plant[0] and "Next: write lib.rs sha256 " + h(V2) in plant[0], str(plant))
    uncommitted = [declare.fmt(x) for x in transducer.update_findings(p, [f"lib.rs sha256 {h(V3)}"], t)]
    check("PLANT: the uncommitted working-tree content is not a source in a git toolset (REFUSED)", len(uncommitted) == 1, str(uncommitted))
    (t / "new.rs").write_bytes(V1)   # never committed
    fresh = [declare.fmt(x) for x in transducer.update_findings(p, [f"new.rs sha256 {h(V1)}"], t)]
    check("PLANT: a file that no commit holds is REFUSED (the working tree is not a source)", len(fresh) == 1 and "is in no commit" in fresh[0] and "Next:" in fresh[0], str(fresh))
print("test_pin_history: " + ("FAILED" if bad else "all passed"))
sys.exit(1 if bad else 0)
