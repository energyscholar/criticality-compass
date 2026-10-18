"""intake_synth - `bin/cc intake synth <id> --seed N [--curves K] [--out DIR]` (plan 1139): a planted synthetic bank for the intake, test
infrastructure (checks.toml [roles] test_infrastructure; outside the measurement closure; no intake stage imports it).
Invariant: the generative model is plan 1139's, fixed; one numpy default_rng(seed) per bank is consumed in curve order, then point order
(DRAW_ORDER), so a seed names its bank byte for byte. The truth (h*) is written only to <out>/<id>-TRUTH/truth.json, a sibling outside the
bank; the bank holds the curves and a MANIFEST of metadata (names, h, n, size, sha256, the seed, this file's sha256), never the truth."""
import hashlib
import json
import re
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
    out = Path(_flag(args, "--out", str(Path(root) / "scratch" / "intake-synth")))
    bank, truth = out / ident, out / f"{ident}-TRUTH"
    refuse = lambda why: print(f"bin/cc intake synth: {why}\n  usage: bin/cc intake synth <id> --seed N [--curves K] [--out DIR]\n  Next: bin/cc intake explain") or 1
    exists = lambda: print(f"synth {ident}: refused, {bank} or {truth} exists; a bank is never overwritten\n  Next: rm -r {bank} {truth}   (or choose another id)") or 1
    return {True: lambda: refuse("needs " + "; ".join(usage)),
            False: lambda: {True: exists, False: lambda: _done(bank, truth, ident, write(bank, truth, ident, int(seed), int(k)))}[bank.exists() or truth.exists()]()}[len(usage) > 0]()
