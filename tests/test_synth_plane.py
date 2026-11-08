"""test_synth_plane - plan 1176 phase C: the planted real-shaped 2-D bank (cc/intake_synth.py --plane), walked by `bin/cc navigate family` and
scored by `bin/cc navigate score` (tests/plane_plant.py), and the plane breakers (tests/breakers-plane/1176-*.toml). Seed 1176, every family x
density of plane_plant.CASES (dense: 30 curves x 30 samples; sparse: 4 slices x 9 curves x 30 samples). It reads no real data.
Plan 1176 C' (O5): a check that gates a STOCHASTIC outcome (C3, C4, C5) is an ENSEMBLE statement over the declared seed list SEEDS (10 seeds,
1176-1185, the RECON's), never one seed (RECON-C run 1: seed 1176 is a clean seed for the sparse decoy, so a one-seed C4 was a lucky green);
per-seed checks remain only for deterministic type facts (C1, C2, C6, the breakers at seed 1176).
Each check names its red mutation (applied with `bin/cc mutate`, seen FAIL by this name):
 C1. the sharp dense bank reaches PRIMARY_READY, truth.json is absent from every bank, and no access log of the intake or the navigator names
     it. Red: plane_write writes truth.json inside the bank (`(truth / "truth.json")` -> `(bank / "truth.json")`).
 C2. two generations of every family x density at one seed are byte-identical (bank files, MANIFEST.json, truth.json). Red: a second rng (the
     noise drawn from np.random.default_rng() unseeded).
 C3. (ensemble) on every seed the sharp dense family walks FOLLOWED_IN_CORRIDOR and every checkpoint (the planted line on each interior curve) scores within w_c.
     Red: the planted slope tilted in the data only (sharp's centre sharp_c(h, p) + 1.2 h, a +-8.7-sample tilt, beyond w_c; the declared guess unchanged; + 0.6 h stays inside w_c and was seen GREEN).
 C4. THE HEADLINE (C' acceptance, ruling 10-20): over the ensemble (SEEDS x dense, and SEEDS x the 4 sparse slices) the decoy crossover arc is
     never FOLLOWED_IN_CORRIDOR with an all-narrow path census (every traced point's curve Located), although its arc lies inside the
     suspect's corridor (sag < w_c: FOLLOWED is reachable, so this check CAN fire). A FOLLOWED decoy whose path crosses a Broad or AtSpanEnd
     curve is reported, typed, not a failure (a broad maximum drifting smoothly IS a locus of maxima; DIAG-C E1). Red: the sigma-plateau
     collapsed to the single argmax sample (intake_feature BRACKET "COLUMN" -> (rank, rank)); Broad made Located (KIND (False, True) -> Located).
 C5. (ensemble) the null (monotone) family acquires no line at either density on any seed: verdict INDETERMINATE, terminals none, never FOLLOWED. (Spec said ABSENT:
     frozen linenav types a corridor of UNREAD windows INDETERMINATE; ABSENT needs CLEAR, i.e. resolved reads, which B1 forbids on a monotone
     curve.) Red: a bump seeded into the null family (null's C + the sharp peak).
 C3m. (plan 1176 C'', O4, acceptance (b)) the MISALIGNED-grid variant (the sharp line on per-curve subsets of a 61-point master grid) follows
     like the aligned one: on every seed FOLLOWED_IN_CORRIDOR with every checkpoint within w_c. Red: rank coordinates (the oracle reads the query's
     fast as the same RANK FRACTION of each curve's own samples: Oracle.__call__'s fast = v[round(u1 (n - 1))] of the nearest curve).
 Plan 1176 C'' (O4): the declarations walk corridor "continuous" (span units, w_c 0.15 of each span); C4's reachability check is restated in
     span units (sag / fast span < w_c; decoy half-width >= 3 w_c of the span).
 C6. every outcome is typed: a linenav.Verdict member or a plane_plant.Refused code, and every verdict cell of the RECON table names one.
     Red: plane_plant.outcome returns the bare word (`lambda: linenav.Verdict[word]` -> `lambda: word`).
 BREAKER <id>: each tests/breakers-plane/*.toml's observed break (HOLDS when every declaration of its case meets [expect], else FAILS) is
     the break it declares. Red: the breaker's declared break flipped (each file's own `break`), or the rule it states broken in code."""
import hashlib
import json
import re
import sys
import tempfile
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
from lib import bad, bootstrap, check  # noqa: E402
bootstrap(ROOT, "cc", "tests")
import intake_synth  # noqa: E402
import linenav  # noqa: E402
import plane_plant as P  # noqa: E402

SEED = 1176
SEEDS = tuple(range(1176, 1186))   # O5: the declared seed list of every ensemble check (>= 10), the RECON's seeds
ENSEMBLE = [("sharp", "dense"), ("misaligned", "dense"), ("decoy", "dense"), ("decoy", "sparse"), ("null", "dense"), ("null", "sparse")]   # the cases C3, C3m, C4, C5 read
SPAN_T = float(intake_synth.PLANE_GRID[-1] - intake_synth.PLANE_GRID[0])   # the bank's fast span (every aligned curve's; the master grid's ends)
WC = linenav.PARAMS["continuous"]["wc"]   # C'': the frozen continuous corridor, a fraction of each span


def digest(d):
    return {str(p.relative_to(d)): hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(d.rglob("*")) if p.is_file()}


def c2():
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        for f, d in P.CASES:
            [intake_synth.plane_write(tmp / g / "bank", tmp / g / "truth", "x", SEED, f, d) for g in ("a", "b")]
            check(f"C2. {f} {d}: two generations at one seed are byte-identical", digest(tmp / "a") == digest(tmp / "b"),
                  str(sorted(k for k in digest(tmp / "a") if digest(tmp / "a")[k] != digest(tmp / "b").get(k)))[:200])
            [__import__("shutil").rmtree(tmp / g) for g in ("a", "b")]


def breakers(w, banks, tmp, rows):
    """Each plane breaker: its case's outcomes (reusing the main rows for an unedited case at SEED), then HOLDS or FAILS against [expect]."""
    files = sorted((ROOT / "tests" / "breakers-plane").glob("*.toml"))
    check("BREAKER the plane breakers exist (6)", len(files) == 6, str([f.name for f in files]))
    for f in files:
        b = tomllib.loads(f.read_text())
        c, e = b["case"], b["expect"]
        reuse = {True: lambda: [v for fam, den, p, v in rows if fam == c["family"] and den in c["densities"]], False: lambda: None}[c["edit"] == "none" and c["seed"] == SEED]()
        got = reuse if reuse is not None else [P.walked(w, ident, held)[1] for den in c["densities"]
                                               for _, _, _, ident, held in P.plant_all(w, banks, tmp, c["seed"], [(c["family"], den)], c["edit"], f"-{b['id']}")]
        names = [v.name for v in got]
        holds = len(names) > 0 and not set(names) & set(e.get("never", [])) and set(names) <= set(e.get("only", names))
        observed = {True: "HOLDS", False: "FAILS"}[holds]
        print(f"BREAK {b['id']}: {observed} (declared {b['break']}): {', '.join(names)}")
        check(f"BREAKER {b['id']}: observed {observed} is the declared {b['break']}", observed == b["break"] and b["id"] == f.stem, ", ".join(names))


def main():
    c2()
    with tempfile.TemporaryDirectory() as tmp:
        w, banks = P.copy(tmp)
        planted = P.plant_all(w, banks, tmp, SEED)
        walked = {ident: P.walked(w, ident, held) for _, _, _, ident, held in planted}
        rows = [(f, d, p, walked[i][1]) for f, d, p, i, _ in planted]
        for f, d, p, i, _ in planted:
            print(f"  {i}: {walked[i][0]} {getattr(walked[i][1], 'name', walked[i][1])} [{walked[i][2]}] {walked[i][3]}/{walked[i][4]} within w_c")
        by = lambda f, d: [(i, walked[i]) for ff, dd, _, i, _ in planted if (ff, dd) == (f, d)]   # noqa: E731
        name = lambda v: getattr(v, "name", None)   # noqa: E731

        # ---- C1 the truth is outside every bank, and nothing the intake or the navigator opened names it
        sid, sw = by("sharp", "dense")[0]
        check("C1. the sharp dense bank reaches PRIMARY_READY", sw[0] == "PRIMARY_READY", sw[0])
        inside = [str(p.relative_to(banks)) for p in banks.rglob("*") if "truth" in p.name.lower()]
        check("C1. truth.json is absent from every bank", inside == [], str(inside[:3]))
        logs = [*(w / "declarations").glob("*/access.log"), *(w / "results" / "navigate").glob("*.jsonl")]
        named = [str(p.name) for p in logs if re.search(r"truth|TRUTH", p.read_text())]
        check("C1. no access log of the intake or the navigator names the truth", len(logs) > 0 and named == [], f"{len(logs)} logs; naming it: {named[:3]}")

        # ---- the ensemble (O5): SEEDS x ENSEMBLE; seed SEED reuses the walks above
        ens = {(f, d, s): [x for ff, dd, _, i, _ in planted if (ff, dd) == (f, d) for x in [walked[i]]] for f, d in ENSEMBLE for s in (SEED,)}
        for s in SEEDS[1:]:
            for f, d, _, i, held in P.plant_all(w, banks, tmp, s, ENSEMBLE):
                x = P.walked(w, i, held)
                ens.setdefault((f, d, s), []).append(x)
                print(f"  {i}: {x[0]} {getattr(x[1], 'name', x[1])} [{x[2]}] {x[3]}/{x[4]} within w_c; census {P.census_cell(x[7])}; path [{P.kinds_cell(x[8])}]")
        runs = lambda f, d: [x for s in SEEDS for x in ens[(f, d, s)]]   # noqa: E731

        # ---- C3 the sharp line, dense, every seed
        sh = runs("sharp", "dense")
        check(f"C3. the sharp dense line walks FOLLOWED_IN_CORRIDOR on every seed ({len(SEEDS)})", len(sh) == len(SEEDS) and all(name(x[1]) == "FOLLOWED_IN_CORRIDOR" for x in sh),
              str([name(x[1]) for x in sh]))
        check("C3. every checkpoint of the sharp dense line is within w_c on every seed", len(sh) == len(SEEDS) and all(x[4] > 0 and x[3] == x[4] for x in sh), str([f"{x[3]}/{x[4]}" for x in sh]))

        # ---- C3m the misaligned grids follow like the aligned ones (C'' acceptance (b))
        mis = runs("misaligned", "dense")
        check(f"C3m. the misaligned-grid line walks FOLLOWED_IN_CORRIDOR on every seed ({len(SEEDS)}), like the aligned one",
              len(mis) == len(SEEDS) and all(name(x[1]) == "FOLLOWED_IN_CORRIDOR" for x in mis), str([name(x[1]) for x in mis]))
        check("C3m. every checkpoint of the misaligned-grid line is within w_c on every seed", len(mis) == len(SEEDS) and all(x[4] > 0 and x[3] == x[4] for x in mis),
              str([f"{x[3]}/{x[4]}" for x in mis]))

        # ---- C4 the decoy: never FOLLOWED with an all-narrow path census, over the ensemble
        check("C4. the decoy arc lies inside the suspect's corridor (sag < w_c of the fast span): FOLLOWED is reachable, the gate can fire",
              intake_synth.SAG / SPAN_T < WC and intake_synth.W_D >= 3 * WC * SPAN_T - 1e-12, f"sag {intake_synth.SAG / SPAN_T:.3f} of the span")
        for d in ("dense", "sparse"):
            got = runs("decoy", d)
            fol = [x for x in got if name(x[1]) == "FOLLOWED_IN_CORRIDOR"]
            bad4 = [P.kinds_cell(x[8]) for x in fol if P.narrow(x[8])]
            print(f"C4 decoy {d}: {len(got)} runs, FOLLOWED {len(fol)} (path kinds: {[P.kinds_cell(x[8]) for x in fol]}), FOLLOWED with an all-Located path {len(bad4)}")
            check(f"C4. the decoy ({d}, {len(got)} runs over {len(SEEDS)} seeds) is never FOLLOWED_IN_CORRIDOR with an all-Located path census",
                  len(got) == len(SEEDS) * len(intake_synth.DENSITY[d][1]) and all(name(x[1]) is not None for x in got) and bad4 == [], str(bad4)[:300])

        # ---- C5 the null family, every seed
        for d in ("dense", "sparse"):
            got = [(name(x[1]), x[2]) for x in runs("null", d)]
            check(f"C5. the null family ({d}, {len(got)} runs over {len(SEEDS)} seeds) acquires no line: INDETERMINATE, terminals none, never FOLLOWED",
                  len(got) == len(SEEDS) * len(intake_synth.DENSITY[d][1]) and all(v == "INDETERMINATE" and t.startswith("none") for v, t in got),
                  str([g for g in got if g[0] != "INDETERMINATE"][:5]))

        # ---- C6 typed outcomes, and the RECON table's verdict column
        check("C6. every outcome is a linenav.Verdict member or a typed Refused", all(isinstance(v, (linenav.Verdict, P.Refused)) for *_, v in rows),
              str([v for *_, v in rows if not isinstance(v, (linenav.Verdict, P.Refused))][:3]))
        alphabet = set(linenav.Verdict.__members__) | {v.code for *_, v in rows if isinstance(v, P.Refused)}
        md = P.table([(f, d, p, SEED, *walked[i][:5], *walked[i][7:9]) for f, d, p, i, _ in planted])
        cells = [ln.split("|")[6].strip() for ln in md.splitlines()[2:] if ln.startswith("| ") and ln.count("|") == 11]
        check("C6. every verdict cell of the RECON table is in the alphabet", len(cells) == len(planted) and set(cells) <= alphabet, str(sorted(set(cells) - alphabet)))

        breakers(w, banks, tmp, rows)


try:
    main()
except Exception as e:   # a crash is a named FAIL, never a silent pass
    check("C1-C6. the checks run to the end", False, repr(e)[:300])
print(f"FAILED: {', '.join(bad)}" if bad else "test_synth_plane: all passed")
sys.exit(1 if bad else 0)
