"""test_island_table - plan 0884 P2.1: the island-table-v1 reader (cc/formats.py csv) and the one-side window cutter (cc/windows.py).
(1) a planted 3 x 3 table (one vacant site, the deposit's \\r\\r\\n terminator) reads as the expected s[4, 3, 3] int8, bit for bit; (2) a moment 0.5 is refused with the exact line;
(3) a repeated (row, col) is refused with the exact line; (4) a non-integer index and a ragged row are refused; (5) the cutter returns the expected slice of a planted 5 x 7 stack,
refuses a window that does not fit, and its origin table is total over cc.toml alphabets.window_origin; (6) formats.problems names a window that does not fit."""
import sys
import tempfile
import tomllib
from pathlib import Path
import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path[:0] = [str(ROOT / "cc"), str(ROOT / "cc" / "instruments")]
import formats  # noqa: E402
import windows  # noqa: E402

bad = []


def check(name, ok, why=""):
    print(("ok   " if ok else "FAIL ") + name + ("" if ok else f": {why}"))
    if not ok:
        bad.append(name)


tmp = Path(tempfile.mkdtemp(prefix="island-table-"))


def put(name, lines, eol="\r\r\n"):
    f = tmp / name
    f.write_bytes((eol.join(lines) + eol).encode())
    return f


def refusal(f):
    s, why = formats._island_table(f)
    return why if s is None else None


# (1) the planted 3 x 3 table: sites (5, 20) .. (7, 22) except (6, 21) vacant; four frames; indices start away from 0 (the extent-min rule)
grid = {(r, c): [(-1.0) ** (r + c + k) for k in range(4)] for r in (5, 6, 7) for c in (20, 21, 22) if (r, c) != (6, 21)}
f = put("p3.csv", [",".join([str(float(r)), str(float(c)), *map(str, v)]) for (r, c), v in grid.items()])
s, why = formats._island_table(f)
want = np.zeros((4, 3, 3), np.int8)
for (r, c), v in grid.items():
    want[:, r - 5, c - 20] = v
check("3 x 3 table reads bit for bit, vacant site 0, int8, \\r\\r\\n terminator", why is None and s.dtype == np.int8 and s.shape == (4, 3, 3) and np.array_equal(s, want) and s[0, 1, 1] == 0, f"{why} {None if s is None else s.tolist()}")
check("header shape through the registered reader", formats.HEADER["csv"](f, "s")[0] == (4, 3, 3))
# (2)-(4) refusals, each with its exact text
r0 = ["2.0,14.0,1.0,-1.0", "2.0,15.0,-1.0,1.0", "3.0,14.0,1.0,1.0"]
check("moment 0.5 refused with its line", refusal(put("m.csv", r0[:2] + ["3.0,14.0,0.5,1.0", "3.0,15.0,1.0,1.0"])) == "m.csv line 3: moment 0.5 is not one of [-1, 1]")
check("repeated (row, col) refused with its line", refusal(put("d.csv", r0 + ["2.0,15.0,1.0,1.0"])) == "d.csv line 4: (row, col) = (2, 15) is listed twice")
check("non-integer index refused", refusal(put("i.csv", r0[:1] + ["2.5,15.0,1.0,1.0"])) == "i.csv line 2: row, col = 2.5, 15.0 is not an integer index")
check("ragged row refused", refusal(put("r.csv", r0[:1] + ["2.0,15.0,1.0"])).startswith("r.csv line 2: 3 fields (the first row has 4"))
check("non-number refused", refusal(put("n.csv", r0[:1] + ["2.0,15.0,x,1.0"])) == "n.csv line 2: a field is not a number")
# (5) the cutter
st = np.arange(2 * 5 * 7, dtype=np.int8).reshape(2, 5, 7)
w = {"side": 3, "origin": "extent-min"}
check("cutter returns the origin slice", np.array_equal(windows.crop(st, w), st[:, :3, :3]) and windows.window_shape(st.shape, w) == (2, 3, 3))
check("cutter refuses a window larger than the extent", windows.window_shape(st.shape, {"side": 6, "origin": "extent-min"}) is None)
try:
    windows.crop(st, {"side": 6, "origin": "extent-min"})
    check("crop of a window that does not fit raises", False, "no exception")
except ValueError as e:
    check("crop of a window that does not fit raises", "does not fit a stack of extent 5 x 7" in str(e), str(e))
cfg = tomllib.loads((ROOT / "cc.toml").read_text())
check("origin table is total over cc.toml alphabets.window_origin", sorted(windows.ORIGINS) == sorted(cfg["alphabets"]["window_origin"]))
# (6) formats.problems names the window that does not fit (a 3 x 3 file, side 5)
m = {"windows": {"side": 5, "origin": "extent-min"}, "observable": {"final_size": 1, "levels": [1]}, "block_map": {"name": "majority-occupied3", "factor": 3}, "axes": {"size": [5]}}
got = formats.problems("island-table-v1", "data.files[0]", "GL", {"key": "s"}, {"path": "p3.csv", "size": 5}, f, m)
check("problems: a window larger than the file is named", len(got) == 1 and "extent 3 x 3; the declared window side 5 at origin extent-min does not fit" in got[0][1], got)
sys.exit(1 if bad else 0)
