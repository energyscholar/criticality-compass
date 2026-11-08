"""test_transformed - plan 0872 F1: the declared finite-size transform. The stability column of v06-rules is a total table over (raw stability, drift_code);
the geometry accepts TRANSFORMED where it accepts STABLE for a line and refuses a relevant exponent measured on a pre-asymptotic pair; WALKING survives only off a
CONVERGING point; the instrument's y_inf equals the limit of a planted geometric correction. v01-v05 read what they read."""
import itertools
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
from lib import bad, bootstrap, check  # noqa: E402
bootstrap(ROOT, "cc", "cc/instruments")
import admit  # noqa: E402
import detect  # noqa: E402
import door  # noqa: E402


T6, T5 = detect.load_tables("v06-rules"), detect.load_tables("v05-rules")
RAW = {"STABLE": "ZERO!", "CROSSING": "POS", "OFF": "SIG-", "UNRES": "UNRES"}       # a stability.d sign cell that maps to each raw code
DRIFT = {"CONVERGING": "POS", "MARGINAL-DRIFT": "ZERO!", "PERSISTENT": "NEG", "UNRES": "UNRES"}
bad_cells = []
for raw, d in itertools.product([*RAW, "NOT-MEASURED", "NOT-EVALUATED"], [*DRIFT, "NOT-MEASURED", "NOT-EVALUATED"]):
    cells = {"stability.d": RAW.get(raw, raw), **({} if d == "NOT-MEASURED" else {"needle_chain.drift": DRIFT.get(d, d)})}
    got = detect.codes_of(cells, T6)["stability"]
    want = raw if raw in ("NOT-MEASURED", "NOT-EVALUATED") else "TRANSFORMED" if raw in ("STABLE", "CROSSING") and d == "CONVERGING" else raw
    bad_cells += [(raw, d, got, want)] * (got != want)
check("the stability column equals the spec's sentence on all 6 x 6 cells (TRANSFORMED iff raw STABLE/CROSSING and drift CONVERGING; a null raw is that null)", not bad_cells, str(bad_cells[:3]))
check("v05-rules is untouched: its stability never reads TRANSFORMED", "TRANSFORMED" not in T5.codes["columns"]["signature"]["stability"]["alphabet"])

base = {"needle.d_ord": "NEG", "needle.d_dis": "NEG", "needle.velocity": "ZERO!", "across.y_last": "ZERO!", "two_start.D": ["ZERO!"] * 3, "declared.probe": "COMPLETE"}


def geom(tables, stab, drift, across="ZERO!"):
    codes = detect.codes_of({**base, "across.y_last": across, "stability.d": stab, "needle_chain.drift": drift}, tables)
    return detect.axes_of(codes, tables)["geometry"], detect.verdict_of({n: codes[n] for n in tables.codes["columns"]["signature"]}, tables)


check("a marginal exponent whose raw stability CROSSES on a CONVERGING point reads LINE under v06-rules (it was WALKING under v05-rules)",
      geom(T6, "POS", "POS")[0] == "LINE" and geom(T5, "POS", "POS")[0] == "WALKING", f"{geom(T6, 'POS', 'POS')} {geom(T5, 'POS', 'POS')}")
check("the same CROSSING on a PERSISTENT or MARGINAL-DRIFT point still reads WALKING (real walking stays detectable)",
      geom(T6, "POS", "NEG")[0] == "WALKING" and geom(T6, "POS", "ZERO!")[0] == "WALKING")
check("a marginal STABLE exponent on a CONVERGING point reads LINE (TRANSFORMED is accepted wherever a line accepted STABLE) and its verdict agrees",
      geom(T6, "ZERO!", "POS")[0] == "LINE" and geom(T6, "ZERO!", "POS")[1][0] == "LINE")
g, (v, _, _, why) = geom(T6, "POS", "POS", across="POS")
check("a RELEVANT exponent on a CONVERGING point is refused (REFUSE-UNRES), never a POINT, and the refusal names a Next line", g == "REFUSE-UNRES" and v == "REFUSE-UNRES" and "Next:" in why, f"{g} {v}")
check("a RELEVANT STABLE exponent off a CONVERGING point still reads POINT", geom(T6, "ZERO!", "NEG", across="POS")[0] == "POINT")
check("OFF on a CONVERGING point stays REFUSE-OFF", geom(T6, "SIG-", "POS")[0] == "REFUSE-OFF")

# the instrument's maths: y_inf recovers the limit of a planted geometric correction y_k = y_inf + (y_1 - y_inf) r^(k-1)
m, inst = detect.load_input("x2b-xy"), detect.instrument("transform")[0]
ctx = door.context(m, inst, None)
mod = detect.instrument("transform")[1]
ln3 = np.log(3)


def planted(y_inf, y1, r, rows=4):
    y2 = y_inf + (y1 - y_inf) * r
    lnR = np.array([0.0, y1 * ln3, (y1 + y2) * ln3]) + 5.0
    lnv = np.array([np.log(0.4), np.log(0.4 * r)])
    x = np.tile(np.hstack([lnR, lnv]), (rows, 1)) + 0 * np.arange(rows)[:, None]
    return admit.nodefield(x)


for y_inf, y1, r in ((0.1, -0.08, 0.12), (-0.3, 0.5, 0.5), (0.0, 0.2, 0.9)):
    out = mod.ratio(planted(y_inf, y1, r), ctx)
    ok = door.decays(out, ctx)
    got = mod.transform(ok, ctx)["y_inf"] if not isinstance(ok, door.Null) else None
    check(f"y_inf recovers the planted limit {y_inf} (y1 {y1}, r {r})", got is not None and np.allclose(got, y_inf, atol=1e-9), str(got))
refused = door.decays(mod.ratio(planted(0.1, 0.0, 1.5), ctx), ctx)
check("a correction that does not decay (r = 1.5) is NOT-EVALUATED with a reason, never a number", isinstance(refused, door.Null) and refused.value == "NOT-EVALUATED" and "does not decay" in refused.reason, str(refused))
print("".join(f"FAILED {x}\n" for x in bad) + "test_transformed: " + ("FAILED" if bad else "all passed"))
sys.exit(1 if bad else 0)
