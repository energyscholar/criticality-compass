"""test_wrong_l - plan 1282 P1b: the door refuses a file of the format npz-sized-v1 whose stored L is absent, malformed, or not its declared size, BY NAME
(the finding's field: .L.header / .L.absent / .L.shape / .L.object / .L.dtype / .L.value). W1 L=81 under size 243; W2 the same at 81 passes; W3 the level-count finding
still fires beside it; W4 no L; W5 the legacy format npz-v1 is untouched (the A4.9 declared limitation, pinned); W6 CARRIES_L is total over cc.toml [alphabets] formats;
W7 L of shape (1,); W8 a bare .npy; W9 a float L; W10 sampler.sized on a missing, non-str or unknown format returns [] and never calls heads; W11 an object L, no exception.
Reads the author's toolset (cc.toml [check] needs_data); every case plants one input in a fresh copy of the repo and one file under <data root>/1282-p1/.
Seen RED on 961c476 (P1a's commit; no .L finding at all, sampler.CARRIES_L and sampler.sized absent); W2, W5, W10, W11 also seen RED on a named mutant (evidence in the plan's P1b report)."""
import contextlib
import io
import os
import re
import shutil
import sys
import tempfile
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
from lib import bad, bootstrap, check, guarded  # noqa: E402
bootstrap(ROOT, "cc", "cc/instruments")
import numpy as np  # noqa: E402
import author  # noqa: E402
import declare  # noqa: E402
import sampler  # noqa: E402

DATA = Path(os.environ["CC_DATA_ROOT"])
PID = f"wl-{os.getpid()}"
FIELD = "data.files[0].L"


def chain():
    tools = sampler.load(sampler.toolset_of(DATA))
    return sampler.sample(tools, 1.00 * sampler.KC, 0.0, 81, "ordered", sampler.seed_of("1282-p1-test", "poc", "1.00", 81, "ordered", 0), sampler.Run(20, 1, 10))[0]


def writer_npz(c):
    return lambda path: sampler.write(c, path), "f.npz"


def writer_sans_l(c):
    return lambda path: np.savez(path, O=c.O, G=c.G, K=c.couplings["K"]), "f.npz"


def writer_with_l(L):
    return lambda c: (lambda path: np.savez(path, O=c.O, G=c.G, K=c.couplings["K"], L=L), "f.npz")


def writer_npy(c):
    return lambda path: np.save(path, c.O), "f.npy"


def plant(td, writer, fmt, size, extra=""):
    """Write one chain file under the data root and one input wl-<pid> (a copy of x4's four files, one [[data.files]] block) into a fresh copy of the repo: its path."""
    c = chain()
    save, name = writer(c)
    folder = DATA / "1282-p1" / PID
    folder.mkdir(parents=True, exist_ok=True)
    save(folder / name)
    repo = Path(td) / "repo"
    shutil.copytree(ROOT, repo, ignore=shutil.ignore_patterns(".git", "__pycache__", "rust", "results"))
    src, dst = repo / "inputs" / "x4-ising-field-ch", repo / "inputs" / PID
    dst.mkdir()
    for f in ("points.toml", "couplings.toml", "transducer.toml"):
        (dst / f).write_text((src / f).read_text().replace("x4-ising-field-ch", PID))
    (dst / "couplings.toml").write_text(re.sub(r"^names = .*$", 'names = ["K"]', (dst / "couplings.toml").read_text(), flags=re.M))
    head = (src / "m.toml").read_text().split("\n[data]\n")[0].replace("x4-ising-field-ch", PID)
    block = (f'\n[data]\nformat = "{fmt}"\n\n[[data.files]]\npoint = "0.46"\nstart = "ordered"\nchain = 0\nsize = {size}\n'
             f'path = "1282-p1/{PID}/{name}"\narrays.Q = {{ key = "O", level = 0 }}\n{extra}')
    (dst / "m.toml").write_text(head + block)
    with contextlib.redirect_stdout(io.StringIO()):
        author.data_add(repo, PID)
    return repo


def findings(writer, fmt, size, extra=""):
    """The loc of every finding of the planted input whose field starts data.files[0].L, and all findings of the input."""
    try:
        with tempfile.TemporaryDirectory() as td:
            repo = plant(td, writer, fmt, size, extra)
            allf = [f for f in declare.validate(repo, PID, "v10-rules")[0] if isinstance(f, declare.F)]
    finally:
        shutil.rmtree(DATA / "1282-p1" / PID, ignore_errors=True)
        with contextlib.suppress(OSError):
            (DATA / "1282-p1").rmdir()
    return sorted(f.loc.split(":", 1)[1] for f in allf if f.loc.split(":", 1)[1].startswith(FIELD)), allf


def only(name, writer, fmt, size, arm):
    got, _ = findings(writer, fmt, size)
    want = [f"{FIELD}.{arm}"] if arm else []
    check(name, got == want, f"findings at {FIELD}*: {got}, wanted {want}")


def w1():
    only("W1 L=81 declared at size 243: exactly .L.value", writer_npz, "npz-sized-v1", 243, "value")


def w2():
    only("W2 L=81 declared at size 81: no .L finding", writer_npz, "npz-sized-v1", 81, None)


def w3():
    got, allf = findings(writer_npz, "npz-sized-v1", 243, 'arrays.G = { key = "G", level = 1 }\n')
    lv = [f for f in allf if f.loc.endswith("data.files[0].arrays.G") and "G stores 3 levels but observable.levels declares" in f.msg]
    check("W3 .L.value and the existing level-count finding at arrays.G both fire", got == [f"{FIELD}.value"] and len(lv) == 1, f"{got}; {[f.msg for f in lv]}")


def w4():
    only("W4 no L: .L.absent", writer_sans_l, "npz-sized-v1", 81, "absent")


def w5():
    only("W5 the W1 file under npz-v1 (the A4.9 declared limitation): no .L finding", writer_npz, "npz-v1", 243, None)


def w6():
    have, want = set(sampler.CARRIES_L), set(tomllib.loads((ROOT / "cc.toml").read_text())["alphabets"]["formats"])
    check("W6 sampler.CARRIES_L is total over cc.toml [alphabets] formats", have == want, f"only in CARRIES_L {sorted(have - want)}; only in cc.toml {sorted(want - have)}")


def w7():
    only("W7 L of shape (1,): .L.shape", writer_with_l(np.array([81])), "npz-sized-v1", 81, "shape")


def w8():
    only("W8 a bare .npy: .L.header", writer_npy, "npz-sized-v1", 81, "header")


def w9():
    only("W9 L a float64: .L.dtype", writer_with_l(np.float64(81.0)), "npz-sized-v1", 81, "dtype")


def w10():
    def never():
        raise AssertionError("heads() called for a format that does not carry L")
    for fmt in (None, ["npz-sized-v1"], "nope"):
        got = sampler.sized("p", "data.files[0]", {"size": 81}, never, None, fmt)
        check(f"W10 sampler.sized on format {fmt!r}: [] and heads never called", got == [], str(got))


def w11():
    only("W11 L an object array: .L.object, no exception", writer_with_l(np.array(81, dtype=object)), "npz-sized-v1", 81, "object")


for name, fn in (("W1", w1), ("W2", w2), ("W3", w3), ("W4", w4), ("W5", w5), ("W6", w6), ("W7", w7), ("W8", w8), ("W9", w9), ("W10", w10), ("W11", w11)):
    guarded(name, fn)
print("".join(f"FAILED {b}\n" for b in bad) + "test_wrong_l: " + ("FAILED" if bad else "all passed"))
sys.exit(1 if bad else 0)
