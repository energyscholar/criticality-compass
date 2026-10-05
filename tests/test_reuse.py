"""test_reuse - content-keyed result reuse in detect.run (plan 0876). Run in a COPY of the tree (the stored results are rewritten there).
1. an unchanged key returns the stored result and measures nothing; the file's bytes do not move
2. a mutated instrument module changes the code hash, so the key misses and `run` re-measures
3. a table edited by one byte: the same input under that set is a re-verdict (derived_from set, nothing measured), never the stale stored verdict
A result with no code hash has no key and is always measured."""
import json
import shutil
import stat
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
bad = []
INPUT, SET, FORK = "b7-at-line", "v01-rules", "t-reuse"
DRIVER = """
import json, sys
sys.path[:0] = [sys.argv[1] + "/cc", sys.argv[1] + "/cc/instruments"]
import detect
calls = []
real = detect.measure
detect.measure = lambda *a: calls.append(1) or real(*a)
res = detect.run(sys.argv[2], sys.argv[3], True)
print(json.dumps({"calls": len(calls), "derived_from": res["derived_from"], "code_hash": res["code_hash"], "read": res["read"], "signature": res["signature"]}))
"""


def check(name, ok, why=""):
    print(("ok   " if ok else "FAIL ") + name + ("" if ok else f": {why}"))
    if not ok:
        bad.append(name)


with tempfile.TemporaryDirectory() as t:
    repo = Path(t) / "repo"
    shutil.copytree(ROOT, repo, ignore=shutil.ignore_patterns(".git", "__pycache__"))
    for q in [repo, *repo.rglob("*")]:
        q.chmod(q.stat().st_mode | stat.S_IWUSR)

    def run(name, tables):
        r = subprocess.run([sys.executable, "-c", DRIVER, str(repo), name, tables], capture_output=True, text=True)
        return json.loads(r.stdout.splitlines()[-1]) if r.returncode == 0 else {"error": r.stderr[-400:]}

    def file_sha(rid):
        return subprocess.run(["sha256sum", str(repo / "results" / f"{rid}.json")], capture_output=True, text=True).stdout.split()[0]
    rid = f"{INPUT}@{SET}"
    first = run(INPUT, SET)
    check("a stored result with no code hash has no key: run measures", first.get("calls") == 1, str(first)[:300])
    before = file_sha(rid)
    again = run(INPUT, SET)
    check("an unchanged key returns the stored result: nothing measured, same signature, file bytes unchanged",
          again.get("calls") == 0 and again["signature"] == first["signature"] and file_sha(rid) == before, str(again)[:300])
    shutil.copytree(repo / "tables" / SET, repo / "tables" / FORK)
    for q in (repo / "tables" / FORK).iterdir():
        q.chmod(q.stat().st_mode | stat.S_IWUSR)
    derived = run(INPUT, FORK)
    check("a table set that differs only in tables/*: re-verdict from the stored result, nothing measured",
          derived.get("calls") == 0 and derived["derived_from"] == rid and derived["signature"] == first["signature"], str(derived)[:300])
    f = repo / "tables" / FORK / "verdict.toml"
    f.write_text(f.read_text() + "\n# planted: one edited table\n")
    edited = run(INPUT, FORK)
    key = f"tables/{FORK}/verdict.toml"
    check("one edited byte of a table: the input under that set is a re-verdict whose read names the edited table, never the stale stored result",
          edited.get("calls") == 0 and edited["derived_from"] == rid and edited["read"][key] != derived["read"][key], str(edited)[:300])
    inst = repo / "cc" / "instruments" / "across.py"
    inst.write_text(inst.read_text() + "\n# planted: one edited instrument module\n")
    mutated = run(INPUT, SET)
    check("a mutated instrument module changes the key: run re-measures and records the new code hash",
          mutated.get("calls") == 1 and mutated["code_hash"] != first["code_hash"], str(mutated)[:300])
print("test_reuse: " + ("FAILED" if bad else "all passed"))
sys.exit(1 if bad else 0)
