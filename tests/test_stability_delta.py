"""test_stability_delta - plan 0877 T1: the Delta-basis stability instrument. Planted chains with a known Delta growth per size step, measured through
detect.measure with the REAL instrument: d_D = yD2 - yD1 (the last edge of the chain of step exponents) per control pair; the cell by sign against eps.y; the per-point
combination (every touching pair must agree) through a scratch copy of v07-rules whose `stability` column reads the instrument; v07-rules reads it nowhere."""
import re
import shutil
import sys
import tempfile
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path[:0] = [str(ROOT / "cc"), str(ROOT / "cc" / "instruments")]
import declare  # noqa: E402
import detect  # noqa: E402

bad = []


def check(name, ok, why=""):
    print(("ok   " if ok else "FAIL ") + name + ("" if ok else f": {why}"))
    if not ok:
        bad.append(name)


N = 3000
# the chain a b c d e f g; per control pair the step exponents (yD1, yD2): d = yD2 - yD1 is what the instrument must read.
GROWTH3 = {("a", "b"): (-0.5, -0.05),    # d = +0.45 CROSSING
           ("b", "c"): (0.0, 0.5),       # d = +0.5  CROSSING
           ("c", "d"): (-0.05, -0.02),   # d = +0.03 STABLE
           ("d", "e"): (-0.02, 0.01),    # d = +0.03 STABLE
           ("e", "f"): (0.5, 0.0),       # d = -0.5  OFF
           ("f", "g"): None}             # Delta is exactly zero at L 81: its sign is not constant over the resamples (a null)
WANT_D = {("a", "b"): 0.45, ("b", "c"): 0.5, ("c", "d"): 0.03, ("d", "e"): 0.03, ("e", "f"): -0.5}
WANT_PAIR = {("a", "b"): "SIG+", ("b", "c"): "SIG+", ("e", "f"): "SIG-"}   # the resolved cells; the two STABLE pairs read SLOW+ or ZERO!
WANT_POINT = {"a": "CROSSING", "b": "CROSSING", "c": "UNRES", "d": "STABLE", "e": "UNRES", "f": "NOT-EVALUATED", "g": "NOT-EVALUATED"}


def planted(tmp, sizes, growth):
    """Files and the input dict m of a chain whose pair (p, q) has Delta(L_0) = 0.1 and Delta(L_k+1) = Delta(L_k) 3^y_k; iid noise 0.02."""
    rng, files, pts, mean = np.random.default_rng(5), [], ["a"], {"a": {L: 0.5 for L in sizes}}
    for (p, q), ys in growth.items():
        d = [0.1, 0.0, 0.1] if ys is None else [0.1, *(0.1 * 3 ** sum(ys[:k]) for k in range(1, len(ys) + 1))]
        mean[q] = {L: mean[p][L] + x for L, x in zip(sizes, d)}
        pts.append(q)
    for pt in pts:
        for L in sizes:
            np.savez(Path(tmp) / f"{pt}-{L}.npz", G=mean[pt][L] + 0.02 * rng.standard_normal(N))
            files.append({"point": pt, "size": L, "start": "random", "path": f"{pt}-{L}.npz", "arrays": {"G": {"key": "G"}}})
    rel = lambda **kw: {"provenance": "Coupling", "template": "chain", **kw}   # noqa: E731
    return {"instruments": ["stability_delta"], "obtained": {p: "truth" for p in pts},
            "axes": {"point": pts, "size": sizes, "starts": ["random"], "main_start": "random"},
            "relations": {"size": rel(axis="size"), "control": rel(axis="point")},
            "interval": {"method": "block", "b": 50, "resamples": 100, "level": 0.95, "seed": 3}, "eps": {"y": 0.25},
            "data": {"format": "npz-v1", "files": files}}


NEW = '''[columns.signature.stability]
from = "stability_delta.d"
alphabet = ["STABLE", "CROSSING", "OFF", "UNRES", "TRANSFORMED"]
combine.over = "pair"
combine.agree = ["STABLE", "CROSSING", "OFF"]
combine.disagree = "UNRES"
combine.rank = ["NOT-MEASURED", "NOT-EVALUATED", "UNRES", "OFF", "CROSSING", "STABLE", "TRANSFORMED"]

[columns.signature.stability.map]
"SIG-" = "OFF"
"NEG" = "OFF"
"SLOW-" = "STABLE"
"ZERO!" = "STABLE"
"SLOW+" = "STABLE"
"POS" = "CROSSING"
"SIG+" = "CROSSING"
"UNRES" = "UNRES"

'''


def scratch_tables(tmp):
    """v07-rules with ONE change: the signature column `stability` reads stability_delta.d (the alphabet keeps TRANSFORMED so verdict.toml still partitions)."""
    shutil.copytree(ROOT / "tables" / "v07-rules", Path(tmp) / "sd")
    f = Path(tmp) / "sd" / "codes.toml"
    f.write_text(re.sub(r"\[columns\.signature\.stability\].*?(?=\[columns\.signature\.two_start\])", lambda _: NEW, f.read_text(), flags=re.S))
    return detect.load_tables("sd", Path(tmp))


def read(sizes, growth, with_tables=True):
    with tempfile.TemporaryDirectory() as tmp:
        m = planted(tmp, sizes, growth)
        T = scratch_tables(tmp) if with_tables else detect.load_tables("v07-rules")
        c, reg = declare.Ctx(ROOT, data_root=tmp), {n: detect.instrument(n) for n in sorted(declare.Ctx(ROOT).reg)}
        out = detect.measure(m, c, reg, T)
        pairs = {k[1]: v for k, v in out.items() if k[0] == "stability_delta"}
        pts = {}
        for pt in m["axes"]["point"]:
            cells = detect.cells_of_rows(detect.point_rows(m, c, reg, out, pt, detect.used(T)))
            pts[pt] = detect.codes_of(cells, T)["stability"]
        return pairs, pts, T


# --- three sizes: d = yD2 - yD1 per pair, the cells, the per-point combination
pairs, pts, T = read([27, 81, 243], GROWTH3)
for pr, want in WANT_D.items():
    r, rep = pairs[pr]
    got = r["d"].estimate
    check(f"pair {'->'.join(pr)}: d = yD2 - yD1 = {want:+.2f} (read {got:+.3f}, hw {(r['d'].hi - r['d'].lo) / 2:.3f})", abs(got - want) < 0.05, f"{got}")
    y = np.asarray(rep["y_steps"])
    check(f"pair {'->'.join(pr)}: d recovered to 1e-9 per resample from the reported y_steps (yD2 - yD1)", np.allclose(r["d"].vector, y[:, 1] - y[:, 0], rtol=0, atol=1e-9),
          str(np.abs(r["d"].vector - (y[:, 1] - y[:, 0])).max()))
    if pr in WANT_PAIR:
        check(f"pair {'->'.join(pr)}: cell {WANT_PAIR[pr]}", r["d"].cell == WANT_PAIR[pr], r["d"].cell)
    else:
        check(f"pair {'->'.join(pr)}: a d of +-0.03 reads inside the margin (SLOW+ or ZERO!)", r["d"].cell in ("SLOW+", "ZERO!"), r["d"].cell)
r = pairs[("f", "g")][0]["d"]
check("a pair whose Delta changes sign over the resamples reads NOT-EVALUATED with the logcoord reason", r.cell == "NOT-EVALUATED" and "sign of Delta not constant" in (r.reason or ""), f"{r.cell} {r.reason}")
check("per point: agree CROSSING -> CROSSING; {CROSSING, STABLE} -> UNRES; {STABLE, STABLE} -> STABLE; {STABLE, OFF} -> UNRES; a null pair -> that null (alone or beside a resolved pair)",
      pts == WANT_POINT, str(pts))
check("v07-rules reads stability_delta.d NOWHERE (not in used(T7))", "stability_delta.d" not in detect.used(detect.load_tables("v07-rules")))
check("the scratch set reads it, and no longer reads stability.d for the column stability", "stability_delta.d" in detect.used(T))

# --- four sizes: d is the LAST edge of the chain of step exponents (yD3 - yD2); the first edge (yD2 - yD1) reads differently
G4 = {("a", "b"): (-0.5, -0.5, -0.05),    # last-edge d = +0.45 CROSSING; first-edge d = 0.0
      ("b", "c"): (0.0, 0.5, 0.5)}        # last-edge d = 0.0 (STABLE); first-edge d = +0.5
pairs, pts, _ = read([27, 81, 243, 729], G4)
got = {pr: pairs[pr][0]["d"].cell for pr in G4}
check("four sizes: d is the last edge: (-0.5,-0.5,-0.05) reads CROSSING-class SIG+, (0.0,0.5,0.5) reads inside the margin", got[("a", "b")] == "SIG+" and got[("b", "c")] in ("SLOW+", "SLOW-", "ZERO!"), str(got))
print("".join(f"FAILED {x}\n" for x in bad) + "test_stability_delta: " + ("FAILED" if bad else "all passed"))
sys.exit(1 if bad else 0)
