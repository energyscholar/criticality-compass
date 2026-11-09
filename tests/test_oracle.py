"""test_oracle - plan 1282 P3: the total Oracle sum type and `cc navigate --oracle declared`. Data-free (0 core-h): the exact 2-D Ising field is a walk-identity check.
Breakers, each seen RED: B1 (ZERO-pinned interior; RED on navigate.MOVE which stops, GREEN on MOVE_LIVE which is UNRESOLVED), B2 (inverted field; RED on a lo/hi-swapped table),
B3 (literal-uniform ZERO; REFUSE). Plan 1282 P5 (below): the Measured field, the scan terminal, its breakers and a synthetic loader fixture. Also E-LOG (append-before-use record), dispatch totality, MOVE_LIVE totality, cc/navigate.py byte-unchanged against main 8d0551f."""
import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
from lib import check  # noqa: E402
sys.path[:0] = [str(ROOT / "cc")]
import navigate  # noqa: E402
import oracle  # noqa: E402
from sign import Sign  # noqa: E402

S = Sign
ST = oracle.StartDecl(0.35, 0.60, 0.01, oracle.KC)
N = ST.n()


def walk_of(field, table):
    return navigate.walk(lambda j: oracle.reading(field, ST.k(j), table), N)


def b1(K):   # honest ends, ZERO at every interior probe
    return {K < 0.36: S.SIG_MINUS, K > 0.59: S.SIG_PLUS}.get(True, S.ZERO)


with tempfile.TemporaryDirectory() as t:
    for lo, hi in ((0.35, 0.60), (0.40, 0.48)):
        lines, status = oracle.cli(Path(t), ["declared", "--start", str(lo), str(hi), "--dk", "0.01"])
        check(f"M-PoC start [{lo}, {hi}]: BRACKET [0.44, 0.45], status 0, lines returned not printed", status == 0 and lines[-1] == "navigate declared: BRACKET [0.44, 0.45]", lines[-1])
    log = [json.loads(ln) for ln in (Path(t) / "results" / "navigate" / "declared.access.jsonl").read_text().splitlines()]
    want = {"path": "declared:exact", "size": 0, "route": "declared"}
    check("E-LOG: one record per probe, route declared, fields as specified", len(log) > 0 and all(r[k] == v for r in log for k, v in want.items()) and all(r["partition"].startswith("declared:") and r["sha256"] and "pid" in r and "argv" in r and "git_head" in r for r in log), str(log[:1]))
    lines, status = oracle.cli(Path(t), ["declared", "--start", "0.35"])
    check("usage refusal is a value (status 2), not an exception", status == 2 and lines[0].startswith("REFUSED"), str(lines))

w = walk_of(oracle.EXACT, oracle.MOVE_LIVE)
check("exact field walk: BRACKET one node wide, straddling K_c", w.outcome == "BRACKET" and w.hi - w.lo == 1 and ST.k(w.lo) < oracle.KC < ST.k(w.hi), str((w.outcome, w.lo, w.hi)))

w1 = walk_of(b1, oracle.MOVE_LIVE)
w1_red = walk_of(b1, navigate.MOVE)
check("B1 GREEN: ZERO-pinned interior ends UNRESOLVED under MOVE_LIVE", w1.outcome == "UNRESOLVED", w1.outcome)
check("B1 seen RED: the same reader on navigate.MOVE stops (a false location)", w1_red.outcome == "STOP", w1_red.outcome)

inverted = lambda K: {True: S.SIG_PLUS, False: S.SIG_MINUS}[K < oracle.KC]  # noqa: E731
swap = {k: {"lo": "hi", "hi": "lo"}.get(v, v) for k, v in oracle.MOVE_LIVE.items()}
check("B2: inverted field REFUSEs under MOVE_LIVE", walk_of(inverted, oracle.MOVE_LIVE).outcome == "REFUSE")
check("B2 seen RED: the lo/hi-swapped table bisects to a false BRACKET", walk_of(inverted, swap).outcome == "BRACKET", walk_of(inverted, swap).outcome)
check("B3: literal-uniform ZERO REFUSEs", walk_of(lambda K: S.ZERO, oracle.MOVE_LIVE).outcome == "REFUSE")

check("MOVE_LIVE total over Sign + {None}", set(oracle.MOVE_LIVE) == set(Sign) | {None})
check("MOVE_LIVE maps MID to unresolved where navigate.MOVE stops", oracle.MOVE_LIVE[S.ZERO] == "unresolved" and navigate.MOVE[S.ZERO] == "stop")
ne = oracle.reading(lambda K: None, 0.4, oracle.MOVE_LIVE)
check("not established -> the _refuse-shaped Reading, move refuse", ne == navigate.Reading("REFUSE", None, None, None, 0, None, navigate.NE, "refuse"), str(ne))
live = oracle.LiveDetector(None, None, None, None)
check("Oracle dispatch total: both constructors read, LiveDetector is a total REFUSE stub", set(oracle.READERS) == {oracle.Declared, oracle.LiveDetector} and oracle.read_of(live)(3).move == "refuse")
r = subprocess.run(["git", "diff", "8d0551f", "--", "cc/navigate.py"], cwd=ROOT, capture_output=True, text=True)
check("cc/navigate.py byte-unchanged against main 8d0551f", r.returncode == 0 and r.stdout == "", r.stderr or r.stdout[:200])
# ---- plan 1282 P5: the Measured order field and the scan terminal (data-free: declared sign sequences + a synthetic loader fixture; 0 core-h)
import ast  # noqa: E402
import hashlib  # noqa: E402
import numpy as np  # noqa: E402
import oracle_measured  # noqa: E402
import schema  # noqa: E402

KS = oracle.StartDecl(0.40, 0.48, 0.01, oracle.KC)
NK = KS.n()
KCV = oracle.KC


def fake_of(rule):
    """a bare K -> Sign field, wrapped through the module-level oracle.reading (no .name needed): j -> navigate.Reading"""
    return lambda j: oracle.reading(rule, KS.k(j), oracle.MOVE_LIVE)


def band(lo_edge, hi_edge):   # SIG- below lo_edge, UNRES on [lo_edge, hi_edge], SIG+ above (nodes are 0.01 apart, 1e-9 guards the float grid)
    return lambda K: {K < lo_edge - 1e-9: S.SIG_MINUS, K > hi_edge + 1e-9: S.SIG_PLUS}.get(True, S.UNRES)


def scan_of(rule):
    return oracle_measured.scan(fake_of(rule), NK)


def ks(w):
    return KS.k(w.lo), KS.k(w.hi)


faithful = lambda K: band(KCV - 0.015, KCV + 0.015)(K)  # noqa: E731
wf = scan_of(faithful)
unres = [j for j, r in wf.trace if r.move == "unresolved"]
check("B-CONTAIN: faithful field with an UNRES band -> BRACKET containing K_c, >= 2 interior UNRES nodes", wf.outcome == "BRACKET" and ks(wf)[0] < KCV < ks(wf)[1] and len(unres) >= 2 and wf.lo < min(unres) and max(unres) < wf.hi, str((wf.outcome, ks(wf), unres)))
check("B-CONTAIN: the bracket is [last SIG-, first SIG+] = [0.42, 0.46]", wf.outcome == "BRACKET" and tuple(round(k, 2) for k in ks(wf)) == (0.42, 0.46), str(ks(wf)))

moves = [r.move for _, r in wf.trace]
first_unres = moves.index("unresolved")
mut_lo, mut_hi = KS.k(first_unres), KS.k(first_unres + 1)   # (i) band-collapse mutant: [first_unres, first_unres + 1]
check("B-CONTAIN-MUTANT (i) seen RED: the band-collapse fold's bracket EXCLUDES K_c", not (mut_lo < KCV < mut_hi), str((mut_lo, mut_hi)))
ww = navigate.walk(fake_of(faithful), NK)
check("B-CONTAIN-MUTANT (ii) seen RED: navigate.walk on the same field is UNRESOLVED, not BRACKET (the terminal discriminator)", ww.outcome == "UNRESOLVED" and wf.outcome == "BRACKET", ww.outcome)
check("B-CONTAIN-MUTANT: GREEN under the real fold (scan is the Measured terminal in TERMINAL)", oracle.TERMINAL[oracle.Measured] is oracle_measured.scan and oracle.TERMINAL[oracle.Exact] is navigate.walk and set(oracle.TERMINAL) == {oracle.Exact, oracle.Measured})

unfaithful = lambda K: S.SIG_MINUS if K < 0.425 else S.SIG_PLUS  # noqa: E731   # SIG+ at 0.43, below K_c = 0.4407: an unfaithful flank
wu = scan_of(unfaithful)
check("B-UNFAITHFUL-FLANK (characterization of the premise): a resolved SIG+ at 0.43 < K_c gives [0.42, 0.43], which excludes K_c", wu.outcome == "BRACKET" and not (ks(wu)[0] < KCV < ks(wu)[1]) and tuple(round(k, 2) for k in ks(wu)) == (0.42, 0.43), str((wu.outcome, ks(wu))))

zig = lambda K: S.SIG_PLUS if abs(K - 0.41) < 1e-9 else (S.SIG_MINUS if K < 0.445 else S.SIG_PLUS)  # noqa: E731   # a SIG+ at 0.41, below SIG- at 0.42..0.44
wd = scan_of(zig)
his_ = [j for j, r in wd.trace if r.move == "hi"]
check("B-DISORDERED seen REFUSE: a hi below the last lo is refused, though a hi above it exists", wd.outcome == "REFUSE" and (wd.lo, wd.hi) == (0, NK - 1) and max(his_) > 2, str((wd.outcome, wd.lo, wd.hi)))

wide = band(0.43, 0.46)
ww4 = scan_of(wide)
u4 = [j for j, r in ww4.trace if r.move == "unresolved"]
check("B-WIDE-BAND: a 4-node UNRES band still brackets, K_c inside, independent of band width", len(u4) == 4 and ww4.outcome == "BRACKET" and ks(ww4)[0] < KCV < ks(ww4)[1], str((ww4.outcome, ks(ww4), u4)))

inv = scan_of(lambda K: S.SIG_PLUS if K < KCV else S.SIG_MINUS)
check("B-ORIENT: the inverted field (SIG+ below, SIG- above) is REFUSE, never a bracket; the faithful one BRACKETs", inv.outcome == "REFUSE" and inv.outcome in {"BRACKET", "REFUSE"} and wf.outcome == "BRACKET", inv.outcome)
a_lo, b_hi = [np.full(40, 0.2)] * 10, [np.full(40, 0.5)] * 10   # big L below the partner: d < 0
orient = oracle.Measured(243, 81, 10, 2, lambda K: (a_lo, b_hi), lambda K: "")
check("B-ORIENT: the needle sign of (big < partner) is SIG-, move lo (pins SIG- = below K_c in the table)", orient(0.4) == S.SIG_MINUS and oracle.reading(orient, 0.4, oracle.MOVE_LIVE).move == "lo", str(orient(0.4)))

wa = scan_of(lambda K: S.UNRES)
check("B-ALL-UNRES: every node UNRES -> REFUSE, never a false bracket", wa.outcome == "REFUSE" and (wa.lo, wa.hi) == (0, NK - 1), str(wa.outcome))

gap = oracle.Measured(243, 81, 10, 2, lambda K: ([], []), lambda K: "")
check("B-REFUSE-GAP: under-replicated read -> cell None, move refuse (a value, not an exception)", gap(0.4) is None and oracle.reading(gap, 0.4, oracle.MOVE_LIVE).move == "refuse")
holey = lambda K: None if abs(K - 0.43) < 1e-9 else faithful(K)  # noqa: E731
wh = scan_of(holey)
check("B-REFUSE-GAP: a REFUSE node is not a flank and does not corrupt the bracket", wh.outcome == "BRACKET" and ks(wh)[0] < KCV < ks(wh)[1], str((wh.outcome, ks(wh))))
check("scan is total: SIG- everywhere and SIG+ everywhere (one flank missing) both REFUSE", scan_of(lambda K: S.SIG_MINUS).outcome == "REFUSE" and scan_of(lambda K: S.SIG_PLUS).outcome == "REFUSE")

# ---- the type, the closure, the frozen walk
meas = oracle.Measured(243, 81, 10, 2, lambda K: ([], []), lambda K: "")
check("Measured carries no K_c; both order types carry .name and .read_digest", not hasattr(meas, "kc") and not hasattr(meas, "target") and meas.name == "measured" and oracle.EXACT.name == "exact" and callable(meas.read_digest) and callable(oracle.EXACT.read_digest))
check("Exact.read_digest is the constant sha256(decl_str): the P3 log record is byte-identical", oracle.EXACT.read_digest(0.1) == oracle.EXACT.read_digest(0.9) == hashlib.sha256(oracle.EXACT.decl_str.encode()).hexdigest())
tree = ast.parse((ROOT / "cc" / "oracle_measured.py").read_text())
imported = {a.name.split(".")[0] for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names} | {n.module.split(".")[0] for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)}
check("oracle_measured imports nothing from oracle, detect or door (outside the measure_hash closure; no cycle)", not imported & {"oracle", "detect", "door"} and {"navigate", "sampler"} <= imported, str(sorted(imported)))
r5 = subprocess.run(["git", "diff", "150b3fe", "--", "cc/navigate.py"], cwd=ROOT, capture_output=True, text=True)
check("cc/navigate.py byte-unchanged against the P3 tip 150b3fe", r5.returncode == 0 and r5.stdout == "", r5.stderr or r5.stdout[:200])
check("MeasuredStart spans the 7 non-uniform labels", oracle_measured.MeasuredStart(oracle_measured.GRID, KCV).n() == 7 and oracle_measured.MeasuredStart(oracle_measured.GRID, KCV).k(3) == oracle_measured.sampler.LABELS["1.00"])

# ---- the loader fixture: production layout (1282/<run>/<STEM>), real load_rehearsal -> navigate.needle, then the whole CLI
rng = np.random.default_rng(0)


def write_chain(run, label, L, c, mean, flat=None):
    run.mkdir(parents=True, exist_ok=True)
    G = np.zeros((40, oracle_measured.sampler.SIZES[L])) + mean
    G[:, -1] = flat if flat is not None else mean + rng.normal(0, 0.01, 40)
    np.savez(run / oracle_measured.STEM.format(family="poc", label=label, L=L, start="random", chain=c), O=np.zeros((40, 2)), G=G, L=np.array(L), K=np.array(float(label)))


def write_label(root, label, run="rung1-aaaaaaaaaaaa", sign_=1.0, mid=False):
    for c in range(10):
        write_chain(root / "1282" / run, label, 243, c, 0.0, flat=(0.3 if c % 2 else -0.3) if mid else 0.5 + 0.3 * sign_)
        write_chain(root / "1282" / run, label, 81, c, 0.0, flat=0.0 if mid else 0.5)


with tempfile.TemporaryDirectory() as t:
    dr = Path(t) / "data"
    for label in oracle_measured.GRID:
        write_label(dr, label, sign_={True: -1.0, False: 1.0}[float(label) < 1.0], mid=label == "1.00")
    K98 = oracle_measured.sampler.LABELS["0.98"]
    a, b = oracle_measured.load_rehearsal(dr, K98)
    cell = navigate.needle(a, b, 10, 2).cell
    check("loader fixture: load_rehearsal -> navigate.needle reads a resolved Sign from the production layout", len(a) == 10 and len(b) == 10 and cell == S.SIG_MINUS, str((len(a), len(b), cell)))
    check("loader: the final-level g1 (shape (N,)), as lists not np.stack", isinstance(a, list) and a[0].shape == (40,))
    check("file_shas: bytes-only digest of the files read; 20 files; stable", oracle_measured.file_shas(dr, K98) == oracle_measured.file_shas(dr, K98) != hashlib.sha256().hexdigest() and len(oracle_measured.paths(dr, K98)[243]) == 10)
    check("loader: an absent label is an empty read (needle REFUSE), not an exception", oracle_measured.load_rehearsal(dr / "nowhere", K98) == ([], []) and oracle_measured.file_shas(dr / "nowhere", K98) == hashlib.sha256().hexdigest())
    write_chain(dr / "1282" / "rung0", "0.98", 243, 0, 0.0)   # a second run dir now holds the same (label, L, chain): AMBIGUOUS
    check("loader: >= 2 run dirs matching one chain is AMBIGUOUS -> ([], []) -> REFUSE, never a silent pick", oracle_measured.load_rehearsal(dr, K98) == ([], []) and navigate.needle(*oracle_measured.load_rehearsal(dr, K98), 10, 2).cell is None)
    (dr / "1282" / "rung0" / oracle_measured.STEM.format(family="poc", label="0.98", L=243, start="random", chain=0)).unlink()
    schema.DATA_ROOT_FLAG = str(dr)
    try:
        repo = Path(t) / "repo"
        lines, status = oracle.cli(repo, ["measured", "--L", "243"])
        check("CLI measured on the fixture: BRACKET [0.4319, 0.4495] (labels 0.98..1.02) containing K_c, status 0", status == 0 and lines[-1] == "navigate measured: BRACKET [0.4319, 0.4495]", str(lines[-1:]))
        mlog = [json.loads(ln) for ln in (repo / "results" / "navigate" / "measured.access.jsonl").read_text().splitlines()]
        check("E-LOG measured: one record per node, partition measured:, per-node bytes digest recorded BEFORE use, distinct per label", len(mlog) == 7 and all(r["partition"].startswith("measured:") and r["path"] == "declared:measured" for r in mlog) and len({r["sha256"] for r in mlog}) == 7, str(mlog[:1]))
        lines, status = oracle.cli(repo, ["measured", "--L", "27"])
        check("CLI measured: an L with no declared partner is a NAMED REFUSE (status 2)", status == 2 and lines[0].startswith("REFUSED") and "no declared partner" in lines[0], str(lines))
    finally:
        schema.DATA_ROOT_FLAG = None
    empty = Path(t) / "empty"
    empty.mkdir()
    schema.DATA_ROOT_FLAG = str(empty)
    try:
        lines, status = oracle.cli(Path(t), ["measured", "--L", "243"])
        check("CLI measured with no data: a NAMED REFUSE value at status 2, not a crash", status == 2 and lines[0].startswith("REFUSED") and "no 1282/<run>/" in lines[0], str(lines))
    finally:
        schema.DATA_ROOT_FLAG = None

sys.exit(int(bool(__import__("lib").bad)))
