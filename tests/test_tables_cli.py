"""test_tables_cli - bin/cc authoring, run and freeze commands, as a subprocess inside a temp copy of the repo."""
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
import frozen  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent


from lib import bad, check  # noqa: E402


with tempfile.TemporaryDirectory() as t:
    repo = Path(t) / "repo"
    shutil.copytree(ROOT, repo, ignore=shutil.ignore_patterns(".git", "__pycache__"))
    frozen.thaw(repo)   # the copy only; the live tree is frozen

    def cc(*args):
        r = subprocess.run([sys.executable, str(repo / "bin" / "cc"), *args], capture_output=True, text=True, cwd=repo)
        return r.returncode, r.stdout + r.stderr

    rc, out = cc("tables", "fork", "verdict-x-rules", "t1")
    want = "Next: edit tables/t1/verdict.toml, then bin/cc validate, then bin/cc run --all --tables t1"
    check("fork copies the set and prints its Next line", rc == 0 and want in out, out)
    writable = os.access(repo / "tables/t1/verdict.toml", os.W_OK) and os.access(repo / "tables/t1", os.W_OK)
    check("the fork is writable", writable)
    rc, out = cc("tables", "fork", "verdict-x-rules", "t1")
    check("fork refuses an existing target",
          rc == 1 and "tables/t1 already exists." in out and "Next: pick another name" in out, out)
    rc, out = cc("tables", "split", "t1", "--column", "stability", "--value", "CROSSING",
                 "--verdict", "REFUSE-WALKING-UNCONFIRMED")
    check("split touches 14 rows and the copy stays a partition",
          rc == 0 and "touched 14 rows (19 rows now)" in out and "verdict.toml: clean" in out, out)
    rc, out = cc("validate")
    check("the split copy validates clean", rc == 0 and "validate: clean" in out, out)
    rc, out = cc("tables", "drop", "t1")
    check("drop removes an unfrozen set", rc == 0 and not (repo / "tables/t1").exists(), out)
    rc, out = cc("tables", "drop", "v01-rules")      # the default set (plan 0864 R10b: was verdict-x-rules)
    check("drop refuses the default set",
          rc == 1 and "is the default rulebook" in out and "Next:" in out and (repo / "tables/v01-rules").is_dir(), out)

    rc, out = cc("new", "case", "potts-q4")
    rc2, out2 = cc("validate")
    todo = "cases/potts-q4.toml:family: still TODO\n  Next: replace it with a short description of the model"
    check("new case then validate names its TODOs with Next lines", rc == 0 and rc2 == 1 and todo in out2, out2)
    check("new case writes the breaker_verdict field", 'breaker_verdict = ""' in (repo / "cases/potts-q4.toml").read_text())
    rc, out = cc("new", "case", "potts-q4")
    check("new case refuses an existing file", rc == 1 and "already exists" in out and "Next:" in out, out)

    rc, out = cc("new", "input", "w2b", "--like", "w2-potts", "--points", "6,7")
    m = (repo / "inputs/w2b/m.toml").read_text()
    check("new input --points writes the renamed blocks",
          rc == 0 and 'id = "w2b"' in m and 'path = "w2/q6-L27-random.npz"' in m
          and 'path = "w2/q7-L243-ordered.npz"' in m, out + m[:300])
    fx = tempfile.mkdtemp(dir=t)   # plan 1273 A2: a fixture data root, so the content check runs on every host
    (Path(fx) / "fixture").mkdir()
    rc, out = cc("validate", "--data-root", fx)
    gone = [f"w2/q{q}-L{s}-{st}.npz" for q in (6, 7) for s in (27, 81, 243) for st in ("random", "ordered")]
    check("validate names every missing data file (12: six per new point)",
          rc == 1 and all(f"{g} does not exist under the data root" in out for g in gone), out)
    rc, out = cc("new", "input", "w2c", "--like", "w2-potts", "--points", "6", "--pattern-point", "2")
    m = (repo / "inputs/w2c/m.toml").read_text()
    check("a pattern that occurs twice in a file name is not guessed",
          '"TODO"   # was w2/q2-L27-random.npz' in m, m[-400:])
    rc, out = cc("new", "input", "w2d", "--like", "w2-potts", "--instruments", "across")
    rc2, out2 = cc("validate")
    left = [f for f in ("w2d/m.toml:two_start", "inputs/w2d/m.toml:relations", "w2d/m.toml:eps") if f in out2]
    check("--instruments drops the tables no kept instrument needs", rc == 0 and not left, out + out2)
    rc, out = cc("new", "input", "w2e", "--like", "w2-potts", "--points", "6", "--data-dir", "w2x",
                 "--label-format", "d{label}-L{size}-{start}.npz", "--add-instrument", "needle")
    m = (repo / "inputs/w2e/m.toml").read_text()
    check("--data-dir and --label-format retarget every block", rc == 0 and 'path = "w2x/d6-L27-random.npz"' in m
          and 'path = "w2x/d6-L243-ordered.npz"' in m and "w2/q" not in m, out + m[-300:])
    rc, out = cc("new", "input", "w2f", "--like", "w2-potts", "--label-format", "{bogus}")
    check("--label-format refuses an unknown field", rc == 1 and "{label}, {size} and {start}" in out, out)
    rc, out = cc("validate")
    todo = [f"inputs/w2e/m.toml:{k}: still TODO\n  Next: " for k in (
        "relations.matched.template", "sinks.ordered", "sinks.disordered", "eps.step", "eps.sink",
        "data.files[0].arrays.GL.key", "obtained.6")] + ['inputs/w2e/points.toml:points.6: still TODO\n  Next: write a case id']
    want_n = (m + (repo / "inputs/w2e/points.toml").read_text() + (repo / "inputs/w2e/transducer.toml").read_text()).count('"TODO"')   # plan 0883: + the transducer file's TODOs
    got_n = len([x for x in out.splitlines() if x.startswith("inputs/w2e/") and "still TODO" in x])
    check("--add-instrument writes TODOs that validate names, each with a Next line",
          rc == 1 and want_n == got_n > 15 and all(t in out for t in todo) and "obtained.6: still TODO\n  Next: write one of: truth" in out, out[:900])
    rc, out = cc("new", "instrument", "foo")
    rc2, out2 = cc("validate")
    check("new instrument writes a template and a stub, and names the checks.toml line",
          rc == 0 and 'checks.toml [roles].maths: "cc/instruments/foo.py"' in out and "TODO-STAGE" in (repo / "cc/instruments/foo.py").read_text()
          and "instruments/foo.toml:unit: still TODO" in out2, out + out2[:400])
    for bad_id, why in (("door", "shadow"), ("Foo", "not an instrument id"), ("foo", "already exists")):
        rc, out = cc("new", "instrument", bad_id)
        check(f"new instrument refuses '{bad_id}'", rc == 1 and why in out and "Next:" in out, out)
    rc, out = cc("run", "w2-potts", "--dry")
    check("run is refused while an instrument has findings",
          rc == 1 and out.startswith("REFUSED: the instrument registry has findings.") and "instruments/foo.toml" in out, out)
    (repo / "instruments/foo.toml").write_text((repo / "instruments/across.toml").read_text().replace('"across"', '"foo"'))
    ck = repo / "checks.toml"
    ck.write_text(ck.read_text().replace('"cc/instruments/two_start.py",', '"cc/instruments/two_start.py", "cc/instruments/foo.py",'))
    rc, out = cc("run", "w2-potts", "--dry")
    check("run is refused while the stub still holds TODO-STAGE", rc == 1 and "still holds the TODO-STAGE marker" in out, out)
    (repo / "cc/instruments/foo.py").write_text((repo / "cc/instruments/across.py").read_text())
    rc, out = cc("run", "w2-potts", "--dry")
    check("run is accepted once the instrument validates", rc == 0 and "run w2-potts@" in out, out[:600])
    rc, out = cc("data", "add", "w2-potts")
    check("data add refuses to overwrite a manifest", rc == 1 and "already exists" in out and "Next:" in out, out)
    rc, out = cc("tables", "bogus")
    check("an unknown tables subcommand has a Next line", rc == 1 and "Next:" in out, out)
    rc, out = cc("run", "w2")
    check("run names the inputs when the name is wrong",
          rc == 1 and "no input 'w2'. Inputs:" in out and "Next:" in out, out)

    # plan 0881 P2.7: the measured input has NO frozen or keyed result under any set (c2-bc-two-start has frozen v03 results, so its run was a re-verdict)
    cc("tables", "fork", "verdict-x-rules", "t2")    # the live verdict-x-rules is already frozen
    rid = "x3-clock6-3@t2"
    frozen_files = json.loads((repo / "FROZEN.json").read_text())["files"]
    for q in (repo / "results").glob("x3-clock6-3@*"):   # plan 0876 B: a keyed result under another set would make this run a re-verdict (JSON only, vectors named in the parent's NPZ); the test is of a MEASURED run
        if f"results/{q.name}" not in frozen_files:
            q.unlink()
    rc, out = cc("run", "x3-clock6-3", "--tables", "t2")
    check("run writes the result JSON and NPZ",
          rc == 0 and (repo / f"results/{rid}.json").is_file() and (repo / f"results/{rid}.npz").is_file(), out)
    rc, out = cc("freeze", rid)
    check("freeze freezes the result, what it read, and the table set",
          rc == 0 and out.startswith("froze ") and "1 dir for" in out, out)
    rc, out = cc("run", "x3-clock6-3", "--tables", "t2")
    refused = f"REFUSED: results/{rid}.json is frozen (a frozen result never changes)."
    nxt = ("Next: bin/cc tables fork t2 <new-name>, edit tables/<new-name>/verdict.toml, "
           "then bin/cc run x3-clock6-3 --tables <new-name>")
    check("a frozen result id is refused with its Next line", rc == 1 and refused in out and nxt in out, out)
    rc, out = cc("run", "x3-clock6-3", "--tables", "t2", "--dry")
    check("a dry run of a frozen id writes nothing and is allowed", rc == 0 and "dry: nothing written" in out, out)
    rc, out = cc("tables", "drop", "t2")
    check("a frozen set is never dropped", rc == 1 and "Next:" in out, out)
    v = repo / "tables/verdict-x-rules/verdict.toml"
    frozen.thaw(v)
    v.write_text(v.read_text() + "\n# edited after it was frozen\n")
    rc, out = cc("run", "w2-potts", "--dry")
    check("an edited frozen table is refused (C7)",
          rc == 1 and "REFUSED: tables/verdict-x-rules/verdict.toml changed after it was frozen." in out
          and "Next: git checkout -- tables/verdict-x-rules/verdict.toml" in out, out)
    for p in [repo, *repo.rglob("*")]:
        p.chmod(0o755 if p.is_dir() else 0o644)
print("".join(f"FAILED {b}\n" for b in bad) + "test_tables_cli: " + ("FAILED " + str(len(bad)) if bad else "all passed"))
sys.exit(1 if bad else 0)
