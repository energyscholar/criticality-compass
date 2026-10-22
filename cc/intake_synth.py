"""intake_synth - `bin/cc intake synth <id> --seed N [--curves K] [--out DIR]` (plan 1139): a planted synthetic bank for the intake, test
infrastructure (checks.toml [roles] test_infrastructure; outside the measurement closure; no intake stage imports it).
Invariant: the generative model is plan 1139's, fixed; one numpy default_rng(seed) per bank is consumed in curve order, then point order
(DRAW_ORDER), so a seed names its bank byte for byte. The truth (h*) is written only to <out>/<id>-TRUTH/truth.json, a sibling outside the
bank; the bank holds the curves and a MANIFEST of metadata (names, h, n, size, sha256, the seed, this file's sha256), never the truth."""
import hashlib
import json
import re
import tomllib
from pathlib import Path

import numpy as np

MODEL = "C(T, h) = B + A(h) / (1 + ((T - T_p(h)) / w)^2) + eps; T_p(h) = 2.27 + 0.30 h; A(h) = 1.0 + 1.5 exp(-(h - h*)^2 / (2 * 0.12^2)); eps ~ N(0, sigma)"
B, W, TP0, TP1, A0, A1, S, H_STAR, SIGMA = 0.5, 0.08, 2.27, 0.30, 1.0, 1.5, 0.12, 0.10, 0.03
GRID = np.linspace(1.5, 3.5, 161)   # the master fast-knob grid; each curve keeps its own subset
N_LO, N_HI = 40, 120                 # n_k is uniform over the integers in [N_LO, N_HI]
DRAW_ORDER = ("one numpy default_rng(seed) per bank; for each curve k = 0..K-1 in order: n_k = rng.integers(40, 121); the kept grid indices = "
              "sort(rng.choice(161, n_k, replace=False)); eps = rng.normal(0, 0.03, n_k), in ascending T")
PATTERN = "curve_{index:03d}.csv"


def curve(rng, h):
    """One curve's rows (T, C) in ascending T, drawn in DRAW_ORDER from the bank's one generator."""
    n = int(rng.integers(N_LO, N_HI + 1))
    t = GRID[np.sort(rng.choice(GRID.size, n, replace=False))]
    c = B + (A0 + A1 * np.exp(-(h - H_STAR) ** 2 / (2 * S ** 2))) / (1 + ((t - (TP0 + TP1 * h)) / W) ** 2) + rng.normal(0, SIGMA, n)
    return "T,C,sigma\n" + "".join(f"{a:.4f},{b:.10f},{SIGMA}\n" for a, b in zip(t, c))


def write(bank, truth, ident, seed, k):
    """Write the K curves and MANIFEST.json into `bank` and truth.json into `truth` (both absent before; the caller's table refuses otherwise)."""
    rng, code = np.random.default_rng(seed), hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    bank.mkdir(parents=True)
    hs = [round(float(h), 10) for h in np.linspace(-0.5, 0.5, k)]
    rows = []
    for i, h in enumerate(hs):
        data = curve(rng, h).encode()
        (bank / PATTERN.format(index=i)).write_bytes(data)
        rows.append({"name": PATTERN.format(index=i), "h": h, "n": data.count(b"\n") - 1, "size": len(data), "sha256": hashlib.sha256(data).hexdigest()})
    (bank / "MANIFEST.json").write_text(json.dumps({
        "schema": 1, "kind": "intake-synth-manifest", "id": ident, "seed": seed, "draw_order": DRAW_ORDER, "reader": "csv-curve-v1", "pattern": PATTERN,
        "columns": ["T", "C", "sigma"], "slow": {"name": "h", "unit": "dimensionless"}, "fast": {"name": "T", "unit": "dimensionless", "column": "T"},
        "measured": {"name": "C", "unit": "dimensionless", "column": "C"}, "replicate": "NONE",
        "generator": {"path": "cc/intake_synth.py", "sha256": code}, "files": rows}, indent=1) + "\n")
    truth.mkdir(parents=True)
    (truth / "truth.json").write_text(json.dumps({"schema": 1, "kind": "intake-synth-truth", "id": ident, "h_star": H_STAR, "model": MODEL, "seed": seed,
                                                  "parameters": {"B": B, "w": W, "T_p": [TP0, TP1], "A": [A0, A1], "s": S, "sigma": SIGMA, "grid": [1.5, 3.5, 161], "n": [N_LO, N_HI]},
                                                  "curves": k, "generator": {"path": "cc/intake_synth.py", "sha256": code}}, indent=1) + "\n")
    return rows


# ---- plan 1176 phase C: the planted real-shaped 2-D bank (`--plane FAMILY --density D`). The same Lorentzian MODEL family, on a declared plane
# of curves (slow h) x samples (fast T); every parameter is fixed here BEFORE any run (no value below was chosen by looking at a verdict).
PLANE_GRID = np.linspace(1.5, 3.5, 30)   # the aligned fast grid: 30 samples per curve (dense and sparse)
DT = float(PLANE_GRID[1] - PLANE_GRID[0])   # one sample, in T
WC = 5   # linenav grid w_c, in cells (samples): the decoy's width is stated against it
MASTER = np.linspace(1.5, 3.5, 61)   # the misaligned variant: each curve keeps a seeded subset of this grid, n_k uniform over [24, 36]
DENSITY = {"dense": (30, (0.0,)), "sparse": (9, (0.0, 1.0, 2.0, 3.0))}   # density -> (curves per slice, the slice values of the second knob p)
TP2 = 0.05   # the line (and the arc) moves by 0.05 in T per unit of the second knob p (sparse slices)
SAG, ARC0 = 0.20, 2.50   # decoy arc: T_arc(h, p) = ARC0 + SAG (1 - 4 h^2) + TP2 p (its ends at h = +-0.5 on ARC0; SAG = 2.9 samples, inside w_c, so FOLLOWED is reachable: the gate CAN fire)
A_D, W_D, S_D = 1.0, 3 * WC * DT, 0.5   # decoy: height 1, half-width 3 w_c (15 samples, width >> w_c), sigma half the height (comparable to it)
M_NULL = 0.5   # null: C = B + M_NULL (T - 1.5) + eps, monotone in T (no interior maximum anywhere)
sharp_c = lambda h, p: TP0 + TP1 * h + TP2 * p   # noqa: E731  the planted line: the existing MODEL's T_p(h), shifted per slice
arc_c = lambda h, p: ARC0 + SAG * (1 - 4 * h ** 2) + TP2 * p   # noqa: E731
lor = lambda t, a, c, w: a / (1 + ((t - c) / w) ** 2)   # noqa: E731
PLANE = {   # family -> (the curve's C without noise at (t, h, p), sigma, the declarer's guessed line (h, p) -> T, its kind, grid kind); total over FAMILIES
    "sharp": (lambda t, h, p: B + lor(t, A0 + A1 * np.exp(-(h - H_STAR) ** 2 / (2 * S ** 2)), sharp_c(h, p), W), SIGMA, sharp_c, "LINE", "ALIGNED"),
    "decoy": (lambda t, h, p: B + lor(t, A_D, arc_c(h, p), W_D), S_D, arc_c, "CROSSOVER_ARC", "ALIGNED"),
    "null": (lambda t, h, p: B + M_NULL * (t - 1.5), SIGMA, sharp_c, "NONE", "ALIGNED"),   # no line: the guess is the sharp family's line
    "misaligned": (lambda t, h, p: B + lor(t, A0 + A1 * np.exp(-(h - H_STAR) ** 2 / (2 * S ** 2)), sharp_c(h, p), W), SIGMA, sharp_c, "LINE", "SUBSET"),
}
FAMILIES = tuple(PLANE)
GRIDS = {"ALIGNED": lambda rng: PLANE_GRID, "SUBSET": lambda rng: MASTER[np.sort(rng.choice(MASTER.size, int(rng.integers(24, 37)), replace=False))]}
PLANE_DRAW = ("one numpy default_rng(seed) per bank; for each slice p in order, each curve h in order: (SUBSET grid only) n_k = rng.integers(24, 37), "
              "the kept MASTER indices = sort(rng.choice(61, n_k, replace=False)); then eps = rng.normal(0, sigma, n_k), in ascending T")
LAYOUT = {"dense": "PER_FILE", "sparse": "LONG_TABLE"}   # a second knob is a [replicate.key] COLUMN, so the sparse lattice is one long table


def plane_curves(rng, family, density):
    """[(p, h, T values, C values, sigma)] in DRAW_ORDER: slices in order, curves in slow order."""
    k, ps = DENSITY[density]
    f, sig, _, _, grid = PLANE[family]
    hs = [round(float(h), 10) for h in np.linspace(-0.5, 0.5, k)]
    out = []
    for p in ps:
        for h in hs:
            t = GRIDS[grid](rng)
            out.append((p, h, t, f(t, h, p) + rng.normal(0, sig, t.size), sig))
    return out


def plane_write(bank, truth, ident, seed, family, density):
    """Write a plane bank (dense: one csv-curve-v1 file per curve; sparse: bank.csv, table-curve-v1 with columns T,C,sigma,p,h) and MANIFEST.json
    into `bank`, and truth.json into `truth` (outside the bank): the family, its parameters and the declarer's guessed line per curve."""
    rng, code = np.random.default_rng(seed), hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    cs, (_, sig, guess, kind, grid) = plane_curves(rng, family, density), PLANE[family]
    bank.mkdir(parents=True)
    row = lambda t, c, s, extra="": "".join(f"{a:.4f},{b:.10f},{s}{extra}\n" for a, b in zip(t, c))   # noqa: E731
    files = {"PER_FILE": lambda: [(PATTERN.format(index=i), "T,C,sigma\n" + row(t, c, s), h) for i, (p, h, t, c, s) in enumerate(cs)],
             "LONG_TABLE": lambda: [("bank.csv", "# plan 1176 phase C: the sparse plane as one long table\nT,C,sigma,p,h\n"
                                     + "".join(row(t, c, s, f",{p},{h}") for p, h, t, c, s in cs), None)]}[LAYOUT[density]]()
    rows = []
    for name, text, h in files:
        (bank / name).write_bytes(text.encode())
        rows.append({"name": name, "h": h, "n": text.count("\n") - 1, "size": len(text), "sha256": hashlib.sha256(text.encode()).hexdigest()})
    (bank / "MANIFEST.json").write_text(json.dumps({
        "schema": 1, "kind": "intake-synth-manifest", "id": ident, "seed": seed, "draw_order": PLANE_DRAW, "reader": "csv-curve-v1", "pattern": PATTERN,
        "layout": LAYOUT[density], "columns": ["T", "C", "sigma"], "slow": {"name": "h", "unit": "dimensionless"},
        "fast": {"name": "T", "unit": "dimensionless", "column": "T"}, "measured": {"name": "C", "unit": "dimensionless", "column": "C"}, "replicate": "NONE",
        "slices": {"column": "p", "values": list(DENSITY[density][1])}, "curves": [{"p": p, "h": h, "n": int(t.size)} for p, h, t, _, _ in cs],
        "generator": {"path": "cc/intake_synth.py", "sha256": code}, "files": rows}, indent=1) + "\n")
    truth.mkdir(parents=True)
    (truth / "truth.json").write_text(json.dumps({
        "schema": 1, "kind": "intake-synth-plane-truth", "id": ident, "seed": seed, "family": family, "density": density, "line_kind": kind, "grid": grid,
        "sigma": sig, "parameters": {"B": B, "w": W, "T_p": [TP0, TP1, TP2], "A": [A0, A1], "s": S, "h_star": H_STAR, "decoy": {"A": A_D, "w": W_D, "sigma": S_D, "arc": [ARC0, SAG]},
                                     "null_slope": M_NULL, "fast_grid": [1.5, 3.5, 30], "master": [1.5, 3.5, 61]},
        "guess": [{"p": p, "h": h, "T": float(guess(h, p))} for p, h, _, _, _ in cs],   # the declarer's guessed line on each curve (the suspect's ends, the checkpoints)
        "generator": {"path": "cc/intake_synth.py", "sha256": code}}, indent=1) + "\n")
    return rows


def _flag(args, name, absent):
    return {True: lambda: args[args.index(name) + 1], False: lambda: absent}[name in args and args.index(name) + 1 < len(args)]()


def _done(bank, truth, ident, rows):
    print(f"synth {ident}: wrote {len(rows)} curves ({min(r['n'] for r in rows)} to {max(r['n'] for r in rows)} points each) and MANIFEST.json to {bank}\n"
          f"  the truth is in {truth / 'truth.json'}, outside the bank; no intake stage reads it\n  Next: bin/cc new intake {ident} --from-synth {ident}")
    return 0


def cli(root, args):
    """bin/cc intake synth: a usage refusal (no id, a seed or curve count that is not an integer, fewer than 2 curves) or a bank that exists
    already (refused: a bank is never overwritten), else write. Every branch is a row of a two-row table."""
    ident, seed, k = {True: lambda: args[0], False: lambda: ""}[len(args) > 0 and not args[0].startswith("--")](), _flag(args, "--seed", ""), _flag(args, "--curves", "9")
    usage = [u for ok, u in ((re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]*", ident) is not None, "an id (letters, digits, _ . -)"),
                             (re.fullmatch(r"\d+", seed) is not None, "--seed N (a non-negative integer)"),
                             (re.fullmatch(r"\d+", k) is not None and int(k) >= 2, "--curves K (an integer, at least 2)")) if not ok]
    fam, dens = _flag(args, "--plane", ""), _flag(args, "--density", "dense")   # plan 1176 C: a plane bank (no --plane: the plan 1139 bank)
    usage += [u for ok, u in ((fam in ("",) + FAMILIES, f"--plane one of {' '.join(FAMILIES)}"), (dens in DENSITY, f"--density one of {' '.join(DENSITY)}")) if not ok]
    out = Path(_flag(args, "--out", str(Path(root) / "scratch" / "intake-synth")))
    bank, truth = out / ident, out / f"{ident}-TRUTH"
    refuse = lambda why: print(f"bin/cc intake synth: {why}\n  usage: bin/cc intake synth <id> --seed N [--curves K] [--plane FAMILY [--density dense|sparse]] [--out DIR]\n  Next: bin/cc intake explain") or 1
    exists = lambda: print(f"synth {ident}: refused, {bank} or {truth} exists; a bank is never overwritten\n  Next: rm -r {bank} {truth}   (or choose another id)") or 1
    made = {False: lambda: write(bank, truth, ident, int(seed), int(k)), True: lambda: plane_write(bank, truth, ident, int(seed), fam, dens)}
    return {True: lambda: refuse("needs " + "; ".join(usage)),
            False: lambda: {True: exists, False: lambda: _done(bank, truth, ident, made[fam != ""]())}[bank.exists() or truth.exists()]()}[len(usage) > 0]()


def declare(m, ident, sid):
    """`bin/cc new intake <id> --from-synth <sid>`: (the intake.toml values the MANIFEST states as metadata, the template lines of the VARIANT
    rows the MANIFEST rules out (reader csv-curve-v1 has no field of table-curve-v1), the CC transducer.toml text).
    Invariant: it fills metadata only and never a choice (intake.mode, acquisition, interval, bracket, projection, bridge, their bias and
    the shift stay TODO), and it writes no truth: neither h* nor the model's parameters appear in what it returns."""
    q, cmd = (lambda v: json.dumps(v)), f"bin/cc intake synth {sid} --seed {m['seed']}"
    values = {
        "basis.read": f'[ {{ what = {q(f"<intake-synth>/{sid}/MANIFEST.json: file names, h, n, size and sha256 per file; the seed; the generator sha256")}, class = "LISTING" }} ]',
        "source.kind": q("DEPOSIT"), "source.origin": q("PLANTED"), "source.deposit": q(cmd + " (cc/intake_synth.py)"), "source.root": q(f"<intake-synth>/{sid}"),
        "source.universe": q("*"), "source.truth_side": q(["truth.json"]), "reader.name": q(m["reader"]),
        "selection.layout": q("PER_FILE"), "selection.files": q([f["name"] for f in m["files"]]),
        "selection.excluded": '[ { file = "MANIFEST.json", why = "metadata (in basis), not a curve" } ]',
        "selection.slow.source": q("LISTED"), "selection.slow.values": q([repr(float(f["h"])) for f in m["files"]]),
        "knobs.slow.name": q(m["slow"]["name"]), "knobs.slow.unit": q(m["slow"]["unit"]),
        "knobs.fast.name": q(m["fast"]["name"]), "knobs.fast.unit": q(m["fast"]["unit"]), "knobs.fast.source": q("COLUMN"), "knobs.fast.key": q(m["fast"]["column"]),
        "measured.name": q(m["measured"]["name"]), "measured.unit": q(m["measured"]["unit"]), "measured.key": q(m["measured"]["column"]), "measured.shape": q("SCALAR_PER_LOCUS"),
        "measured.uncertainty.kind": q("COLUMN"), "measured.uncertainty.key": q(m["columns"][2]),
        "replicate.identity": q(m["replicate"]), "replicate.key.kind": q("NONE"),   # (1160 A33: was replicate.key "")
    }
    cfg = tomllib.loads((Path(__file__).resolve().parent.parent / "cc.toml").read_text())["transducer"]
    trans = (f"# declarations/{ident}/transducer.toml - written by bin/cc new intake {ident} --from-synth {sid}: the CC transducer file of a synthetic bank.\n"
             f"# The update pin is the generator cc/intake_synth.py of the Compass itself (route compass:, cc.toml [transducer] update_routes).\n"
             f'schema = 1\nkind = "transducer"\nid = {q(ident)}\n\n[transducer]\n'
             f'model = "the planted synthetic bank of bin/cc intake synth: one peak in T per curve, on a seeded subset of a 161-point T grid, with Gaussian noise; the planted values are in the generator, not here"\n'
             f'update = [{q("compass:" + m["generator"]["path"] + " sha256 " + m["generator"]["sha256"])}]\n'
             f'inputs = {q(cmd)}\noutput = {q(cfg["phase1_output"])}\n\n'
             f'[reduction]\nname = "none in the Compass: the bank stores one value of C per (h, T) point"\nkeeps = "the planted value of C at each kept point, with its noise"\n'
             f'discards = "nothing the bank holds"\n\n[interval]\nrole = {q(cfg["interval_role"])}\nkeeps = "the planted noise sigma written on every row"\ndiscards = "the noise draw itself"\n')
    dropped = frozenset({"reader.comment", "reader.format", "reader.header", "source.converted_from", "source.blinded_from", "source.key_sha256", "replicate.key.separator", "replicate.key.field", "replicate.key.column"})   # csv-curve-v1 has no other field; a DEPOSIT has no converted_from
    return values, dropped, trans
