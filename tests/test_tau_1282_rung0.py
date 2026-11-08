"""test_tau_1282_rung0 - plan 1282 P2c: the rung 0 tool (tests/tau_1282_rung0.py). R1 the chain table equals the declared 41 chains value for value and the skip rule reproduces every skip
from its tau_low; R2 the 41 run seeds and the 16 bench seeds are >= 3e9, pairwise distinct and disjoint from the 840 run seeds and the 84 pilot seeds; R3 the cost formula on a hand fixture
(three cells, one `ordered-of`) returns 18.072123958333332 core-h and 1.7x that at f = 1.7; R4 the stripe partition at the midpoint of the two attractors.
Needs no data root and touches no toolset. Seen RED on a detached CC worktree (the tool absent); R3 also seen RED by mutation (the burn term dropped)."""
import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
from lib import bad, bootstrap, check, guarded  # noqa: E402
bootstrap(ROOT, "cc", "cc/instruments")

TOOL = ROOT / "tests" / "tau_1282_rung0.py"


def tool():
    spec = importlib.util.spec_from_file_location("tau_1282_rung0", TOOL)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


# (k, L, start, tag, burn, skip, N) in the brief's order: cells 1-14, cells 9-11 at tags rung0.0 .. rung0.9
def declared():
    one = [("1.00", 27, "ordered", 5_000, 1, 200_000), ("1.00", 27, "random", 5_000, 1, 200_000), ("1.00", 81, "ordered", 30_000, 10, 200_000), ("1.00", 81, "random", 30_000, 10, 200_000),
           ("0.98", 81, "ordered", 100_000, 10, 200_000), ("1.00", 243, "ordered", 320_000, 100, 240_000), ("1.00", 243, "random", 320_000, 100, 240_000),
           ("0.98", 243, "ordered", 200_000, 10, 200_000)]
    ten = [("1.02", 243, "random", 60_000, 1, 200_000), ("1.05", 243, "random", 60_000, 1, 200_000), ("1.10", 243, "random", 60_000, 1, 200_000)]
    ord3 = [("1.02", 243, "ordered", 2_000, 1, 200_000), ("1.05", 243, "ordered", 2_000, 1, 200_000), ("1.10", 243, "ordered", 2_000, 1, 200_000)]
    out = [(k, L, s, "rung0", b, sk, n) for k, L, s, b, sk, n in one]
    for k, L, s, b, sk, n in ten:
        out += [(k, L, s, f"rung0.{j}", b, sk, n) for j in range(10)]
    return out + [(k, L, s, "rung0", b, sk, n) for k, L, s, b, sk, n in ord3]


def r1():
    m = tool()
    got = [(c.cell.k, c.cell.L, c.cell.start, c.tag, c.run.burn, c.run.skip, c.run.N) for c in m.chain_table()]
    check("R1 the chain table has 41 chains", len(got) == 41, str(len(got)))
    check("R1 the chain table equals the declared 41, value for value", got == declared(), str([(a, b) for a, b in zip(got, declared()) if a != b][:3]))
    want = {58: 1, 630: 10, 185: 10, 6_800: 100, 133: 10, 60: 1, 21: 1, 6.8: 1}
    check("R1 skip_of reproduces the skip of every cell from its tau_low", all(m.skip_of(t) == sk for t, sk in want.items()), str({t: m.skip_of(t) for t in want}))
    check("R1 each cell's skip is skip_of(tau_low)", all(c.run.skip == m.skip_of(c.cell.tau_low) for c in m.chain_table()), "")
    check("R1 skip_of is the largest ladder step <= tau_low / 10 (boundaries)", [m.skip_of(x) for x in (9.99, 10, 99.9, 100, 999.9, 1000, 5000)] == [1, 1, 1, 10, 10, 100, 100], str([m.skip_of(x) for x in (9.99, 10, 99.9, 100, 999.9, 1000, 5000)]))


def r2():
    import sampler
    m = tool()
    runs = [c.seed for c in m.chain_table()]
    bench = [m.bench_seed(L, s) for L in (27, 81, 243) for s in (1, 10, 100, 1000)] + [m.contended_seed(i) for i in range(4)]
    check("R2 41 run seeds and 16 bench seeds", len(runs) == 41 and len(bench) == 16, f"{len(runs)} {len(bench)}")
    allp = runs + bench
    check("R2 all 57 are >= 3e9", min(allp) >= 3_000_000_000, str(min(allp)))
    check("R2 all 57 are pairwise distinct", len(set(allp)) == 57, str(len(set(allp))))
    old = {sampler.seed_of("1282-v10", F, k, L, s, j) for F, k, L, s in sampler.cells() for j in range(10)}
    pilot = {sampler.seed_of("1282-v10", F, k, L, s, "pilot") for F, k, L, s in sampler.cells()}
    check("R2 the 840 run seeds and the 84 pilot seeds are those counts", len(old) == 840 and len(pilot) == 84, f"{len(old)} {len(pilot)}")
    check("R2 disjoint from the 840 run seeds and the 84 pilot seeds", not (set(allp) & old) and not (set(allp) & pilot), str(sorted(set(allp) & (old | pilot))[:3]))


def fixture():
    m = tool()
    A, B, C, D = ("poc", "1.00", 243, "ordered"), ("decoy", "1.00", 27, "random"), ("poc", "1.05", 81, "random"), ("poc", "1.05", 81, "ordered")
    taus = {A: (14_000.0, "rung0", "converged"), B: (10.0, "pilot", "converged"), C: (None, "ordered-of", None), D: (40.0, "pilot", "converged")}
    bn = m.Bench(y={(243, 1000): 230.0, (27, 10): 0.1, (81, 10): 0.5}, b={243: 0.22, 27: 0.003, 81: 0.025})
    return m, [A, B, C], taus, bn


def r3():
    m, cells, taus, bn = fixture()
    want = 18.072123958333332
    tot, rows = m.core_hours(cells, taus, bn, 1000)
    check("R3 core_hours on the hand fixture is 18.072123958333332 (rel 1e-12)", abs(tot - want) <= 1e-12 * want, repr(tot))
    check("R3 the cells' terms are 65,016,000 + 2,006 + 41,640.25 ms", [round(r["core_h"] * 3.6e6, 4) for r in rows] == [65_016_000.0, 2_006.0, 41_640.25], str([r["core_h"] * 3.6e6 for r in rows]))
    check("R3 the ordered-of cell takes its partner's tau and the L^2 burn", rows[2]["tau"] == 40.0 and rows[2]["burn"] == 6_561 and rows[2]["skip"] == 80 and rows[2]["sstar"] == 10, str(rows[2]))
    tot17, _ = m.core_hours(cells, taus, bn, 1000, 1.7)
    check("R3 at f = 1.7 the total is 1.7 x that value", abs(tot17 - 1.7 * tot) <= 1e-12 * tot17, repr(tot17))


def r4():
    m = tool()
    got = [m.stripe_class(x, 0.8) for x in (0.41, 0.39, 0.40)]
    check("R4 m = 0.41 / 0.39 / 0.40 at m_ord = 0.8 are ABOVE_MID / BELOW_MID / ABOVE_MID", got == ["ABOVE_MID", "BELOW_MID", "ABOVE_MID"], str(got))


for n, f in (("R1", r1), ("R2", r2), ("R3", r3), ("R4", r4)):
    guarded(n, f)
print("test_tau_1282_rung0: " + ("FAILED" if bad else "all passed"))
sys.exit(1 if bad else 0)
