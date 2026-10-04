"""test_across_delta - plan 0872 F2: the difference estimator of across. A planted chain a -> b -> c with a known Delta growth (Delta(L) ~ L^y),
measured through detect.measure with the REAL instrument; the per-point cell combines the control pairs that touch the point (all must agree);
the signature column across reads across_delta when the input declares it; the validator refuses a chain that does not move the probed coupling."""
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


SIZES, N = [27, 81, 243], 3000


def planted(tmp, y1, y2):
    """Files and the input dict m of the chain a -> b -> c: Delta(a->b)(L) = 0.1 (L/27)^y1, Delta(b->c)(L) = 0.1 (L/27)^y2; iid noise 0.02."""
    rng, files = np.random.default_rng(5), []
    for L in SIZES:
        d1, d2 = 0.1 * (L / 27) ** y1, 0.1 * (L / 27) ** y2
        for pt, mean in (("a", 0.5), ("b", 0.5 + d1), ("c", 0.5 + d1 + d2)):
            np.savez(Path(tmp) / f"{pt}-{L}.npz", G=mean + 0.02 * rng.standard_normal(N))
            files.append({"point": pt, "size": L, "start": "random", "path": f"{pt}-{L}.npz", "arrays": {"G": {"key": "G"}}})
    rel = {"template": "chain", "axis": "point", "provenance": "Coupling"}
    return {"instruments": ["across_delta"], "obtained": {p: "truth" for p in "abc"},
            "axes": {"point": ["a", "b", "c"], "size": SIZES, "starts": ["random"], "main_start": "random"},
            "relations": {"size": {"template": "chain", "axis": "size", "provenance": "Coupling"}, "control": rel},
            "interval": {"method": "block", "b": 50, "resamples": 100, "level": 0.95, "seed": 3}, "eps": {"y": 0.25},
            "data": {"format": "npz-v1", "files": files}}


def read(y1, y2):
    with tempfile.TemporaryDirectory() as tmp:
        m, T = planted(tmp, y1, y2), detect.load_tables("v06-rules")
        c, reg = declare.Ctx(ROOT, data_root=tmp), {n: detect.instrument(n) for n in sorted(declare.Ctx(ROOT).reg)}
        out = detect.measure(m, c, reg, T)
        rows = {pt: detect.point_rows(m, c, reg, out, pt, detect.used(T)) for pt in "abc"}
        pairs = {k[1]: v[0]["y_last"].cell for k, v in out.items() if k[0] == "across_delta"}
        dlt = {pt: next(r for r in rows[pt] if r[0] == "across_delta") for pt in "abc"}
        cells = {pt: detect.cells_of_rows([dlt[pt]]) for pt in "abc"}
        return pairs, {pt: dlt[pt][4] for pt in "abc"}, {pt: detect.codes_of(cells[pt], T)["across_dlt"] for pt in "abc"}


pairs, per, codes = read(0.0, 0.0)
check("planted Delta ~ L^0 on both pairs: both pair cells ZERO! (marginal)", pairs == {("a", "b"): "ZERO!", ("b", "c"): "ZERO!"}, str(pairs))
check("a point reads one Reading per control pair that touches it (a: 1, b: 2, c: 1), labelled a->b",
      {pt: [lab for lab, _ in per[pt]] for pt in per} == {"a": ["a->b"], "b": ["a->b", "b->c"], "c": ["b->c"]}, str({pt: [lab for lab, _ in per[pt]] for pt in per}))
check("all pairs agree: every point across_dlt MARGINAL", codes == {"a": "MARGINAL", "b": "MARGINAL", "c": "MARGINAL"}, str(codes))
pairs, per, codes = read(0.0, 1.0)
check("planted Delta ~ L^1 on the second pair: that pair reads SIG+, the first ZERO!", pairs == {("a", "b"): "ZERO!", ("b", "c"): "SIG+"}, str(pairs))
check("the pairs touching b DISAGREE (MARGINAL, RELEVANT): b reads UNRES, never either code; a MARGINAL, c RELEVANT",
      codes == {"a": "MARGINAL", "b": "UNRES", "c": "RELEVANT"}, str(codes))
pairs, per, codes = read(-1.0, -1.0)
check("planted Delta ~ L^-1 on both pairs: every point IRRELEVANT", codes == {"a": "IRRELEVANT", "b": "IRRELEVANT", "c": "IRRELEVANT"}, str(codes))

# the signature column across: ONE declared choice per input
T = detect.load_tables("v06-rules")
sig = lambda cells: detect.codes_of(cells, T)["across"]   # noqa: E731
check("an input that declares no across_delta reads the covariance code (IRRELEVANT)", sig({"across.y_last": "SIG-"}) == "IRRELEVANT")
check("an input that declares across_delta reads the difference code, whatever the covariance reads (MARGINAL, not IRRELEVANT)",
      sig({"across.y_last": "SIG-", "across_delta.y_last": ["ZERO!"]}) == "MARGINAL")
check("a declared across_delta that is NOT-EVALUATED reads UNRES, never the covariance code", sig({"across.y_last": "POS", "across_delta.y_last": ["NOT-EVALUATED"]}) == "UNRES")
check("two touching pairs that disagree read UNRES through the signature column", sig({"across.y_last": "POS", "across_delta.y_last": ["ZERO!", "SIG+"]}) == "UNRES")
check("a null covariance is the null (no across instrument: nothing to probe)", sig({"across_delta.y_last": ["ZERO!"]}) == "NOT-MEASURED")
check("v05-rules is untouched: it has no across_dlt column", "across_dlt" not in detect.load_tables("v05-rules").codes["columns"].get("helper", {}))

# the validator: the chain must move the probed coupling
src = (ROOT / "inputs" / "x2b-xy" / "m.toml").read_text()
base = src.replace('"along", "needle_chain"]', '"along", "needle_chain", "across_delta"]')
for why, mtext, find in (
        ("an input that declares across_delta with no relations.control.coupling is refused, with a Next line", base, "relations.control.coupling is not declared"),
        ("a control chain over a coupling that across does not probe is refused", base.replace('[relations.control]\n', '[relations.control]\ncoupling = "K"\n'), "not the probed coupling"),
        ("across_delta without across is refused", base.replace('"needle", "across", ', '"needle", ').replace('[relations.control]\n', '[relations.control]\ncoupling = "T"\n'), "declares across_delta but not across"),
        ("a control chain over the probed coupling is admitted", base.replace('[relations.control]\n', '[relations.control]\ncoupling = "T"\n'), None)):
    with tempfile.TemporaryDirectory() as t:
        d = Path(t) / "inputs" / "x2b-xy"
        d.mkdir(parents=True)
        shutil.copy(ROOT / "cc.toml", t)
        shutil.copy(ROOT / "checks.toml", t)
        (d / "m.toml").write_text(mtext)
        shutil.copy(ROOT / "inputs" / "x2b-xy" / "couplings.toml", d)
        found = declare.check_file(d / "couplings.toml", t, data_root=declare.Ctx(ROOT).data_root)
        hit = [f for f in found if find and find in f.msg]
        check(why, (not found) if find is None else bool(hit) and "Next:" in declare.fmt(hit[0]), str([f.msg[:90] for f in found]))
print("".join(f"FAILED {x}\n" for x in bad) + "test_across_delta: " + ("FAILED" if bad else "all passed"))
sys.exit(1 if bad else 0)
