"""test_feature - plan 1176 phase B (ruling R1): the per-curve feature projection and the real-data side oracle (cc/intake_feature.py).
Every family is planted here as a LONG_TABLE (tests/intake_plant.py) and run in process through S0-S5; the oracle takes S5's Census and S2's
seal state. It reads no real data. Each check names its red mutation (applied with `bin/cc mutate`, seen FAIL by this name, reverted):
 B1. a monotone family: every curve AtSpanEnd, every cell UNRES. Red: span-end argmax as Located (EDGE = {True: Located, ...}).
 B2. curves of two rows: Absent. Red: n < 2 (SIZED keyed on len(rows) >= 2).
 B3. a 7-sample Located peak: Below NEG, Inside MID, Above POS, OffSpan UNRES. Red: NEG and POS swapped in SIDE.
 B4. a one-curve family: SINGLE at every cell. Red: FAMILY's one-curve answer "MID".
 B5. SIDE's key set is FEATURES x LOCI. Red: the row (Located, OffSpan) deleted.
 B6. the evidence is FiniteStored("<id>:<seal hash>") (UNSEALED: "<id>:UNSEALED"), never Sharp. Red: the evidence built as a Sharp().
 B7. the same answers after the declaration dir and the bank are deleted post-census. Red: the oracle re-opens a bank file from its root.
 B8. POLICY holds [feature_projection.FEATURE_ARGMAX_FAST] with non-empty estimand, preserves and discards; without it the oracle is the typed
     refusal PROJECTION_UNDECLARED. Red: the row removed from intake/POLICY.toml.
 B9. intake_feature is its own role in checks.toml, outside the measurement closure, and tests/test_budget.py (FEATURE_CAP 200, disjointness)
     passes. Red: FEATURE_CAP made 100 (the cap assert FAILS); cc/intake_feature.py also listed under intake_handoff (the disjointness assert FAILS)."""
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
import intake_seal  # noqa: E402
import intake_synth  # noqa: E402
from intake_plant import long_table, rooted, run, write_long  # noqa: E402

T = intake.tables(ROOT)
bad = []


def check(name, ok, why=""):
    print(("ok   " if ok else "FAIL ") + name + ("" if ok else f": {why}"))
    if not ok:
        bad.append(name)


def rows(cs, s=0.03):
    """A curve's rows (T, C, sigma) at T = 1, 2, ... in ascending T."""
    return [f"{1.0 + j:.4f},{c:.4f},{s:.4f}" for j, c in enumerate(cs)]


def cells(o, curves, n):
    """Every cell of the plane and one beyond each sample end: {(k, s): side name}."""
    return {(k, s): o((float(k), float(s))).name for k in range(curves) for s in range(-1, n + 1)}


# ---- B5 totality (first: a hole in SIDE would stop every check below at its first lookup)
check("B5. SIDE's key set is FEATURES x LOCI", set(F.SIDE) == set(itertools.product(F.FEATURES, F.LOCI)), str(set(itertools.product(F.FEATURES, F.LOCI)) ^ set(F.SIDE)))

# ---- B8 the POLICY row (first: without it every oracle below is the refusal)
row = T["policy"].get("feature_projection", {}).get(F.KEY, {})
check("B8. POLICY declares the projection in M with non-empty estimand, preserves and discards",
      all(str(row.get(k, "")).strip() for k in ("estimand", "preserves", "discards")), str(row)[:300])

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
            return F.oracle(rooted(T, tmp), census, seal), census, seal   # the tables the run used, as values

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
        check("B3. the sides are members of the alphabet given (linenav's Side by name)", all(isinstance(o((0.0, float(s))), F.Side) for s in range(7)), "")
        wide = F.feature([(1.0 + j, c, 0.6) for j, c in enumerate([0.0, 1.0, 8.0, 10.0, 9.0, 1.0, 0.0])], T["policy"]["policy"]["tier_z"], "COLUMN")
        check("B3. the sigma-plateau holds the samples within Z sigma of the maximum (ranks 2..4)", wide == F.Located(7, 3, 2, 4, "TIERED"), str(wide))
        check("B3. no sigma column: the bracket is the argmax sample, UNTIERED", F.feature([(1.0 + j, c) for j, c in enumerate(PEAK)], 2.0, "NONE") == F.Located(7, 3, 3, 3, "UNTIERED"), "")

        # ---- B4 one curve
        o1, _, _ = oracle([(0.1, rows(PEAK))], "one")
        check("B4. a one-curve family: SINGLE at every cell", set(cells(o1, 1, 7).values()) == {"SINGLE"}, str(sorted(set(cells(o1, 1, 7).values()))))

        # ---- B6 evidence
        sealed = intake_seal.SealState(intake_seal.SealStatus.SEALED, "", {"declaration_sha256": "ab12"})
        check("B6. the evidence is FiniteStored(<id>:UNSEALED) on an unsealed run, never Sharp",
              type(o.evidence).__name__ == "FiniteStored" and o.evidence == F.FiniteStored("peak:UNSEALED"), repr(o.evidence))
        check("B6. a sealed census: FiniteStored(<id>:<seal hash>)", F.oracle(rooted(T, tmp), census, sealed).evidence == F.FiniteStored("peak:ab12"), repr(F.oracle(rooted(T, tmp), census, sealed).evidence))

        # ---- B7 census only
        before = cells(o, 3, 7)
        shutil.rmtree(banks / "peak")   # the bank first: the loader's audit hook logs into the declaration dir while it exists
        shutil.rmtree(tmp / "declarations" / "peak")
        try:
            after = cells(F.oracle(rooted(T, tmp), census, seal), 3, 7)
        except OSError as e:
            after = f"the oracle opened a file: {e!r}"
        check("B7. the same answers after the declaration dir and the bank are deleted post-census", after == before, str(after)[:300])

        # ---- B8 POLICY row
        bare = {**T, "policy": {k: v for k, v in T["policy"].items() if k != "feature_projection"}}
        check("B8. without the row the oracle is the typed refusal PROJECTION_UNDECLARED", F.oracle(bare, census, seal) == F.Unprojected(), repr(F.oracle(bare, census, seal)))


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
