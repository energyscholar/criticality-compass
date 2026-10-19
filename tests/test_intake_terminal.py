"""test_intake_terminal - plan 1160 P6: S10 KERNEL_HANDOFF and the terminal (cc/intake_terminal.py), plan 1118's REDUCE as A over a declared chain.
 T1. The synthetic quickstart bank (intake_synth, seed 1, 9 curves) reaches Located, and its span holds h*. The truth is read HERE, from the
     truth file intake_synth writes beside the bank, never by a stage.
 T2. Planted chains through the terminal's own path (door.nodefield, the chain relation, kernel.A, the result): RESOLVED; EXPLORATORY when
     sigma is made 100 times larger; UNTIERED when no sigma is given (tiering NONE), n_tied NOT_EVALUATED and the span the flanking ranks; a
     plateau of three tied maxima gives n_tied = 3; MaxAtPathEnd at either end; NoInteriorMaximum for ARGMAX_FAST on a monotone chain.
 T3. End to end on the synthetic bank: its first four curves (h below h*) give MaxAtPathEnd; ARGMAX_FAST as the PRIMARY projection on
     a planted noise-free ridge (each curve's peak T rises with h) gives NoInteriorMaximum (on the noisy synthetic bank the argmax T is not
     monotone in h, so it finds a local maximum: printed as information); interval NONE gives UNTIERED; [shift] c = -1000.5 gives the same result as
     c = 0 (x + c is applied at S10 only, and A takes differences).
 T4. Port equality: on 60 seeded random banks (5 to 12 curves, 20 to 60 points each, some monotone), the terminal's MAX_MEASURED result equals
     plan 1118's reduce_ (studies/DIAL1118/dial/methods.py, run in a subprocess, read only: -B, no bytecode written there): a Bracket is a
     Located with the same flanking ranks and tier when n_tied = 1 (the same m and tier, and a span that holds 1118's, when n_tied > 1);
     Refuse("max at path end") is MaxAtPathEnd.
Seen RED: see the P6.2 lines of the scratchpad's p6-seenred.txt (each mutation applied, the test run, the mutation reverted)."""
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path[:0] = [str(ROOT / "cc"), str(ROOT / "tests")]
import door  # noqa: E402
import intake  # noqa: E402
import intake_data  # noqa: E402
import intake_synth  # noqa: E402
import intake_terminal as term  # noqa: E402
from intake_plant import SHIFT, long_table, per_file, run, write_long  # noqa: E402

DIAL = Path.home() / "software" / "scratch" / "wt-1118b" / "studies" / "DIAL1118" / "dial"
T = intake.tables(ROOT)
Z = T["policy"]["policy"]["tier_z"]
bad = []


def check(name, ok, why=""):
    print(("ok   " if ok else "FAIL ") + name + ("" if ok else f": {why}"))
    if not ok:
        bad.append(name)


def chain(r, s=None, bias="MAX_MEASURED"):
    """The terminal's path on planted values: door.nodefield on r (and sigma), the chain relation, A, the result."""
    xs = [door.nodefield(np.asarray(v, float), None) for v in ([r] + [s] * (s is not None))]
    return term.reduce(xs, bias, Z, term.chain(len(r)))


# ---- T2. planted chains
pk = [0.0, 1.0, 3.0, 1.0, 0.0]
check("T2. a clear interior peak, sigma 0.1: Located at rank 2, span 1..3, RESOLVED, n_tied 1", chain(pk, [0.1] * 5) == term.Located(2, 1, 3, "RESOLVED", 1), str(chain(pk, [0.1] * 5)))
check("T2. the same peak, sigma x 100: EXPLORATORY (every curve tied, n_tied 5, the span the whole chain)", chain(pk, [10.0] * 5) == term.Located(2, 0, 4, "EXPLORATORY", 5), str(chain(pk, [10.0] * 5)))
check("T2. the same peak, no sigma (tiering NONE): UNTIERED, n_tied NOT_EVALUATED, the span the flanking ranks", chain(pk) == term.Located(2, 1, 3, "UNTIERED", "NOT_EVALUATED"), str(chain(pk)))
plateau = [0.0, 1.0, 3.0, 3.0, 3.0, 1.0, 0.0]
check("T2. a plateau of three equal maxima: n_tied 3, the span their chain neighbourhood 1..5 (EXPLORATORY: the edge out of rank 2 is 0)",
      chain(plateau, [0.1] * 7) == term.Located(2, 1, 5, "EXPLORATORY", 3), str(chain(plateau, [0.1] * 7)))
check("T2. a rising chain: MaxAtPathEnd at the last rank", chain([0.0, 1.0, 2.0, 3.0, 4.0], [0.1] * 5) == term.MaxAtPathEnd(4), str(chain([0.0, 1.0, 2.0, 3.0, 4.0], [0.1] * 5)))
check("T2. a falling chain: MaxAtPathEnd at rank 0", chain([4.0, 3.0, 2.0, 1.0, 0.0], [0.1] * 5) == term.MaxAtPathEnd(0), "")
check("T2. ARGMAX_FAST on a monotone chain: NoInteriorMaximum", chain([0.0, 1.0, 2.0, 3.0, 4.0], bias="ARGMAX_FAST") == term.NoInteriorMaximum(), "")
check("T2. ARGMAX_FAST takes local maxima (plan 1118 PAIR): an interior local maximum at rank 1 is Located while the global maximum is at the end",
      chain([0.0, 2.0, 1.0, 3.0, 4.0], bias="ARGMAX_FAST") == term.Located(1, 0, 2, "UNTIERED", "NOT_EVALUATED"), str(chain([0.0, 2.0, 1.0, 3.0, 4.0], bias="ARGMAX_FAST")))
check("T2. the words of a result carry no value (only the type, ranks, tier and n_tied)", not re.search(r"\d\.\d", chain(pk, [0.1] * 5).words()), chain(pk, [0.1] * 5).words())

with tempfile.TemporaryDirectory() as tmp:
    tmp = Path(tmp)
    banks = tmp / "banks"
    intake_synth.write(banks / "pf", tmp / "pf-TRUTH", "pf", 1, 9)
    m = json.loads((banks / "pf" / "MANIFEST.json").read_text())
    h_star = json.loads((tmp / "pf-TRUTH" / "truth.json").read_text())["h_star"]   # the truth, read by the test only
    curves = [(f["h"], (banks / "pf" / f["name"]).read_text().splitlines()[1:]) for f in m["files"]]

    def s10(text, ident):
        out = run(T, tmp, ident, text)
        return out["S10"], [e.result.reason for e in out.values() if e.mark is intake.Mark.REFUSED]

    def got(text, ident):
        e, refused = s10(text, ident)
        return {True: lambda: e.result.evidence.columns[0], False: lambda: refused}[e.mark is intake.Mark.PASSED]()

    def lt(blocks, ident, edit=lambda t: t):
        (banks / ident).mkdir()
        write_long(banks / ident, blocks)
        return edit(long_table(m, ident).replace("<long-test>/pf", f"<long-test>/{ident}"))

    # ---- T1. the quickstart bank
    q = got(per_file(m, "q"), "q")
    res = getattr(q, "result", None)
    span = {True: lambda: (q.slows[res.lo_rank][0], q.slows[res.hi_rank][0]), False: lambda: None}[isinstance(res, term.Located)]()
    check("T1. the synthetic quickstart bank reaches Located over its 9 curves", isinstance(res, term.Located) and len(q.slows) == 9, str(res or q))
    check("T1. the Located span holds h* (read from the truth file by this test)", span is not None and span[0] <= h_star <= span[1], f"span {span}, h* {h_star}")
    rec = getattr(q, "record", lambda: {})()
    check("T1. the RESULT.json record's span_slow is the slow values at lo_rank and hi_rank, and holds h*",
          span is not None and rec.get("span_slow") == [list(q.slows[res.lo_rank]), list(q.slows[res.hi_rank])] and rec["span_slow"][0][0] <= h_star <= rec["span_slow"][1][0], str(rec)[:300])
    check("T1. the result names curves by rank: lo < m < hi, ranks of the slow order", span is not None and res.lo_rank < res.m < res.hi_rank and list(q.slows) == sorted(q.slows), str(res))

    # ---- T3. end to end
    low = got(lt([c for c in curves if c[0] < h_star][:4], "low"), "low")
    check("T3. the first four curves (h below h*): MaxAtPathEnd at their last rank", getattr(low, "result", None) == term.MaxAtPathEnd(3), str(getattr(low, "result", low)))
    fast = lambda t: t.replace('to = "C_max"', 'to = "T_star"', 1).replace('bias = "MAX_MEASURED"', 'bias = "ARGMAX_FAST"', 1).replace('on = "C_max"', 'on = "T_star"', 1)
    ridge = [(h, [f"{1 + 0.5 * j:.4f},{-((1 + 0.5 * j) - (5 + k)) ** 2:.4f},0.0300" for j in range(40)]) for k, (h, _) in enumerate(curves[:6])]   # each curve peaks at T = 5 + k
    af = got(lt(ridge, "af", fast), "af")
    check("T3. ARGMAX_FAST as the PRIMARY projection on a planted ridge whose peak T rises with h: NoInteriorMaximum", getattr(af, "result", None) == term.NoInteriorMaximum(), str(getattr(af, "result", af)))
    syn = got(fast(per_file(m, "as")), "as")
    print(f"  (information) ARGMAX_FAST on the noisy synthetic bank: {getattr(getattr(syn, 'result', None), 'words', lambda: syn)()}")
    un = got(per_file(m, "un").replace('method = "STATED"', 'method = "NONE"', 1), "un")
    check("T3. interval NONE (tiering NONE): Located, UNTIERED, n_tied NOT_EVALUATED, the span the flanking ranks",
          isinstance(getattr(un, "result", None), term.Located) and (un.result.tier, un.result.n_tied, un.result.hi_rank - un.result.lo_rank) == ("UNTIERED", "NOT_EVALUATED", 2), str(getattr(un, "result", un)))
    sh = got(SHIFT("-1000.5")(per_file(m, "sh")), "sh")
    check("T3. [shift] c = -1000.5 gives the result of c = 0 (x + c at S10 only; A takes differences)", getattr(sh, "result", None) == res, f"{getattr(sh, 'result', sh)} against {res}")

# ---- T4. port equality against plan 1118's reduce_
rng = np.random.default_rng(1160)
BANKS = []
for b in range(60):
    n = int(rng.integers(5, 13))
    x = np.sort(rng.uniform(-1, 1, n))
    shape = {0: lambda: rng.normal(0, 1, n), 1: lambda: np.sort(rng.normal(0, 1, n)), 2: lambda: -np.abs(x - rng.uniform(-1, 1)) * 3}[b % 3]()   # random, monotone, one peak
    cs = []
    for k in range(n):
        npt = int(rng.integers(20, 61))
        Tk = np.sort(rng.uniform(1.5, 3.5, npt))
        Ck = shape[k] + 0.5 * np.exp(-((Tk - 2.5) / 0.2) ** 2) + rng.normal(0, 0.02, npt)
        cs.append({"x": float(x[k]), "T": Tk.tolist(), "C": Ck.tolist(), "sigma": rng.uniform(0.01, 0.3, npt).tolist()})
    BANKS.append(cs)
PROBE = """import json, sys
sys.path.insert(0, sys.argv[1])
from methods import make_curve, reduce_, Z
out = []
for cs in json.load(sys.stdin):
    r = reduce_([make_curve(k, f"c{k}", c["x"], c["T"], c["C"], c["sigma"], list(range(len(c["T"])))) for k, c in enumerate(cs)])
    out.append({True: ["Bracket", r[3], r[4], r[2]] if type(r).__name__ == "Bracket" else None, False: ["Refuse", r[0]]}[type(r).__name__ == "Bracket"])
print(json.dumps({"Z": Z, "out": out}))
"""
p = subprocess.run([sys.executable, "-B", "-I", "-c", PROBE, str(DIAL)], input=json.dumps(BANKS), capture_output=True, text=True, timeout=600,
                   cwd=tempfile.gettempdir(), env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"})
check("T4. plan 1118's methods.py ran in a subprocess (read only)", p.returncode == 0 and DIAL.is_dir(), (p.stderr or str(DIAL))[-400:])
theirs = {True: lambda: json.loads(p.stdout), False: lambda: {"Z": None, "out": []}}[p.returncode == 0]()
check("T4. plan 1118's Z is POLICY's tier_z", theirs["Z"] == Z, str(theirs["Z"]))
ours = []
for cs in BANKS:
    cv = [intake_data.Curve(f"c{k}", (c["x"],), tuple(zip(c["T"], c["C"], c["sigma"])), 1) for k, c in enumerate(cs)]
    xs = [door.nodefield(v, None) for v in term.values(cv, "MAX_MEASURED", "STATED", 0.0)]
    ours.append(term.reduce(xs, "MAX_MEASURED", Z, term.chain(len(cv))))
SAME = {   # (1118's kind, ours' type) -> are they the same result; total over the pairs the two can produce
    ("Bracket", "Located"): lambda a, o: o.tier == a[3] and {True: (o.lo_rank, o.hi_rank) == (a[1], a[2]), False: o.lo_rank <= a[1] and a[2] <= o.hi_rank and o.m == a[1] + 1}[o.n_tied == 1],
    ("Bracket", "MaxAtPathEnd"): lambda a, o: False, ("Refuse", "Located"): lambda a, o: False,
    ("Refuse", "MaxAtPathEnd"): lambda a, o: a[1] == "max at path end",
}
diff = [(i, a, o) for i, (a, o) in enumerate(zip(theirs["out"], ours)) if not SAME[(a[0], type(o).__name__)](a, o)]
kinds = {(a[0], getattr(o, "tier", type(o).__name__)) for a, o in zip(theirs["out"], ours)}
print(f"  port: {len(ours)} banks; (1118, ours) kinds seen: {sorted(kinds)}")
check("T4. on every bank the terminal's result is plan 1118's reduce_ result", len(theirs["out"]) == len(ours) == 60 and not diff, str(diff[:3])[:600])
check("T4. the banks exercise a Bracket RESOLVED, a Bracket EXPLORATORY and a path-end refusal", {("Bracket", "RESOLVED"), ("Bracket", "EXPLORATORY"), ("Refuse", "MaxAtPathEnd")} <= kinds, str(sorted(kinds)))

print("test_intake_terminal: " + ("FAILED " + "; ".join(bad) if bad else "all passed"))
sys.exit(1 if bad else 0)
