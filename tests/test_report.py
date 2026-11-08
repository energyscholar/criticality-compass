"""test_report - plan 0884 amendment 4 (P2a): the relation-free `report` instrument, and the gate that can fail.
A scratch copy of the repo gets planted island-table inputs (a 27 x 27 fully listed grid, the data root a scratch directory):
(1) `report` with an unused [relations] table is REFUSED; (2) `report` with no [observable] is REFUSED; (3) a planted 3000-frame record is ACCEPTED by validate under block AND gamma,
and `bin/cc run` reads it (the sinks, and the level means of an all +1 point = 1 and of a random +-1 point near 0); (4) the same record at 64 frames is REFUSED at the interval floors
with CC's own sentences (block: b <= 2; gamma: tau_declared <= 1); (5) method chains: ten 20-frame chain files per cell are accepted by chain_cells, one chain is refused.
SEEN RED: each of (1)-(5) is re-run against a scratch copy whose rule is removed by a text mutant, and must then FAIL (the rule is the only thing that made it hold)."""
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
import numpy as np

ROOT = Path(__file__).resolve().parent.parent


from lib import bad, check  # noqa: E402


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
source = "tests/test_report.py"

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


tmp = Path(tempfile.mkdtemp(prefix="report-scratch-"))
try:
    data = tmp / "data"
    (data / "planted").mkdir(parents=True)
    rng = np.random.default_rng(884)
    long_ = {"ord": np.ones((3000, S * S)), "rnd": rng.choice([-1.0, 1.0], size=(3000, S * S))}
    for pt, a in long_.items():
        table(data / "planted" / f"{pt}-3000.csv", a)
        table(data / "planted" / f"{pt}-64.csv", a[:64])
    for k in range(10):
        table(data / "planted" / f"c{k}.csv", rng.choice([-1.0, 1.0], size=(20, S * S)))
    env = {**os.environ, "CC_DATA_ROOT": str(data)}

    def fresh(name):
        repo = tmp / name
        shutil.copytree(ROOT, repo, ignore=shutil.ignore_patterns(".git", "__pycache__", "rust", "results"))
        (repo / "results").mkdir()
        fz = json.loads((repo / "FROZEN.json").read_text())   # the scratch copy holds no results: the frozen ones are not its to check
        fz["files"] = {k: v for k, v in fz["files"].items() if not k.startswith("results/")}
        (repo / "FROZEN.json").write_text(json.dumps(fz, indent=1) + "\n")
        (repo / "inputs" / "planted").mkdir()
        (repo / "inputs" / "planted" / "transducer.toml").write_text(TRANS)
        (repo / "inputs" / "planted" / "couplings.toml").write_text(COUP)
        (repo / "inputs" / "planted" / "points.toml").write_text('schema = 1\nkind = "points"\ninput = "planted"\n\n[points]\n"ord" = "none"\n"rnd" = "none"\n')
        return repo

    def cc(repo, *a):
        r = subprocess.run([sys.executable, str(repo / "bin" / "cc"), *a], cwd=repo, env=env, capture_output=True, text=True)
        return r.returncode, r.stdout + r.stderr

    def declare(repo, text, blocks):
        (repo / "inputs" / "planted" / "m.toml").write_text(text + files(blocks))
        pins = "".join(f'"{b[1] if False else "planted/" + b[1]}" = "{__import__("hashlib").sha256((data / "planted" / b[1]).read_bytes()).hexdigest()}"\n' for b in sorted(set(blocks), key=lambda x: x[1]))
        (repo / "fixtures" / "data").mkdir(parents=True, exist_ok=True)
        (repo / "fixtures" / "data" / "planted.toml").write_text('schema = 1\nkind = "data-manifest"\ninput = "planted"\n\n[files]\n' + pins)

    def validate(repo):
        return cc(repo, "validate", "--input", "planted", "--tables", "v08-rules")[1]

    def mutate(repo, rel, old, new):
        p = repo / rel
        t = p.read_text()
        assert old in t, (rel, old)
        p.write_text(t.replace(old, new))

    L3000 = [("ord", "ord-3000.csv", ""), ("rnd", "rnd-3000.csv", "")]
    L64 = [("ord", "ord-64.csv", ""), ("rnd", "rnd-64.csv", "")]

    # (1) report + an unused relations table
    REL = '\n[relations.control]\ntemplate = "chain"\naxis = "point"\nprovenance = "Coupling"\ncoupling = "T"\ndirection_from = "planted"\n'
    r1 = fresh("r1")
    declare(r1, HEAD + REL + BLOCK + TAIL, L3000)
    o = validate(r1)
    check("report + a relations table: refused as unused", "table present but no declared instrument uses it" in o and "validate: clean" not in o, o[:500])
    mutate(r1, "cc/declare.py", 'out += when(not need("relations") and "relations" in d,', 'out += when(False and "relations" in d,')
    mutate(r1, "cc/declare.py", 'for rn in rels if rn not in need]', 'for rn in rels if False]')
    o = validate(r1)
    check("seen red: with both unused-relations rules removed the table is NOT refused", "uses it" not in o and "not used by any declared instrument" not in o, o[:500])

    # (2) report with no observable
    r2 = fresh("r2")
    declare(r2, (HEAD.replace(HEAD[HEAD.index("[observable]"):HEAD.index("[block_map]")], "")) + BLOCK + TAIL, L3000)
    o = validate(r2)
    check("report with no [observable]: refused as a missing required table", "observable" in o and "missing required table (a declared instrument needs it)" in o and "validate: clean" not in o, o[:500])
    mutate(r2, "cc/declare.py", "want and name not in d, p, name,", "False and name not in d, p, name,")
    o = validate(r2)
    check("seen red: with the missing-table rule removed the input is NOT refused for it", "missing required table (a declared instrument needs it)" not in o, o[:500])

    # (3) the 3000-frame record: accepted under block and gamma, and read
    r3 = fresh("r3")
    declare(r3, HEAD + BLOCK + TAIL, L3000)
    o = validate(r3)
    check("planted 3000-frame record: validate ACCEPTS it under block (b 9, 3000 // 9 = 333 >= 30)", o.rstrip().endswith("validate: clean") and "min_blocks" not in o, o[:500])
    declare(r3, HEAD + GAMMA + TAIL, L3000)
    o = validate(r3)
    check("planted 3000-frame record: validate ACCEPTS it under gamma (tau_declared 3, 3000 >= 64 * 3)", o.rstrip().endswith("validate: clean"), o[:500])
    declare(r3, HEAD + BLOCK + TAIL, L3000)
    rc, o = cc(r3, "run", "planted", "--tables", "v08-rules")
    res = json.loads(next((r3 / "results").glob("planted@v08-rules.json")).read_text()) if rc == 0 else {}
    rep = {(x["unit"]["point"], x["name"]): x["estimate"] for x in res.get("reports", [])}
    ok = (rc == 0 and rep.get(("ord", "sinks")) == [1.0, 0.0] and rep.get(("rnd", "sinks")) == [1.0, 0.0] and rep.get(("ord", "levels")) == [1.0, 1.0]
          and len(rep.get(("rnd", "levels"), [])) == 2 and all(abs(v) < 0.05 for v in rep[("rnd", "levels")]))
    check("bin/cc run reads it: sinks [1, 0]; the all +1 point has level means [1, 1]; the random point is near 0", ok, (o[-500:], rep))
    r3m = fresh("r3m")
    declare(r3m, HEAD + BLOCK + TAIL, L3000)
    mutate(r3m, "cc/declare.py", "    mb, b = iv.get(\"min_blocks\"), iv.get(\"b\")\n", "    mb, b = iv.get(\"min_blocks\"), iv.get(\"b\")\n    mb = 10 ** 9\n")
    o = validate(r3m)
    check("seen red: with a floor that refuses every record the 3000-frame record is NOT accepted (the acceptance can fail)", not o.rstrip().endswith("validate: clean") and "min_blocks" in o, o[:500])

    # (4) the same record at 64 frames: refused at the floors with CC's own sentences
    r4 = fresh("r4")
    declare(r4, HEAD + BLOCK + TAIL, L64)
    o = validate(r4)
    check("64 frames, block: refused at the floor, CC's sentence (b <= 2)", "hold fewer than min_blocks = 30 blocks of b = 9" in o and 'keep method = "block" with b <= 2 (n 64 // min_blocks 30)' in o, o[:600])
    declare(r4, HEAD + GAMMA + TAIL, L64)
    o = validate(r4)
    check("64 frames, gamma: refused at the floor, CC's sentence (tau_declared <= 1)", "fewer than k_gamma * tau_declared = 64 * 3 = 192 samples" in o and "this record admits tau_declared <= 1" in o, o[:600])
    r4m = fresh("r4m")
    declare(r4m, HEAD + BLOCK + TAIL, L64)
    mutate(r4m, "cc/declare.py", "    mb, b = iv.get(\"min_blocks\"), iv.get(\"b\")\n", "    return []\n    mb, b = iv.get(\"min_blocks\"), iv.get(\"b\")\n")
    mutate(r4m, "cc/declare.py", "    td = iv.get(\"tau_declared\")\n    if iv.get(\"method\") != \"gamma\"", "    return []\n    td = iv.get(\"tau_declared\")\n    if iv.get(\"method\") != \"gamma\"")
    o = validate(r4m)
    check("seen red: with the floors removed the 64-frame record is NOT refused (the refusal comes from the floor and nothing else)", o.rstrip().endswith("validate: clean"), o[:500])
    declare(r4m, HEAD + GAMMA + TAIL, L64)
    o = validate(r4m)
    check("seen red: with the floors removed the 64-frame gamma record is NOT refused", o.rstrip().endswith("validate: clean"), o[:500])

    # (5) method chains: chain_cells accepts ten chains per cell and refuses one
    r5 = fresh("r5")
    ten = [("ord", f"c{k}.csv", f"chain = {k}\n") for k in range(10)]
    CH = HEAD.replace('point = ["ord", "rnd"]', 'point = ["ord"]').replace('"rnd" = "observed"\n', "")
    declare(r5, CH + CHAINS + TAIL, ten)
    (r5 / "inputs" / "planted" / "points.toml").write_text('schema = 1\nkind = "points"\ninput = "planted"\n\n[points]\n"ord" = "none"\n')
    o = validate(r5)
    check("ten chains per cell: chain_cells accepts (validate clean)", o.rstrip().endswith("validate: clean"), o[:600])
    declare(r5, CH + CHAINS + TAIL, ten[:1])
    o = validate(r5)
    check("one chain per cell: refused, naming the cell and 0..9", "holds chains [0], not exactly 0..9" in o, o[:600])
    mutate(r5, "cc/declare.py", "    return out + [at(p, \"data.files\", f\"cell (point", "    return out[:0] + [at(p, \"data.files\", f\"cell (point")
    mutate(r5, "cc/declare.py", "for k, v in list(bad.items())[:5]]", "for k, v in list(bad.items())[:0]]")
    o = validate(r5)
    check("seen red: with chain_cells' finding removed the one-chain cell is NOT refused", "holds chains" not in o, o[:600])
finally:
    shutil.rmtree(tmp, ignore_errors=True)
print("test_report: " + ("FAILED" if bad else "all passed"))
sys.exit(1 if bad else 0)
