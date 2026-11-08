"""test_seeds - plan 1282 P1c: cc/seal_reach.seal_seeds, the seed refusal of the seal (PRE section 4, A4.4, A4.9). D1 the production seal: 840 run + 84 pilot seeds, all distinct, in [3e9, 4e9);
D2 a seed_fn blind to j is a SeedClash whose dups are the exact (seed, keys) the sha256 formula gives; D3 a planted inventory range is a SeedClash naming it; D4 another S gives 840 disjoint run seeds.
Data-free. Seen RED on e90c90f (cc/seal_reach.py absent: every case FAILs on ModuleNotFoundError)."""
import hashlib
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
from lib import bad, bootstrap, check, guarded  # noqa: E402
bootstrap(ROOT, "cc", "cc/instruments")

S = "1282-v10"


def formula(S, F, k, L, s, j):
    """PRE section 4, written out here from the sha256, independent of cc/sampler.py."""
    return 3_000_000_000 + int(hashlib.sha256(f"1282|{S}|{F}|{k}|{L}|{s}|{j}".encode("utf-8")).hexdigest()[:8], 16) % 1_000_000_000


def d1():
    import seal_reach as R
    r = R.seal_seeds(S)
    ok = isinstance(r, R.Seeds)
    check("D1 the production seal is Seeds", ok, repr(r)[:200])
    allseeds = r.run + r.pilot
    check("D1 840 run seeds and 84 pilot seeds", len(r.run) == 840 and len(r.pilot) == 84, f"{len(r.run)} {len(r.pilot)}")
    check("D1 all 924 are distinct", len(set(allseeds)) == 924, str(len(set(allseeds))))
    check("D1 every seed is in [3e9, 4e9)", all(3_000_000_000 <= x < 4_000_000_000 for x in allseeds), f"{min(allseeds)} {max(allseeds)}")
    check("D1 the first run seed is the formula's for (poc, 0.90, 27, ordered, 0)", r.run[0] == formula(S, "poc", "0.90", 27, "ordered", 0), str(r.run[0]))


def d2():
    import seal_reach as R
    r = R.seal_seeds(S, seed_fn=lambda S_, F, k, L, s, j: formula(S_, F, k, L, s, 0))
    check("D2 a seed_fn blind to j is a SeedClash", isinstance(r, R.SeedClash), repr(r)[:200])
    keys = tuple(sorted((("poc", "0.90", 27, "ordered", j) for j in (*range(10), "pilot")), key=repr))
    want = (formula(S, "poc", "0.90", 27, "ordered", 0), keys)
    check("D2 the clash is exactly the sha256 seed and its eleven keys", want in r.dups, f"{want} not in {r.dups[:1]}")
    check("D2 84 duplicated seeds, none in the inventory", len(r.dups) == 84 and r.hits == (), f"{len(r.dups)} {r.hits[:1]}")


def d3():
    import seal_reach as R
    s0 = R.seal_seeds(S).run[0]
    r = R.seal_seeds(S, inventory=((s0, s0 + 1, "planted"),))
    check("D3 a planted range is a SeedClash", isinstance(r, R.SeedClash), repr(r)[:200])
    check("D3 it names the range and the one key", r.hits == ((s0, ("poc", "0.90", 27, "ordered", 0), "planted"),) and r.dups == (), repr(r.hits))


def d4():
    import seal_reach as R
    a, b = R.seal_seeds(S), R.seal_seeds("1282-other")
    check("D4 another S is Seeds with 840 run seeds", isinstance(b, R.Seeds) and len(b.run) == 840, repr(b)[:200])
    check("D4 its run seeds are disjoint from D1's", not set(a.run) & set(b.run), str(len(set(a.run) & set(b.run))))


for name, fn in (("D1", d1), ("D2", d2), ("D3", d3), ("D4", d4)):
    guarded(name, fn)
print("".join(f"FAILED {b}\n" for b in bad) + "test_seeds: " + ("FAILED" if bad else "all passed"))
sys.exit(1 if bad else 0)
