"""test_frozen_run_1282 - plan 1282 P2d: the frozen-run harness (tests/frozen_run_1282.py) and the sampler fold it resumes (cc/sampler.py). Tiny chains at K/K_c 0.92 and 1.08, seeds 1282400 + i.
F1 resume identity (the central test): a chain stopped after i completed yields, its checkpoint loaded in a fresh process and continued, equals the uninterrupted chain by chain_sha, content_sha and
file sha; F2 the H3 classify table; F3 the manifest (name, edits, caps, tau-independence); F4 the 840 seeds equal seal_seeds; F5 the atom names parse; F6 the RunState -> exit table; F7 STOP is
bounded by bounded submission, SIGTERM drains; F8 chunking (a burn is ceil(n / CHUNK_SWEEPS) compiled calls, a stop inside a yield returns the INPUT fold unchanged).
Reads the toolset through the data root (cc.toml [check] needs_data is the B2-ruled absence: run it explicitly with CC_DATA_ROOT set). Mutant pattern: each RED is an edit of a copy of this tree, run, and removed."""
import contextlib
import copy
import hashlib
import importlib.util
import io
import json
import os
import shutil
import signal
import subprocess
import sys
import tempfile
import time
from pathlib import Path

for _k in [k for k in os.environ if k.startswith("GIT_")]:
    del os.environ[_k]   # a git hook sets GIT_DIR/GIT_INDEX_FILE: the throwaway clones below must not act on the real worktree

ROOT = Path(__file__).resolve().parent.parent
from lib import bad, bootstrap, check, guarded, parse, real_root  # noqa: E402
bootstrap(ROOT, "cc", "cc/instruments")
import numpy as np  # noqa: E402
import sampler  # noqa: E402
import seal_reach  # noqa: E402

SPEC = importlib.util.spec_from_file_location("frozen_run_1282", ROOT / "tests" / "frozen_run_1282.py")
H = importlib.util.module_from_spec(SPEC)
sys.modules["frozen_run_1282"] = H
SPEC.loader.exec_module(H)
KC = sampler.KC
TMP = Path(tempfile.mkdtemp(prefix="frz1282-"))
MSHA = "m" * 64


def tools():
    t = sampler.load(sampler.toolset_of(real_root()))
    assert not isinstance(t, sampler.Mismatch), f"the toolset does not match the pins: {t}"
    return t


def row(i, N=40, skip=3, burn=20, k="0.92", s="ordered"):
    return H.row_of("poc", k, 27, s, i, 1282400 + i, N, skip, burn)


def counting(stop_at):
    """A stopper replacement: True at its stop_at-th call (work() polls once before begin, once after it, then once per yield: the call after yield i is the (2 + i)-th)."""
    calls = []

    def make(D, pid):
        def poll():
            calls.append(1)
            return len(calls) == stop_at
        return poll
    return make


def run_work(D, r, stop_at=None, ckpt_s=0):
    """work() in this process, optionally stopped at the stop_at-th poll."""
    H.TOOLS = tools()
    real = H.stopper
    if stop_at is not None:
        H.stopper = counting(stop_at)
    try:
        return H.work(str(D), r, MSHA, ckpt_s, 1)
    finally:
        H.stopper = real


RESUME_SNIPPET = ("import importlib.util,sys;spec=importlib.util.spec_from_file_location('frozen_run_1282',sys.argv[1]);H=importlib.util.module_from_spec(spec);sys.modules['frozen_run_1282']=H;"
                  "spec.loader.exec_module(H);import json;H._init();print(H.work(sys.argv[2],json.loads(sys.argv[3]),sys.argv[4],0,1))")


def resume_fresh_process(root, D, r):
    """The continuation of a stopped chain in a fresh Python process of the tree at `root` (nothing in memory survives)."""
    p = subprocess.run([sys.executable, "-c", RESUME_SNIPPET, str(Path(root) / "tests" / "frozen_run_1282.py"), str(D), json.dumps(r), MSHA], capture_output=True, text=True, env=os.environ)
    return p.stdout.strip(), p.stderr.strip()[-300:]


def chain_of(D, stem):
    with np.load(Path(D) / f"{stem}.npz") as z:
        return sampler.Chain(z["O"], z["G"], int(z["L"]), {"K": float(z["K"])}, z["M1"])


def f1():
    r = row(0)
    A = TMP / "f1-A"
    A.mkdir()
    check("F1 the uninterrupted run is DONE", run_work(A, r) == "DONE")
    cA, shaA, fileA = H.chain_sha(chain_of(A, r["stem"])), H.content_sha(A / f"{r['stem']}.npz").hex, H.file_sha(A / f"{r['stem']}.npz")
    t = tools()
    ref, _ = sampler.sample(t, float(r["k"]) * KC, 0.0, 27, "ordered", r["seed"], sampler.Run(40, 3, 20))
    check("F1 the harness chain is sampler.sample's chain (one code path)", H.chain_sha(ref) == cA)
    check("F1 the npz carries M1 and it is the chain's M1", np.array_equal(chain_of(A, r["stem"]).M1, ref.M1))
    for i in (1, 2, 18, 39):
        D = TMP / f"f1-{i}"
        D.mkdir()
        check(f"F1 i={i}: stopped after {i} completed yields", run_work(D, r, stop_at=2 + i) == "STOPPED" and (D / f"{r['stem']}.ckpt.npz").exists())
        out, err = resume_fresh_process(ROOT, D, r)
        got = (H.chain_sha(chain_of(D, r["stem"])), H.content_sha(D / f"{r['stem']}.npz").hex, H.file_sha(D / f"{r['stem']}.npz")) if out == "DONE" else None
        check(f"F1 i={i}: resumed chain_sha == uninterrupted", got is not None and got[0] == cA, err or str(out))
        check(f"F1 i={i}: resumed content_sha == uninterrupted", got is not None and got[1] == shaA, "")
        check(f"F1 i={i}: resumed npz FILE sha == uninterrupted (Pi8)", got is not None and got[2] == fileA, "")
        check(f"F1 i={i}: resumes = 1 in the call record and the checkpoint is gone", json.loads((D / f"{r['stem']}.json").read_text())["resumes"] == 1 and not (D / f"{r['stem']}.ckpt.npz").exists(), "")
    C = TMP / "f1-cadence"
    C.mkdir()
    run_work(C, r, ckpt_s=1e-9)
    check("F1 a checkpoint after every yield changes no output byte", H.content_sha(C / f"{r['stem']}.npz").hex == shaA and H.file_sha(C / f"{r['stem']}.npz") == fileA)


def planted(name, N=40):
    """A run dir holding one DONE chain made by work(): (D, row)."""
    D = TMP / name
    D.mkdir()
    r = row(0, N=N)
    run_work(D, r)
    return D, r


def f2():
    t = tools()
    cls = lambda D, r: H.classify(D, r, H.read_done(D), t.build, MSHA)[0]   # noqa: E731
    D, r = planted("f2-done")
    check("F2 Sha, present, equal -> DONE", cls(D, r) is H.ChainState.DONE)
    line = (D / "done.tsv").read_text()
    (D / "done.tsv").write_text(line.replace(r["stem"] + " ", r["stem"] + " 0", 1).replace(" 0", " f", 1) if False else f"{r['stem']} {'0' * 64} {'0' * 64}\n")
    check("F2 Sha, present, row's sha differs -> REDO (corrupt)", H.classify(D, r, H.read_done(D), t.build, MSHA) == (H.ChainState.REDO, "corrupt"))
    (D / "done.tsv").write_text("")
    check("F2 Sha, absent -> RECORD", cls(D, r) is H.ChainState.RECORD)
    (D / "done.tsv").write_text(line[:-1])
    check("F2 a done.tsv with a torn last line (no newline) reads that row as absent -> RECORD", cls(D, r) is H.ChainState.RECORD)
    (D / "done.tsv").write_text(line)
    npz = D / f"{r['stem']}.npz"
    data = npz.read_bytes()
    npz.write_bytes(data[:len(data) // 2])
    check("F2 a truncated npz is Unreadable -> REDO (corrupt)", isinstance(H.content_sha(npz), H.Unreadable) and H.classify(D, r, H.read_done(D), t.build, MSHA) == (H.ChainState.REDO, "corrupt"))
    npz.unlink()
    check("F2 absent, no checkpoint -> FRESH", cls(D, r) is H.ChainState.FRESH)
    S = TMP / "f2-resume"
    S.mkdir()
    run_work(S, r, stop_at=5)
    check("F2 absent, matching checkpoint -> RESUME", cls(S, r) is H.ChainState.RESUME)
    check("F2 absent, checkpoint of another manifest -> FRESH", H.classify(S, r, {}, t.build, "x" * 64)[0] is H.ChainState.FRESH)
    check("F2 absent, checkpoint of another build -> FRESH", H.classify(S, r, {}, "0" * 64, MSHA)[0] is H.ChainState.FRESH)
    check("F2 a non-zip file is Unreadable, a missing file is a value too", isinstance(H.content_sha(TMP / "nope.npz"), H.Unreadable))


def fixtures(cells, root):
    """cells: [(F, k, L, s, N, skip, burn, flag)] -> (cells.tsv, cost-inputs.tsv, bench.tsv) paths in `root`."""
    root.mkdir(parents=True, exist_ok=True)
    (root / "cells.tsv").write_text("F\tk\tL\ts\tN\tskip\tburn\ttau\n" + "".join(f"{F}\t{k}\t{L}\t{s}\t{N}\t{sk}\t{b}\t5\n" for F, k, L, s, N, sk, b, _ in cells))
    (root / "cost-inputs.tsv").write_text("F\tk\tL\ts\ttau_c\tsource\tform\ttau_own\tN_pilot_over_tau\tflag\tskip\tburn\tsstar\n"
                                          + "".join(f"{F}\t{k}\t{L}\t{s}\t5\tpilot\tconverged\tnone\t100\t{fl}\t{sk}\t{b}\t10\n" for F, k, L, s, N, sk, b, fl in cells))
    rows = [f"x\ty\t2\t3\t{L}\t{s}\t100\t{0.001 * s * L / 27}\t0\t{0.00295 * (L / 27) ** 2}\t0\t1\t0\t0\t1" for L in (27, 81, 243) for s in (1, 10, 100, 1000)] + ["x\ty\t2\t3\t27\t1\t100\t0.002\t0\t0\t0\t4\t0\t0\t1"]
    (root / "bench.tsv").write_text("host\tbuild\tnumpy\tpython\tL\ts\tn\ty_med\ty_min\tb_med\twall_med\tprocs\tload_before\tload_after\tcpu_over_wall\n" + "\n".join(rows) + "\n")
    return root / "cells.tsv", root / "cost-inputs.tsv", root / "bench.tsv"


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def manifest(h, cells_p, ci_p, bn_p, *extra, scale="rung1", root=None, ckpt=0, f=1.7, scratch=None):
    """Run `manifest` through h.main in this process: (exit code, stdout, run dir or None)."""
    args = ["manifest", "--cost-inputs", str(ci_p), "--cost-inputs-sha", sha(ci_p), "--bench", str(bn_p), "--bench-sha", sha(bn_p), "--f", str(f), "--ckpt-seconds", str(ckpt), "--root", str(root)]
    args += ["--scratch", scratch] if scratch else ["--cells", str(cells_p), "--cells-sha", sha(cells_p), "--scale", scale]
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        code = h.main(args + list(extra))
    lines = out.getvalue().splitlines()
    return code, out.getvalue(), (Path(lines[0]) if code == 0 else None)


def f3():
    fx = TMP / "f3"
    base = [("poc", "1.00", 27, "ordered", 1000, 10, 100, ""), ("poc", "1.00", 81, "random", 1000, 10, 100, "PILOT-SHORT"), ("decoy", "0.98", 243, "ordered", 1000, 100, 500, "")]
    cp, ci, bn = fixtures(base, fx / "in")
    code, out, D = manifest(H, cp, ci, bn, root=fx / "out")
    m, rows, msha = H.read_manifest(D)
    check("F3 the run dir name carries the manifest sha", D.name == f"rung1-{msha[:12]}" and len(rows) == 30, D.name)
    check("F3 N is CELLS.N // divisor on every row, skip and burn are copied", all(r["N"] == 10 for r in rows) and {(r["skip"], r["burn"]) for r in rows} == {(10, 100), (100, 500)}, "")
    bench = H.bench_of(bn)
    c = lambda L, sk, b, N: H.COST.chain_core_h(L, sk, b, N, bench, 1.7)   # noqa: E731
    check("F3 a rung1 manifest's cap_core_h is the stage cap 9, and rung2's 45, whatever the rows cost",
          m["cap_core_h"] == 9 and H.read_manifest(manifest(H, cp, ci, bn, root=fx / "o2", scale="rung2")[2])[0]["cap_core_h"] == 45, str(m["cap_core_h"]))
    only = fx / "only.txt"
    keep = [r["stem"] for r in rows if r["j"] in (0, 1) and r["L"] in (27, 81)]
    only.write_text("\n".join(keep) + "\n")
    _, _, Do = manifest(H, cp, ci, bn, "--only", str(only), root=fx / "o3")
    mo, ro, _ = H.read_manifest(Do)
    byte_equal = [r for r in rows if r["stem"] in keep] == ro
    want = 2 * (2 * c(27, 10, 100, 10) + 2 * 4 * c(81, 10, 100, 10)) + 0.2
    check("F3 --only keeps exactly the listed rows, byte-equal to the unfiltered ones", byte_equal and len(ro) == 4, str(len(ro)))
    check("F3 an --only manifest's cap is 2 x sum(upper) + 0.2, the PILOT-SHORT row x 4 (COST called directly)", abs(mo["cap_core_h"] - want) <= 1e-12 * want, f"{mo['cap_core_h']} vs {want}")
    _, _, Ds = manifest(H, None, ci, bn, root=fx / "o4", scratch="27,3,10,3,20")
    ms = H.read_manifest(Ds)[0]
    want = 2 * (2 * c(27, 3, 20, 10) + c(27, 3, 20, 10)) + 0.2
    check("F3 a --scratch manifest's cap is 2 x sum(upper) + 0.2 (no uplift)", abs(ms["cap_core_h"] - want) <= 1e-12 * want, f"{ms['cap_core_h']} vs {want}")
    check("F3 a scratch manifest uses K/K_c 0.92 and 1.08 and seeds 1282400 + i, below seed_of's range",
          {r["k"] for r in H.read_manifest(Ds)[1]} == {"0.92", "1.08"} and [r["seed"] for r in H.read_manifest(Ds)[1]] == [1282400, 1282401, 1282402], "")
    cp2, ci2, bn2 = fixtures([(*base[0][:4], 150, *base[0][5:])], fx / "in150")
    code, out, _ = manifest(H, cp2, ci2, bn2, root=fx / "o5")
    check("F3 N = 150 at rung1 is refused (not divisible by 100), exit 2", code == 2 and out.startswith("BLOCKED"), out)
    lo = fixtures([("poc", "1.00", 243, "ordered", 1000, 10, 10, "")], fx / "in-lo")
    hi = fixtures([("poc", "1.00", 243, "ordered", 1000, 10, 10 ** 9, "")], fx / "in-hi")
    ml = H.read_manifest(manifest(H, *lo, root=fx / "o6")[2])[0]
    mh = H.read_manifest(manifest(H, *hi, root=fx / "o7")[2])[0]
    check("F3 a burn of 10^9 is accepted with the same stop_bound_s as a burn of 10 (tau-independence)", ml["stop_bound_s"] == mh["stop_bound_s"], f"{ml['stop_bound_s']} {mh['stop_bound_s']}")
    check("F3 stop_bound_s = CHUNK_SWEEPS x b(243) x F / 1000 + 10", abs(mh["stop_bound_s"] - (sampler.CHUNK_SWEEPS * bench.b[243] * 1.7 / 1000 + 10)) < 1e-9, str(mh["stop_bound_s"]))
    Dh = manifest(H, *hi, root=fx / "o7")[2]
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        code = H.main(["project", "--run-dir", str(Dh)])
    check("F3 project on a rung fixture whose upper sum exceeds 9 -> BLOCKED, exit 2", code == 2 and "BLOCKED projection" in out.getvalue(), out.getvalue())
    oh = fx / "hi-only.txt"
    oh.write_text(H.read_manifest(Dh)[1][0]["stem"] + "\n")
    Dho = manifest(H, *hi, "--only", str(oh), root=fx / "o8")[2]
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        code = H.main(["project", "--run-dir", str(Dho)])
    check("F3 project on an --only fixture never refuses", code == 0 and "DONE project" in out.getvalue(), out.getvalue())


def clone(dest):
    """A throwaway committed copy of this tree's cc/ and tests/ (a mutant or a dirty edit is made in the copy, never here)."""
    dest = Path(dest)
    shutil.copytree(ROOT / "cc", dest / "cc", ignore=shutil.ignore_patterns("__pycache__"))
    shutil.copytree(ROOT / "tests", dest / "tests", ignore=shutil.ignore_patterns("__pycache__"))
    (dest / ".gitignore").write_text("__pycache__/\n")   # the real tree ignores bytecode; a clone that did not would read as CODE-CHANGED after its first import
    for a in (["init", "-q"], ["add", ".gitignore", "cc", "tests"], ["-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qm", "x"]):
        subprocess.run(["git", "-C", str(dest), *a], check=True, capture_output=True)
    return dest


def py(root, *args, **kw):
    return subprocess.run([sys.executable, str(Path(root) / "tests" / "frozen_run_1282.py"), *map(str, args)], capture_output=True, text=True, **kw)


def build_in(root, outdir, scratch, f=1.7):
    fx = TMP / ("fx-" + hashlib.sha256(str(outdir).encode()).hexdigest()[:8])
    cp, ci, bn = fixtures([("poc", "1.00", 27, "ordered", 100, 10, 100, "")], fx)
    p = py(root, "manifest", "--cost-inputs", ci, "--cost-inputs-sha", sha(ci), "--bench", bn, "--bench-sha", sha(bn), "--f", f, "--ckpt-seconds", 0, "--root", outdir, "--scratch", scratch)
    assert p.returncode == 0, p.stdout + p.stderr
    return Path(p.stdout.splitlines()[0])


def f3b():
    """The driver's own refusals, in a committed copy."""
    C = clone(TMP / "f3b-clone")
    D = build_in(C, TMP / "f3b-out", "27,2,5,3,20")
    other = TMP / "f3b-copy" / D.name
    shutil.copytree(D, other)
    mp = other / "manifest.toml"
    b = bytearray(mp.read_bytes())
    b[b.index(b"\nf = ") + 5] = ord("9")
    mp.write_bytes(bytes(b))
    p = py(C, "serve", "--run-dir", other, "--procs", 1)
    check("F3 an edited manifest byte -> FAILED MANIFEST-CHANGED", "FAILED MANIFEST-CHANGED" in p.stdout, p.stdout + p.stderr[-300:])
    (C / "tests" / "frozen_run_1282.py").write_text((C / "tests" / "frozen_run_1282.py").read_text() + "\n# uncommitted edit\n")
    p = py(C, "serve", "--run-dir", D, "--procs", 1)
    check("F3 an uncommitted edit under an existing manifest -> FAILED CODE-CHANGED", "FAILED CODE-CHANGED" in p.stdout, p.stdout + p.stderr[-300:])


def f4():
    fx = TMP / "f4"
    cells = [(F, k, L, s, 100, 10, 100, "") for F, k, L, s in sampler.cells()]
    cp, ci, bn = fixtures(cells, fx / "in")
    code, _, D = manifest(H, cp, ci, bn, root=fx / "out")
    rows = H.read_manifest(D)[1]
    seeds = seal_reach.seal_seeds("1282-v10")
    check("F4 seal_seeds returns Seeds, not SeedClash", isinstance(seeds, seal_reach.Seeds), type(seeds).__name__)
    check("F4 a full rung-1 manifest has 840 rows and its seeds are exactly seal_seeds' run seeds", len(rows) == 840 and set(r["seed"] for r in rows) == set(seeds.run), f"{len(rows)}")
    check("F4 every grid seed is in [3e9, 4e9)", all(3_000_000_000 <= r["seed"] < 4_000_000_000 for r in rows), "")


def f5_f6():
    atoms = frozenset(H.ChainState.__members__)
    check("F5 ChainState atoms are DONE RECORD REDO RESUME FRESH, and each name parses to itself", atoms == {"DONE", "RECORD", "REDO", "RESUME", "FRESH"} and all(parse(a, atoms) == {a} for a in atoms), str(sorted(atoms)))
    ratoms = frozenset(H.RunState.__members__)
    check("F5 RunState atoms are RUNNING DONE STOPPED DRAINED FAILED LOCKED, and each name parses to itself", ratoms == {"RUNNING", "DONE", "STOPPED", "DRAINED", "FAILED", "LOCKED"} and all(parse(a, ratoms) == {a} for a in ratoms), str(sorted(ratoms)))
    check("F5 a wrong name is no atom", parse("DONNE", atoms) is None and parse("RunState", ratoms) is None, "")
    check("F6 the exit table is total over the RunState atoms", set(H.EXIT) == set(H.RunState), "")
    check("F6 every non-RUNNING state exits 0 (launchd must not respawn a terminal state); RUNNING never exits", all(v == 0 for k, v in H.EXIT.items() if k is not H.RunState.RUNNING) and H.EXIT[H.RunState.RUNNING] is None, str(H.EXIT))


def wait_for(fn, limit=60):
    t0 = time.time()
    while time.time() - t0 < limit:
        if fn():
            return True
        time.sleep(0.05)
    return False


def begins(D):
    p = Path(D) / "driver.log"
    return [ln for ln in p.read_text().splitlines() if " begin " in ln] if p.exists() else []


def f7():
    C = clone(TMP / "f7-clone")
    D = build_in(C, TMP / "f7-out", "27,40,300,3000,20")
    srv = subprocess.Popen([sys.executable, str(C / "tests" / "frozen_run_1282.py"), "serve", "--run-dir", str(D), "--procs", "2"], stdout=subprocess.PIPE, text=True)
    check("F7 two chains begin", wait_for(lambda: len(begins(D)) >= 2))
    (D / "STOP").write_text("")
    t0 = time.time()
    srv.wait(timeout=60)
    ck = list(D.glob("*.ckpt.npz"))
    check("F7 after STOP no new chain begins: exactly the 2 begin lines", len(begins(D)) == 2, str(len(begins(D))))
    check("F7 the run is STOPPED, exit 0, within the bound", srv.returncode == 0 and (D / "status.line").read_text().startswith("STOPPED") and time.time() - t0 < H.read_manifest(D)[0]["stop_bound_s"], (D / "status.line").read_text())
    check("F7 at most 2 checkpoints and every other row stays FRESH (no files)", len(ck) <= 2 and not list(D.glob("*.npz")) == [] or len(ck) <= 2, str(len(ck)))
    check("F7 no final chain file for a stopped chain", not [p for p in D.glob("*.npz") if ".ckpt" not in p.name and ".tmp" not in p.name], "")
    Dn = TMP / "f7-notstarted"
    Dn.mkdir()
    (Dn / "STOP").write_text("")
    r = row(0)
    check("F7 STOP present before a row's begin -> STOPPED, `notstarted <stem>` logged, no checkpoint",
          run_work(Dn, r) == "STOPPED" and f"notstarted {r['stem']}" in (Dn / "driver.log").read_text() and not list(Dn.glob("*.ckpt.npz")), "")
    D2 = build_in(C, TMP / "f7-out2", "27,40,300,3000,20", f=1.8)
    srv = subprocess.Popen([sys.executable, str(C / "tests" / "frozen_run_1282.py"), "serve", "--run-dir", str(D2), "--procs", "2"], stdout=subprocess.PIPE, text=True)
    wait_for(lambda: len(begins(D2)) >= 2)
    srv.send_signal(signal.SIGTERM)
    srv.wait(timeout=60)
    check("F7 SIGTERM -> DRAIN.<pid> written, DRAINED, exit 0", srv.returncode == 0 and (D2 / f"DRAIN.{srv.pid}").exists() and (D2 / "status.line").read_text().startswith("DRAINED"), (D2 / "status.line").read_text())
    before = len(begins(D2))
    srv2 = subprocess.Popen([sys.executable, str(C / "tests" / "frozen_run_1282.py"), "serve", "--run-dir", str(D2), "--procs", "2"], stdout=subprocess.PIPE, text=True)
    check("F7 a second life (another pid) ignores the first life's DRAIN file and runs", wait_for(lambda: len(begins(D2)) >= before + 2) and srv2.pid != srv.pid, "")
    (D2 / "STOP").write_text("")
    srv2.wait(timeout=60)


def f9():
    """F9: a worker kill -9 (BrokenProcessPool) makes the driver exit non-zero promptly, not after the surviving workers' chains."""
    C = clone(TMP / "f9-clone")
    D = build_in(C, TMP / "f9-out", "27,40,3000,3000,20")
    srv = subprocess.Popen([sys.executable, str(C / "tests" / "frozen_run_1282.py"), "serve", "--run-dir", str(D), "--procs", "2"], stdout=subprocess.PIPE, text=True)
    check("F9 two chains begin", wait_for(lambda: len(begins(D)) >= 2))
    victim = int(begins(D)[0].rsplit("pid=", 1)[1])
    os.kill(victim, signal.SIGKILL)
    t0 = time.time()
    try:
        srv.wait(timeout=30)
    except subprocess.TimeoutExpired:
        srv.kill()
        srv.wait()
    check("F9 driver exits non-zero within 30 s of a worker kill -9 (survivors do not hold it)", srv.returncode == 70 and time.time() - t0 < 30, f"rc={srv.returncode} after {time.time() - t0:.1f}s")
    check("F9 no worker of that life survives the driver's exit", not [ln for ln in subprocess.run(["pgrep", "-f", str(D)], capture_output=True, text=True).stdout.split() if int(ln) != os.getpid()], "")


class Spy:
    """Stands in for the compiled module: records the sweeps of every isfield_sweeps_rs call."""

    def __init__(self, real, log):
        self._real, self.log = real, log

    def isfield_sweeps_rs(self, s, k, h, n, seed):
        self.log.append(n)
        return self._real.isfield_sweeps_rs(s, k, h, n, seed)

    def __getattr__(self, name):
        return getattr(self._real, name)


def f8():
    t = tools()
    real, calls, polls = t.field.rs, [], []
    t.field.rs = Spy(real, calls)
    try:
        run = sampler.Run(2, 3, 120_000)
        f = sampler.begin(t, 0.92 * KC, 0.0, 27, "ordered", 1282400, run, lambda: polls.append(1) or False)
        check("F8 burn 120,000 -> 3 compiled calls of 50,000 / 50,000 / 20,000", calls == [50_000, 50_000, 20_000], str(calls))
        check("F8 poll is called between the chunks (twice for 3 chunks)", len(polls) == 2, str(len(polls)))
        calls.clear()
        sampler.advance(t, f, 0.92 * KC, 0.0, run, lambda: False)
        check("F8 skip 3 -> one compiled call", calls == [3], str(calls))
        got = sampler.begin(t, 0.92 * KC, 0.0, 27, "ordered", 1282400, run, lambda: True)
        check("F8 a poll that stops during the burn -> NotStarted", isinstance(got, sampler.NotStarted), type(got).__name__)
        Dn = TMP / "f8-burn"
        Dn.mkdir()
        H.TOOLS = t
        real_stop, H.stopper = H.stopper, lambda D, pid: (lambda: True)
        try:
            res = H.work(str(Dn), row(0, N=2, burn=120_000), MSHA, 0, 1)
        finally:
            H.stopper = real_stop
        check("F8 work stopped in the burn -> STOPPED and no checkpoint file", res == "STOPPED" and not list(Dn.glob("*.ckpt.npz")), res)
        long = sampler.Run(3, 120_000, 20)
        f1 = sampler.advance(t, sampler.begin(t, 0.92 * KC, 0.0, 27, "random", 1282401, long, lambda: False), 0.92 * KC, 0.0, long, lambda: False)
        held = copy.deepcopy((f1.s, f1.rng_state, f1.i, f1.O, f1.G, f1.M1))
        r8 = row(1, N=3, skip=120_000, k="0.92", s="random")
        H.ckpt_write(Dn, r8, f1, t.build, MSHA, 0, 0.0, 0.0)
        z1 = {k: v for k, v in np.load(Dn / f"{r8['stem']}.ckpt.npz").items()}
        calls.clear()
        r = sampler.advance(t, f1, 0.92 * KC, 0.0, long, lambda: True)
        now = (f1.s, f1.rng_state, f1.i, f1.O, f1.G, f1.M1)
        same = lambda a, b: np.array_equal(np.asarray(a, dtype=object) if isinstance(a, list) and False else a, b) if not isinstance(a, dict) else a == b   # noqa: E731
        check("F8 a stop inside a long yield (Fold.i >= 1) returns Stopped carrying the INPUT fold", isinstance(r, sampler.Stopped) and r.f is f1, type(r).__name__)
        check("F8 the fold in hand is unchanged by value (s, rng_state, i, O, G, M1)", all(same(a, b) for a, b in zip(held, now)) and calls == [50_000], str(calls))
        H.ckpt_write(Dn, r8, r.f, t.build, MSHA, 0, 0.0, 0.0)
        z2 = {k: v for k, v in np.load(Dn / f"{r8['stem']}.ckpt.npz").items()}
        check("F8 the checkpoint written from Stopped equals the one of the previous yield", z1.keys() == z2.keys() and all(np.array_equal(z1[k], z2[k]) for k in z1), "")
    finally:
        t.field.rs = real


for n, f in (("F1", f1), ("F2", f2), ("F3", f3), ("F3b", f3b), ("F4", f4), ("F5/F6", f5_f6), ("F7", f7), ("F8", f8), ("F9", f9)):
    guarded(n, f)
shutil.rmtree(TMP, ignore_errors=True)
print("test_frozen_run_1282: " + ("FAILED" if bad else "all passed"))
sys.exit(1 if bad else 0)
