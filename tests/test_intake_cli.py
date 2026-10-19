"""test_intake_cli - plan 1139: the intake from the command line on synthetic data. Each check was seen RED under a stated mutation (the
plan-1139 report lists them).
 1. `bin/cc intake synth`: the same seed writes a byte-identical bank (and truth file); a different seed writes a different bank.
 2. The bank holds no truth file, and no stage opens the truth directory: every access-log line is a loader read inside the bank.
 3. Each LIVE stage refuses a planted bad bank with its named reason: a repeated T (S5 FAST_VALUE_REPEATED), two files with one h
    (S5 CURVE_REPEATED), a wrong header (first file: S4 COLUMNS_DIFFER; a later file: S5 FILE_DIFFERS_FROM_FIRST), bytes changed after
    their pin (S3 PIN_MISMATCH).
 4. An unsealed run reaches the data stages and reports UNSEALED; a run after an edit that follows the seal reports SEALED_THEN_EDITED.
 5. docs/INTAKE-QUICKSTART.md's command block is the plan's sequence, and it runs clean in a copy of the Compass with the edit step done
    by applying the quickstart's filled example.
    Plan 1160 P5: the run now passes S7, S8 and S9 (interval STATED, tiering STATED; CANDIDATE_BRACKET) and is PRIMARY_INCOMPLETE missing
    only confirmation. Seen RED: TIERING["STATED"] made REPLICATES in cc/intake_feasible.py: the S7-S9 check FAILS.
Tests 2 to 5 run in one copy of the Compass (its code, tables and docs; not .git, results, benchmark, fixtures, data), never in this tree."""
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CC = str(ROOT / "bin" / "cc")
bad = []


def check(name, ok, why=""):
    print(("ok   " if ok else "FAIL ") + name + ("" if ok else f": {why}"))
    if not ok:
        bad.append(name)


def cc(*args, cwd=ROOT):
    return subprocess.run([CC, *args], capture_output=True, text=True, cwd=cwd)


def tree(d):
    """{relative path: bytes} of every file under d."""
    return {q.relative_to(d).as_posix(): q.read_bytes() for q in sorted(Path(d).rglob("*")) if q.is_file()}


# ---- 1. the synthetic bank is a function of its seed
with tempfile.TemporaryDirectory() as tmp:
    runs = {name: cc("intake", "synth", "b", "--seed", seed, "--out", str(Path(tmp) / name)) for name, seed in (("a", "1"), ("a2", "1"), ("c", "2"))}
    check("1. synth exits 0 three times", all(r.returncode == 0 for r in runs.values()), str([r.stdout + r.stderr for r in runs.values()])[:400])
    a, a2, c = (tree(Path(tmp) / n) for n in ("a", "a2", "c"))
    check("1. the bank holds 9 curves and MANIFEST.json, the truth sits beside it", sorted(a) == sorted([f"b/curve_{i:03d}.csv" for i in range(9)] + ["b/MANIFEST.json", "b-TRUTH/truth.json"]), str(sorted(a)))
    check("1. the same seed writes a byte-identical bank and truth file", a == a2, str([k for k in a if a[k] != a2.get(k)])[:200])
    check("1. a different seed writes a different bank", all(a[k] != c[k] for k in a if k.endswith(".csv")), str([k for k in a if k.endswith(".csv") and a[k] == c[k]]))

# ---- 5. the quickstart is the sequence the plan names, and it runs
SEQUENCE = """bin/cc intake explain
bin/cc intake synth demo1 --seed 1
bin/cc new intake demo1 --from-synth demo1
#   edit declarations/demo1/intake.toml: replace each remaining TODO (the quickstart shows a filled example)
bin/cc intake lint demo1
bin/cc intake seal demo1 --universe scratch/intake-synth/demo1 --author "<name>" --as human --unconfirmed    # optional
bin/cc intake run demo1
cat declarations/demo1/intake-report.md"""
QS = (ROOT / "docs" / "INTAKE-QUICKSTART.md").read_text()
blocks = re.findall(r"```(\w*)\n(.*?)\n```", QS, re.S)
check("5. the quickstart's first block is the plan's command sequence, line for line", blocks[0] == ("", SEQUENCE), blocks[0][1][:300])
FILLED = dict(blocks)["toml"]


def fill(path):
    """Apply the quickstart's filled example: each `key = value` under a section replaces that section's `key = "TODO"` line; a key with no
    TODO line goes after the last line replaced in its section."""
    lines, sec, last = path.read_text().splitlines(), "", {}
    want = [(sec, ln) for ln in FILLED.splitlines() for sec in [ln if ln.startswith("[") else sec] if not ln.startswith("[")]
    for sec, ln in want:
        key = ln.split("=")[0].strip()
        heads = [i for i, x in enumerate(lines) if x.strip() == sec]
        end = next((i for i in range(heads[0] + 1, len(lines)) if lines[i].startswith("[")), len(lines))
        hit = [i for i in range(heads[0] + 1, end) if lines[i].split("=")[0].strip() == key and '"TODO"' in lines[i]]
        at = hit[0] if hit else last[sec] + 1
        lines[at:at + bool(hit)] = [ln]
        last[sec] = at
    path.write_text("\n".join(lines) + "\n")


def slurp(p):
    """A file's text, or "" when it is absent: a stage that crashed or was withheld leaves no file, and the check that reads it fails by name."""
    return Path(p).read_text() if Path(p).is_file() else ""


def copy(dst):
    shutil.copytree(ROOT, dst, ignore=shutil.ignore_patterns(".git", "__pycache__", "results", "benchmark", "fixtures", "data", "scratch", "demo*", "bad*"))


def sh(line, cwd):
    return subprocess.run(["bash", "-c", line], capture_output=True, text=True, cwd=cwd, env={k: v for k, v in os.environ.items() if not k.startswith("CC_")})


with tempfile.TemporaryDirectory() as tmp:
    w = Path(tmp) / "cc"
    copy(w)
    seq = [{True: lambda ln=ln: (ln, fill(w / "declarations" / "demo1" / "intake.toml")), False: lambda ln=ln: (ln, sh(ln, w))}[ln.startswith("#")]()
           for ln in SEQUENCE.splitlines()]
    runs = {ln: r for ln, r in seq if r is not None}
    check("5. every command of the sequence exits 0", all(r.returncode == 0 for r in runs.values()), str({k: r.stdout[-300:] + r.stderr[-300:] for k, r in runs.items() if r.returncode})[:900])
    lint, report = runs["bin/cc intake lint demo1"].stdout, runs["cat declarations/demo1/intake-report.md"].stdout
    check("5. lint passes FORMAT and (plan 1160 P1) CHOICES", lint.startswith("S0 EXECUTED, PASS.") and "\nS1 EXECUTED, PASS." in lint, lint[:300])
    check("5. S3, S4, S5 and (plan 1160 P4) S6 EXECUTED PASS", all(f"- **{s}** (LIVE): EXECUTED, PASS." in report for s in ("S3 SOURCE_INTEGRITY", "S4 SHAPE", "S5 CENSUS", "S6 ADMISSIBILITY"))
          and "S6 ADMISSIBILITY** (LIVE): EXECUTED, PASS. ADMITTED_ON_LOGGED_PATHS_ONLY" in report, report[:600])
    check("5. the census label says 9 curves, MISALIGNED", "Sampling: 9 curves;" in report and report.count("MISALIGNED") == 1 and "MISALIGNED; curves_with_slow = 9" in report, report[:300])
    check("5. (plan 1160 P5) S7, S8 and S9 EXECUTED PASS", all(f"- **{s}** (LIVE): EXECUTED, PASS." in report for s in ("S7 INTERVAL_FEASIBILITY", "S8 RESOLUTION_AND_IDENTIFIABILITY", "S9 ALTERNATIVE_INTAKE"))
          and "tiering = STATED" in report and "max_bracket = CANDIDATE_BRACKET" in report, report[:1500])
    check("5. seal status SEALED and PRIMARY_INCOMPLETE missing only confirmation (plan 1160 P5: was the S7..S9 stubs)", "Seal status** (advisory; sealing is recommended and not enforced): SEALED." in report
          and "PRIMARY verdict: PRIMARY_INCOMPLETE**. Missing: confirmation" in report, report[:900])

    # ---- 2. the truth stays outside: the bank holds none, and every logged access is a loader read of a bank file
    bank, log = w / "scratch" / "intake-synth" / "demo1", w / "declarations" / "demo1" / "access.log"
    check("2. the bank holds no truth file and no file names h_star", "truth.json" not in tree(bank) and not any(b"h_star" in v for v in tree(bank).values()), str(sorted(tree(bank))))
    acc = [json.loads(x) for x in slurp(log).splitlines()]
    check("2. the access log holds 9 loader reads and nothing else; none of the truth directory",
          len(acc) == 9 and all(a["route"] == "loader" and Path(a["path"]).parent == bank.resolve() for a in acc), str([(a["route"], a["path"]) for a in acc if a["route"] != "loader" or "TRUTH" in a["path"]])[:400])

    # ---- 4. advisory seal: an unsealed run reaches the data stages; an edit after the seal is reported
    sh("bin/cc new intake demo2 --from-synth demo1", w)
    fill(w / "declarations" / "demo2" / "intake.toml")
    un = (sh("bin/cc intake run demo2", w), slurp(w / "declarations" / "demo2" / "intake-report.md"))[1]
    check("4. an unsealed run reports UNSEALED and its data stages executed", "): UNSEALED." in un and "- **S5 CENSUS** (LIVE): EXECUTED, PASS." in un, un[:700])
    with open(w / "declarations" / "demo1" / "intake.toml", "a") as f:
        f.write("# an edit after the seal\n")
    ed = (sh("bin/cc intake run demo1", w), slurp(w / "declarations" / "demo1" / "intake-report.md"))[1]
    check("4. a run after an edit that follows the seal reports SEALED_THEN_EDITED", "): SEALED_THEN_EDITED." in ed, ed[:700])

    # ---- 3. planted bad banks, each refused by its stage with its named reason
    def planted(ident, before, after):
        """A copy of bank demo1 as <ident>, spoiled by `before(bank dir)`, declared --from-synth and filled, run, spoiled by
        `after(bank dir)` (the bytes changed after their pin), and run again. Returns the last report."""
        b = w / "scratch" / "intake-synth" / ident
        shutil.copytree(bank, b)
        before(b)
        sh(f"bin/cc new intake {ident} --from-synth {ident}", w)
        fill(w / "declarations" / ident / "intake.toml")
        sh(f"bin/cc intake run {ident}", w)
        after(b)
        sh(f"bin/cc intake run {ident}", w)
        return slurp(w / "declarations" / ident / "intake-report.md")

    def edit(name, f):
        return lambda b: (b / name).write_bytes(f((b / name).read_bytes()))

    def repeat_row(data):   # the second data row twice: T stays ascending (non-decreasing) and one T repeats
        ls = data.splitlines(keepends=True)
        return b"".join(ls[:2] + ls[1:])

    def same_h(b):
        m = json.loads((b / "MANIFEST.json").read_text())
        m["files"][1]["h"] = m["files"][0]["h"]
        (b / "MANIFEST.json").write_text(json.dumps(m))

    keep = lambda b: None
    cases = [("3. a repeated T: S5 refuses FAST_VALUE_REPEATED", "badt", edit("curve_003.csv", repeat_row), keep, "S5 CENSUS** (LIVE): EXECUTED, REFUSE FAST_VALUE_REPEATED."),
             ("3. two files with one h: S5 refuses CURVE_REPEATED", "badh", same_h, keep, "S5 CENSUS** (LIVE): EXECUTED, REFUSE CURVE_REPEATED."),
             ("3. a wrong header in the first file: S4 refuses COLUMNS_DIFFER", "badhead", edit("curve_000.csv", lambda x: x.replace(b"T,C,sigma", b"T,Q,sigma", 1)), keep,
              "S4 SHAPE** (LIVE): EXECUTED, REFUSE COLUMNS_DIFFER."),
             ("3. a wrong header in a later file: S5 refuses FILE_DIFFERS_FROM_FIRST", "badhead2", edit("curve_005.csv", lambda x: x.replace(b"T,C,sigma", b"T,C,err", 1)), keep,
              "S5 CENSUS** (LIVE): EXECUTED, REFUSE FILE_DIFFERS_FROM_FIRST."),
             ("3. bytes changed after their pin: S3 refuses PIN_MISMATCH", "badpin", keep, edit("curve_002.csv", lambda x: x + b"3.5000,0.5,0.03\n"),
              "S3 SOURCE_INTEGRITY** (LIVE): EXECUTED, REFUSE PIN_MISMATCH.")]
    for name, ident, before, after, want in cases:
        got = planted(ident, before, after)
        check(name, want in got and "PRIMARY verdict: PRIMARY_REFUSED_AT" in got, "\n".join(x for x in got.splitlines() if "EXECUTED" in x or "verdict" in x)[:700])

print("test_intake_cli: " + ("FAILED " + "; ".join(bad) if bad else "all passed"))
sys.exit(1 if bad else 0)
