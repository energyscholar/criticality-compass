"""test_data_root - the data root is moved by --data-root > CC_DATA_ROOT > cc.toml [data] root, and moving it moves NO measurement (plan 0929 A4).
(1) the precedence is a table (pure, no data);  (2) one locked input measured from the declared root and from a copy of its data files in a
scratch root: byte-identical measure_hash, `read` map and verdict cells, and the header records WHO chose the root;  (3) `view.stale` finds a stored
result's files at the moved root (and refuses when the moved root is empty);  (4) the comparison can fail: a root-sensitive hash is flagged.
Data-dependent: needs CC_DATA_ROOT to name the populated data (cc.toml [check] needs_data); cc.toml [data] holds only the NAME (plan 0985)."""
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path[:0] = [str(ROOT / "cc"), str(ROOT / "cc" / "instruments")]
import schema  # noqa: E402

bad = []
INPUT = "w2-potts-2"


def check(name, ok, why=""):
    print(("ok   " if ok else "FAIL ") + name + ("" if ok else f": {why}"))
    if not ok:
        bad.append(name)


cfg = tomllib.loads((ROOT / "cc.toml").read_text())
home = lambda s: os.path.expanduser(s)  # noqa: E731
check("precedence: flag over env over cc.toml",
      schema.resolve_data_root(cfg, "/f", "/e") == (Path("/f"), "flag") and schema.resolve_data_root(cfg, None, "/e") == (Path("/e"), "env")
      and schema.resolve_data_root(cfg, None, "") == (ROOT / "data", "default"))

CHILD = """
import json, sys
sys.path[:0] = [sys.argv[1] + "/cc", sys.argv[1] + "/cc/instruments"]
import detect, view
import glob
st = json.loads(open(sorted(glob.glob(sys.argv[1] + "/results/" + sys.argv[2] + "@*.json"))[0]).read())   # a stored result of this input, whatever its set
out = {"stale": view.stale(st)}
try:
    res, how = detect.run_keyed(sys.argv[2], "v01-rules", False, reuse=False)
    out.update(mh=res["measure_hash"], read=res["read"], sig=[(s["point"], s["verdict"]) for s in res["signature"]], src=res.get("data_root_source"))
except Exception as e:
    out["err"] = repr(e)[:200]
print(json.dumps(out))
"""


def measure(env_root=None, flag=None):
    env = {k: v for k, v in os.environ.items() if k != "CC_DATA_ROOT"}
    if env_root:
        env["CC_DATA_ROOT"] = env_root
    code = CHILD if flag is None else CHILD.replace("import detect, view", f"import schema; schema.DATA_ROOT_FLAG = {flag!r}\nimport detect, view")
    r = subprocess.run([sys.executable, "-c", code, str(ROOT), INPUT], capture_output=True, text=True, env=env, cwd=ROOT)
    return json.loads(r.stdout) if r.returncode == 0 else {"err": r.stderr[-400:], "stale": "child failed"}


def same(a, b):
    """What must not move when only the root moves."""
    return all(a[k] == b[k] for k in ("mh", "read", "sig"))


if not os.environ.get("CC_DATA_ROOT"):
    print("test_data_root: REFUSED: CC_DATA_ROOT names no data\n  Next: CC_DATA_ROOT=<populated data root> bin/cc test test_data_root")
    sys.exit(1)
declared = Path(home(os.environ["CC_DATA_ROOT"]))
m = tomllib.loads((ROOT / "inputs" / INPUT / "m.toml").read_text())
with tempfile.TemporaryDirectory() as t:
    moved = Path(t) / "elsewhere" / "data"
    for rel in {b["path"] for b in m["data"]["files"]}:
        (moved / rel).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(declared / rel, moved / rel)
    base, env_, flag_ = measure(str(declared)), measure(str(moved)), measure(str(declared), str(moved))
    both = measure(str(Path(t) / "empty"), str(moved))   # the flag wins over an env that points at nothing
    check("measured from the root CC_DATA_ROOT names", "err" not in base, base.get("err", ""))
    check("moved by CC_DATA_ROOT: measure_hash, read map and verdict cells are byte-identical", "err" not in env_ and same(base, env_), env_.get("err", ""))
    check("moved by the flag: the same", "err" not in flag_ and same(base, flag_), flag_.get("err", ""))
    check("the flag wins over the env", "err" not in both and same(base, both), both.get("err", ""))
    check("the header records the source: env / env / flag / flag",
          (base.get("src"), env_.get("src"), flag_.get("src"), both.get("src")) == ("env", "env", "flag", "flag"), str((base.get("src"), env_.get("src"), flag_.get("src"))))
    check("a stored result's files are found at the moved root", env_.get("stale") is None and flag_.get("stale") is None, str(env_.get("stale")))
    empty = measure(str(Path(t) / "empty"))
    check("an empty moved root is not silently the declared one: nothing is measured from it, and a stored result is REFUSED as changed",
          "err" in empty and str(empty["stale"]).startswith("REFUSED: "), str(empty)[:200])
    # the comparison can fail: a hash that sees the root differs between the two roots
    assert "mh" in base and "mh" in env_, (base, env_)
    sensitive = lambda r, root: {**r, "mh": hashlib.sha256((r["mh"] + str(root)).encode()).hexdigest()}  # noqa: E731
    check("breaker: a root-sensitive hash is flagged by the comparison", not same(sensitive(base, declared), sensitive(env_, moved)))
print("test_data_root: " + ("FAILED " + ", ".join(bad) if bad else "ok"))
sys.exit(1 if bad else 0)
