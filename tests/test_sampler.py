"""test_sampler - plan 1282 P1a: cc/sampler.py, the declared sampler adapter ((K, h, L, start, seed) -> the npz CC reads), and the alphabet entry "npz-sized-v1".
S1 a written chain re-reads (keys O G L K), the transducer model sentences pass declare; S2 same args same bytes; S3 sixty chains declared in an input validate with no finding at
couplings/transducer/data; S4 the tool pins (a changed byte is a Mismatch value); S5 a missing table key raises KeyError; S6 the same input without the alphabet entry is
refused at data.format; S7 the declared seeds; S8 h comes only from FAMILY_H. Reads the author's data root (cc.toml [check] needs_data).
Seen RED on 1f4ab4b (cc/sampler.py absent, "npz-sized-v1" not in cc.toml [alphabets] formats); S6 and S8 also seen RED by mutation (evidence in the plan's P1a report)."""
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path[:0] = [str(ROOT / "cc"), str(ROOT / "cc" / "instruments")]
import numpy as np  # noqa: E402
import declare  # noqa: E402
import schema  # noqa: E402

bad = []
REAL = schema.resolve_data_root(tomllib.loads((ROOT / "cc.toml").read_text()))[0]


def check(name, ok, why=""):
    print(("ok   " if ok else "FAIL ") + name + ("" if ok else f": {why}"))
    if not ok:
        bad.append(name)


def guarded(name, fn):
    """Run one test; an exception (an ImportError on a tree without cc/sampler.py) is that test's FAIL, never a crash of the file."""
    try:
        fn()
    except Exception as e:  # noqa: BLE001
        check(name, False, f"{type(e).__name__}: {e}")


def tools():
    import sampler
    t = sampler.load(sampler.toolset_of(REAL))
    assert not isinstance(t, sampler.Mismatch), f"the toolset does not match the pins: {t}"
    return t


def raises(fn, exc):
    try:
        fn()
    except exc as e:
        return e
    return None


def arrays_of(ch):
    return b"".join(a.tobytes() for a in (ch.O, ch.G, ch.M1))


def s1():
    import sampler
    t, tmp = tools(), Path(tempfile.mkdtemp(prefix="s1-"))
    try:
        for F in sampler.FAMILY_H:
            ch, call = sampler.sample(t, sampler.LABELS["1.00"], sampler.FAMILY_H[F], 27, "random", sampler.seed_of("1282-v10", F, "1.00", 27, "random", 0), sampler.Run(20, 1, 10))
            sampler.write(ch, tmp / f"{F}.npz")
            z = np.load(tmp / f"{F}.npz")
            check(f"S1 {F}: the file holds exactly O G L K, L == 27, G has 2 levels", set(z.files) == {"O", "G", "L", "K"} and int(z["L"]) == 27 and z["G"].shape[1] == 2, str(z.files))
            check(f"S1 {F}: O is (20, 2), K is the label's coupling", z["O"].shape == (20, 2) and float(z["K"]) == sampler.LABELS["1.00"], str(z["O"].shape))
            want = f"2D Ising in a uniform field h = {'0' if F == 'poc' else '0.02'} (held fixed), compiled heat bath (tools/lattice_field_rs.py), K/K_c 0.90-1.10"
            check(f"S1 {F}: transducer_model is its sentence", sampler.transducer_model(F) == want, sampler.transducer_model(F))
            d = tmp / "inputs" / "x4-ising-field-ch"
            d.mkdir(parents=True, exist_ok=True)
            src = (ROOT / "inputs" / "x4-ising-field-ch" / "transducer.toml").read_text()
            (d / "transducer.toml").write_text(re.sub(r'^model = .*$', "model = " + json.dumps(sampler.transducer_model(F)), src, flags=re.M))
            found = declare.check_file(d / "transducer.toml", ROOT, ctx=schema.Ctx(ROOT, data_root=REAL))
            check(f"S1 {F}: the model sentence passes declare.check_file", not [f for f in found if "transducer.model" in f.loc], str([f.loc for f in found]))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def s2():
    import sampler
    t, run = tools(), sampler.Run(20, 1, 10)
    a, b = (sampler.sample(t, 0.44, 0.0, 27, "random", 3_100_000_000, run)[0] for _ in range(2))
    c = sampler.sample(t, 0.44, 0.0, 27, "random", 3_100_000_001, run)[0]
    check("S2 same arguments, same bytes", arrays_of(a) == arrays_of(b))
    check("S2 another seed, other bytes", arrays_of(a) != arrays_of(c))
    check("S2 seed_of is an int", type(sampler.seed_of("1282-v10", "poc", "1.00", 27, "random", 0)) is int)


def inline(d):
    return "{ " + ", ".join(f"{k} = {json.dumps(v)}" for k, v in d.items()) + " }"


def block(e):
    return "[[data.files]]\n" + "".join(f"{k} = {json.dumps(e[k])}\n" for k in ("point", "size", "start", "path", "chain")) + "".join(f"arrays.{n} = {inline(a)}\n" for n, a in e["arrays"].items())


def s3_s6():
    import sampler
    t, pid = tools(), os.getpid()
    iid, tmp = f"s3-{pid}", Path(tempfile.mkdtemp(prefix="s3-"))
    store = REAL / "1282-p1" / iid
    try:
        store.mkdir(parents=True)
        entries = []
        for L in sampler.SIZES:
            for s in sampler.STARTS:
                for j in sampler.CHAINS:
                    ch, _ = sampler.sample(t, sampler.LABELS["1.00"], sampler.FAMILY_H["poc"], L, s, sampler.seed_of("1282-v10", "poc", "1.00", L, s, j), sampler.Run(20, 1, 10))
                    sampler.write(ch, store / sampler.fname(L, s, j))
                    entries.append(sampler.entry(f"1282-p1/{iid}/{sampler.fname(L, s, j)}", "1.00", L, s, j))
        check("S3 sixty chain files, covering every (L, start) row of the arrays table", len(entries) == 60 and len({(e["size"], e["start"]) for e in entries}) == 6, str(len(entries)))
        repo = tmp / "repo"
        shutil.copytree(ROOT, repo, ignore=shutil.ignore_patterns(".git", "__pycache__", "rust"))
        x4, new = ROOT / "inputs" / "x4-ising-field-ch", repo / "inputs" / iid
        new.mkdir()
        sub = lambda s: s.replace("x4-ising-field-ch", iid)  # noqa: E731
        (new / "couplings.toml").write_text(sub((x4 / "couplings.toml").read_text()).replace('names = ["K", "h"]', 'names = ["K"]'))
        (new / "points.toml").write_text(sub((x4 / "points.toml").read_text()).replace('"0.46" = "ising-field-decoy"\n', '"1.00" = "ising-field-decoy"\n').replace('"0.5" = "ising-field-decoy"\n', "").replace('"0.55" = "ising-field-decoy"\n', ""))
        (new / "transducer.toml").write_text(re.sub(r'^model = .*$', "model = " + json.dumps(sampler.transducer_model("poc")), sub((x4 / "transducer.toml").read_text()), flags=re.M))
        head = sub((x4 / "m.toml").read_text()).partition("[[data.files]]")[0]
        head = re.sub(r'\[obtained\].*?\n\n', '[obtained]\n"1.00" = "observed"\n\n', head, flags=re.S)
        head = re.sub(r'^point = \[.*\]$', 'point = ["1.00"]', head, flags=re.M).replace('format = "npz-v1"', 'format = "npz-sized-v1"')
        (new / "m.toml").write_text(head + "\n".join(block(e) for e in entries))
        env = {**os.environ, "CC_DATA_ROOT": str(REAL)}
        add = subprocess.run([sys.executable, str(repo / "bin" / "cc"), "data", "add", iid], cwd=repo, env=env, capture_output=True, text=True)
        check("S3 bin/cc data add pins the sixty files", add.returncode == 0, (add.stdout + add.stderr)[-400:])

        def mine():
            found, _ = declare.validate(repo, iid)
            return [f for f in found if getattr(f, "loc", None) and (re.search(r"(couplings|transducer)\.toml:", f.loc) or ":data" in f.loc)], found
        ours, found = mine()
        print("     validate findings elsewhere (reported, not asserted):", [f.loc for f in found if f not in ours][:6])
        check("S3 validate: no finding at couplings.toml, transducer.toml or data.*", ours == [], str([(f.loc, f.msg) for f in ours][:4]))
        cc = repo / "cc.toml"
        keep = cc.read_text()
        cc.write_text(keep.replace(', "npz-sized-v1"', ""))
        ours, _ = mine()
        cc.write_text(keep)
        check("S6 without the alphabet entry the input is refused at data.format", any(f.loc.endswith("m.toml:data.format") for f in ours), str([f.loc for f in ours][:4]))
        ours, _ = mine()
        check("S6 with the entry restored there is none", not any(f.loc.endswith("m.toml:data.format") for f in ours))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
        shutil.rmtree(store, ignore_errors=True)
        if store.parent.is_dir() and not any(store.parent.iterdir()):
            store.parent.rmdir()   # the declared store's parent, when no other run holds a file in it


def s4():
    import sampler
    tmp = Path(tempfile.mkdtemp(prefix="s4-"))
    try:
        (tmp / "data").mkdir()
        for n in (*sampler.PINS, sampler.SO):
            (tmp / n).parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(REAL.parent / n, tmp / n)
        check("S4 toolset_of(<tmp>/data) is <tmp>", sampler.toolset_of(tmp / "data") == tmp)
        check("S4 unchanged tools load", not isinstance(sampler.load(tmp), sampler.Mismatch))
        f = tmp / "tools" / "flow.py"
        f.write_bytes(f.read_bytes() + b"\n")
        check("S4 one byte changed in flow.py is Mismatch('tools/flow.py')", sampler.load(tmp) == sampler.Mismatch("tools/flow.py"), str(sampler.load(tmp)))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def s5():
    import sampler
    t, run = tools(), sampler.Run(2, 1, 1)
    e = raises(lambda: sampler.sample(t, 0.44, 0.0, 27, "cold", 3_100_000_000, run), KeyError)
    check("S5a an unknown start raises KeyError('cold')", e is not None and e.args[0] == "cold", str(e))
    e = raises(lambda: sampler.sample(t, 0.44, 0.0, 30, "random", 3_100_000_000, run), KeyError)
    check("S5b an unknown size raises KeyError(30)", e is not None and e.args[0] == 30, str(e))


def s7():
    import sampler
    check("S7 seed_of random", sampler.seed_of("1282-v10", "poc", "1.00", 27, "random", "pilot") == 3110426675, str(sampler.seed_of("1282-v10", "poc", "1.00", 27, "random", "pilot")))
    check("S7 seed_of ordered", sampler.seed_of("1282-v10", "poc", "1.00", 27, "ordered", "pilot") == 3067375471, str(sampler.seed_of("1282-v10", "poc", "1.00", 27, "ordered", "pilot")))


def s8():
    import sampler
    check("S8 FAMILY_H is {poc 0.0, decoy 0.02}", sampler.FAMILY_H == {"poc": 0.0, "decoy": 0.02}, str(sampler.FAMILY_H))
    t, run, seed = tools(), sampler.Run(20, 1, 10), 3_100_000_000
    (a, ca), (b, cb) = (sampler.sample(t, 0.44, sampler.FAMILY_H[F], 27, "random", seed, run) for F in ("poc", "decoy"))
    check("S8 one seed, one cell: poc and decoy arrays differ", arrays_of(a) != arrays_of(b))
    check("S8 Call.h is each family's value", (ca.h, cb.h) == (0.0, 0.02), str((ca.h, cb.h)))


def s9():
    """S9 the .so is bound to the pins: the toolset's isfield.rs changed by one byte, PINS patched to its new sha (restored after), no rebuild -> the built .so still carries the old source."""
    import sampler
    tmp, keep = Path(tempfile.mkdtemp(prefix="s9-")), dict(sampler.PINS)
    try:
        for n in (*sampler.PINS, sampler.SO):
            (tmp / n).parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(REAL.parent / n, tmp / n)
        check("S9 unchanged toolset (with its .so) loads", not isinstance(sampler.load(tmp), sampler.Mismatch))
        f = tmp / sampler.SRC
        f.write_bytes(f.read_bytes() + b"\n")
        sampler.PINS[sampler.SRC] = hashlib.sha256(f.read_bytes()).hexdigest()
        got = sampler.load(tmp)
        check("S9 isfield.rs changed by one byte, pin patched, no rebuild: Mismatch('tools/rust_samplers.so')", got == sampler.Mismatch(sampler.SO), str(got))
        (tmp / sampler.SO).unlink()
        got = sampler.load(tmp)
        check("S9 an absent .so is Mismatch('tools/rust_samplers.so')", got == sampler.Mismatch(sampler.SO), str(got))
    finally:
        sampler.PINS.clear()
        sampler.PINS.update(keep)
        shutil.rmtree(tmp, ignore_errors=True)


for n, f in (("S1", s1), ("S2", s2), ("S3/S6", s3_s6), ("S4", s4), ("S5", s5), ("S7", s7), ("S8", s8), ("S9", s9)):
    guarded(n, f)
print("test_sampler: " + ("FAILED" if bad else "all passed"))
sys.exit(1 if bad else 0)
