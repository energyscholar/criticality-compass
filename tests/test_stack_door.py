"""test_stack_door - plan 0873 A1 (items 2-4): the stack door. A planted wrong final_size gives its exact finding; a planted TIFF with no
reader gives the exact Next line; a limited block map that keeps level 0 is refused; the reduced-array cache is keyed and ignored by git;
and the input x4s-stack (the x4-ising-field declarations over the raw X4s snapshots) reads what the frozen x4-ising-field reads at
(0.46, h 0, plus): every estimate and every cell equal (the interval ends differ: the bootstrap draws one index set per block in
data.files order, and this input has 3 blocks where x4-ising-field has 18)."""
import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
from lib import bad, bootstrap, check  # noqa: E402
bootstrap(ROOT, "cc", "cc/instruments")
import declare  # noqa: E402
import detect  # noqa: E402
import door  # noqa: E402
import formats  # noqa: E402


def judge(text, **over):
    """The findings (as printed) of a planted input m.toml with `text`, located as tests/planted/x.toml."""
    with tempfile.TemporaryDirectory() as t:
        f = Path(t) / "planted" / "x.toml"
        f.parent.mkdir()
        f.write_text(text)
        return [declare.fmt(x).replace(str(f), "tests/planted/x.toml") for x in declare.check_file(f, ROOT, **over)]


base = (ROOT / "inputs" / "x4s-stack" / "m.toml").read_text().replace('id = "x4s-stack"', 'id = "x"')
check("the planted base (x4s-stack, id x) is clean", judge(base) == [], str(judge(base)))

# 1. a wrong final_size: the exact finding, and the fix removes it
wrong = base.replace("final_size = 9", "final_size = 10")
want = ("tests/planted/x.toml:observable.final_size: L 27 is not final_size * factor^k (final_size 10, factor 3)\n"
        "  Next: set [observable] final_size and [block_map] factor so that L = final_size * factor^k, or fix the file")
check("a planted final_size 10 gives the exact finding at L 27", want in judge(wrong), str(judge(wrong))[:400])
check("the planted final_size 9 no longer gives it", want not in judge(wrong.replace("final_size = 10", "final_size = 9")))
lv = base.replace("levels = [2, 3, 4]", "levels = [3, 4, 5]")
want = ("tests/planted/x.toml:observable.levels: x4s/K0.4600-h0.0000-L27-plus.npz reduces to 2 levels but observable.levels declares 3 for size 27\n"
        "  Next: set observable.levels to the derived level count")
check("a planted observable.levels that disagrees with the derived count gives its exact finding", want in judge(lv), str(judge(lv))[:400])

# 2. a TIFF with no reader: the exact Next line (the module is declared absent, whatever this machine holds)
with tempfile.TemporaryDirectory() as t:
    (Path(t) / "stack.tif").write_bytes(b"")
    first = base.index("[[data.files]]")
    second = base.index("[[data.files]]", first + 1)
    blk = base[first:second].replace("x4s/K0.4600-h0.0000-L27-plus.npz", "stack.tif")
    blk = "".join(ln + "\n" for ln in blk.splitlines() if not ln.startswith("arrays.E"))
    tif = (base[:first] + blk + "\n" + base[second:]).replace('format = "snapshots-v1"', 'format = "image-stack-v1"')
    real = formats.have
    formats.have = lambda mod: mod != "tifffile"
    try:
        got = judge(tif, data_root=t)
    finally:
        formats.have = real
    want = ("tests/planted/x.toml:data.files[0].path: stack.tif: no reader for .tif files (tifffile is not importable)\n"
            "  Next: pip install tifffile, or convert the stack to .npy (shape [N, L, L])")
    check("a planted .tif with no importable reader gives the exact Next line", want in got, str(got)[:500])
    (Path(t) / "stack.xyz").write_bytes(b"")
    other = judge(tif.replace("stack.tif", "stack.xyz"), data_root=t)
    check("an extension no reader names is refused with the readers listed",
          any("'.xyz' is not a file of format image-stack-v1" in x and "Next: use a file with one of: .npy .tif .tiff" in x for x in other), str(other)[:400])

# 3. level 0 exclusion: a limited block map that keeps level 0 is refused
lim = base.replace('limited = "none"', 'limited = "assigned"')
want = ("tests/planted/x.toml:observable.level_floor: block_map.limited = 'assigned' but level 0 is not excluded (level_floor 0)\n"
        "  Next: set [observable] level_floor = 1: the finest level carries the cell or instrument scale, not the system")
check("a planted limited = assigned without level_floor gives its exact finding", want in judge(lim), str(judge(lim))[:400])
check("with level_floor = 1 it is clean", judge(lim.replace("final_size = 9", "final_size = 9\nlevel_floor = 1")) == [])

# 4. the cache: keyed, reused, ignored by git
m = declare.load(ROOT / "inputs" / "x4s-stack" / "m.toml")[0]
root = declare.Ctx(ROOT).data_root
first = door.load_blocks(m, root)
files = sorted((ROOT / "results" / "reduced" / "x4s-stack").glob("*.npz"))
second = door.load_blocks(m, root)
check("the reduced cache holds one file per raw stack (3), named by a sha", len(files) >= 3 and all(len(f.stem) == 64 for f in files), str(files))
check("a second load (a cache hit) returns the same arrays", all(a[0] == b[0] and all(a[1][k].tobytes() == b[1][k].tobytes() for k in a[1]) for a, b in zip(first, second)))
check("results/reduced is ignored by git", subprocess.run(["git", "check-ignore", "-q", "results/reduced/x4s-stack/x.npz"], cwd=ROOT).returncode == 0)

# 5. x4s-stack reads what the frozen x4-ising-field reads at (0.46, plus): estimates and cells equal
new = detect.run("x4s-stack", "v07-rules", write=False)
old = json.loads((ROOT / "results" / "x4-ising-field@v07-rules.json").read_text())
key = lambda r: (r["instrument"], r["column"], json.dumps(r["unit"]))  # noqa: E731
want = {key(r): r for r in old["readings"] if r["unit"] == {"point": "0.46"}}
rows = [r for r in new["readings"] if r["cell"] not in ("NOT-MEASURED",)]
check("x4s-stack declares instruments that measure at least 5 readings", len(rows) >= 5, str(len(rows)))
diff = [(key(r), f) for r in rows for f in ("estimate", "cell", "code", "per_size", "flags", "reason", "eps") if r[f] != want[key(r)][f]]
check("every estimate, cell, code, flag and reason of x4s-stack equals the frozen x4-ising-field at (0.46, plus)", not diff, str(diff)[:500])
print("".join(f"FAILED {x}\n" for x in bad) + "test_stack_door: " + ("FAILED" if bad else "all passed"))
sys.exit(1 if bad else 0)
