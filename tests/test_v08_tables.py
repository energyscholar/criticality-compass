"""test_v08_tables - plan 0877 T2/T3/T6: the rulebook v08-rules (stability on the Delta basis, no transform; Origin declaration A on across_dlt; the dead-secondary rule D2).
Cells are read through the set's own functions. A planted CONVERGING chain is measured through detect.measure with the REAL instruments under v08-rules: every pair reads RAW
(the transform did not leak into the Delta basis), the raw exponent of the difference is read, ruling A reads its sub-eps residual MARGINAL. tables/v07-rules is byte-identical."""
import hashlib
import shutil
import sys
import tempfile
import tomllib
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
from lib import bad, bootstrap, check  # noqa: E402
bootstrap(ROOT, "cc", "cc/instruments")
import declare  # noqa: E402
import detect  # noqa: E402
import frozen  # noqa: E402


T8, T7 = detect.load_tables("v08-rules"), detect.load_tables("v07-rules")
FILES = ("codes", "compose", "family", "geometry", "membership", "order", "probe", "verdict")

# --- v07-rules is untouched: the sha256 of each of its files as they were at plan 0877's start (05f9832); plan 0985 moved the pins of codes and verdict ONCE: the only change is the wording of one comment and one description (a private ruling named by its person is named by its role)
V07 = {"codes": "c082b98285b41763ba0c1739abc847074e94c21dcf9f932420164977249b9370", "compose": "3c1b72137520285fe5bc96a76db9fc695d7ac3d552a619d7b9bccb8640a59957",
       "family": "90fb7bdef4fd6d6287ec62411e85a5e2dcf58855e2fb19318683d2b1e5248d10", "geometry": "70fb209010b59e1077458c98657e3e88e7edba6f72dc81bf7fe690575b1d60f5",
       "membership": "662350091b555b3d88494406f751a3dd1c164e60486f3f5d86b096b7c7f75f6e", "order": "ab789dc52e449c1e46ce382630894247d40d0b199ddd7724a872519f1eaf5978",
       "probe": "38a288f312a29c0a4abe3b0f93a9294d5a0e4e96cabe6b6e930bc1a1e1f6b076", "verdict": "fb661107f34393ab1b4ed8cbbce4f13587d6fca2b9e8db4ce3e488bebadb0572"}
got = {n: hashlib.sha256((ROOT / "tables" / "v07-rules" / f"{n}.toml").read_bytes()).hexdigest() for n in FILES}
check("tables/v07-rules is byte-identical to its state at the start of plan 0877 (sha256 of all eight files)", got == V07, str({n: g for n, g in got.items() if g != V07[n]}))

# --- T2: the alphabet, the rows, the witness
sig8 = T8.codes["columns"]["signature"]
check("v08-rules: the signature column stability has no TRANSFORMED, and reads stability_delta.d directly", sig8["stability"]["alphabet"] == ["STABLE", "CROSSING", "OFF", "UNRES"]
      and sig8["stability"]["from"] == "stability_delta.d" and "stability_delta.d" in detect.used(T8), str(sig8["stability"]["alphabet"]))
rows = [(n, r["when"]["stability"]) for n, ax in (("verdict", T8.verdict), ("geometry", T8.axes["geometry"][0])) for r in ax["row"] if "stability" in r["when"]]
check("no verdict or geometry row of v08-rules names TRANSFORMED", not [n for n, w in rows if "TRANSFORMED" in w], str(rows)[:200])
check("stability_raw (the covariance stability) stays declared and is read by no signature column", "stability_raw" in T8.codes["columns"]["helper"]
      and not any("stability_raw" in (c["from"] if isinstance(c["from"], list) else [c["from"]]) for c in sig8.values()))
base = {"needle": "MID", "needle_pair": "SAME-WINDOW", "sink": "NEITHER", "flow": "STOPPED", "across": "MARGINAL", "stability": "STABLE", "two_start": "INDEP", "probe": "COMPLETE", "drift_code": "CONVERGING"}


def geom(**kw):
    g, _ = T8.axes["geometry"]
    return g["row"][detect.row_of(g, {**base, **kw})]["verdict"], detect.verdict_of({**base, **kw}, T8)[0]


check("a CONVERGING point whose Delta stability CROSSES (d_D POS / SIG+) reads WALKING (the witness the transform consumed is restored)", geom(stability="CROSSING") == ("WALKING", "WALKING"), str(geom(stability="CROSSING")))
check("a CONVERGING point with d_D inside the margin (STABLE) and across MARGINAL reads LINE", geom() == ("LINE", "LINE"), str(geom()))
check("RELEVANT + STABLE reads POINT (the F1 row that sent RELEVANT + TRANSFORMED to REFUSE-UNRES is gone)", geom(across="RELEVANT") == ("POINT", "POINT"), str(geom(across="RELEVANT")))
check("a stability that is not measured refuses with its own name (an honest null, never STABLE)", geom(stability="NOT-MEASURED") == ("REFUSE-STABILITY-UNMEASURED",) * 2, str(geom(stability="NOT-MEASURED")))
stab = lambda cells: detect.codes_of({"stability_delta.d": cells}, T8)["stability"]   # noqa: E731
check("stability map: SLOW-, ZERO!, SLOW+ STABLE; POS, SIG+ CROSSING; NEG, SIG- OFF; UNRES UNRES (a CONVERGING d_D POS must read CROSSING: that is the witness)",
      [stab([c]) for c in ("SLOW-", "ZERO!", "SLOW+", "POS", "SIG+", "NEG", "SIG-", "UNRES")] == ["STABLE"] * 3 + ["CROSSING"] * 2 + ["OFF"] * 2 + ["UNRES"])
check("stability per point: every touching pair must agree: [SLOW+, ZERO!] STABLE, [SIG+, SIG+] CROSSING, [SIG-] OFF, [SLOW+, SIG+] UNRES, a null pair is that null",
      (stab(["SLOW+", "ZERO!"]), stab(["SIG+", "SIG+"]), stab(["SIG-"]), stab(["SLOW+", "SIG+"]), stab(["NOT-EVALUATED"]), stab(["ZERO!", "NOT-EVALUATED"]))
      == ("STABLE", "CROSSING", "OFF", "UNRES", "NOT-EVALUATED", "NOT-EVALUATED"))
check("an input that does not declare stability_delta reads stability NOT-MEASURED under v08-rules, and its v07 stability is the covariance one (still TRANSFORMED-capable)",
      detect.codes_of({}, T8)["stability"] == "NOT-MEASURED" and "TRANSFORMED" in T7.codes["columns"]["signature"]["stability"]["alphabet"])
check("v08-rules has no membership rule for across_delta (every pair reads the instrument's default RAW); v07-rules has one", "across_delta" not in T8.membership and "across_delta" in T7.membership)
check("the eight files of v08-rules validate (every partition proved)", not [f for n in FILES for f in declare.check_file(ROOT / "tables" / "v08-rules" / f"{n}.toml", ROOT)])

# --- ruling A: across_dlt reads a resolved sub-eps residual MARGINAL; across_cov and y_inf_code keep v07's map
dlt = lambda T, c: detect.codes_of({"across_delta.y_last": c}, T)["across_dlt"]   # noqa: E731
check("ruling A: across_dlt reads SLOW- and SLOW+ MARGINAL (v07: WEAK); ZERO! MARGINAL; POS RELEVANT; SIG- IRRELEVANT",
      [dlt(T8, [c]) for c in ("SLOW-", "SLOW+", "ZERO!", "POS", "SIG-")] == ["MARGINAL", "MARGINAL", "MARGINAL", "RELEVANT", "IRRELEVANT"]
      and [dlt(T7, [c]) for c in ("SLOW-", "SLOW+")] == ["WEAK", "WEAK"], str([dlt(T8, [c]) for c in ("SLOW-", "SLOW+", "ZERO!", "POS", "SIG-")]))
check("ruling A edits across_dlt only: across_cov and y_inf_code keep v07's maps (SLOW- and SLOW+ read WEAK)",
      all(T8.codes["columns"]["helper"][h]["map"] == T7.codes["columns"]["helper"][h]["map"] for h in ("across_cov", "y_inf_code")))
check("v08-rules: a pair resolved SLOW- beside a pair resolved ZERO! agree MARGINAL (v07: UNRES)", dlt(T8, ["SLOW-", "ZERO!"]) == "MARGINAL" and dlt(T7, ["SLOW-", "ZERO!"]) == "UNRES")

# --- T6: D2 (the dead-secondary rule): a null covariance no longer blocks a live Delta reading
ac = lambda T, cov, dl: detect.codes_of({"across.y_last": cov, "across_delta.y_last": dl}, T)["across"]   # noqa: E731
check("D2: across_cov NOT-EVALUATED + across_dlt MARGINAL reads MARGINAL under v08-rules and NOT-EVALUATED under v07-rules",
      ac(T8, "NOT-EVALUATED", ["ZERO!"]) == "MARGINAL" and ac(T7, "NOT-EVALUATED", ["ZERO!"]) == "NOT-EVALUATED", f"{ac(T8, 'NOT-EVALUATED', ['ZERO!'])} {ac(T7, 'NOT-EVALUATED', ['ZERO!'])}")
check("D2: the 24k T 0.5 cells of the recon (covariance NOT-EVALUATED, the Delta pair read SLOW+ / ZERO!) read MARGINAL (v08) and NOT-EVALUATED (v07)",
      ac(T8, "NOT-EVALUATED", ["ZERO!"]) == "MARGINAL" and ac(T8, "NOT-EVALUATED", ["SLOW+"]) == "MARGINAL" and ac(T7, "NOT-EVALUATED", ["SLOW+"]) == "NOT-EVALUATED")
nn = {(a, b): detect.codes_of({"across.y_last": a, "across_delta.y_last": [b]}, T8)["across"] for a in ("NOT-MEASURED", "NOT-EVALUATED") for b in ("NOT-MEASURED", "NOT-EVALUATED")}
check("D2: the four null-null keys: NM,NM = NM; NM,NE = NE; NE,NM = NE; NE,NE = NE (a NOT-EVALUATED anywhere is 'measured, unevaluable')",
      nn == {("NOT-MEASURED", "NOT-MEASURED"): "NOT-MEASURED", ("NOT-MEASURED", "NOT-EVALUATED"): "NOT-EVALUATED", ("NOT-EVALUATED", "NOT-MEASURED"): "NOT-EVALUATED",
             ("NOT-EVALUATED", "NOT-EVALUATED"): "NOT-EVALUATED"}, str(nn))
check("D2: a live covariance still reads through a null Delta as before (RELEVANT, NOT-MEASURED = RELEVANT; RELEVANT, NOT-EVALUATED = UNRES), and the Delta wins when resolved (POS, ZERO! = MARGINAL)",
      ac(T8, "POS", "NOT-MEASURED") == "RELEVANT" and detect.codes_of({"across.y_last": "POS", "across_delta.y_last": ["NOT-EVALUATED"]}, T8)["across"] == "UNRES" and ac(T8, "POS", ["ZERO!"]) == "MARGINAL")
for why, edit, find in (
        ("a nullable that is not true, false or \"either\" is refused", lambda t: t.replace('nullable = "either"', 'nullable = "sometimes"'), "is not true, false or"),
        ("a null VALUE at a key that has a resolved part is refused (only the null-null cells may map to a null)", lambda t: t.replace('"NOT-EVALUATED,MARGINAL" = "MARGINAL"', '"NOT-EVALUATED,MARGINAL" = "NOT-EVALUATED"'), "is not in the alphabet"),
        ("a missing null-first key is refused (the map is total over both sources' nulls)", lambda t: t.replace('"NOT-EVALUATED,WEAK" = "WEAK"\n', ""), "missing key 'NOT-EVALUATED,WEAK'")):
    with tempfile.TemporaryDirectory() as t:
        shutil.copy(ROOT / "cc.toml", t)
        shutil.copy(ROOT / "checks.toml", t)
        shutil.copytree(ROOT / "instruments", Path(t) / "instruments")
        shutil.copytree(ROOT / "tables" / "v08-rules", Path(t) / "tables" / "v08-rules")
        frozen.thaw(Path(t) / "tables" / "v08-rules")   # the set is frozen (read-only): owner-write on the COPY only (ruled E378)
        shutil.copytree(ROOT / "cc", Path(t) / "cc")
        f = Path(t) / "tables" / "v08-rules" / "codes.toml"
        f.write_text(edit(f.read_text()))
        found = declare.check_file(f, t)
        check(why, any(find in x.msg for x in found), str([x.msg[:90] for x in found]))

# --- T3: the Delta basis is RAW. A planted chain whose endpoints read drift CONVERGING is measured under both sets: v07 reads the pair TRANSFORMED, v08 RAW (no leak of the transform).
SIZES, LEVELS, N = [27, 81, 243], [2, 3, 4], 3000
GROWTH = {("a", "b"): (-0.5, -0.05), ("b", "c"): (0.0, 0.5)}   # Delta(a->b): yD1 -0.5, yD2 -0.05 (SLOW-); Delta(b->c): 0.0, +0.5
TOP = {"a": 0.004, "b": 0.004, "c": 0.08}                      # the needle's top velocity; the previous pair's is 0.04: r = 0.1 (a, b CONVERGING), r = 2 (c PERSISTENT)


def planted(tmp):
    rng, files, mean = np.random.default_rng(11), [], {"a": {L: 0.5 for L in SIZES}}
    for (p, q), (y1, y2) in GROWTH.items():
        d = {27: 0.1, 81: 0.1 * 3 ** y1, 243: 0.1 * 3 ** (y1 + y2)}
        mean[q] = {L: mean[p][L] + d[L] for L in SIZES}
    for pt in "abc":
        for L, nb in zip(SIZES, LEVELS):
            lv = {27: [0.40, 0.46], 81: [0.30, 0.40, 0.50], 243: [0.2, 0.3, 0.4, 0.5 + TOP[pt]]}[L]
            np.savez(Path(tmp) / f"{pt}-{L}.npz", G=mean[pt][L] + 0.01 * rng.standard_normal(N), GL=np.array(lv) + 0.01 * rng.standard_normal((N, nb)))
            files.append({"point": pt, "size": L, "start": "random", "path": f"{pt}-{L}.npz", "arrays": {"G": {"key": "G"}, "GL": {"key": "GL"}}})
    rel = lambda t, **kw: {"template": t, "provenance": "Coupling", **kw}   # noqa: E731
    return {"instruments": ["needle_chain", "across_delta", "stability_delta"], "obtained": {p: "truth" for p in "abc"},
            "axes": {"point": ["a", "b", "c"], "size": SIZES, "starts": ["random"], "main_start": "random"},
            "observable": {"name": "g", "definition": "planted", "levels": LEVELS, "final_size": 9},
            "relations": {"size": rel("chain", axis="size"), "control": rel("chain", axis="point"), "chain": rel("matched-chain", axis="size", pairs=[[243, 81], [81, 27]])},
            "interval": {"method": "block", "b": 50, "resamples": 100, "level": 0.95, "seed": 3}, "eps": {"y": 0.25, "drift": 0.5},
            "data": {"format": "npz-v1", "files": files}}


def read(T):
    with tempfile.TemporaryDirectory() as tmp:
        m = planted(tmp)
        c, reg = declare.Ctx(ROOT, data_root=tmp), {n: detect.instrument(n) for n in sorted(declare.Ctx(ROOT).reg)}
        out = detect.measure(m, c, reg, T)
        rows = {pt: detect.point_rows(m, c, reg, out, pt, detect.used(T)) for pt in "abc"}
        pair = {k[1]: (v[0]["y_last"], v[1]) for k, v in out.items() if k[0] == "across_delta"}
        return pair, {pt: detect.codes_of(detect.cells_of_rows(rows[pt]), T) for pt in "abc"}


def read7_8():
    p8, c8 = read(T8)
    p7, c7 = read(T7)
    return p7, c7, p8, c8


p7, c7, p8, c8 = read7_8()
ab, bc = ("a", "b"), ("b", "c")
check("the planted endpoints read drift_code a, b CONVERGING, c PERSISTENT under both sets", [c8[x]["drift_code"] for x in "abc"] == ["CONVERGING", "CONVERGING", "PERSISTENT"]
      and [c7[x]["drift_code"] for x in "abc"] == ["CONVERGING", "CONVERGING", "PERSISTENT"], str([c8[x]["drift_code"] for x in "abc"]))
check("v07-rules reads the CONVERGING pair TRANSFORMED; v08-rules reads EVERY pair RAW (the transform did not leak into the Delta basis)",
      (p7[ab][0].door, p7[bc][0].door) == ("TRANSFORMED", "RAW") and (p8[ab][0].door, p8[bc][0].door) == ("RAW", "RAW"), str((p8[ab][0].door, p8[bc][0].door)))
y1, y2 = np.asarray(p8[ab][1]["y_steps"])[0]
check("v08-rules: the pair a->b reads the raw yD2 = -0.05 (SLOW-) with ratio r = 0, y_last = yD2 to 1e-9; v07 reads the transformed 0 (ZERO!)",
      p8[ab][0].cell == "SLOW-" and abs(p8[ab][0].estimate - y2) < 1e-9 and float(np.asarray(p8[ab][1]["ratio"])[0]) == 0.0 and abs(y2 + 0.05) < 0.01 and p7[ab][0].cell == "ZERO!",
      f"{p8[ab][0].cell} {p8[ab][0].estimate} {y2} {p7[ab][0].cell}")
check("ruling A on the planted residual: v08 across_dlt at a and b reads MARGINAL (SLOW- raw yD2); the pair b->c (SIG+) reads RELEVANT at c; b (MARGINAL, RELEVANT) is UNRES",
      [c8[x]["across_dlt"] for x in "abc"] == ["MARGINAL", "UNRES", "RELEVANT"], str([c8[x]["across_dlt"] for x in "abc"]))
check("v08 stability on the Delta basis: both planted pairs have d_D POS (+0.45, +0.5), so a, b, c all read CROSSING (every touching pair agrees); v07 reads them from the covariance, which this input does not declare: TRANSFORMED / NOT-MEASURED",
      [c8[x]["stability"] for x in "abc"] == ["CROSSING"] * 3 and {c7[x]["stability"] for x in "abc"} == {"NOT-MEASURED"}, str([c8[x]["stability"] for x in "abc"]) + str([c7[x]["stability"] for x in "abc"]))
print("".join(f"FAILED {x}\n" for x in bad) + "test_v08_tables: " + ("FAILED" if bad else "all passed"))
sys.exit(1 if bad else 0)
