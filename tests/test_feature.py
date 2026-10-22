"""test_feature - plan 1176 phase B (ruling R1): the per-curve feature projection and the real-data side oracle (cc/intake_feature.py).
Every family is planted here as a LONG_TABLE (tests/intake_plant.py) and run in process through S0-S5; the oracle takes S5's Census and S2's
seal state. It reads no real data. Each check names its red mutation (applied with `bin/cc mutate`, seen FAIL by this name, reverted):
 B1. a monotone family: every curve AtSpanEnd, every cell UNRES. Red: span-end argmax as Located (EDGE = {True: Located, ...}).
 B2. curves of two rows: Absent. Red: n < 2 (SIZED keyed on len(rows) >= 2).
 B3. a 7-sample Located peak: Below NEG, Inside MID, Above POS, OffSpan UNRES. Red: NEG and POS swapped in SIDE.
 B4. a one-curve family: SINGLE at every cell. Red: FAMILY's one-curve answer "MID".
 B5. SIDE's key set is FEATURES x LOCI (plan 1176 C': four kinds, Broad among them). Red: the row (Located, OffSpan) deleted; C': the Broad
     rows deleted (`**{(Broad, c): "UNRES" ...}` removed).
 B6. the evidence is FiniteStored("<id>:<seal hash>") (UNSEALED: "<id>:UNSEALED"), never Sharp. Red: the evidence built as a Sharp().
 B7. the same answers after the declaration dir and the bank are deleted post-census. Red: the oracle re-opens a bank file from its root.
 B8. POLICY holds [feature_projection.FEATURE_ARGMAX_FAST] with non-empty estimand, preserves and discards; without it the oracle is the typed
     refusal PROJECTION_UNDECLARED. Red: the row removed from intake/POLICY.toml. C': its discards name the bracket width beyond the corridor
     read as Broad. Red: that clause removed from discards.
 B9. intake_feature is its own role in checks.toml, outside the measurement closure, and tests/test_budget.py (FEATURE_CAP 200, disjointness)
     passes. Red: FEATURE_CAP made 100 (the cap assert FAILS); cc/intake_feature.py also listed under intake_handoff (the disjointness assert FAILS).
 B10. (plan 1176 C', O1; C'' restated in span units) an interior sigma-plateau WIDER than w_c of the fast span is Broad and UNRES everywhere;
     one exactly w_c of the span wide (end samples 3 apart on a span of 20: 3/20 = w_c 0.15) stays Located and sides, and on a span of 19 is
     Broad. Red: Broad made Located (KIND (False, True) -> Located); the width rule made `>=` (w_c-wide = Broad).
 Plan 1176 C'' (O4): the oracle is called on a point of the plane in span units (Span, POLICY [coordinate.PLANE_SPAN_UNIT]); the B1-B10
 helpers query each curve at its own measured samples (Oracle.at) and the span map is checked by B11-B14 (each seen red by its mutation):
 B11. nearest curve by slow, a tie to the LOWER rank: on curves at slow 0.25 and 0.75 the point at u = 0.5 reads the lower curve, just
     above it the upper. Red: the tie to the upper rank (Oracle.curve key (d, k) -> (d, -k)).
 B12. the side is the ORDER of the query's fast against the bracket's END SAMPLE values, nothing formed between samples: between rank 2 and the
     peak sample NEG, at the peak MID, past it POS, beyond the span UNRES. Red: Inside widened by half a sample (a midpoint formed between samples).
 B13. a located point re-projects on output to its enclosing measured pair (curves for slow, samples of its nearest curve for fast; at a
     sample: that sample twice; beyond the span: the end twice). Red: Oracle.measured returns the point's own fast value.
 B14. POLICY holds [coordinate.PLANE_SPAN_UNIT] with non-empty map, preserves and discards; without it the oracle is the typed refusal
     COORDINATE_UNDECLARED; Span maps the plane's extent onto [0, 1] x [0, 1]. Red: the row removed from intake/POLICY.toml.
 Plan 1176 amendment E0: a declared [plane.fast_window] is the feature projection's DOMAIN, read through the declared path (the suspect's
 Plane, navfamily.oracle_for). Planted: a two-peak curve, fast 10, 12, .., 30, its SMALL peak at 16 inside the window [11, 21] and its LARGE
 peak at 26 outside it (each seen red by its mutation, applied with `bin/cc mutate`):
 B15. the in-window small peak is Located (rank 3), never the taller out-of-window one (rank 8); with no window the taller one. Red: the window
     ignored (_build's domain FAST_ENDS[True], the whole span); navfamily.oracle_for not handing on cells.plane.window.
 B16. a window edge IS a span end: on [10, 15] the maximum sits on the window's last sample (rank 2), AtSpanEnd. Red: an edge maximum typed
     Located (KIND's span-end test against the CURVE's ends, `lo + i[0] == 0 or hi + i[0] == len(a) - 1`).
 B17. not a row filter: every sample stays in the curve (Oracle.fasts all 11), so T 26 (outside the window, inside the curve's span) sides
     POS, not UNRES. Red: the oracle's fasts filtered to the window (the curve's span shrinks).
 B18. the window is in the fast knob's VALUE unit, never ranks: [12, 18] holds ranks 1..4 (by rank it would hold none). Red: the domain read on ranks (enumerate index).
 B19. the plane's fast span unit and Broad are the WINDOW's: Span fast (lo 11, width 10); a curve with fewer than three in-window samples
     ([12.5, 13.5]: none) is Absent. Red: the span map built over the whole extent (span(cs) without the window)."""
import itertools
import json
import shutil
import subprocess
import sys
import tempfile
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path[:0] = [str(ROOT / "cc"), str(ROOT / "tests")]
import intake  # noqa: E402
import intake_feature as F  # noqa: E402
import intake_suspect as S  # noqa: E402
import navfamily as NF  # noqa: E402
import intake_seal  # noqa: E402
import intake_synth  # noqa: E402
from intake_plant import long_table, rooted, run, write_long  # noqa: E402

T = intake.tables(ROOT)
WC = F.linenav.PARAMS["continuous"]["wc"]   # the frozen continuous corridor's w_c (0.15 of the fast span): the Broad width (C'')
bad = []


def check(name, ok, why=""):
    print(("ok   " if ok else "FAIL ") + name + ("" if ok else f": {why}"))
    if not ok:
        bad.append(name)


def rows(cs, s=0.03):
    """A curve's rows (T, C, sigma) at T = 1, 2, ... in ascending T."""
    return [f"{1.0 + j:.4f},{c:.4f},{s:.4f}" for j, c in enumerate(cs)]


def cells(o, curves, n):
    """Every (curve rank, sample rank) of the plane and one beyond each sample end, read at the curve's own measured fast value (C'': the oracle
    is queried by value, Oracle.at; beyond an end: one unit past it): {(k, s): side name}."""
    at = lambda v, s: ([v[0] - 1.0, *v, v[-1] + 1.0])[s + 1]   # noqa: E731
    return {(k, s): o.at(k, at(o.fasts[k], s)) for k in range(curves) for s in range(-1, n + 1)}


# ---- B5 totality (first: a hole in SIDE would stop every check below at its first lookup)
check("B5. SIDE's key set is FEATURES x LOCI", set(F.SIDE) == set(itertools.product(F.FEATURES, F.LOCI)), str(set(itertools.product(F.FEATURES, F.LOCI)) ^ set(F.SIDE)))

# ---- B8 the POLICY row (first: without it every oracle below is the refusal)
row = T["policy"].get("feature_projection", {}).get(F.KEY, {})
check("B8. POLICY declares the projection in M with non-empty estimand, preserves and discards",
      all(str(row.get(k, "")).strip() for k in ("estimand", "preserves", "discards")), str(row)[:300])
check("B8. its discards name the bracket width beyond the corridor (read as Broad)", "bracket width beyond the corridor (read as Broad)" in str(row.get("discards", "")), str(row.get("discards")))

PEAK = [0.0, 1.0, 2.0, 10.0, 2.0, 1.0, 0.0]   # a sharp interior maximum at rank 3 (sigma 0.03: the plateau is rank 3 alone)
def planted():
    """B1-B4, B6, B7 and the refusal of B8, on planted families run through S0-S5."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        banks = tmp / "banks"
        intake_synth.write(banks / "pf", tmp / "pf-TRUTH", "pf", 1, 9)
        m = json.loads((banks / "pf" / "MANIFEST.json").read_text())

        def family(blocks, ident):
            """(S5's Census or the refusals, S2's SealState) of a planted LONG_TABLE family [(h, rows)]."""
            (banks / ident).mkdir()
            write_long(banks / ident, blocks)
            out = run(T, tmp, ident, long_table(m, ident).replace("<long-test>/pf", f"<long-test>/{ident}"))
            refused = [e.result.reason for e in out.values() if e.mark is intake.Mark.REFUSED]
            return {True: lambda: out["S5"].result.evidence, False: lambda: refused}[out["S5"].mark is intake.Mark.PASSED](), out["S2"].result.evidence

        def oracle(blocks, ident):
            census, seal = family(blocks, ident)
            return F.oracle(rooted(T, tmp), census, seal, "continuous"), census, seal   # the tables the run used, as values

        # ---- B1 monotone
        o, _, _ = oracle([(h, rows([float(j) for j in range(7)])) for h in (0.1, 0.2, 0.3, 0.4)], "mono")
        check("B1. a monotone family: every curve AtSpanEnd", [type(f) for f in o.features] == [F.AtSpanEnd] * 4, str(o.features))
        check("B1. a monotone family: every cell UNRES", set(cells(o, 4, 7).values()) == {"UNRES"}, str(sorted(set(cells(o, 4, 7).values()))))

        # ---- B2 two rows
        o, _, _ = oracle([(h, rows([0.0, 1.0])) for h in (0.1, 0.2, 0.3)], "two")
        check("B2. curves of two rows: Absent, and UNRES everywhere", [type(f) for f in o.features] == [F.Absent] * 3 and set(cells(o, 3, 2).values()) == {"UNRES"}, str(o.features))

        # ---- B3 Located
        o, census, seal = oracle([(h, rows(PEAK)) for h in (0.1, 0.2, 0.3)], "peak")
        want = {**{(k, s): "NEG" for k in range(3) for s in (0, 1, 2)}, **{(k, 3): "MID" for k in range(3)},
                **{(k, s): "POS" for k in range(3) for s in (4, 5, 6)}, **{(k, s): "UNRES" for k in range(3) for s in (-1, 7)}}
        check("B3. a 7-sample peak is Located(rank 3, [3, 3], TIERED)", o.features[0] == F.Located(7, 3, 3, 3, "TIERED"), str(o.features[0]))
        check("B3. Below NEG, Inside MID, Above POS, OffSpan UNRES", cells(o, 3, 7) == want, str(cells(o, 3, 7)))
        check("B3. the sides are members of the alphabet given (linenav's Side by name)", all(isinstance(o(o.span.u((o.slows[0], v))), F.Side) for v in o.fasts[0]), "")
        wide = F.feature([(1.0 + j, c, 0.6) for j, c in enumerate([0.0, 1.0, 8.0, 10.0, 9.0, 1.0, 0.0])], T["policy"]["policy"]["tier_z"], "COLUMN", WC, 20.0)   # span 20: narrow
        check("B3. the sigma-plateau holds the samples within Z sigma of the maximum (ranks 2..4)", wide == F.Located(7, 3, 2, 4, "TIERED"), str(wide))
        check("B3. no sigma column: the bracket is the argmax sample, UNTIERED", F.feature([(1.0 + j, c) for j, c in enumerate(PEAK)], 2.0, "NONE", WC, 20.0) == F.Located(7, 3, 3, 3, "UNTIERED"), "")

        # ---- B10 Broad (O1): a wide interior plateau sides nowhere; exactly w_c wide still sides
        flat = [0.0, 0.0, 9.0, 9.5, 9.8, 10.0, 9.8, 9.5, 9.0, 0.0, 0.0]   # sigma 0.6, Z 2: ranks 2..8 within Z sigma of the max (6 of a span of 10 > w_c)
        ob, _, _ = oracle([(h, rows(flat, 0.6)) for h in (0.1, 0.2, 0.3)], "broad")
        check("B10. an interior plateau 6/10 of the fast span wide (> w_c 0.15) is Broad", ob.features[0] == F.Broad(11, 5, 2, 8, "TIERED"), str(ob.features[0]))
        check("B10. a Broad family is UNRES at every cell", set(cells(ob, 3, 11).values()) == {"UNRES"}, str(sorted(set(cells(ob, 3, 11).values()))))
        edge = [(1.0 + j, c, 0.6) for j, c in enumerate([0.0, 0.0, 0.0, 9.5, 10.0, 9.8, 9.6, 0.0, 0.0, 0.0, 0.0])]   # plateau ranks 3..6: end samples 3 apart
        five = F.feature(edge, T["policy"]["policy"]["tier_z"], "COLUMN", WC, 20.0)
        check("B10. a plateau exactly w_c of the span wide (3 of 20 = 0.15) stays Located", five == F.Located(11, 4, 3, 6, "TIERED"), str(five))
        check("B10. the same plateau on a span of 19 (3/19 > 0.15) is Broad", F.feature(edge, T["policy"]["policy"]["tier_z"], "COLUMN", WC, 19.0) == F.Broad(11, 4, 3, 6, "TIERED"), "")
        check("B10. the census counts the Broad curves (O2)", ob.census() == {"Located": 0, "Broad": 3, "AtSpanEnd": 0, "Absent": 0} and ob.kind((0.5, 0.5)) == "Broad", str(ob.census()))

        # ---- B11-B14 the plane in span units (C'', O4)
        shifted = [0.0, 1.0, 2.0, 3.0, 4.0, 10.0, 4.0]   # the peak at rank 5 (T 6)
        o2, _, _ = oracle([(0.25, rows(PEAK)), (0.75, rows(shifted))], "two-slow")   # curve 0: peak at T 4; curve 1: peak at T 6
        u5 = lambda x: o2.span.u((0.5, x))[1]   # noqa: E731  T as a span fraction
        check("B11. at the slow midpoint (a tie) the LOWER curve answers: T 5 is POS of its peak at T 4", (o2.curve((0.5, u5(5.0))), o2((0.5, u5(5.0))).name) == (0, "POS"),
              str((o2.curve((0.5, u5(5.0))), o2((0.5, u5(5.0))).name)))
        check("B11. just above the midpoint the upper curve answers: T 5 is NEG of its peak at T 6", (o2.curve((0.5 + 1e-9, u5(5.0))), o2((0.5 + 1e-9, u5(5.0))).name) == (1, "NEG"), "")
        check("B11. Span maps the plane's extent onto [0, 1] x [0, 1]", o2.span.u((0.25, 1.0)) == (0.0, 0.0) and o2.span.u((0.75, 7.0)) == (1.0, 1.0), repr(o2.span))
        got = [o2.at(0, x) for x in (3.5, 3.999, 4.0, 4.001, 4.5, 0.5, 7.5)]
        check("B12. by ORDER against the bracket's end sample (T 4): 3.5 NEG, 3.999 NEG, 4 MID, 4.001 POS, 4.5 POS, beyond the span UNRES",
              got == ["NEG", "NEG", "MID", "POS", "POS", "UNRES", "UNRES"], str(got))
        mp = [o2.measured(o2.span.u(p)) for p in ((0.3, 4.3), (0.25, 5.0), (0.25, 7.0))]
        check("B13. re-projection to the enclosing measured pair: between samples, at a sample, at the span end",
              mp == [([0.25, 0.75], [4.0, 5.0]), ([0.25, 0.25], [5.0, 5.0]), ([0.25, 0.25], [7.0, 7.0])], str(mp))
        check("B13. ranks(): the nearest curve and the enclosing sample ranks", o2.ranks(o2.span.u((0.3, 4.3))) == (0, (3, 4)), str(o2.ranks(o2.span.u((0.3, 4.3)))))
        crow = T["policy"].get("coordinate", {}).get(F.SPAN_KEY, {})
        check("B14. POLICY declares the coordinate map with non-empty map, preserves and discards", all(str(crow.get(k, "")).strip() for k in ("map", "preserves", "discards")), str(crow)[:300])
        nocoord = {**T, "policy": {k: v for k, v in T["policy"].items() if k != "coordinate"}}
        check("B14. without it the oracle is the typed refusal COORDINATE_UNDECLARED", F.oracle(nocoord, census, seal, "continuous") == F.Unprojected("COORDINATE_UNDECLARED"),
              repr(F.oracle(nocoord, census, seal, "continuous"))[:200])

        # ---- B15-B19 the declared fast window (E0), through the declared path: [plane.fast_window] -> Plane.window -> navfamily.oracle_for
        two = [0.0, 1.0, 3.0, 5.0, 3.0, 1.0, 0.0, 4.0, 20.0, 4.0, 0.0]   # small peak at rank 3 (fast 16), large at rank 8 (fast 26)
        planted2 = [(h, [f"{10.0 + 2 * j:.4f},{c:.4f},0.0300" for j, c in enumerate(two)]) for h in (0.1, 0.2, 0.3)]

        def windowed(ident, lo, hi):
            """The oracle over a planted two-peak family declaring [plane.fast_window] lo, hi (None: no window), via the suspect's Plane."""
            (banks / ident).mkdir()
            write_long(banks / ident, planted2)
            win = {True: "", False: f"[plane.fast_window]\nlo = {lo}\nhi = {hi}\n"}[lo is None]
            tail = f'\n[plane]\naxes = "slow-fast"\n{win}\n[suspect]\nvertices = [[0.1, 16.0], [0.3, 16.0]]\ncorridor = "continuous"\n'
            out = run(T, tmp, ident, long_table(m, ident).replace("<long-test>/pf", f"<long-test>/{ident}") + tail)
            census, seal = out["S5"].result.evidence, out["S2"].result.evidence
            return NF.oracle_for(rooted(T, tmp), S.suspect(rooted(T, tmp), census), census, seal)

        ow, on = windowed("win", 11.0, 21.0), windowed("nowin", None, None)
        check("B15. the in-window small peak is Located (rank 3), never the taller out-of-window one", ow.features[0] == F.Located(11, 3, 3, 3, "TIERED"), str(ow.features[0]))
        check("B15. with no window the taller peak is Located (rank 8)", on.features[0] == F.Located(11, 8, 8, 8, "TIERED"), str(on.features[0]))
        oe = windowed("winedge", 10.0, 15.0)
        check("B16. a window edge is a span end: the maximum on the window's last sample is AtSpanEnd", type(oe.features[0]) is F.AtSpanEnd and oe.features[0].rank == 2, str(oe.features[0]))
        check("B17. not a row filter: every sample stays in the curve", [len(v) for v in ow.fasts] == [11] * 3, str([len(v) for v in ow.fasts]))
        check("B17. T 26 (outside the window, inside the curve's span) sides POS, not UNRES", ow.at(0, 26.0) == "POS", ow.at(0, 26.0))
        ov = windowed("winv", 12.0, 18.0)
        check("B18. the window is in value units: [12, 18] holds ranks 1..4, the small peak Located at rank 3", ov.features[0] == F.Located(11, 3, 3, 3, "TIERED"),
              repr(ov.features[0]))
        check("B19. the plane's fast span unit is the window's (lo 11, width 10)", (ow.span.lo[1], ow.span.width[1]) == (11.0, 10.0), repr(ow.span))
        check("B19. with no window the fast span is the measured extent (lo 10, width 20)", (on.span.lo[1], on.span.width[1]) == (10.0, 20.0), repr(on.span))
        check("B19. fewer than three in-window samples ([12.5, 13.5]: none) is Absent", type(windowed("winnone", 12.5, 13.5).features[0]) is F.Absent, "")

        # ---- B4 one curve
        o1, _, _ = oracle([(0.1, rows(PEAK))], "one")
        check("B4. a one-curve family: SINGLE at every cell", set(cells(o1, 1, 7).values()) == {"SINGLE"}, str(sorted(set(cells(o1, 1, 7).values()))))

        # ---- B6 evidence
        sealed = intake_seal.SealState(intake_seal.SealStatus.SEALED, "", {"declaration_sha256": "ab12"})
        check("B6. the evidence is FiniteStored(<id>:UNSEALED) on an unsealed run, never Sharp",
              type(o.evidence).__name__ == "FiniteStored" and o.evidence == F.FiniteStored("peak:UNSEALED"), repr(o.evidence))
        check("B6. a sealed census: FiniteStored(<id>:<seal hash>)", F.oracle(rooted(T, tmp), census, sealed, "continuous").evidence == F.FiniteStored("peak:ab12"), repr(F.oracle(rooted(T, tmp), census, sealed, "continuous").evidence))

        # ---- B7 census only
        before = cells(o, 3, 7)
        shutil.rmtree(banks / "peak")   # the bank first: the loader's audit hook logs into the declaration dir while it exists
        shutil.rmtree(tmp / "declarations" / "peak")
        try:
            after = cells(F.oracle(rooted(T, tmp), census, seal, "continuous"), 3, 7)
        except OSError as e:
            after = f"the oracle opened a file: {e!r}"
        check("B7. the same answers after the declaration dir and the bank are deleted post-census", after == before, str(after)[:300])

        # ---- B8 POLICY row
        bare = {**T, "policy": {k: v for k, v in T["policy"].items() if k != "feature_projection"}}
        check("B8. without the row the oracle is the typed refusal PROJECTION_UNDECLARED", F.oracle(bare, census, seal, "continuous") == F.Unprojected(), repr(F.oracle(bare, census, seal, "continuous")))


try:
    planted()
except Exception as e:   # a mutation that breaks the oracle's types stops the planted checks; it is a failure, named here, and the summary still prints
    check("B1-B8. the planted families run to the end", False, repr(e)[:300])


# ---- B9 role, closure, budget
ck = tomllib.loads((ROOT / "checks.toml").read_text())
check("B9. intake_feature is its own role, and outside the measurement closure",
      ck["roles"].get("intake_feature") == ["cc/intake_feature.py"] and "cc/intake_feature.py" in ck["closure"]["measure"]["outside"], str(ck["roles"].get("intake_feature")))
bud = subprocess.run([sys.executable, str(ROOT / "tests" / "test_budget.py")], capture_output=True, text=True)
check("B9. tests/test_budget.py passes (FEATURE_CAP and the disjointness of intake_feature)", bud.returncode == 0, (bud.stdout + bud.stderr)[-300:])

print("test_feature: " + ("FAILED " + "; ".join(bad) if bad else "all passed"))
sys.exit(1 if bad else 0)
