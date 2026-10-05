"""test_chain - plan 0870 P2: size-chain flow (needle_chain drift -> drift_code -> flow), the narrow two_start rule, and the guard that no
cell outside the declared [[change]] list moved between v03-rules and v04-rules on any existing input."""
import json
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path[:0] = [str(ROOT / "cc"), str(ROOT / "cc" / "instruments")]
import declare  # noqa: E402
import detect  # noqa: E402

bad = []


def check(name, ok, why=""):
    print(("ok   " if ok else "FAIL ") + name + ("" if ok else f": {why}"))
    if not ok:
        bad.append(name)


T = detect.load_tables("v04-rules")
base = {"needle.d_ord": "NEG", "needle.d_dis": "NEG", "needle.velocity": "SLOW+", "across.y_last": "ZERO!", "stability.d": "ZERO!",
        "two_start.D": ["ZERO!"] * 3, "declared.probe": "COMPLETE"}


def sig(**over):
    codes = detect.codes_of({**base, **over}, T)
    return {n: codes[n] for n in T.codes["columns"]["signature"]}


for drift, want in (("SIG+", "STOPPED"), ("POS", "STOPPED"), ("ZERO!", "SLOW"), ("SLOW+", "SLOW"), ("SLOW-", "SLOW"), ("NEG", "SLOW"), ("SIG-", "SLOW"),
                    ("UNRES", "SLOW"), ("NOT-EVALUATED", "SLOW"), ("NOT-MEASURED", "SLOW")):
    cells = {} if drift == "NOT-MEASURED" else {"needle_chain.drift": drift}
    got = sig(**cells)
    check(f"a SLOW top-pair flow with drift {drift} reads flow {want}", got["flow"] == want, str(got))
check("a STOPPED top-pair flow stays STOPPED whatever the drift (PERSISTENT)", sig(**{"needle.velocity": "ZERO!", "needle_chain.drift": "SIG-"})["flow"] == "STOPPED")
check("a FLOWING top-pair flow stays FLOWING under a CONVERGING drift", sig(**{"needle.velocity": "SIG+", "needle_chain.drift": "SIG+"})["flow"] == "FLOWING")
check("an unresolved top-pair flow stays UNRES under a CONVERGING drift", sig(**{"needle.velocity": "UNRES", "needle_chain.drift": "SIG+"})["flow"] == "UNRES")
check("a null top-pair flow is the null flow (the loader's rule)", sig(**{"needle.velocity": "NOT-EVALUATED", "needle_chain.drift": "SIG+"})["flow"] == "NOT-EVALUATED")
check("drift_code is kept in the signature, ignored by verdict.toml", "drift_code" in T.codes["columns"]["signature"] and "drift_code" in T.verdict["ignores"])
check("a drift CONVERGING reads CONVERGING and a PERSISTENT one PERSISTENT", (sig(**{"needle_chain.drift": "POS"})["drift_code"], sig(**{"needle_chain.drift": "NEG"})["drift_code"]) == ("CONVERGING", "PERSISTENT"))
for ts, want in ((["INDEP", "INDEP", "COEXIST"], "COEXIST"), (["COEXIST", "INDEP", "INDEP"], "INDEP"), (["COEXIST", "UNRES", "INDEP"], "UNRES"),
                 (["COEXIST", "COEXIST", "COEXIST"], "COEXIST"), (["COEXIST", "FLUCT", "INDEP"], "FLUCT"), (["UNRES", "COEXIST", "COEXIST"], "COEXIST")):
    cells = {"SLOW+": "INDEP", "ZERO!": "INDEP", "POS": "COEXIST", "SIG+": "COEXIST", "UNRES": "UNRES", "NEG": "FLUCT"}
    raw = [next(k for k, v in cells.items() if v == c) for c in ts]
    check(f"two_start sizes {ts} combine to {want} (COEXIST counts only at the largest size)", sig(**{"two_start.D": raw})["two_start"] == want, str(sig(**{"two_start.D": raw})["two_start"]))
for why, edit, find in (
        ("a planted missing cell in the flow table is refused", lambda t: t.replace('"SLOW,CONVERGING" = "STOPPED"\n', ""), "missing key 'SLOW,CONVERGING'"),
        ("a flow table value outside the flow alphabet is refused", lambda t: t.replace('"SLOW,CONVERGING" = "STOPPED"', '"SLOW,CONVERGING" = "HALTED"'), "is not in the alphabet"),
        ("a top_only code outside the alphabet is refused", lambda t: t.replace('combine.top_only = ["COEXIST"]', 'combine.top_only = ["HALTED"]'), "is not in the alphabet")):
    with tempfile.TemporaryDirectory() as t:
        shutil.copy(ROOT / "cc.toml", t)
        shutil.copy(ROOT / "checks.toml", t)
        shutil.copytree(ROOT / "instruments", Path(t) / "instruments")
        shutil.copytree(ROOT / "tables" / "v04-rules", Path(t) / "tables" / "v04-rules")
        f = Path(t) / "tables" / "v04-rules" / "codes.toml"
        f.write_text(edit(f.read_text()))
        found = declare.check_file(f, t)
        check(why, any(find in x.msg for x in found), str([x.msg[:80] for x in found]))
MOVED = {("x5n-bilayer", p, k) for p in ("0.0", "0.1", "0.3") for k in ("verdict", "verdict_class", "geometry")} \
    | {("x5n-bilayer-2", p, k) for p in ("0.0", "0.1", "0.3") for k in ("verdict", "verdict_class", "geometry")} \
    | {("b7-at-line-4", p, "geometry") for p in ("0.0", "0.07")}      # expected/v04-rules.toml [[change]], declared in plan 0870 P-1
moved, n = set(), 0
for f in sorted((ROOT / "results").glob("*@v03-rules.json")):
    a, b = json.loads(f.read_text()), json.loads(Path(str(f).replace("v03-rules", "v04-rules")).read_text())
    for sa, sb in zip(a["signature"], b["signature"]):
        n += 1
        moved |= {(a["input"], sa["point"], k) for k in sa if k not in ("row_line", "why", "axis_lines", "flags") and sa[k] != sb[k]}
    check(f"{a['input']}: a one-pair input reads drift_code NOT-MEASURED under v04-rules", {x["drift_code"] for x in b["signature"]} == {"NOT-MEASURED"})
check(f"{n} points: no cell outside the declared [[change]] list moved from v03-rules to v04-rules on an existing input", moved == MOVED, str(sorted(moved ^ MOVED)))
fresh = detect.run("x2-xy-line-3", "v04-rules", False, reuse=False)      # re-measured now, against the stored result: the drift maths is under test, not only its codes
stored = json.loads((ROOT / "results" / "x2-xy-line-3@v04-rules.json").read_text())
pick = lambda r: [(x["unit"]["point"], x["column"], x["estimate"], x["cell"]) for x in r["readings"] if x["instrument"] == "needle_chain"]   # noqa: E731
check("x2-xy-line-3 re-measured: the drift readings equal the stored ones", pick(fresh) == pick(stored) and len(pick(stored)) == 5, str(pick(fresh)[:2]))
check("x2-xy-line-3 re-measured: omega_eff - 1 at T 0.5 is 1.06 (omega_eff 2.06), CONVERGING, flow STOPPED",
      abs(pick(fresh)[0][2] - 1.063) < 0.01 and fresh["signature"][0]["drift_code"] == "CONVERGING" and fresh["signature"][0]["flow"] == "STOPPED", str(pick(fresh)[0]))
import view  # noqa: E402
text = "\n".join(view.explain(stored, "0.6", None, "basic"))
check("explain reads the drift trace and the flow derivation of x2-xy-line-3 T 0.6", "flow = STOPPED from flow_top SLOW and drift_code CONVERGING" in text and "matched-chain" in text, text[-300:])
print("".join(f"FAILED {x}\n" for x in bad) + "test_chain: " + ("FAILED" if bad else "all passed"))
sys.exit(1 if bad else 0)
