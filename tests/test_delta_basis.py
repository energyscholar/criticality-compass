"""test_delta_basis - plan 0874: across_delta reads the TRANSFORMED exponent on a pair whose BOTH endpoints read drift_code CONVERGING (delta_basis TRANSFORMED), the raw
yD2 on any other pair (RAW); a point combines ONLY its TRANSFORMED touching pairs when at least one exists. Planted chain a -> b -> c with known Delta growth and known
needle drift (a, b CONVERGING with r = 0.1; c PERSISTENT with r = 2), measured through detect.measure with the REAL instruments under v07-rules and v06-rules."""
import dataclasses
import shutil
import sys
import tempfile
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path[:0] = [str(ROOT / "cc"), str(ROOT / "cc" / "instruments")]
import admit  # noqa: E402
import declare  # noqa: E402
import detect  # noqa: E402
import door  # noqa: E402
import frozen  # noqa: E402

bad = []


def check(name, ok, why=""):
    print(("ok   " if ok else "FAIL ") + name + ("" if ok else f": {why}"))
    if not ok:
        bad.append(name)


SIZES, LEVELS, N = [27, 81, 243], [2, 3, 4], 3000
LN3 = np.log(3)
# Delta(a->b)(L): yD1 = -0.5, yD2 = -0.05 (raw SLOW-); with r = 0.1 the transform reads (-0.05 + 0.05)/0.9 = 0 (ZERO!). Delta(b->c)(L): yD1 = 0, yD2 = +0.5 (RELEVANT, RAW).
GROWTH = {("a", "b"): (-0.5, -0.05), ("b", "c"): (0.0, 0.5)}
TOP = {"a": 0.004, "b": 0.004, "c": 0.08}     # needle velocity of the top matched pair; the previous pair's is 0.04, so r = 0.1 (a, b: CONVERGING) and r = 2 (c: PERSISTENT)


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
    return {"instruments": ["needle_chain", "across_delta"], "obtained": {p: "truth" for p in "abc"},
            "axes": {"point": ["a", "b", "c"], "size": SIZES, "starts": ["random"], "main_start": "random"},
            "observable": {"name": "g", "definition": "planted", "levels": LEVELS, "final_size": 9},
            "relations": {"size": rel("chain", axis="size"), "control": rel("chain", axis="point"), "chain": rel("matched-chain", axis="size", pairs=[[243, 81], [81, 27]])},
            "interval": {"method": "block", "b": 50, "resamples": 100, "level": 0.95, "seed": 3}, "eps": {"y": 0.25, "drift": 0.5},
            "data": {"format": "npz-v1", "files": files}}


def read(tables):
    with tempfile.TemporaryDirectory() as tmp:
        m, T = planted(tmp), detect.load_tables(tables)
        c, reg = declare.Ctx(ROOT, data_root=tmp), {n: detect.instrument(n) for n in sorted(declare.Ctx(ROOT).reg)}
        out = detect.measure(m, c, reg, T)
        rows = {pt: detect.point_rows(m, c, reg, out, pt, detect.used(T)) for pt in "abc"}
        cells = {pt: detect.cells_of_rows(rows[pt]) for pt in "abc"}
        pair = {k[1]: (v[0]["y_last"], v[1]) for k, v in out.items() if k[0] == "across_delta"}
        return pair, {pt: detect.codes_of(cells[pt], T) for pt in "abc"}


p7, c7 = read("v07-rules")
p6, c6 = read("v06-rules")
ab, bc = ("a", "b"), ("b", "c")
check("the endpoints read drift_code: a, b CONVERGING, c PERSISTENT (the planted needle)", [c7[x]["drift_code"] for x in "abc"] == ["CONVERGING", "CONVERGING", "PERSISTENT"], str([c7[x]["drift_code"] for x in "abc"]))
check("v07-rules: the pair whose BOTH endpoints are CONVERGING reads delta_basis TRANSFORMED; the pair with a PERSISTENT endpoint reads RAW",
      (p7[ab][0].door, p7[bc][0].door) == ("TRANSFORMED", "RAW"), str((p7[ab][0].door, p7[bc][0].door)))
check("v06-rules writes no membership rule for across_delta: every pair reads the instrument's declared default RAW", (p6[ab][0].door, p6[bc][0].door) == ("RAW", "RAW"), str((p6[ab][0].door, p6[bc][0].door)))
r7, r6 = p7[ab][0], p6[ab][0]
check("the RAW pair reads yD2 = -0.05 (SLOW-); the TRANSFORMED pair reads 0 (ZERO!): the basis changes the reading, not only its name",
      (r6.cell, r7.cell) == ("SLOW-", "ZERO!") and abs(r6.estimate + 0.05) < 0.01 and abs(r7.estimate) < 0.02, f"{r6.cell} {r6.estimate} / {r7.cell} {r7.estimate}")
y1, y2 = np.asarray(p7[ab][1]["y_steps"])[0]
ratio = float(np.asarray(p7[ab][1]["ratio"])[0])
check("the TRANSFORMED estimate equals (yD2 - r yD1)/(1 - r) from the reported step exponents and ratio, to 1e-9", abs(r7.estimate - (y2 - ratio * y1) / (1 - ratio)) < 1e-9, f"{r7.estimate} vs {(y2 - ratio * y1) / (1 - ratio)}")
check("the ratio r is the endpoints' needle |v2|/|v1| = 0.1 (to 10 %), and the RAW pair reports r = 0", abs(ratio - 0.1) < 0.01 and float(np.asarray(p7[bc][1]["ratio"])[0]) == 0.0, str(ratio))
check("the RAW pair reads the raw yD2 under both sets (v06 and v07 agree on a RAW pair)", abs(p7[bc][0].estimate - p6[bc][0].estimate) < 1e-12 and p7[bc][0].cell == "SIG+", f"{p7[bc][0].estimate} {p6[bc][0].estimate}")
check("under v07-rules a point combines ONLY its TRANSFORMED pairs: a MARGINAL, b MARGINAL (its RAW pair b->c is ignored), c RELEVANT (its only pair is RAW)",
      [c7[x]["across_dlt"] for x in "abc"] == ["MARGINAL", "MARGINAL", "RELEVANT"], str([c7[x]["across_dlt"] for x in "abc"]))
check("under v06-rules the same data read a WEAK, b UNRES (its two pairs disagree), c RELEVANT: the per-point rule is the table's, not the data's",
      [c6[x]["across_dlt"] for x in "abc"] == ["WEAK", "UNRES", "RELEVANT"], str([c6[x]["across_dlt"] for x in "abc"]))

# the per-point rule, cell by cell, through the table's own function
T7, T6 = detect.load_tables("v07-rules"), detect.load_tables("v06-rules")
dlt = lambda T, y, d: detect.codes_of({"across_delta.y_last": y, "across_delta.y_last@door": d}, T)["across_dlt"]   # noqa: E731
check("pairs [TRANSFORMED ZERO!, RAW SIG+] combine to MARGINAL (only the TRANSFORMED one), and [RAW SIG+, TRANSFORMED ZERO!] too (order does not matter)",
      dlt(T7, ["ZERO!", "SIG+"], ["TRANSFORMED", "RAW"]) == "MARGINAL" and dlt(T7, ["SIG+", "ZERO!"], ["RAW", "TRANSFORMED"]) == "MARGINAL")
check("pairs [RAW ZERO!, RAW SIG+] (no TRANSFORMED pair) combine over both, as today: they disagree, UNRES",
      dlt(T7, ["ZERO!", "SIG+"], ["RAW", "RAW"]) == "UNRES")
check("two TRANSFORMED pairs that disagree are UNRES, never either code", dlt(T7, ["ZERO!", "SIG+"], ["TRANSFORMED", "TRANSFORMED"]) == "UNRES")
check("a TRANSFORMED pair that is NOT-EVALUATED leaves the point NOT-EVALUATED -> UNRES (a dead preferred pair is not replaced by a RAW one)",
      dlt(T7, ["NOT-EVALUATED", "ZERO!"], ["TRANSFORMED", "RAW"]) == "NOT-EVALUATED")
check("v06-rules ignores the door values: [TRANSFORMED ZERO!, RAW SIG+] is UNRES there", dlt(T6, ["ZERO!", "SIG+"], ["TRANSFORMED", "RAW"]) == "UNRES")
check("a cell list with no door values reads as today (the 0872 reading): v07-rules agrees on [ZERO!, ZERO!]",
      detect.codes_of({"across_delta.y_last": ["ZERO!", "ZERO!"]}, T7)["across_dlt"] == "MARGINAL")

# the door table: the membership rule, the declared default, the ratio table, the decay refusal
inst = detect.instrument("across_delta")[0]
codes = lambda a, b: {"p": {"drift_code": a}, "q": {"drift_code": b}}   # noqa: E731
mem = lambda rules, a, b: door.member_for(inst, rules, "across_delta", ("p", "q"), codes(a, b))["door"]   # noqa: E731
check("membership: both CONVERGING -> TRANSFORMED; one MARGINAL-DRIFT / PERSISTENT / UNRES / NOT-MEASURED / NOT-EVALUATED -> RAW",
      mem(T7.membership, "CONVERGING", "CONVERGING") == "TRANSFORMED"
      and {mem(T7.membership, "CONVERGING", x) for x in ("MARGINAL-DRIFT", "PERSISTENT", "UNRES", "NOT-MEASURED", "NOT-EVALUATED")} == {"RAW"}
      and {mem(T7.membership, x, "CONVERGING") for x in ("MARGINAL-DRIFT", "PERSISTENT", "UNRES", "NOT-MEASURED", "NOT-EVALUATED")} == {"RAW"})
check("a set with no rule for across_delta reads the declared default RAW", mem({}, "CONVERGING", "CONVERGING") == "RAW")
try:
    door.member_for({}, {}, "along", ("p", "q"), codes("MID", "MID"))
    check("an instrument that declares no member_default and has no rule is refused (KeyError), never defaulted", False, "returned")
except KeyError:
    check("an instrument that declares no member_default and has no rule is refused (KeyError), never defaulted", True)
drift = {"p": np.full(4, 1.0), "q": np.full(4, 3.0)}   # r = 3^-(1+1) = 1/9 and 3^-(3+1) = 1/81
rat = door.ratio_of("TRANSFORMED", lambda pt: drift[pt], ("p", "q"), lambda: LN3, 4)
check("ratio table: TRANSFORMED is the mean of the endpoints' 3^-(drift+1); RAW is 0 and never reads the drift",
      np.allclose(rat, (1 / 9 + 1 / 81) / 2) and not door.ratio_of("RAW", lambda pt: 1 / 0, ("p", "q"), lambda: 1 / 0, 4).any())
with tempfile.TemporaryDirectory() as tmp:
    ctx = door.context(planted(tmp), inst, None)
ok = door.basis(admit.nodefield(np.zeros((4, 3))), dataclasses.replace(ctx, ratio=np.array([0.1, 0.2, 0.3, 0.9])))
no = door.basis(admit.nodefield(np.zeros((4, 3))), dataclasses.replace(ctx, ratio=np.array([0.1, 0.2, 0.3, 1.0])))
check("door:basis passes r < 1 at every resample and refuses r >= 1 at any (NOT-EVALUATED with a reason), a RAW r = 0 always passes",
      not isinstance(ok, door.Null) and isinstance(no, door.Null) and no.value == "NOT-EVALUATED" and "does not decay" in no.reason
      and not isinstance(door.basis(admit.nodefield(np.zeros((4, 3))), dataclasses.replace(ctx, ratio=np.zeros(4))), door.Null))
mod = detect.instrument("across_delta")[1]
lnd = np.log(np.array([0.1, 0.1 * 3 ** -0.5, 0.1 * 3 ** -0.55]))   # yD1 = -0.5, yD2 = -0.05
for r, want in ((0.0, -0.05), (0.1, 0.0), (0.5, 0.4)):
    got = mod.growth(admit.nodefield(np.tile(lnd, (4, 1))), dataclasses.replace(ctx, ratio=np.full(4, r)))["y_last"]
    check(f"the growth stage reads (yD2 - r yD1)/(1 - r): r {r} gives {want}", np.allclose(got, want, atol=1e-9), str(got))

# the declarations are validated: a prefer_door that is not a door value, a member_default that is not one
for why, path, edit, find in (
        ("a combine.prefer_door that is not a door value of the source instrument is refused", "tables/v07-rules/codes.toml",
         lambda t: t.replace('combine.prefer_door = "TRANSFORMED"', 'combine.prefer_door = "NOWHERE"'), "is not a door value"),
        ("a member_default that is not one of the instrument's door_values is refused", "instruments/across_delta.toml",
         lambda t: t.replace('member_default = "RAW"', 'member_default = "NOWHERE"'), "is not in door_values"),
        ("a membership rule for across_delta with a gap in its map is refused", "tables/v07-rules/membership.toml",
         lambda t: t.replace('PERSISTENT = "OTHER", ', ""), "missing key 'PERSISTENT'")):
    with tempfile.TemporaryDirectory() as t:
        shutil.copy(ROOT / "cc.toml", t)
        shutil.copy(ROOT / "checks.toml", t)
        shutil.copytree(ROOT / "instruments", Path(t) / "instruments")
        frozen.thaw(Path(t) / "instruments")   # instruments/ is frozen (read-only): owner-write on the COPY only (ruling 5)
        shutil.copytree(ROOT / "tables" / "v07-rules", Path(t) / "tables" / "v07-rules")
        shutil.copytree(ROOT / "cc", Path(t) / "cc")
        f = Path(t) / path
        f.write_text(edit(f.read_text()))
        found = declare.check_file(f, t)
        check(why, any(find in x.msg for x in found), str([x.msg[:90] for x in found]))
print("".join(f"FAILED {x}\n" for x in bad) + "test_delta_basis: " + ("FAILED" if bad else "all passed"))
sys.exit(1 if bad else 0)
