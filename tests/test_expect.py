"""test_expect - plan 0884 amendment 5: a refusal is a declared reading, so the gate scores it rather than going red.
A scratch copy of the repo gets a planted 64-frame island-table input (refused at the block floor) with one file holding a 0.0 moment (a reader refusal): two refusal sentences.
(1) undeclared, both refusals are findings (validate red, as before); (2) [expect] with the sentences file written from CC's OWN output: ONE line 'refused as declared (2 sentences)', validate clean;
(3) one sentence removed from the file => a finding; (4) one sentence added => a finding; (5) one sentence reworded => a finding; (6) the 3000-frame record (accepted) declared refused => a finding
(the positive control: a gate that did not fire); (7) a malformed [expect] is a finding; (8) `bin/cc run` of a declared-refused input still REFUSES (the raw validate is run's gate).
SEEN RED: (2) is re-run against a scratch copy whose score_expected ignores [expect]: validate goes red as in (1); and against a copy whose comparison accepts anything: (3)-(6) go green (the breakers can fail)."""
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
import numpy as np

ROOT = Path(__file__).resolve().parent.parent
bad = []


def check(name, ok, why=""):
    print(("ok   " if ok else "FAIL ") + name + ("" if ok else f": {why}"))
    if not ok:
        bad.append(name)


S = 27
HEAD = '''schema = 1
kind = "input"
id = "planted"
instruments = ["report"]

[obtained]
"ord" = "observed"
"rnd" = "observed"

[axes]
point = ["ord", "rnd"]
size = [27]
starts = ["asgrown"]
main_start = "asgrown"

[observable]
name = "g1-occupied"
definition = "a planted record"
levels = [2]
final_size = 9
level_floor = 0

[block_map]
name = "majority-occupied3"
factor = 3
keeps = "the sign of the local majority over occupied islands"
discards = "the magnitude"
limited = "none"

[windows]
side = 27
origin = "extent-min"
discards = "nothing: the planted grid is the window"

[sinks]
ordered = 1.0
disordered = 0.0
'''
BLOCK = '\n[interval]\nmethod = "block"\ntau_declared = 3\nb = 9\nresamples = 40\nlevel = 0.95\nseed = 12345\nmin_blocks = 30\n'
GAMMA = '\n[interval]\nmethod = "gamma"\nlevel = 0.95\nwindow_s = 1.5\nwindow_max = 400\ndoor_z = 3.0\ntau_declared = 3\ntau_source = "planted: declared"\n'
CHAINS = '\n[interval]\nmethod = "chains"\nm = 10\nr = 2\nalpha = 0.021484375\nchain_root = "planted"\n'
TAIL = '\n[eps]\n\n[kernel]\nuses = []\n\n[data]\nformat = "island-table-v1"\n'
COUP = 'schema = 1\nkind = "couplings"\nid = "planted"\nnames = ["T"]\nprobes = []\n'
TRANS = '''schema = 1
kind = "record"
id = "planted"

[record]
apparatus = "a planted table"
preparation = "none"
observation = "one frame = the +-1 moment of every island"
authors_projection = "none: planted"
source = "tests/test_expect.py"

[reduction]
name = "per-locus mean of the occupied-pair g1 of the declared block states"
keeps = "the typical value of the observable at the locus"
discards = "the frame order"

[interval]
role = "projection C: places the reading's sign cell against its declared margin; never an operator input"
keeps = "the position of the interval ends among the cuts -eps, 0, +eps"
discards = "the shape of the resampled distribution"
'''


def table(path, frames):
    """a 27 x 27 fully listed island grid; frames is [n, 729] of +-1"""
    rr, cc = np.divmod(np.arange(S * S), S)
    with open(path, "w") as f:
        for i in range(S * S):
            f.write(f"{rr[i] + 3}.0,{cc[i] + 5}.0," + ",".join(f"{v:.1f}" for v in frames[:, i]) + "\n")


def files(blocks):
    return "".join(f'\n[[data.files]]\npoint = "{pt}"\nsize = 27\nstart = "asgrown"\npath = "planted/{name}"\n{extra}arrays.GL = {{ key = "csv" }}\n' for pt, name, extra in blocks)



tmp = Path(tempfile.mkdtemp(prefix="expect-scratch-"))
try:
    data = tmp / "data"
    (data / "planted").mkdir(parents=True)
    rng = np.random.default_rng(885)
    long_ = {"ord": np.ones((3000, S * S)), "rnd": rng.choice([-1.0, 1.0], size=(3000, S * S))}
    for pt, a in long_.items():
        table(data / "planted" / f"{pt}-3000.csv", a)
        table(data / "planted" / f"{pt}-64.csv", a[:64])
    zero = long_["rnd"][:64].copy()
    zero[3, 10] = 0.0
    table(data / "planted" / "rnd-zero.csv", zero)
    env = {**os.environ, "CC_DATA_ROOT": str(data)}
    repo = tmp / "r"
    shutil.copytree(ROOT, repo, ignore=shutil.ignore_patterns(".git", "__pycache__", "rust", "results"))
    (repo / "results").mkdir()
    fz = json.loads((repo / "FROZEN.json").read_text())
    fz["files"] = {k: v for k, v in fz["files"].items() if not k.startswith("results/")}
    (repo / "FROZEN.json").write_text(json.dumps(fz, indent=1) + "\n")
    (repo / "inputs" / "planted").mkdir()
    (repo / "inputs" / "planted" / "transducer.toml").write_text(TRANS)
    (repo / "inputs" / "planted" / "couplings.toml").write_text(COUP)
    (repo / "inputs" / "planted" / "points.toml").write_text('schema = 1\nkind = "points"\ninput = "planted"\n\n[points]\n"ord" = "none"\n"rnd" = "none"\n')
    (repo / "expected" / "refusals").mkdir(exist_ok=True)
    for q in (repo / "expected" / "refusals").glob("planted*"):
        q.unlink()
    SENT = repo / "expected" / "refusals" / "planted.txt"
    EXPECT = '\n[expect]\noutcome = "refused"\nsentences = "expected/refusals/planted.txt"\n'

    def cc(*a, cwd=None):
        r = subprocess.run([sys.executable, str((cwd or repo) / "bin" / "cc"), *a], cwd=cwd or repo, env=env, capture_output=True, text=True)
        return r.returncode, r.stdout + r.stderr

    def declare(text, blocks, where=repo):
        (where / "inputs" / "planted" / "m.toml").write_text(text + files(blocks))
        pins = "".join(f'"planted/{b[1]}" = "{hashlib.sha256((data / "planted" / b[1]).read_bytes()).hexdigest() if (data / "planted" / b[1]).is_file() else "0" * 64}"\n' for b in sorted(set(blocks), key=lambda x: x[1]))
        (where / "fixtures" / "data").mkdir(parents=True, exist_ok=True)
        (where / "fixtures" / "data" / "planted.toml").write_text('schema = 1\nkind = "data-manifest"\ninput = "planted"\n\n[files]\n' + pins)

    def validate(where=repo):
        return cc("validate", "--input", "planted", "--tables", "v08-rules", cwd=where)

    L64 = [("ord", "ord-64.csv", ""), ("rnd", "rnd-zero.csv", "")]
    L3000 = [("ord", "ord-3000.csv", ""), ("rnd", "rnd-3000.csv", "")]

    # (1) undeclared: both refusals are findings
    declare(HEAD + BLOCK + TAIL, L64)
    rc, o = validate()
    own = [ln for ln in o.splitlines() if ln.startswith("inputs/planted/")]
    check("undeclared: the reader refusal and the floor refusal are both findings, validate red", rc == 1 and len(own) == 2 and "validate: 2 findings" in o, o[:600])
    SENT.write_text("".join(ln + "\n" + nx + "\n" for ln, nx in zip(own, [x for x in o.splitlines() if x.startswith("  Next")])))   # CC's own output, two lines per sentence
    good = SENT.read_text()

    # (2) declared: ONE line, no finding
    declare(HEAD + BLOCK + EXPECT + TAIL, L64)
    rc, o = validate()
    check("declared: 'planted: refused as declared (2 sentences)', validate clean, rc 0", rc == 0 and "planted: refused as declared (2 sentences)" in o and o.rstrip().endswith("validate: clean") and "inputs/planted/m.toml:data" not in o, o[:600])
    rc, o = cc("run", "planted", "--tables", "v08-rules")
    check("a declared refusal still REFUSES a run (run keeps the raw validate)", rc == 1 and "moment 0.0 is not one of" in o and not list((repo / "results").glob("planted*")), o[:400])

    # (3)-(5) the file and the output differ by one sentence
    first = good.splitlines()
    SENT.write_text("\n".join(first[2:]) + "\n")
    rc, o = validate()
    check("one sentence REMOVED from the file: a finding (the output has a refusal the file no longer holds)", rc == 1 and "a refusal that is not in expected/refusals/planted.txt" in o and "refused as declared" not in o, o[:700])
    SENT.write_text(good + "inputs/planted/m.toml:interval.min_blocks: a sentence CC never produced\n  Next: nothing\n")
    rc, o = validate()
    check("one sentence ADDED to the file: a finding (a declared refusal that did not occur)", rc == 1 and "a declared refusal that did not occur: inputs/planted/m.toml:interval.min_blocks: a sentence CC never produced" in o and "refused as declared" not in o, o[:700])
    SENT.write_text(good.replace("is not one of [-1, 1]", "is not one of [-1, 1, 0]"))
    rc, o = validate()
    check("one sentence REWORDED: a finding", rc == 1 and "a declared refusal that did not occur" in o and "a refusal that is not in" in o and "refused as declared" not in o, o[:700])
    SENT.write_text(good)

    # (6) the positive control: an accepted record declared refused
    declare(HEAD + BLOCK + EXPECT + TAIL, L3000)
    rc, o = validate()
    check("the 3000-frame record (ACCEPTED) declared refused: a finding, not a pass", rc == 1 and "declared refused but the input was ACCEPTED" in o and "refused as declared" not in o, o[:600])

    # (7) a malformed [expect]
    declare(HEAD + BLOCK + '\n[expect]\noutcome = "accepted"\nsentences = "expected/refusals/planted.txt"\n' + TAIL, L64)
    rc, o = validate()
    check("a malformed [expect] (outcome 'accepted'): a finding, and nothing is declared refused", rc == 1 and "'accepted' is not an expected outcome" in o and "refused as declared" not in o, o[:600])

    # (9) amendment 6 F2: a NON-refusal defect listed in the sentence file is still a finding (a missing data file is not a refusal kind of cc.toml [refusal_fields])
    LMISS = [("ord", "ord-64.csv", ""), ("rnd", "no-such-file.csv", "")]
    SENT.write_text("")
    declare(HEAD + BLOCK + TAIL, LMISS)
    rc, o = validate()
    own = [ln for ln in o.splitlines() if ln.startswith("inputs/planted/")]
    nxt = [x for x in o.splitlines() if x.startswith("  Next")]
    SENT.write_text("".join(ln + "\n" + nx + "\n" for ln, nx in zip(own, nxt)))   # CC's own output INCLUDING the missing-file sentence
    miss_ok = any("does not exist under the data root" in ln for ln in own)
    declare(HEAD + BLOCK + EXPECT + TAIL, LMISS)
    rc, o = validate()
    check("a non-refusal defect (missing data file) LISTED in the sentence file is still a finding, validate red", miss_ok and rc == 1 and "does not exist under the data root" in o and "refused as declared" not in o, o[:800])
    SENT.write_text(good)
    declare(HEAD + BLOCK + EXPECT + TAIL, LMISS)
    mut9 = tmp / "mut9"
    shutil.copytree(repo, mut9)
    declare(HEAD + BLOCK + EXPECT + TAIL, LMISS, mut9)
    (mut9 / "expected" / "refusals" / "planted.txt").write_text("".join(ln + "\n" + nx + "\n" for ln, nx in zip(own, nxt)))
    p9 = mut9 / "cc" / "declare.py"
    t9 = p9.read_text()
    old9 = 'got = [f for f in found if f.loc.startswith(pre + "m.toml:") and any(re.search(r, f.loc.split(":", 1)[1]) for r in refusal_fields)]'
    assert old9 in t9
    p9.write_text(t9.replace(old9, "got = [f for f in found if f.loc.startswith(pre)]"))
    rc, o = validate(mut9)
    check("seen red: the old absorber (any finding under inputs/<id>/) swallows the missing-file defect and goes GREEN - the breaker can fail", rc == 0 and "refused as declared" in o, o[:600])

    # SEEN RED: a mutant that ignores [expect]
    mut = tmp / "mut"
    shutil.copytree(repo, mut)
    declare(HEAD + BLOCK + EXPECT + TAIL, L64, mut)
    p = mut / "cc" / "declare.py"
    t = p.read_text()
    old = '    root, lines = Path(root).resolve(), []\n    found, refusal_fields = list(found), list(tomllib.loads((root / "cc.toml").read_text())["refusal_fields"].values())\n'
    assert old in t
    p.write_text(t.replace(old, old + "    return found, lines\n"))
    rc, o = validate(mut)
    check("seen red: a score_expected that ignores [expect] leaves the refusals as findings, validate RED (as before the amendment)", rc == 1 and "refused as declared" not in o and "validate: 2 findings" in o, o[:600])
    # SEEN RED: a comparison that accepts anything makes the breakers (3)-(6) go green
    p.write_text(t.replace("        if not extra and not left:", "        if True:"))
    (mut / "expected" / "refusals" / "planted.txt").write_text(first[0] + "\n" + first[1] + "\n")
    rc, o = validate(mut)
    check("seen red: a comparison that accepts anything lets a file missing a sentence pass (so the breakers above can fail)", rc == 0 and "refused as declared" in o, o[:600])
    declare(HEAD + BLOCK + EXPECT + TAIL, L3000, mut)
    p.write_text(t.replace('        if not got:\n', '        if False:\n'))
    rc, o = validate(mut)
    check("seen red: without the ACCEPTED branch the accepted 3000-frame record declared refused is NOT a finding", "declared refused but the input was ACCEPTED" not in o, o[:600])
finally:
    shutil.rmtree(tmp, ignore_errors=True)
print("test_expect: " + ("FAILED" if bad else "all passed"))
sys.exit(1 if bad else 0)   # plan 0884 amendment 6: the runner reads the exit code; a FAILED line with exit 0 was a gate nobody read
