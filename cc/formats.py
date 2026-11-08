"""formats.py - the stack formats: readers and schema checks (plumbing; plan 0873 A1). A format is DATA: cc.toml [formats.<name>]
names its raw dims, its dtypes, the array kinds the door REDUCES from it (`reduces`) and one reader module per file extension; this
file holds no per-format code. A stack is s[N, L, L]; the levels it reduces to are derived from (L, final_size, factor), never trusted."""
import importlib.util
import zipfile
from functools import lru_cache
from pathlib import Path
import numpy as np
from numpy.lib import format as npy
import reduce
import registry
import windows

ROOT = Path(__file__).resolve().parent.parent


@lru_cache(maxsize=None)
def schemas(root=str(ROOT)):
    """{format name: schema} for every stack format cc.toml declares (a format with no table is a plain array file)."""
    return registry.config(root).get("formats", {})


def have(module):
    return importlib.util.find_spec(module) is not None


def header(path, key):
    """(shape, dtype, None) of the stored stack without loading it, or (None, None, the keys the file holds)."""
    if Path(path).suffix == ".npz":
        with zipfile.ZipFile(path) as z:
            keys = [n[:-4] for n in z.namelist() if n.endswith(".npy")]
            return _head(z.open(key + ".npy")) if key in keys else (None, None, keys)
    with open(path, "rb") as f:
        return _head(f)


def head_of(f):
    """(shape, dtype, None) from an open npy stream positioned at its magic."""
    return _head(f)


def _head(f):
    v = npy.read_magic(f)
    shape, _, dtype = npy.read_array_header_1_0(f) if v == (1, 0) else npy.read_array_header_2_0(f)
    return shape, dtype, None


def _tiff_header(path, key):
    import tifffile
    with tifffile.TiffFile(path) as t:
        return t.series[0].shape, t.series[0].dtype, None


def _tiff_read(path, key):
    import tifffile
    return tifffile.imread(path)


def _npy_read(path, key):
    z = np.load(path)
    return z if isinstance(z, np.ndarray) else z[key]


def _island_table(path):
    """(s[frames, H, W] int8, None) or (None, the refusal naming the line) for a table of islands (cc.toml [formats.island-table-v1], plan 0884): one row per island,
    row, col, then one moment per frame; the record terminator is split on \n and stripped of every \r (the deposit writes \r\r\n). A moment outside `values`, a
    non-integer index, a ragged row or a repeated (row, col) is a refusal, never a repair. Unlisted sites hold `vacant`; H, W are the file's own extents."""
    sch, name = schemas()["island-table-v1"], Path(path).name
    rows = [(i, ln.decode().split(",")) for i, ln in enumerate(Path(path).read_bytes().split(b"\n"), 1) if ln.rstrip(b"\r")]
    seen, cells = set(), []
    for i, f in rows:
        try:
            v = [float(x) for x in f]
        except ValueError:
            return None, f"{name} line {i}: a field is not a number"
        if len(v) != len(rows[0][1]) or len(v) < 3:
            return None, f"{name} line {i}: {len(v)} fields (the first row has {len(rows[0][1])}; a row is row, col and at least one moment)"
        bad = [x for x in v[2:] if x not in sch["values"]]
        key = (v[0], v[1])
        if v[0] != int(v[0]) or v[1] != int(v[1]):
            return None, f"{name} line {i}: row, col = {v[0]}, {v[1]} is not an integer index"
        if bad:
            return None, f"{name} line {i}: moment {bad[0]} is not one of {sch['values']}"
        if key in seen:
            return None, f"{name} line {i}: (row, col) = ({int(key[0])}, {int(key[1])}) is listed twice"
        seen.add(key)
        cells.append((int(v[0]), int(v[1]), v[2:]))
    r0, c0 = min(r for r, _, _ in cells), min(c for _, c, _ in cells)
    s = np.full((len(cells[0][2]), max(r for r, _, _ in cells) - r0 + 1, max(c for _, c, _ in cells) - c0 + 1), sch["vacant"], np.int8)
    for r, c, f in cells:
        s[:, r - r0, c - c0] = f
    return s, None


def _csv_header(path, key):
    s, why = _island_table(path)
    return (None, None, why) if s is None else (s.shape, s.dtype, None)


def _csv_read(path, key):
    s, why = _island_table(path)
    if s is None:
        raise ValueError(why)
    return s


HEADER = {"numpy": header, "tifffile": _tiff_header, "csv": _csv_header}
READ = {"numpy": _npy_read, "tifffile": _tiff_read, "csv": _csv_read}


def levels_for(L, final, factor):
    """The number of block levels of an L-lattice that blocks down to `final` by `factor` (L = final * factor^k gives k + 1), else None."""
    if factor < 2 or final < 1:
        return None
    n = 1
    while final < L:
        final, n = final * factor, n + 1
    return n if final == L else None


def shape_of(fmt, path, key, root=str(ROOT), window=None):
    """The shape of the stored stack (after the input's declared [windows], if any), read from its header through the reader its extension names."""
    shape = HEADER[schemas(root)[fmt]["readers"][Path(path).suffix]](path, key)[0]
    return shape if window is None else windows.window_shape(shape, window)


def read(fmt, path, key, root=str(ROOT), window=None):
    """The raw stack s[N, L, L] of one file through the reader its extension names, cut to the input's declared [windows] if it has one."""
    s = READ[schemas(root)[fmt]["readers"][Path(path).suffix]](path, key)
    return s if window is None else windows.crop(s, window)


def problems(fmt, loc, name, a, b, path, m, root=str(ROOT)):
    """[(field, message, Next)] for one reduced array (G or GL) of a block of a stack-format input: the file, its reader, its stack
    against cc.toml [formats.<fmt>], and the levels derived from (L, final_size, factor) against what m.toml declares."""
    sch, ext, at_ = schemas(root)[fmt], Path(path).suffix, f"{loc}.arrays.{name}"
    mod = sch["readers"].get(ext)
    if mod is None:
        return [(f"{loc}.path", f"{b['path']}: '{ext}' is not a file of format {fmt}", f"use a file with one of: {' '.join(sch['readers'])}")]
    if not have(mod):
        return [(f"{loc}.path", f"{b['path']}: no reader for {ext} files ({mod} is not importable)",
                 f"pip install {sch.get('pip', {}).get(mod, mod)}, or convert the stack to .npy (shape [N, L, L])")]
    shape, dtype, keys = HEADER[mod](path, a["key"])
    if shape is None:
        return [(at_, keys, "fix the file: a table is refused, never repaired")] if isinstance(keys, str) else [(at_, f"key '{a['key']}' absent from {b['path']} (keys: {' '.join(keys)})", "fix the key")]
    w = m.get("windows")
    if w is not None and windows.window_shape(shape, w) is None:
        return [(f"{loc}.path", f"{b['path']} has extent {shape[1]} x {shape[2]}; the declared window side {w['side']} at origin {w['origin']} does not fit",
                 "declare a smaller [windows] side, or leave the file out of the input")]
    shape = shape if w is None else windows.window_shape(shape, w)
    if len(shape) != sch["dims"] or shape[1] != shape[2] or str(dtype) not in sch["dtypes"]:
        return [(at_, f"{b['path']} stores {a['key']} as {str(dtype)} {list(shape)}; {fmt} needs {sch['dims']}-D [N, L, L] of {'/'.join(sch['dtypes'])}",
                 "write the stack as s[N, L, L], or declare another data.format")]
    ob, bm = m.get("observable"), m.get("block_map")
    if ob is None or bm is None:
        return [(at_, f"a {fmt} stack is reduced through the declared map, so m.toml needs [observable] and [block_map]", "add both tables")]
    L, out = shape[1], []
    out += [(f"{loc}.size", f"stored L {L} differs from the declared size {b['size']}", "fix size, or the file")] if L != b["size"] else []
    n = levels_for(L, ob["final_size"], bm["factor"])
    out += [("block_map.name", f"'{bm['name']}' is not a declared block map", f"use one of: {' '.join(reduce.MAPS)}")] if bm["name"] not in reduce.MAPS else []
    out += [("observable.final_size", f"L {L} is not final_size * factor^k (final_size {ob['final_size']}, factor {bm['factor']})",
             "set [observable] final_size and [block_map] factor so that L = final_size * factor^k, or fix the file")] if n is None else []
    want = ob["levels"][m["axes"]["size"].index(b["size"])] if b["size"] in m["axes"]["size"] else n
    out += [("observable.levels", f"{b['path']} reduces to {n} levels but observable.levels declares {want} for size {b['size']}",
             "set observable.levels to the derived level count")] if n is not None and want != n else []
    k = a.get("level")
    return out + ([(at_, f"level {k} is outside the {n} derived levels", f"use a level from 0 to {n - 1}")] if k is not None and n is not None and not 0 <= k < n else [])
