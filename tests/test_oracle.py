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
check("B-CONTAIN-MUTANT: GREEN under the real fold (scan is the Measured terminal in TERMINAL)", oracle.TERMINAL[oracle.Measured] is oracle_measured.scan and oracle.TERMINAL[oracle.Exact] is navigate.walk and set(oracle.TERMINAL) == {oracle.Exact, oracle.Measured, oracle.Reweight})   # plan 1456 WIDTH: Reweight joins the terminal closed-world as a band field (TERMINAL[Reweight] is scan, asserted in the WIDTH block below)

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

# ===================== plan 1456 WIDTH: the dense Ferrenberg-Swendsen reweight navigator (a sibling band field BESIDE Measured) =====================
import sign  # noqa: E402
import oracle_reweight as orw  # noqa: E402

KIW = orw.KI
DKD = orw.DK_DENSE
STW = orw.dense_start(oracle.KC)
NW = STW.n()
ksw = lambda w: (STW.k(w.lo), STW.k(w.hi))  # noqa: E731


def scan_rw(order):
    return oracle_measured.scan(lambda j: oracle.reading(order, STW.k(j), oracle.MOVE_LIVE), NW)   # the Measured terminal, on a dense grid


def mk_load(gen, nchain=10):
    return {L: {(li, c): gen(li, c, L) for li in range(7) for c in range(nchain)} for L in (243, 81)}   # {L: {(label_index, chain): (X, g1)}}


# ---- B-RECOVER (GREEN): the binless FS estimator is correct math (self-consistency + single-source identity + loose pooled band + the sign-blind finding)
rrw = np.random.default_rng(1)
Xlw = [rrw.normal(k, 1.0, 300) for k in KIW]
Niw = np.array([len(x) for x in Xlw])
Xcw = np.concatenate(Xlw)
fsw = orw.fs_solve(Xcw, KIW, Niw)
Dcw = orw._logdenom(Xcw, KIW, Niw, fsw)
rec_err = max(abs(orw._lse(KIW[i] * Xcw - Dcw, 0) - fsw[i]) for i in range(7))
check("B-RECOVER GREEN (ii) multi-source: the binless FS exp(f_i) self-consistency identity sum_a exp(K_i X_a - D_a) = exp(f_i) holds EXACTLY across the 7 pooled sources (< 1e-10)", rec_err < 1e-10, f"max identity err {rec_err:.2e}")
x0 = Xlw[0]
g0 = 2 * x0 + 1   # an affine g1 series on label 0's samples
gm0, xm0s = orw.reweighted(x0, g0, KIW[:1], np.array([len(x0)]), KIW[0])
check("B-RECOVER GREEN (i) single-source: reweighting ONE label to its OWN K_i recovers that label's plain sample mean of BOTH g1 AND X to float tolerance", abs(gm0 - g0.mean()) < 1e-9 and abs(xm0s - x0.mean()) < 1e-9, f"<g1>={gm0:.6f} vs {g0.mean():.6f}; <X> diff {abs(xm0s - x0.mean()):.1e}")
bands = [abs(float((Xcw * orw.weights(Xcw, KIW, Niw, KIW[i], fsw)).sum()) - Xlw[i].mean()) for i in range(7)]
check("B-RECOVER GREEN (ii) multi-source loose pooled band: the pooled <X>_{K_i} is NEAR label i's mean within a LOOSE statistical band (<0.25) but is NOT float-equal (the WHAM optimal combined estimate is not the plain label mean -- never asserted as equality)", all(1e-4 < b < 0.25 for b in bands), f"bands {[round(b, 3) for b in bands]}")
ff0 = orw.fs_solve(-Xcw, KIW, Niw)
Df0 = orw._logdenom(-Xcw, KIW, Niw, ff0)
flip_err = max(abs(orw._lse(KIW[i] * (-Xcw) - Df0, 0) - ff0[i]) for i in range(7))
check("B-RECOVER FINDING (sign-blind): a conjugate-sign FLIP still satisfies the self-consistency identity, so B-RECOVER alone does NOT verify the sign convention -- B-ENERGY-DIRECTION is what pins it", flip_err < 1e-10, f"flipped-sign identity err {flip_err:.2e} (passes -> cannot catch the flip)")

# ---- B-ENERGY-DIRECTION (seen RED): d<X>/dK = Var > 0 (fluctuation-response); flip the conjugate sign and it is -Var < 0 (RED)
K0 = 0.44
eps = 1e-4
wq = orw.weights(Xcw, KIW, Niw, K0, fsw)
Xm0 = float((Xcw * wq).sum())
Varw = float(((Xcw - Xm0) ** 2 * wq).sum())
slope = (float((Xcw * orw.weights(Xcw, KIW, Niw, K0 + eps, fsw)).sum()) - Xm0) / eps
slope_flip = (float((Xcw * orw.weights(-Xcw, KIW, Niw, K0 + eps, ff0)).sum()) - float((Xcw * orw.weights(-Xcw, KIW, Niw, K0, ff0)).sum())) / eps
check("B-ENERGY-DIRECTION seen RED: with the conjugate (energy) sign FLIPPED, d<X>/dK = -Var < 0 -- the wrong-direction response an energy-blind mutant would report", slope_flip < 0, f"flipped slope {slope_flip:.4f}")
check("B-ENERGY-DIRECTION GREEN: the honest d<X>/dK equals the reweighted variance Var > 0 (fluctuation-response identity)", slope > 0 and abs(slope - Varw) < 1e-2 * Varw, f"slope {slope:.4f} == Var {Varw:.4f}")

# ---- B-CROSS (GREEN): the faithful dense field brackets K_c with an interior UNRES band (big g1=X -> <g1>_K=K; small g1=K_c const -> Delta=K-K_c)
rcw = np.random.default_rng(11)
cross = mk_load(lambda li, c, L: (lambda X: (X, X.copy() if L == 243 else np.full(len(X), oracle.KC)))(rcw.normal(KIW[li], 1.0, 600)))
rw_cross = orw.Reweight(243, 81, 10, 2, cross, "d")
wc = scan_rw(rw_cross)
uc = [j for j, r in wc.trace if r.move == "unresolved" and wc.lo < j < wc.hi]
widthc = (wc.hi - wc.lo) * DKD
check("B-CROSS GREEN: the faithful dense field BRACKETs, K_c inside, >= 1 interior UNRES node (the honest band); width = (band+1)*DK_DENSE (B2), >0.01 here is the honest alternative outcome, not scored red", wc.outcome == "BRACKET" and ksw(wc)[0] < oracle.KC < ksw(wc)[1] and len(uc) >= 1, str((wc.outcome, [round(k, 4) for k in ksw(wc)], f"band={len(uc)}", f"width={widthc:.4f}")))

# ---- B-ORIENT (GREEN): the inverted pair (Delta = K_c - K) REFUSEs, never a false bracket
roi = np.random.default_rng(21)
inv = mk_load(lambda li, c, L: (lambda X: (X, np.full(len(X), oracle.KC) if L == 243 else X.copy()))(roi.normal(KIW[li], 1.0, 400)))
wiv = scan_rw(orw.Reweight(243, 81, 10, 2, inv, "d"))
check("B-ORIENT GREEN: the inverted pair (big=const K_c, small=X: Delta = K_c - K, SIG+ below) REFUSEs, never a false bracket; the faithful one BRACKETs", wiv.outcome == "REFUSE" and wc.outcome == "BRACKET", wiv.outcome)

# ---- B-UNDERREP-REFUSE (seen REFUSE): fewer than m matched pools -> None -> refuse
under = {243: {k: v for k, v in cross[243].items() if k != (0, 0)}, 81: cross[81]}   # chain 0 is no longer complete in big -> < m matched pools
check("B-UNDERREP-REFUSE seen REFUSE: fewer than m=10 matched pools -> Reweight(K) is None -> refuse (a REFUSE value, never a clamp)", orw.Reweight(243, 81, 10, 2, under, "d")(0.44) == orw.Refusal("under_replication"), "under-replicated -> Refusal(under_replication)")

# ---- B-NONMONOTONE-REFUSE (seen REFUSE, inherited): a disordered sign sequence refuses
zigw = lambda K: S.SIG_PLUS if abs(K - STW.k(2)) < 1e-9 else (S.SIG_MINUS if K < oracle.KC else S.SIG_PLUS)  # noqa: E731
wz = oracle_measured.scan(lambda j: oracle.reading(zigw, STW.k(j), oracle.MOVE_LIVE), NW)
check("B-NONMONOTONE-REFUSE seen REFUSE: a hi below the last lo -> scan disordered -> REFUSE (inherited P5 fold, not a WIDTH-specific guard)", wz.outcome == "REFUSE", wz.outcome)

# ---- B-IGNORE-E (i) W=1 (seen RED by REFUSE): drop the energy weights -> Delta is K-independent -> no sign change -> scan REFUSE
def delta_W1(load, K):
    d = np.array([np.concatenate([load[243][(li, c)][1] for li in range(7)]).mean() - np.concatenate([load[81][(li, c)][1] for li in range(7)]).mean() for c in range(10)])
    lo, hi = navigate.interval(d, 10, 2)
    return sign.sign(lo, hi, navigate.EPS)[0]
wW1 = oracle_measured.scan(lambda j: oracle.reading(lambda K: delta_W1(cross, K), STW.k(j), oracle.MOVE_LIVE), NW)
check("B-IGNORE-E (i) W=1 seen RED (REFUSE): dropping the energy weights makes Delta(K) K-independent -> no sign change -> scan REFUSE (the real field BRACKETs)", wW1.outcome == "REFUSE" and wc.outcome == "BRACKET", wW1.outcome)

# ---- B-IGNORE-E (ii) coarse-grid interpolation (seen RED by exclusion): FINDING -- displacement is a RED only on a COARSE grid; at native spacing it coincides (~2e-5)
rI = np.random.default_rng(6)
Kcoarse = np.array([0.20, 0.45, 0.70])
cI = 1.0 + 0.45 ** 2   # <g1>_K = <X^2>_K = 1 + K^2 (nonlinear); true FS crossing at K=0.45
XIl = [rI.normal(k, 1.0, 4000) for k in Kcoarse]
NiI = np.array([len(x) for x in XIl])
XI = np.concatenate(XIl)
gI = XI ** 2
fI = orw.fs_solve(XI, Kcoarse, NiI)
dltI = lambda K: float((gI * orw.weights(XI, Kcoarse, NiI, K, fI)).sum()) - cI  # noqa: E731
lo_, hi_ = 0.20, 0.70
for _ in range(60):
    mid = (lo_ + hi_) / 2
    lo_, hi_ = (mid, hi_) if dltI(mid) < 0 else (lo_, mid)
Kfs = (lo_ + hi_) / 2
meanI = np.array([gI[NiI[:i].sum():NiI[:i + 1].sum()].mean() - cI for i in range(3)])
Kinterp = float(np.interp(0.0, meanI, Kcoarse))
check("B-IGNORE-E (ii) coarse-grid interpolation seen RED: linear interp of point means displaces the crossing >= 2*DK_DENSE from the FS crossing (an excluding bracket). FINDING: at native 0.0088 spacing the two coincide (~2e-5) -- the W=1 REFUSE is the RED at native spacing, not displacement", abs(Kfs - Kinterp) >= 2 * DKD, f"FS {Kfs:.5f} interp {Kinterp:.5f} disp {abs(Kfs - Kinterp):.5f}")

# ---- B-GAP-REFUSE (seen REFUSE; the honest null): per-label coverage refuses where the global hull (the tautology) would not
rg = np.random.default_rng(4)
gapl = mk_load(lambda li, c, L: (lambda X: (X, X.copy() if L == 243 else np.full(len(X), 9.0)))(rg.normal(li * 3.0, 0.02, 300)))   # 7 tight disjoint clusters: the reweighted mean lands between clusters
rw_gap = orw.Reweight(243, 81, 10, 2, gapl, "d")
wg = scan_rw(rw_gap)
refuses = sum(1 for j in range(NW) if rw_gap(STW.k(j)) == orw.Refusal("coverage"))
jref = next(j for j in range(NW) if rw_gap(STW.k(j)) == orw.Refusal("coverage"))
Xg, gg, Nig = orw._pool(gapl[243], 0)
xbar = orw.reweighted(Xg, gg, KIW, Nig, STW.k(jref))[1]
allX = np.concatenate([gapl[243][(li, 0)][0] for li in range(7)])
check("B-GAP-REFUSE seen REFUSE: a two-cluster support gap -> the per-label energy-coverage null fails at >= 40/45 dense nodes -> scan REFUSE, not a false bracket", wg.outcome == "REFUSE" and refuses >= 40, f"per-label refuses {refuses}/{NW}, scan {wg.outcome}")
check("B-GAP-REFUSE RED for the mutant: the global-hull predicate (the tautology) COVERS at a refusing node, so a mutant using it would resolve a false reading", allX.min() <= xbar <= allX.max() and rw_gap(STW.k(jref)) == orw.Refusal("coverage"), f"<X>={xbar:.3f} in hull [{allX.min():.2f},{allX.max():.2f}] yet per-label refuses")

# ---- B-FS-CONVERGE (GREEN + seen REFUSE): gauge invariance; a non-converging solve is None -> refuse (never a clamp)
wgauge = float(np.max(np.abs(orw.weights(Xcw, KIW, Niw, K0, fsw) - orw.weights(Xcw, KIW, Niw, K0, fsw + 3.7))))
check("B-FS-CONVERGE GREEN: the FS solve converges and the reweight weights are gauge-invariant under f -> f + const (< 1e-12)", fsw is not None and wgauge < 1e-12, f"max|dw| {wgauge:.1e}")
_sv = orw.FS_MAXIT
orw.FS_MAXIT = 1
nonconv = rw_cross(0.44)
fnone = orw.fs_solve(Xcw, KIW, Niw)
orw.FS_MAXIT = _sv
check("B-FS-CONVERGE seen REFUSE: a non-converging FS solve (FS_MAXIT=1) returns None -> Reweight refuses; restored, it reads again (a REFUSE value, never a clamp)", fnone is None and nonconv == orw.Refusal("fs_nonconverge") and rw_cross(0.44) is not None, str((fnone, nonconv)))

# ---- B-FINITE-L (premise characterization): the bracket contains K* unconditionally; K_c only if |K*-K_c| <= half-width
rf = np.random.default_rng(7)
off = 0.02
fll = mk_load(lambda li, c, L: (lambda X: (X, X.copy() if L == 243 else np.full(len(X), oracle.KC + off)))(rf.normal(KIW[li], 1.0, 2000)))   # N large -> a narrow band so K* is cleanly bracketed near span center
wfl = scan_rw(orw.Reweight(243, 81, 10, 2, fll, "d"))
ksf = ksw(wfl)
Kstar = oracle.KC + off
check("B-FINITE-L (premise characterization): a crossing K* offset from K_c is bracketed UNCONDITIONALLY; K_c is contained only if |K*-K_c| <= half-width (off=0.02 >> half-width here -> K_c excluded, reported not scored red)", wfl.outcome == "BRACKET" and ksf[0] < Kstar < ksf[1] and not (ksf[0] < oracle.KC < ksf[1]), str((wfl.outcome, [round(k, 4) for k in ksf])))

# ---- structure: the sum type, the closure exclusion (measure_hash unchanged), the declared report, no new cutoff
check("TERMINAL[Reweight] is scan (the dense band field scans like Measured); the terminal closed-world is {Exact, Measured, Reweight}", oracle.TERMINAL[oracle.Reweight] is oracle_measured.scan and set(oracle.TERMINAL) == {oracle.Exact, oracle.Measured, oracle.Reweight})
check("Reweight carries .name='reweight' and a CONSTANT read_digest, and NO K_c/target (K_c lives only on the SCORER's DenseStart.target)", orw.Reweight.name == "reweight" and not hasattr(rw_cross, "kc") and not hasattr(rw_cross, "target") and rw_cross.read_digest(0.1) == rw_cross.read_digest(0.9))
check("DenseStart spans the 7-label range at DK_DENSE and carries its OWN labels tuple (B6); K_c is on target, read by the scorer alone", STW.labels == tuple(oracle_measured.GRID) and abs(STW.lo - oracle_measured.sampler.LABELS[oracle_measured.GRID[0]]) < 1e-12 and STW.dk == DKD and STW.target == oracle.KC)
treew = ast.parse((ROOT / "cc" / "oracle_reweight.py").read_text())
impw = {a.name.split(".")[0] for n in ast.walk(treew) if isinstance(n, ast.Import) for a in n.names} | {n.module.split(".")[0] for n in ast.walk(treew) if isinstance(n, ast.ImportFrom)}
check("oracle_reweight imports nothing from oracle, detect or door (acyclic; outside the measure_hash closure)", not impw & {"oracle", "detect", "door"} and {"navigate", "oracle_measured", "sign", "sampler"} <= impw, str(sorted(impw)))
instr = [f"cc/instruments/{p.stem}.py" for p in sorted((ROOT / "cc" / "instruments").glob("*.py"))]
clos = schema.import_closure(ROOT, ["cc/detect.py", "cc/door.py", *instr])
check("oracle_reweight.py AND oracle.py are OUTSIDE the measure_hash import closure (detect/door/instruments) -> WIDTH leaves measure_hash byte-identical", "cc/oracle_reweight.py" not in clos and "cc/oracle.py" not in clos, f"{len(clos)} closure files, oracle* absent")

# ---- the loader fixture: the production layout (1282/<run>/<STEM>) with a real energy array O, driving the REAL CLI reweight end to end
rng2 = np.random.default_rng(3)


def write_rw_chain(run, label, L, c, slope, const):
    run.mkdir(parents=True, exist_ok=True)
    k = oracle_measured.sampler.LABELS[label]
    X = rng2.normal(k, 1.0, 800)
    G = np.zeros((800, oracle_measured.sampler.SIZES[L]))
    G[:, -1] = const + slope * X
    O = np.zeros((800, 2))
    O[:, 0] = X   # the conjugate X = energy level 0, paired per configuration with g1
    np.savez(run / oracle_measured.STEM.format(family="poc", label=label, L=L, start="random", chain=c), O=O, G=G, L=np.array(L), K=np.array(k))


with tempfile.TemporaryDirectory() as t:
    dr = Path(t) / "data"
    run = dr / "1282" / "rung1-aaaaaaaaaaaa"
    for label in oracle_measured.GRID:
        for c in range(10):
            write_rw_chain(run, label, 243, c, 1.0, 0.0)        # big: g1 = X -> <g1>_K = K
            write_rw_chain(run, label, 81, c, 0.0, oracle.KC)   # small: g1 = K_c const -> Delta = K - K_c (crossing at K_c)
    schema.DATA_ROOT_FLAG = str(dr)
    try:
        repo = Path(t) / "repo"
        lines, status = oracle.cli(repo, ["reweight", "--L", "243"])
        br = lines[-1]
        lo_b, hi_b = (float(x) for x in br.split("[")[1].rstrip("]").split(","))
        rlog = [json.loads(ln) for ln in (repo / "results" / "navigate" / "reweight.access.jsonl").read_text().splitlines()]
        check("WIDTH loader fixture: the REAL CLI `reweight --L 243` returns status 0 and a BRACKET header line", status == 0 and lines[0].startswith("navigate reweight (L 243 vs 81") and br.startswith("navigate reweight: BRACKET"), str(lines[-1:]))
        check("WIDTH loader fixture: the dense BRACKET contains K_c (the faithful synthetic crossing)", br.startswith("navigate reweight: BRACKET") and lo_b < oracle.KC < hi_b, br)
        check("WIDTH loader fixture: the access log holds one declared record per dense node (45), partition reweight:, path declared:reweight, written BEFORE use", len(rlog) == NW and all(r["partition"].startswith("reweight:") and r["path"] == "declared:reweight" and r["route"] == "declared" for r in rlog), f"{len(rlog)} records vs {NW}")
        l2, s2 = oracle.cli(repo, ["reweight", "--L", "27"])
        check("WIDTH CLI: an L with no declared partner is a NAMED REFUSE (status 2)", s2 == 2 and l2[0].startswith("REFUSED") and "no declared partner" in l2[0], str(l2[:1]))
    finally:
        schema.DATA_ROOT_FLAG = None
    empty2 = Path(t) / "empty2"
    empty2.mkdir()
    schema.DATA_ROOT_FLAG = str(empty2)
    try:
        l3, s3 = oracle.cli(Path(t), ["reweight", "--L", "243"])
        check("WIDTH CLI: no 1282/<run>/ data -> a NAMED REFUSE at status 2, not a crash", s3 == 2 and l3[0].startswith("REFUSED") and "no 1282/<run>/" in l3[0], str(l3[:1]))
    finally:
        schema.DATA_ROOT_FLAG = None

# ---- plan 1458 P1: an arm DEFECT propagates (never masked as the usage refusal); a real usage error still refuses at status 2
with tempfile.TemporaryDirectory() as t:
    dr = Path(t) / "data"
    run = dr / "1282" / "rung1-bbbbbbbbbbbb"
    for label in oracle_measured.GRID:
        for c in range(10):
            write_rw_chain(run, label, 243, c, 1.0, 0.0)
            write_rw_chain(run, label, 81, c, 0.0, oracle.KC)
            p243 = run / oracle_measured.STEM.format(family="poc", label=label, L=243, start="random", chain=c)
            z = np.load(p243)
            np.savez(p243, O=z["O"][:, 0], G=z["G"], L=z["L"], K=z["K"])   # a malformed npz: 1-D O (O = X, not column_stack)
    schema.DATA_ROOT_FLAG = str(dr)
    try:
        try:
            got = oracle.cli(Path(t) / "repo", ["reweight", "--L", "243"])   # base behaviour: returned the usage tuple (..., 2) -- a defect masked as a CLI typo
        except IndexError:
            got = "IndexError"
        check("B1a: a malformed npz (1-D O) in the reweight arm RAISES IndexError (an arm defect propagates), not the status-2 usage refusal", got == "IndexError", str(got)[:120])
    finally:
        schema.DATA_ROOT_FLAG = None
    for nm, av in (("no --L", ["reweight"]), ("missing operand", ["declared", "--start", "0.35"]), ("no --dk", ["declared", "--start", "0.35", "0.60"]), ("unknown arm", ["bogus"])):
        lu, su = oracle.cli(Path(t), av)
        check(f"B1b: a genuine usage error ({nm}) still returns the usage REFUSE at status 2", su == 2 and lu[0].startswith("REFUSED"), str((lu[:1], su)))

# ---- plan 1458 P2 (B2a): the three refusal reasons are typed and pairwise distinct
_R = getattr(orw, "Refusal", None)
_rs = [orw.Reweight(243, 81, 10, 2, under, "d")(0.44), rw_gap(STW.k(jref))]
orw.FS_MAXIT = 1
_rs.append(rw_cross(0.44))
orw.FS_MAXIT = _sv
check("B2a: under-replication, coverage and fs-nonconvergence are three PAIRWISE-DISTINCT typed Refusal values", _R is not None and _rs == [_R("under_replication"), _R("coverage"), _R("fs_nonconverge")] and len(set(_rs)) == 3, str(_rs))
_ok = rw_cross(0.44)
check("B2b: a well-overlapped fixture still reads a normal Sign (typing the null does not refuse the happy path)", isinstance(_ok, Sign), str(_ok))
_rd = oracle.reading(lambda K: _R and _R("coverage"), 0.44, oracle.MOVE_LIVE)
check("B2c: reading() of a Refusal keeps cell None / move refuse and carries the reason in status", _R is not None and _rd.cell is None and _rd.move == "refuse" and "coverage" in _rd.status, str(_rd))

sys.exit(int(bool(__import__("lib").bad)))
