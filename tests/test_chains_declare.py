"""test_chains_declare - plan 0937 P1 (A2): eligibility of an input of method `chains` is a declare-time schema, and one end-to-end run reads the order statistics.
A scratch copy of the repo gets x8-chains: the x8-ising-needle arrays cut into 10 chain files per cell (chain k = rows 160k..160k+159 of the real array), method chains m 10 r 2.
(1) the clean scratch input validates with no finding; (2) 9 chains in one cell, r 3, and `chain` on a non-chains input are each REFUSED with their exact finding (seen red:
with chain_cells emptied the 9-chain case is no longer refused, so the test can fail); (3) one run under v10-rules: every velocity reading's lo/hi are the (r)th and (m+1-r)th
order statistics of the m per-chain readings (rows 1..m of its stored vector), the estimate is their median; (4) plan 0978: a family over a chains input is READ (the 0937 refusal is deleted; tests/test_0978.py holds the family-layer tests)."""
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path[:0] = [str(ROOT / "cc"), str(ROOT / "cc" / "instruments")]
import declare  # noqa: E402
import schema  # noqa: E402

bad = []


def check(name, ok, why=""):
    print(("ok   " if ok else "FAIL ") + name + ("" if ok else f": {why}"))
    if not ok:
        bad.append(name)


import tomllib  # noqa: E402
cfg = tomllib.loads((ROOT / "cc.toml").read_text())
REAL = schema.resolve_data_root(cfg)[0]
M = 10
X8 = ROOT / "inputs" / "x8-ising-needle"
text = (X8 / "m.toml").read_text()
head, _, _ = text.partition("[[data.files]]")
head = head.replace('id = "x8-ising-needle"', 'id = "x8-chains"')
iv0, iv1 = head.index("[interval]"), head.index("\n[", head.index("[interval]") + 1) + 1
IV = '[interval]\nmethod = "chains"\nm = 10\nr = 2\nalpha = 0.021484375\nchain_root = "chains"\n'
blocks = []
cur = {}
for ln in text[text.index("[[data.files]]"):].splitlines():
    if ln.startswith("[[data.files]]"):
        cur = {}
        blocks.append(cur)
    elif " = " in ln and not ln.startswith("arrays"):
        k, v = ln.split(" = ", 1)
        cur[k] = v
tmp = Path(tempfile.mkdtemp(prefix="chains-scratch-"))
try:
    repo, data = tmp / "repo", tmp / "ts" / "data"   # the data root's parent is the toolset (sampler pins resolve against its git history): link the real one's
    data.parent.mkdir()
    [(data.parent / n).symlink_to(REAL.parent / n) for n in (".git", "tools", "studies") if (REAL.parent / n).exists()]
    shutil.copytree(ROOT, repo, ignore=shutil.ignore_patterns(".git", "__pycache__", "rust"))
    new = repo / "inputs" / "x8-chains"
    new.mkdir()
    for f in ("points.toml", "transducer.toml", "couplings.toml"):
        (new / f).write_text((X8 / f).read_text().replace("x8-ising-needle", "x8-chains"))

    def chain_blocks(skip=None):
        out = []
        for b in blocks:
            src = Path(b["path"].strip('"'))
            for k in range(M):
                if skip == (b["point"], b["size"], k):
                    continue
                out.append("[[data.files]]\npoint = %s\nsize = %s\nstart = %s\npath = \"chains/%s.c%d.npy\"\nchain = %d\narrays.GL = { key = \"npy\" }\n" % (b["point"], b["size"], b["start"], src.with_suffix(""), k, k))
        return "\n".join(out)

    for b in blocks:
        src = Path(b["path"].strip('"'))
        a = np.load(REAL / src)
        n = len(a) // M
        for k in range(M):
            dst = data / "chains" / f"{src.with_suffix('')}.c{k}.npy"
            dst.parent.mkdir(parents=True, exist_ok=True)
            np.save(dst, a[k * n:(k + 1) * n])

    import hashlib
    pins = "".join('"%s" = "%s"\n' % (f.relative_to(data), hashlib.sha256(f.read_bytes()).hexdigest()) for f in sorted(data.rglob("*.npy")))
    (repo / "fixtures" / "data" / "x8-chains.toml").write_text('schema = 1\nkind = "data-manifest"\ninput = "x8-chains"\n\n[files]\n' + pins)

    def declared(iv=IV, skip=None):
        (new / "m.toml").write_text(head[:iv0] + iv + "\n" + head[iv1:] + chain_blocks(skip))
        c = schema.Ctx(repo, data_root=data)
        return [declare.fmt(f) for f in declare.check_file(new / "m.toml", repo, ctx=c)]

    clean = declared()
    check("the clean 10-chain scratch input validates with no finding", clean == [], str(clean)[:600])
    nine = declared(skip=('"1.00"', "243", 9))
    check("9 chains in a cell is refused at declare time, naming the cell and 0..9", any("holds chains [0, 1, 2, 3, 4, 5, 6, 7, 8], not exactly 0..9" in x for x in nine), str(nine)[:600])
    r3 = declared(IV.replace("r = 2", "r = 3"))
    check("r 3 is refused at declare time (r must be rank(m, alpha) = 2)", any("r = 3 is not rank(m, alpha) = 2" in x for x in r3), str(r3)[:600])
    (new / "m.toml").write_text(text.replace('id = "x8-ising-needle"', 'id = "x8-chains"').replace('path = "p1/g1-0.90.npy"', 'path = "p1/g1-0.90.npy"\nchain = 0', 1))
    non = [declare.fmt(f) for f in declare.check_file(new / "m.toml", repo, ctx=schema.Ctx(repo, data_root=REAL))]
    check("a chain label on a non-chains input is refused", any("chain is declared only under an interval method of chains" in x for x in non), str(non)[:600])
    keep = declare.chain_cells
    declare.chain_cells = lambda *a: []
    try:
        mut = declared(skip=('"1.00"', "243", 9))
    finally:
        declare.chain_cells = keep
    check("seen red: with chain_cells emptied the 9-chain input is NOT refused (the test can fail)", not any("holds chains" in x for x in mut), str(mut)[:300])

    declared()
    env = {**os.environ, "CC_DATA_ROOT": str(data)}
    run = subprocess.run([sys.executable, str(repo / "bin" / "cc"), "run", "x8-chains", "--tables", "v10-rules"], cwd=repo, env=env, capture_output=True, text=True)
    check("bin/cc run x8-chains --tables v10-rules succeeds", run.returncode == 0, (run.stdout + run.stderr)[-800:])
    res = json.loads(next((repo / "results").glob("x8-chains@v10-rules*.json")).read_text())
    vec = np.load(repo / res["vectors"])
    rd = [r for r in res["readings"] if r["vector_key"]]
    ok = len(rd) > 0
    for r in rd:
        v = np.asarray(vec[r["vector_key"]], float)
        chains = np.sort(v[1:M + 1])
        ok &= len(v) == M + 1 and (r["lo"], r["hi"]) == (chains[1], chains[M - 2]) and r["estimate"] == float(np.median(chains))
    check("end to end: every reading's lo/hi are the 2nd and 9th order statistics of its 10 per-chain readings", ok, str(rd[:1])[:400])
    (repo / "families").mkdir(exist_ok=True)
    (repo / "families" / "fx.toml").write_text('kind = "family-decl"\nid = "fx"\ninput = "x8-chains"\nschema = 1\ninterior = ["0.95", "0.98", "0.99", "1.00", "1.01", "1.02", "1.05"]\n')
    # plan 0978 (declared edit of the plan 0937 assertions here): the gate `detect.family_refusal` is deleted, so a family over a chains input is READ, never refused
    cli = subprocess.run([sys.executable, str(repo / "bin" / "cc"), "family", "fx", "--tables", "v10-rules"], cwd=repo, env=env, capture_output=True, text=True)
    check("bin/cc family over a chains input is read, not refused (plan 0978)", cli.returncode == 0 and "family fx" in cli.stdout and "REFUSED" not in cli.stdout, (cli.stdout + cli.stderr)[-500:])
    check("the family's f1 reads NOT-MEASURED there (x8-chains declares no across_delta): a null, not an error", "f1      NOT-MEASURED" in cli.stdout, cli.stdout[-500:])
finally:
    shutil.rmtree(tmp, ignore_errors=True)
print("test_chains_declare: " + ("FAILED" if bad else "all passed"))
sys.exit(1 if bad else 0)
