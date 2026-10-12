"""test_0978 - plan 0978: the family layer under method `chains` (and every method). The gate `detect.family_refusal` is gone; f1's readout is a TOTAL table keyed by the result's
interval method (cc/family.py F1_READOUT). T1 totality; T2 byte identity of every stored block family against tests/reference/0978-family-block.txt (recorded at release-1-0 f4f2e48,
before the change); T3 chains: f1 reads rows 1..m, [d_(r), d_(m+1-r)], on hand-set rows; T4 gamma: a declared null, no exception; T5 end_notes (the third entrance) does not raise
on a chains result. Each test carries its planted mutation, which must turn it red (a green that cannot go red is not evidence)."""
import contextlib
import json
import sys
import tomllib
from pathlib import Path
import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path[:0] = [str(ROOT / "cc"), str(ROOT / "cc" / "instruments")]
import family  # noqa: E402
import readout  # noqa: E402

bad = []


def check(name, ok, why=""):
    print(("ok   " if ok else "FAIL ") + name + ("" if ok else f": {why}"))
    if not ok:
        bad.append(name)


@contextlib.contextmanager
def planted(key, fn):
    """Swap one F1_READOUT row (fn None: drop it); restore on exit."""
    keep = dict(family.F1_READOUT)
    try:
        family.F1_READOUT.pop(key, None) if fn is None else family.F1_READOUT.__setitem__(key, fn)
        yield
    finally:
        family.F1_READOUT.clear()
        family.F1_READOUT.update(keep)


def raises(call):
    try:
        call()
        return None
    except Exception as e:   # noqa: BLE001 - the test classifies whatever the planted defect raises
        return type(e).__name__


CFG = tomllib.loads((ROOT / "cc.toml").read_text())
METHODS = set(CFG["alphabets"]["interval_method"])
NULLS = CFG["alphabets"]["nulls"]

# ---- T1 totality
check("T1 F1_READOUT keys == cc.toml alphabets.interval_method", set(family.F1_READOUT) == METHODS, (set(family.F1_READOUT), METHODS))
with planted("chains", None):
    check("T1 seen red: dropping 'chains' breaks totality", set(family.F1_READOUT) != METHODS)

# ---- T2 identity on every stored block family
DUMP = ROOT / "tests" / "reference" / "0978-family-block.txt"


def dump():
    out = []
    for f in sorted((ROOT / "families").glob("*.toml")):
        for ts in sorted(p.parent.name for p in (ROOT / "tables").glob("*/family.toml")):
            msg, got = family.run(ROOT, f.stem, ts)
            out.append(f"## {f.stem} @ {ts}")
            out += str(msg).splitlines() if got is None else family.show(*got)
    return "\n".join(out) + "\n"


want = DUMP.read_text()
check("T2 every family under every set with a family.toml is byte-identical to release-1-0 f4f2e48", dump() == want)
perturbed = lambda d, iv, eps: ("PLANTED " + family._f1_resampled(d, iv, eps)[0], family._f1_resampled(d, iv, eps)[1])   # noqa: E731
with planted("block", perturbed):
    check("T2 seen red: perturbing the block readout moves the transcripts", dump() != want)

# ---- T3 chains on hand-set rows (m 10, r 2)
FAM = tomllib.loads((ROOT / "tables" / "v10-rules" / "family.toml").read_text())
EPS = {"y": 0.25}
INST = {"instruments": ["across_delta"], "eps": EPS}
A = [0.0, 0.0, 0.1, 0.2, 0.1, 0.3, 0.2, 0.1, 0.2, 0.3, 0.1]   # unit p0->p1: row 0 = copy of chain 0, rows 1..10
B = [-0.3, -0.3, 0.0, 0.1, 0.4, 0.2, 0.6, 0.3, 0.2, 0.5, 0.9]   # unit p1->p2; chain 0 gives the MINIMUM difference (-0.3), so a copy of row 0 moves d_(2)
D = np.array(B) - np.array(A)
IV = {"method": "chains", "m": 10, "r": 2, "alpha": 0.021484375, "chain_root": "x"}


def synthetic(interval):
    rd = [{"instrument": "across_delta", "column": "y_last", "unit": {"pair": p}, "vector_key": k, "cell": "SLOW+"}
          for p, k in ((["p0", "p1"], "a"), (["p1", "p2"], "b"))]
    return {"pair_readings": rd, "readings": [], "interval": interval}, {"a": np.array(A), "b": np.array(B)}


def f1_text(interval):
    res, z = synthetic(interval)
    return family.f1_of(FAM, {"interior": ["p0", "p1", "p2"]}, res, z, INST, NULLS)[1][0][2]


g = np.sort(D[1:])
want_text = f"{np.median(g):+.3f} [{g[1]:+.3f}, {g[8]:+.3f}] "
check("T3 chains: f1 reads [d_(2), d_(9)] of rows 1..10 and their median", f1_text(IV).startswith(want_text), (f1_text(IV), want_text))
every = lambda d, iv, eps: (lambda e, lo, hi, c: (f"{e:+.3f} [{lo:+.3f}, {hi:+.3f}] {c}", c))(*readout.chains(np.concatenate([d[:1], d]), iv["r"], eps))   # noqa: E731
with planted("chains", every):   # the plant puts row 0 (a copy of chain 0) in as a replicate
    check("T3 seen red: including row 0 moves the interval", not f1_text(IV).startswith(want_text), f1_text(IV))

# ---- T4 / T5 on a real stored result whose interval method is replaced (block-shaped vectors; the readout must not need resamples/level)
RES = json.loads((ROOT / "results" / "k4-m1@v08-rules.json").read_text())
Z = np.load(ROOT / RES["vectors"])
DECL = family.load_decl(ROOT, "k4-m1")
FAMV8 = tomllib.loads((ROOT / "tables" / "v08-rules" / "family.toml").read_text())
import detect  # noqa: E402
M = detect.load_input("k4-m1")
GAMMA = {"method": "gamma", "level": 0.95, "window_s": 1.0, "window_max": 1, "door_z": 1.0, "tau_declared": 1, "tau_source": "x"}


def f1_under(interval):
    inner, _ = family.interior_of(DECL, RES, FAMV8, M)
    return family.f1_of(FAMV8, {**DECL, "interior": inner}, {**RES, "interval": interval}, Z, M, NULLS)


code, cells = f1_under(GAMMA)
check("T4 gamma: f1 reads NOT-EVALUATED with the declared reason, no exception", code == "NOT-EVALUATED" and all("not replicates" in t for _, _, t, _ in cells), (code, cells[:1]))
with planted("gamma", None):
    check("T4 seen red: removing the gamma row raises KeyError", raises(lambda: f1_under(GAMMA)) == "KeyError")
code, cells = f1_under({**IV, "m": 400})
check("T4 chains on block-shaped vectors reads without resamples/level (no KeyError)", code in FAMV8["alphabets"]["f1"] and len(cells) == 28, code)


def notes(interval):
    return family.end_notes(ROOT, {**RES, "interval": interval})


check("T5 end_notes (the third entrance) over a chains result with a family declared does not raise", isinstance(notes(IV), dict))
check("T5 end_notes over a gamma result does not raise", isinstance(notes(GAMMA), dict))
with planted("chains", None):
    check("T5 seen red: with the chains row gone end_notes raises", raises(lambda: notes(IV)) == "KeyError")
src = " ".join((ROOT / p).read_text() for p in ("cc/detect.py", "cc/score.py", "bin/cc", "cc/family.py"))
check("T5 the gate is gone from every entrance", "family_refusal" not in src)
print("test_0978: " + ("FAILED" if bad else "all passed"))
sys.exit(1 if bad else 0)
