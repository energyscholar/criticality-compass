"""test_reach - plan 1282 P1c: cc/seal_reach.reach, licence_total and seal. The declaration (m.toml, couplings.toml) is edited IN MEMORY from inputs/k4-m1-ch; no file is written.
B1 k4-m1-ch alone leaves the 3 needle_o atoms unreached; B2 x8-ising-needle-ch leaves 9; B3-old (the replaced section-2 line: names = [K], probes = [], no control relation) leaves six; B3-A4 (A4.1 + needle_o, A4.10)
reaches all 12; B4 the licence table is total over verdict.toml's 14 refuse codes; B5/B6 seal returns the Unreachable / a Sealable; B7 a control relation that leaves five points untouched fails clause (iii). B8 (plan 1282 P2a, R-P2.2) isolates clause (ii): B3-A4 without relations.size (control still touches every point, so (iii)
is evaluable and passes) fails (ii) by a refusal VALUE, "relation size not declared".
Data-free. Seen RED on e90c90f (cc/seal_reach.py absent: every case FAILs on ModuleNotFoundError). B8 seen RED on 3e0b80f with seal_reach.why_instrument's relation()
mutated to return None: B8 FAILs by value (a Reach), no KeyError."""
import copy
import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
from lib import bad, bootstrap, check, guarded  # noqa: E402
bootstrap(ROOT, "cc", "cc/instruments")

LABELS = ["0.90", "0.95", "0.98", "1.00", "1.02", "1.05", "1.10"]
A4_TEXT = "the declared order of the points: K increasing, 0.90 -> 1.10"
NEEDLE_O = ["needle_o.d_dis", "needle_o.d_ord", "needle_o.velocity"]
ALL12 = ["across.y_last", "across_delta.y_last", "declared.probe", "needle.d_dis", "needle.d_ord", "needle.velocity", "needle_chain.drift", *NEEDLE_O, "stability_delta.d", "two_start.D"]


def load(i):
    return tomllib.loads((ROOT / "inputs" / i / "m.toml").read_text()), tomllib.loads((ROOT / "inputs" / i / "couplings.toml").read_text())


def b3_base():
    """k4-m1-ch with 7 points K/K_c 0.90..1.10 and the control relation of A4.1, in memory."""
    m, cp = copy.deepcopy(load("k4-m1-ch"))
    m["axes"]["point"] = list(LABELS)
    m["obtained"] = {x: "observed" for x in LABELS}
    m["relations"]["control"]["coupling"] = "K"
    m["relations"]["control"]["direction_from"] = A4_TEXT
    return m, cp


def b3_old():
    m, cp = b3_base()
    cp["names"], cp["probes"] = ["K"], []
    del m["relations"]["control"]
    return m, cp


def b3_a4():
    m, cp = b3_base()
    cp["names"] = cp["probes"] = ["K"]
    m["instruments"].append("needle_o")
    return m, cp


def tables():
    import detect
    return detect.load_tables("v10-rules")


def names(r):
    return [a.name for a in r.atoms]


def whys(r):
    return {a.name: a.why for a in r.atoms}


def b1():
    import seal_reach as R
    r = R.reach(*load("k4-m1-ch"), tables(), ROOT)
    check("B1 k4-m1-ch alone is Unreachable", isinstance(r, R.Unreachable), repr(r)[:200])
    check("B1 exactly the 3 needle_o atoms, each not declared", names(r) == NEEDLE_O and set(whys(r).values()) == {"instrument needle_o not declared"}, repr(whys(r)))


def b2():
    import seal_reach as R
    r = R.reach(*load("x8-ising-needle-ch"), tables(), ROOT)
    check("B2 x8-ising-needle-ch is Unreachable with 9 atoms", isinstance(r, R.Unreachable) and len(r.atoms) == 9, repr(r)[:200])
    check("B2 declared.probe says probe_of = NOT-MEASURED", whys(r)["declared.probe"] == "probe_of = NOT-MEASURED", repr(whys(r)))


def b3_old_case():
    import seal_reach as R
    r = R.reach(*b3_old(), tables(), ROOT)
    check("B3-old is Unreachable", isinstance(r, R.Unreachable), repr(r)[:200])
    want = {"declared.probe": "probe_of = INCOMPLETE", "across_delta.y_last": "relation control not declared", "stability_delta.d": "relation control not declared",
            **dict.fromkeys(NEEDLE_O, "instrument needle_o not declared")}
    check("B3-old exactly six atoms, each with its why", whys(r) == want, repr(whys(r)))
    check("B3-old atoms are sorted by name", names(r) == sorted(names(r)), str(names(r)))


def b3_a4_case():
    import seal_reach as R
    r = R.reach(*b3_a4(), tables(), ROOT)
    check("B3-A4 is Reach of all 12 atoms", isinstance(r, R.Reach) and list(r.atoms) == ALL12, repr(r)[:300])


def b4():
    import seal_reach as R
    refuse = tables().verdict["refuse"]
    r = R.licence_total(refuse)
    check("B4 Licensed, 14 codes in verdict.toml order", isinstance(r, R.Licensed) and list(r.codes) == refuse and len(refuse) == 14, repr(r)[:200])
    g = R.licence_total([*refuse, "REFUSE-PLANTED"])
    check("B4 a code outside the table is a LicenceGap", g == R.LicenceGap(("REFUSE-PLANTED",), ()), repr(g))
    h = R.licence_total(refuse[1:])
    check("B4 a table code the verdict lacks is the gap's extra", h == R.LicenceGap((), (refuse[0],)), repr(h))


def b5():
    import seal_reach as R
    m, cp = b3_old()
    r = R.seal("1282-v10", m, cp, tables(), ROOT)
    check("B5 seal on B3-old is the Unreachable", r == R.reach(m, cp, tables(), ROOT) and isinstance(r, R.Unreachable), repr(r)[:200])


def b6():
    import seal_reach as R
    m, cp = b3_a4()
    r = R.seal("1282-v10", m, cp, tables(), ROOT)
    ok = isinstance(r, R.Sealable)
    check("B6 seal on B3-A4 is Sealable", ok, repr(r)[:200])
    check("B6 924 seeds, 12 atoms", len(r.seeds.run) + len(r.seeds.pilot) == 924 and len(r.atoms) == 12, f"{len(r.seeds.run)} {len(r.seeds.pilot)} {len(r.atoms)}")


def b7():
    import seal_reach as R
    m, cp = b3_a4()
    m["relations"]["control"]["template"] = "pair"
    m["relations"]["control"]["pairs"] = [["0.90", "0.95"]]
    r = R.reach(m, cp, tables(), ROOT)
    why = "points ['0.98', '1.00', '1.02', '1.05', '1.10'] touched by no control pair"
    check("B7 exactly across_delta.y_last and stability_delta.d, each with the untouched points", isinstance(r, R.Unreachable) and whys(r) == {"across_delta.y_last": why, "stability_delta.d": why}, repr(r)[:300])


def b8():
    import seal_reach as R
    m, cp = b3_a4()
    del m["relations"]["size"]
    r = R.reach(m, cp, tables(), ROOT)
    want = dict.fromkeys(["across.y_last", "across_delta.y_last", "needle_chain.drift", "stability_delta.d"], "relation size not declared")
    check("B8 clause (ii) alone: exactly the four atoms reading relation size, each not declared", isinstance(r, R.Unreachable) and whys(r) == want, repr(r)[:300])


for name, fn in (("B1", b1), ("B2", b2), ("B3-old", b3_old_case), ("B3-A4", b3_a4_case), ("B4", b4), ("B5", b5), ("B6", b6), ("B7", b7), ("B8", b8)):
    guarded(name, fn)
print("".join(f"FAILED {b}\n" for b in bad) + "test_reach: " + ("FAILED" if bad else "all passed"))
sys.exit(1 if bad else 0)
