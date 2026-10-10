"""test_bench - plan 0932 P1: the benchmark manifest generator + verifier (cc/bench.py).
A1 verify passes on an intact scratch root, and is seen RED twice with distinct messages (one byte flipped; one file removed).
A2 a role outside the declared alphabet is refused at load (planted row, in ROWS.toml and in MANIFEST.toml).
Identity: every real CC-side row whose path is in FROZEN.json hashes to the FROZEN.json value; generate() refuses (writes nothing) when bytes are absent.
Pure: no data root needed (the real M1/M7 sets are exercised only through the absent-bytes refusal)."""
import json
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path[:0] = [str(ROOT / "cc")]
import bench  # noqa: E402

bad = []


def check(name, ok, why=""):
    print(("ok   " if ok else "FAIL ") + name + ("" if ok else f": {why}"))
    if not ok:
        bad.append(name)


def refused(fn, *a):
    try:
        fn(*a)
    except bench.Refused as r:
        return str(r)
    return None


tmp = Path(tempfile.mkdtemp())
try:
    cc, dr = tmp / "cc", tmp / "data"
    (cc / "cases").mkdir(parents=True)
    (dr / "mapA").mkdir(parents=True)
    (cc / "cases/x.toml").write_text("a = 1\n")
    (dr / "mapA/f1.npz").write_bytes(b"one" * 100)
    (dr / "mapA/f2.npz").write_bytes(b"two" * 100)
    (dr / "mapA/LIST.tsv").write_text("key\tfile\tsha256\n1\tf1.npz\tx\n2\tf2.npz\tx\n")
    rows = tmp / "ROWS.toml"
    rows.write_text('schema = 1\nroles = ["map", "input", "truth", "prediction"]\n[[row]]\nid = "case:x"\nrole = "truth"\nroot = "cc"\npath = "cases/x.toml"\nsource = "t"\n'
                    '[[set]]\nid = "A"\nrole = "map"\nroot = "data"\npath = "mapA"\nlisted_by = "LIST.tsv"\nextra = []\nsource = "t"\n')
    roots, man = {"cc": cc, "data": dr}, tmp / "MANIFEST.toml"
    n, s = bench.generate(rows, man, roots)
    check("generate: 1 row + 3 set files (the list + 2 named), 1 set", (n, s) == (4, 1), f"{(n, s)}")
    check("A1 verify passes on the intact scratch root", bench.verify(man, roots) == [])
    f1 = dr / "mapA/f1.npz"
    raw = f1.read_bytes()
    f1.write_bytes(bytes([raw[0] ^ 1]) + raw[1:])
    r1 = bench.verify(man, roots)
    check("A1 RED: one byte flipped -> a MISMATCH line naming the file", len(r1) >= 1 and r1[0].startswith("MISMATCH") and "f1.npz" in r1[0], str(r1))
    f1.write_bytes(raw)
    (dr / "mapA/f2.npz").unlink()
    r2 = bench.verify(man, roots)
    check("A1 RED: one file removed -> an ABSENT line naming the file, a different message", len(r2) >= 1 and r2[0].startswith("ABSENT") and "f2.npz" in r2[0] and r2[0].split()[0] != r1[0].split()[0], str(r2))
    (dr / "mapA/f2.npz").write_bytes(b"two" * 100)
    check("restored root verifies again", bench.verify(man, roots) == [])
    # A2: planted role
    planted = tmp / "ROWS-bad.toml"
    planted.write_text(rows.read_text().replace('role = "truth"', 'role = "decoy"'))
    msg = refused(bench.load_rows, planted)
    check("A2 RED: a planted role outside the alphabet is refused at load of ROWS.toml, naming the row", msg is not None and "case:x" in msg and "decoy" in msg, str(msg))
    mb = tmp / "MANIFEST-bad.toml"
    mb.write_text(man.read_text().replace('role = "truth"', 'role = "decoy"', 1))
    msg = refused(bench.load_manifest, mb)
    check("A2 RED: the same in MANIFEST.toml", msg is not None and "decoy" in msg, str(msg))
    check("A2 green: the real ROWS.toml loads", refused(bench.load_rows, ROOT / "benchmark/ROWS.toml") is None)
    # absent bytes: nothing written
    out = tmp / "none.toml"
    msg = refused(bench.generate, rows, out, {"cc": cc, "data": tmp / "empty"})
    check("generate refuses and writes nothing when bytes are absent", msg is not None and not out.exists(), str(msg))
finally:
    shutil.rmtree(tmp, ignore_errors=True)

# identity: real CC-side rows vs FROZEN.json
fz = json.load(open(ROOT / "FROZEN.json"))["files"]
real = bench.load_rows(ROOT / "benchmark/ROWS.toml")
cc_rows = [r for r in real["row"] if r["path"] in fz]
check("identity: some real rows are in FROZEN.json", len(cc_rows) > 0)
wrong = [r["path"] for r in cc_rows if bench.sha_of(ROOT / r["path"])[0] != fz[r["path"]]]
check("identity: every real row in FROZEN.json hashes to its FROZEN.json value", not wrong, str(wrong[:3]))
check("every real CC-side row exists", all((ROOT / r["path"]).is_file() for r in real["row"]))
ids = [r["id"] for r in real["row"]]
check("row ids unique", len(ids) == len(set(ids)))

print("test_bench: " + ("FAIL " + str(bad) if bad else "ok"))
sys.exit(1 if bad else 0)
