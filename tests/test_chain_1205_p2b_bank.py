"""test_chain_1205_p2b_bank - plan 1205 P2b on the planted LL1-shape bank (the compute host: ~/scratch/cc-1205-breakers/bank, or $CC_P2B_BANK; expectations in
research/1205/breakers/bank-manifest.json, or $CC_P2B_MANIFEST). The C-shape STEP file at SNR 20 (40000 fast samples, 50 curves, a tanh step of width
0.004 of the span on the S_CURVE path): at stride 1 the location scatters (Located within w_c 0.05 of the planted centre on < 50% of curves); at the
stride 0.004 of the span it is Located within w_c 0.05 on >= 90%. An absent bank is a FAIL (never a silent pass): run this on the compute host.
Red: _edges forces k = 1 (the stride-0.004 check fails); the place made w[:-k, 0] is NOT caught here (the offset is 80 samples = 0.002 of the span, far inside w_c; the
in-process noiseless midpoint check of tests/test_chain_1205_p2b.py P2 catches it)."""
import json
import os
import sys
from dataclasses import dataclass
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path[:0] = [str(ROOT / "cc")]
import chain  # noqa: E402
import intake_feature as F  # noqa: E402

BANK = Path(os.environ.get("CC_P2B_BANK", Path.home() / "scratch" / "cc-1205-breakers" / "bank"))
FILE = "bank-C-STEP-snr20.hd5"
MANIFESTS = [Path(p) for p in (os.environ.get("CC_P2B_MANIFEST", ""),
                               BANK.parent / "bank-manifest.json", BANK / "bank-manifest.json") if str(p)]
bad = []


def check(name, ok, why=""):
    print(("ok   " if ok else "FAIL ") + name + ("" if ok else f": {why}"))
    if not ok:
        bad.append(name)


@dataclass(frozen=True)
class Curve:
    slow: tuple
    rows: list


def main():
    import h5py
    man = json.loads(next(p for p in MANIFESTS if p.is_file()).read_text())["files"][FILE]
    nf, nl = man["fast_samples"], man["lines"]
    planted = man["observables"]["gpib5"]["planted_path_span_units"]
    with h5py.File(BANK / FILE, "r") as f:
        names = [x.decode() for x in f["data"].attrs["column_names"]]
        d = f["data"][:, :]
    col, fc = names.index("Lockin (GPIB 5), X Quadrature [V]"), names.index("DAC 3 [V]")
    cs = [Curve((float(k),), [(float(a), float(v), 0.0) for a, v in zip(d[k * nf:(k + 1) * nf, fc], d[k * nf:(k + 1) * nf, col])]) for k in range(nl)]
    fam = chain.Family("bank", tuple(cs), tuple(float(k) for k in range(nl)), F.span(cs, None), F.FAST_ENDS[True](cs, None), 2.0, "NONE", "")
    s1, s4 = chain.Stride(samples=1), chain.Stride(span=0.004)
    ev = chain.evaluate(fam, chain.Grid((0.05,), (chain.Lane.ARGMAX_ABS_A_FAST,), "bank", (s1, s4)))[chain.Lane.ARGMAX_ABS_A_FAST]
    frac = lambda s: float(np.mean([p.kind == "Located" and abs(p.pos - c) <= 0.05 for p, c in zip(ev[(s, 0.05)][0], planted)]))   # noqa: E731
    f1, f4 = frac(s1), frac(s4)
    check("B1. C-STEP snr20, stride 1: the location scatters (Located within w_c 0.05 of the planted centre on < 50% of 50 curves)", f1 < 0.5, f"{f1}")
    check("B2. C-STEP snr20, stride 0.004 of the span (160 samples): Located within w_c 0.05 of the planted centre on >= 90% of 50 curves", f4 >= 0.9, f"{f4}")
    print(f"     measured: stride 1 {f1:.2f}, stride 0.004 {f4:.2f}")


try:
    main()
except Exception as e:   # an absent bank or manifest is a named FAIL
    check("B. the bank test runs to the end (bank and manifest present)", False, repr(e)[:300])
print(f"{len(bad)} failed" if bad else "test_chain_1205_p2b_bank: all passed")
sys.exit(1 if bad else 0)
