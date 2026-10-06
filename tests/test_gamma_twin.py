"""test_gamma_twin - plan 0878 P3.3: x2b-xy-4 (method gamma) against its bootstrap twin x2b-xy-3 on the SAME frozen data, under v08-rules, per input.
ASSERTS WHAT WAS MEASURED: every point verdict, every needle cell and every Delta-basis cell (across_delta, stability_delta) is equal, EXCEPT the one recorded
difference below (prediction (a) MISSED there). Intervals differ by construction (Gamma against bootstrap) and are compared nowhere except in that record.
No tolerance is widened: the single exception is listed with both intervals. The windows W are printed (prediction (c): 2..20, MISSED: 18..28)."""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
bad = []
PAIR = {"gamma": ("ZERO!", -0.08885391972571863, 5.873327646142151e-05), "bootstrap": ("SLOW-", -0.08474100401192806, -0.0032541638354447247)}
# the ONE recorded difference (the pair 0.85->0.89294), as it appears in the pair readings and, per_point, in the rows of the two points it touches
RECORDED = {("stability_delta", "d", ("0.85", "0.89294")): PAIR, ("stability_delta", "d", "0.85", "0.85->0.89294"): PAIR, ("stability_delta", "d", "0.89294", "0.85->0.89294"): PAIR}


def check(name, ok, why=""):
    print(("ok   " if ok else "FAIL ") + name + ("" if ok else f": {why}"))
    if not ok:
        bad.append(name)


def cells(res):
    """{(instrument, column, point or pair): (cell, lo, hi)} of the needle and the Delta-basis readings."""
    rows = [r for r in res["readings"] + res["pair_readings"] if r["instrument"] in ("needle", "across_delta", "stability_delta")]
    out = {}
    for r in rows:
        u = r["unit"]
        key = (r["instrument"], r["column"], tuple(u["pair"]) if "pair" in u else u["point"])
        out.update({key: (r["cell"], r["lo"], r["hi"])} if r["per_size"] is None else {key + (s["size"],): (s["cell"], s["lo"], s["hi"]) for s in r["per_size"]})
    return out


def differences(g, b):
    return {k: (g[k], b[k]) for k in g if g[k][0] != b[k][0]}


def verdicts(res):
    return {s["point"]: s["verdict"] for s in res["signature"]}


g = json.loads((ROOT / "results" / "x2b-xy-4@v08-rules.json").read_text())
b = json.loads((ROOT / "results" / "x2b-xy-3@v08-rules.json").read_text())
cg, cb = cells(g), cells(b)
check("the two inputs read the same readings", set(cg) == set(cb), str(set(cg) ^ set(cb)))
check("every point verdict is equal", verdicts(g) == verdicts(b))
diff = differences(cg, cb)
for k, (x, y) in diff.items():
    print(f"  difference {k}: gamma {x[0]} [{x[1]:.5g}, {x[2]:.5g}]  bootstrap {y[0]} [{y[1]:.5g}, {y[2]:.5g}]")
check("the cells that differ are exactly the recorded ones", set(diff) == set(RECORDED), str(sorted(map(str, diff))))
for k, rec in RECORDED.items():
    x, y = cg[k], cb[k]
    check(f"recorded difference {k}: gamma and bootstrap read as recorded (cells and both intervals)", (x[0], x[1], x[2]) == rec["gamma"] and (y[0], y[1], y[2]) == rec["bootstrap"], f"{x} {y}")
ws = {(r["instrument"], r["name"], json.dumps(r["unit"])): r["estimate"] for r in g["reports"] if r["name"].startswith("W:") and r["instrument"] in ("across_delta", "stability_delta")}
print(f"  W over the Delta-basis readings: {min(ws.values())}..{max(ws.values())} (prediction (c) 2..20: MISSED)")
check("W is recorded for every Delta-basis reading (8 pairs x 2 instruments)", len(ws) == 16, str(len(ws)))
check("window_max was reached by no Delta-basis reading", max(ws.values()) < g["interval"]["window_max"])

# the RED plant: a copy with one across_delta cell changed must be seen as an unrecorded difference
plant = json.loads(json.dumps(g))
r = next(q for q in plant["pair_readings"] if q["instrument"] == "across_delta")
r["cell"] = "SIG-" if r["cell"] != "SIG-" else "SIG+"
check("PLANT: one changed across_delta cell is an unrecorded difference", set(differences(cells(plant), cb)) != set(RECORDED))
print("test_gamma_twin: " + ("FAILED" if bad else "all passed"))
sys.exit(1 if bad else 0)
