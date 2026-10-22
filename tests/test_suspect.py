"""test_suspect - plan 1176 phase A: FORMAT v14's optional [plane] and [suspect], and the suspect polyline in cells (cc/intake_suspect.py).
Every family is planted here as a LONG_TABLE (tests/intake_plant.py) and run in process through S0-S5; the suspect is converted from S5's Census.
It reads no real data. Each check names its red mutation (applied by hand, seen FAIL by this name, reverted):
 A1. a vertex whose slow value is no curve's (0.15 between 0.1 and 0.2) is SUSPECT_SLOW_NOT_A_CURVE. Red: snap to the nearest curve (cell's
     ranks the curve of least |slow - v[0]|). Its sibling: a fast value beyond the curve's last sample is SUSPECT_FAST_OUT_OF_SPAN. Red: the
     span row of cell deleted (the vertex then lands on the end sample). The in-span conversion is (curve rank, nearest sample rank).
 A2. one vertex is SUSPECT_NEEDS_TWO_VERTICES. Red: `len(s["vertices"]) >= 1`.
 A3. every existing planted declaration (declarations/*, the PER_FILE and LONG_TABLE plants, every CHOICE_PLANTS edit) lints identically under
     v14 and under v13 (FORMAT's tables without [plane] and [suspect]); a declaration with them passes S0 under v14 and is FIELD_UNKNOWN under
     v13. Red: [fields.suspect] required = true in intake/FORMAT.toml.
 A4. intake.tables() reports FORMAT 1160-v15 (plan 1176 C'': was v14, the version check moved with the additive corridor word), header schema
     still 5. Red: the version line left at "1160-v14".
 A7. (plan 1176 C'') the [suspect] corridor alphabet is exactly {grid, continuous}, each a key of linenav.PARAMS. Red: continuous removed.
 A5. a family whose curves carry two values of a second knob ([replicate.key] COLUMN p) without [plane.slice] is PLANE_NEEDS_A_SLICE; with the
     slice it converts on that slice's curves; a slice naming another column is PLANE_SLICE_NOT_THE_SECOND_KNOB. Red: the column ignored
     (_curves keys every curve "").
 A6. intake_suspect is its own role in checks.toml, outside the measurement closure, and tests/test_budget.py (SUSPECT_CAP 160, disjointness)
     passes. Red: SUSPECT_CAP made 100 (the cap assert FAILS); cc/intake_suspect.py also listed under intake_handoff (the disjointness assert FAILS).
 Every code the module refuses with is a row of REFUSAL (each reached below)."""
import json
import subprocess
import sys
import tempfile
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path[:0] = [str(ROOT / "cc"), str(ROOT / "tests")]
import intake  # noqa: E402
import intake_fold  # noqa: E402
import intake_suspect as S  # noqa: E402
import intake_synth  # noqa: E402
from intake_evidence import Census  # noqa: E402
from intake_plant import CHOICE_PLANTS, long_table, per_file, rooted, run, write_long  # noqa: E402
from linenav import PARAMS as S_PARAMS  # noqa: E402

T = intake.tables(ROOT)
T13 = {**T, "format": {**T["format"], "version": "1160-v13", "fields": {k: v for k, v in T["format"]["fields"].items() if k not in ("plane", "suspect")}}}
bad, reached = [], set()


def check(name, ok, why=""):
    print(("ok   " if ok else "FAIL ") + name + ("" if ok else f": {why}"))
    if not ok:
        bad.append(name)


def code(r):
    """The refusal code of a result (recorded as reached), or the result's type name."""
    reached.add(getattr(r, "code", None))
    return getattr(r, "code", type(r).__name__)


PEAK = [0.0, 1.0, 2.0, 10.0, 2.0, 1.0, 0.0]


def rows(cs, extra=""):
    """A curve's rows (T, C, sigma[, extra]) at T = 1, 2, ... in ascending T."""
    return [f"{1.0 + j:.4f},{c:.4f},0.0300{extra}" for j, c in enumerate(cs)]


def section(vertices, plane='axes = "slow-fast"', sl=""):
    return (f"\n[plane]\n{plane}\n" * (plane is not None)) + sl + (f"\n[suspect]\nvertices = {vertices}\ncorridor = \"grid\"\n" * (vertices is not None))


def lint(t, d, text, findings):
    """The lint text of a declaration (the stages before data, each as `bin/cc intake lint` prints it) under tables t."""
    out = intake_fold.fold(intake_fold.before_data(t), intake.bodies(t, d, text, findings))
    return "\n".join(f"{k} {e.text(t)}" for k, e in out.items())


# ---- A4 the version
check("A4. intake.tables() reports FORMAT 1160-v15", T["format"]["version"] == "1160-v15", T["format"]["version"])
corr = set(T["format"]["fields"]["suspect"]["fields"]["corridor"]["values"])
check("A7. the corridor alphabet is {grid, continuous}, each a linenav PARAMS key", corr == {"grid", "continuous"} and corr <= set(S_PARAMS), str(corr))
check("A4. the header schema stays 5 (additive v14)", T["format"]["header"] == {"schema": 5, "kind": "intake"}, str(T["format"]["header"]))


def planted():
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        banks = tmp / "banks"
        intake_synth.write(banks / "pf", tmp / "pf-TRUTH", "pf", 1, 9)
        m = json.loads((banks / "pf" / "MANIFEST.json").read_text())

        def census(blocks, ident, tail, edit=lambda t: t, head="T,C,sigma,h\n"):
            """S5's Census of a planted LONG_TABLE family [(h, rows)] whose declaration ends with `tail`, or the refusals before it."""
            (banks / ident).mkdir()
            write_long(banks / ident, blocks, head)
            out = run(T, tmp, ident, edit(long_table(m, ident).replace("<long-test>/pf", f"<long-test>/{ident}")) + tail)
            return {True: lambda: out["S5"].result.evidence, False: lambda: [e.result.reason for e in out.values() if e.mark is intake.Mark.REFUSED]}[out["S5"].mark is intake.Mark.PASSED]()

        def suspect(blocks, ident, tail, **kw):
            c = census(blocks, ident, tail, **kw)
            return {True: lambda: S.suspect(rooted(T, tmp), c), False: lambda: c}[isinstance(c, Census)]()   # the refusals before S5 as a list

        fam = [(h, rows(PEAK)) for h in (0.1, 0.2, 0.3)]
        # ---- A1 exact slow, in span, nearest sample
        ok = suspect(fam, "in", section("[[0.1, 3.2], [0.3, 6.0], [0.2, 7.0]]"))
        check("A1. an in-span suspect converts to (curve rank, nearest sample rank)", ok == S.Cells(((0, 2), (2, 5), (1, 6)), "grid", 3, 7), repr(ok))
        r = suspect(fam, "off", section("[[0.1, 3.0], [0.15, 4.0]]"))
        check("A1. a vertex whose slow value is no curve's is SUSPECT_SLOW_NOT_A_CURVE (never snapped)", code(r) == "SUSPECT_SLOW_NOT_A_CURVE", repr(r))
        r = suspect(fam, "span", section("[[0.1, 3.0], [0.2, 7.5]]"))
        check("A1. a fast value beyond the curve's last sample is SUSPECT_FAST_OUT_OF_SPAN", code(r) == "SUSPECT_FAST_OUT_OF_SPAN", repr(r))
        check("A1. a refusal's detail names the vertex and the curve rank, never a measured value", "7.0" not in getattr(r, "detail", "7.0") and "vertex 1" in getattr(r, "detail", ""), repr(r))

        # ---- A2 two vertices
        r = suspect(fam, "one", section("[[0.1, 3.0]]"))
        check("A2. one vertex is SUSPECT_NEEDS_TWO_VERTICES", code(r) == "SUSPECT_NEEDS_TWO_VERTICES", repr(r))

        # ---- the other typed refusals (every REFUSAL row reached)
        for ident, tail, want in (("none", "", "SUSPECT_ABSENT"), ("noplane", section("[[0.1, 3.0], [0.2, 4.0]]", plane=None), "PLANE_ABSENT"),
                                  ("pair", section('[[0.1, 3.0], [0.2]]'), "SUSPECT_VERTEX_NOT_A_PAIR"), ("pairs", section('[[0.1, 3.0], [0.2, "4"]]'), "SUSPECT_VERTEX_NOT_A_PAIR")):
            r = suspect(fam, ident, tail)
            check(f"A1. {want} is a typed refusal", code(r) == want, repr(r))

        # ---- A5 a second knob
        two = [(h, rows(PEAK, f",{p}")) for p in (1.0, 2.0) for h in (0.1, 0.2, 0.3)]
        run_p = lambda t: t.replace('identity = "NONE"', 'identity = "RUN"', 1).replace('[replicate.key]\nkind = "NONE"', '[replicate.key]\nkind = "COLUMN"\ncolumn = "p"', 1)
        kw = {"edit": run_p, "head": "T,C,sigma,p,h\n"}
        r = suspect(two, "knob", section("[[0.1, 3.0], [0.3, 4.0]]"), **kw)
        check("A5. a varying second knob without [plane.slice] is PLANE_NEEDS_A_SLICE", code(r) == "PLANE_NEEDS_A_SLICE", repr(r))
        r = suspect(two, "slice", section("[[0.1, 3.0], [0.3, 4.0]]", sl='[plane.slice]\ncolumn = "p"\nvalue = 2.0\n'), **kw)
        check("A5. with the slice it converts on that slice's three curves", r == S.Cells(((0, 2), (2, 3)), "grid", 3, 7), repr(r))
        r = suspect(two, "wrong", section("[[0.1, 3.0], [0.3, 4.0]]", sl='[plane.slice]\ncolumn = "h"\nvalue = 2.0\n'), **kw)
        check("A5. a slice naming another column is PLANE_SLICE_NOT_THE_SECOND_KNOB", code(r) == "PLANE_SLICE_NOT_THE_SECOND_KNOB", repr(r))
        r = suspect(two, "empty", section("[[0.1, 3.0], [0.3, 4.0]]", sl='[plane.slice]\ncolumn = "p"\nvalue = 3.0\n'), **kw)
        check("A5. a slice value no curve carries is PLANE_SLICE_SELECTS_NO_CURVE", code(r) == "PLANE_SLICE_SELECTS_NO_CURVE", repr(r))

        # ---- A3 v13 declarations lint identically
        (tmp / "declarations" / "plain").mkdir(parents=True)
        plants = [("per_file", per_file(m, "plain")), ("long_table", long_table(m, "plain"))] + [(f"CHOICE_PLANTS {c}: {w}", e(per_file(m, "plain"))) for c, w, e in CHOICE_PLANTS]
        diff = [n for n, text in plants if lint(rooted(T, tmp), tmp / "declarations" / "plain", text, []) != lint(rooted(T13, tmp), tmp / "declarations" / "plain", text, [])]
        check(f"A3. every planted declaration ({len(plants)}) lints identically under v14 and v13", not diff, str(diff[:3]))
        added = per_file(m, "plain") + section("[[0.1, 3.0], [0.2, 4.0]]", sl='[plane.slice]\ncolumn = "p"\nvalue = 2.0\n')
        v14, v13 = lint(rooted(T, tmp), tmp / "declarations" / "plain", added, []), lint(rooted(T13, tmp), tmp / "declarations" / "plain", added, [])
        check("A3. [plane] and [suspect] pass S0 under v14 and are FIELD_UNKNOWN under v13", v14.startswith("S0 EXECUTED, PASS") and v13.startswith("S0 EXECUTED, REFUSE FIELD_UNKNOWN"), v14[:200] + " | " + v13[:200])


try:
    planted()
except Exception as e:   # a mutation that breaks the conversion's types stops the planted checks; it is a failure, named here
    check("A1-A5. the planted families run to the end", False, repr(e)[:300])

decls = sorted(p for p in (ROOT / "declarations").iterdir() if (p / "intake.toml").is_file())
diff = []
for d in decls:
    text, found = intake.declared(d), intake._findings(ROOT, d, d.name)
    diff += [d.name] * (lint(T, d, text, found) != lint(T13, d, text, found))
check(f"A3. every committed declaration ({len(decls)}) lints identically under v14 and v13", len(decls) > 0 and not diff, str(diff))

check("A1-A5. every REFUSAL row was reached, and every code reached is a row", reached - {None} == set(S.REFUSAL), str(sorted(set(S.REFUSAL) ^ (reached - {None}))))

# ---- A6 role, closure, budget
ck = tomllib.loads((ROOT / "checks.toml").read_text())
check("A6. intake_suspect is its own role, and outside the measurement closure",
      ck["roles"].get("intake_suspect") == ["cc/intake_suspect.py"] and "cc/intake_suspect.py" in ck["closure"]["measure"]["outside"], str(ck["roles"].get("intake_suspect")))
bud = subprocess.run([sys.executable, str(ROOT / "tests" / "test_budget.py")], capture_output=True, text=True)
check("A6. tests/test_budget.py passes (SUSPECT_CAP and the disjointness of intake_suspect)", bud.returncode == 0, (bud.stdout + bud.stderr)[-300:])

print("test_suspect: " + ("FAILED " + "; ".join(bad) if bad else "all passed"))
sys.exit(1 if bad else 0)
