"""test_chain_1205_p2b - plan 1205 P2b: the STRIDE axis of the edge lane ARGMAX_ABS_A_FAST (cc/chain.py, grid intake/grids/ll1-pre-v6.toml,
declared in research/1205/LL1-PRE-v6.md). It reads no real data. Each check names its red mutation (applied, seen FAIL by this name, reverted):
 P1. stride 1 equals the current lane: (a) in process, the v6 grid's stride-1 edge cells equal the v3 grid's edge cells, curve for curve; (b) the
     v3 golden test (tests/test_chain_1205.py, which compares the ll1-pre-v3 CLI output byte for byte with tests/chain/plant-chain.txt) passes.
     Red: the v3 output gains a stride field (stride_row() always returns a stride); and for (a) Stride.k returns max(2, ...).
 P2. a planted wide tanh step (width 0.01 of the span, 8000 samples, SNR 20: its adjacent-sample step is far below the noise): at stride 1 the
     location scatters (Located within w_c 0.05 of the planted centre on < 50% of curves); at the stride 0.01 of the span it is Located within
     w_c on >= 90%; with no noise the location is the edge MIDPOINT (i + k/2): within one sample of the centre. Red: _edges forces k = 1 (P2 near
     width fails); the place made w[:-k, 0] (the left sample: the noiseless midpoint check fails).
 P3. the grid: the v6 grid has 4 strides; the edge lane has 16 cells (4 x 4) and each sample lane 4; every edge cell carries the stride in samples
     and as a span fraction; a lane's robustness is counted over its own cells. Red: keys() ignores the strides (the edge lane has 4 cells).
 P4. STRIDE_EXCEEDS_WINDOW is reached through the CLI: a family of 30 samples under stride_samples = [1, 40] is typed STRIDE_EXCEEDS_WINDOW on every
     curve in the stride-40 cells (exit 0, the cell printed, never skipped) and Located in the stride-1 cells. Red: FIT made to answer FITS always.
 P5. a grid with a stride that is not a positive integer / a fraction in (0, 1]: REFUSED GRID_UNREADABLE, exit 1. Red: grid() accepts any stride.
 P6. every new enum member name parses (the binding rule's parser) to exactly its own atom, and StrideFit declares ATOMS and an Axiom.
     Red: a member NOT_STRIDE_FITS_WINDOW added to the class and its ATOMS."""
import json
import re
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
from lib import bad, bootstrap, cc as run_cc, check, parse  # noqa: E402
bootstrap(ROOT, "cc", "tests")
import chain  # noqa: E402
import intake_feature as F  # noqa: E402
import intake_synth as S  # noqa: E402
from intake_plant import long_table, write_long  # noqa: E402

V3, V6 = ROOT / "intake" / "grids" / "ll1-pre-v3.toml", ROOT / "intake" / "grids" / "ll1-pre-v6.toml"


@dataclass(frozen=True)
class Curve:
    slow: tuple
    rows: list


def fam(curves, kind="COLUMN"):
    return chain.Family("p2b", tuple(curves), tuple(float(c.slow[0]) for c in curves), F.span(curves, None), F.FAST_ENDS[True](curves, None), 2.0, kind, "h")


def step_curves(n=8000, k=30, width=0.01, snr=20.0, seed=1205, noise=True):
    """k curves of n samples (fast 0 .. 1): amplitude 1 tanh step of the given width (span units) centred at 0.3 + 0.01 j, noise sigma 1 / snr."""
    rng = np.random.default_rng(seed)
    u = np.arange(n) / (n - 1)
    sg = 1.0 / snr
    return [Curve((float(j),), [(float(a), float(b), sg) for a, b in zip(u, 0.5 * np.tanh((u - (0.3 + 0.01 * j)) / width) + (rng.normal(0, sg, n) if noise else 0.0))])
            for j in range(k)], [0.3 + 0.01 * j for j in range(k)]


def grid_file(tmp, text):
    p = Path(tmp) / "g.toml"
    p.write_text(text)
    return chain.grid(str(p))


EDGE = chain.Lane.ARGMAX_ABS_A_FAST
g3, g6 = chain.grid(str(V3)), chain.grid(str(V6))

# ---- P3 the grid
check("P3. the v6 grid declares 4 strides (1 sample; 0.001, 0.004, 0.016 of the span) and keeps the v3 w_c and lanes",
      isinstance(g6, chain.Grid) and [x.label for x in g6.strides] == ["1smp", "0.001span", "0.004span", "0.016span"] and g6.wc == g3.wc and g6.lanes == g3.lanes and g3.strides == (), str(g6))
check("P3. the edge lane has 16 cells (4 strides x 4 w_c), each sample lane 4, in the v6 grid; the v3 grid keeps 4 for the edge lane",
      [len(chain.keys(g6, ln)) for ln in g6.lanes] == [4, 4, 16] and [len(chain.keys(g3, ln)) for ln in g3.lanes] == [4, 4, 4], str([len(chain.keys(g6, ln)) for ln in g6.lanes]))
check("P3. the span strides round to the nearest sample, at least 1 (m = 8001: 0.001 -> 8, 0.004 -> 32, 0.016 -> 128; m = 100: 0.001 -> 1)",
      [s.k(8001) for s in g6.strides] == [1, 8, 32, 128] and [s.k(100) for s in g6.strides][1] == 1, str([s.k(8001) for s in g6.strides]))

# ---- P2 the planted wide step
cs, centre = step_curves()
fm = fam(cs)
grid6 = chain.Grid((0.05,), (EDGE,), "p2b", (chain.Stride(samples=1), chain.Stride(span=0.01)))
ev = chain.evaluate(fm, grid6)[EDGE]
within = lambda key, cen: np.mean([p.kind == "Located" and abs(p.pos - c) <= key[1] for p, c in zip(ev[key][0], cen)])   # noqa: E731
w1, w2 = within((chain.Stride(samples=1), 0.05), centre), within((chain.Stride(span=0.01), 0.05), centre)
check("P2. planted tanh step (width 0.01, SNR 20): at stride 1 the location scatters (Located within w_c 0.05 of the centre on < 50% of curves)", w1 < 0.5, f"{w1}")
check("P2. planted tanh step: at the stride 0.01 of the span it is Located within w_c 0.05 of the centre on >= 90% of curves", w2 >= 0.9, f"{w2}")
cn, cen_n = step_curves(noise=False)
evn = chain.evaluate(fam(cn), grid6)[EDGE]
err = max(abs(p.pos - c) for p, c in zip(evn[(chain.Stride(span=0.01), 0.05)][0], cen_n))
check("P2. noiseless: the located place is the edge MIDPOINT (i + k/2): within one sample (1/7999 of the span) of the centre", err <= 1 / 7999 + 1e-12, f"{err}")

# ---- P1a stride 1 equals the current lane
cl = [Curve((0.1 * (j + 1),), [(1.0 + i, 10.0 / (1 + (i - (8 + 2 * j)) ** 2), 0.03) for i in range(40)]) for j in range(9)]
e3, e6 = chain.evaluate(fam(cl), g3)[EDGE], chain.evaluate(fam(cl), g6)[EDGE]
check("P1. in process: the v6 grid's stride-1 edge cells equal the v3 grid's edge cells, curve for curve (4 w_c)",
      all(e6[(chain.Stride(samples=1), w)] == e3[w] for w in g3.wc) and len(e6) == 16, "")

# ---- P3 rows
ev6 = chain.evaluate(fam(cl), g6)
cells, atoms = chain.rows(fam(cl), g6, ev6)
edge = [c for c in cells if c["lane"] == EDGE.name]
check("P3. rows: 16 edge cells and 4 cells per sample lane; each edge cell names its stride, and each curve its stride in samples and as a span fraction",
      len(edge) == 16 and len([c for c in cells if c["lane"] == "ARGMAX_FAST"]) == 4 and all("stride" in c and all("stride_samples" in x and "stride_span" in x for x in c["curves"]) for c in edge)
      and all("stride" not in c for c in cells if c["lane"] != EDGE.name), str(edge[0])[:300])
check("P3. rows: stride 4 smp... the 0.016 span stride of 40 samples is k = 1 (0.016 x 39 = 0.6 rounds to 1); its fraction is k / 39",
      {(x["stride_samples"], round(x["stride_span"], 6)) for c in edge if c["stride"] == "0.016span" for x in c["curves"]} == {(1, round(1 / 39, 6))}, "")
check("P3. rows: the edge lane's cell counts in its family atoms sum to 16, a sample lane's to 4",
      sum(v["cells"] for v in atoms[EDGE.name].values()) == 16 and sum(v["cells"] for v in atoms["ARGMAX_FAST"].values()) == 4, str(atoms))

# ---- P6 names
E = chain.StrideFit
m = re.search(r"ATOMS:\s+([A-Z_\s|]+?)\.", E.__doc__ or "")
atoms_ = set(re.sub(r"\s", "", m[1]).split("|")) if m else set()
check("P6. StrideFit declares ATOMS and an Axiom, and its members are exactly the atoms", bool(atoms_) and "Axiom" in E.__doc__ and {x.name for x in E} == atoms_, f"{sorted(atoms_)} vs {sorted(x.name for x in E)}")
check("P6. every StrideFit name parses to its own atom alone (STRIDE_EXCEEDS_WINDOW included)", all(parse(x.name, atoms_) == {x.name} and x.value == x.name for x in E) and "STRIDE_EXCEEDS_WINDOW" in atoms_,
      str([x.name for x in E if parse(x.name, atoms_) != {x.name}]))


# ---- P1b, P4, P5 the CLI
def cli_checks():
    r = subprocess.run([sys.executable, str(ROOT / "tests" / "test_chain_1205.py")], capture_output=True, text=True, cwd=ROOT)
    check("P1. the v3 CLI golden (tests/test_chain_1205.py: ll1-pre-v3 output byte for byte) passes", r.returncode == 0, (r.stdout + r.stderr)[-400:])
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        w, banks = tmp / "cc", tmp / "banks"
        shutil.copytree(ROOT, w, ignore=shutil.ignore_patterns(".git", "__pycache__", "results", "benchmark", "fixtures", "data", "scratch"))
        with (w / "intake" / "ROOTS.toml").open("a") as f:
            f.write(f'\n"<chain-test>" = "{banks}"   # test_chain_1205_p2b: the planted banks\n')
        S.write(banks / "pf", tmp / "pf-TRUTH", "pf", 1, 9)
        man = json.loads((banks / "pf" / "MANIFEST.json").read_text())

        cc = lambda *args: run_cc(w, *args)[::-1]   # noqa: E731  (lib.cc returns (returncode, output); this call site reads (output, returncode))

        ident = "short"
        (banks / ident).mkdir()
        curves = [Curve((0.1 * (j + 1),), [(1.0 + i, 10.0 / (1 + (i - (8 + 2 * j)) ** 2), 0.03) for i in range(30)]) for j in range(9)]
        write_long(banks / ident, [(c.slow[0], [f"{r[0]:.4f},{r[1]:.4f},{r[2]:.4f}" for r in c.rows]) for c in curves])
        d = w / "declarations" / ident
        d.mkdir()
        text = long_table(man, ident).replace("<long-test>/pf", f"<chain-test>/{ident}") + '\n[plane]\naxes = "slow-fast"\n'
        (d / "intake.toml").write_text(text)
        (d / "transducer.toml").write_text(S.declare(man, ident, "pf")[2])
        [cc("intake", "profile", ident, root) for root in re.findall(r'^root = "([^"]*)"', text, re.M)[:1]]
        (tmp / "g-x.toml").write_text('wc = [0.05, 0.15]\nlanes = ["ARGMAX_FAST", "ARGMAX_ABS_A_FAST"]\nstride_samples = [1, 40]\n')
        out, rc = cc("chain", ident, "--grid", str(tmp / "g-x.toml"))
        res = w / "results" / "chain" / f"{ident}.json"
        doc = json.loads(res.read_text()) if res.is_file() else {"cells": []}
        by = {(c["stride"], c["wc"]): {x["kind"] for x in c["curves"]} for c in doc["cells"] if "stride" in c}
        check("P4. a stride of 40 samples over 30: every curve is STRIDE_EXCEEDS_WINDOW in the 2 stride-40 cells (exit 0, the cell printed)",
              rc == 0 and by.get(("40smp", 0.05)) == {"STRIDE_EXCEEDS_WINDOW"} and by.get(("40smp", 0.15)) == {"STRIDE_EXCEEDS_WINDOW"}
              and len(re.findall(r"^cell ARGMAX_ABS_A_FAST w_c \S+@40smp: NO_SEGMENT;.*STRIDE_EXCEEDS_WINDOW", out, re.M)) == 2, out[:700])
        check("P4. the stride-1 cells of the same run are Located (no kind is STRIDE_EXCEEDS_WINDOW), and the edge lane has 4 cells",
              by.get(("1smp", 0.05)) is not None and "STRIDE_EXCEEDS_WINDOW" not in by[("1smp", 0.05)] | by[("1smp", 0.15)] and len(by) == 4, str(by))
        for bad_text in ("stride_samples = [0]", "stride_samples = [1.5]", "stride_span = [0.0]", "stride_span = [1.5]", "stride_span = []", 'stride_samples = "1"'):
            (tmp / "g-b.toml").write_text('wc = [0.15]\nlanes = ["ARGMAX_ABS_A_FAST"]\n' + bad_text + "\n")
            out, rc = cc("chain", ident, "--grid", str(tmp / "g-b.toml"))
            check(f"P5. a stride declared as `{bad_text}`: REFUSED GRID_UNREADABLE, exit 1", re.findall(r"^REFUSED ([A-Z_]+):", out, re.M)[:1] == ["GRID_UNREADABLE"] and rc == 1, out[-200:])


try:
    cli_checks()
except Exception as e:   # a crash is a named FAIL, never a silent pass
    check("P1/P4/P5. the CLI checks run to the end", False, repr(e)[:300])
print(f"{len(bad)} failed" if bad else "test_chain_1205_p2b: all passed")
sys.exit(1 if bad else 0)
