"""test_v08_result - plan 0877 T3/T4/T5/T7 on STORED results (no data are read, nothing is measured):
T3 the stored x2b-xy-3@v08-rules is current (its read hashes match the tree) and reads the RAW exponent of the difference (the OBS2 raw yD2 and d_D, not the transformed yD_inf);
T4 its stability_delta vectors equal the across_delta step exponents of x2b-xy-2@v07-rules to 1e-9, pair by pair (same data, same resample plan, same reduce);
T5 a result cannot be re-verdicted under a set that REPLACES a column's instrument with one the input does not declare (and the clause never fires within v01-v07);
T7 family f1 on a pair instrument reads the stored per-pair vectors (a planted VARIES; a null pair reads its null, never a zero)."""
import functools
import json
import sys
import tomllib
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path[:0] = [str(ROOT / "cc"), str(ROOT / "cc" / "instruments")]
import family  # noqa: E402
import reverdict  # noqa: E402
import view  # noqa: E402

bad = []


def check(name, ok, why=""):
    print(("ok   " if ok else "FAIL ") + name + ("" if ok else f": {why}"))
    if not ok:
        bad.append(name)


def load(rid):
    res = json.loads((ROOT / "results" / f"{rid}.json").read_text())
    return res, np.load(ROOT / res["vectors"])


R8, Z8 = load("x2b-xy-3@v08-rules")
R7, Z7 = load("x2b-xy-2@v07-rules")
PAIRS = [tuple(p["pair"]) for p in R8["pairs"] if "across_delta" in p]
key = lambda inst, col, a, b: f"{inst}/{col}/pair={a}->{b}"   # noqa: E731

# --- T3: the stored result is current and reads the RAW basis
check("x2b-xy-3@v08-rules is current: every file it read (the input, the instruments, tables/v08-rules, the data manifest) still hashes as recorded", view.stale(R8, ROOT) is None, str(view.stale(R8, ROOT)))
check("every across_delta pair of x2b-xy-3@v08-rules reads delta_basis RAW (no TRANSFORMED anywhere: the transform did not leak)",
      len(PAIRS) == 8 and {p["delta_basis"] for p in R8["pairs"] if "across_delta" in p} == {"RAW"}, str({p["delta_basis"] for p in R8["pairs"] if "across_delta" in p}))
# results/OBS2.txt (toolset) E2, 600k: the raw yD2 of the difference (the transformed yD_inf +0.0040 / -0.0069 / +0.0014 / +0.0202 are the signature of a leak)
RAW = {("0.5", "0.6"): -0.0066, ("0.6", "0.7"): -0.0173, ("0.7", "0.8"): -0.0091, ("0.8", "0.85"): +0.0136, ("0.85", "0.89294"): +0.0475, ("0.89294", "0.95"): +0.5311, ("0.95", "1.0"): +0.7851, ("1.0", "1.1"): +0.0606}
DD = {("0.5", "0.6"): +0.0746, ("0.6", "0.7"): +0.0728, ("0.7", "0.8"): +0.0711, ("0.8", "0.85"): +0.0508, ("0.85", "0.89294"): -0.0444, ("0.89294", "0.95"): +0.1501, ("0.95", "1.0"): -0.0422, ("1.0", "1.1"): -0.5063}
got = {pr: Z8[key("across_delta", "y_last", *pr)][0] for pr in RAW}
check("the stored across_delta y_last of every pair is the RAW yD2 of results/OBS2.txt E2 (to 5e-5)", all(abs(got[pr] - w) < 5e-5 for pr, w in RAW.items()), str({pr: (round(got[pr], 4), w) for pr, w in RAW.items() if abs(got[pr] - w) >= 5e-5}))
got = {pr: Z8[key("stability_delta", "d", *pr)][0] for pr in DD}
check("the stored stability_delta d of every pair is the d_D of results/OBS2.txt E2 (to 5e-5)", all(abs(got[pr] - w) < 5e-5 for pr, w in DD.items()), str({pr: (round(got[pr], 4), w) for pr, w in DD.items() if abs(got[pr] - w) >= 5e-5}))

# --- T4: the Delta-basis instrument and across_delta share their plan and reduce, so the numbers agree to the last bit
diff = {pr: np.abs(Z8[key("stability_delta", "d", *pr)] - (Z7[key("across_delta", "y_steps", *pr)][:, 1] - Z7[key("across_delta", "y_steps", *pr)][:, 0])).max() for pr in PAIRS}
check("x2b-xy-3's stability_delta d = x2b-xy-2's across_delta (yD2 - yD1) per resample, to 1e-9, for every pair", max(diff.values()) < 1e-9, str(diff))
check("x2b-xy-3's reported y_steps equal x2b-xy-2's, to 1e-9, for every pair", max(np.abs(Z8[key("stability_delta", "y_steps", *pr)] - Z7[key("across_delta", "y_steps", *pr)]).max() for pr in PAIRS) < 1e-9)
check("both results were measured on one resample plan: the same declared interval, and the same 54 data shas",
      R8["interval"] == R7["interval"] and {k: h for k, h in R8["read"].items() if "x2b/" in k} == {k: h for k, h in R7["read"].items() if "x2b/" in k} and len([k for k in R8["read"] if "x2b/" in k]) == 54)

# --- T5: re-verdict refusals
calls = {rid: json.loads((ROOT / "results" / f"{rid}.json").read_text()) for rid in ("x2b-xy-2@v07-rules", "x2b-xy@v07-rules")}
for rid, res in calls.items():
    msg = reverdict.reverdict_refusal(res, "v08-rules", ROOT)
    check(f"reverdict {res['input']} --tables v08-rules is REFUSED (the input does not declare stability_delta: a silent NOT-MEASURED stability is not a re-verdict) and names its Next",
          msg is not None and msg.startswith("REFUSED") and "stability_delta" in msg and "Next:" in msg, str(msg))
check("the refusal for x2b-xy (which declares no across_delta, so its membership is unchanged) comes from the replaced column, not from membership", "membership" not in reverdict.reverdict_refusal(calls["x2b-xy@v07-rules"], "v08-rules", ROOT))
check("x2b-xy-3 declares stability_delta: no signature column of v08-rules is a replacement for it", reverdict.replaced(R8, "v08-rules", ["needle", "across", "stability", "across_delta", "stability_delta"], ROOT) is None)
reverdict.signature_sources = functools.lru_cache(maxsize=None)(reverdict.signature_sources)
sets = [f"v0{k}-rules" for k in range(1, 8)]
hit = []
for f in sorted((ROOT / "results").glob("*.json")):
    res = json.loads(f.read_text())
    if res["tables"] in sets:
        declared = tomllib.loads((ROOT / "inputs" / res["input"] / "m.toml").read_text())["instruments"]
        hit += [(res["run_id"], s, r) for s in sets if (r := reverdict.replaced(res, s, declared, ROOT))]
check("within v01-v07 the new clause fires for NO stored result under NO target set (every earlier set only gains sources)", not hit, str(hit[:3]))

# --- T7: f1 on a pair instrument
fam = tomllib.loads((ROOT / "tables" / "v08-rules" / "family.toml").read_text())
NULLS, RES, PTS = ["NOT-MEASURED", "NOT-EVALUATED"], 100, ["0.5", "0.6", "0.7", "0.8"]
EDGES = list(zip(PTS, PTS[1:]))


def planted(levels, null=None):
    """A stored-result stand-in: per-point across_delta readings (as a real result holds them: no vector, no cell) and per-PAIR readings with their y_last vectors."""
    rng, z, pr = np.random.default_rng(1), {}, []
    for (a, b), y in zip(EDGES, levels):
        vk = f"across_delta/y_last/pair={a}->{b}"
        z[vk] = y + 0.005 * rng.standard_normal(RES + 1)
        dead = (a, b) == null
        pr.append({"instrument": "across_delta", "column": "y_last", "unit": {"pair": [a, b]}, "cell": "NOT-EVALUATED" if dead else "ZERO!", "vector_key": None if dead else vk})
    pts = [{"instrument": "across_delta", "column": "y_last", "unit": {"point": p}, "cell": None, "vector_key": None} for p in PTS]
    return {"interval": {"method": "block", "resamples": RES, "level": 0.95}, "readings": pts, "pair_readings": pr}, z


def f1(levels, null=None):
    res, z = planted(levels, null)
    return family.f1_of(fam, {"interior": PTS}, res, z, {"instruments": ["across_delta"], "eps": {"y": 0.25}}, NULLS)


code, cells = f1([0.0, 0.0, 0.6])
check("f1 on a pair instrument: interior pairs whose y_last differ by 0.6 (> eps 0.25) read VARIES", code == "VARIES", f"{code} {cells}")
check("f1: the units are the consecutive interior pairs (3 pairs, 3 all-pairs differences), labelled a->b", len(cells) == 3 and cells[0][0] == "0.5->0.6" and cells[0][1] == "0.6->0.7", str([c[:2] for c in cells]))
code, cells = f1([0.0, 0.01, -0.01])
check("f1: interior pairs that agree (within eps) read CONSTANT", code == "CONSTANT", f"{code} {cells}")
code, cells = f1([0.0, 0.0, 0.0], null=("0.6", "0.7"))
check("f1: a pair whose reading is a null reads that null, never a zero vector's CONSTANT", code == "NOT-EVALUATED", f"{code} {cells}")
print("".join(f"FAILED {x}\n" for x in bad) + "test_v08_result: " + ("FAILED" if bad else "all passed"))
sys.exit(1 if bad else 0)
